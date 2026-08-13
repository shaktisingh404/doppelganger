from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.state import archetype_store
from db.models import User

router = APIRouter()


@router.get("/archetypes")
def list_archetypes(user: User = Depends(get_current_user)):
    return archetype_store.list()
