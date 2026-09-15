"""Async engine for the web API + sync engine for Celery workers.

Celery tasks are fully synchronous and must NEVER create an event loop
(via asyncio.run) — they use SyncSessionLocal below.
"""
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_async_engine(settings.DATABASE_URL, echo=False, connect_args=connect_args)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

sync_connect_args: dict = {}
if settings.SYNC_DATABASE_URL.startswith("sqlite"):
    sync_connect_args = {"check_same_thread": False, "timeout": 30}

sync_engine = create_engine(settings.SYNC_DATABASE_URL, echo=False, connect_args=sync_connect_args)
SyncSessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)


async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@contextmanager
def get_sync_db():
    """Sync session helper for Celery tasks and scripts (commit/rollback included)."""
    with SyncSessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
