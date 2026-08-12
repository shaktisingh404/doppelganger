"""In-memory persona + chat-history storage (phase 1 scope: no
persistence, no concurrency safety beyond what asyncio's single-threaded
event loop gives us for free — same tradeoff scheduler/models.py makes for
ScheduledCallStore).
"""
from compiler.models import AssembledPersona


class PersonaStore:
    def __init__(self) -> None:
        self._personas: dict[str, AssembledPersona] = {}
        self._histories: dict[str, list[dict[str, str]]] = {}

    def add(self, persona: AssembledPersona) -> None:
        self._personas[persona.persona_id] = persona
        self._histories[persona.persona_id] = []

    def get(self, persona_id: str) -> AssembledPersona | None:
        return self._personas.get(persona_id)

    def history(self, persona_id: str) -> list[dict[str, str]]:
        return self._histories.setdefault(persona_id, [])
