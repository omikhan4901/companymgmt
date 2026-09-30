"""Attendance permissions."""

from app.core import permissions as perms

SELF = perms.register("attendance.self", "Clock in and out, see own records", module="attendance")
VIEW = perms.register("attendance.view", "See others' attendance", module="attendance", scoped=True)
MANAGE = perms.register(
    "attendance.manage", "Add and fix others' attendance records", module="attendance", scoped=True
)
APPROVE = perms.register(
    "attendance.approve", "Approve attendance corrections", module="attendance", scoped=True
)
EXPORT = perms.register("attendance.export", "Export attendance", module="attendance", scoped=True)
