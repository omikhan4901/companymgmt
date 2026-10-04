"""An automation and the record of each time it ran."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import expression

from app.core.models import Base, IdMixin, TenantScoped, TimestampMixin, Versioned


class Automation(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "automations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "owner_membership_id"],
            ["memberships.tenant_id", "memberships.id"],
            ondelete="CASCADE",
        ),
        Index("ix_automations_due", "tenant_id", "enabled", "next_run_at"),
    )

    name: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=expression.false())
    # {"type": "schedule", "every": "week", "weekday": 1, "time": "09:00"} or
    # {"type": "event", "event": "leave.requested"}; checked by schemas.Trigger.
    trigger: Mapped[dict[str, Any]] = mapped_column(JSONB)
    conditions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    actions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # It runs as this person, with their permissions at the time it runs.
    owner_membership_id: Mapped[uuid.UUID]
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # Whether the assistant drafted it (shown in the editor and the audit log).
    drafted_by_ai: Mapped[bool] = mapped_column(Boolean, default=False, server_default=expression.false())
    next_run_at: Mapped[datetime | None]
    last_run_at: Mapped[datetime | None]
    # Set when the engine pauses it (too many runs, its owner left…).
    paused_reason: Mapped[str | None] = mapped_column(String(200))


class AutomationRun(IdMixin, TenantScoped, TimestampMixin, Base):
    __tablename__ = "automation_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "automation_id"], ["automations.tenant_id", "automations.id"], ondelete="CASCADE"
        ),
        CheckConstraint("status IN ('ok', 'skipped', 'failed', 'limited')", name="status"),
        Index("ix_automation_runs_recent", "tenant_id", "automation_id", "created_at"),
    )

    automation_id: Mapped[uuid.UUID]
    status: Mapped[str] = mapped_column(String(10))
    # "schedule", "manual" or the event name.
    cause: Mapped[str] = mapped_column(String(80))
    event_id: Mapped[uuid.UUID | None]
    # What it did: [{"action": "notify", "count": 4}, {"action": "create_task", "task_id": …}]
    detail: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    error: Mapped[str | None] = mapped_column(Text)
