"""Smoke test for the tool catalog, activation, persona attachment/editing,
and the chat-turn tool builder (tools/registry.py) — including handoff's
persona-switching mechanic. Against the real Postgres DB (DATABASE_URL/
JWT_SECRET_KEY come from .env — see backend/README.md's Tests section).
No LLM calls: the tools under test (handoff) don't make any; schedule_callback's
own LLM-free paths are already covered by tests/test_scheduler.py. Run with:
python -m tests.test_tools  (run from backend/)
"""
import os
import uuid

os.environ.setdefault("GROQ_API_KEY", "test-key")

from fastapi.testclient import TestClient

import storage.persona_store as persona_store
from app.main import app
from config import get_settings
from db.session import get_session_factory
from tests._auth_helper import delete_test_user, register_test_user
from tools.handoff import build_handoff_schema, execute_handoff
from tools.models import ActivatedTool, HandoffDestination
from tools.registry import build_chat_tools

with TestClient(app) as client:
    auth, user_id = register_test_user(client)

    # --- GET /tools/catalog -----------------------------------------------

    catalog_resp = client.get("/tools/catalog", headers=auth)
    assert catalog_resp.status_code == 200
    catalog = {t["id"]: t for t in catalog_resp.json()}
    assert catalog.keys() == {"handoff", "google_calendar", "google_sheets"}
    assert catalog["handoff"]["status"] == "available"
    assert catalog["google_calendar"]["status"] == "coming_soon"
    assert catalog["google_sheets"]["status"] == "coming_soon"
    assert catalog["handoff"]["config_fields"] == []  # real config is destinations, not flat fields

    print("catalog: ok")

    # --- fixtures: two personas to route between -----------------------------

    triage = client.post(
        "/personas", json={"name": "Triage", "system_prompt": "You triage requests."}, headers=auth
    ).json()
    billing = client.post(
        "/personas", json={"name": "Billing", "system_prompt": "You are the billing specialist."}, headers=auth
    ).json()

    # --- POST /tools: handoff activation validation --------------------------

    no_destinations = client.post(
        "/tools", json={"tool_id": "handoff", "name": "Route", "destinations": []}, headers=auth
    )
    assert no_destinations.status_code == 400

    unknown_destination = client.post(
        "/tools",
        json={"tool_id": "handoff", "name": "Route", "destinations": [{"persona_id": "nope", "description": "x"}]},
        headers=auth,
    )
    assert unknown_destination.status_code == 400

    ok_activate = client.post(
        "/tools",
        json={
            "tool_id": "handoff",
            "name": "Route to Billing",
            "destinations": [{"persona_id": billing["persona_id"], "description": "Billing or payment questions."}],
        },
        headers=auth,
    )
    assert ok_activate.status_code == 200, ok_activate.text
    activated = ok_activate.json()
    assert activated["tool_id"] == "handoff"
    assert activated["destinations"][0]["persona_id"] == billing["persona_id"]
    tool_instance_id = activated["tool_instance_id"]

    # coming_soon tools can't be activated yet.
    coming_soon_activate = client.post(
        "/tools", json={"tool_id": "google_calendar", "name": "Cal", "config": {"calendar_id": "x"}}, headers=auth
    )
    assert coming_soon_activate.status_code == 400

    # Unknown tool_id -> 404, not a 500.
    unknown_tool = client.post("/tools", json={"tool_id": "does-not-exist", "name": "X", "config": {}}, headers=auth)
    assert unknown_tool.status_code == 404

    print("activation validation: ok")

    # --- GET /tools: lists activated instances ------------------------------

    list_resp = client.get("/tools", headers=auth)
    assert list_resp.status_code == 200
    assert tool_instance_id in {t["tool_instance_id"] for t in list_resp.json()}

    print("list activated: ok")

    # --- POST /personas: attaching tools at create time -----------------------

    bad_attach = client.post(
        "/personas",
        json={"name": "X", "system_prompt": "test", "tool_instance_ids": ["does-not-exist"]},
        headers=auth,
    )
    assert bad_attach.status_code == 400

    good_attach = client.post(
        "/personas",
        json={"name": "X", "system_prompt": "test", "tool_instance_ids": [tool_instance_id]},
        headers=auth,
    )
    assert good_attach.status_code == 200, good_attach.text
    assert good_attach.json()["tool_instance_ids"] == [tool_instance_id]

    print("persona attachment at create time: ok")

    # --- PUT /personas/{id}/tools: editing an existing persona's tools --------

    no_tools_persona = client.post("/personas", json={"name": "Plain", "system_prompt": "test"}, headers=auth).json()
    assert no_tools_persona["tool_instance_ids"] == []
    plain_id = no_tools_persona["persona_id"]

    add_resp = client.put(f"/personas/{plain_id}/tools", json={"tool_instance_ids": [tool_instance_id]}, headers=auth)
    assert add_resp.status_code == 200, add_resp.text
    assert add_resp.json()["tool_instance_ids"] == [tool_instance_id]

    remove_resp = client.put(f"/personas/{plain_id}/tools", json={"tool_instance_ids": []}, headers=auth)
    assert remove_resp.status_code == 200
    assert remove_resp.json()["tool_instance_ids"] == []

    bad_edit = client.put(f"/personas/{plain_id}/tools", json={"tool_instance_ids": ["does-not-exist"]}, headers=auth)
    assert bad_edit.status_code == 400

    missing_persona_edit = client.put("/personas/does-not-exist/tools", json={"tool_instance_ids": []}, headers=auth)
    assert missing_persona_edit.status_code == 404

    # unauthenticated -> 401 before anything else runs
    assert client.put(f"/personas/{plain_id}/tools", json={"tool_instance_ids": []}).status_code == 401

    print("edit existing persona's tools: ok")

    # --- a second user can't activate tools against, or see, the first user's data ---

    auth2, user_id2 = register_test_user(client)
    cross_user_activate = client.post(
        "/tools",
        json={
            "tool_id": "handoff",
            "name": "Cross",
            "destinations": [{"persona_id": billing["persona_id"], "description": "x"}],
        },
        headers=auth2,
    )
    assert cross_user_activate.status_code == 400  # billing isn't user2's persona
    assert client.get("/tools", headers=auth2).json() == []
    delete_test_user(user_id2)

    print("cross-user scoping: ok")

    # --- tools/handoff.py + tools/registry.py: dynamic schema, resolution, execution ---

    handoff_tool = ActivatedTool(
        tool_instance_id=tool_instance_id,
        tool_id="handoff",
        name="Route",
        destinations=[HandoffDestination(persona_id=billing["persona_id"], description="Billing questions.")],
    )
    dangling = ActivatedTool(
        tool_instance_id=str(uuid.uuid4()),
        tool_id="handoff",
        name="Dead",
        destinations=[HandoffDestination(persona_id=str(uuid.uuid4()), description="x")],
    )

    async def _run():
        session_factory = get_session_factory()
        uid = uuid.UUID(user_id)
        triage_id = uuid.UUID(triage["persona_id"])
        billing_id = uuid.UUID(billing["persona_id"])

        async with session_factory() as db:
            schema = await build_handoff_schema(db, handoff_tool, uid)
            assert schema is not None
            assert schema["parameters"]["properties"]["destination_name"]["enum"] == ["Billing"]

            # Every destination unresolvable (e.g. all referenced personas deleted) -> no tool offered at all.
            assert await build_handoff_schema(db, dangling, uid) is None

        print("build_handoff_schema: ok")

        async with session_factory() as db:
            # Before any handoff, the effective persona is the thread's own.
            effective = await persona_store.get_effective(db, triage_id, uid)
            assert (effective or await persona_store.get(db, triage_id, uid)).name == "Triage"

            result = await execute_handoff(db, handoff_tool, str(triage_id), uid, {
                "destination_name": "Billing", "reason": "payment question"
            })
            await db.commit()
        assert "Billing" in result

        async with session_factory() as db:
            # After the handoff fires, the *same* persona_id's effective persona
            # is now Billing -- the conversation didn't move, its brain did.
            effective = await persona_store.get_effective(db, triage_id, uid)
            assert effective.name == "Billing"
            # Untouched thread is unaffected.
            effective_billing = await persona_store.get_effective(db, billing_id, uid)
            assert (effective_billing or await persona_store.get(db, billing_id, uid)).name == "Billing"

            # Unknown destination_name -> error JSON, no crash.
            bad_result = await execute_handoff(db, handoff_tool, str(triage_id), uid, {
                "destination_name": "Nope", "reason": "x"
            })
        assert "error" in bad_result

        # --- tools/registry.py::build_chat_tools, end to end at the unit level ---
        settings = get_settings()
        async with session_factory() as db:
            schemas, _executor = await build_chat_tools(db, [handoff_tool], str(triage_id), uid, settings)
        schema_names = {s["function"]["name"] for s in schemas}
        assert schema_names == {"schedule_callback", "request_handoff"}

        # A handoff tool whose only destination is unresolvable is skipped
        # entirely -- schedule_callback still offered, nothing else breaks.
        async with session_factory() as db:
            schemas_stub, _ = await build_chat_tools(db, [dangling], str(triage_id), uid, settings)
        assert len(schemas_stub) == 1

        print("handoff persona-switching + build_chat_tools: ok")

    # client.portal (not asyncio.run) -- the DB engine is a singleton bound
    # to TestClient's portal loop by the time these HTTP calls above have
    # run; a fresh asyncio.run() loop can't reuse asyncpg connections
    # opened on a different one ("attached to a different loop").
    client.portal.call(_run)

    delete_test_user(user_id)  # cascades: personas, tool_instances, chat_messages

print("ok")
