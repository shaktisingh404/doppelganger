"""DB-backed persona + chat-history storage, scoped per user_id. Async
module-level functions rather than a class — there's no more in-memory
state to encapsulate now that the DB session (passed in per call) carries
it, matching the shape FastAPI's Depends(get_db) already gives every route.
"""
import secrets
import uuid
from datetime import datetime, timezone

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
        share_token=row.share_token,
    )


async def _get_row(db: AsyncSession, persona_id: uuid.UUID, user_id: uuid.UUID) -> PersonaRow | None:
    # deleted_at.is_(None): a soft-deleted persona is invisible to every
    # normal lookup, including get_effective()'s handoff-target resolution
    # below, which is what makes deleting a handoff destination silently
    # fall back to the thread's own persona rather than 500ing.
    return await db.scalar(
        select(PersonaRow).where(
            PersonaRow.id == persona_id, PersonaRow.user_id == user_id, PersonaRow.deleted_at.is_(None)
        )
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


async def update(
    db: AsyncSession, persona_id: uuid.UUID, user_id: uuid.UUID, *, name: str, system_prompt: str, first_message: str
) -> AssembledPersona | None:
    """Edits identity/prompt fields only — archetype_id and
    tool_instance_ids each have their own dedicated update path (the
    former is immutable, the latter is update_tools below)."""
    row = await _get_row(db, persona_id, user_id)
    if row is None:
        return None
    row.name = name
    row.system_prompt = system_prompt
    row.first_message = first_message
    await db.flush()
    return _to_domain(row)


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
        select(PersonaRow)
        .where(PersonaRow.user_id == user_id, PersonaRow.deleted_at.is_(None))
        .order_by(PersonaRow.created_at)
    )
    return [_to_domain(r) for r in result]


async def delete(db: AsyncSession, persona_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    row = await _get_row(db, persona_id, user_id)
    if row is None:
        return False
    row.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return True


async def detach_tool(db: AsyncSession, tool_instance_id: str, user_id: uuid.UUID) -> list[uuid.UUID]:
    """Cascades a tool-instance deletion: strips its id from every one of
    this user's personas that had it attached, so a deleted tool can't be
    silently called from a stale attachment list. Returns the ids of the
    personas actually changed."""
    result = await db.scalars(
        select(PersonaRow).where(PersonaRow.user_id == user_id, PersonaRow.deleted_at.is_(None))
    )
    changed = []
    for row in result:
        if tool_instance_id in row.tool_instance_ids:
            row.tool_instance_ids = [t for t in row.tool_instance_ids if t != tool_instance_id]
            changed.append(row.id)
    await db.flush()
    return changed


async def get_history(db: AsyncSession, persona_id: uuid.UUID, user_id: uuid.UUID) -> list[dict[str, str]]:
    # Confirm ownership first -- otherwise a guessed persona_id from
    # another user could read that user's chat transcript.
    if await _get_row(db, persona_id, user_id) is None:
        return []
    # session_id.is_(None): this is the owner's own authenticated test
    # thread specifically -- excludes every public visitor's conversation
    # (see get_session_history below), which now live in the same table.
    result = await db.scalars(
        select(ChatMessageRow)
        .where(ChatMessageRow.persona_id == persona_id, ChatMessageRow.session_id.is_(None))
        .order_by(ChatMessageRow.seq)
    )
    return [{"role": m.role, "content": m.content} for m in result]


async def append_history(db: AsyncSession, persona_id: uuid.UUID, role: str, content: str) -> None:
    db.add(ChatMessageRow(persona_id=persona_id, role=role, content=content))
    await db.flush()


async def get_session_history(
    db: AsyncSession, persona_id: uuid.UUID, session_id: uuid.UUID
) -> list[dict[str, str]]:
    """The public-chat counterpart of get_history — scoped by session_id
    instead of user_id, since a visitor is never authenticated. No
    ownership check needed here: the caller (app/routers/public.py)
    already validated session_id belongs to persona_id via
    public_session_store.belongs_to before ever reaching this."""
    result = await db.scalars(
        select(ChatMessageRow)
        .where(ChatMessageRow.persona_id == persona_id, ChatMessageRow.session_id == session_id)
        .order_by(ChatMessageRow.seq)
    )
    return [{"role": m.role, "content": m.content} for m in result]


async def append_session_history(
    db: AsyncSession, persona_id: uuid.UUID, session_id: uuid.UUID, role: str, content: str
) -> None:
    db.add(ChatMessageRow(persona_id=persona_id, session_id=session_id, role=role, content=content))
    await db.flush()


async def enable_sharing(db: AsyncSession, persona_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
    """Generates and stores a fresh share token, replacing any previous
    one -- re-enabling sharing after it was off always mints a new link
    rather than reviving the old one. Returns None if the persona doesn't
    exist/isn't owned by user_id."""
    row = await _get_row(db, persona_id, user_id)
    if row is None:
        return None
    row.share_token = secrets.token_urlsafe(24)
    await db.flush()
    return row.share_token


async def disable_sharing(db: AsyncSession, persona_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    row = await _get_row(db, persona_id, user_id)
    if row is None:
        return False
    row.share_token = None
    await db.flush()
    return True


async def get_by_share_token(db: AsyncSession, share_token: str) -> tuple[AssembledPersona, uuid.UUID] | None:
    """The one deliberately unauthenticated lookup in this module — backs
    every route in app/routers/public.py. Still excludes soft-deleted
    personas; a deleted persona's old share link should 404 like
    everything else about it does.

    Returns (persona, owner_user_id), not just the persona — same shape as
    scheduler/models.py::claim_due, for the same reason: an anonymous
    visitor has no user_id of their own, but every internal call this
    persona's chat turn makes (tool resolution, scheduling) still needs
    the *owner's* user_id to scope against, exactly as if the owner had
    made the call themselves."""
    row = await db.scalar(
        select(PersonaRow).where(PersonaRow.share_token == share_token, PersonaRow.deleted_at.is_(None))
    )
    return (_to_domain(row), row.user_id) if row else None
