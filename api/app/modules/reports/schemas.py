"""The overview report: one period, optionally one department, every section a module allows."""

from __future__ import annotations

import uuid
from datetime import date

from app.core.schema import In, Out


class DepartmentCount(Out):
    department_id: uuid.UUID | None
    name: str | None
    people: int


class Headcount(Out):
    active: int
    joined: int
    left: int
    by_department: list[DepartmentCount]


class AttendanceDay(Out):
    day: date
    expected: int
    present: int
    late: int


class PersonCount(Out):
    employee_id: uuid.UUID
    name: str
    count: int


class AttendanceSummary(Out):
    working_days: int
    # Person-days someone was due at work (working days, after leave and holidays).
    expected: int
    present: int
    # present / expected, or None when nobody was expected yet.
    rate: float | None
    late: int
    average_minutes: int | None
    days: list[AttendanceDay]
    most_late: list[PersonCount]


class LeaveByType(Out):
    leave_type_id: uuid.UUID
    name: str
    color: str
    days: float


class LeaveSummary(Out):
    days_taken: float
    by_type: list[LeaveByType]
    away_today: int
    pending: int


class TaskSummary(Out):
    open: int
    overdue: int
    done: int
    most_overdue: list[PersonCount]


class OverviewOut(Out):
    start: date
    end: date
    department_id: uuid.UUID | None
    headcount: Headcount
    # None when the module is switched off.
    attendance: AttendanceSummary | None
    leave: LeaveSummary | None
    tasks: TaskSummary | None


class SubscriptionIn(In):
    weekly: bool = False
    monthly: bool = False
    department_id: uuid.UUID | None = None


class SubscriptionOut(Out):
    weekly: bool
    monthly: bool
    department_id: uuid.UUID | None
    # Staff accounts have no email address to send to.
    has_email: bool
