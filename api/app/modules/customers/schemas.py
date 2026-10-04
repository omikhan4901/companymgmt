"""Customers and their accounts over the API."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.core.schema import In, Name

Amount = Annotated[int, Field(ge=0, le=10**13)]


class CustomerIn(In):
    name: Name
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=1000)
    note: str | None = Field(default=None, max_length=2000)
    credit_limit: Amount | None = None


class CustomerPatch(In):
    name: Name | None = None
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=1000)
    note: str | None = Field(default=None, max_length=2000)
    credit_limit: Amount | None = None
    no_limit: bool = False
    active: bool | None = None


class CustomerOut(BaseModel):
    id: uuid.UUID
    name: str
    phone: str | None
    address: str | None
    note: str | None
    credit_limit: int | None
    active: bool
    # What they owe now (negative: you owe them, e.g. after a return).
    balance: int
    last_activity: date | None
    version: int


class PaymentIn(In):
    amount: Annotated[int, Field(gt=0, le=10**13)]
    occurred_on: date | None = None
    note: str | None = Field(default=None, max_length=500)


class AdjustmentIn(In):
    # Positive adds to what they owe; negative forgives some.
    amount: Annotated[int, Field(ge=-(10**13), le=10**13)]
    note: Annotated[str, Field(min_length=1, max_length=500)]
    occurred_on: date | None = None


class EntryOut(BaseModel):
    id: uuid.UUID
    kind: Literal["sale", "return", "payment", "adjustment"]
    amount: int
    occurred_on: date
    sale_id: uuid.UUID | None
    note: str | None
    created_at: datetime
    # What they owed after this line.
    balance: int


class StatementOut(BaseModel):
    customer: CustomerOut
    opening: int
    entries: list[EntryOut]
    closing: int
    start: date | None
    end: date | None
