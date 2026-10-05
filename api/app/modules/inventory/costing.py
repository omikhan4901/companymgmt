"""Weighted average cost, with no database: what a movement does to quantity and value.

Each product has one average cost across branches. Stock coming in at a known cost
(purchases, opening stock) moves the average; everything else moves at the current
average. Quantity may go below zero (a shop sells before it records the delivery); the
value follows, and the average is kept from the last time stock was positive.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class Position:
    quantity: Decimal
    # Total cost value of what's on hand, minor units (may be fractional while held).
    value: Decimal
    average: Decimal


EMPTY = Position(Decimal(0), Decimal(0), Decimal(0))


def money(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def receive(p: Position, quantity: Decimal, unit_cost: Decimal) -> tuple[Position, Decimal]:
    """Stock in at a cost. Returns the new position and the total change in value.

    If stock was below zero (sold before the delivery was recorded), the units sold early
    are re-costed at this delivery's cost: the total change is then the purchase itself
    plus a cost correction (`correction()` gives that part), and the average never goes
    negative."""
    q = p.quantity + quantity
    if p.quantity < 0:
        # Sold ahead: what arrives covers the shortfall first, at its real cost.
        if q > 0:
            value, average = q * unit_cost, unit_cost
        else:
            value, average = q * p.average, p.average
    else:
        value = p.value + quantity * unit_cost
        average = value / q if q > 0 else p.average
    if q == 0:
        value = Decimal(0)
    return Position(q, value, average), value - p.value


def correction(quantity: Decimal, unit_cost: Decimal, change: Decimal) -> Decimal:
    """The part of `receive`'s change that re-costs stock sold ahead (0 normally)."""
    return change - quantity * unit_cost


def move(p: Position, quantity: Decimal) -> tuple[Position, Decimal]:
    """Stock out (negative) or back in (positive) at the current average cost. Returns
    the new position and the value moved (negative when stock leaves)."""
    value = quantity * p.average
    q = p.quantity + quantity
    v = p.value + value if q != 0 else Decimal(0)
    return Position(q, v, p.average), value
