from __future__ import annotations

from datetime import UTC, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import Principal, get_db, require_role
from ..schemas import RunCreate, RunDetail, RunOut
from ..tables import Role, Run, RunStatus, utcnow
from .tasks import get_task

router = APIRouter(prefix="/api/orgs/{org_id}", tags=["runs"])

# A run still queued after this long gets another worker kick when someone looks at it.
REKICK_AFTER = timedelta(seconds=90)


def _get_run(db: Session, org_id: str, run_id: str) -> Run:
    run = db.get(Run, run_id)
    if run is None or run.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    return run


@router.post("/tasks/{task_id}/runs", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED)
def start_run(
    org_id: str,
    task_id: str,
    request: Request,
    background: BackgroundTasks,
    body: RunCreate | None = None,
    actor: Principal = Depends(require_role(Role.REVIEWER)),
    db: Session = Depends(get_db),
) -> Run:
    """Queue a probe run. A worker picks it up (started on demand in the cloud)."""
    get_task(db, org_id, task_id)
    run = Run(
        org_id=org_id,
        task_id=task_id,
        requested_by=actor.user_id,
        include_llm=(body or RunCreate()).include_llm,
        status=RunStatus.QUEUED.value,
    )
    db.add(run)
    db.flush()
    actor.audit(db, "run.start", "run", run.id, task_id=task_id, include_llm=run.include_llm)
    db.commit()
    background.add_task(request.app.state.dispatcher.kick)  # after the response is sent
    return run


@router.get("/runs", response_model=list[RunOut])
def list_runs(
    org_id: str,
    task_id: str | None = None,
    status_filter: RunStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: Principal = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> list[Run]:
    stmt = select(Run).where(Run.org_id == org_id)
    if task_id:
        stmt = stmt.where(Run.task_id == task_id)
    if status_filter:
        stmt = stmt.where(Run.status == status_filter.value)
    stmt = stmt.order_by(Run.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


@router.get("/runs/{run_id}", response_model=RunDetail)
def read_run(
    org_id: str,
    run_id: str,
    request: Request,
    background: BackgroundTasks,
    _: Principal = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> Run:
    run = _get_run(db, org_id, run_id)
    if run.status == RunStatus.QUEUED.value:
        created = run.created_at if run.created_at.tzinfo else run.created_at.replace(tzinfo=UTC)
        if utcnow() - created > REKICK_AFTER:  # self-heal: the worker that was started is gone
            background.add_task(request.app.state.dispatcher.kick)
    return run


@router.get("/runs/{run_id}/traces")
def read_traces(
    org_id: str,
    run_id: str,
    request: Request,
    _: Principal = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """The LLM adversary's step-by-step tool calls for this run (from MongoDB)."""
    run = _get_run(db, org_id, run_id)
    return request.app.state.traces.for_run(run.id) if run.traces_stored else []
