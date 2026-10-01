"""Payroll: settings, salary structures, loans and advances, runs and payslips.

Money is stored in minor units (paisa, cents) as integers, so sums are exact.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, IdMixin, TenantScoped, TimestampMixin, Versioned

PAY_RULES = ("monthly", "hourly", "daily")
PAYMENT_METHODS = ("cash", "bank", "wallet")
RUN_STATUSES = ("draft", "review", "finalized", "paid")
Money = BigInteger


class PayrollSettings(TenantScoped, TimestampMixin, Versioned, Base):
    """One row per workspace."""

    __tablename__ = "payroll_settings"
    __table_args__ = (
        CheckConstraint("day_basis IN ('calendar', 'thirty')", name="day_basis"),
        CheckConstraint("hours_per_day BETWEEN 1 AND 16", name="hours"),
        CheckConstraint("overtime_multiplier BETWEEN 1 AND 5", name="ot_multiplier"),
        CheckConstraint("overtime_divisor BETWEEN 1 AND 400", name="ot_divisor"),
        CheckConstraint("bonus_percent BETWEEN 0 AND 500", name="bonus_percent"),
        CheckConstraint("bonus_min_months BETWEEN 0 AND 60", name="bonus_months"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    # How a month's salary is split into days: the month's calendar days, or always 30.
    day_basis: Mapped[str] = mapped_column(String(10), default="calendar")
    hours_per_day: Mapped[int] = mapped_column(SmallInteger, default=8)
    # Overtime pays basic / divisor per hour, times the multiplier (Bangladesh: basic / 208, times 2).
    overtime_multiplier: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal(2))
    overtime_divisor: Mapped[int] = mapped_column(SmallInteger, default=208)
    # Festival bonus: a share of basic, after a minimum length of service.
    bonus_percent: Mapped[int] = mapped_column(SmallInteger, default=100)
    bonus_min_months: Mapped[int] = mapped_column(SmallInteger, default=12)
    round_net: Mapped[bool] = mapped_column(Boolean, default=True)
    # Tax deducted at source. Off until the owner checks the table and turns it on.
    tax_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    tax_table: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class SalaryStructure(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    """A person's pay from `effective_from` until the next structure starts."""

    __tablename__ = "salary_structures"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "employee_id", "effective_from"),
        ForeignKeyConstraint(["tenant_id", "employee_id"], ["employees.tenant_id", "employees.id"]),
        CheckConstraint("pay_rule IN ('monthly', 'hourly', 'daily')", name="pay_rule"),
        CheckConstraint("payment_method IN ('cash', 'bank', 'wallet')", name="payment_method"),
        CheckConstraint(
            "basic >= 0 AND house_rent >= 0 AND medical >= 0 AND conveyance >= 0 AND other >= 0"
            " AND rate >= 0",
            name="amounts",
        ),
    )

    employee_id: Mapped[uuid.UUID]
    effective_from: Mapped[date] = mapped_column(Date)
    pay_rule: Mapped[str] = mapped_column(String(10), default="monthly")
    # Monthly amounts (minor units).
    basic: Mapped[int] = mapped_column(Money, default=0)
    house_rent: Mapped[int] = mapped_column(Money, default=0)
    medical: Mapped[int] = mapped_column(Money, default=0)
    conveyance: Mapped[int] = mapped_column(Money, default=0)
    other: Mapped[int] = mapped_column(Money, default=0)
    # Hourly or daily rate for those pay rules (minor units).
    rate: Mapped[int] = mapped_column(Money, default=0)
    overtime: Mapped[bool] = mapped_column(Boolean, default=False)
    deduct_tax: Mapped[bool] = mapped_column(Boolean, default=True)
    # A higher tax-free amount (e.g. women and people over 65), else the table's.
    tax_free_override: Mapped[int | None] = mapped_column(Money)
    payment_method: Mapped[str] = mapped_column(String(8), default="cash")
    # Bank name or wallet provider (e.g. bKash), and the account number, encrypted.
    provider: Mapped[str | None] = mapped_column(String(80))
    account_enc: Mapped[str | None] = mapped_column(String(300))
    account_last4: Mapped[str | None] = mapped_column(String(4))
    note: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class Loan(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    """An advance or loan repaid in monthly installments from payslips."""

    __tablename__ = "payroll_loans"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "employee_id"], ["employees.tenant_id", "employees.id"]),
        CheckConstraint("kind IN ('advance', 'loan')", name="kind"),
        CheckConstraint("principal > 0 AND installment > 0", name="positive"),
        CheckConstraint("outstanding >= 0 AND outstanding <= principal", name="outstanding"),
        CheckConstraint("status IN ('active', 'closed')", name="status"),
        Index("ix_payroll_loans_employee", "tenant_id", "employee_id", "status"),
    )

    employee_id: Mapped[uuid.UUID]
    kind: Mapped[str] = mapped_column(String(8), default="advance")
    label: Mapped[str] = mapped_column(String(120))
    principal: Mapped[int] = mapped_column(Money)
    installment: Mapped[int] = mapped_column(Money)
    outstanding: Mapped[int] = mapped_column(Money)
    # First month to deduct from (YYYY-MM).
    start_period: Mapped[str] = mapped_column(String(7))
    status: Mapped[str] = mapped_column(String(8), default="active")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class PayrollRun(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "payroll_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "period"),
        CheckConstraint("period ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'", name="period"),
        CheckConstraint("status IN ('draft', 'review', 'finalized', 'paid')", name="status"),
    )

    period: Mapped[str] = mapped_column(String(7))
    status: Mapped[str] = mapped_column(String(10), default="draft")
    # Set when this month's pay includes a festival bonus (e.g. "Eid-ul-Fitr bonus").
    bonus_label: Mapped[str | None] = mapped_column(String(80))
    currency: Mapped[str] = mapped_column(String(3))
    headcount: Mapped[int] = mapped_column(Integer, default=0)
    gross: Mapped[int] = mapped_column(Money, default=0)
    deductions: Mapped[int] = mapped_column(Money, default=0)
    net: Mapped[int] = mapped_column(Money, default=0)
    computed_at: Mapped[datetime | None]
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None]
    finalized_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    finalized_at: Mapped[datetime | None]
    paid_at: Mapped[datetime | None]


