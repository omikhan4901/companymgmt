"""Leave rules. Routes are thin wrappers over these functions (and AI tools will be too)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_FLOOR, Decimal

from sqlalchemy import and_, extract, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.errors import Conflict, Forbidden, Invalid, NotFound, PreconditionFailed
from app.core.time import today, utcnow
from app.modules.leave import access, defaults
from app.modules.leave.models import Holiday, LeaveAdjustment, LeavePolicy, LeaveRequest, LeaveType
from app.modules.leave.schemas import (
    AdjustmentIn,
    AdjustmentOut,
    BalanceOut,
    CalendarEntry,
    HolidayIn,
    HolidayOut,
    LeaveTypeIn,
    LeaveTypeOut,
    LeaveTypePatch,
    PersonBalances,
    PolicyIn,
    PolicyOut,
    QuoteOut,
    RequestIn,
    RequestOut,
)
from app.modules.people.access import in_scope, scope_departments
from app.modules.people.models import Employee
from app.modules.people.service import employee_for_membership
from app.modules.platform import hooks
from app.modules.platform.deps import Ctx
from app.modules.platform.models import Branch, Tenant

ZERO = Decimal(0)
HALF = Decimal("0.5")
LIVE = ("pending", "approved")
MAX_CALENDAR_DAYS = 93


def _halves(value: Decimal) -> Decimal:
    """Round down to the nearest half day."""
    return (value * 2).to_integral_value(rounding=ROUND_FLOOR) / 2


def _f(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def local_today(ctx: Ctx) -> date:
    assert ctx.tenant is not None
    return today(ctx.tenant.timezone)


# ---- People -----------------------------------------------------------------------------


async def me(ctx: Ctx) -> Employee:
    assert ctx.membership is not None
    employee = await employee_for_membership(ctx.db, ctx.membership.id)
    if employee is None or employee.status != "active":
        raise Forbidden("You don't have an active profile in this workspace.", code="no_profile")
    return employee


async def _me_or_none(ctx: Ctx) -> Employee | None:
    assert ctx.membership is not None
    return await employee_for_membership(ctx.db, ctx.membership.id)


async def _person(ctx: Ctx, employee_id: uuid.UUID | None, permission: str) -> Employee:
    """Yourself, or someone in your scope when you hold `permission`."""
    own = await _me_or_none(ctx)
    if employee_id is None or (own is not None and own.id == employee_id):
        return await me(ctx)
    if not ctx.can(permission):
        raise NotFound()
    employee = await ctx.db.get(Employee, employee_id)
    if employee is None or not await in_scope(ctx, employee.department_id):
        raise NotFound()
    return employee


# ---- Settings: policy, types, holidays --------------------------------------------------


async def policy(db: AsyncSession) -> LeavePolicy:
    row = await db.scalar(select(LeavePolicy))
    return row or LeavePolicy(weekly_off=defaults.weekly_off_for(None), team_calendar=True)


def _policy_out(row: LeavePolicy) -> PolicyOut:
    return PolicyOut(weekly_off=sorted(row.weekly_off), team_calendar=row.team_calendar)


async def get_policy(ctx: Ctx) -> PolicyOut:
    return _policy_out(await policy(ctx.db))


async def set_policy(ctx: Ctx, body: PolicyIn) -> PolicyOut:
    row = await ctx.db.scalar(select(LeavePolicy).with_for_update())
    before = _policy_out(row).model_dump() if row else None
    if row is None:
        row = LeavePolicy(tenant_id=ctx.tenant_id)
        ctx.db.add(row)
    row.weekly_off = sorted(set(body.weekly_off))
    row.team_calendar = body.team_calendar
    await ctx.db.flush()
    after = _policy_out(row)
    await audit.record(
        ctx.db,
        "leave.policy_changed",
        target_type="workspace",
        target_id=ctx.tenant_id,
        data={"before": before, "after": after.model_dump()},
    )
    await ctx.db.commit()
    return after


async def list_types(ctx: Ctx, *, include_inactive: bool = False) -> list[LeaveTypeOut]:
    query = select(LeaveType).order_by(LeaveType.position, LeaveType.name)
    if not include_inactive:
        query = query.where(LeaveType.active.is_(True))
    return [LeaveTypeOut.model_validate(t) for t in await ctx.db.scalars(query)]


async def _save_type(ctx: Ctx) -> None:
    try:
        async with ctx.db.begin_nested():
            await ctx.db.flush()
    except IntegrityError as exc:
        if "uq_leave_types_name" in str(exc.orig):
            raise Conflict("There's already a leave type with this name.", code="name_taken") from exc
        raise


async def create_type(ctx: Ctx, body: LeaveTypeIn) -> LeaveTypeOut:
    last = await ctx.db.scalar(select(func.max(LeaveType.position)))
    row = LeaveType(**body.model_dump(), position=(last or 0) + 1)
    ctx.db.add(row)
    await _save_type(ctx)
    await audit.record(
        ctx.db,
        "leave.type_created",
        target_type="leave_type",
        target_id=row.id,
        data=body.model_dump(mode="json"),
    )
    await ctx.db.commit()
    return LeaveTypeOut.model_validate(row)


async def leave_type(db: AsyncSession, leave_type_id: uuid.UUID, *, lock: bool = False) -> LeaveType:
    query = select(LeaveType).where(LeaveType.id == leave_type_id)
    row = await db.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise NotFound()
    return row


async def update_type(
    ctx: Ctx, leave_type_id: uuid.UUID, body: LeaveTypePatch, *, version: int | None = None
) -> LeaveTypeOut:
    row = await leave_type(ctx.db, leave_type_id, lock=True)
    if version is not None and version != row.version:
        raise PreconditionFailed()
    changes = body.model_dump(exclude_unset=True, exclude={"unlimited"})
    if body.unlimited:
        changes["days_per_year"] = None
    elif "days_per_year" in changes and changes["days_per_year"] is None:
        del changes["days_per_year"]
    before = {k: getattr(row, k) for k in changes}
    for key, value in changes.items():
        setattr(row, key, value)
    await _save_type(ctx)
    await audit.record(
        ctx.db,
        "leave.type_changed",
        target_type="leave_type",
        target_id=row.id,
        data={"name": row.name, "before": before, "after": changes},
    )
    await ctx.db.commit()
    return LeaveTypeOut.model_validate(row)


async def list_holidays(ctx: Ctx, year: int) -> list[HolidayOut]:
    rows = await ctx.db.scalars(
        select(Holiday)
        .where(Holiday.day >= date(year, 1, 1), Holiday.day <= date(year, 12, 31))
        .order_by(Holiday.day, Holiday.name)
    )
    return [HolidayOut.model_validate(h) for h in rows]


async def add_holiday(ctx: Ctx, body: HolidayIn) -> HolidayOut:
    if body.branch_id is not None and await ctx.db.get(Branch, body.branch_id) is None:
        raise Invalid(errors=[{"field": "branch_id", "message": "Unknown branch."}])
    row = Holiday(day=body.day, name=body.name, branch_id=body.branch_id)
    ctx.db.add(row)
    try:
        async with ctx.db.begin_nested():
            await ctx.db.flush()
    except IntegrityError as exc:
        if "uq_holidays_day" in str(exc.orig):
            raise Conflict("There's already a holiday on this day.", code="holiday_exists") from exc
        raise
    await audit.record(
        ctx.db,
        "leave.holiday_added",
        target_type="holiday",
        target_id=row.id,
        data=body.model_dump(mode="json"),
    )
    await ctx.db.commit()
    return HolidayOut.model_validate(row)


async def remove_holiday(ctx: Ctx, holiday_id: uuid.UUID) -> None:
    row = await ctx.db.get(Holiday, holiday_id)
    if row is None:
        raise NotFound()
    await ctx.db.delete(row)
    await audit.record(
        ctx.db,
        "leave.holiday_removed",
        target_type="holiday",
        target_id=holiday_id,
        data={"day": row.day, "name": row.name},
    )
    await ctx.db.commit()


# ---- Counting days ----------------------------------------------------------------------


async def count_days(
    db: AsyncSession,
    kind: LeaveType,
    employee: Employee,
    start: date,
    end: date,
    half_day: str,
) -> tuple[Decimal, list[date]]:
    """Days a request uses, and the days in the range that don't count."""
    if kind.calendar_days:
        total = Decimal((end - start).days + 1)
        return (HALF if half_day != "none" else total), []
    off = set((await policy(db)).weekly_off)
    holidays = set(
        await db.scalars(
            select(Holiday.day).where(
                Holiday.day >= start,
                Holiday.day <= end,
                or_(Holiday.branch_id.is_(None), Holiday.branch_id == employee.branch_id),
            )
        )
    )
    counted = ZERO
    skipped: list[date] = []
    day = start
    while day <= end:
        if day.isoweekday() in off or day in holidays:
            skipped.append(day)
        else:
            counted += 1
        day += timedelta(days=1)
    if half_day != "none" and counted:
        counted = HALF
    return counted, skipped


