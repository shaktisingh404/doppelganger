"""Storage for the tool catalog (prebuilt types) and activated (configured)
instances. Two different backings on purpose: the catalog is developer-
edited reference content (data/tools/*.json, like archetypes) with no
reason to live in Postgres; activated instances are user data and are
DB-backed, scoped per user_id, as async module-level functions rather
than a class — there's no more in-memory state to encapsulate now that
the DB session (passed in per call) carries it.
"""
import json
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ToolInstance as ToolInstanceRow
from tools.models import ActivatedTool, HandoffDestination, ToolDefinition


class ToolDefinitionStore(ABC):
    @abstractmethod
    def get(self, tool_id: str) -> ToolDefinition: ...

    @abstractmethod
    def list(self) -> list[ToolDefinition]: ...


class FileToolDefinitionStore(ToolDefinitionStore):
    def __init__(self, directory: str | Path):
        self._dir = Path(directory)

    def get(self, tool_id: str) -> ToolDefinition:
        path = self._dir / f"{tool_id}.json"
        if not path.exists():
            raise KeyError(f"unknown tool: {tool_id}")
        return ToolDefinition.model_validate(json.loads(path.read_text()))

    def list(self) -> list[ToolDefinition]:
        return [
            ToolDefinition.model_validate(json.loads(p.read_text()))
            for p in sorted(self._dir.glob("*.json"))
        ]


def _to_domain(row: ToolInstanceRow) -> ActivatedTool:
    return ActivatedTool(
        tool_instance_id=str(row.id),
        tool_id=row.tool_id,
        name=row.name,
        config=row.config,
        destinations=[HandoffDestination(**d) for d in row.destinations],
        created_at=row.created_at,
    )


async def add_instance(db: AsyncSession, instance: ActivatedTool, user_id: uuid.UUID) -> None:
    row = ToolInstanceRow(
        id=uuid.UUID(instance.tool_instance_id),
        user_id=user_id,
        tool_id=instance.tool_id,
        name=instance.name,
        config=instance.config,
        destinations=[d.model_dump() for d in instance.destinations],
    )
    db.add(row)
    await db.flush()


async def get_instance(db: AsyncSession, tool_instance_id: uuid.UUID, user_id: uuid.UUID) -> ActivatedTool | None:
    row = await db.scalar(
        select(ToolInstanceRow).where(ToolInstanceRow.id == tool_instance_id, ToolInstanceRow.user_id == user_id)
    )
    return _to_domain(row) if row else None


async def list_instances(db: AsyncSession, user_id: uuid.UUID) -> list[ActivatedTool]:
    result = await db.scalars(
        select(ToolInstanceRow).where(ToolInstanceRow.user_id == user_id).order_by(ToolInstanceRow.created_at)
    )
    return [_to_domain(r) for r in result]
