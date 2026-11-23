"""Import Terminal-Bench 1 tasks (``original-tasks/<name>/``) into RewardHacker's task format.

Terminal-Bench 1 layout (Apache-2.0, https://github.com/harbor-framework/terminal-bench-1)::

    <name>/task.yaml            instruction, difficulty, timeouts, ...
    <name>/Dockerfile           build context = the task directory
    <name>/docker-compose.yaml  one "client" service in the tasks we support
    <name>/solution.sh          reference solution (run in the image's WORKDIR)
    <name>/run-tests.sh         installs uv + pytest, then runs pytest $TEST_DIR/test_outputs.py
    <name>/tests/               copied to $TEST_DIR (/tests) only at test time

Mapping, chosen to stay faithful to how Terminal-Bench itself runs a task:

* The agent runs as root (TB has no separate agent user) and has network access
  (``environment.network: bridge``), as TB agents do. RewardHacker refuses networked tasks
  unless the operator sets ``RH_ALLOW_TASK_NETWORK=1``; the web API never accepts them.
* ``run-tests.sh`` is copied next to the tests and run unchanged with ``TEST_DIR=/tests``.
* Files the agent must not see (tests, solution, run-tests.sh) are kept out of the build
  context, so a Dockerfile can't bake them into the image by accident.

Benchmark files carry a "never in training corpora" canary: imported tasks belong in a
git-ignored folder, never in a public repository.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml

TB_BASE_IMAGE = "ghcr.io/laude-institute/t-bench/"
TB_BASE_WORKDIR = "/app"  # WORKDIR of every TB base image (checked with docker image inspect)
# Not part of the agent's environment: copied in at verify/solve time, or TB-harness only.
HIDDEN = {"tests", "solution.sh", "solution.yaml", "run-tests.sh", "task.yaml", "docker-compose.yaml"}
ALLOWED_COMPOSE_KEYS = {
    "build",
    "image",
    "container_name",
    "command",
    "environment",
    "volumes",
    "working_dir",
}
MAX_TIMEOUT = 3600


class Unsupported(Exception):
    """The task can't be imported faithfully (the reason is reported, not hidden)."""


@dataclass
class Imported:
    name: str
    out_dir: Path | None
    skipped: str | None = None
    difficulty: str | None = None
    category: str | None = None


def _read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _is_idle_command(command) -> bool:
    """True for the `sleep infinity` keep-alive TB uses (our containers already start idle)."""
    if command is None:
        return True
    words = command if isinstance(command, list) else [command]
    text = " ".join(str(w) for w in words).strip()
    return text in {"sleep infinity", "sh -c sleep infinity"}


def _workdir(dockerfile: str, compose_service: dict) -> str:
    if wd := compose_service.get("working_dir"):
        return str(wd)
    found = re.findall(r"^\s*WORKDIR\s+(\S+)", dockerfile, re.M | re.I)
    if found:
        wd = found[-1].strip("\"'")
        if not wd.startswith("/") or "$" in wd:
            raise Unsupported(f"WORKDIR {wd!r} is relative or uses variables")
        return wd
    froms = re.findall(r"^\s*FROM\s+(?:--\S+\s+)*(\S+)", dockerfile, re.M | re.I)
    if froms and froms[-1].startswith(TB_BASE_IMAGE):
        return TB_BASE_WORKDIR
    raise Unsupported("no WORKDIR (Terminal-Bench requires one)")


def _check(src: Path) -> tuple[dict, dict, str]:
    files = {p.name for p in src.iterdir()}
    if "Dockerfile" not in files:
        raise Unsupported("no Dockerfile")
    if "solution.sh" not in files:
        raise Unsupported("no solution.sh (solution.yaml-only tasks are interactive)")
    if "run-tests.sh" not in files or not (src / "tests").is_dir():
        raise Unsupported("no run-tests.sh or tests/")
    compose = _read_yaml(src / "docker-compose.yaml") if "docker-compose.yaml" in files else {}
    services = compose.get("services") or {}
    if len(services) != 1:
        raise Unsupported(f"{len(services)} containers (only single-container tasks are supported)")
    service = next(iter(services.values())) or {}
    if extra := set(service) - ALLOWED_COMPOSE_KEYS:
        raise Unsupported(f"docker-compose options we don't reproduce: {', '.join(sorted(extra))}")
    if "command" in service and not _is_idle_command(service["command"]):
        # We start every container idle; a startup command (e.g. a server the task relies on)
        # would silently not run, so the task couldn't be reproduced faithfully.
        raise Unsupported(f"docker-compose startup command we don't run: {service['command']!r}")
    dockerfile = (src / "Dockerfile").read_text(encoding="utf-8")
    if re.search(r"^\s*(COPY|ADD)\s+.*\b(tests|solution\.sh|run-tests\.sh)\b", dockerfile, re.M | re.I):
        raise Unsupported("the Dockerfile copies tests or the solution into the image")
    return _read_yaml(src / "task.yaml"), service, dockerfile


