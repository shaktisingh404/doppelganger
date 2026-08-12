"""Smoke test for the FastAPI persona endpoint. Mocks the LLM delta
extraction call — no network, no real API key needed. Run with:
python -m tests.test_app  (run from backend/)
"""
import os

os.environ.setdefault("GROQ_API_KEY", "test-key")

import compiler.layers as layers
from compiler.models import InstanceDelta


async def _fake_extract_delta(description: str) -> InstanceDelta:
    return InstanceDelta(
        specialization="dental clinic",
        things_to_avoid=["discussing pricing over the phone"],
    )


layers.extract_delta = _fake_extract_delta

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)

payload = {
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

resp = client.post("/personas", json=payload)
assert resp.status_code == 200, resp.text
prompt = resp.json()["system_prompt"]

assert "# Business Information" in prompt
assert "Riverside Dental Clinic" in prompt
assert "12 Elm St, Springfield" in prompt
assert "Mon-Fri 9am-5pm" in prompt
assert "- cleanings" in prompt
assert "closed on public holidays" in prompt
assert "say you'll check and follow up" in prompt
assert resp.json()["archetype_id"] == "receptionist"

# business_info stays optional: omitting it must not break the endpoint or
# leak an empty section.
resp2 = client.post("/personas", json={**payload, "business_info": None})
assert resp2.status_code == 200, resp2.text
assert "# Business Information" not in resp2.json()["system_prompt"]

print("ok")
