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
    """Stock in at a cost. Returns the new position and the value added."""
    added = quantity * unit_cost
    q = p.quantity + quantity
    v = p.value + added
    # Below zero, the last known cost stands until stock is positive again.
    average = v / q if q > 0 else (unit_cost if quantity > 0 else p.average)
    return Position(q, v if q != 0 else Decimal(0), average), added


def move(p: Position, quantity: Decimal) -> tuple[Position, Decimal]:
    """Stock out (negative) or back in (positive) at the current average cost. Returns
    the new position and the value moved (negative when stock leaves)."""
    value = quantity * p.average
    q = p.quantity + quantity
    v = p.value + value if q != 0 else Decimal(0)
    return Position(q, v, p.average), value
