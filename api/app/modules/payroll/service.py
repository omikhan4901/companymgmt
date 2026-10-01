"""Payroll rules. Routes are thin wrappers over these functions (and AI tools will be too).

A run moves draft → review → finalized → paid:
- draft: computed from salaries, attendance, unpaid leave, advances and one-off items;
  recomputed on demand while it's a draft.
- review: submitted by whoever prepared it; frozen.
- finalized: approved by someone else (or the owner). Payslips become visible to people,
  advances are repaid and shortfalls become advances for next month.
- paid: marked once the money is sent. Nothing changes after that.
"""

from __future__ import annotations

import csv
import io
import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import anyio
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit, events
from app.core.errors import Conflict, Forbidden, Invalid, NotFound
from app.core.security import crypto
from app.core.spreadsheet import safe_cell
from app.core.time import today, utcnow
from app.modules.attendance.models import AttendanceRecord
from app.modules.leave.models import LeaveRequest, LeaveType
from app.modules.leave.service import count_days
from app.modules.payroll import access, calc, defaults, pdf
from app.modules.payroll.models import Loan, PayItem, PayrollRun, PayrollSettings, Payslip, SalaryStructure
from app.modules.payroll.schemas import (
    ItemIn,
    ItemOut,
    LoanIn,
    LoanOut,
    PayrollSettingsIn,
    PayrollSettingsOut,
    PayslipOut,
    RunDetail,
    RunIn,
    RunOut,
    StructureIn,
    StructureOut,
    TaxTable,
)
from app.modules.people.access import in_scope, scope_departments
from app.modules.people.models import Department, Employee
from app.modules.people.service import employee_for_membership
from app.modules.platform import hooks
from app.modules.platform.deps import Ctx
from app.modules.platform.models import Tenant


def _currency(ctx: Ctx) -> str:
    assert ctx.tenant is not None
    return ctx.tenant.currency


def _today(ctx: Ctx) -> date:
    assert ctx.tenant is not None
    return today(ctx.tenant.timezone)


# ---- Settings ---------------------------------------------------------------------------


async def settings(db: AsyncSession, tenant: Tenant) -> PayrollSettings:
    row = await db.scalar(select(PayrollSettings))
    return row or PayrollSettings(version=0, round_net=True, **defaults.settings_for(tenant.country))


def rules(row: PayrollSettings, currency: str) -> calc.Rules:
    return calc.Rules(
        day_basis=row.day_basis,
        hours_per_day=row.hours_per_day,
        overtime_multiplier=Decimal(row.overtime_multiplier),
        overtime_divisor=row.overtime_divisor,
        bonus_percent=row.bonus_percent,
        bonus_min_months=row.bonus_min_months,
        round_net=row.round_net,
        unit=defaults.unit_for(currency),
        tax=row.tax_table if row.tax_enabled and row.tax_table.get("slabs") else None,
    )


def _settings_out(row: PayrollSettings, currency: str) -> PayrollSettingsOut:
    return PayrollSettingsOut(
        currency=currency,
        day_basis=row.day_basis,
        hours_per_day=row.hours_per_day,
        overtime_multiplier=float(row.overtime_multiplier),
        overtime_divisor=row.overtime_divisor,
        bonus_percent=row.bonus_percent,
        bonus_min_months=row.bonus_min_months,
        round_net=row.round_net,
        tax_enabled=row.tax_enabled,
        tax_table=TaxTable.from_rules(row.tax_table or {}),
        version=row.version or 0,
    )


async def get_settings(ctx: Ctx) -> PayrollSettingsOut:
    assert ctx.tenant is not None
    return _settings_out(await settings(ctx.db, ctx.tenant), _currency(ctx))


