"""Alembic env — imports Base metadata so autogenerate sees all models."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.models  # noqa: F401 — register all models
from app.config import settings
from app.database import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=settings.DATABASE_URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        {"sqlalchemy.url": settings.DATABASE_URL}, prefix="sqlalchemy.", poolclass=None
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
