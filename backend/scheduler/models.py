"""scheduled_calls schema + storage.

In-memory only, same as storage/persona_store.py — this is a
single-process learning project, so a dict is "the storage layer phase 1
already established," not a gap to fill with a real database.
"""
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

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


class ScheduledCallStore:
    def __init__(self) -> None:
        self._rows: dict[str, ScheduledCall] = {}

    def add(self, row: ScheduledCall) -> None:
        self._rows[row.id] = row

    def get(self, call_id: str) -> ScheduledCall | None:
        return self._rows.get(call_id)

    def update(self, row: ScheduledCall) -> None:
        self._rows[row.id] = row

    def list(self, status: ScheduledCallStatus | None = None) -> list[ScheduledCall]:
        rows = sorted(self._rows.values(), key=lambda r: r.scheduled_time)
        if status is None:
            return rows
        return [r for r in rows if r.status == status]

    def count_pending_for_number(self, phone_number: str) -> int:
        return sum(
            1
            for r in self._rows.values()
            if r.phone_number == phone_number and r.status == "pending"
        )