async def put_settings(ctx: Ctx, body: PayrollSettingsIn) -> PayrollSettingsOut:
    if body.tax_enabled and not body.tax_table.slabs:
        raise Invalid(errors=[{"field": "tax_table", "message": "Add the tax slabs before turning tax on."}])
    row = await ctx.db.scalar(select(PayrollSettings).with_for_update())
    before = _settings_out(row, _currency(ctx)).model_dump(mode="json") if row else None
    if row is None:
        row = PayrollSettings(tenant_id=ctx.tenant_id)
        ctx.db.add(row)
    values = body.model_dump(exclude={"tax_table"})
    for key, value in values.items():
        setattr(row, key, value)
    row.tax_table = body.tax_table.to_rules()
    await ctx.db.flush()
    after = _settings_out(row, _currency(ctx))
    await audit.record(
        ctx.db,
        "payroll.settings_changed",
        target_type="workspace",
        target_id=ctx.tenant_id,
        data={"before": before, "after": after.model_dump(mode="json")},
    )
    await ctx.db.commit()
    return after


# ---- Salary structures ------------------------------------------------------------------


def _structure_out(s: SalaryStructure, name: str | None = None) -> StructureOut:
    out = StructureOut.model_validate(s)
    out.employee_name = name
    out.monthly_total = s.basic + s.house_rent + s.medical + s.conveyance + s.other
    return out


async def current_structures(ctx: Ctx, on: date | None = None) -> list[StructureOut]:
    """Each active person's salary in force on `on` (default today)."""
    on = on or _today(ctx)
    latest = (
        select(SalaryStructure.employee_id, func.max(SalaryStructure.effective_from).label("since"))
        .where(SalaryStructure.effective_from <= on)
        .group_by(SalaryStructure.employee_id)
        .subquery()
    )
    rows = await ctx.db.execute(
        select(SalaryStructure, Employee.full_name)
        .join(
            latest,
            and_(
                latest.c.employee_id == SalaryStructure.employee_id,
                latest.c.since == SalaryStructure.effective_from,
            ),
        )
        .join(
            Employee,
            and_(Employee.tenant_id == SalaryStructure.tenant_id, Employee.id == SalaryStructure.employee_id),
        )
        .where(Employee.status == "active")
        .order_by(func.lower(Employee.full_name))
    )
    return [_structure_out(s, name) for s, name in rows]


async def history(ctx: Ctx, employee_id: uuid.UUID) -> list[StructureOut]:
    employee = await ctx.db.get(Employee, employee_id)
    if employee is None:
        raise NotFound()
    rows = await ctx.db.scalars(
        select(SalaryStructure)
        .where(SalaryStructure.employee_id == employee_id)
        .order_by(SalaryStructure.effective_from.desc())
    )
    return [_structure_out(s, employee.full_name) for s in rows]


def _account_context(structure_id: uuid.UUID) -> str:
    return f"salary_structure:{structure_id}:account"


async def set_structure(ctx: Ctx, body: StructureIn) -> StructureOut:
    employee = await ctx.db.get(Employee, body.employee_id)
    if employee is None:
        raise NotFound()
    monthly_total = body.basic + body.house_rent + body.medical + body.conveyance + body.other
    # A volunteer or intern on zero pay is allowed, but only with a note saying so.
    if body.pay_rule == "monthly" and monthly_total == 0 and not body.note:
        raise Invalid(
            errors=[{"field": "basic", "message": "Enter the salary, or add a note for unpaid roles."}]
        )
    if body.pay_rule != "monthly" and body.rate == 0 and not body.note:
        raise Invalid(errors=[{"field": "rate", "message": "Enter the rate."}])
    if body.payment_method != "cash" and not body.provider:
        raise Invalid(errors=[{"field": "provider", "message": "Name the bank or mobile wallet."}])
    previous = await ctx.db.scalar(
        select(SalaryStructure)
        .where(SalaryStructure.employee_id == employee.id)
        .order_by(SalaryStructure.effective_from.desc())
        .limit(1)
    )
    existing = await ctx.db.scalar(
        select(SalaryStructure).where(
            SalaryStructure.employee_id == employee.id, SalaryStructure.effective_from == body.effective_from
        )
    )
    row = existing or SalaryStructure(employee_id=employee.id, effective_from=body.effective_from)
    if existing is None:
        ctx.db.add(row)
    for key, value in body.model_dump(exclude={"employee_id", "effective_from", "account"}).items():
        setattr(row, key, value)
    row.created_by = ctx.user.id
    await ctx.db.flush()
    if body.payment_method == "cash":
        row.account_enc = None
        row.account_last4 = None
    elif body.account:
        digits = "".join(ch for ch in body.account if ch.isdigit())
        row.account_enc = crypto.encrypt(digits, context=_account_context(row.id))
        row.account_last4 = digits[-4:]
    elif previous is not None and previous.id != row.id and previous.account_enc:
        # Same account as before, re-encrypted for this row.
        plain = crypto.decrypt(previous.account_enc, context=_account_context(previous.id))
        row.account_enc = crypto.encrypt(plain, context=_account_context(row.id))
        row.account_last4 = previous.account_last4
    await audit.record(
        ctx.db,
        "payroll.salary_set",
        target_type="employee",
        target_id=employee.id,
        data={
            "employee": employee.full_name,
            "effective_from": body.effective_from,
            "pay_rule": body.pay_rule,
            "monthly_total": body.basic + body.house_rent + body.medical + body.conveyance + body.other,
            "rate": body.rate,
            "payment_method": body.payment_method,
        },
    )
    await ctx.db.commit()
    return _structure_out(row, employee.full_name)


