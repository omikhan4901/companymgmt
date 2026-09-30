"""Attendance: clock-in/out records and correction requests."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, IdMixin, TenantScoped, TimestampMixin, Versioned

# Longest shift we accept in one record.
MAX_SHIFT_HOURS = 24

LOCATION_MODES = ("off", "record", "require")
# Result of the location check at clock-in or clock-out:
# inside/outside the branch area, no_fix = no usable location was sent,
# no_site = no branch has a location set, so there was nothing to compare with.
GEO_RESULTS = ("inside", "outside", "no_fix", "no_site")


class AttendanceSettings(TenantScoped, TimestampMixin, Versioned, Base):
    """One row per workspace (created on first change; defaults apply until then)."""

    __tablename__ = "attendance_settings"
    __table_args__ = (
        CheckConstraint("location_mode IN ('off', 'record', 'require')", name="location_mode"),
        CheckConstraint("max_accuracy_m BETWEEN 10 AND 1000", name="max_accuracy"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    # off: no location; record: save it and flag entries outside; require: clock-in only
    # inside a branch area.
    location_mode: Mapped[str] = mapped_column(String(10), default="require")
    # Fixes less precise than this (metres) don't count as "inside" when location is required.
    max_accuracy_m: Mapped[int] = mapped_column(Integer, default=100)


class AttendanceRecord(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "employee_id"], ["employees.tenant_id", "employees.id"]),
        ForeignKeyConstraint(["tenant_id", "branch_id"], ["branches.tenant_id", "branches.id"]),
        # One open shift per person at a time.
        Index(
            "uq_attendance_open",
            "tenant_id",
            "employee_id",
            unique=True,
            postgresql_where=text("clock_out_at IS NULL"),
        ),
        # Shifts of the same person never overlap.
        ExcludeConstraint(
            ("tenant_id", "="),
            ("employee_id", "="),
            (text("tstzrange(clock_in_at, coalesce(clock_out_at, 'infinity'), '[)')"), "&&"),
            name="no_overlap",
            using="gist",
        ),
        CheckConstraint("clock_out_at IS NULL OR clock_out_at > clock_in_at", name="order"),
        CheckConstraint(
            f"clock_out_at IS NULL OR clock_out_at - clock_in_at <= interval '{MAX_SHIFT_HOURS} hours'",
            name="max_length",
        ),
        CheckConstraint("status IN ('open', 'closed', 'auto_closed')", name="status"),
        CheckConstraint("source IN ('self', 'kiosk', 'manual', 'correction')", name="source"),
        CheckConstraint(
            "in_geo IS NULL OR in_geo IN ('inside', 'outside', 'no_fix', 'no_site')", name="in_geo"
        ),
        CheckConstraint(
            "out_geo IS NULL OR out_geo IN ('inside', 'outside', 'no_fix', 'no_site')", name="out_geo"
        ),
        Index("ix_attendance_date", "tenant_id", "business_date"),
        Index("ix_attendance_employee_date", "tenant_id", "employee_id", "business_date"),
    )

    employee_id: Mapped[uuid.UUID]
    branch_id: Mapped[uuid.UUID | None]
    # The day this shift belongs to, in the branch's timezone, fixed at clock-in. An overnight
    # shift belongs to the day it started.
    business_date: Mapped[date] = mapped_column(Date)
    clock_in_at: Mapped[datetime]
    clock_out_at: Mapped[datetime | None]
    minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default="open")
    source: Mapped[str] = mapped_column(String(12), default="self")
    note: Mapped[str | None] = mapped_column(String(500))
    # Device time the client reported, kept to spot clock skew. Never used for pay.
    client_time: Mapped[datetime | None]
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    # Location at clock-in and clock-out, rounded to ~11 m, with the distance from the
    # branch and the check's result. Only kept for these two moments, never tracked.
    in_latitude: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    in_longitude: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    in_accuracy_m: Mapped[int | None] = mapped_column(Integer)
    in_distance_m: Mapped[int | None] = mapped_column(Integer)
    in_geo: Mapped[str | None] = mapped_column(String(8))
    out_latitude: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    out_longitude: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    out_accuracy_m: Mapped[int | None] = mapped_column(Integer)
    out_distance_m: Mapped[int | None] = mapped_column(Integer)
    out_geo: Mapped[str | None] = mapped_column(String(8))


class AttendanceCorrection(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "attendance_corrections"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "employee_id"], ["employees.tenant_id", "employees.id"]),
        ForeignKeyConstraint(
            ["tenant_id", "record_id"],
            ["attendance_records.tenant_id", "attendance_records.id"],
            ondelete="SET NULL",
        ),
        CheckConstraint("kind IN ('add', 'change', 'remove')", name="kind"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'cancelled')", name="status"),
        CheckConstraint(
            "proposed_clock_out_at IS NULL OR proposed_clock_out_at > proposed_clock_in_at",
            name="order",
        ),
        Index("ix_corrections_status", "tenant_id", "status"),
    )

    employee_id: Mapped[uuid.UUID]
    record_id: Mapped[uuid.UUID | None]
    kind: Mapped[str] = mapped_column(String(10))
    proposed_clock_in_at: Mapped[datetime | None]
    proposed_clock_out_at: Mapped[datetime | None]
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(10), default="pending")
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None]
    decision_note: Mapped[str | None] = mapped_column(Text)
