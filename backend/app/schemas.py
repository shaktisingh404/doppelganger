"""API request/response models — distinct from compiler/models.py's
domain models, which the compiler pipeline owns regardless of transport.
"""
from pydantic import BaseModel

from tools.models import HandoffDestination


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ScheduleCallbackRequest(BaseModel):
    persona_id: str
    phone_number: str
    scheduled_time: str  # ISO 8601 with UTC offset
    context_summary: str
    resume_stage: str | None = None
    source_call_id: str = "debug"


class GeneratePromptResponse(BaseModel):
    system_prompt: str


class CreatePersonaRequest(BaseModel):
    name: str
    system_prompt: str
    first_message: str = ""
    archetype_id: str | None = None
    tool_instance_ids: list[str] = []


class UpdatePersonaRequest(BaseModel):
    """archetype_id is deliberately not editable here — it's the
    persona's category, a structural choice made at creation, not a field
    an edit form touches."""

    name: str
    system_prompt: str
    first_message: str = ""


class UpdatePersonaToolsRequest(BaseModel):
    tool_instance_ids: list[str]


class ActivateToolRequest(BaseModel):
    tool_id: str
    name: str
    config: dict[str, str] = {}
    destinations: list[HandoffDestination] = []


class UpdateToolRequest(BaseModel):
    """No tool_id here — which catalog type an instance is set at
    activation and doesn't change; editing only touches its name/config/
    destinations."""

    name: str
    config: dict[str, str] = {}
    destinations: list[HandoffDestination] = []


class ShareLinkResponse(BaseModel):
    share_token: str


class PublicPersonaInfo(BaseModel):
    """What an anonymous visitor is allowed to know about a shared
    persona — deliberately just the name. No system_prompt, archetype_id,
    or tool_instance_ids; that's the whole point of a public link."""

    name: str


class PublicSessionResponse(BaseModel):
    session_id: str


class PublicChatRequest(BaseModel):
    session_id: str
    message: str
