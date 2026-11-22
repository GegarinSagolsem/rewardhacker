from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...taskspec import TaskSpecError
from ..deps import Principal, get_db, require_role
from ..schemas import TaskOut
from ..storage import BundleError
from ..tables import Role, Task, new_id

router = APIRouter(prefix="/api/orgs/{org_id}/tasks", tags=["tasks"])


def get_task(db: Session, org_id: str, task_id: str) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task not found")
    return task


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def upload_task(
    org_id: str,
    file: UploadFile,
    request: Request,
    actor: Principal = Depends(require_role(Role.REVIEWER)),
    db: Session = Depends(get_db),
) -> Task:
    """Upload a task bundle: a .zip with task.yaml at its top (or in one top-level folder)."""
    settings = request.app.state.settings
    limit = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"max upload is {settings.max_upload_mb} MB"
        )

    task_id = new_id()
    task_files = request.app.state.task_files
    try:
        storage_path, spec = task_files.save(org_id, task_id, data)
    except (BundleError, TaskSpecError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None

    task = Task(
        id=task_id,
        org_id=org_id,
        spec_id=spec.id,
        objective=spec.objective.strip(),
        storage_path=storage_path,
        uploaded_by=actor.user_id,
    )
    db.add(task)
    actor.audit(db, "task.upload", "task", task_id, spec_id=spec.id, size_bytes=len(data))
    db.commit()
    return task


@router.get("", response_model=list[TaskOut])
def list_tasks(
    org_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: Principal = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> list[Task]:
    stmt = (
        select(Task).where(Task.org_id == org_id).order_by(Task.created_at.desc()).limit(limit).offset(offset)
    )
    return list(db.scalars(stmt))


@router.get("/{task_id}", response_model=TaskOut)
def read_task(
    org_id: str,
    task_id: str,
    _: Principal = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> Task:
    return get_task(db, org_id, task_id)
