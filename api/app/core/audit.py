"""Tamper-evident audit log.

Rows are append-only (the app role has INSERT and SELECT only, and a trigger rejects
UPDATE and DELETE). Each tenant's rows form a hash chain: every row stores the previous
row's hash and its own hash over a canonical form of its content. `verify_chain` recomputes
it, so any edit made directly in the database is detected.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, String, Text, UniqueConstraint, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core import context
from app.core.db import current_tenant
from app.core.ids import uuid7
from app.core.models import Base, TenantScoped

GENESIS = "0" * 64

# Keys whose values never go into the audit log.
_REDACT = {"password", "password_hash", "token", "secret", "totp_secret", "code", "pin"}


class AuditEvent(TenantScoped, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    seq: Mapped[int] = mapped_column(BigInteger)
    occurred_at: Mapped[datetime]
    actor_user_id: Mapped[uuid.UUID | None]
    actor_label: Mapped[str | None] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(100), index=True)
    target_type: Mapped[str | None] = mapped_column(String(50))
    target_id: Mapped[str | None] = mapped_column(String(64))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    request_id: Mapped[str | None] = mapped_column(String(64))
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text)


def redact(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: ("[redacted]" if k.lower() in _REDACT else redact(v)) for k, v in data.items()}
    if isinstance(data, list):
        return [redact(v) for v in data]
    return data


def _canonical(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_canonical(v) for v in value]
    return value


def compute_hash(prev_hash: str, fields: dict[str, Any]) -> str:
    body = json.dumps(_canonical(fields), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(f"{prev_hash}|{body}".encode()).hexdigest()


def _hashed_fields(e: AuditEvent) -> dict[str, Any]:
    return {
        "id": e.id,
        "tenant_id": e.tenant_id,
        "seq": e.seq,
        "occurred_at": e.occurred_at,
        "actor_user_id": e.actor_user_id,
        "actor_label": e.actor_label,
        "action": e.action,
        "target_type": e.target_type,
        "target_id": e.target_id,
        "data": e.data,
        "ip": e.ip,
        "request_id": e.request_id,
    }


async def record(
    db: AsyncSession,
    action: str,
    *,
    target_type: str | None = None,
    target_id: uuid.UUID | str | None = None,
    data: dict[str, Any] | None = None,
    actor_user_id: uuid.UUID | None = None,
    actor_label: str | None = None,
) -> AuditEvent:
    """Append an audit event in the current transaction (it commits with the change)."""
    tenant_id = current_tenant(db)
    info = context.current()
    # Serialise writers per tenant so the chain has no forks. Held until commit.
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"audit:{tenant_id}"}
    )
    last = (
        await db.execute(
            select(AuditEvent.seq, AuditEvent.hash)
            .where(AuditEvent.tenant_id == tenant_id)
            .order_by(AuditEvent.seq.desc())
            .limit(1)
        )
    ).first()
    prev_seq, prev_hash = (last[0], last[1]) if last else (0, GENESIS)
    event = AuditEvent(
        id=uuid7(),
        tenant_id=tenant_id,
        seq=prev_seq + 1,
        occurred_at=datetime.now(UTC).replace(microsecond=0),
        actor_user_id=actor_user_id or info.user_id,
        actor_label=actor_label,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        data=_canonical(redact(data or {})),
        ip=info.ip,
        user_agent=(info.user_agent or "")[:300] or None,
        request_id=info.request_id or None,
        prev_hash=prev_hash,
        hash="",
    )
    event.hash = compute_hash(prev_hash, _hashed_fields(event))
    db.add(event)
    await db.flush()
    return event


async def verify_chain(db: AsyncSession) -> tuple[bool, int | None]:
    """Recompute the current tenant's chain. Returns (ok, first bad seq)."""
    tenant_id = current_tenant(db)
    prev = GENESIS
    expected_seq = 1
    rows = await db.stream_scalars(
        select(AuditEvent).where(AuditEvent.tenant_id == tenant_id).order_by(AuditEvent.seq)
    )
    async for e in rows:
        if e.seq != expected_seq or e.prev_hash != prev or compute_hash(prev, _hashed_fields(e)) != e.hash:
            return False, e.seq
        prev = e.hash
        expected_seq += 1
    return True, None
