"""Inventory over the API. Quantities are decimals (kg, m); money in minor units."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.core.schema import In, Name

Qty = Annotated[Decimal, Field(gt=0, le=10**9, max_digits=14, decimal_places=3)]
SignedQty = Annotated[Decimal, Field(ge=-(10**9), le=10**9, max_digits=14, decimal_places=3)]
Cost = Annotated[Decimal, Field(ge=0, le=10**12, max_digits=20, decimal_places=4)]
Amount = Annotated[int, Field(ge=0, le=10**13)]
PaidFrom = Literal["drawer", "petty_cash", "bank", "other"]


class SupplierIn(In):
    name: Name
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=1000)
    tax_id: str | None = Field(default=None, max_length=60)
    note: str | None = Field(default=None, max_length=2000)
    active: bool = True


class SupplierOut(BaseModel):
    id: uuid.UUID
    name: str
    phone: str | None
    address: str | None
    tax_id: str | None
    note: str | None
    active: bool
    # What we owe them now.
    balance: int
    version: int


class SupplierPaymentIn(In):
    amount: Annotated[int, Field(gt=0, le=10**13)]
    paid_from: PaidFrom = "bank"
    occurred_on: date | None = None
    note: str | None = Field(default=None, max_length=500)


class ItemSettingsIn(In):
    track: bool = True
    reorder_level: SignedQty | None = None


class LevelOut(BaseModel):
    branch_id: uuid.UUID | None
    quantity: Decimal
    low: bool


class StockOut(BaseModel):
    product_id: uuid.UUID
    name: str
    code: str | None
    unit: str
    track: bool
    reorder_level: Decimal | None
    quantity: Decimal
    average_cost: Decimal
    value: int
    levels: list[LevelOut]
    low: bool


class OpeningIn(In):
    product_id: uuid.UUID
    branch_id: uuid.UUID | None = None
    quantity: Qty
    unit_cost: Cost


class AdjustmentIn(In):
    product_id: uuid.UUID
    branch_id: uuid.UUID | None = None
    # Positive adds stock; negative removes it (damaged, expired, used in the shop).
    quantity: SignedQty
    reason: Annotated[str, Field(min_length=1, max_length=500)]


class PurchaseLineIn(In):
    product_id: uuid.UUID
    quantity: Qty
    # Cost per unit before tax.
    unit_cost: Cost
    # A tax the workspace can reclaim (input tax), from its own tax rates.
    tax_rate_id: uuid.UUID | None = None


class PurchaseIn(In):
    supplier_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    reference: str | None = Field(default=None, max_length=60)
    received_on: date | None = None
    lines: list[PurchaseLineIn] = Field(min_length=1, max_length=500)
    paid: Amount = 0
    paid_from: PaidFrom = "drawer"
    note: str | None = Field(default=None, max_length=1000)


class PurchaseOut(BaseModel):
    id: uuid.UUID
    supplier_id: uuid.UUID | None
    supplier_name: str | None
    branch_id: uuid.UUID | None
    reference: str | None
    received_on: date
    net: int
    tax: int
    total: int
    paid: int
    paid_from: str
    lines: list[dict[str, object]]
    note: str | None
    created_at: datetime


class TransferLineIn(In):
    product_id: uuid.UUID
    quantity: Qty


class TransferIn(In):
    from_branch_id: uuid.UUID | None = None
    to_branch_id: uuid.UUID | None = None
    lines: list[TransferLineIn] = Field(min_length=1, max_length=500)
    note: str | None = Field(default=None, max_length=1000)


class CountLineIn(In):
    product_id: uuid.UUID
    counted: Annotated[Decimal, Field(ge=0, le=10**9, max_digits=14, decimal_places=3)]


class CountIn(In):
    branch_id: uuid.UUID | None = None
    counted_on: date | None = None
    lines: list[CountLineIn] = Field(min_length=1, max_length=2000)
    note: str | None = Field(default=None, max_length=1000)


class CountOut(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID | None
    counted_on: date
    lines: list[dict[str, object]]
    note: str | None
    # The cost value gained (positive) or lost (negative).
    value: int


class MovementOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    branch_id: uuid.UUID | None
    kind: str
    quantity: Decimal
    unit_cost: Decimal
    value: int
    occurred_at: datetime
    ref_type: str | None
    ref_id: uuid.UUID | None
    note: str | None
