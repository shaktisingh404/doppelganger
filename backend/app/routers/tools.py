"""Tool catalog + activation routes. Activating a tool (POST /tools)
creates a configured ActivatedTool instance; attaching it to a persona
happens separately, via CreatePersonaRequest.tool_instance_ids
(app/routers/personas.py) — activating and attaching are different steps
so one activated tool (e.g. one handoff config) can be reused across
personas without re-entering its config each time.
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

import storage.persona_store as persona_store
import storage.tool_store as tool_store
from app.deps import get_current_user
from app.schemas import ActivateToolRequest, UpdateToolRequest
from app.state import tool_definition_store
from db.models import User
from db.session import get_db
from tools.models import ActivatedTool, HandoffDestination, ToolDefinition

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools", tags=["tools"])


async def _validate_config(
    db: AsyncSession,
    user_id: uuid.UUID,
    tool_id: str,
    definition: ToolDefinition,
    config: dict[str, str],
    destinations: list[HandoffDestination],
) -> None:
    """Shared by activate_tool (create) and update_tool (edit) — same
    config a tool instance must satisfy regardless of which route wrote it."""
    missing = [f.label for f in definition.config_fields if f.required and not config.get(f.key, "").strip()]
    if missing:
        raise HTTPException(status_code=400, detail=f"missing required field(s): {', '.join(missing)}")

    # handoff's real configuration is its destination list, not
    # config_fields — validated here rather than via the generic
    # required-field check above, since "at least one destination,
    # pointing at a real persona" isn't expressible as a flat text field.
    if tool_id == "handoff":
        if not destinations:
            raise HTTPException(status_code=400, detail="handoff needs at least one destination")
        unknown = []
        for d in destinations:
            try:
                found = await persona_store.get(db, uuid.UUID(d.persona_id), user_id)
            except ValueError:
                found = None
            if found is None:
                unknown.append(d.persona_id)
        if unknown:
            raise HTTPException(status_code=400, detail=f"unknown destination persona_id(s): {', '.join(unknown)}")


@router.get("/catalog", response_model=list[ToolDefinition])
def list_catalog(user: User = Depends(get_current_user)):
    return tool_definition_store.list()


@router.post("", response_model=ActivatedTool)
async def activate_tool(
    req: ActivateToolRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    try:
        definition = tool_definition_store.get(req.tool_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if definition.status != "available":
        raise HTTPException(status_code=400, detail=f"{definition.display_name} isn't available to activate yet")

    await _validate_config(db, user.id, req.tool_id, definition, req.config, req.destinations)

    instance = ActivatedTool(
        tool_instance_id=str(uuid.uuid4()),
        tool_id=req.tool_id,
        name=req.name,
        config=req.config,
        destinations=req.destinations,
    )
    await tool_store.add_instance(db, instance, user.id)
    return instance


@router.get("", response_model=list[ActivatedTool])
async def list_activated_tools(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await tool_store.list_instances(db, user.id)


@router.put("/{tool_instance_id}", response_model=ActivatedTool)
async def update_tool(
    tool_instance_id: str,
    req: UpdateToolRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """tool_id is fixed at activation (see UpdateToolRequest) — only
    name/config/destinations are editable here."""
    try:
        tid = uuid.UUID(tool_instance_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="unknown tool_instance_id")
    existing = await tool_store.get_instance(db, tid, user.id)
    if existing is None:
        raise HTTPException(status_code=404, detail="unknown tool_instance_id")

    definition = tool_definition_store.get(existing.tool_id)
    await _validate_config(db, user.id, existing.tool_id, definition, req.config, req.destinations)

    return await tool_store.update_instance(
        db, tid, user.id, name=req.name, config=req.config, destinations=req.destinations
    )


@router.delete("/{tool_instance_id}", status_code=204)
async def delete_tool(
    tool_instance_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    """Soft delete (storage/tool_store.py::delete_instance) plus a cascade:
    strips this instance from every persona that had it attached
    (storage/persona_store.py::detach_tool), so a deleted tool can never
    still be callable from a stale attachment list. The frontend is
    expected to warn the user which assistants will lose it *before*
    calling this — this route just performs the already-confirmed delete."""
    try:
        tid = uuid.UUID(tool_instance_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="unknown tool_instance_id")
    deleted = await tool_store.delete_instance(db, tid, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="unknown tool_instance_id")
    detached = await persona_store.detach_tool(db, tool_instance_id, user.id)
    logger.info("tool_instance_id=%s deleted, detached from %d persona(s)", tool_instance_id, len(detached))
