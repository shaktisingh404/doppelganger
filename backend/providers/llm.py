"""Thin, provider-agnostic LLM wrapper.

One function per tier, each reading its own model name from config. Today
every tier calls Groq (OpenAI-compatible API); adding Anthropic/OpenRouter/
Gemini later means branching inside these functions (e.g. on a
"provider:model" prefix in config), not touching callers in compiler/ or
app/.
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Awaitable, Callable

from openai import AsyncOpenAI

from compiler.models import InstanceDelta
from config import get_settings

logger = logging.getLogger("providers.llm")

_client: AsyncOpenAI | None = None
_THINK_TAG = re.compile(r"<think>.*?</think>", re.DOTALL)
_ORPHAN_THINK_CLOSE = re.compile(r"^.*?</think>", re.DOTALL)


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncOpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)
    return _client


def _strip_thinking(text: str) -> str:
    """Some Groq models (e.g. Qwen reasoning variants) inline <think> traces
    in the content field. Never speak those to a caller.

    Some responses drop the opening <think> tag but still emit the closing
    one after a draft-and-reconsider ramble, so a well-formed-pair regex
    alone lets that ramble through. If a stray </think> survives the first
    pass, treat everything before it as leftover thinking too.
    ponytail: doesn't handle thinking text that trails *after* the real
    answer with no closing tag at all — upgrade to Groq's reasoning_format
    param if that shows up.
    """
    text = _THINK_TAG.sub("", text)
    if "</think>" in text:
        text = _ORPHAN_THINK_CLOSE.sub("", text)
    return text.strip()


async def generate_archetype(prompt: str) -> str:
    """Not wired into any endpoint yet — archetype generation is hand-seeded
    in phase 1 (see data/archetypes/). Kept here so the per-tier model
    config and call shape already exist for when that flow lands."""
    settings = get_settings()
    resp = await _get_client().chat.completions.create(
        model=settings.archetype_model,
        messages=[{"role": "user", "content": prompt}],
    )
    return _strip_thinking(resp.choices[0].message.content)


_DELTA_TOOL = {
    "type": "function",
    "function": {
        "name": "record_instance_delta",
        "description": "Record the extracted slots from the persona description.",
        "parameters": InstanceDelta.model_json_schema(),
    },
}


async def extract_delta(description: str) -> InstanceDelta:
    """Narrow extraction call: free text -> InstanceDelta, forced via tool use
    so the output is structurally guaranteed rather than parsed from prose.

    Some models — reasoning variants especially — are unreliable at strict
    forced tool-calling and occasionally fail the call outright (Groq raises
    a 400 tool_use_failed) rather than returning malformed JSON. Since this
    is an enrichment step, not a required one, degrade to an empty
    InstanceDelta after a retry rather than 500ing the whole persona-create
    request over a flaky extraction call.
    """
    settings = get_settings()
    messages = [
        {
            "role": "user",
            "content": (
                "Extract structured slots from this persona description. "
                "Only use information present in the text; leave fields "
                "empty rather than inventing details.\n\n"
                f"Description: {description}"
            ),
        }
    ]

    for attempt in range(2):
        try:
            resp = await _get_client().chat.completions.create(
                model=settings.delta_model,
                tools=[_DELTA_TOOL],
                tool_choice={"type": "function", "function": {"name": "record_instance_delta"}},
                messages=messages,
            )
            tool_calls = resp.choices[0].message.tool_calls
            if not tool_calls:
                raise ValueError("model returned no tool call")
            return InstanceDelta.model_validate(json.loads(tool_calls[0].function.arguments))
        except Exception as e:
            logger.warning("delta extraction failed (attempt %d/2): %s", attempt + 1, e)

    return InstanceDelta()


ToolExecutor = Callable[[str, dict], Awaitable[str]]


async def run_turn(
    system_prompt: str,
    history: list[dict[str, str]],
    user_message: str,
    *,
    tools: list[dict] | None = None,
    tool_executor: ToolExecutor | None = None,
) -> str:
    """One chat turn against an assembled persona.

    tools/tool_executor are optional and only used by the live /chat
    endpoint (scheduler/tool.py's schedule_callback) — the dispatcher's
    proactive follow-up call passes neither, so it can never itself
    trigger a tool call. When tools are present, the model is told the
    current UTC time so it can resolve relative phrasing ("tomorrow at
    3pm") into the absolute timestamp schedule_callback requires; nothing
    else in this codebase supplies that grounding.
    """
    settings = get_settings()
    if tools:
        now = datetime.now(timezone.utc).isoformat()
        system_prompt = f"{system_prompt}\n\nCurrent UTC time: {now}"
    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": user_message},
    ]
    # Applied to every completion call in this turn (initial + the one
    # after a tool result) — both produce the reply the caller sees, so
    # both need the same phone-call-length/consistency backstop.
    sampling = {"max_tokens": settings.chat_max_tokens, "temperature": settings.chat_temperature}
    if settings.chat_reasoning_effort is not None:
        sampling["reasoning_effort"] = settings.chat_reasoning_effort
    kwargs = {**sampling, "tools": tools, "tool_choice": "auto"} if tools else dict(sampling)

    resp = await _get_client().chat.completions.create(
        model=settings.chat_model, messages=messages, **kwargs
    )
    msg = resp.choices[0].message
    _warn_if_truncated(resp, "initial")

    if msg.tool_calls and tool_executor:
        messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            }
        )
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
                result = await tool_executor(tc.function.name, args)
            except Exception as e:
                logger.exception("tool call failed name=%s args=%s", tc.function.name, tc.function.arguments)
                result = json.dumps({"error": str(e)})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

        resp = await _get_client().chat.completions.create(model=settings.chat_model, messages=messages, **sampling)
        msg = resp.choices[0].message
        _warn_if_truncated(resp, "post-tool")

    reply = _strip_thinking(msg.content)
    if not reply:
        logger.error(
            "run_turn produced an empty reply model=%s finish_reason=%s raw_content=%r",
            settings.chat_model,
            resp.choices[0].finish_reason,
            msg.content,
        )
    return reply


def _warn_if_truncated(resp, stage: str) -> None:
    """finish_reason="length" means the model hit max_tokens before it was
    done — on a reasoning model this can mean every token went to hidden
    chain-of-thought and the visible reply came back empty (see
    chat_reasoning_effort in config.py). Silent otherwise: this loop has
    no way to retry with a bigger budget mid-turn, so the only thing to
    do here is make it loud in logs so a low chat_max_tokens gets noticed
    and raised, instead of a user just seeing a short/empty reply.
    """
    choice = resp.choices[0]
    if choice.finish_reason == "length":
        usage = resp.usage
        reasoning_tokens = getattr(usage.completion_tokens_details, "reasoning_tokens", None) if usage else None
        logger.warning(
            "run_turn reply truncated stage=%s completion_tokens=%s reasoning_tokens=%s — "
            "consider raising chat_max_tokens or check chat_reasoning_effort",
            stage,
            usage.completion_tokens if usage else "?",
            reasoning_tokens,
        )
