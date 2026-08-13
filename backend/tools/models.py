"""Prebuilt tool catalog + activated (configured) instances a persona can
attach and call mid-chat.

Two layers, the same split compiler/ uses for archetype -> persona:
ToolDefinition is the catalog entry (like ArchetypeSpec) — metadata only,
loaded from data/tools/*.json. ActivatedTool is a user-configured instance
of one (like AssembledPersona) — e.g. two personas could each attach their
own differently configured handoff_tool instance. The actual OpenAI tool
schema and executor for each tool_id live in code (tools/handoff.py, one
module per tool), not in the JSON — config is data, behavior isn't.
"""
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class ToolConfigField(BaseModel):
    """One field in a tool's activation form, e.g. google_calendar's
    calendar_id. Rendered generically by the frontend from this spec
    rather than each tool needing its own form component — handoff is the
    one exception, see HandoffDestination below."""

    key: str
    label: str
    placeholder: str | None = None
    required: bool = True
    multiline: bool = False


class ToolDefinition(BaseModel):
    """A prebuilt tool TYPE in the catalog."""

    id: str
    display_name: str
    description: str
    category: str
    status: Literal["available", "coming_soon"] = "available"
    config_fields: list[ToolConfigField] = Field(default_factory=list)


class HandoffDestination(BaseModel):
    """One routable target for a handoff tool: an existing persona plus
    the description that tells the model when this destination fits —
    exactly what feeds the model-facing enum + description in
    tools/handoff.py::build_handoff_schema."""

    persona_id: str
    description: str


class ActivatedTool(BaseModel):
    """A configured, nameable instance of a ToolDefinition, ready to
    attach to a persona. `config` covers simple flat-field tools (e.g. a
    calendar id); `destinations` is handoff-specific — its shape (a list
    of persona+description pairs) doesn't fit the generic key/value form,
    so it gets its own field rather than being shoehorned into config."""

    tool_instance_id: str
    tool_id: str
    name: str
    config: dict[str, str] = Field(default_factory=dict)
    destinations: list[HandoffDestination] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
