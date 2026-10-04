"""Domain events: a record of everything important that happens in a workspace.

`emit` writes the event to `domain_events` in the same transaction as the change, so the
log and the data never disagree. Then:
- in-process subscribers (`on(name)`, e.g. in-app notifications) run immediately, in the
  same transaction: if they fail, the change fails;
- outbox subscribers (`on(name, later=True)`, e.g. emails) run after commit, with retries.

Automations and the weekly brief (M6 and M7) read the log; nothing reads module tables to
find out what happened.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import datetime
from typing import Any

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core import context, outbox
from app.core.db import current_tenant, open_session
from app.core.ids import uuid7
from app.core.models import Base, TenantScoped
from app.core.time import utcnow

Subscriber = Callable[[AsyncSession, "Event"], Awaitable[None]]

_now: dict[str, list[Subscriber]] = {}
_later: dict[str, list[Subscriber]] = {}
TOPIC = "domain_event"
# Set while an automation runs: events it causes carry it in `data["origin"]`, so
# automations never start other automations (no loops).
origin: ContextVar[str | None] = ContextVar("event_origin", default=None)


class DomainEvent(TenantScoped, Base):
    __tablename__ = "domain_events"
    __table_args__ = (Index("ix_domain_events_time", "tenant_id", "occurred_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String(80), index=True)
    occurred_at: Mapped[datetime]
    actor_user_id: Mapped[uuid.UUID | None]
    subject_type: Mapped[str | None] = mapped_column(String(40))
    subject_id: Mapped[str | None] = mapped_column(String(64))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Event:
    """What subscribers receive."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.id = uuid.UUID(payload["id"])
        self.tenant_id = uuid.UUID(payload["tenant_id"])
        self.name: str = payload["name"]
        self.actor_user_id = uuid.UUID(payload["actor_user_id"]) if payload.get("actor_user_id") else None
        self.subject_type: str | None = payload.get("subject_type")
        self.subject_id: str | None = payload.get("subject_id")
        self.data: dict[str, Any] = payload.get("data") or {}

    def as_payload(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "name": self.name,
            "actor_user_id": str(self.actor_user_id) if self.actor_user_id else None,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "data": self.data,
        }


def on(name: str, *, later: bool = False) -> Callable[[Subscriber], Subscriber]:
    """Subscribe to an event ("leave.approved"), a family ("leave.*") or everything ("*")."""

    def register(fn: Subscriber) -> Subscriber:
        target = (_later if later else _now).setdefault(name, [])
        if fn not in target:
            target.append(fn)
        return fn

    return register


def _matching(table: dict[str, list[Subscriber]], name: str) -> list[Subscriber]:
    family = name.split(".", 1)[0] + ".*"
    return [*table.get(name, []), *table.get(family, []), *table.get("*", [])]


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, uuid.UUID | datetime):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


async def emit(
    db: AsyncSession,
    name: str,
    *,
    subject_type: str | None = None,
    subject_id: uuid.UUID | str | None = None,
    data: dict[str, Any] | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> Event:
    tenant_id = current_tenant(db)
    actor = actor_user_id or context.current().user_id
    if origin.get():
        data = {**(data or {}), "origin": origin.get()}
    row = DomainEvent(
        id=uuid7(),
        tenant_id=tenant_id,
        name=name,
        occurred_at=utcnow(),
        actor_user_id=actor,
        subject_type=subject_type,
        subject_id=str(subject_id) if subject_id else None,
        data=_jsonable(data or {}),
    )
    db.add(row)
    event = Event(
        {
            "id": str(row.id),
            "tenant_id": str(tenant_id),
            "name": name,
            "actor_user_id": str(actor) if actor else None,
            "subject_type": subject_type,
            "subject_id": row.subject_id,
            "data": row.data,
        }
    )
    for subscriber in _matching(_now, name):
        await subscriber(db, event)
    if _matching(_later, name):
        outbox.enqueue(db, TOPIC, event.as_payload(), tenant_id=tenant_id)
    return event


@outbox.handler(TOPIC)
async def _deliver(payload: dict[str, Any]) -> None:
    event = Event(payload)
    for subscriber in _matching(_later, event.name):
        async with open_session(event.tenant_id) as db:
            await subscriber(db, event)
            await db.commit()