# ---- Balances ---------------------------------------------------------------------------


def entitled(kind: LeaveType, joined_on: date | None, year: int, as_of: date) -> Decimal:
    """Days earned in `year` by `as_of`: a share for joining mid-year, and month by month
    for monthly accrual."""
    if kind.days_per_year is None:
        return ZERO
    first_month = 1
    if kind.prorate and joined_on is not None:
        if joined_on.year > year:
            return ZERO
        if joined_on.year == year:
            first_month = joined_on.month
    months = 13 - first_month
    if kind.accrual == "monthly":
        if as_of.year < year:
            months = 0
        elif as_of.year == year:
            months = max(0, min(months, as_of.month - first_month + 1))
    if months == 12:
        return Decimal(kind.days_per_year)
    return _halves(Decimal(kind.days_per_year) * months / 12)


@dataclass
class _Totals:
    used: dict[tuple[uuid.UUID, uuid.UUID, int], Decimal]
    pending: dict[tuple[uuid.UUID, uuid.UUID, int], Decimal]
    adjusted: dict[tuple[uuid.UUID, uuid.UUID, int], Decimal]


async def _totals(db: AsyncSession, employee_ids: list[uuid.UUID], years: Iterable[int]) -> _Totals:
    years = list(years)
    year = extract("year", LeaveRequest.start_date)
    used: dict[tuple[uuid.UUID, uuid.UUID, int], Decimal] = defaultdict(lambda: ZERO)
    pending: dict[tuple[uuid.UUID, uuid.UUID, int], Decimal] = defaultdict(lambda: ZERO)
    adjusted: dict[tuple[uuid.UUID, uuid.UUID, int], Decimal] = defaultdict(lambda: ZERO)
    rows = await db.execute(
        select(
            LeaveRequest.employee_id,
            LeaveRequest.leave_type_id,
            year,
            LeaveRequest.status,
            func.sum(LeaveRequest.days),
        )
        .where(
            LeaveRequest.employee_id.in_(employee_ids),
            LeaveRequest.status.in_(LIVE),
            year.in_(years),
        )
        .group_by(LeaveRequest.employee_id, LeaveRequest.leave_type_id, year, LeaveRequest.status)
    )
    for employee_id, type_id, y, status, days in rows:
        target = used if status == "approved" else pending
        target[(employee_id, type_id, int(y))] += days
    adjustments = await db.execute(
        select(
            LeaveAdjustment.employee_id,
            LeaveAdjustment.leave_type_id,
            LeaveAdjustment.year,
            func.sum(LeaveAdjustment.days),
        )
        .where(LeaveAdjustment.employee_id.in_(employee_ids), LeaveAdjustment.year.in_(years))
        .group_by(LeaveAdjustment.employee_id, LeaveAdjustment.leave_type_id, LeaveAdjustment.year)
    )
    for employee_id, type_id, y, days in adjustments:
        adjusted[(employee_id, type_id, int(y))] += days
    return _Totals(used, pending, adjusted)


