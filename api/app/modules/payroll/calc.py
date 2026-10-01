"""Pay calculation as a pure function: no database, so every rule is easy to test.

All amounts are integers in minor units (paisa, cents). Intermediate maths uses Decimal
and each line is rounded half-up to a minor unit. Invariants (tested with Hypothesis):
- gross is the sum of earning lines, deductions the sum of deduction lines;
- net = max(gross - deductions, 0), and anything that didn't fit is carried forward;
- no line is negative except a rounding adjustment.
"""

from __future__ import annotations

import calendar
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import Any

D0 = Decimal(0)


def money(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class Rules:
    """The workspace's payroll settings."""

    day_basis: str = "calendar"
    hours_per_day: int = 8
    overtime_multiplier: Decimal = Decimal(2)
    overtime_divisor: int = 208
    bonus_percent: int = 100
    bonus_min_months: int = 12
    round_net: bool = True
    # Minor units per whole currency unit (100 for taka, dollars, ...).
    unit: int = 100
    tax: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class Structure:
    pay_rule: str = "monthly"
    basic: int = 0
    house_rent: int = 0
    medical: int = 0
    conveyance: int = 0
    other: int = 0
    rate: int = 0
    overtime: bool = False
    deduct_tax: bool = True
    tax_free_override: int | None = None

    @property
    def monthly(self) -> int:
        return self.basic + self.house_rent + self.medical + self.conveyance + self.other


@dataclass(frozen=True)
class LoanDue:
    ref: str
    label: str
    installment: int
    outstanding: int


@dataclass(frozen=True)
class Item:
    kind: str
    label: str
    amount: int
    ref: str | None = None


@dataclass(frozen=True)
class Inputs:
    period: str  # YYYY-MM
    structure: Structure
    joined_on: date | None = None
    left_on: date | None = None
    unpaid_leave_days: Decimal = D0
    # Minutes worked per day (closed shifts) within the period.
    worked: Mapping[date, int] = field(default_factory=dict)
    bonus_label: str | None = None
    loans: Sequence[LoanDue] = ()
    items: Sequence[Item] = ()


@dataclass
class Line:
    code: str
    label: str
    kind: str
    amount: int
    ref: str | None = None

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "code": self.code,
            "label": self.label,
            "kind": self.kind,
            "amount": self.amount,
        }
        if self.ref:
            out["ref"] = self.ref
        return out


@dataclass
class Result:
    lines: list[Line]
    gross: int
    deductions: int
    net: int
    carried_forward: int
    days_in_period: int
    payable_days: Decimal
    worked_minutes: int
    overtime_minutes: int


def period_bounds(period: str) -> tuple[date, date]:
    year, month = (int(x) for x in period.split("-"))
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def months_of_service(joined_on: date | None, until: date) -> int:
    if joined_on is None:
        return 10_000
    months = (until.year - joined_on.year) * 12 + until.month - joined_on.month
    return months - (1 if until.day < joined_on.day else 0)


def annual_tax(income: int, table: Mapping[str, Any], *, tax_free_override: int | None = None) -> int:
    """Yearly tax on a yearly salary (minor units) from a tax table:

    {"tax_free": 37500000, "slabs": [[30000000, 10], [40000000, 15], ..., [null, 30]],
     "exempt_fraction": "1/3", "exempt_cap": 50000000, "minimum": 500000}

    Exact fractions throughout, so "a third of salary" is exactly a third.
    """
    exempt = Fraction(income) * Fraction(str(table.get("exempt_fraction") or 0))
    cap = table.get("exempt_cap")
    if cap is not None:
        exempt = min(exempt, Fraction(cap))
    free = Fraction(tax_free_override if tax_free_override is not None else table.get("tax_free", 0))
    remaining = Fraction(income) - exempt - free
    if remaining <= 0:
        return 0
    tax = Fraction(0)
    for width, rate in table.get("slabs", []):
        if remaining <= 0:
            break
        part = remaining if width is None else min(remaining, Fraction(width))
        tax += part * Fraction(str(rate)) / 100
        remaining -= part
    tax = max(tax, Fraction(table.get("minimum") or 0))
    return money(Decimal(tax.numerator) / Decimal(tax.denominator))


