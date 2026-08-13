"""Request/response shapes for auth routes — distinct from db/models.py's
User (the stored row, includes hashed_password) the same way
app/schemas.py stays distinct from compiler/models.py: API boundary
shapes vs. what's actually persisted.
"""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    # max_length=72: bcrypt's own input cap (see auth/security.py) —
    # enforced here so an over-long password 422s cleanly instead of
    # raising from inside hash_password.
    password: str = Field(min_length=8, max_length=72)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: str
    email: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic
