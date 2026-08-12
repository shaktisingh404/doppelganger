# Dynamic Persona Voice Service — Phase 1

Text-only "brain" for a dynamic voice-persona system. No telephony, STT, or
TTS yet — that comes later once prompt assembly is solid.

## Layers

1. **Common template** (`data/common_template.txt`) — static guardrails and
   output-format rules, loaded once, never regenerated.
2. **Archetype cache** (`data/archetypes/*.json`) — one hand-seeded bundle
   per category, loaded via `storage/archetype_store.py`.
3. **Instance delta** (`compiler/layers.py` + `providers/llm.py::extract_delta`)
   — a narrow LLM call that extracts free text into a validated
   `InstanceDelta`.
4. **Assembly** (`compiler/assembly.py`) — pure string composition of 1-3
   into a final system prompt. No LLM calls.

`compiler/pipeline.py::build_persona` runs the whole thing and is the single
entry point used by both `app/` and `cli.py`.

## Setup

```
pip install -r requirements.txt
cp .env.example .env   # fill in GROQ_API_KEY
```

## Run the API

```
uvicorn app.main:app --reload
```

- `GET /archetypes`
- `POST /personas` — body: `InstanceInput`
- `POST /personas/{id}/chat` — body: `{"message": "..."}`

## Run the CLI (no server needed)

```
python cli.py
```

Prompts for an archetype, name, language, tone, and description, assembles
the persona, prints the system prompt, then drops into a chat loop.

## Tests

Plain smoke-test scripts (assert-based, no pytest) live in `tests/`. Run one:

```
python -m tests.test_scheduler
```

Or all of them:

```
./tests/run_all.sh
```

## Non-goals (this phase)

No telephony/STT/TTS, no real database, no auth, no archetype
auto-generation (`providers.llm.generate_archetype` exists but isn't wired
into any endpoint yet).
