"""The books over the API (amounts in minor units)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from app.core.schema import In

AccountType = Literal["asset", "liability", "equity", "income", "expense"]
Amount = Annotated[int, Field(ge=0, le=10**15)]


class AccountIn(In):
    code: Annotated[str, Field(min_length=1, max_length=20, pattern=r"^[0-9A-Za-z.\-]+$")]
    name: Annotated[str, Field(min_length=1, max_length=120)]
    type: AccountType
    active: bool = True
    description: str | None = Field(default=None, max_length=1000)


class AccountOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    type: AccountType
    role: str | None
    active: bool
    description: str | None
    version: int


class BooksSettingsIn(In):
    locked_until: date | None = None
    # {tax_rate_id: {"output": account_id, "input": account_id}}
    tax_accounts: dict[str, dict[Literal["output", "input"], uuid.UUID | None]] = Field(default_factory=dict)
    # {expense_category_id: account_id}
    expense_accounts: dict[str, uuid.UUID | None] = Field(default_factory=dict)


class BooksSettingsOut(BaseModel):
    locked_until: date | None
    tax_accounts: dict[str, dict[str, str]]
    expense_accounts: dict[str, str]
    version: int


class EntryLineIn(In):
    account_id: uuid.UUID
    debit: Amount = 0
    credit: Amount = 0
    description: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _one_side(self) -> EntryLineIn:
        if (self.debit > 0) == (self.credit > 0):
            raise ValueError("Each line is either a debit or a credit.")
        return self


class EntryIn(In):
    entry_date: date
    memo: Annotated[str, Field(min_length=1, max_length=300)]
    lines: list[EntryLineIn] = Field(min_length=2, max_length=200)


class JournalLineOut(BaseModel):
    account_id: uuid.UUID
    account_code: str
    account_name: str
    debit: int
    credit: int
    description: str | None


class JournalEntryOut(BaseModel):
    id: uuid.UUID
    number: int
    entry_date: date
    memo: str
    source_type: str | None
    source_id: uuid.UUID | None
    reversed_by: uuid.UUID | None
    lines: list[JournalLineOut]


class ReportRow(BaseModel):
    account_id: uuid.UUID
    code: str
    name: str
    type: AccountType
    debit: int
    credit: int
    amount: int = 0


class TrialBalanceOut(BaseModel):
    as_of: date
    rows: list[ReportRow]
    debit: int
    credit: int


class ProfitLossOut(BaseModel):
    start: date
    end: date
    income: list[ReportRow]
    expenses: list[ReportRow]
    total_income: int
    total_expenses: int
    profit: int


class BalanceSheetOut(BaseModel):
    as_of: date
    assets: list[ReportRow]
    liabilities: list[ReportRow]
    equity: list[ReportRow]
    # Profit (or loss) not yet moved into equity.
    earnings: int
    total_assets: int
    total_liabilities: int
    total_equity: int
    balanced: bool


class LedgerRow(BaseModel):
    entry_id: uuid.UUID
    number: int
    entry_date: date
    memo: str
    debit: int
    credit: int
    balance: int


class LedgerOut(BaseModel):
    accounts: list[AccountOut]
    start: date
    end: date
    opening: int
    rows: list[LedgerRow]
    closing: int


class BoxSource(BaseModel):
    """What goes in a box: tax charged or the sales/purchases it was charged on, for some
    tax rates (output: on sales; input: on purchases); account movements; or other boxes."""

    kind: Literal["tax_amount", "tax_base", "account", "boxes"]
    ids: list[str] = Field(min_length=1, max_length=50)
    side: Literal["output", "input"] = "output"
    sign: Literal[1, -1] = 1


class Box(BaseModel):
    code: Annotated[str, Field(min_length=1, max_length=20)]
    label: Annotated[str, Field(min_length=1, max_length=200)]
    sources: list[BoxSource] = Field(default_factory=list, max_length=20)


class TaxTemplateIn(In):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    boxes: list[Box] = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=2000)


class TaxTemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    boxes: list[Box]
    note: str | None
    version: int


class BoxOut(BaseModel):
    code: str
    label: str
    amount: int


class TaxReturnOut(BaseModel):
    template_id: uuid.UUID
    name: str
    start: date
    end: date
    boxes: list[BoxOut]
