"""Terminal-Bench 1 importer, on synthetic tasks (no benchmark data in this repo)."""

from __future__ import annotations

from pathlib import Path

import yaml

from rewardhacker.importers.terminal_bench import import_all
from rewardhacker.taskspec import TaskSpec


def _tb_task(
    root: Path,
    name: str,
    dockerfile: str = "FROM ghcr.io/laude-institute/t-bench/python-3-13:x\n",
    compose: dict | None = None,
    extra: dict[str, str] | None = None,
    test_timeout: float = 60.0,
) -> Path:
    d = root / name
    (d / "tests").mkdir(parents=True)
    (d / "task.yaml").write_text(
        yaml.safe_dump(
            {
                "instruction": "Write hi to /app/hi.txt",
                "difficulty": "easy",
                "category": "file-operations",
                "max_test_timeout_sec": test_timeout,
            }
        ),
        encoding="utf-8",
    )
    (d / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    (d / "docker-compose.yaml").write_text(
        yaml.safe_dump(compose or {"services": {"client": {"build": {"dockerfile": "Dockerfile"}}}}),
        encoding="utf-8",
    )
    (d / "solution.sh").write_text("echo hi > hi.txt\n", encoding="utf-8")
    (d / "run-tests.sh").write_text("pytest $TEST_DIR/test_outputs.py\n", encoding="utf-8")
    (d / "tests" / "test_outputs.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    for rel, text in (extra or {}).items():
        (d / rel).write_text(text, encoding="utf-8")
    return d


def test_imports_a_single_container_task_faithfully(tmp_path):
    src = tmp_path / "original-tasks"
    _tb_task(src, "hello-world", extra={"data.csv": "a,b\n"})
    [r] = import_all(src, tmp_path / "out")
    assert r.skipped is None and r.difficulty == "easy"
    task = TaskSpec.load(r.out_dir)
    assert task.id == "hello-world" and task.objective.startswith("Write hi")
    assert task.environment.workdir == "/app"  # inherited from the TB base image
    assert task.environment.network == "bridge" and task.environment.agent_user is None
    assert task.verifier.command == "TEST_DIR=/tests bash /tests/run-tests.sh"
    assert task.verifier.timeout_sec == 180
    env = {p.name for p in (r.out_dir / "environment").iterdir()}
    assert env == {"Dockerfile", "data.csv"}  # tests, solution and run-tests.sh stay hidden
    assert (r.out_dir / "tests" / "run-tests.sh").is_file()
    assert (r.out_dir / "solution" / "solution.sh").is_file()


def test_reports_why_tasks_are_skipped(tmp_path):
    src = tmp_path / "original-tasks"
    _tb_task(src, "two-boxes", compose={"services": {"client": {}, "db": {}}})
    _tb_task(src, "leaky", dockerfile="FROM ghcr.io/laude-institute/t-bench/x:1\nCOPY tests /tests\n")
    _tb_task(src, "no-workdir", dockerfile="FROM python:3.11-slim\n")
    _tb_task(src, "explicit", dockerfile="FROM python:3.11-slim\nWORKDIR /srv/app\n")
    results = {r.name: r for r in import_all(src, tmp_path / "out")}
    assert "2 containers" in results["two-boxes"].skipped
    assert "copies tests" in results["leaky"].skipped
    assert "WORKDIR" in results["no-workdir"].skipped
    assert TaskSpec.load(results["explicit"].out_dir).environment.workdir == "/srv/app"
    assert not (tmp_path / "out" / "two-boxes").exists()


def test_long_verifier_timeouts_stay_within_the_schema_limit(tmp_path):
    src = tmp_path / "original-tasks"
    _tb_task(src, "slow-tests", test_timeout=3600.0)  # +120 s install headroom would exceed 3600
    [r] = import_all(src, tmp_path / "out")
    assert TaskSpec.load(r.out_dir).verifier.timeout_sec == 3600
