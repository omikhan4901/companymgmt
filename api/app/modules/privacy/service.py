"""Data exports: the whole workspace for its owner, and each person's own data.

Exports sit above every other module (they read all of them), so this module is the top
layer. Encrypted fields come out readable: an export exists to hand people their data.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
import zipfile
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Table, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.audit import AuditEvent
from app.core.models import Base, TenantScoped
from app.core.security import crypto
from app.core.spreadsheet import safe_cell
from app.core.time import utcnow
from app.models_registry import metadata
from app.modules.attendance.models import AttendanceCorrection, AttendanceRecord
from app.modules.leave.models import LeaveAdjustment, LeaveRequest, LeaveType
from app.modules.notifications.models import Notification
from app.modules.payroll.models import PayrollRun, Payslip, SalaryStructure
from app.modules.people.models import Employee
from app.modules.people.service import employee_for_membership
from app.modules.platform.deps import Ctx
from app.modules.platform.models import Membership, User

FORMAT = "companymgmt-export"
VERSION = 1

# Encrypted columns: (column, readable name, encryption context for the row).
DECRYPT: dict[str, tuple[str, str, Callable[[dict[str, Any]], str]]] = {
    "employees": ("national_id_enc", "national_id", lambda r: f"employee:{r['id']}:national_id"),
    "salary_structures": ("account_enc", "account", lambda r: f"salary_structure:{r['id']}:account"),
}


def jsonable(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    return value


def _readable(table: str, row: dict[str, Any]) -> dict[str, Any]:
    if table in DECRYPT:
        column, name, context = DECRYPT[table]
        token = row.pop(column, None)
        row[name] = crypto.decrypt(token, context=context(row)) if token else None
    return {k: jsonable(v) for k, v in row.items()}


def tenant_tables() -> list[Table]:
    scoped = {
        str(getattr(m.class_, "__tablename__", ""))
        for m in Base.registry.mappers
        if issubclass(m.class_, TenantScoped)
    }
    return [t for t in metadata.sorted_tables if t.name in scoped]


async def _rows(db: AsyncSession, table: Table, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
    result = await db.execute(select(table).where(table.c.tenant_id == tenant_id))
    return [_readable(table.name, dict(r._mapping)) for r in result]


def _csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    out = io.StringIO()
    out.write("﻿")
    writer = csv.writer(out)
    writer.writerow(columns)
    for r in rows:
        writer.writerow([safe_cell(r.get(c)) for c in columns])
    return out.getvalue()


README = """CompanyMgmt workspace export
============================

data/<table>.json   Every record in the workspace, one file per table, as stored.
                    National ID and account numbers are decrypted.
