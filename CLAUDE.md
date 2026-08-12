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

### Persona compiler (`backend/compiler/`)

Four layers, only one of which calls an LLM:

1. **Common template** (`data/common_template.txt`) — static guardrails/
   format rules, loaded once via `compiler/layers.py::load_common_template`.
2. **Archetype** (`data/archetypes/*.json`, hand-seeded) — one bundle per
   persona category, loaded through `storage/archetype_store.py`'s
   `ArchetypeStore` interface (`FileArchetypeStore` today; swap
   implementations without touching compiler code).
3. **Instance delta** (`compiler/layers.py::build_instance_delta` →
   `providers/llm.py::extract_delta`) — the *only* LLM call in the
   pipeline, and it's narrow: forced tool-calling extracts free text into
   a fixed `InstanceDelta` schema rather than open-ended generation.
4. **Assembly** (`compiler/assembly.py::assemble_persona`) — pure string
   composition of 1–3 into the final system prompt. No LLM calls. Section
   order matters: archetype-static content stays first (byte-identical
   across every instance of that archetype, forming a stable cacheable
   prefix), instance/delta content that varies per persona always comes
   after.

`compiler/pipeline.py::build_persona` runs all four layers and is the
single entry point used by both `app/main.py` and `cli.py` — don't call
the layers piecemeal from a new call site.

### Tool-calling in chat (`providers/llm.py::run_turn`)

`run_turn` is a generic tool-calling loop, deliberately kept
domain-agnostic (it takes `tools`/`tool_executor` params but doesn't know
what any tool *does*). The `/chat` endpoint in `app/main.py` is what wires
in the scheduling-specific tool (`scheduler.tool.SCHEDULE_CALLBACK_TOOL`)
and its executor. When `tools` is passed, `run_turn` injects the current
UTC time into the system prompt — without that grounding the model can't
resolve relative phrasing ("tomorrow at 3pm") into the absolute timestamp
`schedule_callback` requires; nothing else in the codebase supplies it.

The scheduler's own proactive follow-up firing (see below) calls
`run_turn` with no `tools`, so a fired follow-up can never itself trigger
another tool call.

### Scheduled follow-ups (`backend/scheduler/`)

Not a task queue — a single APScheduler `AsyncIOScheduler` interval job
(`scheduler/dispatcher.py::start_dispatcher`, registered in `app/main.py`'s
FastAPI lifespan) polls an in-memory `ScheduledCallStore`
(`scheduler/models.py`) every `scheduled_callback_poll_interval_seconds`
(default 30s) for due, `pending` rows.

- **Creating a row**: `scheduler/tool.py::schedule_callback` — called
  either by the model mid-chat (via the `run_turn` tool-calling above) or
  directly through the debug `POST /scheduled-calls` endpoint. Validates
  the timestamp is absolute/tz-aware, in the future, within
  `scheduled_callback_max_window_days`, and under
  `scheduled_callback_max_pending_per_number` pending rows for that
  identity. (Chat has no phone number, so `persona_id` stands in as the
  cap key for chat-originated rows — see the executor in `app/main.py`.)
- **Firing a row**: `scheduler/dispatcher.py::_dispatch_one` calls
  `run_turn` with the persona's system prompt plus a hidden instruction
  (`build_resume_context_block`) and appends the reply directly into that
  persona's chat history — a proactive assistant message the user sees on
  their next `GET /personas/{id}/chat/history` poll. One retry
  (`_MAX_ATTEMPTS = 2`) on failure, then the row is marked `failed`.

Storage is in-memory only — a restart wipes every pending row. If that
starts to matter, persist `ScheduledCallStore`; there's no need to replace
APScheduler itself for that (see the poll/retry knobs in `config.py`).

### State model

`app/main.py` holds `_personas`, `_histories`, and `_scheduled_calls` as
plain in-memory dicts — no persistence, no database, single-process only.
This is a deliberate phase-1 scope, not an oversight; don't add a database
layer without checking whether it's actually needed yet.

### Frontend ↔ backend contract

`frontend/src/types.ts` mirrors the backend's Pydantic models by hand
(`ArchetypeSpec`, `InstanceInput`, `AssembledPersona`, `ChatMessage`) — keep
field names/optionality in sync manually when the API contract changes,
there's no shared schema generation. `ChatPanel.tsx` polls
`GET /personas/{id}/chat/history` every 4s (paused mid-send) specifically
to surface proactive scheduler-fired messages without user action.
