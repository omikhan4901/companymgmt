"""In-app notifications: one row per person per thing they should know about."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import uuid7
from app.core.models import Base, TenantScoped


class Notification(TenantScoped, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_inbox", "tenant_id", "user_id", "created_at"),
        Index(
            "ix_notifications_unread",
            "tenant_id",
            "user_id",
            postgresql_where=text("read_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    # The domain event it came from ("leave.approved"); the web app words it from this.
    kind: Mapped[str] = mapped_column(String(80))
    event_id: Mapped[uuid.UUID | None]
    actor_name: Mapped[str | None] = mapped_column(String(120))
    subject_type: Mapped[str | None] = mapped_column(String(40))
    subject_id: Mapped[str | None] = mapped_column(String(64))
    # Where it leads in the app, e.g. "/app/leave".
    link: Mapped[str | None] = mapped_column(String(200))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime]
    read_at: Mapped[datetime | None]
    emailed_at: Mapped[datetime | None]
