"""Customers and their running account (every sale on credit, payment and adjustment)."""

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
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import expression

from app.core.models import Base, IdMixin, TenantScoped, TimestampMixin, Versioned


class Customer(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        Index("ix_customers_name", "tenant_id", "name"),
        Index("ix_customers_phone", "tenant_id", "phone"),
    )

    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    # The most they may owe (minor units); None: no limit.
    credit_limit: Mapped[int | None] = mapped_column(BigInteger)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=expression.true())


class CustomerEntry(IdMixin, TenantScoped, TimestampMixin, Base):
    """One line in a customer's account. Positive amounts add to what they owe."""

    __tablename__ = "customer_entries"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "customer_id"], ["customers.tenant_id", "customers.id"]),
        CheckConstraint("kind IN ('sale', 'return', 'payment', 'adjustment')", name="kind"),
        Index("ix_customer_entries_customer", "tenant_id", "customer_id", "occurred_on"),
    )

    customer_id: Mapped[uuid.UUID]
    kind: Mapped[str] = mapped_column(String(12))
    amount: Mapped[int] = mapped_column(BigInteger)
    occurred_on: Mapped[date] = mapped_column(Date)
    sale_id: Mapped[uuid.UUID | None]
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
