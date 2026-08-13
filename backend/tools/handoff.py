"""handoff tool: hands a conversation off to a *different assistant*
(persona) partway through a chat — matching Vapi's handoff tool (routing
between assistants), not a human-escalation concept.

The model picks a destination via an enum built from the tool's
configured HandoffDestination list (each maps an existing persona_id to
the description that tells the model when that destination fits) — same
config-vs-call-time-args split as scheduler/tool.py's schedule_callback:
the destinations and their descriptions are fixed at activation time, the
model only chooses *which one, when*.

Execution doesn't touch history or start a new chat thread — it marks
the current thread's "active persona" via storage/persona_store.py's
override (set_active), so the next turn's system_prompt/tools resolve to
the destination persona while the conversation and its persona_id/URL
stay exactly where they were. Every lookup here is scoped to user_id —
a destination is always one of the caller's own personas (tools.py
validates this at activation time), so this can never cross into
another user's data even if a token were somehow reused.
"""
import json
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

import storage.persona_store as persona_store
from tools.models import ActivatedTool

logger = logging.getLogger("tools.handoff")


async def _resolve_destinations(
    db: AsyncSession, activated: ActivatedTool, user_id: uuid.UUID
) -> list[tuple[str, str, str]]:
    """(destination name, description, persona_id) for each destination
    whose persona still exists — skipped, not fatal, if one's been
    deleted (no delete endpoint exists today, but resolving defensively
    here costs nothing and avoids a future footgun)."""
    resolved = []
    for dest in activated.destinations:
        persona = await persona_store.get(db, uuid.UUID(dest.persona_id), user_id)
        if persona is not None:
            resolved.append((persona.name, dest.description, dest.persona_id))
    return resolved


async def build_handoff_schema(db: AsyncSession, activated: ActivatedTool, user_id: uuid.UUID) -> dict | None:
    """None if every configured destination has become unresolvable —
    the caller should omit the tool entirely rather than offer a handoff
    with nowhere to go."""
    resolved = await _resolve_destinations(db, activated, user_id)
    if not resolved:
        return None

    destination_lines = "\n".join(f"- {name}: {description}" for name, description, _ in resolved)
    return {
        "name": "request_handoff",
        "description": (
            "Hand this conversation off to a different, better-suited assistant. "
            f"Available destinations:\n{destination_lines}"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "destination_name": {"type": "string", "enum": [name for name, _, _ in resolved]},
                "reason": {
                    "type": "string",
                    "description": "Short reason this conversation is being handed off.",
                },
            },
            "required": ["destination_name", "reason"],
        },
    }


async def execute_handoff(
    db: AsyncSession,
    activated: ActivatedTool,
    persona_id: str,
    user_id: uuid.UUID,
    args: dict,
) -> str:
    by_name = {name: pid for name, _, pid in await _resolve_destinations(db, activated, user_id)}
    destination_name = args.get("destination_name", "")
    destination_persona_id = by_name.get(destination_name)

    if destination_persona_id is None:
        return json.dumps({"error": f"unknown handoff destination {destination_name!r}"})

    await persona_store.set_active(db, uuid.UUID(persona_id), uuid.UUID(destination_persona_id), user_id)
    logger.warning(
        "handoff_requested persona_id=%s destination=%s reason=%s",
        persona_id,
        destination_name,
        args.get("reason", ""),
    )
    return json.dumps({"handed_off_to": destination_name})
