"""SQLAlchemy ORM tables. Distinct from the Pydantic domain models
(compiler/models.py, tools/models.py, scheduler/models.py) — those stay
the shape routers/business logic pass around; storage/*.py converts
between the two at the DB boundary, same role FileArchetypeStore already
plays for JSON <-> ArchetypeSpec.

UUID primary keys everywhere except chat_messages.seq, which exists only
to order a thread's messages — a plain autoincrement is the right tool
for "which came first," not identity.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Identity, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.session import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, default=uuid.uuid4)


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = _now()


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    archetype_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    first_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1")
    tool_instance_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    # Set by tools/handoff.py's execute_handoff — see storage/persona_store.py
    # get_effective(). Self-referencing: the persona currently answering
    # this thread, if a handoff has redirected it away from its own voice.
    active_persona_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("personas.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _now()


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = _uuid_pk()
    # id (UUID) is the primary key, so SQLAlchemy/Postgres won't auto-attach
    # a sequence to seq just because it's an integer — Identity() does that
    # explicitly. seq exists only to order one thread's messages.
    seq: Mapped[int] = mapped_column(Integer, Identity(always=False), nullable=False, unique=True)
    persona_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("personas.id", ondelete="CASCADE"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _now()


class ToolInstance(Base):
    __tablename__ = "tool_instances"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    tool_id: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # list[{"persona_id": str, "description": str}] — see tools/models.py::HandoffDestination
    destinations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = _now()


class ScheduledCall(Base):
    __tablename__ = "scheduled_calls"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    persona_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("personas.id", ondelete="CASCADE"), index=True, nullable=False)
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False)
    scheduled_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    context_summary: Mapped[str] = mapped_column(Text, nullable=False)
    resume_stage: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    source_call_id: Mapped[str] = mapped_column(String(100), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = _now()
