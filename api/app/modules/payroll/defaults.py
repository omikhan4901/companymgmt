"""Starting payroll settings by country.

Bangladesh: overtime at twice the hourly basic (basic / 208), two festival bonuses of up to
one month's basic after a year of service (Labour Act 2006 s.108, Labour Rules 2015
r.111), and a salary tax table.

The tax table is our reading of the Finance Ordinance 2025 for income years 2025-26 and
2026-27. It could not be checked against the official text when it was written, so tax
deduction stays off until the owner reviews the table and turns it on. Not tax advice.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

TAKA = 100  # paisa per taka

BANGLADESH_TAX: dict[str, Any] = {
    "name": "Bangladesh salary tax, income years 2025-26 and 2026-27 (verify before use)",
    "tax_free": 375_000 * TAKA,
    "slabs": [
        [300_000 * TAKA, 10],
        [400_000 * TAKA, 15],
        [500_000 * TAKA, 20],
        [2_000_000 * TAKA, 25],
        [None, 30],
    ],
    "exempt_fraction": "1/3",
    "exempt_cap": 500_000 * TAKA,
    "minimum": 5_000 * TAKA,
}

# Currencies without minor units.
ZERO_DECIMAL = {"JPY", "KRW", "VND", "CLP", "ISK", "UGX", "XAF", "XOF", "PYG", "RWF"}


def unit_for(currency: str) -> int:
    return 1 if currency.upper() in ZERO_DECIMAL else 100


def settings_for(country: str | None) -> dict[str, Any]:
    if country == "BD":
        return {
            "day_basis": "calendar",
            "hours_per_day": 8,
            "overtime_multiplier": Decimal(2),
            "overtime_divisor": 208,
            "bonus_percent": 100,
            "bonus_min_months": 12,
            "tax_enabled": False,
            "tax_table": BANGLADESH_TAX,
        }
    return {
        "day_basis": "calendar",
        "hours_per_day": 8,
        "overtime_multiplier": Decimal("1.5"),
        "overtime_divisor": 173,
        "bonus_percent": 0,
        "bonus_min_months": 0,
        "tax_enabled": False,
        "tax_table": {},
    }