def _balance(kind: LeaveType, employee: Employee, year: int, as_of: date, totals: _Totals) -> BalanceOut:
    key = (employee.id, kind.id, year)
    used, pending, adjusted = totals.used[key], totals.pending[key], totals.adjusted[key]
    unlimited = kind.days_per_year is None
    carried = ZERO
    if not unlimited and kind.carry_over_max > 0:
        # One level only: what was left of last year's own days, up to the limit.
        last = (employee.id, kind.id, year - 1)
        left = (
            entitled(kind, employee.joined_on, year - 1, date(year - 1, 12, 31))
            + totals.adjusted[last]
            - totals.used[last]
            - totals.pending[last]
        )
        carried = min(max(left, ZERO), Decimal(kind.carry_over_max))
    earned = entitled(kind, employee.joined_on, year, as_of)
    full_year = None if unlimited else entitled(kind, employee.joined_on, year, date(year, 12, 31))
    available = None if unlimited else earned + carried + adjusted - used - pending
    return BalanceOut(
        leave_type_id=kind.id,
        name=kind.name,
        paid=kind.paid,
        color=kind.color,
        unlimited=unlimited,
        entitled=float(earned),
        full_year=_f(full_year),
        carried_over=float(carried),
        adjusted=float(adjusted),
        used=float(used),
        pending=float(pending),
        available=_f(available),
    )


