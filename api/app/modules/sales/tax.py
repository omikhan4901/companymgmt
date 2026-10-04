"""Tax maths, with no country's rules built in: each workspace defines its own rates.

A line's taxes apply in order. A normal tax is a percentage of the line's net amount; a
compound tax is a percentage of the net amount plus every tax before it. Prices either
include the taxes (the net amount is worked back from the price) or exclude them. Every
amount is in minor units (paisa, cents) and rounded half up, per line.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class Rate:
    id: str
    name: str
    # Percent, e.g. Decimal("15") or Decimal("7.5").
    percent: Decimal
    compound: bool = False


@dataclass(frozen=True)
class LineTax:
    id: str
    name: str
    percent: Decimal
    amount: int


@dataclass(frozen=True)
class LineResult:
    net: int
    taxes: tuple[LineTax, ...]
    gross: int


def _round(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _multiplier(rates: list[Rate]) -> Decimal:
    """Gross for a net of 1."""
    taxed = Decimal(0)
    for r in rates:
        base = 1 + (taxed if r.compound else 0)
        taxed += base * r.percent / 100
    return 1 + taxed


def line(amount: int, rates: list[Rate], *, inclusive: bool) -> LineResult:
    """Taxes for one line whose price (after quantity and discount) is `amount`."""
    if not rates:
        return LineResult(net=amount, taxes=(), gross=amount)
    net = Decimal(amount) / _multiplier(rates) if inclusive else Decimal(amount)
    taxes: list[LineTax] = []
    so_far = Decimal(0)
    for r in rates:
        base = net + (so_far if r.compound else 0)
        value = base * r.percent / 100
        so_far += value
        taxes.append(LineTax(r.id, r.name, r.percent, _round(value)))
    tax_total = sum(t.amount for t in taxes)
    if inclusive:
        # The price is what the customer pays; any rounding difference stays in the net.
        return LineResult(net=amount - tax_total, taxes=tuple(taxes), gross=amount)
    net_int = _round(net)
    return LineResult(net=net_int, taxes=tuple(taxes), gross=net_int + tax_total)


def cash_round(total: int, step: int) -> int:
    """Round a cash total to the nearest `step` minor units (e.g. 100 = whole taka)."""
    if step <= 1:
        return total
    return _round(Decimal(total) / step) * step
