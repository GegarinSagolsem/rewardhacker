"""Shared helpers for the API tests (fixtures live in conftest.py)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from rewardhacker.llm import Turn
from rewardhacker.models import AgentRun, AgentStep, LLMUsage, ProbeResult, Report, Trial

TASK_DIR = Path(__file__).parent.parent / "loopbench" / "tasks" / "weak-output-check"
PASSWORD = "correct-horse-battery"


def zip_dir(src: Path, prefix: str = "") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                zf.write(p, prefix + p.relative_to(src).as_posix())
    return buf.getvalue()


def zip_entries(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


class SpecLLM:
    """Scripted LLM for spec checks: always reports one issue citing excerpt 1."""

    model = "fake-llm"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def chat(self, system, tools):  # pragma: no cover - not used by the API
        raise NotImplementedError

    def complete_json(self, system: str, prompt: str):
        self.prompts.append(prompt)
        issue = {
            "excerpt": 1,
            "severity": "high",
            "issue": "Tests check format only.",
            "suggestion": "Assert it.",
        }
        return {"summary": "One problem.", "issues": [issue]}, Turn(
            input_tokens=500, output_tokens=40, cost_usd=2e-4
        )


def login(client, email: str) -> dict:
    tok = client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def register(client, email: str) -> dict:
    assert client.post("/api/auth/register", json={"email": email, "password": PASSWORD}).status_code == 201
    return login(client, email)


def make_org(client, headers) -> str:
    r = client.post("/api/orgs", json={"name": "Acme RL"}, headers=headers)
    assert r.status_code == 201 and r.json()["role"] == "admin"
    return r.json()["id"]


def upload(client, org, headers, data: bytes):
    return client.post(
        f"/api/orgs/{org}/tasks", files={"file": ("task.zip", data, "application/zip")}, headers=headers
    )


def fake_report(task_id: str) -> Report:
    agent = AgentRun(
        steps=[AgentStep(step=1, tool="bash", args={"command": "echo 'total: 0' > report.txt"})],
        explanation="wrote a placeholder total",
        stop_reason="submitted",
        usage=LLMUsage(model="fake", calls=2, cost_usd=0.001),
        judgement="shortcut",
    )
    probe = ProbeResult(
        name="adversary",
        title="LLM adversary",
        expect_pass=False,
        status="finding",
        trials=[Trial(index=0, passed=True, agent=agent)],
    )
    return Report(
        task_id=task_id,
        image="img",
        rewardhacker_version="test",
        started_at="2026-11-14T00:00:00+00:00",
        duration_sec=1.0,
        probes=[probe],
        findings=[],
        score=50,
        verdict="exploitable",
        llm_usage=agent.usage,
    )
