"""Transactional outbox: side effects (emails, notifications, cross-module events) are
written in the same transaction as the change, then delivered after commit.

Delivery happens right after the request commits (`dispatch`), and again from a scheduled
job for anything that failed, so nothing is lost if the process dies. Handlers must be
idempotent: an event can be delivered more than once.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, func, literal_column, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import open_session
from app.core.ids import uuid7
from app.core.models import Base

log = logging.getLogger("app.outbox")

Handler = Callable[[dict[str, Any]], Awaitable[None]]
_handlers: dict[str, Handler] = {}

MAX_ATTEMPTS = 8


class OutboxEvent(Base):
    """Global table (not tenant-scoped): the dispatcher reads across tenants.
    Payloads carry the tenant id when a handler needs it."""

    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    tenant_id: Mapped[uuid.UUID | None]
    topic: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_error: Mapped[str | None] = mapped_column(Text)


def handler(topic: str) -> Callable[[Handler], Handler]:
    def wrap(fn: Handler) -> Handler:
        _handlers[topic] = fn
        return fn

    return wrap


def enqueue(
    db: AsyncSession, topic: str, payload: dict[str, Any], tenant_id: uuid.UUID | None = None
) -> uuid.UUID:
    event = OutboxEvent(id=uuid7(), tenant_id=tenant_id, topic=topic, payload=payload)
    db.add(event)
    pending: list[uuid.UUID] = db.info.setdefault("outbox_pending", [])
    pending.append(event.id)
    return event.id


def pending_ids(db: AsyncSession) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = db.info.pop("outbox_pending", [])
    return ids


async def dispatch(ids: list[uuid.UUID] | None = None, limit: int = 50) -> int:
    """Deliver events (the given ids, or anything due). Returns how many were delivered."""
    delivered = 0
    async with open_session() as db:
        query = (
            select(OutboxEvent)
            .where(OutboxEvent.dispatched_at.is_(None), OutboxEvent.attempts < MAX_ATTEMPTS)
            .order_by(OutboxEvent.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        if ids is not None:
            if not ids:
                return 0
            query = query.where(OutboxEvent.id.in_(ids))
        else:
            query = query.where(OutboxEvent.available_at <= func.now())
        events = list((await db.scalars(query)).all())
        for event in events:
            fn = _handlers.get(event.topic)
            try:
                if fn is None:
                    raise LookupError(f"No handler for {event.topic}")
                await fn(event.payload)
            except Exception as exc:  # delivery is retried; log and move on
                log.warning("Outbox delivery failed", extra={"topic": event.topic, "error": str(exc)})
                await db.execute(
                    update(OutboxEvent)
                    .where(OutboxEvent.id == event.id)
                    .values(
                        attempts=OutboxEvent.attempts + 1,
                        last_error=str(exc)[:1000],
                        # Exponential backoff: 1, 2, 4, 8 … minutes.
                        available_at=literal_column(
                            "now() + make_interval(mins => power(2, outbox_events.attempts)::int)"
                        ),
                    )
                )
            else:
                await db.execute(
                    update(OutboxEvent)
                    .where(OutboxEvent.id == event.id)
                    .values(dispatched_at=func.now(), attempts=OutboxEvent.attempts + 1)
                )
                delivered += 1
        await db.commit()
    return delivered