async def balances(
    db: AsyncSession, employees: list[Employee], year: int, as_of: date, kinds: list[LeaveType] | None = None
) -> dict[uuid.UUID, list[BalanceOut]]:
    if kinds is None:
        kinds = list(
            await db.scalars(
                select(LeaveType)
                .where(LeaveType.active.is_(True))
                .order_by(LeaveType.position, LeaveType.name)
            )
        )
    totals = await _totals(db, [e.id for e in employees], (year - 1, year))
    return {e.id: [_balance(k, e, year, as_of, totals) for k in kinds] for e in employees}


async def person_balances(ctx: Ctx, employee_id: uuid.UUID | None, year: int | None) -> PersonBalances:
    employee = await _person(ctx, employee_id, access.VIEW)
    now = local_today(ctx)
    year = year or now.year
    result = await balances(ctx.db, [employee], year, now)
    return PersonBalances(
        employee_id=employee.id, employee_name=employee.full_name, year=year, balances=result[employee.id]
    )


async def team_balances(ctx: Ctx, year: int | None) -> list[PersonBalances]:
    now = local_today(ctx)
    year = year or now.year
    query = select(Employee).where(Employee.status == "active").order_by(func.lower(Employee.full_name))
    scope = await scope_departments(ctx)
    if scope is not None:
        query = query.where(Employee.department_id.in_(scope))
    people = list(await ctx.db.scalars(query.limit(1000)))
    result = await balances(ctx.db, people, year, now)
    return [
        PersonBalances(employee_id=e.id, employee_name=e.full_name, year=year, balances=result[e.id])
        for e in people
    ]


async def _available(
    db: AsyncSession, kind: LeaveType, employee: Employee, year: int, as_of: date
) -> Decimal | None:
    if kind.days_per_year is None:
        return None
    result = await balances(db, [employee], year, as_of, [kind])
    available = result[employee.id][0].available
    return None if available is None else Decimal(str(available))


# ---- Requests ---------------------------------------------------------------------------


async def _check_range(ctx: Ctx, kind: LeaveType, start: date, end: date, half_day: str) -> None:
    if end < start:
        raise Invalid(errors=[{"field": "end_date", "message": "The end date is before the start date."}])
    if start.year != end.year:
        raise Invalid(
            "Leave can't cross into a new year. Split it into two requests.",
            code="crosses_year",
            errors=[{"field": "end_date", "message": "Split it into two requests, one per year."}],
        )
    now = local_today(ctx)
    if start.year < now.year - 1 or end.year > now.year + 1:
        raise Invalid(errors=[{"field": "start_date", "message": "Choose dates within a year of today."}])
    if half_day != "none":
        if start != end:
            raise Invalid(errors=[{"field": "half_day", "message": "A half day is a single day."}])
        if not kind.allow_half_day:
            raise Invalid(errors=[{"field": "half_day", "message": f"{kind.name} can't be taken by halves."}])


async def quote(
    ctx: Ctx,
    leave_type_id: uuid.UUID,
    start: date,
    end: date,
    half_day: str,
    employee_id: uuid.UUID | None = None,
) -> QuoteOut:
    employee = await _person(ctx, employee_id, access.MANAGE)
    kind = await leave_type(ctx.db, leave_type_id)
    await _check_range(ctx, kind, start, end, half_day)
    days, skipped = await count_days(ctx.db, kind, employee, start, end, half_day)
    available = await _available(ctx.db, kind, employee, start.year, max(local_today(ctx), start))
    return QuoteOut(
        days=float(days),
        available=_f(available),
        enough=bool(days) and (available is None or days <= available),
        skipped=skipped,
    )


async def _save_request(db: AsyncSession) -> None:
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        if "leave_no_overlap" in str(exc.orig):
            raise Conflict(
                "There's already leave asked for or approved on some of these days.", code="overlap"
            ) from exc
        raise


async def _lock_person(db: AsyncSession, employee_id: uuid.UUID) -> None:
    """Serialise balance checks for one person (two requests at once can't both fit)."""
    await db.execute(select(Employee.id).where(Employee.id == employee_id).with_for_update())


