"""Attendance rules."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import current_tenant
from app.core.errors import Conflict, Invalid
from app.core.time import local_date, utcnow
from app.modules.attendance.models import MAX_SHIFT_HOURS, AttendanceRecord
from app.modules.people.models import Employee
from app.modules.platform import hooks
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
