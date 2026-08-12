"""schedule_callback tool: lets a persona ask, mid-chat, for a future
follow-up instead of continuing now. Wired into the /personas/{id}/chat
route (app/routers/personas.py) via providers.llm.run_turn's
tools/tool_executor args — execute_schedule_callback_tool_call below is
the tool_executor, kept here rather than in app/ since it's scheduler
domain logic, not routing.

Schema shape matches the {name, description, parameters} convention already
used by ArchetypeSpec.tool_schema_stubs (see compiler/models.py).

The model resolves relative time ("tomorrow after 3pm") into an absolute,
tz-aware timestamp before calling this tool — this function only validates
that result, it does no NLP/parsing of relative language itself.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone

from config import Settings
from scheduler.models import ScheduledCall, ScheduledCallStore

SCHEDULE_CALLBACK_TOOL = {
    "name": "schedule_callback",
    "description": (
        "Schedule a future outbound call back to this caller instead of "
        "continuing now. Resolve any relative time the caller gives you "
        "(e.g. 'tomorrow after 3pm') into an absolute ISO 8601 timestamp "
        "with a UTC offset, using the call's known current time and "
        "timezone, before calling this tool."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "scheduled_time": {
                "type": "string",
                "description": "Absolute ISO 8601 timestamp (with UTC offset) for the callback.",
            },
            "context_summary": {
                "type": "string",
                "description": "Short summary of why this callback exists and what's been discussed.",
            },
            "resume_stage": {
                "type": "string",
                "description": "Workflow stage to resume at on the callback, if applicable.",
            },
        },
        "required": ["scheduled_time", "context_summary"],
    },
}


class ScheduleCallbackError(ValueError):
    """A schedule_callback tool call failed validation — surface the
    message back to the model as the tool's error result rather than
    silently accepting a bad timestamp or an abusive request."""


def schedule_callback(
    store: ScheduledCallStore,
    settings: Settings,
    *,
    persona_id: str,
    phone_number: str,
    source_call_id: str,
    scheduled_time: str,
    context_summary: str,
    resume_stage: str | None = None,
    now: datetime | None = None,
) -> ScheduledCall:
    now = now or datetime.now(timezone.utc)

    try:
        target = datetime.fromisoformat(scheduled_time)
    except ValueError as e:
        raise ScheduleCallbackError(
            f"scheduled_time is not a valid ISO 8601 timestamp: {scheduled_time!r}"
        ) from e
    if target.tzinfo is None:
        raise ScheduleCallbackError(
            "scheduled_time must include a UTC offset — resolve it to an "
            "absolute timestamp before calling this tool"
        )
    target = target.astimezone(timezone.utc)

    if target <= now:
        raise ScheduleCallbackError(f"scheduled_time {target.isoformat()} is not in the future")

    max_window = timedelta(days=settings.scheduled_callback_max_window_days)
    if target > now + max_window:
        raise ScheduleCallbackError(
            f"scheduled_time is more than {settings.scheduled_callback_max_window_days} "
            "days out"
        )

    pending = store.count_pending_for_number(phone_number)
    if pending >= settings.scheduled_callback_max_pending_per_number:
        raise ScheduleCallbackError(
            f"{phone_number} already has {pending} pending callbacks "
            f"(max {settings.scheduled_callback_max_pending_per_number})"
        )

    row = ScheduledCall(
        id=str(uuid.uuid4()),
        persona_id=persona_id,
        phone_number=phone_number,
        scheduled_time=target,
        context_summary=context_summary,
        resume_stage=resume_stage,
        source_call_id=source_call_id,
    )
    store.add(row)
    return row


async def execute_schedule_callback_tool_call(
    store: ScheduledCallStore, settings: Settings, persona_id: str, tool_name: str, args: dict
) -> str:
    """Adapts providers.llm.run_turn's generic (tool_name, args) -> JSON
    string tool_executor contract to schedule_callback."""
    if tool_name != "schedule_callback":
        return json.dumps({"error": f"unknown tool {tool_name}"})
    try:
        row = schedule_callback(
            store,
            settings,
            persona_id=persona_id,
            # chat has no phone number to key the per-identity pending cap on,
            # so persona_id (1:1 with a chat thread today) stands in for it.
            phone_number=persona_id,
            source_call_id="chat",
            scheduled_time=args.get("scheduled_time", ""),
            context_summary=args.get("context_summary", ""),
            resume_stage=args.get("resume_stage"),
        )
    except ScheduleCallbackError as e:
        return json.dumps({"error": str(e)})
    return json.dumps({"scheduled": True, "id": row.id, "scheduled_time": row.scheduled_time.isoformat()})
