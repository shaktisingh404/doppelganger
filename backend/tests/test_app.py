"""Smoke test for the FastAPI persona endpoints, against the real
Postgres DB (DATABASE_URL/JWT_SECRET_KEY come from .env — see
backend/README.md's Tests section). Mocks the LLM delta extraction call —
no network, no real Groq key needed. Run with:
python -m tests.test_app  (run from backend/)
"""
import os

os.environ.setdefault("GROQ_API_KEY", "test-key")

import compiler.layers as layers
from compiler.models import InstanceDelta

extract_delta_calls = []


async def _fake_extract_delta(description: str) -> InstanceDelta:
    extract_delta_calls.append(description)
    return InstanceDelta(
        specialization="dental clinic",
        things_to_avoid=["discussing pricing over the phone"],
    )


layers.extract_delta = _fake_extract_delta

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from tests._auth_helper import delete_test_user, register_test_user  # noqa: E402

generate_payload = {
    "archetype_id": "receptionist",
    "name": "Priya",
    "language": "English",
    "tone": "warm and efficient",
    "description": "Handles calls for a dental clinic.",
    "business_info": {
        "name": "Riverside Dental Clinic",
        "address": "12 Elm St, Springfield",
        "phone": "555-0134",
        "hours": "Mon-Fri 9am-5pm",
        "services": ["cleanings", "checkups"],
        "notes": ["closed on public holidays"],
    },
}

# `with` keeps one stable event loop/portal for the whole test — required
# now that there's a real async DB engine behind the app; a bare
# TestClient(app) can hand different requests to different loops and blow
# up asyncpg ("attached to a different loop").
with TestClient(app) as client:
    auth, user_id = register_test_user(client)

    # Unauthenticated requests are rejected before anything else runs.
    assert client.get("/personas").status_code == 401

    # --- POST /personas/generate: description -> system_prompt, nothing stored ---

    gen_resp = client.post("/personas/generate", json=generate_payload, headers=auth)
    assert gen_resp.status_code == 200, gen_resp.text
    prompt = gen_resp.json()["system_prompt"]

    assert "# Business Information" in prompt
    assert "Riverside Dental Clinic" in prompt
    assert "12 Elm St, Springfield" in prompt
    assert "Mon-Fri 9am-5pm" in prompt
    assert "- cleanings" in prompt
    assert "closed on public holidays" in prompt
    assert "say you'll check and follow up" in prompt

    # business_info stays optional: omitting it must not break generation
    # or leak an empty section.
    gen_resp2 = client.post(
        "/personas/generate", json={**generate_payload, "business_info": None}, headers=auth
    )
    assert gen_resp2.status_code == 200, gen_resp2.text
    assert "# Business Information" not in gen_resp2.json()["system_prompt"]

    # Unknown archetype -> 404, not a 500.
    bad_gen = client.post(
        "/personas/generate", json={**generate_payload, "archetype_id": "does-not-exist"}, headers=auth
    )
    assert bad_gen.status_code == 404

    assert len(extract_delta_calls) == 2  # the two successful generates above, not the 404

    # An empty description has nothing to extract, so the LLM call is
    # skipped entirely -- this is what makes it cheap enough for the
    # frontend to call the instant an archetype is picked, to preview the
    # full assembled prompt (common template + guardrails) rather than
    # just the archetype's own short blurb.
    blank_gen = client.post("/personas/generate", json={**generate_payload, "description": ""}, headers=auth)
    assert blank_gen.status_code == 200, blank_gen.text
    assert len(extract_delta_calls) == 2  # unchanged -- no call was made
    blank_prompt = blank_gen.json()["system_prompt"]
    assert "# Archetype Guardrails" in blank_prompt
    assert "# Specialization" not in blank_prompt  # nothing to extract -> no leaked section

    # --- POST /personas: the generated (or hand-typed) text becomes a real persona ---

    create_resp = client.post(
        "/personas",
        json={
            "name": "Priya",
            "system_prompt": prompt,
            "first_message": "Hi, thanks for calling Riverside Dental!",
            "archetype_id": "receptionist",
        },
        headers=auth,
    )
    assert create_resp.status_code == 200, create_resp.text
    persona = create_resp.json()
    assert persona["system_prompt"] == prompt
    assert persona["first_message"] == "Hi, thanks for calling Riverside Dental!"
    assert persona["archetype_id"] == "receptionist"
    persona_id = persona["persona_id"]

    # system_prompt can also be typed from scratch, with no /generate call at all.
    scratch_resp = client.post(
        "/personas", json={"name": "Blank", "system_prompt": "You are a test persona."}, headers=auth
    )
    assert scratch_resp.status_code == 200, scratch_resp.text
    assert scratch_resp.json()["archetype_id"] is None

    # --- GET /personas: lists everything this user created, scoped by auth ---

    list_resp = client.get("/personas", headers=auth)
    assert list_resp.status_code == 200
    listed_ids = {p["persona_id"] for p in list_resp.json()}
    assert persona_id in listed_ids
    assert scratch_resp.json()["persona_id"] in listed_ids

    # --- first_message seeds chat history automatically ---

    history_resp = client.get(f"/personas/{persona_id}/chat/history", headers=auth)
    assert history_resp.status_code == 200
    assert history_resp.json() == [
        {"role": "assistant", "content": "Hi, thanks for calling Riverside Dental!"}
    ]

    # --- a second user can't see or touch this one's personas ---

    auth2, user_id2 = register_test_user(client)
    assert client.get("/personas", headers=auth2).json() == []
    assert client.get(f"/personas/{persona_id}", headers=auth2).status_code == 404
    delete_test_user(user_id2)

    delete_test_user(user_id)  # cascades: personas, chat_messages

print("ok")
