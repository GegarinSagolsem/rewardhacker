"""MCP server: lets AI assistants (Claude Code, Claude Desktop, ...) use RewardHacker.

It is a thin client of the REST API, authenticated with an org API key, so every call goes
through the same role checks and lands in the same audit log as the dashboard.

    RH_API_URL=http://127.0.0.1:8000 RH_API_KEY=rh_... rh mcp     # stdio transport
"""

from __future__ import annotations

import io
import logging
import os
import time
import zipfile
from pathlib import Path
from typing import Any

import httpx

from .config import load_dotenv
from .models import Report
from .reporting import report_markdown
from .taskspec import TaskSpec, TaskSpecError

MAX_BUNDLE_BYTES = 20 * 1024 * 1024
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", ".pytest_cache"}

INSTRUCTIONS = """\
RewardHacker red-teams reinforcement-learning coding tasks: it checks whether a task's reward can
be earned without doing the work (free reward, tamperable tests, LLM-found shortcuts), whether
the reference solution passes, and whether the verifier is flaky.

Typical flow: validate_task(path) -> upload_task(path) -> start_run(task, wait=true) -> read the
verdict and findings -> fix the task -> repeat. check_guidelines(task) compares a task with the
team's written guidelines. Tasks and runs can be referred to by full id, 8-character id prefix,
or (for tasks) the id in task.yaml. include_llm=true adds the LLM adversary (~$0.002, capped).
"""


class RewardHackerError(RuntimeError):
    pass


class RewardHackerClient:
    """Minimal REST client for an org API key."""

    def __init__(self, base_url: str, api_key: str, http: httpx.Client | None = None):
        self._http = http or httpx.Client(base_url=base_url.rstrip("/"), timeout=60)
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._key: dict | None = None

    def _req(self, method: str, path: str, **kw: Any) -> Any:
        try:
            r = self._http.request(method, path, headers=self._headers, **kw)
        except httpx.HTTPError as exc:
            raise RewardHackerError(f"cannot reach the RewardHacker API: {exc}") from None
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail")
            except ValueError:
                detail = r.text
            raise RewardHackerError(f"API error {r.status_code}: {detail}")
        return r.json() if r.content else None

    @property
    def key(self) -> dict:
        if self._key is None:
            self._key = self._req("GET", "/api/auth/key")
        return self._key

    @property
    def org(self) -> str:
        return self.key["org_id"]

    def tasks(self) -> list[dict]:
        return self._req("GET", f"/api/orgs/{self.org}/tasks", params={"limit": 200})

    def task(self, task_id: str) -> dict:
        return self._req("GET", f"/api/orgs/{self.org}/tasks/{task_id}")

    def upload(self, data: bytes, filename: str) -> dict:
        files = {"file": (filename, data, "application/zip")}
        return self._req("POST", f"/api/orgs/{self.org}/tasks", files=files)

    def runs(self, task_id: str | None = None, status: str | None = None) -> list[dict]:
        params: dict[str, Any] = {"limit": 200}
        if task_id:
            params["task_id"] = task_id
        if status:
            params["status"] = status
        return self._req("GET", f"/api/orgs/{self.org}/runs", params=params)

    def run(self, run_id: str) -> dict:
        return self._req("GET", f"/api/orgs/{self.org}/runs/{run_id}")

    def traces(self, run_id: str) -> list[dict]:
        return self._req("GET", f"/api/orgs/{self.org}/runs/{run_id}/traces")

    def start_run(self, task_id: str, include_llm: bool) -> dict:
        return self._req(
            "POST", f"/api/orgs/{self.org}/tasks/{task_id}/runs", json={"include_llm": include_llm}
        )

    def spec_check(self, task_id: str) -> dict:
        return self._req("POST", f"/api/orgs/{self.org}/tasks/{task_id}/spec-checks")

    # --- reference resolution: full id, id prefix, or task.yaml id ---

    def resolve_task(self, ref: str) -> dict:
        ref = ref.strip()
        tasks = self.tasks()  # newest first
        for t in tasks:
            if t["id"] == ref:
                return t
        matches = [t for t in tasks if t["id"].startswith(ref)] if len(ref) >= 6 else []
        matches = matches or [t for t in tasks if t["spec_id"] == ref]
        if not matches:
            raise RewardHackerError(f"no task matches {ref!r}; call list_tasks to see what exists")
        return matches[0]

    def resolve_run(self, ref: str) -> dict:
        ref = ref.strip()
        if len(ref) == 32:
            return self.run(ref)
        matches = [r for r in self.runs() if r["id"].startswith(ref)] if len(ref) >= 6 else []
        if not matches:
            raise RewardHackerError(f"no run matches {ref!r}; call list_runs to see recent runs")
        return self.run(matches[0]["id"])


