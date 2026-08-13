"""Shared FastAPI route dependencies: authentication, and the DRY seam
for "get persona or 404" used by every /personas/{id}/... route (and
called directly, not via Depends, wherever persona_id arrives in a
request body instead of the path — see app/routers/scheduled_calls.py).
"""
import uuid

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

import storage.persona_store as persona_store
import storage.tool_store as tool_store
from auth.security import decode_access_token
from compiler.models import AssembledPersona
from config import get_settings
from db.models import User
from db.session import get_db

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=401, detail="not authenticated", headers={"WWW-Authenticate": "Bearer"}
    )
    if credentials is None:
        raise unauthorized
    user_id = decode_access_token(credentials.credentials, get_settings())
    if user_id is None:
        raise unauthorized
    user = await db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


async def require_persona(
    persona_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> AssembledPersona:
    try:
        pid = uuid.UUID(persona_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="unknown persona_id")
    persona = await persona_store.get(db, pid, user.id)
    if persona is None:
        raise HTTPException(status_code=404, detail="unknown persona_id")
    return persona


async def validate_tool_instance_ids(
    tool_instance_ids: list[str], db: AsyncSession, user_id: uuid.UUID
) -> None:
    """Shared by create_persona and the tools-edit route (both attach
    tool_instance_ids to a persona) — raises 400 listing every unknown id
    at once rather than failing on just the first. Called directly (not
    via Depends) since it validates a field nested in a body, not a path
    param FastAPI can resolve on its own."""
    unknown = []
    for tid in tool_instance_ids:
        try:
            found = await tool_store.get_instance(db, uuid.UUID(tid), user_id)
        except ValueError:
            found = None
        if found is None:
            unknown.append(tid)
    if unknown:
        raise HTTPException(status_code=400, detail=f"unknown tool_instance_id(s): {', '.join(unknown)}")
