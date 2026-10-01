"""Announcements: posts to everyone, some branches or some departments, with read receipts."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, IdMixin, TenantScoped, TimestampMixin, Versioned


class Announcement(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "announcements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("audience IN ('everyone', 'branches', 'departments')", name="audience"),
        CheckConstraint("audience = 'everyone' OR cardinality(audience_ids) > 0", name="audience_ids"),
        Index("ix_announcements_feed", "tenant_id", "published_at"),
    )

    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(String(12), default="everyone")
    # Branch or department ids (departments include everything below them).
    audience_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid), default=list)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sql("false"))
    published_at: Mapped[datetime]
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    edited_at: Mapped[datetime | None]


class AnnouncementRead(TenantScoped, Base):
    __tablename__ = "announcement_reads"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "announcement_id"],
            ["announcements.tenant_id", "announcements.id"],
            ondelete="CASCADE",
        ),
    )

    announcement_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    read_at: Mapped[datetime]
