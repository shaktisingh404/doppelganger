"""API request/response models — distinct from compiler/models.py's
domain models, which the compiler pipeline owns regardless of transport.
"""
from pydantic import BaseModel


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
