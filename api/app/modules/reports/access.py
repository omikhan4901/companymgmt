"""Who may see reports. Managers see their own departments; owners and admins everything."""

from __future__ import annotations

from app.core import permissions as perms

VIEW = perms.register("reports.view", "See reports and dashboards", module="people", scoped=True)
