"""Background poller that fires due scheduled callbacks as a proactive
chat message from the persona.

Chat is the only live channel this product has, so the scheduler fires
through providers.llm.run_turn against the persona's own chat history.
Calling (Twilio origination, the realtime bridge) was removed; if it comes
back later, add a channel branch here rather than firing a phone call
inline.

Runs outside any HTTP request, so unlike every router it can't use
Depends(get_db) — each dispatched row gets its own session, opened and
committed/rolled back here directly (db/session.py's get_db does the same
thing for a request; not reused as-is because a bare `async for` over a
generator dependency doesn't correctly propagate an exception from the
loop body back into its except/rollback block the way FastAPI's own DI
machinery does).

APScheduler's AsyncIOScheduler just drives the poll interval — a single
job, not a task queue. See config.py for the interval/retry-delay knobs.

Safe to run this in more than one process at once (multiple uvicorn
workers, multiple replicas) with no broker: scheduler/models.py::claim_due
atomically claims due rows via a single UPDATE ... RETURNING, so two
pollers racing on the same row is a non-issue — Postgres serializes it.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import scheduler.models as scheduled_call_store
import storage.persona_store as persona_store
from config import Settings, get_settings
from db.session import get_session_factory
from providers.llm import run_turn
from scheduler.models import ScheduledCall

logger = logging.getLogger("scheduler")

_MAX_ATTEMPTS = 2  # the original attempt + exactly one retry, no backoff series


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


async def _dispatch_one(row: ScheduledCall, user_id: uuid.UUID, settings: Settings) -> None:
    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            row.attempts += 1
            persona_id = uuid.UUID(row.persona_id)
            # get_effective, not get: if this persona has since been
            # handed off (tools/handoff.py), the follow-up should come
            # from whoever is actually answering the thread now.
            persona = await persona_store.get_effective(db, persona_id, user_id)
            if persona is None:
                row.status = "failed"
                await scheduled_call_store.update(db, row, user_id)
                await db.commit()
                logger.error(
                    "scheduled_followup_unknown_persona id=%s persona_id=%s", row.id, row.persona_id
                )
                return

            # session_id set -> this callback was requested from inside a
            # public visitor's conversation (app/routers/public.py), so the
            # follow-up must land back in that same session's thread, not
            # the owner's own. Handoff is never offered in public sessions
            # (tools/registry.py's include_handoff=False there), so
            # get_effective's persona-wide active_persona_id resolution
            # above is still correct either way.
            session_id = uuid.UUID(row.session_id) if row.session_id else None
            if session_id is not None:
                history = await persona_store.get_session_history(db, persona_id, session_id)
            else:
                history = await persona_store.get_history(db, persona_id, user_id)
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
                    # Un-claim it: claim_due only ever matches status="pending",
                    # so without this a retried row would stay "processing"
                    # forever and never get polled again.
                    row.status = "pending"
                    row.scheduled_time = datetime.now(timezone.utc) + timedelta(
                        seconds=settings.scheduled_callback_retry_delay_seconds
                    )
                else:
                    row.status = "failed"
                    logger.error(
                        "scheduled_callback_failed id=%s persona_id=%s attempts=%d",
                        row.id,
                        row.persona_id,
                        row.attempts,
                    )
                await scheduled_call_store.update(db, row, user_id)
                await db.commit()
                return

            if session_id is not None:
                await persona_store.append_session_history(db, persona_id, session_id, "assistant", reply)
            else:
                await persona_store.append_history(db, persona_id, "assistant", reply)
            row.status = "completed"
            await scheduled_call_store.update(db, row, user_id)
            await db.commit()
            logger.info(
                "scheduled_followup_delivered id=%s persona_id=%s attempt=%d",
                row.id,
                row.persona_id,
                row.attempts,
            )
        except Exception:
            # Anything not already handled above (DB errors, bugs) —
            # already-logged run_turn failures don't re-hit this since
            # that inner except returns before propagating.
            logger.exception(
                "scheduled_followup_dispatch_error id=%s persona_id=%s attempt=%d",
                row.id,
                row.persona_id,
                row.attempts,
            )
            await db.rollback()
            raise


async def poll_once(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    session_factory = get_session_factory()
    async with session_factory() as db:
        due = await scheduled_call_store.claim_due(db, now)
    for row, user_id in due:
        await _dispatch_one(row, user_id, settings)


def start_dispatcher(settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        poll_once,
        "interval",
        seconds=settings.scheduled_callback_poll_interval_seconds,
        args=[settings],
        id="scheduled_callback_poll",
    )
    scheduler.start()
    return scheduler
