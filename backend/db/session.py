"""Async SQLAlchemy engine + session factory. One engine per process,
built lazily from settings.database_url so importing this module never
requires Settings to already be constructed (mirrors config.get_settings'
own lazy @lru_cache pattern).
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import get_settings


class Base(DeclarativeBase):
    pass


def asyncpg_url(database_url: str) -> str:
    """Accepts a plain postgresql:// URL (what most tools/docs print) and
    normalizes it to the asyncpg driver SQLAlchemy's async engine needs —
    one less thing to get right when pasting a connection string in."""
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(asyncpg_url(get_settings().database_url))
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: one session per request, committed on success,
    rolled back on any exception, always closed."""
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
