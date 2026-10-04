"""Who may record and manage expenses."""

from __future__ import annotations

from app.core import permissions as perms

MODULE = "expenses"
RECORD = perms.register("expenses.record", "Record expenses (and see your own)", module=MODULE)
MANAGE = perms.register(
    "expenses.manage", "See all expenses, change categories, top up petty cash", module=MODULE
)
