"""Password hashing (Argon2) and JWT access tokens."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()
ALGORITHM = "HS256"
# Verified against when the e-mail is unknown, so login takes the same time either way.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        _hasher.verify(password, _DUMMY_HASH)
        return False
    return _hasher.verify(password, password_hash)


def create_token(user_id: str, secret: str, ttl_minutes: int) -> str:
    now = datetime.now(UTC)
    claims = {"sub": user_id, "iat": now, "exp": now + timedelta(minutes=ttl_minutes)}
    return jwt.encode(claims, secret, algorithm=ALGORITHM)


def decode_token(token: str, secret: str) -> str | None:
    """Return the user id in a valid token, or None for anything invalid or expired."""
    try:
        claims = jwt.decode(token, secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        return None
    sub = claims.get("sub")
    return sub if isinstance(sub, str) else None
