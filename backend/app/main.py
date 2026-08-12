"""FastAPI composition root: creates the app, wires the lifespan
dispatcher, and mounts the routers. Route handlers live in app/routers/;
in-memory state lives in app/state.py; request/response schemas live in
app/schemas.py.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import archetypes, personas, scheduled_calls
from app.state import persona_store, scheduled_call_store
from config import get_settings
from scheduler.dispatcher import start_dispatcher


@asynccontextmanager
async def _lifespan(app: FastAPI):
    dispatcher = start_dispatcher(
        scheduled_call_store, get_settings(), persona_store.get, persona_store.history
    )
    try:
        yield
    finally:
        dispatcher.shutdown(wait=False)


app = FastAPI(title="Dynamic Persona Voice Service", lifespan=_lifespan)

# Vite dev server origin — the frontend also proxies /api through Vite in
# dev, but CORS is what makes direct cross-origin calls work too (e.g. a
# frontend build served separately from the proxy later).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(archetypes.router)
app.include_router(personas.router)
app.include_router(scheduled_calls.router)
