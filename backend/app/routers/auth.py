"""Register/login/me. Registration logs you in too — returns a token
immediately rather than forcing a second /login call right after signup.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user
from auth.schemas import Token, UserCreate, UserLogin, UserPublic
from auth.security import create_access_token, hash_password, verify_password
from config import get_settings
from db.models import User
from db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_for(user: User) -> Token:
    access_token = create_access_token(user.id, get_settings())
    return Token(
        access_token=access_token,
        user=UserPublic(id=str(user.id), email=user.email, created_at=user.created_at),
    )


@router.post("/register", response_model=Token)
async def register(req: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == req.email))
    if existing is not None:
        raise HTTPException(status_code=400, detail="email already registered")

    user = User(email=req.email, hashed_password=hash_password(req.password))
    db.add(user)
    await db.flush()  # populates user.id (client-side default) without ending the request's transaction
    logger.info("user registered id=%s", user.id)
    return _token_for(user)


@router.post("/login", response_model=Token)
async def login(req: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == req.email))
    if user is None or not verify_password(req.password, user.hashed_password):
        # Same message for "no such user" and "wrong password" -- confirming
        # an email is registered is its own small information leak. The log
        # line can distinguish internally without that leaking externally —
        # a burst of these against one email is worth being able to see.
        logger.warning("login failed email=%s reason=%s", req.email, "no such user" if user is None else "bad password")
        raise HTTPException(status_code=401, detail="incorrect email or password")
    return _token_for(user)


@router.get("/me", response_model=UserPublic)
async def me(user: User = Depends(get_current_user)):
    return UserPublic(id=str(user.id), email=user.email, created_at=user.created_at)