def _not_enough(kind: LeaveType, available: Decimal) -> Invalid:
    return Invalid(
        f"Not enough {kind.name.lower()} left: {available.normalize():f} days available.",
        code="not_enough_balance",
        extra={"available": float(available)},
    )


async def create_request(ctx: Ctx, body: RequestIn) -> RequestOut:
    employee = await _person(ctx, body.employee_id, access.MANAGE)
    if employee.status != "active":
        raise Invalid(errors=[{"field": "employee_id", "message": "This person is no longer active."}])
    kind = await leave_type(ctx.db, body.leave_type_id)
    if not kind.active:
        raise Invalid(errors=[{"field": "leave_type_id", "message": "This leave type is switched off."}])
    await _check_range(ctx, kind, body.start_date, body.end_date, body.half_day)
    await _lock_person(ctx.db, employee.id)
    days, _ = await count_days(ctx.db, kind, employee, body.start_date, body.end_date, body.half_day)
    if not days:
        raise Invalid(
            "These are all days off already.",
            code="no_working_days",
            errors=[
                {"field": "end_date", "message": "Every day in this range is a weekly off or a holiday."}
            ],
        )
    available = await _available(
        ctx.db, kind, employee, body.start_date.year, max(local_today(ctx), body.start_date)
    )
    if available is not None and days > available:
        raise _not_enough(kind, available)
    row = LeaveRequest(
        employee_id=employee.id,
        leave_type_id=kind.id,
        start_date=body.start_date,
        end_date=body.end_date,
        half_day=body.half_day,
        days=days,
        reason=body.reason or None,
        status="pending",
        requested_by=ctx.user.id,
    )
    ctx.db.add(row)
    await _save_request(ctx.db)
    await audit.record(
        ctx.db,
        "leave.requested",
        target_type="leave_request",
        target_id=row.id,
        data=_audit_data(row, employee, kind),
    )
    await ctx.db.commit()
    return _out(row, employee.full_name, kind.name)


def _audit_data(row: LeaveRequest, employee: Employee, kind: LeaveType) -> dict[str, object]:
    # The reason stays out of the audit log: it can hold health details.
    return {
        "employee": employee.full_name,
        "type": kind.name,
        "start_date": row.start_date,
        "end_date": row.end_date,
        "days": row.days,
    }


def _out(row: LeaveRequest, employee_name: str | None, type_name: str | None) -> RequestOut:
    out = RequestOut.model_validate(row)
    out.employee_name = employee_name
    out.leave_type_name = type_name
    return out


