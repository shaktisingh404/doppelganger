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


class UpdatePersonaToolsRequest(BaseModel):
    tool_instance_ids: list[str]


class ActivateToolRequest(BaseModel):
    tool_id: str
    name: str
    config: dict[str, str] = {}
    destinations: list[HandoffDestination] = []
