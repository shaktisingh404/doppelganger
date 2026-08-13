"""Process-wide singletons — now just the two file/JSON-backed catalogs
(developer-edited reference content, no reason to live in Postgres).
Everything else (personas, tool instances, scheduled calls, chat history)
is user-scoped and DB-backed — see storage/persona_store.py,
storage/tool_store.py, scheduler/models.py — fetched per request via
Depends(get_db), not held here.
"""
from config import get_settings
from storage.archetype_store import ArchetypeStore, FileArchetypeStore
from storage.tool_store import FileToolDefinitionStore, ToolDefinitionStore

archetype_store: ArchetypeStore = FileArchetypeStore(get_settings().archetypes_dir)
tool_definition_store: ToolDefinitionStore = FileToolDefinitionStore(get_settings().tools_dir)
