"""Who may build automations: owners and admins (they act for the whole workspace)."""

from __future__ import annotations

from app.core import permissions as perms

MANAGE = perms.register("automations.manage", "Create, change and pause automations", module="platform")
