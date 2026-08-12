"""Persona CRUD + chat routes."""
from fastapi import APIRouter, Depends, HTTPException

from app.deps import require_persona
from app.schemas import ChatMessage, ChatRequest, ChatResponse
from app.state import archetype_store, persona_store, scheduled_call_store
from compiler.models import AssembledPersona, InstanceInput
from compiler.pipeline import build_persona
from config import get_settings
from guardrails.drift import check_drift
from providers.llm import run_turn
from scheduler.tool import SCHEDULE_CALLBACK_TOOL, execute_schedule_callback_tool_call

router = APIRouter(prefix="/personas", tags=["personas"])


@router.post("", response_model=AssembledPersona)
async def create_persona(instance: InstanceInput):
    try:
        persona = await build_persona(instance, archetype_store)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    persona_store.add(persona)
    return persona


@router.get("/{persona_id}", response_model=AssembledPersona)
def get_persona(persona: AssembledPersona = Depends(require_persona)):
    return persona


@router.post("/{persona_id}/chat", response_model=ChatResponse)
async def chat(
    persona_id: str, req: ChatRequest, persona: AssembledPersona = Depends(require_persona)
):
    history = persona_store.history(persona_id)
    check_drift(history)  # TODO: act on the result once implemented

    reply = await run_turn(
        persona.system_prompt,
        history,
        req.message,
        tools=[{"type": "function", "function": SCHEDULE_CALLBACK_TOOL}],
        tool_executor=lambda name, args: execute_schedule_callback_tool_call(
            scheduled_call_store, get_settings(), persona_id, name, args
        ),
    )
    history.append({"role": "user", "content": req.message})
    history.append({"role": "assistant", "content": reply})
    return ChatResponse(reply=reply)


@router.get("/{persona_id}/chat/history", response_model=list[ChatMessage])
def get_chat_history(persona_id: str, persona: AssembledPersona = Depends(require_persona)):
    """Polled by the frontend so proactive messages — e.g. a fired
    scheduled follow-up (scheduler/dispatcher.py) — show up without the
    user having to send anything first."""
    return persona_store.history(persona_id)
