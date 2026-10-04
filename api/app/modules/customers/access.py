"""Who may see and change customers and their dues."""

from __future__ import annotations

from app.core import permissions as perms

MODULE = "customers"
VIEW = perms.register("customers.view", "See customers and what they owe", module=MODULE)
MANAGE = perms.register("customers.manage", "Add customers, record payments and adjust dues", module=MODULE)
