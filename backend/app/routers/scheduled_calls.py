"""Scheduled-callback admin/debug routes. scheduler/tool.py's
schedule_callback is also reachable live, mid-chat, via the
schedule_callback tool wired into POST /personas/{id}/chat
(app/routers/personas.py) — this router exists to create/inspect rows
directly without going through a chat turn.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

import scheduler.models as scheduled_call_store
from app.deps import get_current_user, require_persona
from app.schemas import ScheduleCallbackRequest
from config import get_settings
from db.models import User
from db.session import get_db
from scheduler.models import ScheduledCall, ScheduledCallStatus
from scheduler.tool import ScheduleCallbackError, schedule_callback

router = APIRouter(prefix="/scheduled-calls", tags=["scheduled-calls"])


@router.post("", response_model=ScheduledCall)
async def create_scheduled_call(
    req: ScheduleCallbackRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    # req.persona_id arrives in the body, not the path, so require_persona
    # is called directly with this route's own already-resolved db/user
    # rather than via Depends (which only resolves defaults for route params).
    await require_persona(req.persona_id, db, user)
    try:
        return await schedule_callback(
            db,
            get_settings(),
            user_id=user.id,
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
async def list_scheduled_calls(
    status: ScheduledCallStatus | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await scheduled_call_store.list_all(db, user.id, status=status)
