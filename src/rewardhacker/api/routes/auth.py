from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..deps import current_user, get_db
from ..schemas import Credentials, MeOut, OrgOut, Token, UserOut
from ..security import create_token, hash_password, verify_password
from ..tables import Membership, Org, User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: Credentials, db: Session = Depends(get_db)) -> User:
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered") from None
    return user


@router.post("/login", response_model=Token)
def login(body: Credentials, request: Request, db: Session = Depends(get_db)) -> Token:
    user = db.scalars(select(User).where(User.email == body.email)).first()
    if not verify_password(body.password, user.password_hash if user else None) or user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong email or password")
    settings = request.app.state.settings
    return Token(access_token=create_token(user.id, settings.jwt_secret, settings.token_ttl_minutes))


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(current_user), db: Session = Depends(get_db)) -> MeOut:
    rows = db.execute(
        select(Org, Membership.role)
        .join(Membership, Membership.org_id == Org.id)
        .where(Membership.user_id == user.id)
        .order_by(Org.created_at)
    ).all()
    orgs = [OrgOut(id=o.id, name=o.name, created_at=o.created_at, role=role) for o, role in rows]
    return MeOut(id=user.id, email=user.email, created_at=user.created_at, orgs=orgs)
