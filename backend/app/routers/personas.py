"""Persona CRUD + chat routes. Every route requires auth; personas/tools/
history are all scoped to the authenticated user (see storage/persona_store.py).

Creation is two steps, not one: POST /generate turns free text into a
system_prompt string (the "Generate" button); POST / turns a (possibly
hand-edited) system_prompt into a real, stored persona. Nothing forces a
caller through /generate first — system_prompt can be typed from scratch.
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

import storage.persona_store as persona_store
import storage.tool_store as tool_store
from app.deps import get_current_user, require_persona, validate_tool_instance_ids
from app.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    CreatePersonaRequest,
    GeneratePromptResponse,
    UpdatePersonaRequest,
    UpdatePersonaToolsRequest,
)
from app.state import archetype_store
from compiler.models import AssembledPersona, InstanceInput
from compiler.pipeline import generate_system_prompt, instantiate_persona
from config import get_settings
from db.models import User
from db.session import get_db
from guardrails.drift import check_drift
from providers.llm import run_turn
from tools.registry import build_chat_tools

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/personas", tags=["personas"])


@router.post("/generate", response_model=GeneratePromptResponse)
async def generate_prompt(instance: InstanceInput, user: User = Depends(get_current_user)):
    try:
        system_prompt = await generate_system_prompt(instance, archetype_store)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return GeneratePromptResponse(system_prompt=system_prompt)


@router.post("", response_model=AssembledPersona)
async def create_persona(
    req: CreatePersonaRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    await validate_tool_instance_ids(req.tool_instance_ids, db, user.id)

    persona = instantiate_persona(
        name=req.name,
        system_prompt=req.system_prompt,
        first_message=req.first_message,
        archetype_id=req.archetype_id,
        tool_instance_ids=req.tool_instance_ids,
    )
    await persona_store.add(db, persona, user.id)
    return persona


@router.get("", response_model=list[AssembledPersona])
async def list_personas(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await persona_store.list_all(db, user.id)


@router.get("/{persona_id}", response_model=AssembledPersona)
async def get_persona(persona: AssembledPersona = Depends(require_persona)):
    return persona


@router.put("/{persona_id}", response_model=AssembledPersona)
async def update_persona(
    req: UpdatePersonaRequest,
    persona: AssembledPersona = Depends(require_persona),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await persona_store.update(
        db, uuid.UUID(persona.persona_id), user.id,
        name=req.name, system_prompt=req.system_prompt, first_message=req.first_message,
    )


@router.delete("/{persona_id}", status_code=204)
async def delete_persona(
    persona: AssembledPersona = Depends(require_persona),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Soft delete — see storage/persona_store.py::delete. A persona used
    as a handoff destination elsewhere just stops resolving as one
    (tools/handoff.py already skips unresolvable destinations); no cascade
    needed on this side."""
    await persona_store.delete(db, uuid.UUID(persona.persona_id), user.id)


@router.put("/{persona_id}/tools", response_model=AssembledPersona)
async def update_persona_tools(
    req: UpdatePersonaToolsRequest,
    persona: AssembledPersona = Depends(require_persona),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Replaces the whole attached-tools list — add or remove by sending
    the new full set, same as the create-time Tools checkboxes just
    re-submitted after edits."""
    await validate_tool_instance_ids(req.tool_instance_ids, db, user.id)
    return await persona_store.update_tools(db, uuid.UUID(persona.persona_id), user.id, req.tool_instance_ids)


@router.post("/{persona_id}/chat", response_model=ChatResponse)
async def chat(
    persona_id: str,
    req: ChatRequest,
    persona: AssembledPersona = Depends(require_persona),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    pid = uuid.UUID(persona_id)
    history = await persona_store.get_history(db, pid, user.id)
    check_drift(history)  # TODO: act on the result once implemented

    # The *effective* persona for this turn — the handoff destination if
    # tools/handoff.py has redirected this thread, otherwise the thread's
    # own persona. `persona` (above) stays the thread's original identity
    # for validating persona_id and reading history; only which
    # system_prompt/tools answer with can change.
    effective = await persona_store.get_effective(db, pid, user.id) or persona

    # Defensive skip-on-miss: resolving instead of trusting
    # tool_instance_ids directly means a chat turn never crashes on a
    # dangling id — it silently loses that one tool instead. A soft-
    # deleted/detached tool is expected here (tool_store.get_instance just
    # returns None, no exception); a malformed id string hitting the
    # ValueError branch below would mean one got into storage without
    # going through validate_tool_instance_ids, worth knowing about.
    activated_tools = []
    for tid in effective.tool_instance_ids:
        try:
            tool = await tool_store.get_instance(db, uuid.UUID(tid), user.id)
        except ValueError:
            tool = None
            logger.warning("persona_id=%s has a malformed tool_instance_id=%r", persona_id, tid)
        if tool is not None:
            activated_tools.append(tool)

    tools, tool_executor = await build_chat_tools(db, activated_tools, persona_id, user.id, get_settings())

    reply = await run_turn(
        effective.system_prompt,
        history,
        req.message,
        tools=tools,
        tool_executor=tool_executor,
    )
    await persona_store.append_history(db, pid, "user", req.message)
    await persona_store.append_history(db, pid, "assistant", reply)
    return ChatResponse(reply=reply)


@router.get("/{persona_id}/chat/history", response_model=list[ChatMessage])
async def get_chat_history(
    persona_id: str,
    persona: AssembledPersona = Depends(require_persona),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Polled by the frontend so proactive messages — e.g. a fired
    scheduled follow-up (scheduler/dispatcher.py) — show up without the
    user having to send anything first."""
    return await persona_store.get_history(db, uuid.UUID(persona_id), user.id)
