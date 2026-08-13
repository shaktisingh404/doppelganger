"""Smoke test for providers/llm.py's non-network-dependent behavior. Run
with: python -m tests.test_providers  (run from backend/)
"""
import asyncio
import json
import os
from types import SimpleNamespace

os.environ.setdefault("GROQ_API_KEY", "test-key")

import providers.llm as llm
from compiler.models import InstanceDelta
from providers.llm import _strip_thinking

assert _strip_thinking("Hello there!") == "Hello there!"
assert _strip_thinking("<think>hmm, let me consider</think>Hello!") == "Hello!"
assert (
    _strip_thinking("draft answer... on second thought...\n</think>\n\nFinal answer.")
    == "Final answer."
)
assert _strip_thinking("<think>reasoning</think> stray trailer </think> final") == "final"


def _fake_response(arguments: str):
    tool_call = SimpleNamespace(function=SimpleNamespace(arguments=arguments))
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[tool_call]))])


class _FakeClient:
    """Each entry in side_effects is either an Exception to raise or a
    pre-built fake response to return, consumed in order."""

    def __init__(self, side_effects):
        self._side_effects = list(side_effects)
        self.call_count = 0
        self.calls = []  # kwargs of every create() call, for asserting what was sent
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.call_count += 1
        self.calls.append(kwargs)
        effect = self._side_effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect


async def _run():
    # Both attempts fail (mirrors Groq's real tool_use_failed 400) -> falls
    # back to an empty InstanceDelta instead of propagating the error. This
    # is exactly what was crashing POST /personas with a 500 before the fix.
    fake = _FakeClient([Exception("tool_use_failed"), Exception("tool_use_failed")])
    llm._get_client = lambda: fake
    delta = await llm.extract_delta("some description")
    assert delta == InstanceDelta()
    assert fake.call_count == 2

    # First attempt fails, second succeeds -> the retry recovers the result
    # rather than giving up after one flaky call.
    good = _fake_response(json.dumps({"specialization": "retirement planning"}))
    fake2 = _FakeClient([Exception("tool_use_failed"), good])
    llm._get_client = lambda: fake2
    delta2 = await llm.extract_delta("some description")
    assert delta2.specialization == "retirement planning"
    assert fake2.call_count == 2

    # No tool_calls at all (model answered in plain text instead) is
    # treated the same as a failure, not an IndexError crash.
    no_tool_call = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=None))]
    )
    fake3 = _FakeClient([no_tool_call, no_tool_call])
    llm._get_client = lambda: fake3
    delta3 = await llm.extract_delta("some description")
    assert delta3 == InstanceDelta()


asyncio.run(_run())
print("ok")


def _fake_chat_response(content=None, tool_calls=None, finish_reason="stop"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason, message=SimpleNamespace(content=content, tool_calls=tool_calls)
            )
        ],
        usage=SimpleNamespace(completion_tokens=0, completion_tokens_details=None),
    )


def _fake_tool_call(call_id, name, arguments):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


async def _run_turn_tests():
    # No tools passed (the dispatcher's proactive-followup call site) never
    # sends tools/tool_choice to the API and just returns the plain reply.
    fake = _FakeClient([_fake_chat_response(content="Hi there!")])
    llm._get_client = lambda: fake
    reply = await llm.run_turn("system", [], "hello")
    assert reply == "Hi there!"
    assert "tools" not in fake.calls[0]
    assert fake.call_count == 1

    # A tool call gets executed and its result fed back; the *second*
    # completion's reply is returned, not the first (tool-call-only) one.
    tool_call = _fake_tool_call("call_1", "schedule_callback", json.dumps({"scheduled_time": "x"}))
    fake2 = _FakeClient(
        [
            _fake_chat_response(content=None, tool_calls=[tool_call]),
            _fake_chat_response(content="Scheduled, talk soon!"),
        ]
    )
    llm._get_client = lambda: fake2

    executed = []

    async def executor(name, args):
        executed.append((name, args))
        return json.dumps({"scheduled": True})

    reply2 = await llm.run_turn(
        "system",
        [],
        "call me back tomorrow",
        tools=[{"type": "function", "function": {"name": "schedule_callback"}}],
        tool_executor=executor,
    )
    assert reply2 == "Scheduled, talk soon!"
    assert executed == [("schedule_callback", {"scheduled_time": "x"})]
    assert fake2.call_count == 2
    second_call_messages = fake2.calls[1]["messages"]
    assert any(
        m.get("role") == "tool" and m.get("tool_call_id") == "call_1" for m in second_call_messages
    )
    # the grounding line is only added when tools are actually in play
    assert "Current UTC time" in fake2.calls[0]["messages"][0]["content"]
    assert "Current UTC time" not in fake.calls[0]["messages"][0]["content"]

    # A reasoning model that burns its whole max_tokens budget on hidden
    # chain-of-thought (see chat_reasoning_effort in config.py) comes back
    # with finish_reason="length" and empty content -- run_turn still
    # returns "" rather than raising (nothing left to retry with mid-turn),
    # but it must log loudly rather than silently swallowing this, since
    # this is exactly the bug that shipped: users saw a blank reply with
    # nothing in the logs to explain why.
    import logging

    class _CollectingHandler(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []

        def emit(self, record):
            self.records.append(record)

    handler = _CollectingHandler()
    llm.logger.addHandler(handler)
    llm.logger.setLevel(logging.DEBUG)
    try:
        truncated = _fake_chat_response(
            content="",
            finish_reason="length",
        )
        truncated.usage = SimpleNamespace(
            completion_tokens=200, completion_tokens_details=SimpleNamespace(reasoning_tokens=200)
        )
        fake3 = _FakeClient([truncated])
        llm._get_client = lambda: fake3
        reply3 = await llm.run_turn("system", [], "hello")
        assert reply3 == ""
    finally:
        llm.logger.removeHandler(handler)

    levels = [r.levelno for r in handler.records]
    assert logging.WARNING in levels, "expected a truncation warning to be logged"
    assert logging.ERROR in levels, "expected the empty-reply to be logged as an error"


asyncio.run(_run_turn_tests())
print("run_turn tool-calling + truncated/empty-reply logging: ok")
