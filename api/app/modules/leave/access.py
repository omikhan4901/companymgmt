"""Leave permissions."""

from app.core import permissions as perms

SELF = perms.register("leave.self", "Ask for leave and see own balances", module="leave")
VIEW = perms.register("leave.view", "See others' leave and balances", module="leave", scoped=True)
APPROVE = perms.register("leave.approve", "Approve and reject leave requests", module="leave", scoped=True)
MANAGE = perms.register(
    "leave.manage", "Ask for leave for others and adjust balances", module="leave", scoped=True
)
SETTINGS = perms.register("leave.settings", "Change leave types, holidays and the work week", module="leave")
