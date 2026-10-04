"""Expense categories and expenses (including petty cash top-ups)."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, deferred, mapped_column
from sqlalchemy.sql import expression

from app.core.models import Base, IdMixin, TenantScoped, TimestampMixin, Versioned


class ExpenseCategory(IdMixin, TenantScoped, TimestampMixin, Base):
    __tablename__ = "expense_categories"
    __table_args__ = (UniqueConstraint("tenant_id", "id"),)

    name: Mapped[str] = mapped_column(String(80))
    # A code the accountant maps to the books (M9), e.g. "6100".
    code: Mapped[str | None] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=expression.true())
    position: Mapped[int] = mapped_column(Integer, default=0)


class Expense(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "expenses"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "category_id"], ["expense_categories.tenant_id", "expense_categories.id"]
        ),
        CheckConstraint("kind IN ('expense', 'top_up')", name="kind"),
        CheckConstraint("paid_from IN ('drawer', 'petty_cash', 'bank', 'other')", name="paid_from"),
        CheckConstraint("amount > 0", name="amount"),
        Index("ix_expenses_day", "tenant_id", "occurred_on"),
    )

    # "top_up": money put into petty cash (not spending).
    kind: Mapped[str] = mapped_column(String(10), default="expense")
    occurred_on: Mapped[date] = mapped_column(Date)
    amount: Mapped[int] = mapped_column(BigInteger)
    category_id: Mapped[uuid.UUID | None]
    payee: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    # "drawer": taken from the till's cash (counts against the drawer when it closes).
    paid_from: Mapped[str] = mapped_column(String(12), default="petty_cash")
    branch_id: Mapped[uuid.UUID | None]
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    receipt_name: Mapped[str | None] = mapped_column(String(200))
    receipt_type: Mapped[str | None] = mapped_column(String(100))
    receipt: Mapped[bytes | None] = deferred(mapped_column(LargeBinary))
