"""Database engine and sessions.

Tenant isolation at the database level: every transaction a session opens runs
`set_config('app.tenant_id', …, true)` (transaction-local, so it is safe behind PgBouncer
in transaction mode). Row-level security policies compare against it. A session without a
tenant sees no tenant rows at all.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, SessionTransaction

from app.core.config import get_settings

TENANT_KEY = "tenant_id"
USER_KEY = "user_id"

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _apply_context(session: Session, connection: Connection) -> None:
    tenant = session.info.get(TENANT_KEY)
    user = session.info.get(USER_KEY)
    connection.execute(
        text("SELECT set_config('app.tenant_id', :t, true), set_config('app.user_id', :u, true)"),
        {"t": str(tenant) if tenant else "", "u": str(user) if user else ""},
    )


@event.listens_for(Session, "after_begin")
def _on_begin(session: Session, transaction: SessionTransaction, connection: Connection) -> None:
    _apply_context(session, connection)


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url.get_secret_value(),
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
            # psycopg 3 prepares statements only after repeated use; disable it so
            # PgBouncer in transaction mode (Neon's pooler) never sees stale statements.
            connect_args={"prepare_threshold": None},
        )
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, autoflush=True)
    return _engine


def sessionmaker() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


async def set_tenant(
    session: AsyncSession, tenant_id: uuid.UUID | None, user_id: uuid.UUID | None = None
) -> None:
    """Bind the session to a tenant. Applies to the current and every later transaction."""
    session.info[TENANT_KEY] = tenant_id
    if user_id is not None:
        session.info[USER_KEY] = user_id
    if session.in_transaction():
        await session.execute(
            text("SELECT set_config('app.tenant_id', :t, true), set_config('app.user_id', :u, true)"),
            {
                "t": str(tenant_id) if tenant_id else "",
                "u": str(session.info.get(USER_KEY) or ""),
            },
        )


def current_tenant(session: AsyncSession) -> uuid.UUID:
    tenant = session.info.get(TENANT_KEY)
    if not isinstance(tenant, uuid.UUID):
        raise RuntimeError("No tenant is bound to this session.")
    return tenant


@asynccontextmanager
async def open_session(
    tenant_id: uuid.UUID | None = None, user_id: uuid.UUID | None = None
) -> AsyncIterator[AsyncSession]:
    """A session for jobs and scripts. The caller commits; anything else rolls back."""
    async with sessionmaker()() as session:
        session.info[TENANT_KEY] = tenant_id
        session.info[USER_KEY] = user_id
        try:
            yield session
        finally:
            await session.rollback()


async def get_db() -> AsyncIterator[AsyncSession]:
    """Request-scoped session. Routes must `await db.commit()` before returning.

    FastAPI runs this cleanup after the response is sent, so a commit here could fail
    after the client already saw success. Uncommitted work is rolled back.
    """
    async with sessionmaker()() as session:
        try:
            yield session
        finally:
            await session.rollback()


def row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row._mapping)
