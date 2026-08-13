"""Smoke test for public share links (app/routers/public.py) — enabling/
disabling sharing, the public info endpoint's field allowlist, and
(the thing that matters most) that two different sessions against the
same share token never see each other's messages. Against the real
Postgres DB (DATABASE_URL/JWT_SECRET_KEY come from .env — see
backend/README.md's Tests section). No real LLM calls — app.routers.
public.run_turn is monkeypatched, same pattern test_scheduler.py uses for
dispatcher.run_turn. Run with:
python -m tests.test_public_chat  (run from backend/)
"""
import os

os.environ.setdefault("GROQ_API_KEY", "test-key")

import app.routers.public as public_router  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from tests._auth_helper import delete_test_user, register_test_user  # noqa: E402


async def _fake_run_turn(system_prompt, history, user_message, *, tools=None, tool_executor=None):
    return f"echo: {user_message}"


public_router.run_turn = _fake_run_turn

with TestClient(app) as client:
    auth, user_id = register_test_user(client)

    persona = client.post(
        "/personas", json={"name": "Front Desk", "system_prompt": "You are a helpful assistant."}, headers=auth
    ).json()
    persona_id = persona["persona_id"]

    # --- sharing is off by default; the info endpoint 404s -------------

    assert client.get("/public/does-not-exist").status_code == 404

    # --- enable sharing --------------------------------------------------

    share_resp = client.post(f"/personas/{persona_id}/share", headers=auth)
    assert share_resp.status_code == 200, share_resp.text
    token = share_resp.json()["share_token"]
    assert token

    # unauthenticated -> 401, confirms this really is an owner-only route
    assert client.post(f"/personas/{persona_id}/share").status_code == 401

    print("enable sharing: ok")

    # --- public info: name only, nothing persona-internal ----------------

    info_resp = client.get(f"/public/{token}")
    assert info_resp.status_code == 200, info_resp.text
    info = info_resp.json()
    assert info == {"name": "Front Desk"}
    assert "system_prompt" not in info
    assert "archetype_id" not in info
    assert "tool_instance_ids" not in info

    print("public info allowlist: ok")

    # --- session isolation: two sessions, same token, zero cross-talk ---

    session_a = client.post(f"/public/{token}/session").json()["session_id"]
    session_b = client.post(f"/public/{token}/session").json()["session_id"]
    assert session_a != session_b

    chat_resp = client.post(f"/public/{token}/chat", json={"session_id": session_a, "message": "hi from A"})
    assert chat_resp.status_code == 200, chat_resp.text
    assert chat_resp.json()["reply"] == "echo: hi from A"

    history_a = client.get(f"/public/{token}/chat/history", params={"session_id": session_a}).json()
    assert history_a == [
        {"role": "user", "content": "hi from A"},
        {"role": "assistant", "content": "echo: hi from A"},
    ]

    history_b = client.get(f"/public/{token}/chat/history", params={"session_id": session_b}).json()
    assert history_b == []

    # the owner's own authenticated history stays clean of visitor traffic
    owner_history = client.get(f"/personas/{persona_id}/chat/history", headers=auth).json()
    assert owner_history == []

    print("session isolation: ok")

    # --- a session minted for a different persona can't be replayed here -

    other_persona = client.post(
        "/personas", json={"name": "Other", "system_prompt": "test"}, headers=auth
    ).json()
    other_share = client.post(f"/personas/{other_persona['persona_id']}/share", headers=auth).json()["share_token"]
    foreign_session = client.post(f"/public/{other_share}/session").json()["session_id"]

    cross_chat = client.post(f"/public/{token}/chat", json={"session_id": foreign_session, "message": "x"})
    assert cross_chat.status_code == 404

    print("cross-persona session rejected: ok")

    # --- malformed / unknown session_id -> 404, not a 500 ----------------

    assert client.post(f"/public/{token}/chat", json={"session_id": "not-a-uuid", "message": "x"}).status_code == 404
    assert (
        client.get(f"/public/{token}/chat/history", params={"session_id": "not-a-uuid"}).status_code == 404
    )

    # --- regenerating sharing mints a fresh token; the old one dies ------

    regen_resp = client.post(f"/personas/{persona_id}/share", headers=auth)
    new_token = regen_resp.json()["share_token"]
    assert new_token != token
    assert client.get(f"/public/{token}").status_code == 404
    assert client.get(f"/public/{new_token}").status_code == 200

    print("regenerate: ok")

    # --- disable sharing -> link 404s immediately -------------------------

    disable_resp = client.delete(f"/personas/{persona_id}/share", headers=auth)
    assert disable_resp.status_code == 204
    assert client.get(f"/public/{new_token}").status_code == 404

    print("disable sharing: ok")

    delete_test_user(user_id)

print("ok")
