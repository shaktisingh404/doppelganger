"""Smoke test for scheduler/ (tool validation, store, dispatcher retry/fail
logic — no real network, fake originate_call). Run with:
python -m tests.test_scheduler  (run from backend/)
"""
import asyncio
import os

os.environ.setdefault("GROQ_API_KEY", "test-key")

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from config import Settings
from scheduler import dispatcher
from scheduler.models import ScheduledCall, ScheduledCallStore
from scheduler.tool import ScheduleCallbackError, schedule_callback

NOW = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
SETTINGS = Settings(
    groq_api_key="x",
    scheduled_callback_max_window_days=30,
    scheduled_callback_max_pending_per_number=2,
    scheduled_callback_retry_delay_seconds=300,
)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# --- tool validation ---------------------------------------------------

store = ScheduledCallStore()

row = schedule_callback(
    store,
    SETTINGS,
    persona_id="p1",
    phone_number="+15559998888",
    source_call_id="CA_SRC",
    scheduled_time=_iso(NOW + timedelta(hours=6)),
    context_summary="caller wants a quote follow-up",
    resume_stage="pricing",
    now=NOW,
)
assert row.status == "pending"
assert row.scheduled_time == NOW + timedelta(hours=6)
assert store.get(row.id) is row

try:
    schedule_callback(
        store, SETTINGS, persona_id="p1", phone_number="+1", source_call_id="c",
        scheduled_time=_iso(NOW - timedelta(hours=1)), context_summary="x", now=NOW,
    )
    assert False, "should reject a past timestamp"
except ScheduleCallbackError:
    pass

try:
    schedule_callback(
        store, SETTINGS, persona_id="p1", phone_number="+1", source_call_id="c",
        scheduled_time=_iso(NOW + timedelta(days=60)), context_summary="x", now=NOW,
    )
    assert False, "should reject a window that's too far out"
except ScheduleCallbackError:
    pass

try:
    schedule_callback(
        store, SETTINGS, persona_id="p1", phone_number="+1", source_call_id="c",
        scheduled_time="not-a-timestamp", context_summary="x", now=NOW,
    )
    assert False, "should reject a non-ISO timestamp"
except ScheduleCallbackError:
    pass

try:
    schedule_callback(
        store, SETTINGS, persona_id="p1", phone_number="+1", source_call_id="c",
        scheduled_time="2026-08-12T00:00:00", context_summary="x", now=NOW,
    )
    assert False, "should reject a timestamp with no UTC offset"
except ScheduleCallbackError:
    pass

# per-number cap: SETTINGS allows 2 pending; number already has 0, so 2 more succeed, 3rd rejected
number = "+15551112222"
schedule_callback(
    store, SETTINGS, persona_id="p1", phone_number=number, source_call_id="c",
    scheduled_time=_iso(NOW + timedelta(hours=1)), context_summary="x", now=NOW,
)
schedule_callback(
    store, SETTINGS, persona_id="p1", phone_number=number, source_call_id="c",
    scheduled_time=_iso(NOW + timedelta(hours=2)), context_summary="x", now=NOW,
)
try:
    schedule_callback(
        store, SETTINGS, persona_id="p1", phone_number=number, source_call_id="c",
        scheduled_time=_iso(NOW + timedelta(hours=3)), context_summary="x", now=NOW,
    )
    assert False, "should reject once the per-number pending cap is hit"
except ScheduleCallbackError:
    pass

print("tool validation: ok")


# --- resume-context block -----------------------------------------------

block = dispatcher.build_resume_context_block("caller wants a quote follow-up", "pricing")
assert "caller wants a quote follow-up" in block
assert "Resume at stage: pricing" in block
assert dispatcher.build_resume_context_block("just checking in", None).count("Resume at stage") == 0

print("resume-context block: ok")


# --- dispatcher: success, retry-once, then fail (chat firing) -----------


def _due_row(**overrides) -> ScheduledCall:
    defaults = dict(
        id="row1",
        persona_id="p1",
        phone_number="+15559998888",
        scheduled_time=NOW,
        context_summary="ctx",
        source_call_id="CA_SRC",
    )
    defaults.update(overrides)
    return ScheduledCall(**defaults)


async def _run():
    fake_persona = SimpleNamespace(system_prompt="You are a test persona.")
    histories: dict[str, list[dict[str, str]]] = {}

    def get_persona(pid: str):
        return fake_persona if pid == "p1" else None

    def get_history(pid: str) -> list[dict[str, str]]:
        return histories.setdefault(pid, [])

    async def fake_run_turn_ok(system_prompt, history, user_message):
        return "Hey, following up like I said I would!"

    dispatcher.run_turn = fake_run_turn_ok
    ok_store = ScheduledCallStore()
    ok_store.add(_due_row(id="ok"))
    await dispatcher.poll_once(ok_store, SETTINGS, get_persona, get_history)
    assert ok_store.get("ok").status == "completed"
    assert ok_store.get("ok").attempts == 1
    assert histories["p1"][-1] == {
        "role": "assistant",
        "content": "Hey, following up like I said I would!",
    }

    async def fake_run_turn_fail(system_prompt, history, user_message):
        raise RuntimeError("llm down")

    dispatcher.run_turn = fake_run_turn_fail
    retry_store = ScheduledCallStore()
    retry_store.add(_due_row(id="retry"))
    await dispatcher.poll_once(retry_store, SETTINGS, get_persona, get_history)
    row = retry_store.get("retry")
    assert row.status == "pending"
    assert row.attempts == 1
    assert row.scheduled_time > NOW  # bumped forward by the retry delay

    # second poll after the bumped time still isn't due yet
    await dispatcher.poll_once(retry_store, SETTINGS, get_persona, get_history)
    assert retry_store.get("retry").attempts == 1

    # force it due again to exercise the final-failure path
    row.scheduled_time = datetime.now(timezone.utc) - timedelta(seconds=1)
    retry_store.update(row)
    await dispatcher.poll_once(retry_store, SETTINGS, get_persona, get_history)
    failed = retry_store.get("retry")
    assert failed.status == "failed"
    assert failed.attempts == 2

    # unknown persona fails immediately, no retry wasted
    unknown_store = ScheduledCallStore()
    unknown_store.add(_due_row(id="unknown", persona_id="does-not-exist"))
    await dispatcher.poll_once(unknown_store, SETTINGS, get_persona, get_history)
    unknown = unknown_store.get("unknown")
    assert unknown.status == "failed"
    assert unknown.attempts == 1


asyncio.run(_run())
print("dispatcher retry/fail: ok")

print("ok")
