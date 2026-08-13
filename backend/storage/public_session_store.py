"""Storage for public_sessions — one row per anonymous visitor's
conversation with a persona shared via app/routers/public.py. Split out
from persona_store.py the same way tool_store.py/scheduler/models.py each
own their own table.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import PublicSession as PublicSessionRow


async def create(db: AsyncSession, persona_id: uuid.UUID) -> uuid.UUID:
    row = PublicSessionRow(persona_id=persona_id)
    db.add(row)
    await db.flush()
    return row.id


async def belongs_to(db: AsyncSession, session_id: uuid.UUID, persona_id: uuid.UUID) -> bool:
    """Defends against a session_id minted for one persona being replayed
    against a different persona's public endpoints (e.g. copy-pasted
    localStorage state, or a deliberate probe)."""
    row = await db.scalar(
        select(PublicSessionRow).where(PublicSessionRow.id == session_id, PublicSessionRow.persona_id == persona_id)
    )
    return row is not None
