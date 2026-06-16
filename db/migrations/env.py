"""Alembic environment — the bootstrap that runs database migrations.

Alembic imports this file every time you run ``alembic upgrade``/``downgrade``.
It tells Alembic how to connect (as the *owner* role, since migrations issue DDL
and grant privileges) and what the target schema looks like (``Base.metadata``
from the ORM models). It supports both "online" mode (connect to a live DB, the
normal path) and "offline" mode (emit SQL without connecting). The connection is
async, so the online path drives the migrations through an asyncio event loop.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from fixmate.core.models import Base
from fixmate.core.settings import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Migrations run as the owner role (DDL, role grants), not fixmate_app.
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit migration SQL to stdout without connecting to a database."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run the migrations against an already-open (sync-style) connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Open an async engine, run migrations on it, and dispose it."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for the normal (connected) migration path."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
