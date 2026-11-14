from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_db, require_role
from ..schemas import RunCreate, RunDetail, RunOut
from ..tables import Membership, Role, Run, RunStatus
from .tasks import get_task

router = APIRouter(prefix="/api/orgs/{org_id}", tags=["runs"])


def _get_run(db: Session, org_id: str, run_id: str) -> Run:
    run = db.get(Run, run_id)
    if run is None or run.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    return run


@router.post("/tasks/{task_id}/runs", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED)
def start_run(
    org_id: str,
    task_id: str,
    body: RunCreate | None = None,
    member: Membership = Depends(require_role(Role.REVIEWER)),
    db: Session = Depends(get_db),
) -> Run:
    """Queue a probe run. A worker (`rh worker`) picks it up."""
    get_task(db, org_id, task_id)
    run = Run(
        org_id=org_id,
        task_id=task_id,
        requested_by=member.user_id,
        include_llm=(body or RunCreate()).include_llm,
        status=RunStatus.QUEUED.value,
    )
    db.add(run)
    db.commit()
    return run


@router.get("/runs", response_model=list[RunOut])
def list_runs(
    org_id: str,
    task_id: str | None = None,
    status_filter: RunStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: Membership = Depends(require_role(Role.VIEWER)),
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
    _: Membership = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> Run:
    return _get_run(db, org_id, run_id)


@router.get("/runs/{run_id}/traces")
def read_traces(
    org_id: str,
    run_id: str,
    request: Request,
    _: Membership = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """The LLM adversary's step-by-step tool calls for this run (from MongoDB)."""
    run = _get_run(db, org_id, run_id)
    return request.app.state.traces.for_run(run.id) if run.traces_stored else []
