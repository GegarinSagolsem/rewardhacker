"""End-to-end: probe every LoopBench task in Docker and compare with its expected.yaml."""

from pathlib import Path

import pytest
import yaml

from rewardhacker.runner import probe_task
from rewardhacker.sandbox import DockerError, check_docker
from rewardhacker.taskspec import TaskSpec

BENCH = Path(__file__).resolve().parents[1] / "loopbench" / "tasks"
TASKS = sorted(d for d in BENCH.iterdir() if (d / "expected.yaml").is_file())


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
    expected = yaml.safe_load((task_dir / "expected.yaml").read_text())
    report = probe_task(TaskSpec.load(task_dir))
    assert report.verdict == expected["verdict"], report.model_dump_json(indent=2)
    assert sorted(f.code for f in report.findings) == sorted(expected["findings"])
