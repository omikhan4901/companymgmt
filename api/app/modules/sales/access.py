"""Who may sell, see sales, and run the shop's settings."""

from __future__ import annotations

from app.core import permissions as perms

MODULE = "sales"
SELL = perms.register("sales.sell", "Sell at the till and open or close the cash drawer", module=MODULE)
VIEW = perms.register("sales.view", "See all sales and the day's figures", module=MODULE)
MANAGE = perms.register(
    "sales.manage", "Change products, prices, taxes and receipts; refund and void sales", module=MODULE
)
