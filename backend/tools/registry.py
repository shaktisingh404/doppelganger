"""Combines the always-on schedule_callback tool with a persona's
attached (activated, catalog) tools into what providers.llm.run_turn
needs for one chat turn: a tool schema list + one dispatching executor.

Centralized here rather than split across app/routers/personas.py so
"what tools does this chat turn get" has one place to read, not two.
"""
import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings
from providers.llm import ToolExecutor
from scheduler.tool import SCHEDULE_CALLBACK_TOOL, execute_schedule_callback_tool_call
from tools.handoff import build_handoff_schema, execute_handoff
from tools.models import ActivatedTool


async def build_chat_tools(
    db: AsyncSession,
    activated_tools: list[ActivatedTool],
    persona_id: str,
    user_id: uuid.UUID,
    settings: Settings,
) -> tuple[list[dict], ToolExecutor]:
    """Attached tools whose type has no registered schema (or, for
    handoff, no resolvable destination) are silently skipped rather than
    breaking the whole chat turn over one bad tool. At most one instance
    per tool_id is included — OpenAI function names must be unique per
    request, and today's schemas use a fixed name (e.g. "request_handoff"),
    so two attached instances of the same tool_id would otherwise collide;
    the first one attached wins. (For handoff specifically, this is a
    non-issue in practice: one instance already holds a list of
    destinations, matching how it's meant to be used.)
    """
    schemas = [{"type": "function", "function": SCHEDULE_CALLBACK_TOOL}]
    by_name: dict[str, ActivatedTool] = {}
    seen_tool_ids: set[str] = set()

    for activated in activated_tools:
        if activated.tool_id in seen_tool_ids:
            continue
        if activated.tool_id == "handoff":
            schema = await build_handoff_schema(db, activated, user_id)
        else:
            schema = None
        if schema is None:
            continue
        schemas.append({"type": "function", "function": schema})
        by_name[schema["name"]] = activated
        seen_tool_ids.add(activated.tool_id)

    async def executor(name: str, args: dict) -> str:
        if name == "schedule_callback":
            return await execute_schedule_callback_tool_call(db, settings, user_id, persona_id, name, args)
        activated = by_name.get(name)
        if activated is None:
            return json.dumps({"error": f"unknown tool {name}"})
        if activated.tool_id == "handoff":
            return await execute_handoff(db, activated, persona_id, user_id, args)
        return json.dumps({"error": f"no executor for tool {activated.tool_id}"})

    return schemas, executor
