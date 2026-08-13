"""scheduled_calls domain model + DB-backed, user-scoped storage. Async
module-level functions rather than a class — same shape as
storage/persona_store.py now that the DB session (passed in per call)
carries the state a dict used to.
"""
import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ScheduledCall as ScheduledCallRow

# "processing": a poller has atomically claimed the row (see claim_due)
# and is currently dispatching it -- transient, should never be visible
# for more than the length of one LLM call. Not reachable from the API
# (ScheduleCallbackRequest/schedule_callback only ever create "pending").
ScheduledCallStatus = Literal["pending", "processing", "completed", "failed", "cancelled"]


class ScheduledCall(BaseModel):
    id: str
    persona_id: str
    phone_number: str
    scheduled_time: datetime  # UTC
    context_summary: str
    resume_stage: str | None = None
    status: ScheduledCallStatus = "pending"
    source_call_id: str
    attempts: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Set when this callback was requested from inside a public visitor's
    # session (app/routers/public.py), not the owner's own authenticated
    # thread -- scheduler/dispatcher.py uses it to fire the eventual
    # proactive reply back into that same visitor's conversation rather
    # than the owner's.
    session_id: str | None = None


def _to_domain(row: ScheduledCallRow) -> ScheduledCall:
    return ScheduledCall(
        id=str(row.id),
        persona_id=str(row.persona_id),
        phone_number=row.phone_number,
        scheduled_time=row.scheduled_time,
        context_summary=row.context_summary,
        resume_stage=row.resume_stage,
        status=row.status,
        source_call_id=row.source_call_id,
        attempts=row.attempts,
        created_at=row.created_at,
        session_id=str(row.session_id) if row.session_id else None,
    )


async def add(db: AsyncSession, call: ScheduledCall, user_id: uuid.UUID) -> None:
    row = ScheduledCallRow(
        id=uuid.UUID(call.id),
        user_id=user_id,
        persona_id=uuid.UUID(call.persona_id),
        session_id=uuid.UUID(call.session_id) if call.session_id else None,
        phone_number=call.phone_number,
        scheduled_time=call.scheduled_time,
        context_summary=call.context_summary,
        resume_stage=call.resume_stage,
        status=call.status,
        source_call_id=call.source_call_id,
        attempts=call.attempts,
    )
    db.add(row)
    await db.flush()


async def get(db: AsyncSession, call_id: uuid.UUID, user_id: uuid.UUID) -> ScheduledCall | None:
    row = await db.scalar(
        select(ScheduledCallRow).where(ScheduledCallRow.id == call_id, ScheduledCallRow.user_id == user_id)
    )
    return _to_domain(row) if row else None


async def update(db: AsyncSession, call: ScheduledCall, user_id: uuid.UUID) -> None:
    row = await db.scalar(
        select(ScheduledCallRow).where(
            ScheduledCallRow.id == uuid.UUID(call.id), ScheduledCallRow.user_id == user_id
        )
    )
    if row is None:
        return
    row.scheduled_time = call.scheduled_time
    row.status = call.status
    row.attempts = call.attempts
    await db.flush()


async def claim_due(db: AsyncSession, now: datetime) -> list[tuple[ScheduledCall, uuid.UUID]]:
    """Atomically claims every pending, due row across every user by
    flipping it to "processing" in one UPDATE ... RETURNING, then commits
    immediately (the caller does the actual dispatch in a separate
    transaction per row). Safe if more than one dispatcher process is
    polling at once (multiple uvicorn workers, multiple replicas):
    Postgres serializes concurrent UPDATEs against the same rows, so two
    pollers can never both claim the same row — the second one's WHERE
    status="pending" simply matches nothing once the first commits.
    No broker needed for this; it's the standard "Postgres as a queue"
    claim pattern.

    ponytail: no lease/heartbeat recovery — if a poller crashes after
    claiming but before dispatching, that row is stuck "processing"
    forever. Add a cron sweep (processing + older than N minutes ->
    pending) if that ever happens in practice; not worth the complexity
    until it does.
    """
    result = await db.execute(
        sa_update(ScheduledCallRow)
        .where(ScheduledCallRow.status == "pending", ScheduledCallRow.scheduled_time <= now)
        .values(status="processing")
        .returning(ScheduledCallRow)
    )
    await db.commit()
    rows = result.scalars().all()
    return [(_to_domain(r), r.user_id) for r in rows]


async def list_all(db: AsyncSession, user_id: uuid.UUID, status: ScheduledCallStatus | None = None) -> list[ScheduledCall]:
    query = select(ScheduledCallRow).where(ScheduledCallRow.user_id == user_id)
    if status is not None:
        query = query.where(ScheduledCallRow.status == status)
    result = await db.scalars(query.order_by(ScheduledCallRow.scheduled_time))
    return [_to_domain(r) for r in result]


async def count_pending_for_number(db: AsyncSession, phone_number: str, user_id: uuid.UUID) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(ScheduledCallRow)
        .where(
            ScheduledCallRow.phone_number == phone_number,
            ScheduledCallRow.user_id == user_id,
            ScheduledCallRow.status == "pending",
        )
    )
