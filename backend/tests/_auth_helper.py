"""Shared helper for tests that need an authenticated user against the
real Postgres DB (see backend/README.md's Tests section) — not itself a
test, tests/run_all.sh only globs test_*.py so this file is skipped.
Every test user is uniquely emailed and deleted at the end of its test
(cascades to every persona/tool_instance/scheduled_call/chat_message it
owns via the FK ondelete="CASCADE" in db/models.py), so repeat runs don't
pile up data in a real, shared database.
"""
import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine

from config import get_settings
from db.models import User
from db.session import asyncpg_url


def register_test_user(client: TestClient) -> tuple[dict, str]:
    """Registers a uniquely-emailed user. Returns (auth_headers, user_id)."""
    email = f"test-{uuid.uuid4()}@example.com"
    resp = client.post("/auth/register", json={"email": email, "password": "test-password-123"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]["id"]


def delete_test_user(user_id: str) -> None:
    """A fresh, throwaway engine — not db.session's shared singleton,
    which by this point is bound to TestClient's portal event loop.
    asyncpg connections are loop-bound, so reusing that engine from this
    function's own asyncio.run() loop raises "attached to a different
    loop"; a disposable engine sidesteps needing to share one at all.
    """

    async def _delete():
        engine = create_async_engine(asyncpg_url(get_settings().database_url))
        try:
            async with engine.connect() as conn:
                await conn.execute(delete(User).where(User.id == uuid.UUID(user_id)))
                await conn.commit()
        finally:
            await engine.dispose()

    asyncio.run(_delete())
