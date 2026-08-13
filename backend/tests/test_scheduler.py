"""Smoke test for scheduler/ (tool validation, DB-backed store, dispatcher
retry/fail logic) against the real Postgres DB (DATABASE_URL/
JWT_SECRET_KEY come from .env — see backend/README.md's Tests section).
No LLM network calls — dispatcher.run_turn is monkeypatched. Run with:
python -m tests.test_scheduler  (run from backend/)
"""
import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

os.environ.setdefault("GROQ_API_KEY", "test-key")

from sqlalchemy import delete

import scheduler.models as scheduled_call_store
import storage.persona_store as persona_store
import storage.public_session_store as public_session_store
from compiler.models import AssembledPersona
from config import get_settings
from db.models import User
from db.session import get_session_factory
from scheduler import dispatcher
from scheduler.models import ScheduledCall
from scheduler.tool import ScheduleCallbackError, schedule_callback
from utils.logging_config import configure as configure_logging

# Standalone (doesn't import app.main like test_app.py/test_tools.py do,
# so nothing else triggers this) -- without it, dispatcher's/tool's
# logger.warning/.exception calls below still fire, just through
# Python's unformatted last-resort handler instead of our timestamped
# format, same gap this whole logging setup exists to close.
configure_logging()

NOW = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
# Real database_url/jwt_secret_key from .env, only the scheduler-specific
# knobs overridden (a lower cap makes the per-number-cap test cheap).
SETTINGS = get_settings().model_copy(
    update={
        "scheduled_callback_max_window_days": 30,
        "scheduled_callback_max_pending_per_number": 2,
        "scheduled_callback_retry_delay_seconds": 300,
    }
)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _due_row(persona_id: str, **overrides) -> ScheduledCall:
    defaults = dict(
        id=str(uuid.uuid4()),
        persona_id=persona_id,
        phone_number="+15559998888",
        scheduled_time=NOW,
        context_summary="ctx",
        source_call_id="CA_SRC",
    )
    defaults.update(overrides)
    return ScheduledCall(**defaults)