def _clamp(value, default: int) -> int:
    try:
        return max(1, min(MAX_TIMEOUT, int(float(value))))
    except (TypeError, ValueError):
        return default


def convert(src: Path, out: Path) -> Imported:
    """Convert one TB1 task directory into ``out/<name>/``. Never partially writes on failure."""
    name = src.name
    try:
        meta, service, dockerfile = _check(src)
        workdir = _workdir(dockerfile, service)
        instruction = str(meta.get("instruction") or "").strip()
        if not instruction:
            raise Unsupported("empty instruction")
        task_id = re.sub(r"[^a-z0-9_-]", "-", name.lower())[:64].strip("-")
        if not task_id:
            raise Unsupported("name can't be turned into a task id")
    except Unsupported as exc:
        return Imported(name, None, skipped=str(exc))

    dest = out / task_id
    tmp = out / f".{task_id}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "environment").mkdir(parents=True)
    for item in src.iterdir():
        if item.name in HIDDEN:
            continue
        target = tmp / "environment" / item.name
        if item.is_dir():
            shutil.copytree(item, target, symlinks=True)
        else:
            shutil.copy2(item, target)
    shutil.copytree(src / "tests", tmp / "tests", symlinks=True)
    shutil.copy2(src / "run-tests.sh", tmp / "tests" / "run-tests.sh")
    (tmp / "solution").mkdir()
    shutil.copy2(src / "solution.sh", tmp / "solution" / "solution.sh")

    spec = {
        "id": task_id,
        "objective": instruction + "\n",
        "environment": {
            "dockerfile": "environment/Dockerfile",
            "context": "environment",
            "workdir": workdir,
            "network": "bridge",
        },
        "verifier": {
            # TB runs run-tests.sh in the container's working directory with TEST_DIR set.
            "command": "TEST_DIR=/tests bash /tests/run-tests.sh",
            "timeout_sec": min(
                MAX_TIMEOUT, _clamp(meta.get("max_test_timeout_sec"), 180) + 120
            ),  # + tool install
            "files": "tests",
            "mount_path": "/tests",
        },
        "solution": {
            "command": "bash /solution/solution.sh",
            "timeout_sec": _clamp(meta.get("max_agent_timeout_sec"), 900),
            "files": "solution",
            "mount_path": "/solution",
        },
        "limits": {"cpus": 2, "memory": "2g", "pids": 1024},
    }
    (tmp / "task.yaml").write_text(
        "# Imported from Terminal-Bench 1 (Apache-2.0) by `rh import-tb`. Do not commit:\n"
        "# benchmark data must never appear in training corpora.\n"
        + yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    (tmp / "SOURCE.txt").write_text(
        f"terminal-bench-1 original-tasks/{name}\n"
        f"difficulty: {meta.get('difficulty')}\ncategory: {meta.get('category')}\n",
        encoding="utf-8",
    )
    shutil.rmtree(dest, ignore_errors=True)
    tmp.rename(dest)
    return Imported(name, dest, difficulty=meta.get("difficulty"), category=meta.get("category"))


def import_all(source: Path, out: Path, names: list[str] | None = None) -> list[Imported]:
    """``source`` is TB1's ``original-tasks`` directory."""
    out.mkdir(parents=True, exist_ok=True)
    dirs = sorted(p for p in source.iterdir() if p.is_dir() and (not names or p.name in names))
    if names and (missing := set(names) - {d.name for d in dirs}):
        raise FileNotFoundError(f"not found in {source}: {', '.join(sorted(missing))}")
    return [convert(d, out) for d in dirs]