# ---- Advances and loans -----------------------------------------------------------------


async def list_loans(ctx: Ctx, employee_id: uuid.UUID | None, include_closed: bool) -> list[LoanOut]:
    query = select(Loan, Employee.full_name).join(
        Employee, and_(Employee.tenant_id == Loan.tenant_id, Employee.id == Loan.employee_id)
    )
    if employee_id:
        query = query.where(Loan.employee_id == employee_id)
    if not include_closed:
        query = query.where(Loan.status == "active")
    rows = await ctx.db.execute(query.order_by(Loan.created_at.desc()).limit(1000))
    out = []
    for loan, name in rows:
        item = LoanOut.model_validate(loan)
        item.employee_name = name
        out.append(item)
    return out


async def add_loan(ctx: Ctx, body: LoanIn) -> LoanOut:
    employee = await ctx.db.get(Employee, body.employee_id)
    if employee is None:
        raise NotFound()
    if body.installment > body.principal:
        raise Invalid(
            errors=[{"field": "installment", "message": "The installment is more than the amount."}]
        )
    loan = Loan(
        employee_id=employee.id,
        kind=body.kind,
        label=body.label,
        principal=body.principal,
        installment=body.installment,
        outstanding=body.principal,
        start_period=body.start_period,
        status="active",
        created_by=ctx.user.id,
    )
    ctx.db.add(loan)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "payroll.loan_added",
        target_type="payroll_loan",
        target_id=loan.id,
        data={
            "employee": employee.full_name,
            "kind": body.kind,
            "principal": body.principal,
            "installment": body.installment,
        },
    )
    await ctx.db.commit()
    out = LoanOut.model_validate(loan)
    out.employee_name = employee.full_name
    return out


async def close_loan(ctx: Ctx, loan_id: uuid.UUID) -> LoanOut:
    loan = await ctx.db.scalar(select(Loan).where(Loan.id == loan_id).with_for_update())
    if loan is None:
        raise NotFound()
    if loan.status == "closed":
        raise Conflict("This is already closed.", code="already_closed")
    loan.status = "closed"
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "payroll.loan_closed",
        target_type="payroll_loan",
        target_id=loan.id,
        data={"outstanding_written_off": loan.outstanding},
    )
    await ctx.db.commit()
    return LoanOut.model_validate(loan)


# ---- Runs -------------------------------------------------------------------------------


async def _run(ctx: Ctx, run_id: uuid.UUID, *, lock: bool = False) -> PayrollRun:
    query = select(PayrollRun).where(PayrollRun.id == run_id)
    run = await ctx.db.scalar(query.with_for_update() if lock else query)
    if run is None:
        raise NotFound()
    return run


async def list_runs(ctx: Ctx) -> list[RunOut]:
    query = select(PayrollRun).order_by(PayrollRun.period.desc()).limit(120)
    if not (ctx.can(access.RUN) or ctx.can(access.APPROVE)):
        query = query.where(PayrollRun.status.in_(("finalized", "paid")))
    return [RunOut.model_validate(r) for r in await ctx.db.scalars(query)]


