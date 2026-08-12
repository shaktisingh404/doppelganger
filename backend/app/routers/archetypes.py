from fastapi import APIRouter

from app.state import archetype_store

router = APIRouter()


@router.get("/archetypes")
def list_archetypes():
    return archetype_store.list()
