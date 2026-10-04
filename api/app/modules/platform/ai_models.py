"""What the assistant keeps: each workspace's AI settings, usage, and conversations."""

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
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import expression

from app.core.models import Base, IdMixin, TenantScoped, TimestampMixin, Versioned


class AIAllowance(Base):
    """Questions a month per plan, set by platform operators (global, not per tenant)."""

    __tablename__ = "ai_allowances"

    plan_key: Mapped[str] = mapped_column(String(40), ForeignKey("plans.key"), primary_key=True)
    # None: no limit. 0: no AI on this plan.
    questions_per_month: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime | None]
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class AISettings(TenantScoped, TimestampMixin, Versioned, Base):
    """One row per workspace; AI stays off until an owner switches it on."""

    __tablename__ = "ai_settings"

    tenant_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=expression.false())
    terms_accepted_at: Mapped[datetime | None]
    terms_accepted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    # Features the workspace's admins ticked for AI help (M7); empty until they choose.
    features: Mapped[list[str]] = mapped_column(JSONB, default=list)


class AIUsage(IdMixin, TenantScoped, TimestampMixin, Base):
    """One row per question (or brief); what allowances count, and what cost reports read."""

    __tablename__ = "ai_usage"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "membership_id"], ["memberships.tenant_id", "memberships.id"], ondelete="CASCADE"
        ),
        Index("ix_ai_usage_month", "tenant_id", "created_at"),
    )

    membership_id: Mapped[uuid.UUID]
    kind: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(80))
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)


class Conversation(IdMixin, TenantScoped, TimestampMixin, Base):
    """A person's chat with the assistant. Only they can see it."""

    __tablename__ = "ai_conversations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "membership_id"], ["memberships.tenant_id", "memberships.id"], ondelete="CASCADE"
        ),
        Index("ix_ai_conversations_member", "tenant_id", "membership_id"),
    )

    membership_id: Mapped[uuid.UUID]
    title: Mapped[str] = mapped_column(String(200))


class Message(IdMixin, TenantScoped, TimestampMixin, Base):
    __tablename__ = "ai_messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "conversation_id"],
            ["ai_conversations.tenant_id", "ai_conversations.id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("role IN ('user', 'assistant')", name="role"),
        Index("ix_ai_messages_conversation", "tenant_id", "conversation_id"),
    )

    conversation_id: Mapped[uuid.UUID]
    role: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    # [{"n": 1, "capability": "leave.balances", "label": "...", "link": "/app/leave"}]
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)


class Proposal(IdMixin, TenantScoped, TimestampMixin, Base):
    """Something the assistant offered to do. Nothing changes until the person who asked
    confirms it, as themselves, with their permissions at that moment."""

    __tablename__ = "ai_proposals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "membership_id"], ["memberships.tenant_id", "memberships.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "conversation_id"],
            ["ai_conversations.tenant_id", "ai_conversations.id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("status IN ('pending', 'done', 'cancelled', 'failed')", name="status"),
        Index("ix_ai_proposals_member", "tenant_id", "membership_id", "status"),
    )

    membership_id: Mapped[uuid.UUID]
    conversation_id: Mapped[uuid.UUID | None]
    # The assistant message that offered it (set once the answer is saved).
    message_id: Mapped[uuid.UUID | None]
    capability: Mapped[str] = mapped_column(String(80))
    args: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # What the person sees before confirming: [{"label": "Title", "value": "…"}]
    preview: Mapped[list[dict[str, str]]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(10), default="pending")
    expires_at: Mapped[datetime]
    decided_at: Mapped[datetime | None]
    error: Mapped[str | None] = mapped_column(Text)
    # Where to see the result, e.g. "/app/tasks?task=…".
    link: Mapped[str | None] = mapped_column(String(300))
