"""Tool catalog + activation routes. Activating a tool (POST /tools)
creates a configured ActivatedTool instance; attaching it to a persona
happens separately, via CreatePersonaRequest.tool_instance_ids
(app/routers/personas.py) — activating and attaching are different steps
so one activated tool (e.g. one handoff config) can be reused across
personas without re-entering its config each time.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

import storage.persona_store as persona_store
import storage.tool_store as tool_store
from app.deps import get_current_user
from app.schemas import ActivateToolRequest
from app.state import tool_definition_store
from db.models import User
from db.session import get_db
from tools.models import ActivatedTool, ToolDefinition

router = APIRouter(prefix="/tools", tags=["tools"])


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

    missing = [
        f.label for f in definition.config_fields if f.required and not req.config.get(f.key, "").strip()
    ]
    if missing:
        raise HTTPException(status_code=400, detail=f"missing required field(s): {', '.join(missing)}")

    # handoff's real configuration is its destination list, not
    # config_fields — validated here rather than via the generic
    # required-field check above, since "at least one destination,
    # pointing at a real persona" isn't expressible as a flat text field.
    if req.tool_id == "handoff":
        if not req.destinations:
            raise HTTPException(status_code=400, detail="handoff needs at least one destination")
        unknown = []
        for d in req.destinations:
            try:
                found = await persona_store.get(db, uuid.UUID(d.persona_id), user.id)
            except ValueError:
                found = None
            if found is None:
                unknown.append(d.persona_id)
        if unknown:
            raise HTTPException(status_code=400, detail=f"unknown destination persona_id(s): {', '.join(unknown)}")

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
