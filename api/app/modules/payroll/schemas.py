"""Payroll request and response shapes. Money is an integer in minor units (paisa, cents)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.core.schema import In, Out, ShortName

Amount = Annotated[int, Field(ge=0, le=10**13)]
Period = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")]
Label = Annotated[str, StringConstraints(min_length=1, max_length=120, strip_whitespace=True)]


class TaxSlab(BaseModel):
    width: Amount | None
    rate: Annotated[Decimal, Field(ge=0, le=100)]


class TaxTable(BaseModel):
    name: Annotated[str, StringConstraints(max_length=200)] = ""
    tax_free: Amount = 0
    slabs: list[TaxSlab] = Field(default_factory=list, max_length=20)
    # A share of salary that isn't taxed, as a decimal or a fraction ("1/3").
    exempt_fraction: Annotated[
        str, StringConstraints(pattern=r"^(\d+(\.\d+)?|\d+/[1-9]\d*)$", max_length=20)
    ] = "0"
    exempt_cap: Amount | None = None
    minimum: Amount = 0

    @field_validator("exempt_fraction")
    @classmethod
    def _fraction(cls, value: str) -> str:
        if not 0 <= Fraction(value) <= 1:
            raise ValueError("Use a share between 0 and 1, like 1/3.")
        return value

    @field_validator("slabs")
    @classmethod
    def _open_ended_last(cls, slabs: list[TaxSlab]) -> list[TaxSlab]:
        if any(s.width is None for s in slabs[:-1]):
            raise ValueError("Only the last slab can be open-ended.")
        return slabs

    def to_rules(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tax_free": self.tax_free,
            "slabs": [[s.width, str(s.rate)] for s in self.slabs],
            "exempt_fraction": self.exempt_fraction,
            "exempt_cap": self.exempt_cap,
            "minimum": self.minimum,
        }

    @classmethod
    def from_rules(cls, data: dict[str, Any]) -> TaxTable:
        return cls(
            name=data.get("name", ""),
            tax_free=data.get("tax_free", 0),
            slabs=[TaxSlab(width=w, rate=Decimal(str(r))) for w, r in data.get("slabs", [])],
            exempt_fraction=str(data.get("exempt_fraction") or "0"),
            exempt_cap=data.get("exempt_cap"),
            minimum=data.get("minimum", 0),
        )


class PayrollSettingsOut(BaseModel):
    currency: str
    day_basis: Literal["calendar", "thirty"]
    hours_per_day: int
    overtime_multiplier: float
    overtime_divisor: int
    bonus_percent: int
    bonus_min_months: int
    round_net: bool
    tax_enabled: bool
    tax_table: TaxTable
    version: int


class PayrollSettingsIn(In):
    day_basis: Literal["calendar", "thirty"] = "calendar"
    hours_per_day: Annotated[int, Field(ge=1, le=16)] = 8
    overtime_multiplier: Annotated[Decimal, Field(ge=1, le=5)] = Decimal(2)
    overtime_divisor: Annotated[int, Field(ge=1, le=400)] = 208
    bonus_percent: Annotated[int, Field(ge=0, le=500)] = 100
    bonus_min_months: Annotated[int, Field(ge=0, le=60)] = 12
    round_net: bool = True
    tax_enabled: bool = False
    tax_table: TaxTable = Field(default_factory=TaxTable)


class StructureOut(Out):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str | None = None
    effective_from: date
    pay_rule: Literal["monthly", "hourly", "daily"]
    basic: int
    house_rent: int
    medical: int
    conveyance: int
    other: int
    rate: int
    monthly_total: int = 0
    overtime: bool
    deduct_tax: bool
    tax_free_override: int | None
    payment_method: Literal["cash", "bank", "wallet"]
    provider: str | None
    account_last4: str | None
    note: str | None
    created_at: datetime


class StructureIn(In):
    employee_id: uuid.UUID
    effective_from: date
    pay_rule: Literal["monthly", "hourly", "daily"] = "monthly"
    basic: Amount = 0
    house_rent: Amount = 0
    medical: Amount = 0
    conveyance: Amount = 0
    other: Amount = 0
    rate: Amount = 0
    overtime: bool = False
    deduct_tax: bool = True
    tax_free_override: Amount | None = None
    payment_method: Literal["cash", "bank", "wallet"] = "cash"
    provider: Annotated[str, StringConstraints(max_length=80, strip_whitespace=True)] | None = None
    # Digits, spaces and dashes; stored encrypted. Leave out to keep the previous one.
    account: Annotated[str, StringConstraints(pattern=r"^[0-9 \-]{4,34}$")] | None = None
    note: Annotated[str, StringConstraints(max_length=300)] | None = None


class LoanOut(Out):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str | None = None
    kind: Literal["advance", "loan"]
    label: str
    principal: int
    installment: int
    outstanding: int
    start_period: str
    status: Literal["active", "closed"]
    created_at: datetime
    version: int


class LoanIn(In):
    employee_id: uuid.UUID
    kind: Literal["advance", "loan"] = "advance"
    label: ShortName
    principal: Annotated[int, Field(gt=0, le=10**13)]
    installment: Annotated[int, Field(gt=0, le=10**13)]
    start_period: Period


class RunIn(In):
    period: Period
    bonus_label: Annotated[str, StringConstraints(max_length=80, strip_whitespace=True)] | None = None


class RunOut(Out):
    id: uuid.UUID
    period: str
    status: Literal["draft", "review", "finalized", "paid"]
    bonus_label: str | None
    currency: str
    headcount: int
    gross: int
    deductions: int
    net: int
    computed_at: datetime | None
    created_by: uuid.UUID | None
    submitted_by: uuid.UUID | None
    submitted_at: datetime | None
    finalized_by: uuid.UUID | None
    finalized_at: datetime | None
    paid_at: datetime | None
    version: int


class PayLine(BaseModel):
    code: str
    label: str
    kind: Literal["earning", "deduction"]
    amount: int
    ref: str | None = None


class PayslipOut(Out):
    id: uuid.UUID
    run_id: uuid.UUID
    period: str | None = None
    status: str | None = None
    currency: str | None = None
    employee_id: uuid.UUID
    employee_name: str
    employee_code: str | None
    department_name: str | None
    job_title: str | None
    pay_rule: str
    days_in_period: int
    payable_days: float
    unpaid_leave_days: float
    worked_minutes: int
    overtime_minutes: int
    lines: list[PayLine]
    gross: int
    deductions: int
    net: int
    carried_forward: int
    payment_method: str
    provider: str | None
    account_last4: str | None


class RunDetail(RunOut):
    payslips: list[PayslipOut]
    # People with no salary set for this month (so they were left out).
    missing: list[dict[str, Any]]


class ItemIn(In):
    employee_id: uuid.UUID
    kind: Literal["earning", "deduction"]
    label: Label
    amount: Annotated[int, Field(gt=0, le=10**13)]


class ItemOut(Out):
    id: uuid.UUID
    run_id: uuid.UUID
    employee_id: uuid.UUID
    kind: str
    label: str
    amount: int
