from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import API_KEY_PREFIX, Principal, get_db, hash_api_key, require_role
from ..schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from ..tables import ApiKey, Role, utcnow

router = APIRouter(prefix="/api/orgs/{org_id}/api-keys", tags=["api keys"])
admin_only = require_role(Role.ADMIN, allow_api_key=False)


@router.get("", response_model=list[ApiKeyOut])
def list_keys(org_id: str, _: Principal = Depends(admin_only), db: Session = Depends(get_db)) -> list[ApiKey]:
    return list(db.scalars(select(ApiKey).where(ApiKey.org_id == org_id).order_by(ApiKey.created_at.desc())))


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_key(
    org_id: str, body: ApiKeyCreate, actor: Principal = Depends(admin_only), db: Session = Depends(get_db)
) -> ApiKeyCreated:
    """Create a key for CI / scripts: `Authorization: Bearer rh_...`. The key is returned once."""
    if body.role == Role.ADMIN:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "API keys can be viewer or reviewer, not admin"
        )
    key = API_KEY_PREFIX + secrets.token_urlsafe(32)
    row = ApiKey(
        org_id=org_id,
        name=body.name.strip(),
        prefix=key[:10],
        key_hash=hash_api_key(key),
        role=body.role.value,
        created_by=actor.user_id,
    )
    db.add(row)
    db.flush()
    actor.audit(db, "apikey.create", "api_key", row.id, name=row.name, role=row.role)
    db.commit()
    return ApiKeyCreated(**ApiKeyOut.model_validate(row).model_dump(), key=key)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_key(
    org_id: str, key_id: str, actor: Principal = Depends(admin_only), db: Session = Depends(get_db)
) -> Response:
    row = db.get(ApiKey, key_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "key not found")
    if row.revoked_at is None:
        row.revoked_at = utcnow()
        actor.audit(db, "apikey.revoke", "api_key", row.id, name=row.name)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
