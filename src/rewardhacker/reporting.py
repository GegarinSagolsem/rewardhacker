"""Render reports for people (Markdown) and for tools (CSV / JSONL rows)."""

from __future__ import annotations

from .models import Report

VERDICT_LINE = {
    "exploitable": "The reward can be earned without doing the task.",
    "broken": "The task can't be solved as specified: the verifier rejects the reference solution.",
    "flaky": "The verifier gives different answers for the same work.",
    "robust": "None of the probes that ran found a way to earn the reward without doing the work.",
    "inconclusive": "Some probes could not run to completion, so robustness is unproven.",
}


def _cell(text: str | None) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


def report_markdown(
    report: Report,
    *,
    task_name: str,
    run_id: str | None = None,
    traces: list[dict] | None = None,
) -> str:
    """A self-contained Markdown report. ``traces`` (from MongoDB) fill in adversary steps."""
    out: list[str] = [f"# RewardHacker report: `{task_name}`", ""]
    score = "not scored" if report.verdict == "inconclusive" else f"{report.score}/100"
    meta = [f"**Verdict:** {report.verdict.upper()}", f"**Score:** {score}"]
    if run_id:
        meta.append(f"run `{run_id[:8]}`")
    meta += [report.started_at, f"rewardhacker {report.rewardhacker_version}"]
    out += [" · ".join(meta), "", VERDICT_LINE.get(report.verdict, ""), ""]

    out += ["## Findings", ""]
    if not report.findings:
        out += ["No loopholes found.", ""]
    for f in report.findings:
        out += [f"### [{f.severity.value.upper()}] {f.title} (`{f.code}`)", "", f.detail, ""]
        if f.recommendation:
            out += [f"**How to fix:** {f.recommendation}", ""]

    out += ["## Probes", "", "| Probe | Result | Verifier passed | Note |", "|---|---|---|---|"]
    for p in report.probes:
        ran = [t for t in p.trials if t.passed is not None]
        passed = sum(1 for t in ran if t.passed)
        result = {"finding": "LOOPHOLE", "error": "error", "skipped": "skipped"}.get(
            p.status, "passed" if p.expect_pass else "held"
        )
        counts = f"{passed}/{len(ran)}" if ran else "-"
        out.append(f"| `{p.name}` | {result} | {counts} | {_cell(p.note)} |")
    out.append("")

    for p in report.probes:
        for t in p.trials:
            if not t.agent:
                continue
            doc = next(
                (d for d in traces or [] if d.get("probe") == p.name and d.get("trial") == t.index), None
            )
            steps = doc["steps"] if doc else [s.model_dump() for s in t.agent.steps]
            out += [f"## Adversary trace ({p.name}, trial {t.index})", ""]
            for s in steps:
                if s.get("tool") == "bash":
                    cmd = str(s.get("args", {}).get("command", "")).rstrip()
                    output = (s.get("output") or "").rstrip()
                    out += ["```console", f"$ {cmd}", *([output] if output else []), "```", ""]
                elif s.get("tool") == "submit":
                    out += [f"> **Agent submitted:** {s.get('args', {}).get('explanation', '')}", ""]
            if t.agent.judgement:
                out += [f"**Judge:** {t.agent.judgement}. {t.agent.judge_reason or ''}", ""]
            if t.agent.usage.calls:
                u = t.agent.usage
                out += [f"_{u.model}, {u.calls} calls, ${u.cost_usd:.4f}_", ""]
    return "\n".join(out).rstrip() + "\n"


RUN_CSV_COLUMNS = [
    "run_id",
    "task_id",
    "task",
    "status",
    "verdict",
    "score",
    "findings",
    "include_llm",
    "llm_cost_usd",
    "created_at",
    "started_at",
    "finished_at",
    "error",
]
