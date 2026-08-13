# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Doppelganger is a dynamic persona voice/chat service, two parts:

- **`backend/`** — Python/FastAPI. Compiles a persona (archetype + free-text
  description) into an assembled system prompt, then serves text chat
  against it.
- **`frontend/`** — React + TypeScript (Vite). Persona builder + chat UI:
  archetype picker → instance form → assembled persona view → live chat.

Chat is currently the only live channel. Calling (Twilio Media Streams +
a realtime voice bridge) existed at one point and was removed; if it comes
back, it re-enters as a channel branch in `scheduler/dispatcher.py`, not a
bolt-on.

## Commands

Run both halves for local dev:

```bash
# backend (from backend/)
source .venv/bin/activate  # or use .venv/bin/python directly
uvicorn app.main:app --reload --port 8010

# frontend (from frontend/, separate terminal)
npm run dev
```

Frontend dev server is `http://localhost:5173` and proxies `/api/*` to the
backend on port 8010 (`frontend/vite.config.ts`). Port 8010 is used instead
of 8000 to dodge a common local conflict — if you change it, update both
the uvicorn `--port` and the vite proxy target together.

Backend setup:

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # fill in GROQ_API_KEY
```

**Tests** (backend only; assert-based smoke test scripts, no pytest):

```bash
cd backend
python -m tests.test_scheduler     # run one
./tests/run_all.sh                 # run all, stops at first failure
```

Each test file targets one module (`test_app.py` → `app/main.py`,
`test_scheduler.py` → `scheduler/`, etc.) and is runnable standalone via
`python -m tests.<name>` — must be invoked with `-m` from `backend/`, not
as a bare script path, or the `from config import ...`-style absolute
imports break.

**Frontend:**

```bash
cd frontend
npm run build   # tsc -b && vite build
npm run lint    # oxlint
```

**CLI** (exercise the persona pipeline without the API or frontend):

```bash
cd backend && python cli.py
```

## Architecture

Full docs live in **`docs/`** — start at [`docs/README.md`](./docs/README.md).
Quick orientation:

- **Persona compiler** (`backend/compiler/`) — 4 layers (common template →
  archetype → LLM-extracted instance delta → pure-string assembly),
  entered via `compiler/pipeline.py`'s `generate_system_prompt` (the
  "Generate" preview step) and `instantiate_persona` (the "Create" step).
  Details: [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md).
- **State is Postgres-backed**, not in-memory — every persona, tool
  instance, scheduled call, and chat message is a real DB row, scoped per
  authenticated user (JWT bearer auth). Soft delete (`deleted_at`), not
  hard delete. Details: [`docs/DATABASE.md`](./docs/DATABASE.md),
  [`docs/AUTH.md`](./docs/AUTH.md).
- **Tool-calling in chat** (`providers/llm.py::run_turn`) — generic,
  domain-agnostic tool-calling loop; `app/routers/personas.py`'s
  `POST /personas/{id}/chat` wires in the always-on `schedule_callback`
  tool plus whatever's attached (see `tools/registry.py`). Chat sampling
  (`chat_max_tokens`/`chat_temperature`/`chat_reasoning_effort` in
  `config.py`) and the common template's "1-2 sentences per turn" rule
  keep replies phone-call length, not essays. Details:
  [`docs/BACKEND.md`](./docs/BACKEND.md).
- **Handoff** (`tools/handoff.py`) — routes a *live conversation* to a
  different assistant mid-chat (matches Vapi's real behavior, not human
  escalation) via a `Persona.active_persona_id` override. Details:
  [`docs/TOOLS.md`](./docs/TOOLS.md).
- **Scheduled follow-ups** (`backend/scheduler/`) — not a task queue, a
  single APScheduler interval job polling Postgres directly. Safe under
  multiple worker processes with no broker: `scheduler/models.py::claim_due`
  atomically claims due rows via one `UPDATE ... RETURNING`, so two
  pollers can never double-fire the same row. Details:
  [`docs/SCHEDULER.md`](./docs/SCHEDULER.md).
- **Frontend ↔ backend contract** — `frontend/src/types.ts` mirrors the
  backend's Pydantic models by hand; keep field names/optionality in sync
  manually, there's no shared schema generation. `ChatPanel.tsx` polls
  `GET /personas/{id}/chat/history` every 4s (paused mid-send) to surface
  proactive scheduler-fired messages without user action. Details:
  [`docs/FRONTEND.md`](./docs/FRONTEND.md), every endpoint:
  [`docs/API.md`](./docs/API.md).
