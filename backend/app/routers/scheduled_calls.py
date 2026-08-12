"""Scheduled-callback admin/debug routes. scheduler/tool.py's
schedule_callback is also reachable live, mid-chat, via the
schedule_callback tool wired into POST /personas/{id}/chat
(app/routers/personas.py) — this router exists to create/inspect rows
directly without going through a chat turn.
"""
from fastapi import APIRouter, HTTPException

from app.deps import require_persona
from app.schemas import ScheduleCallbackRequest
from app.state import scheduled_call_store
from config import get_settings
from scheduler.models import ScheduledCall, ScheduledCallStatus
from scheduler.tool import ScheduleCallbackError, schedule_callback

router = APIRouter(prefix="/scheduled-calls", tags=["scheduled-calls"])


@router.post("", response_model=ScheduledCall)
def create_scheduled_call(req: ScheduleCallbackRequest):
    require_persona(req.persona_id)
    try:
        return schedule_callback(
            scheduled_call_store,
            get_settings(),
            persona_id=req.persona_id,
            phone_number=req.phone_number,
            source_call_id=req.source_call_id,
            scheduled_time=req.scheduled_time,
            context_summary=req.context_summary,
            resume_stage=req.resume_stage,
        )
    except ScheduleCallbackError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[ScheduledCall])
def list_scheduled_calls(status: ScheduledCallStatus | None = None):
    return scheduled_call_store.list(status=status)
