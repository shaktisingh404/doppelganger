# Doppelganger

Dynamic persona voice service — two-part project:

- **`backend/`** — Python/FastAPI. Persona compiler (archetype + instance
  delta → assembled system prompt), text chat, and scheduled follow-ups
  (a persona can ask mid-chat to be reminded later; a background poller
  fires it back into the same chat when due). See `backend/README.md` for
  details. Calling (Twilio Media Streams + a realtime voice bridge) was
  removed — chat is the only live channel today.
- **`frontend/`** — React + TypeScript (Vite). Persona builder + chat UI
  that drives the backend API directly (archetype picker → instance form →
  assembled persona view → live chat).

## Run both

```
# backend
cd backend
source .venv/bin/activate  # or use .venv/bin/python directly
uvicorn app.main:app --reload --port 8010

# frontend (separate terminal)
cd frontend
npm run dev
```

Open the frontend's dev URL (typically `http://localhost:5173`). It proxies
`/api/*` requests to the backend at `http://localhost:8010` (configured in
`frontend/vite.config.ts`).

Port 8010 is used instead of the more common 8000 because 8000 may already
be occupied by another service on your machine — change both the uvicorn
`--port` and `frontend/vite.config.ts`'s proxy target together if you'd
rather use a different port.

## License

[MIT](LICENSE)
