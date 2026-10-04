"""Expenses over the API (amounts in minor units)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.core.schema import In

Amount = Annotated[int, Field(gt=0, le=10**13)]
PaidFrom = Literal["drawer", "petty_cash", "bank", "other"]


class CategoryIn(In):
    name: Annotated[str, Field(min_length=1, max_length=80)]
    code: str | None = Field(default=None, max_length=20)
    active: bool = True
    position: int = Field(default=0, ge=0, le=10000)


class CategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str | None
    active: bool
    position: int


class ExpenseIn(In):
    amount: Amount
    occurred_on: date | None = None
    category_id: uuid.UUID | None = None
    payee: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=2000)
    paid_from: PaidFrom = "petty_cash"
    branch_id: uuid.UUID | None = None


class ExpensePatch(In):
    amount: Amount | None = None
    occurred_on: date | None = None
    category_id: uuid.UUID | None = None
    payee: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=2000)
    paid_from: PaidFrom | None = None


class TopUpIn(In):
    amount: Amount
    occurred_on: date | None = None
    note: str | None = Field(default=None, max_length=500)


class ExpenseOut(BaseModel):
    id: uuid.UUID
    kind: Literal["expense", "top_up"]
    occurred_on: date
    amount: int
    category_id: uuid.UUID | None
    category_name: str | None
    payee: str | None
    note: str | None
    paid_from: PaidFrom
    branch_id: uuid.UUID | None
    created_by_name: str | None
    created_at: datetime
    has_receipt: bool
    receipt_name: str | None
    version: int


class CategoryTotal(BaseModel):
    category_id: uuid.UUID | None
    name: str
    total: int


class ExpensesOut(BaseModel):
    items: list[ExpenseOut]
    total: int
    by_category: list[CategoryTotal]
    # Money in petty cash now (top-ups minus what was paid from it).
    petty_cash: int
