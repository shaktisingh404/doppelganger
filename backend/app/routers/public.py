"""Public, unauthenticated chat routes for a persona's share link
(enabled via POST /personas/{id}/share). No Depends(get_current_user)
anywhere in this file — a visitor here is never a User row, just a
share_token plus a session_id their browser holds in localStorage.

Every route resolves the persona (and its owner's user_id) via
_require_shared_persona first. Every internal call after that —
persona_store.get_effective, tool_store.get_instance, build_chat_tools —
is scoped by that owner's user_id exactly as if the owner had made the
call themselves; the anonymous visitor only ever supplies share_token and
session_id, never anything persona-internal.

handoff is deliberately not offered here (build_chat_tools's
include_handoff=False) — see tools/registry.py's docstring for why: it
redirects by persona, not by session, so offering it publicly would let
one visitor's handoff silently redirect every other concurrent visitor's
conversation too.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

import storage.persona_store as persona_store
import storage.public_session_store as public_session_store
import storage.tool_store as tool_store
from app.schemas import ChatMessage, ChatResponse, PublicChatRequest, PublicPersonaInfo, PublicSessionResponse
from compiler.models import AssembledPersona
from config import get_settings
from db.session import get_db
from providers.llm import run_turn
from tools.registry import build_chat_tools

router = APIRouter(prefix="/public", tags=["public"])


async def _require_shared_persona(db: AsyncSession, share_token: str) -> tuple[AssembledPersona, uuid.UUID]:
    found = await persona_store.get_by_share_token(db, share_token)
    if found is None:
        # Same message whether the token never existed or sharing was
        # since disabled -- no reason to distinguish for an outsider.
        raise HTTPException(status_code=404, detail="unknown or unshared link")
    return found


async def _require_session(db: AsyncSession, persona_id: uuid.UUID, session_id: str) -> uuid.UUID:
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="unknown session_id")
    if not await public_session_store.belongs_to(db, sid, persona_id):
        raise HTTPException(status_code=404, detail="unknown session_id")
    return sid


@router.get("/{share_token}", response_model=PublicPersonaInfo)
async def get_public_persona(share_token: str, db: AsyncSession = Depends(get_db)):
    persona, _ = await _require_shared_persona(db, share_token)
    return PublicPersonaInfo(name=persona.name)


@router.post("/{share_token}/session", response_model=PublicSessionResponse)
async def create_public_session(share_token: str, db: AsyncSession = Depends(get_db)):
    persona, _ = await _require_shared_persona(db, share_token)
    session_id = await public_session_store.create(db, uuid.UUID(persona.persona_id))
    return PublicSessionResponse(session_id=str(session_id))


@router.post("/{share_token}/chat", response_model=ChatResponse)
async def public_chat(share_token: str, req: PublicChatRequest, db: AsyncSession = Depends(get_db)):
    persona, owner_id = await _require_shared_persona(db, share_token)
    pid = uuid.UUID(persona.persona_id)
    session_id = await _require_session(db, pid, req.session_id)

    history = await persona_store.get_session_history(db, pid, session_id)

    # Same handoff-aware resolution the authenticated chat route uses —
    # handoff state lives on the persona, not the session, so this is
    # consistent whether or not this particular session ever triggers one.
    effective = await persona_store.get_effective(db, pid, owner_id) or persona

    activated_tools = []
    for tid in effective.tool_instance_ids:
        try:
            tool = await tool_store.get_instance(db, uuid.UUID(tid), owner_id)
        except ValueError:
            tool = None
        if tool is not None:
            activated_tools.append(tool)

    tools, tool_executor = await build_chat_tools(
        db,
        activated_tools,
        persona.persona_id,
        owner_id,
        get_settings(),
        include_handoff=False,
        session_id=str(session_id),
    )

    reply = await run_turn(
        effective.system_prompt,
        history,
        req.message,
        tools=tools,
        tool_executor=tool_executor,
    )
    await persona_store.append_session_history(db, pid, session_id, "user", req.message)
    await persona_store.append_session_history(db, pid, session_id, "assistant", reply)
    return ChatResponse(reply=reply)


@router.get("/{share_token}/chat/history", response_model=list[ChatMessage])
async def get_public_chat_history(share_token: str, session_id: str, db: AsyncSession = Depends(get_db)):
    persona, _ = await _require_shared_persona(db, share_token)
    pid = uuid.UUID(persona.persona_id)
    sid = await _require_session(db, pid, session_id)
    return await persona_store.get_session_history(db, pid, sid)