async def create_run(ctx: Ctx, body: RunIn) -> RunDetail:
    start, _ = calc.period_bounds(body.period)
    if start > _today(ctx).replace(day=1) + timedelta(days=62):
        raise Invalid(
            errors=[{"field": "period", "message": "Choose this month, a past month or next month."}]
        )
    run = PayrollRun(
        period=body.period,
        status="draft",
        bonus_label=body.bonus_label or None,
        currency=_currency(ctx),
        created_by=ctx.user.id,
    )
    ctx.db.add(run)
    try:
        async with ctx.db.begin_nested():
            await ctx.db.flush()
    except IntegrityError as exc:
        if "uq_payroll_runs_tenant_id_period" in str(exc.orig):
            raise Conflict("There's already a payroll for this month.", code="run_exists") from exc
        raise
    await compute(ctx, run)
    await audit.record(
        ctx.db,
        "payroll.run_created",
        target_type="payroll_run",
        target_id=run.id,
        data={"period": run.period, "bonus": run.bonus_label, "headcount": run.headcount, "net": run.net},
    )
    await ctx.db.commit()
    return await run_detail(ctx, run.id)


async def recompute(ctx: Ctx, run_id: uuid.UUID) -> RunDetail:
    run = await _run(ctx, run_id, lock=True)
    _require_status(run, "draft")
    await compute(ctx, run)
    await ctx.db.commit()
    return await run_detail(ctx, run.id)


def _require_status(run: PayrollRun, *allowed: str) -> None:
    if run.status not in allowed:
        raise Conflict(f"This payroll is {run.status}, so it can't be changed that way.", code="wrong_status")


async def _people(db: AsyncSession, start: date, end: date) -> list[Employee]:
    """Everyone employed for at least a day of the period."""
    return list(
        await db.scalars(
            select(Employee)
            .where(
                or_(Employee.joined_on.is_(None), Employee.joined_on <= end),
                or_(Employee.left_on.is_(None), Employee.left_on >= start),
                or_(Employee.status == "active", Employee.left_on >= start),
            )
            .order_by(func.lower(Employee.full_name))
        )
    )


async def _structures(db: AsyncSession, end: date) -> dict[uuid.UUID, SalaryStructure]:
    found: dict[uuid.UUID, SalaryStructure] = {}
    for s in await db.scalars(
        select(SalaryStructure)
        .where(SalaryStructure.effective_from <= end)
        .order_by(SalaryStructure.effective_from)
    ):
        found[s.employee_id] = s  # later ones replace earlier ones
    return found


async def _worked(db: AsyncSession, start: date, end: date) -> dict[uuid.UUID, dict[date, int]]:
    rows = await db.execute(
        select(
            AttendanceRecord.employee_id, AttendanceRecord.business_date, func.sum(AttendanceRecord.minutes)
        )
        .where(
            AttendanceRecord.business_date >= start,
            AttendanceRecord.business_date <= end,
            AttendanceRecord.minutes.is_not(None),
        )
        .group_by(AttendanceRecord.employee_id, AttendanceRecord.business_date)
    )
    out: dict[uuid.UUID, dict[date, int]] = defaultdict(dict)
    for employee_id, day, minutes in rows:
        out[employee_id][day] = int(minutes or 0)
    return out


async def _unpaid_leave(
    db: AsyncSession, people: dict[uuid.UUID, Employee], start: date, end: date
) -> dict[uuid.UUID, Decimal]:
    rows = await db.execute(
        select(LeaveRequest, LeaveType)
        .join(
            LeaveType,
            and_(LeaveType.tenant_id == LeaveRequest.tenant_id, LeaveType.id == LeaveRequest.leave_type_id),
        )
        .where(
            LeaveRequest.status == "approved",
            LeaveType.paid.is_(False),
            LeaveRequest.end_date >= start,
            LeaveRequest.start_date <= end,
        )
    )
    out: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    for request, kind in rows:
        employee = people.get(request.employee_id)
        if employee is None:
            continue
        if request.start_date >= start and request.end_date <= end:
            out[employee.id] += Decimal(request.days)
        else:
            days, _ = await count_days(
                db,
                kind,
                employee,
                max(request.start_date, start),
                min(request.end_date, end),
                request.half_day,
            )
            out[employee.id] += days
    return out


