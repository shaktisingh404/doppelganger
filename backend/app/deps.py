"""Shared FastAPI route dependencies — the DRY seam for "get persona or
404", used by every /personas/{id}/... route (and called directly, not via
Depends, wherever persona_id arrives in a request body instead of the
path — see app/routers/scheduled_calls.py).
"""
from fastapi import HTTPException

from app.state import persona_store
from compiler.models import AssembledPersona


def require_persona(persona_id: str) -> AssembledPersona:
    persona = persona_store.get(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="unknown persona_id")
    return persona
