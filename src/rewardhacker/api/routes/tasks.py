from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...taskspec import TaskSpec, TaskSpecError
from ..deps import get_db, require_role
from ..schemas import TaskOut
from ..storage import BundleError, extract_bundle
from ..tables import Membership, Role, Task, new_id

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
    member: Membership = Depends(require_role(Role.REVIEWER)),
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
    dest = settings.storage_dir / org_id / task_id
    try:
        root = extract_bundle(data, dest)
        spec = TaskSpec.load(root)
    except (BundleError, TaskSpecError) as exc:
        shutil.rmtree(dest, ignore_errors=True)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc).replace(str(dest), "<bundle>")
        ) from None

    task = Task(
        id=task_id,
        org_id=org_id,
        spec_id=spec.id,
        objective=spec.objective.strip(),
        storage_path=str(root),
        uploaded_by=member.user_id,
    )
    db.add(task)
    db.commit()
    return task


@router.get("", response_model=list[TaskOut])
def list_tasks(
    org_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: Membership = Depends(require_role(Role.VIEWER)),
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
    _: Membership = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> Task:
    return get_task(db, org_id, task_id)