async def _loans(db: AsyncSession, period: str) -> dict[uuid.UUID, list[calc.LoanDue]]:
    out: dict[uuid.UUID, list[calc.LoanDue]] = defaultdict(list)
    for loan in await db.scalars(
        select(Loan)
        .where(Loan.status == "active", Loan.outstanding > 0, Loan.start_period <= period)
        .order_by(Loan.created_at)
    ):
        out[loan.employee_id].append(
            calc.LoanDue(str(loan.id), loan.label, loan.installment, loan.outstanding)
        )
    return out


async def compute(ctx: Ctx, run: PayrollRun) -> None:
    """(Re)build every payslip of a draft run from current data."""
    assert ctx.tenant is not None
    start, end = calc.period_bounds(run.period)
    rule = rules(await settings(ctx.db, ctx.tenant), run.currency)
    people = await _people(ctx.db, start, end)
    by_id = {p.id: p for p in people}
    structures = await _structures(ctx.db, end)
    worked = await _worked(ctx.db, start, end)
    unpaid = await _unpaid_leave(ctx.db, by_id, start, end)
    loans = await _loans(ctx.db, run.period)
    items: dict[uuid.UUID, list[calc.Item]] = defaultdict(list)
    for item in await ctx.db.scalars(
        select(PayItem).where(PayItem.run_id == run.id).order_by(PayItem.created_at)
    ):
        items[item.employee_id].append(calc.Item(item.kind, item.label, item.amount, str(item.id)))
    departments = {d.id: d.name for d in await ctx.db.scalars(select(Department))}

    await ctx.db.execute(delete(Payslip).where(Payslip.run_id == run.id))
    totals = {"gross": 0, "deductions": 0, "net": 0}
    count = 0
    for person in people:
        s = structures.get(person.id)
        if s is None:
            continue
        result = calc.calculate(
            calc.Inputs(
                period=run.period,
                structure=calc.Structure(
                    pay_rule=s.pay_rule,
                    basic=s.basic,
                    house_rent=s.house_rent,
                    medical=s.medical,
                    conveyance=s.conveyance,
                    other=s.other,
                    rate=s.rate,
                    overtime=s.overtime,
                    deduct_tax=s.deduct_tax,
                    tax_free_override=s.tax_free_override,
                ),
                joined_on=person.joined_on,
                left_on=person.left_on,
                unpaid_leave_days=unpaid.get(person.id, Decimal(0)),
                worked=worked.get(person.id, {}),
                bonus_label=run.bonus_label,
                loans=loans.get(person.id, ()),
                items=items.get(person.id, ()),
            ),
            rule,
        )
        ctx.db.add(
            Payslip(
                run_id=run.id,
                employee_id=person.id,
                employee_name=person.full_name,
                employee_code=person.employee_code,
                department_id=person.department_id,
                department_name=departments.get(person.department_id) if person.department_id else None,
                job_title=person.job_title,
                pay_rule=s.pay_rule,
                structure_id=s.id,
                days_in_period=result.days_in_period,
                payable_days=result.payable_days,
                unpaid_leave_days=min(unpaid.get(person.id, Decimal(0)), Decimal(result.days_in_period)),
                worked_minutes=result.worked_minutes,
                overtime_minutes=result.overtime_minutes,
                lines=[line.as_dict() for line in result.lines],
                gross=result.gross,
                deductions=result.deductions,
                net=result.net,
                carried_forward=result.carried_forward,
                payment_method=s.payment_method,
                provider=s.provider,
                account_last4=s.account_last4,
            )
        )
        totals["gross"] += result.gross
        totals["deductions"] += result.deductions
        totals["net"] += result.net
        count += 1
    run.headcount = count
    run.gross, run.deductions, run.net = totals["gross"], totals["deductions"], totals["net"]
    run.computed_at = utcnow()
    await ctx.db.flush()


def _payslip_out(p: Payslip, run: PayrollRun | None = None) -> PayslipOut:
    out = PayslipOut.model_validate(p)
    if run is not None:
        out.period, out.status, out.currency = run.period, run.status, run.currency
    return out


