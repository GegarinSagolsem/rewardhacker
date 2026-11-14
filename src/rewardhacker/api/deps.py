"""Request dependencies: DB session, current user, org role checks."""

from __future__ import annotations

from collections.abc import Callable, Iterator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .security import decode_token
from .tables import Membership, Role, User

_bearer = HTTPBearer(auto_error=False)


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.sessionmaker() as session:
        yield session


def current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "not authenticated", headers={"WWW-Authenticate": "Bearer"}
    )
    if creds is None:
        raise unauthorized
    user_id = decode_token(creds.credentials, request.app.state.settings.jwt_secret)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise unauthorized
    return user


def require_role(min_role: Role) -> Callable[..., Membership]:
    """Dependency: the caller must belong to path param ``org_id`` with at least ``min_role``."""

    def dep(org_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Membership:
        m = db.get(Membership, (user.id, org_id))
        if m is None:
            # 404, not 403: don't reveal which orgs exist to outsiders.
            raise HTTPException(status.HTTP_404_NOT_FOUND, "org not found")
        if Role(m.role).rank < min_role.rank:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires role {min_role.value} or higher")
        return m

    return dep
