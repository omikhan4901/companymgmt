"""How each thing that happens becomes a balanced journal entry.

A posting is a list of legs: an account (by role, or a chosen account) and a signed
amount, positive for a debit and negative for a credit. Every posting must sum to zero;
`balanced` checks it, and the property tests in tests/test_ledger.py prove the rules
always produce balanced entries. Returns and refunds come through the same rules with
negative amounts, which simply swap sides.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

PAID_FROM_ROLE = {"drawer": "drawer", "petty_cash": "petty_cash", "bank": "bank", "other": "cash"}


@dataclass(frozen=True)
class Leg:
    # An account role ("cash", "sales"…) or a chosen account's id.
    account: str | uuid.UUID
    amount: int
    description: str | None = None
    tax_rate_id: uuid.UUID | None = None
    tax_base: int | None = None


@dataclass
class Posting:
    memo: str
    legs: list[Leg] = field(default_factory=list)

    def add(self, account: str | uuid.UUID, amount: int, **extra: Any) -> None:
        if amount:
            self.legs.append(Leg(account, amount, **extra))


def balanced(legs: Iterable[Leg]) -> bool:
    return sum(leg.amount for leg in legs) == 0


def sides(amount: int) -> tuple[int, int]:
    """(debit, credit) for a signed amount."""
    return (amount, 0) if amount >= 0 else (0, -amount)


@dataclass(frozen=True)
class SaleLineFacts:
    net: int
    # [(tax_rate_id, amount)]
    taxes: Sequence[tuple[uuid.UUID, int]]


def sale(
    number: int,
    kind: str,
    cash: int,
    on_account: int,
    rounding: int,
    lines: Sequence[SaleLineFacts],
    output_accounts: dict[uuid.UUID, uuid.UUID],
) -> Posting:
    """A sale (or, with negative amounts, a return): money in, sales and tax out."""
    p = Posting(f"{'Return' if kind == 'return' else 'Sale'} #{number}")
    p.add("drawer", cash)
    p.add("receivables", on_account)
    p.add("sales", -sum(line.net for line in lines))
    taxes: dict[uuid.UUID, int] = defaultdict(int)
    bases: dict[uuid.UUID, int] = defaultdict(int)
    for line in lines:
        for rate_id, amount in line.taxes:
            taxes[rate_id] += amount
            bases[rate_id] += line.net
    for rate_id, amount in taxes.items():
        p.add(
            output_accounts.get(rate_id, "tax_payable"),
            -amount,
            tax_rate_id=rate_id,
            tax_base=-bases[rate_id],
        )
    p.add("rounding", -rounding)
    # Anything left over (a line rounded differently from its taxes) goes to rounding.
    p.add("rounding", -sum(leg.amount for leg in p.legs))
    return p


def stock(kind: str, value: int, name: str) -> Posting | None:
    """The cost side of stock moving. Purchases and transfers are posted elsewhere (or net
    to nothing)."""
    if kind in ("purchase", "transfer_out", "transfer_in") or not value:
        return None
    if kind in ("sale", "return", "void"):
        p = Posting(f"Cost of goods: {name}")
        p.add("inventory", value)
        p.add("cogs", -value)
        return p
    if kind == "opening":
        p = Posting(f"Opening stock: {name}")
        p.add("inventory", value)
        p.add("opening", -value)
        return p
    p = Posting(f"Stock {'count' if kind == 'count' else 'adjustment'}: {name}")
    p.add("inventory", value)
    p.add("stock_adjustments", -value)
    return p


def purchase(
    reference: str,
    net: int,
    taxes: Sequence[tuple[uuid.UUID, int, int]],
    paid: int,
    paid_from: str,
    owed: int,
    input_accounts: dict[uuid.UUID, uuid.UUID],
) -> Posting:
    p = Posting(f"Purchase {reference}".strip())
    p.add("inventory", net)
    for rate_id, amount, base in taxes:
        p.add(input_accounts.get(rate_id, "tax_receivable"), amount, tax_rate_id=rate_id, tax_base=base)
    p.add(PAID_FROM_ROLE.get(paid_from, "cash"), -paid)
    p.add("payables", -owed)
    return p


def supplier_payment(name: str, amount: int, paid_from: str) -> Posting:
    p = Posting(f"Paid {name}")
    p.add("payables", amount)
    p.add(PAID_FROM_ROLE.get(paid_from, "bank"), -amount)
    return p


def customer_payment(name: str, amount: int) -> Posting:
    p = Posting(f"Received from {name}")
    p.add("cash", amount)
    p.add("receivables", -amount)
    return p


def customer_adjustment(name: str, amount: int, note: str | None) -> Posting:
    """Positive adds to what they owe; negative writes some off."""
    p = Posting(f"Adjustment for {name}" + (f": {note}" if note else ""))
    p.add("receivables", amount)
    p.add("write_offs", -amount)
    return p


def expense(label: str, amount: int, paid_from: str, account: uuid.UUID | None) -> Posting:
    p = Posting(label)
    p.add(account or "expenses", amount)
    p.add(PAID_FROM_ROLE.get(paid_from, "cash"), -amount)
    return p


def petty_top_up(amount: int) -> Posting:
    p = Posting("Petty cash top-up")
    p.add("petty_cash", amount)
    p.add("cash", -amount)
    return p


def payroll(period: str, gross: int, net: int, deductions: int) -> Posting:
    p = Posting(f"Payroll {period}")
    p.add("salaries", gross)
    p.add("salaries_payable", -net)
    p.add("deductions_payable", -deductions)
    # If gross isn't exactly net plus deductions, the difference is a deduction to pay.
    p.add("deductions_payable", -sum(leg.amount for leg in p.legs))
    return p


def reverse(legs: Iterable[Leg]) -> list[Leg]:
    return [
        Leg(
            leg.account,
            -leg.amount,
            leg.description,
            leg.tax_rate_id,
            -leg.tax_base if leg.tax_base else None,
        )
        for leg in legs
    ]
