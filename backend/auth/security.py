"""Password hashing (bcrypt directly — passlib is unmaintained and breaks
against bcrypt>=4.1, a well-known incompatibility) and JWT access tokens
(pyjwt). Kept separate from auth/schemas.py and app/routers/auth.py so
"how a password/token is proven" stays independent of the request/response
shapes and route wiring around it.

bcrypt's algorithm caps input at 72 bytes; auth/schemas.py::UserCreate
enforces that at the request boundary so a too-long password fails with a
clean 422, not a ValueError from inside hash_password.
"""
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from config import Settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: uuid.UUID, settings: Settings) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> uuid.UUID | None:
    """None on any failure (expired, malformed, wrong signature) — the
    caller (app/deps.py::get_current_user) turns that into a 401, never
    a 500; token forgery/expiry is expected traffic, not a server error."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
