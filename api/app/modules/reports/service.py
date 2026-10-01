"""The overview report: headcount, attendance, leave and tasks for a period.

Numbers are worked out from the records themselves on every request: a 100-person company
has a few thousand attendance rows a month, which is quick to go through. Managers see
their own departments only, like everywhere else.

Attendance rate is "present ÷ expected", where someone is expected on each working day of
the period (not their weekly day off, not a holiday, not on approved leave, and only while
they worked here). Late means the day's first clock-in came after the start of the working
day plus the grace period, in the workspace's time zone.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select

from app.core.errors import Invalid, NotFound
from app.core.time import today
from app.modules.attendance.models import AttendanceRecord
from app.modules.attendance.service import settings as attendance_settings
from app.modules.leave.models import Holiday, LeaveRequest, LeaveType
from app.modules.leave.service import count_days, policy
from app.modules.people.access import scope_departments, subtree
from app.modules.people.models import Department, Employee
from app.modules.platform.deps import Ctx
from app.modules.reports import access
from app.modules.reports.schemas import (
    AttendanceDay,
    AttendanceSummary,
    DepartmentCount,
    Headcount,
    LeaveByType,
    LeaveSummary,
    OverviewOut,
    PersonCount,
    TaskSummary,
)
from app.modules.tasks.models import Task

MAX_DAYS = 366
TOP = 5


def _on(ctx: Ctx, module: str) -> bool:
    return ctx.entitlements is not None and module in ctx.entitlements.modules


async def _departments(ctx: Ctx, department_id: uuid.UUID | None) -> list[uuid.UUID] | None:
    """The departments the report covers (None: the whole workspace)."""
    scope = await scope_departments(ctx)
    if department_id is None:
        return scope
    if await ctx.db.get(Department, department_id) is None:
        raise NotFound()
    chosen = await subtree(ctx.db, department_id)
    if scope is not None:
        if department_id not in scope:
            raise NotFound()
        chosen = [d for d in chosen if d in scope]
    return chosen


def _employed(person: Employee, day: date) -> bool:
    return (person.joined_on is None or person.joined_on <= day) and (
        person.left_on is None or person.left_on >= day
    )


async def overview(ctx: Ctx, start: date, end: date, department_id: uuid.UUID | None = None) -> OverviewOut:
    ctx.require(access.VIEW)
    if end < start:
        raise Invalid(errors=[{"field": "end", "message": "The end can't be before the start."}])
    if (end - start).days >= MAX_DAYS:
        raise Invalid(errors=[{"field": "end", "message": "Choose up to a year at a time."}])
    assert ctx.tenant is not None
    now = today(ctx.tenant.timezone)
    departments = await _departments(ctx, department_id)

    query = select(Employee).where(
        or_(Employee.status == "active", Employee.left_on >= start),
        or_(Employee.joined_on.is_(None), Employee.joined_on <= end),
    )
    if departments is not None:
        query = query.where(Employee.department_id.in_(departments))
    people = list(await ctx.db.scalars(query))
    ids = [p.id for p in people]

    return OverviewOut(
        start=start,
        end=end,
        department_id=department_id,
        headcount=await _headcount(ctx, people, start, end),
        attendance=await _attendance(ctx, people, start, min(end, now)) if _on(ctx, "attendance") else None,
        leave=await _leave(ctx, people, start, end, now) if _on(ctx, "leave") else None,
        tasks=await _tasks(ctx, people, ids, start, end, now) if _on(ctx, "tasks") else None,
    )


async def _headcount(ctx: Ctx, people: list[Employee], start: date, end: date) -> Headcount:
    active = [p for p in people if p.status == "active"]
    counts = Counter(p.department_id for p in active)
    known = [d for d in counts if d is not None]
    rows = await ctx.db.execute(select(Department.id, Department.name).where(Department.id.in_(known)))
    names: dict[uuid.UUID, str] = {row.id: row.name for row in rows}
    by_department = sorted(
        (
            DepartmentCount(department_id=d, name=names.get(d) if d else None, people=n)
            for d, n in counts.items()
        ),
        key=lambda c: (-c.people, c.name or "~"),
    )
    return Headcount(
        active=len(active),
        joined=sum(1 for p in people if p.joined_on and start <= p.joined_on <= end),
        left=sum(1 for p in people if p.left_on and start <= p.left_on <= end),
        by_department=by_department,
    )


async def _off_days(ctx: Ctx, start: date, end: date) -> tuple[set[int], dict[uuid.UUID | None, set[date]]]:
    """Weekly days off, and holidays by branch (None: every branch)."""
    weekly = set((await policy(ctx.db)).weekly_off)
    holidays: dict[uuid.UUID | None, set[date]] = defaultdict(set)
    for day, branch in await ctx.db.execute(
        select(Holiday.day, Holiday.branch_id).where(Holiday.day >= start, Holiday.day <= end)
    ):
        holidays[branch].add(day)
    return weekly, holidays


async def _approved_leave(ctx: Ctx, ids: list[uuid.UUID], start: date, end: date) -> list[LeaveRequest]:
    if not ids or not _on(ctx, "leave"):
        return []
    return list(
        await ctx.db.scalars(
            select(LeaveRequest).where(
                LeaveRequest.employee_id.in_(ids),
                LeaveRequest.status == "approved",
                LeaveRequest.start_date <= end,
                LeaveRequest.end_date >= start,
            )
        )
    )


async def _attendance(ctx: Ctx, people: list[Employee], start: date, end: date) -> AttendanceSummary:
    assert ctx.tenant is not None
    zone = ZoneInfo(ctx.tenant.timezone)
    settings = await attendance_settings(ctx.db)
    late_after = datetime.combine(date(2000, 1, 1), settings.day_starts_at) + timedelta(
        minutes=settings.late_after_minutes
    )
    ids = [p.id for p in people]
    weekly, holidays = await _off_days(ctx, start, end)

    away: set[tuple[uuid.UUID, date]] = set()
    for request in await _approved_leave(ctx, ids, start, end):
        if request.half_day != "none":
            continue  # half a day off: still expected in
        day = max(request.start_date, start)
        while day <= min(request.end_date, end):
            away.add((request.employee_id, day))
            day += timedelta(days=1)

    first_in: dict[tuple[uuid.UUID, date], datetime] = {}
    minutes = 0
    if ids and end >= start:
        rows = await ctx.db.execute(
            select(
                AttendanceRecord.employee_id,
                AttendanceRecord.business_date,
                AttendanceRecord.clock_in_at,
                AttendanceRecord.minutes,
            ).where(
                AttendanceRecord.employee_id.in_(ids),
                AttendanceRecord.business_date >= start,
                AttendanceRecord.business_date <= end,
            )
        )
        for employee_id, day, clock_in, worked in rows:
            key = (employee_id, day)
            if key not in first_in or clock_in < first_in[key]:
                first_in[key] = clock_in
            minutes += worked or 0

    days: list[AttendanceDay] = []
    late_by: Counter[uuid.UUID] = Counter()
    present_days = 0
    day = start
    while day <= end:
        if day.isoweekday() not in weekly:
            expected = present = late = 0
            for person in people:
                if not _employed(person, day) or (person.id, day) in away:
                    continue
                if day in holidays[None] or (person.branch_id and day in holidays[person.branch_id]):
                    continue
                expected += 1
                arrived = first_in.get((person.id, day))
                if arrived is None:
                    continue
                present += 1
                local = arrived.astimezone(zone).replace(tzinfo=None)
                if local.time() > late_after.time():
                    late += 1
                    late_by[person.id] += 1
            if expected or present:
                days.append(AttendanceDay(day=day, expected=expected, present=present, late=late))
        day += timedelta(days=1)
    present_days = len(first_in)
    expected_total = sum(d.expected for d in days)
    present_total = sum(d.present for d in days)
    names = {p.id: p.full_name for p in people}
    return AttendanceSummary(
        working_days=sum(1 for d in days if d.expected),
        expected=expected_total,
        present=present_total,
        rate=round(present_total / expected_total, 4) if expected_total else None,
        late=sum(d.late for d in days),
        average_minutes=round(minutes / present_days) if present_days else None,
        days=days,
        most_late=[PersonCount(employee_id=i, name=names[i], count=n) for i, n in late_by.most_common(TOP)],
    )


async def _leave(ctx: Ctx, people: list[Employee], start: date, end: date, now: date) -> LeaveSummary:
    ids = [p.id for p in people]
    by_id = {p.id: p for p in people}
    kinds = {k.id: k for k in await ctx.db.scalars(select(LeaveType))}
    taken: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    away_today = set()
    for request in await _approved_leave(ctx, ids, start, end):
        kind = kinds[request.leave_type_id]
        first, last = max(request.start_date, start), min(request.end_date, end)
        if first == request.start_date and last == request.end_date:
            days = request.days
        else:
            days, _ = await count_days(
                ctx.db, kind, by_id[request.employee_id], first, last, request.half_day
            )
        taken[kind.id] += days
    for request in await _approved_leave(ctx, ids, now, now):
        away_today.add(request.employee_id)
    pending = 0
    if ids:
        pending = int(
            await ctx.db.scalar(
                select(func.count())
                .select_from(LeaveRequest)
                .where(LeaveRequest.employee_id.in_(ids), LeaveRequest.status == "pending")
            )
            or 0
        )
    by_type = sorted(
        (
            LeaveByType(leave_type_id=k, name=kinds[k].name, color=kinds[k].color, days=float(d))
            for k, d in taken.items()
            if d
        ),
        key=lambda t: -t.days,
    )
    return LeaveSummary(
        days_taken=float(sum(taken.values(), Decimal(0))),
        by_type=by_type,
        away_today=len(away_today),
        pending=pending,
    )


async def _tasks(
    ctx: Ctx, people: list[Employee], ids: list[uuid.UUID], start: date, end: date, now: date
) -> TaskSummary:
    if not ids:
        return TaskSummary(open=0, overdue=0, done=0, most_overdue=[])
    assert ctx.tenant is not None
    zone = ZoneInfo(ctx.tenant.timezone)
    since = datetime.combine(start, datetime.min.time(), zone).astimezone(UTC)
    until = datetime.combine(end + timedelta(days=1), datetime.min.time(), zone).astimezone(UTC)
    rows = (
        await ctx.db.execute(
            select(Task.assignee_id, Task.status, Task.due_date, Task.completed_at).where(
                Task.assignee_id.in_(ids)
            )
        )
    ).all()
    open_ = [r for r in rows if r.status != "done"]
    overdue = Counter(r.assignee_id for r in open_ if r.due_date and r.due_date < now)
    done = sum(1 for r in rows if r.status == "done" and r.completed_at and since <= r.completed_at < until)
    names = {p.id: p.full_name for p in people}
    return TaskSummary(
        open=len(open_),
        overdue=sum(overdue.values()),
        done=done,
        most_overdue=[
            PersonCount(employee_id=i, name=names[i], count=n)
            for i, n in overdue.most_common(TOP)
            if i is not None
        ],
    )