async def run_detail(ctx: Ctx, run_id: uuid.UUID) -> RunDetail:
    run = await _run(ctx, run_id)
    preparer = ctx.can(access.RUN) or ctx.can(access.APPROVE)
    if not preparer and run.status not in ("finalized", "paid"):
        raise NotFound()
    query = select(Payslip).where(Payslip.run_id == run.id).order_by(func.lower(Payslip.employee_name))
    if not preparer:
        scope = await scope_departments(ctx)
        if scope is not None:
            query = query.where(Payslip.department_id.in_(scope))
    slips = list(await ctx.db.scalars(query))
    missing: list[dict[str, Any]] = []
    if preparer and run.status == "draft":
        start, end = calc.period_bounds(run.period)
        paid = {p.employee_id for p in slips}
        structures = await _structures(ctx.db, end)
        missing = [
            {"employee_id": str(p.id), "employee_name": p.full_name}
            for p in await _people(ctx.db, start, end)
            if p.id not in paid and p.id not in structures
        ]
    return RunDetail(
        **RunOut.model_validate(run).model_dump(),
        payslips=[_payslip_out(p, run) for p in slips],
        missing=missing,
    )


async def add_item(ctx: Ctx, run_id: uuid.UUID, body: ItemIn) -> ItemOut:
    run = await _run(ctx, run_id, lock=True)
    _require_status(run, "draft")
    if await ctx.db.get(Employee, body.employee_id) is None:
        raise NotFound()
    item = PayItem(
        run_id=run.id,
        employee_id=body.employee_id,
        kind=body.kind,
        label=body.label,
        amount=body.amount,
        created_by=ctx.user.id,
    )
    ctx.db.add(item)
    await ctx.db.flush()
    await compute(ctx, run)
    await audit.record(
        ctx.db,
        "payroll.item_added",
        target_type="payroll_run",
        target_id=run.id,
        data={"employee_id": body.employee_id, "kind": body.kind, "label": body.label, "amount": body.amount},
    )
    await ctx.db.commit()
    return ItemOut.model_validate(item)


async def list_items(ctx: Ctx, run_id: uuid.UUID) -> list[ItemOut]:
    run = await _run(ctx, run_id)
    rows = await ctx.db.scalars(select(PayItem).where(PayItem.run_id == run.id).order_by(PayItem.created_at))
    return [ItemOut.model_validate(i) for i in rows]


async def remove_item(ctx: Ctx, run_id: uuid.UUID, item_id: uuid.UUID) -> None:
    run = await _run(ctx, run_id, lock=True)
    _require_status(run, "draft")
    item = await ctx.db.scalar(select(PayItem).where(PayItem.id == item_id, PayItem.run_id == run.id))
    if item is None:
        raise NotFound()
    await ctx.db.delete(item)
    await ctx.db.flush()
    await compute(ctx, run)
    await audit.record(
        ctx.db,
        "payroll.item_removed",
        target_type="payroll_run",
        target_id=run.id,
        data={"label": item.label, "amount": item.amount},
    )
    await ctx.db.commit()


async def delete_run(ctx: Ctx, run_id: uuid.UUID) -> None:
    run = await _run(ctx, run_id, lock=True)
    _require_status(run, "draft")
    await audit.record(
        ctx.db,
        "payroll.run_deleted",
        target_type="payroll_run",
        target_id=run.id,
        data={"period": run.period},
    )
    await ctx.db.delete(run)
    await ctx.db.commit()


async def submit(ctx: Ctx, run_id: uuid.UUID) -> RunDetail:
    run = await _run(ctx, run_id, lock=True)
    _require_status(run, "draft")
    if run.headcount == 0:
        raise Conflict("Nobody has a salary for this month yet.", code="empty_run")
    run.status = "review"
    run.submitted_by = ctx.user.id
    run.submitted_at = utcnow()
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "payroll.submitted",
        target_type="payroll_run",
        target_id=run.id,
        data={"period": run.period, "net": run.net},
    )
    await events.emit(
        ctx.db,
        "payroll.submitted",
        subject_type="payroll_run",
        subject_id=run.id,
        data={"period": run.period, "headcount": run.headcount, "net": run.net, "currency": run.currency},
    )
    await ctx.db.commit()
    return await run_detail(ctx, run.id)