class Payslip(IdMixin, TenantScoped, TimestampMixin, Base):
    """One person's pay for one run. A snapshot: later edits to people or salaries don't
    change it."""

    __tablename__ = "payslips"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "run_id", "employee_id"),
        ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["payroll_runs.tenant_id", "payroll_runs.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["tenant_id", "employee_id"], ["employees.tenant_id", "employees.id"]),
        CheckConstraint(
            "net >= 0 AND gross >= 0 AND deductions >= 0 AND carried_forward >= 0", name="amounts"
        ),
        CheckConstraint("net = GREATEST(gross - deductions, 0)", name="net"),
        Index("ix_payslips_employee", "tenant_id", "employee_id"),
    )

    run_id: Mapped[uuid.UUID]
    employee_id: Mapped[uuid.UUID]
    employee_name: Mapped[str] = mapped_column(String(200))
    employee_code: Mapped[str | None] = mapped_column(String(40))
    department_id: Mapped[uuid.UUID | None]
    department_name: Mapped[str | None] = mapped_column(String(120))
    job_title: Mapped[str | None] = mapped_column(String(120))
    pay_rule: Mapped[str] = mapped_column(String(10))
    structure_id: Mapped[uuid.UUID | None]
    days_in_period: Mapped[int] = mapped_column(SmallInteger)
    payable_days: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    unpaid_leave_days: Mapped[Decimal] = mapped_column(Numeric(6, 1), default=Decimal(0))
    worked_minutes: Mapped[int] = mapped_column(Integer, default=0)
    overtime_minutes: Mapped[int] = mapped_column(Integer, default=0)
    # [{"code", "label", "kind": "earning" | "deduction", "amount", "ref"?}]
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    gross: Mapped[int] = mapped_column(Money, default=0)
    deductions: Mapped[int] = mapped_column(Money, default=0)
    net: Mapped[int] = mapped_column(Money, default=0)
    # Deductions that didn't fit this month; becomes an advance repaid next month.
    carried_forward: Mapped[int] = mapped_column(Money, default=0)
    payment_method: Mapped[str] = mapped_column(String(8), default="cash")
    provider: Mapped[str | None] = mapped_column(String(80))
    account_last4: Mapped[str | None] = mapped_column(String(4))


class PayItem(IdMixin, TenantScoped, TimestampMixin, Base):
    """A one-off earning or deduction added to a draft run (e.g. a sales commission)."""

    __tablename__ = "payroll_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["payroll_runs.tenant_id", "payroll_runs.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["tenant_id", "employee_id"], ["employees.tenant_id", "employees.id"]),
        CheckConstraint("kind IN ('earning', 'deduction')", name="kind"),
        CheckConstraint("amount > 0", name="amount"),
        Index("ix_payroll_items_run", "tenant_id", "run_id"),
    )

    run_id: Mapped[uuid.UUID]
    employee_id: Mapped[uuid.UUID]
    kind: Mapped[str] = mapped_column(String(10))
    label: Mapped[str] = mapped_column(String(120))
    amount: Mapped[int] = mapped_column(Money)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
