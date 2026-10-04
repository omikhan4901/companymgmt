"""Suppliers, stock settings per item, the movement ledger, purchases, transfers, counts."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

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
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import expression

from app.core.models import Base, IdMixin, TenantScoped, TimestampMixin, Versioned

Quantity = Numeric(14, 3)
Cost = Numeric(20, 4)


class Supplier(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("tenant_id", "id"),)

    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(Text)
    tax_id: Mapped[str | None] = mapped_column(String(60))
    note: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=expression.true())


class SupplierEntry(IdMixin, TenantScoped, TimestampMixin, Base):
    """What we owe a supplier: purchases add, payments subtract."""

    __tablename__ = "supplier_entries"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "supplier_id"], ["suppliers.tenant_id", "suppliers.id"]),
        CheckConstraint("kind IN ('purchase', 'payment', 'adjustment')", name="kind"),
        Index("ix_supplier_entries_supplier", "tenant_id", "supplier_id", "occurred_on"),
    )

    supplier_id: Mapped[uuid.UUID]
    kind: Mapped[str] = mapped_column(String(12))
    amount: Mapped[int] = mapped_column(BigInteger)
    occurred_on: Mapped[date] = mapped_column(Date)
    purchase_id: Mapped[uuid.UUID | None]
    paid_from: Mapped[str | None] = mapped_column(String(12))
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class StockItem(TenantScoped, TimestampMixin, Base):
    """Stock settings and the running cost of one catalogue item (sales.products)."""

    __tablename__ = "stock_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "product_id"], ["products.tenant_id", "products.id"], ondelete="CASCADE"
        ),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    track: Mapped[bool] = mapped_column(Boolean, default=True, server_default=expression.true())
    # Alert when a branch's stock falls to this or below.
    reorder_level: Mapped[Decimal | None] = mapped_column(Quantity)
    quantity: Mapped[Decimal] = mapped_column(Quantity, default=Decimal(0))
    value: Mapped[Decimal] = mapped_column(Cost, default=Decimal(0))
    average_cost: Mapped[Decimal] = mapped_column(Cost, default=Decimal(0))


class StockLevel(IdMixin, TenantScoped, Base):
    """How many of an item are at a branch (no branch: the main store)."""

    __tablename__ = "stock_levels"
    __table_args__ = (
        UniqueConstraint("tenant_id", "product_id", "branch_key"),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"], ["products.tenant_id", "products.id"], ondelete="CASCADE"
        ),
    )

    product_id: Mapped[uuid.UUID]
    branch_id: Mapped[uuid.UUID | None]
    # branch_id, or all zeros for "no branch" (so the unique constraint works).
    branch_key: Mapped[uuid.UUID]
    quantity: Mapped[Decimal] = mapped_column(Quantity, default=Decimal(0))
    # Set while the level is at or below the reorder level, so the alert is sent once.
    low_since: Mapped[datetime | None]


class StockMovement(IdMixin, TenantScoped, TimestampMixin, Base):
    """Every change to stock, never edited. Levels and values are sums of these."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "product_id"], ["products.tenant_id", "products.id"]),
        CheckConstraint(
            "kind IN ('opening', 'purchase', 'sale', 'return', 'void', 'adjustment', 'count',"
            " 'transfer_out', 'transfer_in')",
            name="kind",
        ),
        Index("ix_stock_movements_product", "tenant_id", "product_id", "occurred_at"),
        Index("ix_stock_movements_ref", "tenant_id", "ref_type", "ref_id"),
    )

    product_id: Mapped[uuid.UUID]
    branch_id: Mapped[uuid.UUID | None]
    kind: Mapped[str] = mapped_column(String(14))
    quantity: Mapped[Decimal] = mapped_column(Quantity)
    # Cost per unit (incoming) and the cost value moved (negative when stock leaves).
    unit_cost: Mapped[Decimal] = mapped_column(Cost)
    value: Mapped[Decimal] = mapped_column(Cost)
    occurred_at: Mapped[datetime]
    ref_type: Mapped[str | None] = mapped_column(String(20))
    ref_id: Mapped[uuid.UUID | None]
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class Purchase(IdMixin, TenantScoped, TimestampMixin, Base):
    __tablename__ = "purchases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "supplier_id"], ["suppliers.tenant_id", "suppliers.id"]),
        Index("ix_purchases_day", "tenant_id", "received_on"),
    )

    supplier_id: Mapped[uuid.UUID | None]
    branch_id: Mapped[uuid.UUID | None]
    reference: Mapped[str | None] = mapped_column(String(60))
    received_on: Mapped[date] = mapped_column(Date)
    # Minor units: the goods, input tax the workspace can reclaim, and the total.
    net: Mapped[int] = mapped_column(BigInteger)
    tax: Mapped[int] = mapped_column(BigInteger, default=0)
    total: Mapped[int] = mapped_column(BigInteger)
    paid: Mapped[int] = mapped_column(BigInteger, default=0)
    paid_from: Mapped[str] = mapped_column(String(12), default="drawer")
    # [{"product_id", "name", "quantity", "unit_cost", "tax_rate_id", "tax"}]
    lines: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class Transfer(IdMixin, TenantScoped, TimestampMixin, Base):
    __tablename__ = "stock_transfers"

    from_branch_id: Mapped[uuid.UUID | None]
    to_branch_id: Mapped[uuid.UUID | None]
    lines: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class StockCount(IdMixin, TenantScoped, TimestampMixin, Base):
    __tablename__ = "stock_counts"

    branch_id: Mapped[uuid.UUID | None]
    counted_on: Mapped[date] = mapped_column(Date)
    # [{"product_id", "name", "expected", "counted", "difference", "value"}]
    lines: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    items: Mapped[int] = mapped_column(Integer, default=0)
