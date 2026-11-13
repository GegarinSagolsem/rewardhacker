"""`rh` command-line interface."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .models import Report, Severity
from .probes import ALL_PROBES
from .runner import probe_task
from .sandbox import DockerError
from .taskspec import TaskSpec, TaskSpecError

app = typer.Typer(
    help="RewardHacker: red-team your rewards. Finds RL tasks that can be passed without doing the work.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

SEVERITY_STYLE = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "cyan",
    Severity.INFO: "dim",
}
VERDICT_STYLE = {
    "robust": "bold green",
    "exploitable": "bold red",
    "broken": "bold red",
    "flaky": "bold yellow",
    "inconclusive": "bold magenta",
}


def _load(path: Path) -> TaskSpec:
    try:
        return TaskSpec.load(path)
    except TaskSpecError as exc:
        console.print(f"[red]Invalid task:[/red] {exc}")
        raise typer.Exit(2) from exc


@app.command()
def version() -> None:
    """Print the version."""
    console.print(f"rewardhacker {__version__}")


@app.command()
def validate(path: Annotated[Path, typer.Argument(help="Task directory")]) -> None:
    """Check that a task directory and its task.yaml are well-formed."""
    task = _load(path)
    console.print(f"[green]OK[/green] {task.id}: {task.objective.strip().splitlines()[0]}")


@app.command("probes")
def list_probes() -> None:
    """List the available probes."""
    table = Table("probe", "expects verifier to", "what it does")
    for p in ALL_PROBES:
        table.add_row(p.name, "pass" if p.expect_pass else "fail", p.title)
    console.print(table)


def render(report: Report) -> None:
    table = Table(title=f"Probes for [bold]{report.task_id}[/bold]", show_lines=False)
    table.add_column("probe")
    table.add_column("expected")
    table.add_column("verifier passed", justify="right")
    table.add_column("status")
    for p in report.probes:
        ran = p.ran
        status_style = {"ok": "green", "finding": "red", "skipped": "dim", "error": "magenta"}
        status = f"[{status_style[p.status]}]{p.status}[/]"
        if p.note and p.status in ("skipped", "error"):
            status += f" [dim]({p.note})[/dim]"
        table.add_row(
            p.name,
            "pass" if p.expect_pass else "fail",
            f"{p.pass_count}/{len(ran)}" if ran else "-",
            status,
        )
    console.print(table)
    for f in report.findings:
        style = SEVERITY_STYLE[f.severity]
        console.print(
            Panel(
                f"{f.detail}\n\n[bold]Fix:[/bold] {f.recommendation}",
                title=f"[{style}]{f.severity.upper()}[/] {f.title}  [dim]({f.code})[/dim]",
                title_align="left",
                border_style=style,
            )
        )
    style = VERDICT_STYLE[report.verdict]
    console.print(
        f"Verdict: [{style}]{report.verdict.upper()}[/]   Score: [bold]{report.score}/100[/bold]"
        f"   [dim]({report.duration_sec}s)[/dim]"
    )


@app.command()
def probe(
    path: Annotated[Path, typer.Argument(help="Task directory")],
    json_out: Annotated[
        Path | None, typer.Option("--json", help="Write the full report as JSON to this file")
    ] = None,
    only: Annotated[
        str | None, typer.Option(help="Comma-separated probe names to run (default: all)")
    ] = None,
    trials: Annotated[int | None, typer.Option(min=1, max=20, help="Override trials per probe")] = None,
    fail_under: Annotated[int | None, typer.Option(help="Exit 1 if the score is below this (for CI)")] = None,
) -> None:
    """Red-team a task: run every probe and report how its reward can be gamed."""
    task = _load(path)
    names = [n.strip() for n in only.split(",")] if only else None

    def on_event(event: str, data: dict) -> None:
        if event == "build_start":
            console.print(f"[dim]Building environment for {data['task']}...[/dim]")
        elif event == "probe_start":
            console.print(f"[dim]  probe {data['probe']}: {data['title']}[/dim]")

    try:
        report = probe_task(task, names, trials, on_event)
    except (DockerError, ValueError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc

    render(report)
    if json_out:
        json_out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"[dim]Report written to {json_out}[/dim]")
    if fail_under is not None:
        if report.score < fail_under:
            raise typer.Exit(1)
    elif report.verdict != "robust":
        raise typer.Exit(1)


@app.command()
def bench(
    path: Annotated[Path, typer.Argument(help="Directory of benchmark tasks")] = Path("loopbench/tasks"),
    jobs: Annotated[int, typer.Option(min=1, max=16, help="Tasks to probe in parallel")] = 4,
    json_out: Annotated[Path | None, typer.Option("--json", help="Write results as JSON")] = None,
) -> None:
    """Run LoopBench: probe tasks with known problems and report precision / recall."""
    import json

    from .bench import run_bench

    def on_done(o) -> None:
        mark = "[green]PASS[/green]" if o.correct else "[red]FAIL[/red]"
        console.print(f"  {mark} {o.task_id}" + (f" [red]{o.error}[/red]" if o.error else ""))

    console.print(f"[dim]Running LoopBench on {path} with {jobs} parallel job(s)...[/dim]")
    result = run_bench(path, jobs=jobs, on_done=on_done)

    table = Table("task", "expected", "got", "missed", "false alarms")
    for o in sorted(result.outcomes, key=lambda o: o.task_id):
        got = o.report.verdict if o.report else "error"
        style = "green" if o.verdict_ok else "red"
        table.add_row(
            o.task_id,
            o.expected.verdict,
            f"[{style}]{got}[/]",
            ", ".join(sorted(o.false_negatives)) or "-",
            ", ".join(sorted(o.false_positives)) or "-",
        )
    console.print(table)
    s = result.summary()
    console.print(
        f"Tasks fully correct: [bold]{s['tasks_fully_correct']}/{s['tasks']}[/bold]   "
        f"Verdict accuracy: [bold]{s['verdict_accuracy']:.0%}[/bold]   "
        f"Precision: [bold]{s['precision']:.0%}[/bold]   Recall: [bold]{s['recall']:.0%}[/bold]"
    )
    if json_out:
        payload = {
            "summary": s,
            "tasks": [
                {
                    "task_id": o.task_id,
                    "expected": o.expected.model_dump(),
                    "verdict": o.report.verdict if o.report else None,
                    "findings": sorted(o.found),
                    "error": o.error,
                }
                for o in result.outcomes
            ],
        }
        json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if s["tasks_fully_correct"] != s["tasks"]:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
