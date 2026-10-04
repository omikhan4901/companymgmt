"""Catalogue, taxes, cash drawer sessions, sales and their lines."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import expression

from app.core.models import Base, IdMixin, TenantScoped, TimestampMixin, Versioned

Money = BigInteger
Quantity = Numeric(12, 3)
Percent = Numeric(7, 4)


class ShopSettings(TenantScoped, TimestampMixin, Versioned, Base):
    """One row per workspace: how prices and receipts work. Nothing here is guessed for a
    country; the workspace's own accountant sets it."""

    __tablename__ = "shop_settings"

    tenant_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    prices_include_tax: Mapped[bool] = mapped_column(Boolean, default=True, server_default=expression.true())
    # Round cash totals to this many minor units (1 = no rounding, 100 = whole taka).
    cash_rounding: Mapped[int] = mapped_column(Integer, default=1)
    # Printed on receipts: e.g. "BIN" / "VAT reg. no." and its value.
    tax_id_label: Mapped[str | None] = mapped_column(String(40))
    tax_id: Mapped[str | None] = mapped_column(String(60))
    receipt_header: Mapped[str | None] = mapped_column(Text)
    receipt_footer: Mapped[str | None] = mapped_column(Text)
    # The next sale number (receipts count up from 1 in each workspace).
    next_number: Mapped[int] = mapped_column(BigInteger, default=1)


class TaxRate(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "tax_rates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("percent >= 0 AND percent <= 100", name="percent"),
    )

    name: Mapped[str] = mapped_column(String(60))
    # Short code the accountant uses in returns (e.g. "VAT15", "SD").
    code: Mapped[str | None] = mapped_column(String(20))
    percent: Mapped[Decimal] = mapped_column(Percent)
    # Charged on the price plus the taxes before it.
    compound: Mapped[bool] = mapped_column(Boolean, default=False, server_default=expression.false())
    position: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=expression.true())
    # Applied to new products unless chosen otherwise.
    default: Mapped[bool] = mapped_column(Boolean, default=False, server_default=expression.false())


class ProductCategory(IdMixin, TenantScoped, TimestampMixin, Base):
    __tablename__ = "product_categories"
    __table_args__ = (UniqueConstraint("tenant_id", "id"),)

    name: Mapped[str] = mapped_column(String(80))
    color: Mapped[str] = mapped_column(String(7), default="#0f766e")
    position: Mapped[int] = mapped_column(Integer, default=0)


class Product(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "category_id"], ["product_categories.tenant_id", "product_categories.id"]
        ),
        Index("ix_products_name", "tenant_id", "name"),
        CheckConstraint("price >= 0", name="price"),
    )

    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str | None] = mapped_column(String(40))
    category_id: Mapped[uuid.UUID | None]
    # Minor units, including or excluding tax per the shop settings.
    price: Mapped[int] = mapped_column(Money)
    tax_rate_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid), default=list)
    # Sold by weight or length ("kg", "m") lets quantities have decimals.
    unit: Mapped[str] = mapped_column(String(10), default="pcs")
    favorite: Mapped[bool] = mapped_column(Boolean, default=False, server_default=expression.false())
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=expression.true())
    position: Mapped[int] = mapped_column(Integer, default=0)


class CashSession(IdMixin, TenantScoped, TimestampMixin, Base):
    """A cash drawer from opening to closing (one shift at one till)."""

    __tablename__ = "cash_sessions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        Index(
            "uq_cash_sessions_open",
            "tenant_id",
            "opened_by",
            unique=True,
            postgresql_where=expression.text("closed_at IS NULL"),
        ),
    )

    branch_id: Mapped[uuid.UUID | None]
    opened_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    opened_at: Mapped[datetime]
    opening_float: Mapped[int] = mapped_column(Money, default=0)
    closed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None]
    # What should be in the drawer, and what was counted, when it closed.
    expected_cash: Mapped[int | None] = mapped_column(Money)
    counted_cash: Mapped[int | None] = mapped_column(Money)
    note: Mapped[str | None] = mapped_column(Text)


class Sale(IdMixin, TenantScoped, TimestampMixin, Base):
    __tablename__ = "sales"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "number"),
        # The till's own id for the sale: sending it twice (offline retry) records it once.
        UniqueConstraint("tenant_id", "client_id"),
        ForeignKeyConstraint(["tenant_id", "session_id"], ["cash_sessions.tenant_id", "cash_sessions.id"]),
        ForeignKeyConstraint(["tenant_id", "original_id"], ["sales.tenant_id", "sales.id"]),
        CheckConstraint("kind IN ('sale', 'return')", name="kind"),
        CheckConstraint("status IN ('completed', 'voided')", name="status"),
        Index("ix_sales_time", "tenant_id", "sold_at"),
    )

    number: Mapped[int] = mapped_column(BigInteger)
    client_id: Mapped[uuid.UUID]
    kind: Mapped[str] = mapped_column(String(10), default="sale")
    status: Mapped[str] = mapped_column(String(10), default="completed")
    original_id: Mapped[uuid.UUID | None]
    session_id: Mapped[uuid.UUID | None]
    branch_id: Mapped[uuid.UUID | None]
    sold_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    sold_at: Mapped[datetime]
    customer_id: Mapped[uuid.UUID | None]
    # All in minor units; negative on returns.
    net: Mapped[int] = mapped_column(Money)
    tax: Mapped[int] = mapped_column(Money)
    rounding: Mapped[int] = mapped_column(Money, default=0)
    total: Mapped[int] = mapped_column(Money)
    paid_cash: Mapped[int] = mapped_column(Money, default=0)
    change: Mapped[int] = mapped_column(Money, default=0)
    # Put on the customer's account (credit sale).
    on_account: Mapped[int] = mapped_column(Money, default=0)
    prices_include_tax: Mapped[bool] = mapped_column(Boolean)
    note: Mapped[str | None] = mapped_column(Text)
    voided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    voided_at: Mapped[datetime | None]
    void_reason: Mapped[str | None] = mapped_column(Text)


class SaleLine(IdMixin, TenantScoped, Base):
    __tablename__ = "sale_lines"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "sale_id"], ["sales.tenant_id", "sales.id"], ondelete="CASCADE"),
        Index("ix_sale_lines_sale", "tenant_id", "sale_id"),
    )

    sale_id: Mapped[uuid.UUID]
    position: Mapped[int] = mapped_column(Integer)
    product_id: Mapped[uuid.UUID | None]
    name: Mapped[str] = mapped_column(String(120))
    quantity: Mapped[Decimal] = mapped_column(Quantity)
    unit_price: Mapped[int] = mapped_column(Money)
    discount: Mapped[int] = mapped_column(Money, default=0)
    net: Mapped[int] = mapped_column(Money)
    tax: Mapped[int] = mapped_column(Money)
    total: Mapped[int] = mapped_column(Money)
    # [{"id": …, "name": "VAT", "code": "VAT15", "percent": "15", "amount": 130}]
    taxes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # For returns: the line returned.
    returned_line_id: Mapped[uuid.UUID | None]