async def list_requests(
    ctx: Ctx,
    *,
    status: str = "all",
    mine: bool = False,
    employee_id: uuid.UUID | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[RequestOut]:
    query = (
        select(LeaveRequest, Employee.full_name, LeaveType.name)
        .join(
            Employee,
            and_(Employee.tenant_id == LeaveRequest.tenant_id, Employee.id == LeaveRequest.employee_id),
        )
        .join(
            LeaveType,
            and_(LeaveType.tenant_id == LeaveRequest.tenant_id, LeaveType.id == LeaveRequest.leave_type_id),
        )
    )
    sees_others = ctx.can(access.VIEW) or ctx.can(access.APPROVE)
    if mine or not sees_others:
        own = await me(ctx)
        if employee_id is not None and employee_id != own.id:
            raise NotFound()
        query = query.where(LeaveRequest.employee_id == own.id)
    else:
        scope = await scope_departments(ctx)
        if scope is not None:
            own_or_none = await _me_or_none(ctx)
            query = query.where(
                Employee.department_id.in_(scope) | (Employee.id == (own_or_none.id if own_or_none else None))
            )
        if employee_id is not None:
            query = query.where(LeaveRequest.employee_id == employee_id)
    if status != "all":
        query = query.where(LeaveRequest.status == status)
    if start is not None:
        query = query.where(LeaveRequest.end_date >= start)
    if end is not None:
        query = query.where(LeaveRequest.start_date <= end)
    order = (
        (LeaveRequest.start_date.asc(), LeaveRequest.created_at.asc())
        if status == "pending"
        else (LeaveRequest.start_date.desc(), LeaveRequest.created_at.desc())
    )
    rows = (await ctx.db.execute(query.order_by(*order).limit(500))).all()
    return [_out(r, name, type_name) for r, name, type_name in rows]


async def _locked_request(ctx: Ctx, request_id: uuid.UUID) -> tuple[LeaveRequest, Employee, LeaveType]:
    row = await ctx.db.scalar(select(LeaveRequest).where(LeaveRequest.id == request_id).with_for_update())
    if row is None:
        raise NotFound()
    employee = await ctx.db.get(Employee, row.employee_id)
    kind = await ctx.db.get(LeaveType, row.leave_type_id)
    assert employee is not None
    assert kind is not None
    return row, employee, kind


async def _decidable(ctx: Ctx, request_id: uuid.UUID) -> tuple[LeaveRequest, Employee, LeaveType]:
    row, employee, kind = await _locked_request(ctx, request_id)
    if not await in_scope(ctx, employee.department_id):
        raise NotFound()
    if row.status != "pending":
        raise Conflict("This request was already decided.", code="already_decided")
    return row, employee, kind


def _decide(ctx: Ctx, row: LeaveRequest, status: str, note: str | None) -> None:
    row.status = status
    row.decided_by = ctx.user.id
    row.decided_at = utcnow()
    row.decision_note = note or None


async def approve(ctx: Ctx, request_id: uuid.UUID, note: str | None) -> RequestOut:
    row, employee, kind = await _decidable(ctx, request_id)
    if ctx.membership is not None and employee.membership_id == ctx.membership.id and not ctx.is_owner:
        raise Forbidden("Someone else has to approve your own leave.", code="self_approval")
    await _lock_person(ctx.db, employee.id)
    # Balances can change after asking (a smaller type, an adjustment): check again. This
    # request is already counted as pending, so it fits while nothing is overdrawn.
    as_of = max(local_today(ctx), row.start_date)
    available = await _available(ctx.db, kind, employee, row.start_date.year, as_of)
    if available is not None and available < 0:
        raise _not_enough(kind, available + row.days)
    _decide(ctx, row, "approved", note)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "leave.approved",
        target_type="leave_request",
        target_id=row.id,
        data=_audit_data(row, employee, kind),
    )
    await ctx.db.commit()
    return _out(row, employee.full_name, kind.name)


async def reject(ctx: Ctx, request_id: uuid.UUID, note: str | None) -> RequestOut:
    row, employee, kind = await _decidable(ctx, request_id)
    _decide(ctx, row, "rejected", note)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "leave.rejected",
        target_type="leave_request",
        target_id=row.id,
        data={**_audit_data(row, employee, kind), "note": note},
    )
    await ctx.db.commit()
    return _out(row, employee.full_name, kind.name)


async def cancel(ctx: Ctx, request_id: uuid.UUID, note: str | None) -> RequestOut:
    row, employee, kind = await _locked_request(ctx, request_id)
    own = await _me_or_none(ctx)
    is_own = own is not None and own.id == employee.id
    may_approve = ctx.can(access.APPROVE) and await in_scope(ctx, employee.department_id)
    if not is_own and not may_approve:
        raise NotFound()
    if row.status not in LIVE:
        raise Conflict("This request is already closed.", code="already_decided")
    if is_own and not may_approve and row.status == "approved" and row.start_date <= local_today(ctx):
        raise Conflict(
            "This leave has already started. Ask your manager to change it.", code="already_started"
        )
    _decide(ctx, row, "cancelled", note)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "leave.cancelled",
        target_type="leave_request",
        target_id=row.id,
        data={**_audit_data(row, employee, kind), "by_owner_of_request": is_own},
    )
    await ctx.db.commit()
    return _out(row, employee.full_name, kind.name)


# ---- Who's away -------------------------------------------------------------------------


