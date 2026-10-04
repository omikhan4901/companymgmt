"""Reports people asked to get by email."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, IdMixin, TenantScoped, TimestampMixin


class ReportSubscription(IdMixin, TenantScoped, TimestampMixin, Base):
    """One member's overview report, emailed every week or every month."""

    __tablename__ = "report_subscriptions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "membership_id", "frequency"),
        ForeignKeyConstraint(
            ["tenant_id", "membership_id"], ["memberships.tenant_id", "memberships.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "department_id"], ["departments.tenant_id", "departments.id"], ondelete="CASCADE"
        ),
        CheckConstraint("frequency IN ('weekly', 'monthly')", name="frequency"),
    )

    membership_id: Mapped[uuid.UUID]
    frequency: Mapped[str] = mapped_column(String(10))
    # None: everything the member can see.
    department_id: Mapped[uuid.UUID | None]
    last_sent_on: Mapped[date | None] = mapped_column(Date)


class SignalDismissal(IdMixin, TenantScoped, TimestampMixin, Base):
    """Someone dismissed a signal; it stays hidden for them until `until`."""

    __tablename__ = "signal_dismissals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "membership_id", "key"),
        ForeignKeyConstraint(
            ["tenant_id", "membership_id"], ["memberships.tenant_id", "memberships.id"], ondelete="CASCADE"
        ),
    )

    membership_id: Mapped[uuid.UUID]
    key: Mapped[str] = mapped_column(String(200))
    until: Mapped[date] = mapped_column(Date)
