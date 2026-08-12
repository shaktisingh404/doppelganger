"""Pydantic models shared across the compiler and API boundary."""
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ArchetypeSpec(BaseModel):
    """Layer 2: one precomputed bundle per category (finance advisor, etc)."""

    id: str
    display_name: str
    persona_text: str
    guardrail_additions: list[str] = Field(default_factory=list)
    tool_schema_stubs: list[dict] = Field(default_factory=list)


class BusinessInfo(BaseModel):
    """Hard facts about the business a persona represents. Injected verbatim
    into the assembled prompt — never run through LLM extraction, since
    paraphrasing an address or hours risks drifting from the real value."""

    name: str
    address: str | None = None
    phone: str | None = None
    hours: str | None = None
    services: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class InstanceInput(BaseModel):
    """What the caller provides to build one persona instance."""

    archetype_id: str
    name: str
    language: str
    tone: str | None = None
    description: str
    business_info: BusinessInfo | None = None


class InstanceDelta(BaseModel):
    """Layer 3: fixed, validated slots extracted from free-text description."""

    specialization: str | None = None
    extra_constraint: str | None = None
    key_talking_points: list[str] = Field(default_factory=list)
    things_to_avoid: list[str] = Field(default_factory=list)


class AssembledPersona(BaseModel):
    """Layer 4 output: the final composed system prompt plus metadata."""

    persona_id: str
    archetype_id: str
    name: str
    system_prompt: str
    version: str = "1"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
