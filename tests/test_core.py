"""Unit tests that do not need Docker."""

from pathlib import Path

import pytest

from rewardhacker.models import (
    Finding,
    ProbeResult,
    Severity,
    Trial,
    score_findings,
    verdict_for,
)
from rewardhacker.probes import NullProbe, ReferenceProbe
from rewardhacker.registry import get_probes
from rewardhacker.taskspec import TaskSpec, TaskSpecError

BENCH = Path(__file__).resolve().parents[1] / "loopbench" / "tasks"


def make_task(tmp_path: Path, yaml_text: str) -> Path:
    (tmp_path / "environment").mkdir()
    (tmp_path / "environment" / "Dockerfile").write_text("FROM alpine\n")
    (tmp_path / "task.yaml").write_text(yaml_text)
    return tmp_path


def result(name: str, expect_pass: bool, outcomes: list[bool | None]) -> ProbeResult:
    return ProbeResult(
        name=name,
        title=name,
        expect_pass=expect_pass,
        status="ok",
        trials=[Trial(index=i, passed=o) for i, o in enumerate(outcomes)],
    )


def test_all_loopbench_tasks_load():
    tasks = [TaskSpec.load(d) for d in BENCH.iterdir() if d.is_dir()]
    assert len(tasks) >= 10
    assert all(t.root.is_dir() for t in tasks)


def test_rejects_path_escape(tmp_path):
    root = make_task(
        tmp_path,
        "id: evil\nobjective: x\nverifier:\n  command: 'true'\n  files: ../../etc\n",
    )
    with pytest.raises(TaskSpecError, match="escapes"):
        TaskSpec.load(root)


def test_rejects_unknown_fields(tmp_path):
    root = make_task(tmp_path, "id: t\nobjective: x\nverifier:\n  command: 'true'\nbogus: 1\n")
    with pytest.raises(TaskSpecError):
        TaskSpec.load(root)


def test_rejects_bad_id(tmp_path):
    root = make_task(tmp_path, "id: Bad ID!\nobjective: x\nverifier:\n  command: 'true'\n")
    with pytest.raises(TaskSpecError):
        TaskSpec.load(root)


def test_missing_solution_dir(tmp_path):
    root = make_task(tmp_path, "id: t\nobjective: x\nverifier:\n  command: 'true'\nsolution:\n  command: x\n")
    with pytest.raises(TaskSpecError, match="solution"):
        TaskSpec.load(root)


def test_null_probe_flags_free_reward():
    findings = NullProbe().evaluate(result("null", False, [True, True]))
    assert [f.code for f in findings] == ["null-passes"]
    assert findings[0].severity == Severity.CRITICAL


def test_null_probe_quiet_when_verifier_rejects():
    assert NullProbe().evaluate(result("null", False, [False, False])) == []


def test_reference_probe_broken_vs_flaky():
    assert ReferenceProbe().evaluate(result("reference", True, [False] * 3))[0].code == ("reference-fails")
    assert ReferenceProbe().evaluate(result("reference", True, [True, False, True]))[0].code == (
        "flaky-reference"
    )
    assert ReferenceProbe().evaluate(result("reference", True, [True] * 3)) == []


def test_skipped_trials_are_ignored():
    assert NullProbe().evaluate(result("null", False, [None, None])) == []


def _finding(sev: Severity) -> Finding:
    return Finding(code="x", severity=sev, probe="p", title="t", detail="d")


def test_scoring_and_verdicts():
    ok = [result("null", False, [False])]
    assert score_findings([]) == 100
    assert verdict_for([], ok) == "robust"
    assert verdict_for([_finding(Severity.CRITICAL)], ok) == "exploitable"
    assert verdict_for([_finding(Severity.HIGH)], ok) == "broken"
    assert verdict_for([_finding(Severity.MEDIUM)], ok) == "flaky"
    assert score_findings([_finding(Severity.CRITICAL)] * 3) == 0
    skipped = [ProbeResult(name="n", title="n", expect_pass=False, status="skipped")]
    assert verdict_for([], skipped) == "inconclusive"
    errored = [*ok, ProbeResult(name="adversary", title="a", expect_pass=False, status="error")]
    assert verdict_for([], errored) == "inconclusive"  # one probe failed: not provably robust
    assert verdict_for([_finding(Severity.CRITICAL)], errored) == "exploitable"


def test_get_probes():
    assert len(get_probes()) == 9
    assert len(get_probes(include_llm=False)) == 8
    assert [p.name for p in get_probes(["null"])] == ["null"]
    with pytest.raises(ValueError, match="unknown"):
        get_probes(["nope"])


def test_task_network_needs_operator_opt_in(tmp_path, monkeypatch):
    import shutil

    from rewardhacker.sandbox import DockerError, Sandbox
    from rewardhacker.taskspec import TaskSpec

    src = Path(__file__).parent.parent / "loopbench" / "tasks" / "weak-output-check"
    shutil.copytree(src, tmp_path / "t")
    y = tmp_path / "t" / "task.yaml"
    y.write_text(y.read_text().replace("environment:\n", "environment:\n  network: bridge\n"))
    task = TaskSpec.load(tmp_path / "t")
    assert task.environment.network == "bridge"
    monkeypatch.delenv("RH_ALLOW_TASK_NETWORK", raising=False)
    with pytest.raises(DockerError, match="RH_ALLOW_TASK_NETWORK"):
        Sandbox("unused-image", task).__enter__()  # refused before any docker call


def test_markdown_report_does_not_score_inconclusive_runs():
    from rewardhacker.models import Report
    from rewardhacker.reporting import report_markdown

    base = dict(task_id="t", image="i", rewardhacker_version="0", started_at="now", duration_sec=1.0)
    unsure = Report(**base, probes=[], findings=[], score=100, verdict="inconclusive")
    assert "**Score:** not scored" in report_markdown(unsure, task_name="t")
    clean = Report(**base, probes=[], findings=[], score=100, verdict="robust")
    assert "**Score:** 100/100" in report_markdown(clean, task_name="t")
