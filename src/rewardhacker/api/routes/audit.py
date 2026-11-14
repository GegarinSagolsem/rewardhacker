from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import Principal, get_db, require_role
from ..schemas import AuditOut
from ..tables import AuditEvent, Role

router = APIRouter(prefix="/api/orgs/{org_id}/audit", tags=["audit"])


@router.get("", response_model=list[AuditOut])
def list_audit(
    org_id: str,
    action: str | None = Query(None, description="Filter by action prefix, e.g. 'member.'"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: Principal = Depends(require_role(Role.ADMIN, allow_api_key=False)),
    db: Session = Depends(get_db),
) -> list[AuditEvent]:
    """Who did what in this org, newest first. Admins only."""
    stmt = select(AuditEvent).where(AuditEvent.org_id == org_id)
    if action:
        stmt = stmt.where(AuditEvent.action.startswith(action))
    stmt = stmt.order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))
