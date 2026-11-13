"""End-to-end: probe every LoopBench task in Docker and compare with its expected.yaml."""

from pathlib import Path

import pytest

from rewardhacker.bench import discover, run_one
from rewardhacker.sandbox import DockerError, check_docker

BENCH = Path(__file__).resolve().parents[1] / "loopbench" / "tasks"
TASKS = discover(BENCH)


def _docker_available() -> bool:
    try:
        check_docker()
        return True
    except DockerError:
        return False


pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(not _docker_available(), reason="Docker daemon not available"),
]


@pytest.mark.parametrize("task_dir", TASKS, ids=[d.name for d in TASKS])
def test_loopbench_task(task_dir: Path):
    outcome = run_one(task_dir)
    assert outcome.error is None, outcome.error
    detail = outcome.report.model_dump_json(indent=2)
    assert outcome.report.verdict == outcome.expected.verdict, detail
    assert not outcome.false_negatives, f"missed {outcome.false_negatives}: {detail}"
    assert not outcome.false_positives, f"false alarms {outcome.false_positives}: {detail}"