async def reopen(ctx: Ctx, run_id: uuid.UUID) -> RunDetail:
    run = await _run(ctx, run_id, lock=True)
    _require_status(run, "review")
    run.status = "draft"
    run.submitted_by = None
    run.submitted_at = None
    await ctx.db.flush()
    await audit.record(
        ctx.db, "payroll.reopened", target_type="payroll_run", target_id=run.id, data={"period": run.period}
    )
    await ctx.db.commit()
    return await run_detail(ctx, run.id)


def _next_period(period: str) -> str:
    year, month = (int(x) for x in period.split("-"))
    return f"{year + (month == 12):04d}-{month % 12 + 1:02d}"


async def finalize(ctx: Ctx, run_id: uuid.UUID) -> RunDetail:
    run = await _run(ctx, run_id, lock=True)
    _require_status(run, "review")
    if ctx.user.id in (run.submitted_by, run.created_by) and not ctx.is_owner:
        raise Forbidden("Someone else has to finalize the payroll you prepared.", code="self_approval")
    slips = list(await ctx.db.scalars(select(Payslip).where(Payslip.run_id == run.id)))
    # Repay advances, once (the run is locked and leaves 'review' here).
    repaid: dict[str, int] = defaultdict(int)
    for slip in slips:
        for line in slip.lines:
            if line.get("code") == "loan" and line.get("ref"):
                repaid[line["ref"]] += int(line["amount"])
    if repaid:
        for loan in await ctx.db.scalars(
            select(Loan).where(Loan.id.in_([uuid.UUID(r) for r in repaid])).with_for_update()
        ):
            loan.outstanding = max(loan.outstanding - repaid[str(loan.id)], 0)
            if loan.outstanding == 0:
                loan.status = "closed"
    # Deductions that didn't fit become an advance repaid from next month's pay.
    for slip in slips:
        if slip.carried_forward > 0:
            ctx.db.add(
                Loan(
                    employee_id=slip.employee_id,
                    kind="advance",
                    label=f"Carried from {run.period}",
                    principal=slip.carried_forward,
                    installment=slip.carried_forward,
                    outstanding=slip.carried_forward,
                    start_period=_next_period(run.period),
                    status="active",
                    created_by=ctx.user.id,
                )
            )
    run.status = "finalized"
    run.finalized_by = ctx.user.id
    run.finalized_at = utcnow()
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "payroll.finalized",
        target_type="payroll_run",
        target_id=run.id,
        data={"period": run.period, "headcount": run.headcount, "gross": run.gross, "net": run.net},
    )
    await events.emit(
        ctx.db,
        "payroll.finalized",
        subject_type="payroll_run",
        subject_id=run.id,
        data={
            "period": run.period,
            "headcount": run.headcount,
            "net": run.net,
            "currency": run.currency,
            # Whose payslips are now ready (members only; people without a login can't be told).
            "membership_ids": list(
                await ctx.db.scalars(
                    select(Employee.membership_id).where(
                        Employee.id.in_([s.employee_id for s in slips]), Employee.membership_id.is_not(None)
                    )
                )
            ),
        },
    )
    await ctx.db.commit()
    return await run_detail(ctx, run.id)


async def mark_paid(ctx: Ctx, run_id: uuid.UUID) -> RunDetail:
    run = await _run(ctx, run_id, lock=True)
    _require_status(run, "finalized")
    run.status = "paid"
    run.paid_at = utcnow()
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "payroll.paid",
        target_type="payroll_run",
        target_id=run.id,
        data={"period": run.period, "net": run.net},
    )
    await ctx.db.commit()
    return await run_detail(ctx, run.id)


