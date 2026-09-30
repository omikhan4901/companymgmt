"""People: departments (a tree) and employees."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, IdMixin, TenantScoped, TimestampMixin, Versioned

EMPLOYMENT_TYPES = ("full_time", "part_time", "contract", "intern", "daily")
EMPLOYEE_STATUSES = ("active", "inactive", "left")


class Department(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "parent_id"], ["departments.tenant_id", "departments.id"]),
        Index(
            "uq_departments_sibling_name",
            "tenant_id",
            func.coalesce(text("parent_id"), text("'00000000-0000-0000-0000-000000000000'::uuid")),
            func.lower(text("name")),
            unique=True,
        ),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="not_own_parent"),
    )

    name: Mapped[str] = mapped_column(String(120))
    parent_id: Mapped[uuid.UUID | None]


class Employee(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "membership_id"),
        Index(
            "uq_employees_code",
            "tenant_id",
            func.lower(text("employee_code")),
            unique=True,
            postgresql_where=text("employee_code IS NOT NULL"),
        ),
        ForeignKeyConstraint(["tenant_id", "membership_id"], ["memberships.tenant_id", "memberships.id"]),
        ForeignKeyConstraint(["tenant_id", "department_id"], ["departments.tenant_id", "departments.id"]),
        ForeignKeyConstraint(["tenant_id", "branch_id"], ["branches.tenant_id", "branches.id"]),
        CheckConstraint(
            "employment_type IN ('full_time', 'part_time', 'contract', 'intern', 'daily')",
            name="employment_type",
        ),
        CheckConstraint("status IN ('active', 'inactive', 'left')", name="status"),
        CheckConstraint("left_on IS NULL OR joined_on IS NULL OR left_on >= joined_on", name="dates"),
        Index("ix_employees_tenant_name", "tenant_id", func.lower(text("full_name"))),
    )

    # Set when this person can sign in (a member of the workspace).
    membership_id: Mapped[uuid.UUID | None]
    employee_code: Mapped[str | None] = mapped_column(String(40))
    full_name: Mapped[str] = mapped_column(String(200))
    preferred_name: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(40))
    department_id: Mapped[uuid.UUID | None]
    branch_id: Mapped[uuid.UUID | None]
    job_title: Mapped[str | None] = mapped_column(String(120))
    employment_type: Mapped[str] = mapped_column(String(12), default="full_time")
    status: Mapped[str] = mapped_column(String(10), default="active")
    joined_on: Mapped[date | None] = mapped_column(Date)
    left_on: Mapped[date | None] = mapped_column(Date)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    # National ID number, encrypted (AES-GCM, bound to this employee's id).
    national_id_enc: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)
