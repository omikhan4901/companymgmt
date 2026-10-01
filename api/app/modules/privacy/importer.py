"""Restore a workspace export into a new, empty workspace.

Business records come across: branches, departments, people, attendance, leave and
payroll. Logins, roles, invitations and the audit log don't: they belong to the old
workspace, and the owner invites people again. Every record gets a new id (the old
workspace may still exist on this server), references are rewritten to match, and
encrypted fields are encrypted again for their new rows.
"""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Table, delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.errors import Conflict, Invalid
from app.core.ids import uuid7
from app.core.security import crypto
from app.modules.attendance.models import AttendanceRecord
from app.modules.leave.models import LeaveRequest
from app.modules.payroll.models import Loan, PayrollRun, SalaryStructure
from app.modules.people.models import Department, Employee
from app.modules.people.service import employee_for_membership
from app.modules.platform.deps import Ctx
from app.modules.platform.models import Branch
from app.modules.privacy.service import FORMAT, VERSION, tenant_tables

MAX_UPLOAD = 50 * 1024 * 1024
MAX_UNPACKED = 500 * 1024 * 1024
MAX_FILES = 200

# Imported, in this order of preference (the real order follows foreign keys).
IMPORTED = {
    "branches",
    "departments",
    "employees",
    "attendance_settings",
    "attendance_records",
    "attendance_corrections",
    "leave_policies",
    "leave_types",
    "holidays",
    "leave_requests",
    "leave_adjustments",
    "payroll_settings",
    "salary_structures",
    "payroll_loans",
    "payroll_runs",
    "payslips",
    "payroll_items",
}
# Settings the new workspace was given when its modules were switched on; replaced.
SEEDED = ("leave_types", "leave_policies", "payroll_settings", "attendance_settings")
# Readable field in the export → (stored column, encryption context for the new row).
ENCRYPTED: dict[str, dict[str, tuple[str, Callable[[str], str]]]] = {
    "employees": {"national_id": ("national_id_enc", lambda rid: f"employee:{rid}:national_id")},
    "salary_structures": {"account": ("account_enc", lambda rid: f"salary_structure:{rid}:account")},
}


def _read(body: bytes) -> dict[str, list[dict[str, Any]]]:
    if len(body) > MAX_UPLOAD:
        raise Invalid("The file is too large.", code="import_too_large")
    try:
        archive = zipfile.ZipFile(io.BytesIO(body))
        infos = archive.infolist()
        if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_UNPACKED:
            raise Invalid("The file unpacks to too much data.", code="import_too_large")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format") != FORMAT or manifest.get("version") != VERSION:
            raise Invalid("This isn't a CompanyMgmt workspace export.", code="import_format")
        data: dict[str, list[dict[str, Any]]] = {}
        for name in IMPORTED:
            path = f"data/{name}.json"
            if path in archive.namelist():
                rows = json.loads(archive.read(path))
                if not isinstance(rows, list):
                    raise Invalid("The export is damaged.", code="import_format")
                data[name] = rows
        return data
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise Invalid("This isn't a CompanyMgmt workspace export.", code="import_format") from exc


async def _check_empty(db: AsyncSession, own: Employee | None) -> None:
    """Only into a workspace with no business records yet (besides the owner's profile)."""
    for model in (AttendanceRecord, LeaveRequest, PayrollRun, SalaryStructure, Loan, Department):
        if await db.scalar(select(func.count()).select_from(model)):
            raise Conflict(
                "Import only into a new workspace with nothing in it yet.", code="import_not_empty"
            )
    people = await db.scalar(select(func.count()).select_from(Employee))
    if (people or 0) > (1 if own else 0):
        raise Conflict("Import only into a new workspace with nothing in it yet.", code="import_not_empty")


def _remap(value: Any, ids: dict[str, str]) -> Any:
    if isinstance(value, str):
        return ids.get(value, value)
    if isinstance(value, list):
        return [_remap(v, ids) for v in value]
    if isinstance(value, dict):
        return {k: _remap(v, ids) for k, v in value.items()}
    return value


def _user_columns(table: Table) -> set[str]:
    return {c.name for c in table.c if any(fk.target_fullname == "users.id" for fk in c.foreign_keys)}


async def import_workspace(ctx: Ctx, body: bytes) -> dict[str, int]:
    assert ctx.tenant is not None
    assert ctx.membership is not None
    db = ctx.db
    data = _read(body)
    own = await employee_for_membership(db, ctx.membership.id)
    await _check_empty(db, own)

    ids: dict[str, str] = {}
    for exported in data.values():
        for row in exported:
            if row.get("id"):
                ids[str(row["id"])] = str(uuid7())
    # The person importing is already here: their old profile becomes this one.
    merged: str | None = None
    if own is not None and ctx.user.email:
        match = next(
            (
                e
                for e in data.get("employees", [])
                if (e.get("email") or "").lower() == ctx.user.email.lower()
            ),
            None,
        )
        if match:
            merged = str(match["id"])
            ids[merged] = str(own.id)

    for name in SEEDED:
        if name in data:
            table = next(t for t in tenant_tables() if t.name == name)
            await db.execute(delete(table))
    if data.get("branches"):
        # The new workspace's default branch, unless someone already uses it.
        if own is not None:
            own.branch_id = None
        await db.flush()
        await db.execute(delete(Branch))

    counts: dict[str, int] = {}
    for table in tenant_tables():
        rows = data.get(table.name) or []
        if table.name not in IMPORTED or not rows:
            continue
        columns = {c.name for c in table.c}
        users = _user_columns(table)
        prepared = []
        for row in rows:
            if table.name == "employees" and merged and str(row.get("id")) == merged:
                continue
            new = _remap(
                {k: v for k, v in row.items() if k in columns or k in ENCRYPTED.get(table.name, {})}, ids
            )
            new["tenant_id"] = str(ctx.tenant.id)
            for column in users:
                new[column] = None  # people from the old workspace may not exist here
            if table.name == "employees":
                new["membership_id"] = None
            for readable, (column, context) in ENCRYPTED.get(table.name, {}).items():
                plain = new.pop(readable, None)
                new[column] = crypto.encrypt(str(plain), context=context(new["id"])) if plain else None
                if table.name == "salary_structures":
                    new["account_last4"] = str(plain)[-4:] if plain else None
            prepared.append({k: v for k, v in new.items() if k in columns})
        if prepared:
            await db.execute(insert(table), [_typed(table, r) for r in prepared])
        counts[table.name] = len(prepared)
    await audit.record(
        db, "workspace.imported", target_type="workspace", target_id=ctx.tenant.id, data={"tables": counts}
    )
    await db.commit()
    return counts


def _typed(table: Table, row: dict[str, Any]) -> dict[str, Any]:
    """JSON strings back to the column's Python type (uuid, dates, decimals)."""
    out: dict[str, Any] = {}
    for key, value in row.items():
        column = table.c[key]
        if value is None:
            out[key] = None
            continue
        try:
            python_type = column.type.python_type
        except NotImplementedError:
            out[key] = value
            continue
        if python_type is uuid.UUID:
            out[key] = uuid.UUID(str(value))
        elif python_type.__name__ in ("date", "datetime", "Decimal") and isinstance(value, str):
            out[key] = _parse(python_type, value)
        else:
            out[key] = value
    return out


def _parse(python_type: type, value: str) -> Any:
    if python_type is datetime:
        return datetime.fromisoformat(value)
    if python_type is date:
        return date.fromisoformat(value)
    if python_type is Decimal:
        return Decimal(value)
    return value
