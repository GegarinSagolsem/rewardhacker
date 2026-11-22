"""Run a set of probes against a task and assemble the report."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime

from . import __version__
from .models import LLMUsage, ProbeResult, Report, Trial, score_findings, verdict_for
from .probes import NOT_APPLICABLE, Probe
from .registry import get_probes
from .sandbox import DockerError, Sandbox, build_image, check_docker
from .taskspec import TaskSpec

EventHandler = Callable[[str, dict], None]


def _noop(event: str, data: dict) -> None:
    pass


def run_trial(probe: Probe, task: TaskSpec, image: str, index: int) -> Trial:
    trial = Trial(index=index)
    with Sandbox(image, task) as sb:
        trial.setup = probe.prepare(sb, task, trial)
        if trial.setup is not None and trial.setup.exit_code == NOT_APPLICABLE:
            trial.note = "not applicable: " + (trial.setup.stdout.strip() or "setup declined")
            return trial
        if trial.setup is not None and trial.setup.exit_code != 0:
            trial.note = "setup exited non-zero; verifying anyway"
        tests = task.resolve(task.verifier.files)
        if tests.is_dir():
            sb.copy_in(tests, task.verifier.mount_path)
        trial.verify = sb.exec(
            task.verifier.command, timeout=task.verifier.timeout_sec, user=task.verifier.user
        )
        trial.passed = trial.verify.exit_code == 0 and not trial.verify.timed_out
        probe.after_verify(sb, task, trial)
    return trial


def run_probe(
    probe: Probe, task: TaskSpec, image: str, trials: int | None, on_event: EventHandler
) -> ProbeResult:
    result = ProbeResult(name=probe.name, title=probe.title, expect_pass=probe.expect_pass, status="ok")
    reason = probe.not_applicable(task)
    if reason:
        result.status, result.note = "skipped", reason
        return result
    for i in range(trials or probe.trials):
        on_event("trial_start", {"probe": probe.name, "index": i})
        try:
            trial = run_trial(probe, task, image, i)
        except DockerError as exc:
            result.status, result.note = "error", str(exc)
            return result
        result.trials.append(trial)
        on_event("trial_end", {"probe": probe.name, "index": i, "passed": trial.passed})
        if err := probe.trial_error(trial):
            result.status, result.note = "error", err
            return result
        if trial.passed is None and trial.note and trial.note.startswith("not applicable"):
            result.status, result.note = "skipped", trial.note
            return result
    return result


def probe_task(
    task: TaskSpec,
    probe_names: list[str] | None = None,
    trials: int | dict[str, int] | None = None,
    on_event: EventHandler = _noop,
) -> Report:
    """Probe a task. ``trials`` overrides trial counts: one number for all probes, or per probe."""
    probes = get_probes(probe_names)
    check_docker()
    started = datetime.now(UTC)
    t0 = time.monotonic()

    on_event("build_start", {"task": task.id})
    image = build_image(task)
    on_event("build_end", {"image": image})

    results: list[ProbeResult] = []
    findings = []
    for probe in probes:
        on_event("probe_start", {"probe": probe.name, "title": probe.title})
        if probe.name == "adversary" and any(f.code == "null-passes" for f in findings):
            # Free reward is already proven; an LLM run would cost money and add nothing.
            results.append(
                ProbeResult(
                    name=probe.name,
                    title=probe.title,
                    expect_pass=probe.expect_pass,
                    status="skipped",
                    note="skipped: verifier already passes with no work",
                )
            )
            continue
        n = trials.get(probe.name) if isinstance(trials, dict) else trials
        result = run_probe(probe, task, image, n, on_event)
        new = probe.evaluate(result) if result.status == "ok" else []
        if new:
            result.status = "finding"
        findings.extend(new)
        results.append(result)
        on_event("probe_end", {"probe": probe.name, "result": result})

    # If the verifier passes with no work at all, every tamper probe "succeeds" too. Those
    # findings share one root cause, so report it once.
    if any(f.code == "null-passes" for f in findings):
        tamper = {p.name for p in probes if not p.expect_pass and p.name != "null"}
        findings = [f for f in findings if f.probe not in tamper]
        for r in results:
            if r.name in tamper and r.status == "finding":
                r.status, r.note = "ok", "implied by null-passes"

    usage = LLMUsage()
    for r in results:
        for t in r.trials:
            if t.agent:
                usage.merge(t.agent.usage)

    return Report(
        task_id=task.id,
        image=image,
        rewardhacker_version=__version__,
        started_at=started.isoformat(timespec="seconds"),
        duration_sec=round(time.monotonic() - t0, 2),
        probes=results,
        findings=findings,
        score=score_findings(findings),
        verdict=verdict_for(findings, results),
        llm_usage=usage if usage.calls else None,
    )
