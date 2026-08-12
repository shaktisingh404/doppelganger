"""Storage interface for the archetype cache (Layer 2).

File/JSON-backed today; swap the implementation for Postgres later without
touching compiler code, which only ever depends on ArchetypeStore.
"""
import json
from abc import ABC, abstractmethod
from pathlib import Path

from compiler.models import ArchetypeSpec


class ArchetypeStore(ABC):
    @abstractmethod
    def get(self, archetype_id: str) -> ArchetypeSpec: ...

    @abstractmethod
    def list(self) -> list[ArchetypeSpec]: ...


class FileArchetypeStore(ArchetypeStore):
    def __init__(self, directory: str | Path):
        self._dir = Path(directory)

    def get(self, archetype_id: str) -> ArchetypeSpec:
        path = self._dir / f"{archetype_id}.json"
        if not path.exists():
            raise KeyError(f"unknown archetype: {archetype_id}")
        return ArchetypeSpec.model_validate(json.loads(path.read_text()))

    def list(self) -> list[ArchetypeSpec]:
        return [
            ArchetypeSpec.model_validate(json.loads(p.read_text()))
            for p in sorted(self._dir.glob("*.json"))
        ]
