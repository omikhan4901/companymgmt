"""Attendance rules."""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import current_tenant
from app.core.errors import Conflict, Forbidden, Invalid, NotFound
from app.core.time import local_date, today, utcnow
from app.modules.attendance import access
from app.modules.attendance.models import MAX_SHIFT_HOURS, AttendanceRecord, AttendanceSettings
from app.modules.attendance.schemas import (
    DayOut,
    PresentOut,
    StatusOut,
    TimesheetOut,
    TimesheetRow,
    record_out,
)
from app.modules.people.access import in_scope, scope_departments
from app.modules.people.models import Employee
from app.modules.people.service import employee_for_membership
from app.modules.platform import hooks
from app.modules.platform.deps import Ctx
from app.modules.platform.models import Branch, Membership, Tenant, User

MAX_SHIFT = timedelta(hours=MAX_SHIFT_HOURS)
# How far in the future a manual time may be (clock differences between devices).
FUTURE_SLACK = timedelta(minutes=5)


def minutes_between(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)


async def branch_timezone(db: AsyncSession, branch_id: uuid.UUID | None) -> str:
    if branch_id is not None:
        branch = await db.get(Branch, branch_id)
        if branch is not None:
            return branch.timezone
    tenant = await db.get(Tenant, current_tenant(db))
    return tenant.timezone if tenant else "UTC"


async def default_branch(db: AsyncSession, employee: Employee) -> uuid.UUID | None:
    if employee.branch_id is not None:
        return employee.branch_id
    return await db.scalar(
        select(Branch.id).where(Branch.is_active.is_(True)).order_by(Branch.created_at).limit(1)
    )


def validate_times(clock_in: datetime, clock_out: datetime | None) -> None:
    now = utcnow()
    if clock_in.tzinfo is None or (clock_out is not None and clock_out.tzinfo is None):
        raise Invalid(errors=[{"field": "clock_in_at", "message": "Include a timezone in times."}])
    if clock_in > now + FUTURE_SLACK:
        raise Invalid(errors=[{"field": "clock_in_at", "message": "This time is in the future."}])
    if clock_out is not None:
        if clock_out <= clock_in:
            raise Invalid(errors=[{"field": "clock_out_at", "message": "Clock-out must be after clock-in."}])
        if clock_out > now + FUTURE_SLACK:
            raise Invalid(errors=[{"field": "clock_out_at", "message": "This time is in the future."}])
        if clock_out - clock_in > MAX_SHIFT:
            raise Invalid(
                errors=[
                    {
                        "field": "clock_out_at",
                        "message": f"A shift can't be longer than {MAX_SHIFT_HOURS} hours.",
                    }
                ]
            )


async def save(db: AsyncSession, record: AttendanceRecord) -> None:
    """Flush, turning database guards into clear answers."""
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        message = str(exc.orig)
        if "uq_attendance_open" in message:
            raise Conflict("Already clocked in.", code="already_clocked_in") from exc
        if "no_overlap" in message:
            raise Conflict("This overlaps another shift for the same person.", code="overlap") from exc
        raise


async def business_date_for(db: AsyncSession, branch_id: uuid.UUID | None, instant: datetime) -> date:
    """The day a shift belongs to: the clock-in date in the branch's timezone."""
    return local_date(instant, await branch_timezone(db, branch_id))


async def _close_on_removal(db: AsyncSession, membership: Membership, user: User) -> None:
    employee = await db.scalar(select(Employee).where(Employee.membership_id == membership.id))
    if employee is None:
        return
    record = await db.scalar(
        select(AttendanceRecord)
        .where(AttendanceRecord.employee_id == employee.id, AttendanceRecord.clock_out_at.is_(None))
        .with_for_update()
    )
    if record is None:
        return
    end = min(utcnow(), record.clock_in_at + MAX_SHIFT)
    if end <= record.clock_in_at:
        end = record.clock_in_at + timedelta(minutes=1)
    record.clock_out_at = end
    record.status = "auto_closed"
    record.minutes = None
    record.note = ((record.note or "") + " [closed when access was removed]").strip()[:500]


def register_hooks() -> None:
    if _close_on_removal not in hooks.member_removed:
        hooks.member_removed.append(_close_on_removal)


# ---- Reads shared by the routes and capabilities ----------------------------------------


async def me(ctx: Ctx) -> Employee:
    assert ctx.membership is not None
    employee = await employee_for_membership(ctx.db, ctx.membership.id)
    if employee is None or employee.status != "active":
        raise Forbidden("You don't have an active profile in this workspace.", code="no_profile")
    return employee


async def open_record(
    db: AsyncSession, employee_id: uuid.UUID, *, lock: bool = False
) -> AttendanceRecord | None:
    query = select(AttendanceRecord).where(
        AttendanceRecord.employee_id == employee_id, AttendanceRecord.clock_out_at.is_(None)
    )
    if lock:
        query = query.with_for_update()
    return await db.scalar(query)


