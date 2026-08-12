"""Background poller that fires due scheduled callbacks as a proactive
chat message from the persona.

Chat is the only live channel this product has, so the scheduler fires
through providers.llm.run_turn against the persona's own chat history.
Calling (Twilio origination, the realtime bridge) was removed; if it comes
back later, add a channel branch here rather than firing a phone call
inline.

APScheduler's AsyncIOScheduler just drives the poll interval — a single
job, not a task queue. See config.py for the interval/retry-delay knobs.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from compiler.models import AssembledPersona
from config import Settings
from providers.llm import run_turn
from scheduler.models import ScheduledCall, ScheduledCallStore

logger = logging.getLogger("scheduler")

_MAX_ATTEMPTS = 2  # the original attempt + exactly one retry, no backoff series

GetPersona = Callable[[str], "AssembledPersona | None"]
GetHistory = Callable[[str], list[dict[str, str]]]


def build_resume_context_block(context_summary: str, resume_stage: str | None) -> str:
    """The hidden instruction fed to the model to produce a proactive
    follow-up turn — never shown to the user verbatim, only the model's
    reply is.
    """
    lines = [
        "This is a scheduled follow-up you arranged earlier.",
        f"Context: {context_summary}",
    ]
    if resume_stage:
        lines.append(f"Resume at stage: {resume_stage}")
    lines.append("Send a brief opening message now to resume the conversation.")
    return "\n".join(lines)


async def _dispatch_one(
    row: ScheduledCall,
    store: ScheduledCallStore,
    settings: Settings,
    get_persona: GetPersona,
    get_history: GetHistory,
) -> None:
    row.attempts += 1
    persona = get_persona(row.persona_id)
    if persona is None:
        row.status = "failed"
        store.update(row)
        logger.error(
            "scheduled_followup_unknown_persona id=%s persona_id=%s", row.id, row.persona_id
        )
        return

    history = get_history(row.persona_id)
    prompt = build_resume_context_block(row.context_summary, row.resume_stage)

    try:
        reply = await run_turn(persona.system_prompt, history, prompt)
    except Exception:
        logger.exception(
            "scheduled_followup_failed id=%s persona_id=%s attempt=%d",
            row.id,
            row.persona_id,
            row.attempts,
        )
        if row.attempts < _MAX_ATTEMPTS:
            row.scheduled_time = datetime.now(timezone.utc) + timedelta(
                seconds=settings.scheduled_callback_retry_delay_seconds
            )
            store.update(row)
        else:
            row.status = "failed"
            store.update(row)
            logger.error(
                "scheduled_callback_failed id=%s persona_id=%s attempts=%d",
                row.id,
                row.persona_id,
                row.attempts,
            )
        return

    history.append({"role": "assistant", "content": reply})
    row.status = "completed"
    store.update(row)
    logger.info(
        "scheduled_followup_delivered id=%s persona_id=%s attempt=%d",
        row.id,
        row.persona_id,
        row.attempts,
    )


async def poll_once(
    store: ScheduledCallStore, settings: Settings, get_persona: GetPersona, get_history: GetHistory
) -> None:
    now = datetime.now(timezone.utc)
    due = [r for r in store.list(status="pending") if r.scheduled_time <= now]
    for row in due:
        await _dispatch_one(row, store, settings, get_persona, get_history)


def start_dispatcher(
    store: ScheduledCallStore,
    settings: Settings,
    get_persona: GetPersona,
    get_history: GetHistory,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        poll_once,
        "interval",
        seconds=settings.scheduled_callback_poll_interval_seconds,
        args=[store, settings, get_persona, get_history],
        id="scheduled_callback_poll",
    )
    scheduler.start()
    return scheduler