# ---------- formatting ----------


def _short(i: str | None) -> str:
    return (i or "")[:8]


def _run_line(r: dict, task_name: str | None = None) -> str:
    verdict = (r.get("verdict") or "-").upper() if r["status"] == "done" else r["status"]
    score = f"{r['score']}/100" if r.get("score") is not None else "-"
    llm = " +adversary" if r.get("include_llm") else ""
    name = f" {task_name}" if task_name else ""
    return f"- run `{_short(r['id'])}`{name}: **{verdict}** score {score}{llm} ({r['created_at'][:16]})"


def summarize_run(run: dict, task_name: str) -> str:
    status = run["status"]
    if status in ("queued", "running"):
        hint = " A worker (`rh worker`) must be running to process it." if status == "queued" else ""
        return f"Run `{_short(run['id'])}` on `{task_name}` is **{status}**.{hint}"
    if status == "failed":
        return f"Run `{_short(run['id'])}` on `{task_name}` **failed**: {run.get('error')}"
    report = run.get("report") or {}
    lines = [
        f"Run `{_short(run['id'])}` on `{task_name}`: **{(run.get('verdict') or '?').upper()}**, "
        f"score {run.get('score')}/100"
        + (f", LLM cost ${run['llm_cost_usd']:.4f}" if run.get("llm_cost_usd") else ""),
        "",
    ]
    findings = report.get("findings", [])
    if not findings:
        lines.append("No findings.")
    for f in findings:
        lines.append(f"- [{f['severity'].upper()}] {f['title']} (`{f['code']}`)")
        if f.get("recommendation"):
            lines.append(f"  Fix: {f['recommendation']}")
    lines += ["", "Call get_report for the full report, including the adversary's commands."]
    return "\n".join(lines)


def _zip_task(root: Path) -> bytes:
    buf = io.BytesIO()
    total = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(root.rglob("*")):
            if (
                any(part in SKIP_DIRS for part in p.relative_to(root).parts)
                or not p.is_file()
                or p.is_symlink()
            ):
                continue
            total += p.stat().st_size
            if total > MAX_BUNDLE_BYTES * 5:
                raise RewardHackerError("task folder is too large (over 100 MB uncompressed)")
            zf.write(p, p.relative_to(root).as_posix())
    data = buf.getvalue()
    if len(data) > MAX_BUNDLE_BYTES:
        raise RewardHackerError("zipped task is over 20 MB")
    return data


# ---------- the server ----------


