from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..deps import current_user, get_db, require_role
from ..schemas import MemberAdd, MemberOut, MemberUpdate, OrgCreate, OrgOut
from ..tables import Membership, Org, Role, User

router = APIRouter(prefix="/api/orgs", tags=["orgs"])


def _member_out(m: Membership, email: str) -> MemberOut:
    return MemberOut(user_id=m.user_id, email=email, role=Role(m.role), created_at=m.created_at)


def _ensure_other_admin(db: Session, org_id: str, user_id: str) -> None:
    """Refuse to remove or demote the org's last admin."""
    admins = db.scalar(
        select(func.count())
        .select_from(Membership)
        .where(
            Membership.org_id == org_id, Membership.role == Role.ADMIN.value, Membership.user_id != user_id
        )
    )
    if not admins:
        raise HTTPException(status.HTTP_409_CONFLICT, "an org must keep at least one admin")


@router.post("", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
def create_org(body: OrgCreate, user: User = Depends(current_user), db: Session = Depends(get_db)) -> OrgOut:
    org = Org(name=body.name.strip())
    db.add(org)
    db.flush()
    db.add(Membership(user_id=user.id, org_id=org.id, role=Role.ADMIN.value))
    db.commit()
    return OrgOut(id=org.id, name=org.name, created_at=org.created_at, role=Role.ADMIN)


@router.get("", response_model=list[OrgOut])
def list_orgs(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[OrgOut]:
    rows = db.execute(
        select(Org, Membership.role)
        .join(Membership, Membership.org_id == Org.id)
        .where(Membership.user_id == user.id)
        .order_by(Org.created_at)
    ).all()
    return [OrgOut(id=o.id, name=o.name, created_at=o.created_at, role=r) for o, r in rows]


@router.get("/{org_id}/members", response_model=list[MemberOut])
def list_members(
    org_id: str, _: Membership = Depends(require_role(Role.VIEWER)), db: Session = Depends(get_db)
) -> list[MemberOut]:
    rows = db.execute(
        select(Membership, User.email)
        .join(User, User.id == Membership.user_id)
        .where(Membership.org_id == org_id)
        .order_by(Membership.created_at)
    ).all()
    return [_member_out(m, email) for m, email in rows]


@router.post("/{org_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    org_id: str,
    body: MemberAdd,
    _: Membership = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> MemberOut:
    user = db.scalars(select(User).where(User.email == body.email)).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no user with that email; they must register first")
    if db.get(Membership, (user.id, org_id)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already a member")
    m = Membership(user_id=user.id, org_id=org_id, role=body.role.value)
    db.add(m)
    db.commit()
    return _member_out(m, user.email)


@router.patch("/{org_id}/members/{user_id}", response_model=MemberOut)
def update_member(
    org_id: str,
    user_id: str,
    body: MemberUpdate,
    _: Membership = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> MemberOut:
    m = db.get(Membership, (user_id, org_id))
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "member not found")
    if m.role == Role.ADMIN.value and body.role != Role.ADMIN:
        _ensure_other_admin(db, org_id, user_id)
    m.role = body.role.value
    db.commit()
    return _member_out(m, db.get(User, user_id).email)


@router.delete("/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    org_id: str,
    user_id: str,
    _: Membership = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> Response:
    m = db.get(Membership, (user_id, org_id))
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "member not found")
    if m.role == Role.ADMIN.value:
        _ensure_other_admin(db, org_id, user_id)
    db.delete(m)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
