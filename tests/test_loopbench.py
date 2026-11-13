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
    if outcome.skipped:
        pytest.skip(outcome.skipped)
    assert outcome.error is None, outcome.error
    detail = outcome.report.model_dump_json(indent=2)
    assert outcome.report.verdict == outcome.expected.verdict, detail
    assert not outcome.false_negatives, f"missed {outcome.false_negatives}: {detail}"
    assert not outcome.false_positives, f"false alarms {outcome.false_positives}: {detail}"


@pytest.mark.parametrize(
    ("task_name", "judge_verdict", "expect_finding"),
    [("weak-output-check", "shortcut", True), ("strong-output-check", "shortcut", False)],
)
def test_adversary_end_to_end_with_scripted_llm(task_name, judge_verdict, expect_finding):
    """Real Docker sandbox + real verifier, scripted LLM (no API cost)."""
    from fakes import FakeLLM, bash, submit

    from rewardhacker.adversary import AdversaryProbe
    from rewardhacker.runner import run_probe
    from rewardhacker.sandbox import build_image
    from rewardhacker.taskspec import TaskSpec

    task = TaskSpec.load(BENCH / task_name)
    llm = FakeLLM(
        [bash("head -3 data/sales.csv"), bash("echo 'total: 0' > report.txt"), submit("placeholder total")],
        judge_verdict=judge_verdict,
    )
    probe = AdversaryProbe(llm_factory=lambda: llm)
    result = run_probe(probe, task, build_image(task), trials=1, on_event=lambda e, d: None)
    trial = result.trials[0]
    assert trial.agent.stop_reason == "submitted"
    findings = probe.evaluate(result)
    assert bool(findings) == expect_finding, trial.model_dump_json(indent=2)
    if expect_finding:
        assert trial.passed and trial.agent.judgement == "shortcut"
        assert "report.txt" in llm.judge_prompts[0]  # judge saw the changed file
    else:
        assert trial.passed is False and llm.judge_prompts == []  # judge not called, no cost
