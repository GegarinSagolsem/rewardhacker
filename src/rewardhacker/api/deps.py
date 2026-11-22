"""Request dependencies: DB session, current user, org-scoped principals (users or API keys)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, timedelta

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .security import decode_token
from .tables import ApiKey, AuditEvent, Membership, Org, Role, User, utcnow

_bearer = HTTPBearer(auto_error=False)
API_KEY_PREFIX = "rh_"


def _unauthorized() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, "not authenticated", headers={"WWW-Authenticate": "Bearer"}
    )


def hash_api_key(key: str) -> str:
    # Keys are 256-bit random, so a fast hash is fine (no brute-forcing a password).
    return hashlib.sha256(key.encode()).hexdigest()


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.sessionmaker() as session:
        yield session


def current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """A signed-in person (JWT). API keys are not accepted here."""
    if creds is None:
        raise _unauthorized()
    user_id = decode_token(creds.credentials, request.app.state.settings.jwt_secret)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise _unauthorized()
    return user


@dataclass(frozen=True)
class Principal:
    """Whoever is acting inside an org: a member (JWT) or an org API key."""

    org_id: str
    role: Role
    label: str
    user_id: str | None = None
    api_key_id: str | None = None

    def audit(
        self,
        db: Session,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        **data: object,
    ) -> None:
        """Add an audit event to the session; it commits together with the change it records."""
        db.add(
            AuditEvent(
                org_id=self.org_id,
                actor_user_id=self.user_id,
                actor_api_key_id=self.api_key_id,
                actor_label=self.label,
                action=action,
                target_type=target_type,
                target_id=target_id,
                data=data or None,
            )
        )


def resolve_api_key(db: Session, key: str) -> ApiKey:
    """The active key row for a raw ``rh_`` key, or 401."""
    row = db.scalars(select(ApiKey).where(ApiKey.key_hash == hash_api_key(key))).first()
    if row is None or row.revoked_at is not None:
        raise _unauthorized()
    return row


def _from_api_key(db: Session, key: str, org_id: str) -> Principal:
    row = resolve_api_key(db, key)
    if row.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "org not found")
    now, last = utcnow(), row.last_used_at
    if last is not None and last.tzinfo is None:  # SQLite drops the offset
        last = last.replace(tzinfo=UTC)
    if last is None or now - last > timedelta(minutes=1):  # don't write on every request
        row.last_used_at = now
        db.commit()
    return Principal(org_id=org_id, role=Role(row.role), label=f"key: {row.name}", api_key_id=row.id)


def require_role(min_role: Role, allow_api_key: bool = True) -> Callable[..., Principal]:
    """Dependency: the caller acts in path param ``org_id`` with at least ``min_role``."""

    def dep(
        org_id: str,
        request: Request,
        creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
        db: Session = Depends(get_db),
    ) -> Principal:
        if creds is None:
            raise _unauthorized()
        if creds.credentials.startswith(API_KEY_PREFIX):
            if not allow_api_key:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "API keys can't do this; sign in as a member")
            principal = _from_api_key(db, creds.credentials, org_id)
        else:
            user = current_user(request, creds, db)
            m = db.get(Membership, (user.id, org_id))
            if m is None:
                # 404, not 403: don't reveal which orgs exist to outsiders.
                raise HTTPException(status.HTTP_404_NOT_FOUND, "org not found")
            principal = Principal(org_id=org_id, role=Role(m.role), label=user.email, user_id=user.id)
        if principal.role.rank < min_role.rank:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires role {min_role.value} or higher")
        return principal

    return dep


LLM_NOT_ENABLED = (
    "AI features (the LLM adversary, guidelines and spec checks) are not enabled for this "
    "organization. The static probes are free and always available."
)


def require_llm_access(db: Session, org_id: str) -> None:
    """Paid AI features are per-org opt-in (cost control on the public deployment)."""
    org = db.get(Org, org_id)
    if org is None or not org.llm_enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, LLM_NOT_ENABLED)
