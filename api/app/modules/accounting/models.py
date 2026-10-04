"""Accounts, journal entries and lines, settings, and tax-return templates."""

from __future__ import annotations

import uuid
from datetime import date
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
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import expression

from app.core.models import Base, IdMixin, TenantScoped, TimestampMixin, Versioned

TYPES = ("asset", "liability", "equity", "income", "expense")


class Account(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "code"),
        # A role the automatic postings look for ("cash", "sales", "tax_payable"…).
        Index(
            "uq_accounts_role",
            "tenant_id",
            "role",
            unique=True,
            postgresql_where=expression.text("role IS NOT NULL"),
        ),
        CheckConstraint("type IN ('asset', 'liability', 'equity', 'income', 'expense')", name="type"),
    )

    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(10))
    role: Mapped[str | None] = mapped_column(String(30))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=expression.true())
    description: Mapped[str | None] = mapped_column(Text)


class AccountingSettings(TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "accounting_settings"

    tenant_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    # Nothing can be posted on or before this date.
    locked_until: Mapped[date | None] = mapped_column(Date)
    # Where each tax rate's tax goes, on sales (output) and purchases (input):
    # {tax_rate_id: {"output": account_id, "input": account_id}}.
    tax_accounts: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Where each expense category goes: {category_id: account_id}.
    expense_accounts: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    next_number: Mapped[int] = mapped_column(BigInteger, default=1)


class JournalEntry(IdMixin, TenantScoped, TimestampMixin, Base):
    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "number"),
        # An automatic posting is made once per thing and reason (safe to backfill again).
        Index(
            "uq_journal_source",
            "tenant_id",
            "source_type",
            "source_id",
            "reason",
            unique=True,
            postgresql_where=expression.text("source_id IS NOT NULL"),
        ),
        Index("ix_journal_date", "tenant_id", "entry_date"),
    )

    number: Mapped[int] = mapped_column(BigInteger)
    entry_date: Mapped[date] = mapped_column(Date)
    memo: Mapped[str] = mapped_column(String(300))
    # "sale", "expense", "payroll_run"… or None for entries typed by hand.
    source_type: Mapped[str | None] = mapped_column(String(30))
    source_id: Mapped[uuid.UUID | None]
    # Distinguishes postings for the same thing ("post", "void", "cogs", "reverse:<id>").
    reason: Mapped[str] = mapped_column(String(60), default="post")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    # Set on an entry that a later one reverses.
    reversed_by: Mapped[uuid.UUID | None]


class JournalLine(IdMixin, TenantScoped, Base):
    __tablename__ = "journal_lines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "entry_id"], ["journal_entries.tenant_id", "journal_entries.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["tenant_id", "account_id"], ["accounts.tenant_id", "accounts.id"]),
        CheckConstraint("debit >= 0 AND credit >= 0 AND (debit = 0 OR credit = 0)", name="one_side"),
        Index("ix_journal_lines_account", "tenant_id", "account_id"),
        Index("ix_journal_lines_entry", "tenant_id", "entry_id"),
    )

    entry_id: Mapped[uuid.UUID]
    account_id: Mapped[uuid.UUID]
    debit: Mapped[int] = mapped_column(BigInteger, default=0)
    credit: Mapped[int] = mapped_column(BigInteger, default=0)
    description: Mapped[str | None] = mapped_column(String(300))
    # For tax lines: which rate and the amount it was charged on (tax returns read these).
    tax_rate_id: Mapped[uuid.UUID | None]
    tax_base: Mapped[int | None] = mapped_column(BigInteger)
    position: Mapped[int] = mapped_column(Integer, default=0)


class TaxReturnTemplate(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    """A return the workspace's accountant laid out: boxes and what goes in each."""

    __tablename__ = "tax_return_templates"

    name: Mapped[str] = mapped_column(String(120))
    # [{"code": "1", "label": "Standard-rated sales", "sources": [{"kind": "tax_base",
    #   "ids": [tax_rate_id], "side": "output", "sign": 1}]}]
    boxes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    note: Mapped[str | None] = mapped_column(Text)
