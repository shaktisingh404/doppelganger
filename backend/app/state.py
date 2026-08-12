"""Process-wide singleton stores — the composition root for this app's
in-memory state (phase 1 scope: single process, no persistence). Routers
import these instances directly rather than each owning their own state.
"""
from config import get_settings
from scheduler.models import ScheduledCallStore
from storage.archetype_store import ArchetypeStore, FileArchetypeStore
from storage.persona_store import PersonaStore

archetype_store: ArchetypeStore = FileArchetypeStore(get_settings().archetypes_dir)
persona_store = PersonaStore()
scheduled_call_store = ScheduledCallStore()
