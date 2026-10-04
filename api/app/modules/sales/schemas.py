"""Sales over the API. Money is always in minor units (paisa, cents)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.core.schema import In, Name

Amount = Annotated[int, Field(ge=0, le=10**13)]
Qty = Annotated[Decimal, Field(gt=0, le=100000, max_digits=12, decimal_places=3)]


class ShopSettingsIn(In):
    prices_include_tax: bool = True
    cash_rounding: Annotated[int, Field(ge=1, le=10000)] = 1
    tax_id_label: str | None = Field(default=None, max_length=40)
    tax_id: str | None = Field(default=None, max_length=60)
    receipt_header: str | None = Field(default=None, max_length=1000)
    receipt_footer: str | None = Field(default=None, max_length=1000)


class ShopSettingsOut(BaseModel):
    prices_include_tax: bool
    cash_rounding: int
    tax_id_label: str | None
    tax_id: str | None
    receipt_header: str | None
    receipt_footer: str | None
    version: int


class TaxRateIn(In):
    name: Annotated[str, Field(min_length=1, max_length=60)]
    code: str | None = Field(default=None, max_length=20)
    percent: Annotated[Decimal, Field(ge=0, le=100, max_digits=7, decimal_places=4)]
    compound: bool = False
    position: int = Field(default=0, ge=0, le=1000)
    active: bool = True
    default: bool = False


class TaxRateOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str | None
    percent: Decimal
    compound: bool
    position: int
    active: bool
    default: bool
    version: int


class ProductCategoryIn(In):
    name: Annotated[str, Field(min_length=1, max_length=80)]
    color: Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")] = "#0f766e"
    position: int = Field(default=0, ge=0, le=10000)


class ProductCategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    color: str
    position: int


class ProductIn(In):
    name: Name
    code: str | None = Field(default=None, max_length=40)
    category_id: uuid.UUID | None = None
    price: Amount
    # None: the workspace's default taxes.
    tax_rate_ids: list[uuid.UUID] | None = Field(default=None, max_length=10)
    unit: Annotated[str, Field(min_length=1, max_length=10)] = "pcs"
    favorite: bool = False
    active: bool = True
    position: int = Field(default=0, ge=0, le=100000)


class ProductPatch(In):
    name: Name | None = None
    code: str | None = Field(default=None, max_length=40)
    category_id: uuid.UUID | None = None
    price: Amount | None = None
    tax_rate_ids: list[uuid.UUID] | None = Field(default=None, max_length=10)
    unit: str | None = Field(default=None, min_length=1, max_length=10)
    favorite: bool | None = None
    active: bool | None = None
    position: int | None = Field(default=None, ge=0, le=100000)


class ProductOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str | None
    category_id: uuid.UUID | None
    price: int
    tax_rate_ids: list[uuid.UUID]
    unit: str
    favorite: bool
    active: bool
    position: int
    version: int


class OpenIn(In):
    opening_float: Amount = 0
    branch_id: uuid.UUID | None = None


class CloseIn(In):
    counted_cash: Amount
    note: str | None = Field(default=None, max_length=1000)


class DrawerOut(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID | None
    opened_by_name: str | None
    opened_at: datetime
    opening_float: int
    closed_at: datetime | None
    # Cash in and out so far (or at closing).
    cash_sales: int
    cash_refunds: int
    cash_expenses: int
    expected_cash: int
    counted_cash: int | None
    difference: int | None
    sales_count: int
    note: str | None


class LineIn(In):
    product_id: uuid.UUID | None = None
    # For an item that isn't in the catalogue (needs a name and price).
    name: str | None = Field(default=None, max_length=120)
    quantity: Qty = Decimal(1)
    # Only for items not in the catalogue, or with sales.manage to change a price.
    unit_price: Amount | None = None
    discount: Amount = 0
    # Items not in the catalogue: which taxes (None: the defaults).
    tax_rate_ids: list[uuid.UUID] | None = Field(default=None, max_length=10)


class SaleIn(In):
    # Made by the till, so a sale sent twice (after a dropped connection) is kept once.
    client_id: uuid.UUID
    lines: list[LineIn] = Field(min_length=1, max_length=200)
    customer_id: uuid.UUID | None = None
    paid_cash: Amount = 0
    note: str | None = Field(default=None, max_length=500)
    # When the till made it, if it was offline; defaults to now.
    sold_at: datetime | None = None


class LineTaxOut(BaseModel):
    id: str
    name: str
    code: str | None = None
    percent: Decimal
    amount: int


class LineOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID | None
    name: str
    quantity: Decimal
    unit_price: int
    discount: int
    net: int
    tax: int
    total: int
    taxes: list[LineTaxOut]
    returned: Decimal = Decimal(0)


class SaleOut(BaseModel):
    id: uuid.UUID
    number: int
    kind: Literal["sale", "return"]
    status: Literal["completed", "voided"]
    original_id: uuid.UUID | None
    sold_at: datetime
    sold_by_name: str | None
    customer_id: uuid.UUID | None
    customer_name: str | None
    net: int
    tax: int
    rounding: int
    total: int
    paid_cash: int
    change: int
    on_account: int
    prices_include_tax: bool
    note: str | None
    void_reason: str | None
    lines: list[LineOut]


class ReturnLineIn(In):
    line_id: uuid.UUID
    quantity: Qty


class ReturnIn(In):
    client_id: uuid.UUID
    lines: list[ReturnLineIn] = Field(min_length=1, max_length=200)
    # Back to their account instead of cash (only for sales to a customer).
    to_account: bool = False
    note: str | None = Field(default=None, max_length=500)


class VoidIn(In):
    reason: Annotated[str, Field(min_length=1, max_length=500)]


class TaxSummary(BaseModel):
    id: str
    name: str
    code: str | None
    percent: Decimal
    # The sales the tax was charged on, and the tax.
    taxable: int
    amount: int


class SaleReceiptOut(BaseModel):
    sale: SaleOut
    shop_name: str
    branch_name: str | None
    branch_address: str | None
    tax_id_label: str | None
    tax_id: str | None
    header: str | None
    footer: str | None
    currency: str
    taxes: list[TaxSummary]


class SellerTotal(BaseModel):
    name: str
    count: int
    total: int


class ProductTotal(BaseModel):
    name: str
    quantity: Decimal
    total: int


class DayTotal(BaseModel):
    day: date
    count: int
    total: int


class SummaryOut(BaseModel):
    start: date
    end: date
    count: int
    net: int
    tax: int
    total: int
    cash: int
    on_account: int
    returns: int
    taxes: list[TaxSummary]
    sellers: list[SellerTotal]
    products: list[ProductTotal]
    days: list[DayTotal]