async def calendar(ctx: Ctx, start: date, end: date) -> list[CalendarEntry]:
    if end < start:
        raise Invalid(errors=[{"field": "to", "message": "The end date is before the start date."}])
    if (end - start).days >= MAX_CALENDAR_DAYS:
        raise Invalid(errors=[{"field": "to", "message": f"Choose at most {MAX_CALENDAR_DAYS} days."}])
    query = (
        select(LeaveRequest, Employee, LeaveType)
        .join(
            Employee,
            and_(Employee.tenant_id == LeaveRequest.tenant_id, Employee.id == LeaveRequest.employee_id),
        )
        .join(
            LeaveType,
            and_(LeaveType.tenant_id == LeaveRequest.tenant_id, LeaveType.id == LeaveRequest.leave_type_id),
        )
        .where(LeaveRequest.end_date >= start, LeaveRequest.start_date <= end, LeaveRequest.status.in_(LIVE))
    )
    own = await _me_or_none(ctx)
    full = ctx.can(access.VIEW)
    if full:
        scope = await scope_departments(ctx)
        if scope is not None:
            query = query.where(
                Employee.department_id.in_(scope) | (Employee.id == (own.id if own else None))
            )
    else:
        # Colleagues see that someone in their department is away, not why, and only once
        # it is approved.
        mine = LeaveRequest.employee_id == (own.id if own else None)
        if (await policy(ctx.db)).team_calendar and own is not None:
            same_team = Employee.department_id.is_not_distinct_from(own.department_id)
            query = query.where(mine | (same_team & (LeaveRequest.status == "approved")))
        else:
            query = query.where(mine)
    rows = (
        await ctx.db.execute(query.order_by(LeaveRequest.start_date, Employee.full_name).limit(1000))
    ).all()
    entries = []
    for row, employee, kind in rows:
        detailed = full or (own is not None and employee.id == own.id)
        entries.append(
            CalendarEntry(
                employee_id=employee.id,
                employee_name=employee.preferred_name or employee.full_name,
                start_date=row.start_date,
                end_date=row.end_date,
                half_day=row.half_day,
                status=row.status,
                leave_type_name=kind.name if detailed else None,
                color=kind.color if detailed else None,
            )
        )
    return entries


# ---- Adjustments ------------------------------------------------------------------------


async def add_adjustment(ctx: Ctx, body: AdjustmentIn) -> AdjustmentOut:
    employee = await ctx.db.get(Employee, body.employee_id)
    if employee is None or not await in_scope(ctx, employee.department_id):
        raise NotFound()
    kind = await leave_type(ctx.db, body.leave_type_id)
    if kind.days_per_year is None:
        raise Invalid(errors=[{"field": "leave_type_id", "message": f"{kind.name} has no limit to adjust."}])
    if body.days == 0:
        raise Invalid(errors=[{"field": "days", "message": "Add or remove at least half a day."}])
    row = LeaveAdjustment(
        employee_id=employee.id,
        leave_type_id=kind.id,
        year=body.year,
        days=body.days,
        reason=body.reason,
        created_by=ctx.user.id,
    )
    ctx.db.add(row)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "leave.adjusted",
        target_type="leave_adjustment",
        target_id=row.id,
        data={
            "employee": employee.full_name,
            "type": kind.name,
            "year": body.year,
            "days": body.days,
            "reason": body.reason,
        },
    )
    await ctx.db.commit()
    await ctx.db.refresh(row)
    return AdjustmentOut.model_validate(row)


async def list_adjustments(ctx: Ctx, employee_id: uuid.UUID | None, year: int | None) -> list[AdjustmentOut]:
    employee = await _person(ctx, employee_id, access.VIEW)
    query = select(LeaveAdjustment).where(LeaveAdjustment.employee_id == employee.id)
    if year is not None:
        query = query.where(LeaveAdjustment.year == year)
    rows = await ctx.db.scalars(query.order_by(LeaveAdjustment.created_at.desc()).limit(500))
    return [AdjustmentOut.model_validate(r) for r in rows]


# ---- Switching the module on ------------------------------------------------------------


async def seed(db: AsyncSession, tenant: Tenant, module: str) -> None:
    """Give a workspace sensible leave types and a work week the first time Leave is on."""
    if module != "leave":
        return
    if await db.scalar(select(LeavePolicy)) is None:
        db.add(LeavePolicy(weekly_off=defaults.weekly_off_for(tenant.country), team_calendar=True))
    if not await db.scalar(select(func.count()).select_from(LeaveType)):
        for position, d in enumerate(defaults.types_for(tenant.country), start=1):
            db.add(
                LeaveType(
                    position=position,
                    name=d.name,
                    paid=d.paid,
                    days_per_year=d.days_per_year,
                    accrual=d.accrual,
                    carry_over_max=d.carry_over_max,
                    allow_half_day=d.allow_half_day,
                    calendar_days=d.calendar_days,
                    prorate=d.prorate,
                    color=d.color,
                )
            )
    await db.flush()


def register_hooks() -> None:
    if seed not in hooks.module_enabled:
        hooks.module_enabled.append(seed)
