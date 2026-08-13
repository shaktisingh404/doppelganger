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
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ScheduledCall as ScheduledCallRow

ScheduledCallStatus = Literal["pending", "completed", "failed", "cancelled"]


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
    )


async def add(db: AsyncSession, call: ScheduledCall, user_id: uuid.UUID) -> None:
    row = ScheduledCallRow(
        id=uuid.UUID(call.id),
        user_id=user_id,
        persona_id=uuid.UUID(call.persona_id),
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


async def list_due(db: AsyncSession, now: datetime) -> list[tuple[ScheduledCall, uuid.UUID]]:
    """Every pending, due row across every user — the dispatcher polls
    the whole table (there's no per-user context in a background job),
    scoping only kicks in when it resolves each row's persona."""
    result = await db.scalars(
        select(ScheduledCallRow).where(ScheduledCallRow.status == "pending", ScheduledCallRow.scheduled_time <= now)
    )
    return [(_to_domain(r), r.user_id) for r in result]


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