async def main():
    session_factory = get_session_factory()

    # --- fixtures: two real users (FK-backed personas need a real owner) ---
    async with session_factory() as db:
        user = User(email=f"test-{uuid.uuid4()}@example.com", hashed_password="x")
        other_user = User(email=f"test-{uuid.uuid4()}@example.com", hashed_password="x")
        db.add(user)
        db.add(other_user)
        await db.flush()
        user_id, other_user_id = user.id, other_user.id

        persona = AssembledPersona(
            persona_id=str(uuid.uuid4()), name="P1", system_prompt="You are a test persona."
        )
        await persona_store.add(db, persona, user_id)
        await db.commit()
    persona_id = persona.persona_id

    # --- tool validation ------------------------------------------------

    async with session_factory() as db:
        row = await schedule_callback(
            db,
            SETTINGS,
            user_id=user_id,
            persona_id=persona_id,
            phone_number="+15559998888",
            source_call_id="CA_SRC",
            scheduled_time=_iso(NOW + timedelta(hours=6)),
            context_summary="caller wants a quote follow-up",
            resume_stage="pricing",
            now=NOW,
        )
        await db.commit()
    assert row.status == "pending"
    assert row.scheduled_time == NOW + timedelta(hours=6)

    async def _expect_reject(reason: str, **kwargs):
        async with session_factory() as db:
            try:
                await schedule_callback(db, SETTINGS, user_id=user_id, persona_id=persona_id, now=NOW, **kwargs)
                assert False, f"should reject: {reason}"
            except ScheduleCallbackError:
                pass

    await _expect_reject(
        "a past timestamp",
        phone_number="+1", source_call_id="c",
        scheduled_time=_iso(NOW - timedelta(hours=1)), context_summary="x",
    )
    await _expect_reject(
        "a window that's too far out",
        phone_number="+1", source_call_id="c",
        scheduled_time=_iso(NOW + timedelta(days=60)), context_summary="x",
    )
    await _expect_reject(
        "a non-ISO timestamp",
        phone_number="+1", source_call_id="c",
        scheduled_time="not-a-timestamp", context_summary="x",
    )
    await _expect_reject(
        "a timestamp with no UTC offset",
        phone_number="+1", source_call_id="c",
        scheduled_time="2026-08-12T00:00:00", context_summary="x",
    )

    # per-number cap: SETTINGS allows 2 pending; number already has 0, so 2 more succeed, 3rd rejected
    number = "+15551112222"
    async with session_factory() as db:
        await schedule_callback(
            db, SETTINGS, user_id=user_id, persona_id=persona_id, phone_number=number, source_call_id="c",
            scheduled_time=_iso(NOW + timedelta(hours=1)), context_summary="x", now=NOW,
        )
        await schedule_callback(
            db, SETTINGS, user_id=user_id, persona_id=persona_id, phone_number=number, source_call_id="c",
            scheduled_time=_iso(NOW + timedelta(hours=2)), context_summary="x", now=NOW,
        )
        await db.commit()
    await _expect_reject(
        "once the per-number pending cap is hit",
        phone_number=number, source_call_id="c",
        scheduled_time=_iso(NOW + timedelta(hours=3)), context_summary="x",
    )

    print("tool validation: ok")

    # --- scoping: another user can't see or fetch this one's rows --------

    async with session_factory() as db:
        others_view = await scheduled_call_store.list_all(db, other_user_id)
        direct_fetch = await scheduled_call_store.get(db, uuid.UUID(row.id), other_user_id)
    assert row.id not in {r.id for r in others_view}
    assert direct_fetch is None

    print("scoping: ok")

    # --- claim_due: concurrent pollers never double-claim the same row ---

    claim_target = _due_row(persona_id)
    async with session_factory() as db:
        await scheduled_call_store.add(db, claim_target, user_id)
        await db.commit()

    # Two independent sessions racing on the same due row, same as two
    # separate dispatcher processes polling at once -- this is exactly
    # the scenario claim_due's atomic UPDATE ... RETURNING exists for.
    async def _claim():
        async with session_factory() as db:
            return await scheduled_call_store.claim_due(db, NOW + timedelta(hours=1))

    results = await asyncio.gather(_claim(), _claim())
    claimed_ids = [r.id for batch in results for r, _ in batch if r.id == claim_target.id]
    assert len(claimed_ids) == 1, f"expected exactly one claim, got {len(claimed_ids)}"

    async with session_factory() as db:
        claimed_row = await scheduled_call_store.get(db, uuid.UUID(claim_target.id), user_id)
    assert claimed_row.status == "processing"

    print("claim_due: no double-claim under concurrency: ok")

    # --- resume-context block -------------------------------------------

    block = dispatcher.build_resume_context_block("caller wants a quote follow-up", "pricing")
    assert "caller wants a quote follow-up" in block
    assert "Resume at stage: pricing" in block
    assert dispatcher.build_resume_context_block("just checking in", None).count("Resume at stage") == 0

    print("resume-context block: ok")

    # --- dispatcher: success, retry-once, then fail ----------------------

    async def fake_run_turn_ok(system_prompt, history, user_message):
        return "Hey, following up like I said I would!"

    dispatcher.run_turn = fake_run_turn_ok
    ok_row = _due_row(persona_id)
    async with session_factory() as db:
        await scheduled_call_store.add(db, ok_row, user_id)
        await db.commit()
    await dispatcher._dispatch_one(ok_row, user_id, SETTINGS)
    async with session_factory() as db:
        refreshed = await scheduled_call_store.get(db, uuid.UUID(ok_row.id), user_id)
    assert refreshed.status == "completed"
    assert refreshed.attempts == 1
    async with session_factory() as db:
        history = await persona_store.get_history(db, uuid.UUID(persona_id), user_id)
    assert history[-1] == {"role": "assistant", "content": "Hey, following up like I said I would!"}

    async def fake_run_turn_fail(system_prompt, history, user_message):
        raise RuntimeError("llm down")

    dispatcher.run_turn = fake_run_turn_fail
    retry_row = _due_row(persona_id)
    async with session_factory() as db:
        await scheduled_call_store.add(db, retry_row, user_id)
        await db.commit()

    await dispatcher._dispatch_one(retry_row, user_id, SETTINGS)
    async with session_factory() as db:
        row1 = await scheduled_call_store.get(db, uuid.UUID(retry_row.id), user_id)
    assert row1.status == "pending"
    assert row1.attempts == 1
    assert row1.scheduled_time > NOW  # bumped forward by the retry delay

    # second dispatch after the bump exercises the final-failure path once forced due again
    row1.scheduled_time = datetime.now(timezone.utc) - timedelta(seconds=1)
    await dispatcher._dispatch_one(row1, user_id, SETTINGS)
    async with session_factory() as db:
        row2 = await scheduled_call_store.get(db, uuid.UUID(retry_row.id), user_id)
    assert row2.status == "failed"
    assert row2.attempts == 2

    # A row pointing at a persona that doesn't resolve for this user --
    # fails immediately, no retry wasted. Deliberately never inserted via
    # scheduled_call_store.add(): scheduled_calls.persona_id is now
    # FK-enforced (ON DELETE CASCADE), so a *stored* row can never
    # reference a persona that doesn't exist -- this exercises
    # _dispatch_one's defensive branch directly rather than via a
    # scenario the real poll_once()/FK-constrained schema can't produce.
    unknown_row = _due_row(str(uuid.uuid4()))
    await dispatcher._dispatch_one(unknown_row, user_id, SETTINGS)
    assert unknown_row.status == "failed"
    assert unknown_row.attempts == 1

    print("dispatcher retry/fail: ok")

    # --- dispatcher: a callback scheduled from a public session fires ---
    # --- back into that session's thread, not the owner's own ----------

    dispatcher.run_turn = fake_run_turn_ok
    async with session_factory() as db:
        session_id = await public_session_store.create(db, uuid.UUID(persona_id))
        await db.commit()
    session_row = _due_row(persona_id, session_id=str(session_id))
    async with session_factory() as db:
        await scheduled_call_store.add(db, session_row, user_id)
        await db.commit()
    await dispatcher._dispatch_one(session_row, user_id, SETTINGS)

    async with session_factory() as db:
        session_history = await persona_store.get_session_history(db, uuid.UUID(persona_id), session_id)
        owner_history = await persona_store.get_history(db, uuid.UUID(persona_id), user_id)
    assert session_history[-1] == {"role": "assistant", "content": "Hey, following up like I said I would!"}
    # The owner's own thread got exactly one assistant message from the
    # earlier ok_row dispatch -- still length 1, not 2, proves this
    # session-scoped dispatch didn't also (incorrectly) append there too.
    assert len(owner_history) == 1

    print("session-scoped dispatch: ok")

    # --- cleanup: cascades personas/scheduled_calls/chat_messages ---------
    async with session_factory() as db:
        await db.execute(delete(User).where(User.id.in_([user_id, other_user_id])))
        await db.commit()


asyncio.run(main())
print("ok")