async def scoped_employee(ctx: Ctx, employee_id: uuid.UUID) -> Employee:
    employee = await ctx.db.get(Employee, employee_id)
    if employee is None or not await in_scope(ctx, employee.department_id):
        raise NotFound()
    return employee


async def settings(db: AsyncSession) -> AttendanceSettings:
    """The workspace's attendance settings (defaults until someone changes them)."""
    row = await db.scalar(select(AttendanceSettings))
    return row or AttendanceSettings(location_mode="require", max_accuracy_m=100)


async def status(ctx: Ctx) -> StatusOut:
    """Whether this person is clocked in, and how long they've worked today."""
    employee = await me(ctx)
    record = await open_record(ctx.db, employee.id)
    assert ctx.tenant is not None
    day = today(ctx.tenant.timezone)
    worked = await ctx.db.scalar(
        select(func.coalesce(func.sum(AttendanceRecord.minutes), 0)).where(
            AttendanceRecord.employee_id == employee.id, AttendanceRecord.business_date == day
        )
    )
    forgot = record is not None and utcnow() - record.clock_in_at > MAX_SHIFT
    return StatusOut(
        employee_id=employee.id,
        employee_name=employee.preferred_name or employee.full_name,
        open_record=record_out(record) if record else None,
        today_minutes=int(worked or 0),
        forgot_clock_out=forgot,
        location_mode=(await settings(ctx.db)).location_mode,
    )


async def present(ctx: Ctx) -> list[PresentOut]:
    """Who is clocked in right now, within this member's scope."""
    query = (
        select(AttendanceRecord, Employee)
        .join(
            Employee,
            and_(
                Employee.tenant_id == AttendanceRecord.tenant_id, Employee.id == AttendanceRecord.employee_id
            ),
        )
        .where(AttendanceRecord.clock_out_at.is_(None))
    )
    scope = await scope_departments(ctx)
    if scope is not None:
        query = query.where(Employee.department_id.in_(scope))
    rows = (await ctx.db.execute(query.order_by(AttendanceRecord.clock_in_at))).all()
    return [
        PresentOut(
            employee_id=e.id,
            employee_name=e.preferred_name or e.full_name,
            clock_in_at=r.clock_in_at,
            branch_id=r.branch_id,
        )
        for r, e in rows
    ]


def month_range(month: str) -> tuple[date, date]:
    try:
        year, mon = (int(x) for x in month.split("-"))
        start = date(year, mon, 1)
    except ValueError as exc:
        raise Invalid(errors=[{"field": "month", "message": "Use YYYY-MM."}]) from exc
    return start, date(year, mon, calendar.monthrange(year, mon)[1])


async def timesheet_rows(
    ctx: Ctx, start: date, end: date, employee_id: uuid.UUID | None
) -> list[TimesheetRow]:
    employees_query = select(Employee).where(Employee.status != "left")
    if not ctx.can(access.VIEW):
        employees_query = select(Employee).where(Employee.id == (await me(ctx)).id)
    else:
        scope = await scope_departments(ctx)
        if scope is not None:
            employees_query = employees_query.where(Employee.department_id.in_(scope))
        if employee_id:
            employees_query = employees_query.where(Employee.id == employee_id)
    employees = (await ctx.db.scalars(employees_query.order_by(func.lower(Employee.full_name)))).all()
    ids = [e.id for e in employees]
    totals: dict[tuple[uuid.UUID, date], tuple[int, int, int]] = {}
    if ids:
        rows = await ctx.db.execute(
            select(
                AttendanceRecord.employee_id,
                AttendanceRecord.business_date,
                func.coalesce(func.sum(AttendanceRecord.minutes), 0),
                func.count(),
                func.count().filter(AttendanceRecord.status == "auto_closed"),
            )
            .where(
                AttendanceRecord.employee_id.in_(ids),
                AttendanceRecord.business_date >= start,
                AttendanceRecord.business_date <= end,
            )
            .group_by(AttendanceRecord.employee_id, AttendanceRecord.business_date)
        )
        for emp, day, minutes, count, review in rows:
            totals[(emp, day)] = (int(minutes or 0), int(count or 0), int(review or 0))
    result = []
    for e in employees:
        days = [
            DayOut(
                date=d,
                minutes=totals[(e.id, d)][0],
                records=totals[(e.id, d)][1],
                needs_review=totals[(e.id, d)][2],
            )
            for d in sorted(day for (emp, day) in totals if emp == e.id)
        ]
        result.append(
            TimesheetRow(
                employee_id=e.id,
                employee_name=e.full_name,
                days=days,
                total_minutes=sum(d.minutes for d in days),
                days_present=sum(1 for d in days if d.records),
            )
        )
    return result


async def timesheet(ctx: Ctx, month: str, employee_id: uuid.UUID | None = None) -> TimesheetOut:
    """Hours per person per day for a month (everyone in scope, or just yourself)."""
    start, end = month_range(month)
    return TimesheetOut(
        month=month, start=start, end=end, rows=await timesheet_rows(ctx, start, end, employee_id)
    )