def calculate(inputs: Inputs, rules: Rules) -> Result:
    s = inputs.structure
    start, end = period_bounds(inputs.period)
    days_in_month = (end - start).days + 1
    basis = 30 if rules.day_basis == "thirty" else days_in_month
    first = max(start, inputs.joined_on) if inputs.joined_on else start
    last = min(end, inputs.left_on) if inputs.left_on else end
    employed = max((last - first).days + 1, 0)
    if rules.day_basis == "thirty":
        employed = basis if employed == days_in_month else min(employed, basis)

    worked = {d: m for d, m in inputs.worked.items() if first <= d <= last}
    worked_minutes = sum(worked.values())
    limit = rules.hours_per_day * 60
    overtime_minutes = sum(max(m - limit, 0) for m in worked.values()) if s.overtime else 0

    lines: list[Line] = []

    def earn(code: str, label: str, amount: Decimal | int, ref: str | None = None) -> None:
        value = money(Decimal(amount))
        if value > 0:
            lines.append(Line(code, label, "earning", value, ref))

    def deduct(code: str, label: str, amount: Decimal | int, ref: str | None = None) -> None:
        value = money(Decimal(amount))
        if value > 0:
            lines.append(Line(code, label, "deduction", value, ref))

    share = Decimal(employed) / Decimal(basis) if basis else D0
    unpaid = min(inputs.unpaid_leave_days, Decimal(employed))
    if s.pay_rule == "monthly":
        for code, label, amount in (
            ("basic", "Basic", s.basic),
            ("house_rent", "House rent", s.house_rent),
            ("medical", "Medical", s.medical),
            ("conveyance", "Conveyance", s.conveyance),
            ("other", "Other allowances", s.other),
        ):
            earn(code, label, Decimal(amount) * share)
        if unpaid > 0:
            deduct("unpaid_leave", "Unpaid leave", Decimal(s.monthly) / Decimal(basis) * unpaid)
        hourly_ot = Decimal(s.basic) / Decimal(rules.overtime_divisor) * rules.overtime_multiplier
    elif s.pay_rule == "hourly":
        earn("hours", "Hours worked", Decimal(s.rate) * worked_minutes / 60)
        # Overtime hours are already paid once above; the premium is the extra part.
        hourly_ot = Decimal(s.rate) * (rules.overtime_multiplier - 1)
    else:
        earn("days", "Days worked", Decimal(s.rate) * len([m for m in worked.values() if m > 0]))
        hourly_ot = Decimal(s.rate) / Decimal(rules.hours_per_day) * rules.overtime_multiplier
    if overtime_minutes:
        earn("overtime", "Overtime", hourly_ot * overtime_minutes / 60)

    bonus = 0
    if inputs.bonus_label and months_of_service(inputs.joined_on, end) >= rules.bonus_min_months:
        bonus = money(Decimal(s.basic) * rules.bonus_percent / 100)
        earn("bonus", inputs.bonus_label, bonus)

    for item in inputs.items:
        (earn if item.kind == "earning" else deduct)("item", item.label, item.amount, item.ref)

    gross_before_tax = sum(x.amount for x in lines if x.kind == "earning")
    if rules.tax and s.deduct_tax:
        # Tax deducted at source: this year's expected salary, spread over 12 months.
        if s.pay_rule == "monthly":
            yearly = s.monthly * 12 + money(Decimal(s.basic) * rules.bonus_percent / 100) * 2
        else:
            yearly = gross_before_tax * 12
        deduct(
            "tax",
            "Income tax",
            Decimal(annual_tax(yearly, rules.tax, tax_free_override=s.tax_free_override)) / 12,
        )

    for loan in inputs.loans:
        deduct("loan", loan.label, min(loan.installment, loan.outstanding), loan.ref)

    gross = sum(x.amount for x in lines if x.kind == "earning")
    deductions = sum(x.amount for x in lines if x.kind == "deduction")
    if rules.round_net and gross - deductions > 0:
        net_raw = gross - deductions
        rounded = money(Decimal(net_raw) / rules.unit) * rules.unit
        if rounded != net_raw:
            lines.append(Line("rounding", "Rounding", "earning", rounded - net_raw))
            gross += rounded - net_raw
    net = max(gross - deductions, 0)
    carried = max(deductions - gross, 0)
    return Result(
        lines=lines,
        gross=gross,
        deductions=deductions,
        net=net,
        carried_forward=carried,
        days_in_period=basis,
        payable_days=Decimal(employed) - unpaid,
        worked_minutes=worked_minutes,
        overtime_minutes=overtime_minutes,
    )