csv/*.csv           The same people, attendance, leave and payslips as spreadsheets.
manifest.json       What's inside, row counts and when it was made.

Money is in minor units (paisa, cents): 2080000 means 20,800.00.
Keep this file safe: it contains personal and salary data.
"""


async def workspace_export(ctx: Ctx) -> tuple[bytes, str]:
    tenant = ctx.tenant
    assert tenant is not None
    db = ctx.db
    buffer = io.BytesIO()
    counts: dict[str, int] = {}
    data: dict[str, list[dict[str, Any]]] = {}
    for table in tenant_tables():
        data[table.name] = await _rows(db, table, tenant.id)
        counts[table.name] = len(data[table.name])
    member_ids = [uuid.UUID(m["user_id"]) for m in data.get("memberships", [])]
    users = [
        {"id": str(u.id), "name": u.name, "email": u.email, "username": u.username, "locale": u.locale}
        for u in await db.scalars(select(User).where(User.id.in_(member_ids)))
    ]
    names = {e["id"]: e["full_name"] for e in data.get("employees", [])}
    for key in ("attendance_records", "leave_requests", "payslips"):
        for row in data.get(key, []):
            row.setdefault("employee_name", names.get(row.get("employee_id")))
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", README)
        manifest = {
            "format": FORMAT,
            "version": VERSION,
            "workspace": {
                "id": str(tenant.id),
                "name": tenant.name,
                "country": tenant.country,
                "currency": tenant.currency,
            },
            "exported_at": utcnow().isoformat(),
            "exported_by": str(ctx.user.id),
            "tables": counts,
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        for name, rows in data.items():
            zf.writestr(f"data/{name}.json", json.dumps(rows, indent=1, ensure_ascii=False))
        zf.writestr("data/users.json", json.dumps(users, indent=1, ensure_ascii=False))
        zf.writestr(
            "csv/people.csv",
            _csv(
                data.get("employees", []),
                [
                    "employee_code",
                    "full_name",
                    "email",
                    "phone",
                    "job_title",
                    "employment_type",
                    "status",
                    "joined_on",
                    "left_on",
                    "national_id",
                ],
            ),
        )
        zf.writestr(
            "csv/attendance.csv",
            _csv(
                data.get("attendance_records", []),
                [
                    "business_date",
                    "employee_name",
                    "clock_in_at",
                    "clock_out_at",
                    "minutes",
                    "status",
                    "source",
                    "note",
                ],
            ),
        )
        zf.writestr(
            "csv/leave.csv",
            _csv(
                data.get("leave_requests", []),
                ["employee_name", "start_date", "end_date", "half_day", "days", "status", "reason"],
            ),
        )
        zf.writestr(
            "csv/payslips.csv",
            _csv(
                data.get("payslips", []),
                [
                    "employee_name",
                    "run_id",
                    "gross",
                    "deductions",
                    "net",
                    "carried_forward",
                    "payment_method",
                ],
            ),
        )
    await audit.record(
        db, "workspace.exported", target_type="workspace", target_id=tenant.id, data={"tables": counts}
    )
    await db.commit()
    return buffer.getvalue(), f"{tenant.slug}-export-{utcnow():%Y%m%d}.zip"


async def my_data(ctx: Ctx) -> tuple[bytes, str]:
    """Everything this workspace holds about the signed-in person."""
    assert ctx.membership is not None
    db, user = ctx.db, ctx.user
    me = await employee_for_membership(db, ctx.membership.id)
    out: dict[str, Any] = {
        "format": f"{FORMAT}-personal",
        "version": VERSION,
        "exported_at": utcnow().isoformat(),
        "account": {
            "name": user.name,
            "email": user.email,
            "username": user.username,
            "locale": user.locale,
            "two_step_verification": user.totp_enabled_at is not None,
            "created_at": user.created_at,
        },
        "membership": {"role": ctx.role.name if ctx.role else None, "joined_at": ctx.membership.created_at},
    }

    async def rows(model: Any, *where: Any) -> list[dict[str, Any]]:
        table = model.__table__
        result = await db.execute(select(table).where(*where))
        return [_readable(table.name, dict(r._mapping)) for r in result]

    if me is not None:
        out["profile"] = (await rows(Employee, Employee.id == me.id))[0]
        out["attendance"] = await rows(AttendanceRecord, AttendanceRecord.employee_id == me.id)
        out["attendance_corrections"] = await rows(
            AttendanceCorrection, AttendanceCorrection.employee_id == me.id
        )
        out["leave_requests"] = await rows(LeaveRequest, LeaveRequest.employee_id == me.id)
        out["leave_adjustments"] = await rows(LeaveAdjustment, LeaveAdjustment.employee_id == me.id)
        out["leave_types"] = await rows(LeaveType)
        out["salaries"] = await rows(SalaryStructure, SalaryStructure.employee_id == me.id)
        published = select(PayrollRun.id).where(PayrollRun.status.in_(("finalized", "paid")))
        out["payslips"] = await rows(
            Payslip, and_(Payslip.employee_id == me.id, Payslip.run_id.in_(published))
        )
    out["audit_events_by_me"] = await rows(AuditEvent, AuditEvent.actor_user_id == user.id)
    out["notifications"] = await rows(Notification, Notification.user_id == user.id)
    out["memberships_elsewhere"] = len(
        list(await db.scalars(select(Membership.id).where(Membership.user_id == user.id)))
    )
    await audit.record(db, "privacy.personal_export", target_type="user", target_id=user.id, data={})
    await db.commit()
    body = json.dumps(jsonable(out), indent=1, ensure_ascii=False).encode()
    return body, f"my-data-{utcnow():%Y%m%d}.json"
