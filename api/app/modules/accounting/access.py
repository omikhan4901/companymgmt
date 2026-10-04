"""Who may read and keep the books."""

from __future__ import annotations

from app.core import permissions as perms

MODULE = "accounting"
VIEW = perms.register("accounting.view", "See the books and financial reports", module=MODULE)
MANAGE = perms.register(
    "accounting.manage",
    "Change accounts, post journal entries, lock periods, set up tax returns",
    module=MODULE,
)
