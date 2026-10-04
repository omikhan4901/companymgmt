"""Who may see and change stock."""

from __future__ import annotations

from app.core import permissions as perms

MODULE = "inventory"
VIEW = perms.register("inventory.view", "See stock levels and movements", module=MODULE)
MANAGE = perms.register(
    "inventory.manage", "Receive purchases, transfer and count stock, manage suppliers", module=MODULE
)
