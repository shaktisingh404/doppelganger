"""Pydantic models shared across the compiler and API boundary."""
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator, model_validator

# Reference files are injected verbatim into the prompt (see
# compiler/assembly.py), so these bound how much of the model's context a
# persona's reference material can eat — not a storage limit, a prompt-size
# one. Text extraction happens client-side (File.text() on .txt/.md), so
# there's no upload endpoint or parsing library to size these against.
MAX_REFERENCE_FILE_CHARS = 20_000
MAX_REFERENCE_FILES_TOTAL_CHARS = 40_000


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


class ReferenceFile(BaseModel):
    """A small text document (.txt/.md) injected verbatim into the prompt,
    same rationale as BusinessInfo — never paraphrased by extract_delta,
    since summarizing reference material risks losing or distorting the
    facts it exists to pin down."""

    filename: str
    content: str

    @field_validator("content")
    @classmethod
    def _within_per_file_limit(cls, content: str) -> str:
        if len(content) > MAX_REFERENCE_FILE_CHARS:
            raise ValueError(f"file exceeds {MAX_REFERENCE_FILE_CHARS} character limit")
        return content


class InstanceInput(BaseModel):
    """What the caller provides to build one persona instance."""

    archetype_id: str
    name: str
    language: str
    tone: str | None = None
    description: str
    business_info: BusinessInfo | None = None
    # Free-text paragraph describing HOW the persona should converse
    # (pacing, formality, question style, escalation behavior) — distinct
    # from `description`, which is WHAT it knows/talks about. Surfaced as
    # the "Working style" field in the Generate panel (AssistantEditor.tsx).
    conversational_style: str | None = None
    reference_files: list[ReferenceFile] = Field(default_factory=list)

    @model_validator(mode="after")
    def _within_total_reference_limit(self) -> "InstanceInput":
        total = sum(len(f.content) for f in self.reference_files)
        if total > MAX_REFERENCE_FILES_TOTAL_CHARS:
            raise ValueError(
                f"reference files total {total} characters, exceeds {MAX_REFERENCE_FILES_TOTAL_CHARS} limit"
            )
        return self


class InstanceDelta(BaseModel):
    """Layer 3: fixed, validated slots extracted from free-text description."""

    specialization: str | None = None
    extra_constraint: str | None = None
    key_talking_points: list[str] = Field(default_factory=list)
    things_to_avoid: list[str] = Field(default_factory=list)


class AssembledPersona(BaseModel):
    """A created, chattable persona: identity + the final system_prompt/
    first_message text. Generation (description -> system_prompt, via
    compiler/pipeline.py::generate_system_prompt) and creation (this
    object's identity) are separate steps — the text here may have been
    hand-edited after generation, so nothing downstream should assume it
    still matches any InstanceInput that produced a first draft of it."""

    persona_id: str
    archetype_id: str | None = None
    name: str
    first_message: str = ""
    system_prompt: str
    version: str = "1"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Activated tools.models.ActivatedTool instances this persona can call
    # mid-chat, in addition to the always-on schedule_callback tool. Kept
    # as bare ids, not embedded objects — the router resolves them against
    # app.state.tool_instance_store per chat turn, so a tool's config can
    # change without touching every persona that references it.
    tool_instance_ids: list[str] = Field(default_factory=list)
    # Non-None means an anonymous visitor holding this token can chat with
    # this persona via app/routers/public.py — see
    # storage/persona_store.py::enable_sharing/disable_sharing.
    share_token: str | None = None
