"""DB-backed persona + chat-history storage, scoped per user_id. Async
module-level functions rather than a class — there's no more in-memory
state to encapsulate now that the DB session (passed in per call) carries
it, matching the shape FastAPI's Depends(get_db) already gives every route.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compiler.models import AssembledPersona
from db.models import ChatMessage as ChatMessageRow
from db.models import Persona as PersonaRow


def _to_domain(row: PersonaRow) -> AssembledPersona:
    return AssembledPersona(
        persona_id=str(row.id),
        archetype_id=row.archetype_id,
        name=row.name,
        first_message=row.first_message,
        system_prompt=row.system_prompt,
        version=row.version,
        created_at=row.created_at,
        tool_instance_ids=row.tool_instance_ids,
    )


async def _get_row(db: AsyncSession, persona_id: uuid.UUID, user_id: uuid.UUID) -> PersonaRow | None:
    return await db.scalar(
        select(PersonaRow).where(PersonaRow.id == persona_id, PersonaRow.user_id == user_id)
    )


async def add(db: AsyncSession, persona: AssembledPersona, user_id: uuid.UUID) -> None:
    row = PersonaRow(
        id=uuid.UUID(persona.persona_id),
        user_id=user_id,
        archetype_id=persona.archetype_id,
        name=persona.name,
        first_message=persona.first_message,
        system_prompt=persona.system_prompt,
        version=persona.version,
        tool_instance_ids=persona.tool_instance_ids,
    )
    db.add(row)
    await db.flush()
    # Seeded so the chat UI can show it as the opening bubble through the
    # same history it already polls — no separate delivery path.
    if persona.first_message:
        await append_history(db, row.id, "assistant", persona.first_message)


async def update_tools(
    db: AsyncSession, persona_id: uuid.UUID, user_id: uuid.UUID, tool_instance_ids: list[str]
) -> AssembledPersona | None:
    row = await _get_row(db, persona_id, user_id)
    if row is None:
        return None
    row.tool_instance_ids = tool_instance_ids
    await db.flush()
    return _to_domain(row)


async def get(db: AsyncSession, persona_id: uuid.UUID, user_id: uuid.UUID) -> AssembledPersona | None:
    row = await _get_row(db, persona_id, user_id)
    return _to_domain(row) if row else None


async def get_effective(db: AsyncSession, persona_id: uuid.UUID, user_id: uuid.UUID) -> AssembledPersona | None:
    """The persona whose system_prompt/tools should answer the next turn
    in this chat thread — the handoff destination if tools/handoff.py has
    redirected this thread, otherwise the thread's own persona. Both rows
    are looked up scoped to the same user_id: a handoff destination is
    always one of the caller's own personas (tools.py validates this at
    activation time), so this can never cross into another user's data."""
    row = await _get_row(db, persona_id, user_id)
    if row is None:
        return None
    if row.active_persona_id is not None:
        active_row = await _get_row(db, row.active_persona_id, user_id)
        if active_row is not None:
            return _to_domain(active_row)
    return _to_domain(row)


async def set_active(db: AsyncSession, persona_id: uuid.UUID, active_persona_id: uuid.UUID, user_id: uuid.UUID) -> None:
    row = await _get_row(db, persona_id, user_id)
    if row is not None:
        row.active_persona_id = active_persona_id
        await db.flush()


async def list_all(db: AsyncSession, user_id: uuid.UUID) -> list[AssembledPersona]:
    result = await db.scalars(
        select(PersonaRow).where(PersonaRow.user_id == user_id).order_by(PersonaRow.created_at)
    )
    return [_to_domain(r) for r in result]


async def get_history(db: AsyncSession, persona_id: uuid.UUID, user_id: uuid.UUID) -> list[dict[str, str]]:
    # Confirm ownership first -- otherwise a guessed persona_id from
    # another user could read that user's chat transcript.
    if await _get_row(db, persona_id, user_id) is None:
        return []
    result = await db.scalars(
        select(ChatMessageRow).where(ChatMessageRow.persona_id == persona_id).order_by(ChatMessageRow.seq)
    )
    return [{"role": m.role, "content": m.content} for m in result]


async def append_history(db: AsyncSession, persona_id: uuid.UUID, role: str, content: str) -> None:
    db.add(ChatMessageRow(persona_id=persona_id, role=role, content=content))
    await db.flush()