async def transfer_sheet(ctx: Ctx, run_id: uuid.UUID) -> tuple[str, str]:
    """A CSV of who gets paid how much, and where (bank or wallet account in full)."""
    run = await _run(ctx, run_id)
    _require_status(run, "finalized", "paid")
    unit = defaults.unit_for(run.currency)
    slips = list(
        await ctx.db.scalars(
            select(Payslip)
            .where(Payslip.run_id == run.id)
            .order_by(Payslip.payment_method, func.lower(Payslip.employee_name))
        )
    )
    structures = {
        s.id: s
        for s in await ctx.db.scalars(
            select(SalaryStructure).where(
                SalaryStructure.id.in_([p.structure_id for p in slips if p.structure_id])
            )
        )
    }
    buffer = io.StringIO()
    buffer.write("﻿")
    writer = csv.writer(buffer)
    writer.writerow(["Name", "Code", "Method", "Bank or wallet", "Account", f"Amount ({run.currency})"])
    for p in slips:
        if p.net == 0:
            continue
        s = structures.get(p.structure_id) if p.structure_id else None
        account = crypto.decrypt(s.account_enc, context=_account_context(s.id)) if s and s.account_enc else ""
        amount = Decimal(p.net) / unit
        writer.writerow(
            [
                safe_cell(v)
                for v in (
                    p.employee_name,
                    p.employee_code,
                    p.payment_method,
                    p.provider,
                    account,
                    f"{amount:.{0 if unit == 1 else 2}f}",
                )
            ]
        )
    await audit.record(
        ctx.db,
        "payroll.transfer_sheet_downloaded",
        target_type="payroll_run",
        target_id=run.id,
        data={"period": run.period, "rows": len(slips)},
    )
    await ctx.db.commit()
    return buffer.getvalue(), f"payroll-{run.period}-transfers.csv"


# ---- Payslips ---------------------------------------------------------------------------


async def my_payslips(ctx: Ctx) -> list[PayslipOut]:
    assert ctx.membership is not None
    me = await employee_for_membership(ctx.db, ctx.membership.id)
    if me is None:
        return []
    rows = await ctx.db.execute(
        select(Payslip, PayrollRun)
        .join(PayrollRun, and_(PayrollRun.tenant_id == Payslip.tenant_id, PayrollRun.id == Payslip.run_id))
        .where(Payslip.employee_id == me.id, PayrollRun.status.in_(("finalized", "paid")))
        .order_by(PayrollRun.period.desc())
    )
    return [_payslip_out(p, r) for p, r in rows]


async def payslip(ctx: Ctx, payslip_id: uuid.UUID) -> PayslipOut:
    row = (
        await ctx.db.execute(
            select(Payslip, PayrollRun)
            .join(
                PayrollRun, and_(PayrollRun.tenant_id == Payslip.tenant_id, PayrollRun.id == Payslip.run_id)
            )
            .where(Payslip.id == payslip_id)
        )
    ).first()
    if row is None:
        raise NotFound()
    slip, run = row
    assert ctx.membership is not None
    me = await employee_for_membership(ctx.db, ctx.membership.id)
    published = run.status in ("finalized", "paid")
    own = me is not None and me.id == slip.employee_id and published
    preparer = ctx.can(access.RUN) or ctx.can(access.APPROVE)
    viewer = ctx.can(access.VIEW) and published and await in_scope(ctx, slip.department_id)
    if not (own or preparer or viewer):
        raise NotFound()
    return _payslip_out(slip, run)


async def payslip_pdf(ctx: Ctx, payslip_id: uuid.UUID, lang: str) -> tuple[bytes, str]:
    slip = await payslip(ctx, payslip_id)
    assert ctx.tenant is not None
    company = ctx.tenant.name
    body = await anyio.to_thread.run_sync(lambda: pdf.render_pdf(slip, company=company, lang=lang))
    code = slip.employee_code or str(slip.employee_id)[:8]
    return body, f"payslip-{slip.period}-{code}-{lang}.pdf"


# ---- Switching the module on ------------------------------------------------------------


async def seed(db: AsyncSession, tenant: Tenant, module: str) -> None:
    if module != "payroll" or await db.scalar(select(PayrollSettings)) is not None:
        return
    db.add(PayrollSettings(round_net=True, **defaults.settings_for(tenant.country)))
    await db.flush()


def register_hooks() -> None:
    if seed not in hooks.module_enabled:
        hooks.module_enabled.append(seed)
