"""Leave: types, workspace policy, holidays, requests and balance adjustments."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, IdMixin, TenantScoped, TimestampMixin, Versioned

Days = Numeric(6, 1)


class LeavePolicy(TenantScoped, TimestampMixin, Versioned, Base):
    """One row per workspace."""

    __tablename__ = "leave_policies"
    __table_args__ = (CheckConstraint("weekly_off <@ ARRAY[1,2,3,4,5,6,7]::smallint[]", name="weekly_off"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    # ISO weekdays that are not working days (Monday=1 … Sunday=7).
    weekly_off: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), default=lambda: [6, 7])
    # Whether people see who else in their department is away (names and dates only).
    team_calendar: Mapped[bool] = mapped_column(Boolean, default=True)


class LeaveType(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "leave_types"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        Index("uq_leave_types_name", "tenant_id", func.lower(text("name")), unique=True),
        CheckConstraint("accrual IN ('yearly', 'monthly')", name="accrual"),
        CheckConstraint("days_per_year IS NULL OR days_per_year >= 0", name="days"),
        CheckConstraint("carry_over_max >= 0", name="carry"),
        CheckConstraint("color ~ '^#[0-9a-fA-F]{6}$'", name="color"),
    )

    name: Mapped[str] = mapped_column(String(80))
    paid: Mapped[bool] = mapped_column(Boolean, default=True)
    # None means no limit (e.g. unpaid leave).
    days_per_year: Mapped[Decimal | None] = mapped_column(Days)
    accrual: Mapped[str] = mapped_column(String(10), default="yearly")
    carry_over_max: Mapped[Decimal] = mapped_column(Days, default=Decimal(0))
    allow_half_day: Mapped[bool] = mapped_column(Boolean, default=True)
    # Count every calendar day (e.g. maternity leave), not only working days.
    calendar_days: Mapped[bool] = mapped_column(Boolean, default=False)
    # Someone who joins mid-year gets a share of the yearly days.
    prorate: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    color: Mapped[str] = mapped_column(String(7), default="#6d28d9")
    # Display order.
    position: Mapped[int] = mapped_column(SmallInteger, default=0)


class Holiday(IdMixin, TenantScoped, TimestampMixin, Base):
    __tablename__ = "holidays"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "branch_id"], ["branches.tenant_id", "branches.id"]),
        Index(
            "uq_holidays_day",
            "tenant_id",
            "day",
            func.coalesce(text("branch_id"), text("'00000000-0000-0000-0000-000000000000'::uuid")),
            unique=True,
        ),
    )

    day: Mapped[date] = mapped_column(Date)
    name: Mapped[str] = mapped_column(String(120))
    # None: every branch.
    branch_id: Mapped[uuid.UUID | None]


class LeaveRequest(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "leave_requests"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "employee_id"], ["employees.tenant_id", "employees.id"]),
        ForeignKeyConstraint(["tenant_id", "leave_type_id"], ["leave_types.tenant_id", "leave_types.id"]),
        CheckConstraint("end_date >= start_date", name="order"),
        CheckConstraint("half_day IN ('none', 'morning', 'afternoon')", name="half_day"),
        CheckConstraint("half_day = 'none' OR start_date = end_date", name="half_single_day"),
        CheckConstraint("days > 0", name="days"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'cancelled')", name="status"),
        # A person can't have two live requests covering the same day.
        ExcludeConstraint(
            ("tenant_id", "="),
            ("employee_id", "="),
            (text("daterange(start_date, end_date, '[]')"), "&&"),
            name="leave_no_overlap",
            using="gist",
            where=text("status IN ('pending', 'approved')"),
        ),
        Index("ix_leave_requests_status", "tenant_id", "status"),
        Index("ix_leave_requests_employee", "tenant_id", "employee_id", "start_date"),
    )

    employee_id: Mapped[uuid.UUID]
    leave_type_id: Mapped[uuid.UUID]
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    half_day: Mapped[str] = mapped_column(String(10), default="none")
    days: Mapped[Decimal] = mapped_column(Days)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="pending")
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None]
    decision_note: Mapped[str | None] = mapped_column(Text)


class LeaveAdjustment(IdMixin, TenantScoped, TimestampMixin, Base):
    """Manual changes to a balance (opening balance, correction, carry-over override)."""

    __tablename__ = "leave_adjustments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "employee_id"], ["employees.tenant_id", "employees.id"]),
        ForeignKeyConstraint(["tenant_id", "leave_type_id"], ["leave_types.tenant_id", "leave_types.id"]),
        CheckConstraint("days <> 0", name="days"),
        Index("ix_leave_adjustments_lookup", "tenant_id", "employee_id", "leave_type_id", "year"),
    )

    employee_id: Mapped[uuid.UUID]
    leave_type_id: Mapped[uuid.UUID]
    year: Mapped[int] = mapped_column(SmallInteger)
    days: Mapped[Decimal] = mapped_column(Days)
    reason: Mapped[str] = mapped_column(String(300))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
