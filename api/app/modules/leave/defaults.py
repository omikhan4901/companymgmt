"""What a workspace starts with when Leave is switched on, by country.

Bangladesh starts close to the Labour Act 2006: casual 10 days, sick 14 days, earned leave
accruing monthly (the Act counts one day per 18 days worked; 18 a year is a round default)
carried over up to 40 days, and maternity leave of 16 weeks counted in calendar days.
These are starting points, not legal advice; owners can change all of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class TypeDefault:
    name: str
    days_per_year: Decimal | None
    paid: bool = True
    accrual: str = "yearly"
    carry_over_max: Decimal = Decimal(0)
    allow_half_day: bool = True
    calendar_days: bool = False
    prorate: bool = True
    color: str = "#6d28d9"


BANGLADESH = (
    TypeDefault("Casual leave", Decimal(10), color="#6d28d9"),
    TypeDefault("Sick leave", Decimal(14), color="#be123c"),
    TypeDefault("Earned leave", Decimal(18), accrual="monthly", carry_over_max=Decimal(40), color="#15803d"),
    TypeDefault(
        "Maternity leave",
        Decimal(112),
        allow_half_day=False,
        calendar_days=True,
        prorate=False,
        color="#c2410c",
    ),
    TypeDefault("Unpaid leave", None, paid=False, color="#52525b"),
)

GENERAL = (
    TypeDefault("Annual leave", Decimal(15), carry_over_max=Decimal(5), color="#6d28d9"),
    TypeDefault("Sick leave", Decimal(10), color="#be123c"),
    TypeDefault("Unpaid leave", None, paid=False, color="#52525b"),
)

# ISO weekdays off (Monday=1 … Sunday=7).
FRIDAY = [5]
FRIDAY_SATURDAY = [5, 6]
SATURDAY = [6]
WEEKEND = [6, 7]

WEEKLY_OFF = {
    "BD": FRIDAY,
    "SA": FRIDAY_SATURDAY,
    "QA": FRIDAY_SATURDAY,
    "KW": FRIDAY_SATURDAY,
    "OM": FRIDAY_SATURDAY,
    "BH": FRIDAY_SATURDAY,
    "NP": SATURDAY,
}


def types_for(country: str | None) -> tuple[TypeDefault, ...]:
    return BANGLADESH if country == "BD" else GENERAL


def weekly_off_for(country: str | None) -> list[int]:
    return list(WEEKLY_OFF.get(country or "", WEEKEND))