def build_server(client: RewardHackerClient):
    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
    from mcp_types import ToolAnnotations

    from . import __version__

    server = MCPServer(name="rewardhacker", version=__version__, instructions=INSTRUCTIONS)
    read_only = ToolAnnotations(read_only_hint=True, open_world_hint=False)
    acts = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)

    def call(fn, *args, **kw):
        try:
            return fn(*args, **kw)
        except RewardHackerError as exc:
            raise ToolError(str(exc)) from None

    @server.tool(annotations=read_only)
    def whoami() -> str:
        """Which RewardHacker organization and role this connection acts as."""
        k = call(lambda: client.key)
        org, role, name = k["org_name"], k["role"], k["name"]
        return f'Organization **{org}** (`{k["org_id"]}`) as **{role}**, via API key "{name}".'

    @server.tool(annotations=read_only)
    def list_tasks() -> str:
        """List the organization's uploaded tasks with their latest verdict."""
        tasks = call(client.tasks)
        if not tasks:
            return "No tasks yet. Use upload_task to add one."
        latest: dict[str, dict] = {}
        for r in call(client.runs):
            latest.setdefault(r["task_id"], r)
        out = []
        for t in tasks:
            r = latest.get(t["id"])
            verdict = ((r.get("verdict") or r["status"]).upper()) if r else "not run"
            out.append(f"- `{t['spec_id']}` (task `{_short(t['id'])}`): {verdict}")
        return "\n".join(out)

    @server.tool(annotations=read_only)
    def validate_task(path: str) -> str:
        """Check a local task folder (with task.yaml) for format errors, without uploading it."""
        try:
            spec = TaskSpec.load(Path(path).expanduser())
        except TaskSpecError as exc:
            raise ToolError(f"invalid task: {exc}") from None
        ref = "yes" if spec.solution else "no"
        return f"OK: `{spec.id}`, verifier `{spec.verifier.command}`, reference solution: {ref}."

    @server.tool(annotations=acts)
    def upload_task(path: str) -> str:
        """Zip a local task folder (containing task.yaml) and upload it to the organization."""
        root = Path(path).expanduser().resolve()
        try:
            spec = TaskSpec.load(root)
        except TaskSpecError as exc:
            raise ToolError(f"invalid task: {exc}") from None
        task = call(client.upload, call(_zip_task, spec.root), f"{spec.id}.zip")
        tid = task["id"]
        return f"Uploaded `{task['spec_id']}` as task `{_short(tid)}` (full id `{tid}`). Next: start_run."

    @server.tool(annotations=read_only)
    def get_task(task: str) -> str:
        """A task's objective and recent runs. `task` = id, id prefix, or task.yaml id."""
        t = call(client.resolve_task, task)
        runs = call(client.runs, task_id=t["id"])[:10]
        lines = [
            f"# `{t['spec_id']}` (task `{t['id']}`)",
            "",
            "Objective:",
            t["objective"],
            "",
            "Recent runs:",
        ]
        lines += [_run_line(r) for r in runs] or ["- none"]
        return "\n".join(lines)

    @server.tool(annotations=acts)
    def start_run(task: str, include_llm: bool = False, wait: bool = True, timeout_sec: int = 600) -> str:
        """Queue a probe run for a task. With wait=true, poll until it finishes (needs a running
        `rh worker`) and return the verdict and findings. include_llm adds the LLM adversary."""
        t = call(client.resolve_task, task)
        run = call(client.start_run, t["id"], include_llm)
        if not wait:
            return summarize_run(run, t["spec_id"])
        deadline = time.monotonic() + max(10, min(timeout_sec, 1800))
        while run["status"] in ("queued", "running") and time.monotonic() < deadline:
            time.sleep(3)
            run = call(client.run, run["id"])
        text = summarize_run(run, t["spec_id"])
        if run["status"] in ("queued", "running"):
            text += f"\nStill {run['status']} after {timeout_sec}s; check later with get_run."
        return text

    @server.tool(annotations=read_only)
    def list_runs(status: str | None = None, task: str | None = None, limit: int = 20) -> str:
        """Recent runs, newest first. Optional filters: status (queued|running|done|failed), task."""
        task_id = call(client.resolve_task, task)["id"] if task else None
        runs = call(client.runs, task_id=task_id, status=status)[: max(1, min(limit, 100))]
        names = {t["id"]: t["spec_id"] for t in call(client.tasks)}
        return "\n".join(_run_line(r, names.get(r["task_id"])) for r in runs) or "No runs."

    @server.tool(annotations=read_only)
    def get_run(run: str) -> str:
        """Status, verdict and findings (with fixes) of one run. `run` = id or 8-char prefix."""
        r = call(client.resolve_run, run)
        return summarize_run(r, call(client.task, r["task_id"])["spec_id"])

    @server.tool(annotations=read_only)
    def get_report(run: str) -> str:
        """The full Markdown report for a finished run, including the adversary's commands."""
        r = call(client.resolve_run, run)
        if r["status"] != "done" or not r.get("report"):
            return summarize_run(r, call(client.task, r["task_id"])["spec_id"])
        traces = call(client.traces, r["id"]) if r.get("traces_stored") else []
        name = call(client.task, r["task_id"])["spec_id"]
        return report_markdown(
            Report.model_validate(r["report"]), task_name=name, run_id=r["id"], traces=traces
        )

    @server.tool(annotations=acts)
    def check_guidelines(task: str) -> str:
        """Compare a task with the organization's written guidelines (RAG + one LLM call, ~$0.001)."""
        t = call(client.resolve_task, task)
        res = call(client.spec_check, t["id"])["result"]
        lines = [f"Guideline check for `{t['spec_id']}`: {res.get('summary') or ''}", ""]
        for i in res.get("issues", []):
            where = f" (guideline: {i['heading']})" if i.get("heading") else ""
            lines.append(f"- [{i['severity'].upper()}] {i['issue']}{where}")
            if i.get("suggestion"):
                lines.append(f"  Fix: {i['suggestion']}")
        if not res.get("issues"):
            lines.append("No guideline problems found.")
        return "\n".join(lines)

    return server


def main() -> None:
    load_dotenv()
    key = os.environ.get("RH_API_KEY", "").strip()
    if not key.startswith("rh_"):
        raise SystemExit("RH_API_KEY must be set to an org API key (rh_...). Create one under API keys.")
    url = os.environ.get("RH_API_URL", "http://127.0.0.1:8000")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one INFO line per poll is noise
    build_server(RewardHackerClient(url, key)).run("stdio")
