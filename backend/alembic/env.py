import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# db/models.py must be imported so its tables register on Base.metadata
# before autogenerate/create can see them.
import db.models  # noqa: F401
from config import get_settings
from db.session import Base, asyncpg_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Pulled from our own Settings (.env) rather than duplicated in
# alembic.ini's sqlalchemy.url — one source of truth for the connection string.
config.set_main_option("sqlalchemy.url", asyncpg_url(get_settings().database_url))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
