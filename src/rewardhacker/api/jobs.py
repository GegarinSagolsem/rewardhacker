"""Postgres-backed job queue. The ``runs`` table is the queue.

Workers claim the oldest queued run with ``SELECT ... FOR UPDATE SKIP LOCKED``, so any number
of workers can poll the same table without double-claiming a run and without a broker.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Report
from ..registry import STATIC_PROBES
from ..runner import probe_task
from ..taskspec import TaskSpec
from .tables import Run, RunStatus, Task, utcnow
from .traces import TraceStore

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
# Longer than any single run, and longer than a Cloud Build worker's 30-min timeout, so a run
# still "running" after this has lost its worker.
STALE_AFTER = timedelta(minutes=40)

ProbeFn = Callable[[TaskSpec, list[str] | None], Report]


def _default_probe(task: TaskSpec, probe_names: list[str] | None) -> Report:
    return probe_task(task, probe_names)


def claim_next(db: Session, worker_id: str) -> Run | None:
    stmt = (
        select(Run)
        .where(Run.status == RunStatus.QUEUED.value)
        .order_by(Run.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    run = db.scalars(stmt).first()
    if run is None:
        db.rollback()
        return None
    run.status = RunStatus.RUNNING.value
    run.started_at = utcnow()
    run.attempts += 1
    run.worker = worker_id
    db.commit()
    return run


def recover_stale(db: Session, stale_after: timedelta = STALE_AFTER) -> int:
    """Requeue runs whose worker died mid-run (or fail them after too many attempts)."""
    cutoff = utcnow() - stale_after
    stuck = db.scalars(
        select(Run).where(Run.status == RunStatus.RUNNING.value, Run.started_at < cutoff).with_for_update()
    ).all()
    for run in stuck:
        if run.attempts >= MAX_ATTEMPTS:
            run.status, run.error = RunStatus.FAILED.value, "worker lost too many times"
            run.finished_at = utcnow()
        else:
            run.status, run.worker = RunStatus.QUEUED.value, None
    db.commit()
    return len(stuck)


def split_traces(report: Report, run: Run) -> tuple[dict, list[dict]]:
    """Separate agent steps (→ MongoDB) from the report summary (→ Postgres)."""
    data = report.model_dump(mode="json")
    docs: list[dict] = []
    for probe in data["probes"]:
        for trial in probe["trials"]:
            agent = trial.get("agent")
            if not agent:
                continue
            docs.append(
                {
                    "run_id": run.id,
                    "org_id": run.org_id,
                    "task_id": run.task_id,
                    "probe": probe["name"],
                    "trial": trial["index"],
                    **agent,
                }
            )
            agent["steps"] = []
    return data, docs


def execute(
    db: Session,
    run: Run,
    traces: TraceStore,
    probe_fn: ProbeFn = _default_probe,
    open_task: Callable[[str], Path] = Path,
) -> Run:
    """Probe the run's task and store the outcome. Never raises for task-level failures.
    ``open_task`` maps ``Task.storage_path`` to a local folder (``TaskFiles.open``)."""
    task_row = db.get(Task, run.task_id)
    # End the read transaction before probing (up to the worker's 30-minute limit): otherwise the
    # connection sits "idle in transaction" all that time, which Postgres/Neon may cut, and then
    # the final commit fails and the finished run is lost and re-run.
    db.commit()
    try:
        if task_row is None:
            raise RuntimeError("task was deleted")
        spec = TaskSpec.load(open_task(task_row.storage_path))
        names = None if run.include_llm else [p.name for p in STATIC_PROBES]
        report = probe_fn(spec, names)
    except Exception as exc:
        log.exception("run %s failed", run.id)
        run.status, run.error = RunStatus.FAILED.value, f"{type(exc).__name__}: {exc}"[:4000]
    else:
        stripped, docs = split_traces(report, run)
        try:
            traces.save(docs)
            run.report, run.traces_stored = stripped, bool(docs)
        except Exception:
            # Keep the steps inline rather than lose them when MongoDB is unreachable.
            log.exception("could not store traces for run %s; keeping them in the report", run.id)
            run.report, run.traces_stored = report.model_dump(mode="json"), False
        run.verdict, run.score = report.verdict, report.score
        run.llm_cost_usd = report.llm_usage.cost_usd if report.llm_usage else None
        run.status, run.error = RunStatus.DONE.value, None
    run.finished_at = utcnow()
    db.commit()
    return run
