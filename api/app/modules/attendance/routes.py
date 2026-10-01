"""Attendance API: clocking in and out, corrections, manual records, timesheets, export."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit, events
from app.core.errors import Conflict, Forbidden, Invalid, NotFound
from app.core.http import check_if_match, decode_cursor, encode_cursor, set_etag
from app.core.schema import Page
from app.core.spreadsheet import safe_cell
from app.core.time import utcnow
from app.modules.attendance import access, geo, service
from app.modules.attendance.models import AttendanceCorrection, AttendanceRecord, AttendanceSettings
from app.modules.attendance.schemas import (
    ClockIn,
    ClockOut,
    CorrectionIn,
    CorrectionOut,
    DecisionIn,
    GeoIn,
    PresentOut,
    RecordIn,
    RecordOut,
    RecordPatch,
    SettingsIn,
    SettingsOut,
    StatusOut,
    TimesheetOut,
    correction_out,
    record_out,
)
from app.modules.attendance.service import (
    MAX_SHIFT,
    business_date_for,
    default_branch,
    minutes_between,
    register_hooks,
    save,
    validate_times,
)
from app.modules.attendance.service import me as _me
from app.modules.attendance.service import open_record as _open_record
from app.modules.attendance.service import scoped_employee as _scoped_employee
from app.modules.attendance.service import settings as _settings
from app.modules.people.access import scope_departments
from app.modules.people.models import Employee
from app.modules.people.service import employee_for_membership
from app.modules.platform.catalog import WORKSPACE_MANAGE
from app.modules.platform.deps import Ctx, allow
from app.modules.platform.models import Branch

register_hooks()

router = APIRouter(prefix="/v1/attendance", tags=["attendance"])
MODULE = "attendance"


async def _sites(db: AsyncSession, only: uuid.UUID | None = None) -> list[geo.Site]:
    query = select(Branch).where(Branch.is_active.is_(True), Branch.latitude.is_not(None))
    if only is not None:
        query = query.where(Branch.id == only)
    return [
        geo.Site(b.id, float(b.latitude or 0), float(b.longitude or 0), b.geofence_m)
        for b in await db.scalars(query)
    ]


def _point(location: GeoIn | None) -> geo.Point | None:
    return geo.Point(location.latitude, location.longitude, location.accuracy_m) if location else None


def _store(record: AttendanceRecord, prefix: str, point: geo.Point | None, result: geo.Check) -> None:
    setattr(record, f"{prefix}_geo", result.result)
    setattr(record, f"{prefix}_distance_m", result.distance_m)
    if point is not None:
        setattr(record, f"{prefix}_latitude", geo.rounded(point.latitude))
        setattr(record, f"{prefix}_longitude", geo.rounded(point.longitude))
        setattr(record, f"{prefix}_accuracy_m", min(round(point.accuracy_m), 100_000))


# ---- Self service -----------------------------------------------------------------------


@router.post("/clock-in", response_model=RecordOut, status_code=201)
async def clock_in(body: ClockIn, ctx: Ctx = Depends(allow(access.SELF, module=MODULE))) -> RecordOut:
    employee = await _me(ctx)
    existing = await _open_record(ctx.db, employee.id)
    if existing is not None:
        raise Conflict(
            "You're already clocked in.",
            code="already_clocked_in",
            extra={"record": record_out(existing).model_dump(mode="json")},
        )
    branch_id = body.branch_id or await default_branch(ctx.db, employee)
    if body.branch_id is not None:
        branch = await ctx.db.get(Branch, body.branch_id)
        if branch is None or not branch.is_active:
            raise Invalid(errors=[{"field": "branch_id", "message": "Unknown branch."}])
    settings = await _settings(ctx.db)
    point = _point(body.location)
    located: geo.Check | None = None
    if settings.location_mode != "off":
        located = geo.check(
            point,
            await _sites(ctx.db, only=body.branch_id),
            max_accuracy_m=settings.max_accuracy_m,
            prefer=body.branch_id or employee.branch_id,
        )
        if settings.location_mode == "require":
            await _enforce(ctx, located, point, settings)
        if located.branch_id is not None and body.branch_id is None:
            branch_id = located.branch_id
    # The server's clock decides; the device's time is only kept to spot skew.
    now = utcnow()
    record = AttendanceRecord(
        employee_id=employee.id,
        branch_id=branch_id,
        business_date=await business_date_for(ctx.db, branch_id, now),
        clock_in_at=now,
        status="open",
        source="self",
        note=body.note,
        client_time=body.client_time,
        created_by=ctx.user.id,
    )
    if located is not None:
        _store(record, "in", point, located)
    ctx.db.add(record)
    await save(ctx.db, record)
    await ctx.db.commit()
    return record_out(record)


async def _enforce(
    ctx: Ctx, located: geo.Check, point: geo.Point | None, settings: AttendanceSettings
) -> None:
    """Clock-in rules when location is required."""
    if located.result == "no_fix":
        raise Invalid(
            "Turn on location for this site to clock in.",
            code="location_required",
            errors=[{"field": "location", "message": "Location is required to clock in."}],
        )
    if point is not None and point.accuracy_m > settings.max_accuracy_m and located.result != "inside":
        raise Invalid(
            "Your location isn't precise enough. Turn on precise location or step outside, then try again.",
            code="location_imprecise",
            extra={"accuracy_m": round(point.accuracy_m), "max_accuracy_m": settings.max_accuracy_m},
        )
    if located.result == "outside":
        branch = await ctx.db.get(Branch, located.branch_id) if located.branch_id else None
        name = branch.name if branch else "your branch"
        raise Forbidden(
            f"You're about {located.distance_m} m from {name}. Clock in when you get there.",
            code="outside_area",
            extra={
                "distance_m": located.distance_m,
                "branch_id": str(located.branch_id),
                "branch_name": name,
            },
        )


@router.post("/clock-out", response_model=RecordOut)
async def clock_out(body: ClockOut, ctx: Ctx = Depends(allow(access.SELF, module=MODULE))) -> RecordOut:
    employee = await _me(ctx)
    record = await _open_record(ctx.db, employee.id, lock=True)
    if record is None:
        raise Conflict("You're not clocked in.", code="not_clocked_in")
    now = utcnow()
    if now - record.clock_in_at > MAX_SHIFT:
        raise Conflict(
            "You were clocked in for more than a day. Tell us when you left instead.",
            code="forgot_clock_out",
            extra={"record": record_out(record).model_dump(mode="json")},
        )
    if now <= record.clock_in_at:
        now = record.clock_in_at + timedelta(seconds=1)
    settings = await _settings(ctx.db)
    if settings.location_mode != "off":
        # Clock-out is never blocked (that would leave shifts open); it's flagged instead.
        point = _point(body.location)
        sites = await _sites(ctx.db, only=record.branch_id) or await _sites(ctx.db)
        _store(record, "out", point, geo.check(point, sites, max_accuracy_m=settings.max_accuracy_m))
    record.clock_out_at = now
    record.minutes = minutes_between(record.clock_in_at, now)
    record.status = "closed"
    if body.note:
        record.note = ((record.note + " · ") if record.note else "") + body.note
        record.note = record.note[:500]
    await save(ctx.db, record)
    await ctx.db.commit()
    return record_out(record)


# ---- Settings ---------------------------------------------------------------------------


async def _settings_out(db: AsyncSession, settings: AttendanceSettings) -> SettingsOut:
    total = await db.scalar(select(func.count()).select_from(Branch).where(Branch.is_active.is_(True)))
    located = await db.scalar(
        select(func.count())
        .select_from(Branch)
        .where(Branch.is_active.is_(True), Branch.latitude.is_not(None))
    )
    return SettingsOut(
        location_mode=settings.location_mode,
        max_accuracy_m=settings.max_accuracy_m,
        branches_total=int(total or 0),
        branches_located=int(located or 0),
    )


@router.get("/settings", response_model=SettingsOut)
async def get_settings(ctx: Ctx = Depends(allow(access.SELF, module=MODULE))) -> SettingsOut:
    return await _settings_out(ctx.db, await _settings(ctx.db))


@router.put("/settings", response_model=SettingsOut)
async def put_settings(
    body: SettingsIn, ctx: Ctx = Depends(allow(WORKSPACE_MANAGE, module=MODULE))
) -> SettingsOut:
    row = await ctx.db.scalar(select(AttendanceSettings).with_for_update())
    before = {"location_mode": row.location_mode, "max_accuracy_m": row.max_accuracy_m} if row else None
    if row is None:
        row = AttendanceSettings(tenant_id=ctx.tenant_id)
        ctx.db.add(row)
    row.location_mode = body.location_mode
    row.max_accuracy_m = body.max_accuracy_m
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "attendance.settings_changed",
        target_type="workspace",
        target_id=ctx.tenant_id,
        data={"before": before, "after": body.model_dump()},
    )
    await ctx.db.commit()
    return await _settings_out(ctx.db, row)


# ---- Corrections ------------------------------------------------------------------------


@router.post("/corrections", response_model=CorrectionOut, status_code=201)
async def request_correction(
    body: CorrectionIn, ctx: Ctx = Depends(allow(access.SELF, module=MODULE))
) -> CorrectionOut:
    employee = await _me(ctx)
    record: AttendanceRecord | None = None
    if body.kind in ("change", "remove"):
        if body.record_id is None:
            raise Invalid(errors=[{"field": "record_id", "message": "Choose the record to fix."}])
        record = await ctx.db.scalar(
            select(AttendanceRecord)
            .where(AttendanceRecord.id == body.record_id, AttendanceRecord.employee_id == employee.id)
            .with_for_update()
        )
        if record is None:
            raise NotFound()
    if body.kind in ("add", "change"):
        if body.clock_in_at is None or body.clock_out_at is None:
            raise Invalid(errors=[{"field": "clock_out_at", "message": "Give both the start and end time."}])
        validate_times(body.clock_in_at, body.clock_out_at)
    duplicate = (
        select(func.count())
        .select_from(AttendanceCorrection)
        .where(AttendanceCorrection.employee_id == employee.id, AttendanceCorrection.status == "pending")
    )
    if body.record_id is not None:
        duplicate = duplicate.where(AttendanceCorrection.record_id == body.record_id)
    else:
        duplicate = duplicate.where(
            AttendanceCorrection.kind == "add", AttendanceCorrection.proposed_clock_in_at == body.clock_in_at
        )
    if await ctx.db.scalar(duplicate):
        raise Conflict("You already asked for this. Wait for a decision.", code="duplicate_request")
    correction = AttendanceCorrection(
        employee_id=employee.id,
        record_id=record.id if record else None,
        kind=body.kind,
        proposed_clock_in_at=body.clock_in_at,
        proposed_clock_out_at=body.clock_out_at,
        reason=body.reason,
        status="pending",
        requested_by=ctx.user.id,
    )
    ctx.db.add(correction)
    # A shift left open for more than a day is set aside (not counted) until someone
    # decides, so the person can clock in again.
    if record is not None and record.clock_out_at is None:
        if utcnow() - record.clock_in_at <= MAX_SHIFT and body.kind != "remove":
            raise Conflict("Clock out first, then ask to fix the times.", code="still_open")
        record.clock_out_at = min(
            body.clock_out_at or record.clock_in_at + MAX_SHIFT, record.clock_in_at + MAX_SHIFT
        )
        record.status = "auto_closed"
        record.minutes = None
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "attendance.correction_requested",
        target_type="attendance_correction",
        target_id=correction.id,
        data={"kind": body.kind, "record_id": correction.record_id, "reason": body.reason},
    )
    await events.emit(
        ctx.db,
        "attendance.correction_requested",
        subject_type="attendance_correction",
        subject_id=correction.id,
        data={
            "employee_id": employee.id,
            "employee_name": employee.full_name,
            "department_id": employee.department_id,
            "membership_id": employee.membership_id,
            "kind": correction.kind,
            "status": correction.status,
        },
    )
    await ctx.db.commit()
    return correction_out(correction, employee.full_name)


@router.get("/corrections", response_model=list[CorrectionOut])
async def list_corrections(
    ctx: Ctx = Depends(allow(access.SELF, module=MODULE)),
    status: Literal["pending", "approved", "rejected", "cancelled", "all"] = "pending",
    mine: bool = False,
) -> list[CorrectionOut]:
    return await service.list_corrections(ctx, status=status, mine=mine)


@router.post("/corrections/{correction_id}/approve", response_model=CorrectionOut)
async def approve_correction(
    correction_id: uuid.UUID, body: DecisionIn, ctx: Ctx = Depends(allow(access.APPROVE, module=MODULE))
) -> CorrectionOut:
    return await service.approve_correction(ctx, correction_id, body.note)


@router.post("/corrections/{correction_id}/reject", response_model=CorrectionOut)
async def reject_correction(
    correction_id: uuid.UUID, body: DecisionIn, ctx: Ctx = Depends(allow(access.APPROVE, module=MODULE))
) -> CorrectionOut:
    return await service.reject_correction(ctx, correction_id, body.note)


@router.post("/corrections/{correction_id}/cancel", response_model=CorrectionOut)
async def cancel_correction(
    correction_id: uuid.UUID, ctx: Ctx = Depends(allow(access.SELF, module=MODULE))
) -> CorrectionOut:
    employee = await _me(ctx)
    correction = await ctx.db.scalar(
        select(AttendanceCorrection)
        .where(AttendanceCorrection.id == correction_id, AttendanceCorrection.employee_id == employee.id)
        .with_for_update()
    )
    if correction is None:
        raise NotFound()
    if correction.status != "pending":
        raise Conflict("This request was already decided.", code="already_decided")
    correction.status = "cancelled"
    correction.decided_at = utcnow()
    await ctx.db.commit()
    return correction_out(correction, employee.full_name)


# ---- Records (managers) -----------------------------------------------------------------


@router.get("/records", response_model=Page[RecordOut])
async def list_records(
    ctx: Ctx = Depends(allow(access.SELF, module=MODULE)),
    start: date | None = Query(default=None, alias="from"),
    end: date | None = Query(default=None, alias="to"),
    employee_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    mine: bool = False,
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> Page[RecordOut]:
    if start and end and end < start:
        raise Invalid(errors=[{"field": "to", "message": "The end date is before the start date."}])
    if start and end and (end - start).days > 366:
        raise Invalid(errors=[{"field": "to", "message": "Choose at most one year."}])
    query = select(AttendanceRecord, Employee.full_name).join(
        Employee,
        and_(Employee.tenant_id == AttendanceRecord.tenant_id, Employee.id == AttendanceRecord.employee_id),
    )
    if mine or not ctx.can(access.VIEW):
        me = await _me(ctx)
        if employee_id is not None and employee_id != me.id:
            raise NotFound()
        query = query.where(AttendanceRecord.employee_id == me.id)
    else:
        scope = await scope_departments(ctx)
        if scope is not None:
            own = await employee_for_membership(ctx.db, ctx.membership.id) if ctx.membership else None
            query = query.where(
                Employee.department_id.in_(scope) | (Employee.id == (own.id if own else None))
            )
        if employee_id:
            query = query.where(AttendanceRecord.employee_id == employee_id)
    if branch_id:
        query = query.where(AttendanceRecord.branch_id == branch_id)
    if start:
        query = query.where(AttendanceRecord.business_date >= start)
    if end:
        query = query.where(AttendanceRecord.business_date <= end)
    after = decode_cursor(cursor)
    if after:
        query = query.where(
            tuple_(AttendanceRecord.clock_in_at, AttendanceRecord.id)
            < tuple_(literal(datetime.fromisoformat(str(after["t"]))), literal(uuid.UUID(str(after["id"]))))
        )
    rows = (
        await ctx.db.execute(
            query.order_by(AttendanceRecord.clock_in_at.desc(), AttendanceRecord.id.desc()).limit(limit + 1)
        )
    ).all()
    items = [record_out(r, name) for r, name in rows[:limit]]
    next_cursor = (
        encode_cursor({"t": items[-1].clock_in_at.isoformat(), "id": items[-1].id})
        if len(rows) > limit
        else None
    )
    return Page(items=items, next_cursor=next_cursor)


@router.post("/records", response_model=RecordOut, status_code=201)
async def add_record(body: RecordIn, ctx: Ctx = Depends(allow(access.MANAGE, module=MODULE))) -> RecordOut:
    employee = await _scoped_employee(ctx, body.employee_id)
    validate_times(body.clock_in_at, body.clock_out_at)
    if body.branch_id is not None and await ctx.db.get(Branch, body.branch_id) is None:
        raise Invalid(errors=[{"field": "branch_id", "message": "Unknown branch."}])
    branch_id = body.branch_id or await default_branch(ctx.db, employee)
    record = AttendanceRecord(
        employee_id=employee.id,
        branch_id=branch_id,
        business_date=await business_date_for(ctx.db, branch_id, body.clock_in_at),
        clock_in_at=body.clock_in_at,
        clock_out_at=body.clock_out_at,
        minutes=minutes_between(body.clock_in_at, body.clock_out_at) if body.clock_out_at else None,
        status="closed" if body.clock_out_at else "open",
        source="manual",
        note=body.note,
        created_by=ctx.user.id,
    )
    ctx.db.add(record)
    await save(ctx.db, record)
    await audit.record(
        ctx.db,
        "attendance.record_added",
        target_type="attendance_record",
        target_id=record.id,
        data={
            "employee": employee.full_name,
            "clock_in_at": body.clock_in_at,
            "clock_out_at": body.clock_out_at,
        },
    )
    await ctx.db.commit()
    return record_out(record, employee.full_name)


async def _scoped_record(ctx: Ctx, record_id: uuid.UUID) -> tuple[AttendanceRecord, Employee]:
    record = await ctx.db.scalar(
        select(AttendanceRecord).where(AttendanceRecord.id == record_id).with_for_update()
    )
    if record is None:
        raise NotFound()
    return record, await _scoped_employee(ctx, record.employee_id)


@router.patch("/records/{record_id}", response_model=RecordOut)
async def edit_record(
    record_id: uuid.UUID,
    body: RecordPatch,
    request: Request,
    response: Response,
    ctx: Ctx = Depends(allow(access.MANAGE, module=MODULE)),
) -> RecordOut:
    record, employee = await _scoped_record(ctx, record_id)
    check_if_match(request, record.version)
    before = {"clock_in_at": record.clock_in_at, "clock_out_at": record.clock_out_at, "note": record.note}
    clock_in_at = body.clock_in_at or record.clock_in_at
    clock_out_at = body.clock_out_at or record.clock_out_at
    validate_times(clock_in_at, clock_out_at)
    record.clock_in_at = clock_in_at
    record.clock_out_at = clock_out_at
    record.business_date = await business_date_for(ctx.db, record.branch_id, clock_in_at)
    record.minutes = minutes_between(clock_in_at, clock_out_at) if clock_out_at else None
    record.status = "closed" if clock_out_at else "open"
    if body.note is not None:
        record.note = body.note
    await save(ctx.db, record)
    await audit.record(
        ctx.db,
        "attendance.record_edited",
        target_type="attendance_record",
        target_id=record.id,
        data={
            "employee": employee.full_name,
            "before": before,
            "after": {"clock_in_at": clock_in_at, "clock_out_at": clock_out_at, "note": record.note},
        },
    )
    await ctx.db.commit()
    set_etag(response, record.version)
    return record_out(record, employee.full_name)


@router.delete("/records/{record_id}", status_code=204)
async def delete_record(
    record_id: uuid.UUID, ctx: Ctx = Depends(allow(access.MANAGE, module=MODULE))
) -> None:
    record, employee = await _scoped_record(ctx, record_id)
    await audit.record(
        ctx.db,
        "attendance.record_deleted",
        target_type="attendance_record",
        target_id=record.id,
        data={
            "employee": employee.full_name,
            "clock_in_at": record.clock_in_at,
            "clock_out_at": record.clock_out_at,
        },
    )
    await ctx.db.delete(record)
    await ctx.db.commit()


# ---- Overviews --------------------------------------------------------------------------


@router.get("/status", response_model=StatusOut)
async def my_status(ctx: Ctx = Depends(allow(access.SELF, module=MODULE))) -> StatusOut:
    return await service.status(ctx)


@router.get("/present", response_model=list[PresentOut])
async def present_now(ctx: Ctx = Depends(allow(access.VIEW, module=MODULE))) -> list[PresentOut]:
    return await service.present(ctx)


@router.get("/timesheet", response_model=TimesheetOut)
async def timesheet(
    month: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
    employee_id: uuid.UUID | None = None,
    ctx: Ctx = Depends(allow(access.SELF, module=MODULE)),
) -> TimesheetOut:
    return await service.timesheet(ctx, month, employee_id)


@router.get("/export.csv")
async def export_csv(
    start: date = Query(alias="from"),
    end: date = Query(alias="to"),
    ctx: Ctx = Depends(allow(access.EXPORT, module=MODULE)),
) -> StreamingResponse:
    if end < start or (end - start).days > 366:
        raise Invalid(errors=[{"field": "to", "message": "Choose a range of at most one year."}])
    query = (
        select(AttendanceRecord, Employee)
        .join(
            Employee,
            and_(
                Employee.tenant_id == AttendanceRecord.tenant_id, Employee.id == AttendanceRecord.employee_id
            ),
        )
        .where(AttendanceRecord.business_date >= start, AttendanceRecord.business_date <= end)
    )
    scope = await scope_departments(ctx)
    if scope is not None:
        query = query.where(Employee.department_id.in_(scope))
    rows = (
        await ctx.db.execute(query.order_by(AttendanceRecord.business_date, func.lower(Employee.full_name)))
    ).all()
    buffer = io.StringIO()
    buffer.write("﻿")  # BOM so Excel opens UTF-8 (Bangla names) correctly
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Date",
            "Employee",
            "Code",
            "Clock in (UTC)",
            "Clock out (UTC)",
            "Minutes",
            "Status",
            "Source",
            "Note",
        ]
    )
    for r, e in rows:
        writer.writerow(
            [
                safe_cell(v)
                for v in (
                    r.business_date.isoformat(),
                    e.full_name,
                    e.employee_code,
                    r.clock_in_at.isoformat(),
                    r.clock_out_at.isoformat() if r.clock_out_at else "",
                    r.minutes if r.minutes is not None else "",
                    r.status,
                    r.source,
                    r.note,
                )
            ]
        )
    await audit.record(
        ctx.db,
        "attendance.exported",
        target_type="attendance",
        data={"from": start, "to": end, "rows": len(rows)},
    )
    await ctx.db.commit()
    filename = f"attendance-{start.isoformat()}-to-{end.isoformat()}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
