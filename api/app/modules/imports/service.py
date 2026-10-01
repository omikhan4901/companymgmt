"""Import people, departments and leave balances from a CSV file.

The same file is sent twice: first to preview (nothing is saved; every row says what
would happen, or what's wrong with it), then to import. The import is all or nothing and
refuses a file that still has problems, so a half-imported company never happens.

People are matched to existing profiles by employee code, then by email; matched people
are updated with the cells that are filled in. Departments are created from paths like
"Design / Motion". A leave column sets how many days the person has left this year, by
recording an adjustment, so balances stay explainable.
"""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy import select

from app.core import audit
from app.core.errors import Forbidden, Invalid
from app.core.ids import uuid7
from app.core.spreadsheet import safe_cell
from app.core.time import today
from app.modules.imports import parse
from app.modules.imports.schemas import CellError, ColumnOut, ImportOut, RowOut
from app.modules.leave import access as leave_access
from app.modules.leave.models import LeaveAdjustment, LeaveType
from app.modules.leave.service import balances
from app.modules.people.access import PEOPLE_MANAGE
from app.modules.people.models import Department, Employee
from app.modules.people.schemas import EmployeeIn
from app.modules.people.service import check_people_limit
from app.modules.platform.deps import Ctx
from app.modules.platform.models import Branch

PROFILE = ("full_name", "preferred_name", "employee_code", "email", "phone", "job_title", "employment_type")
DATES = ("joined_on", "date_of_birth")
REASON = "Days left set by a spreadsheet import"
Action = Literal["create", "update", "unchanged", "error"]

# Template headers, in the workspace's language.
TEMPLATE = {
    "en": {
        "full_name": "Name",
        "employee_code": "Employee code",
        "email": "Email",
        "phone": "Phone",
        "department": "Department",
        "branch": "Branch",
        "job_title": "Job title",
        "employment_type": "Employment type",
        "joined_on": "Joined on",
        "date_of_birth": "Date of birth",
        "leave": "{name} (days left)",
    },
    "bn": {
        "full_name": "নাম",
        "employee_code": "কোড",
        "email": "ইমেইল",
        "phone": "ফোন",
        "department": "বিভাগ",
        "branch": "শাখা",
        "job_title": "পদবি",
        "employment_type": "চাকরির ধরন",
        "joined_on": "যোগদানের তারিখ",
        "date_of_birth": "জন্ম তারিখ",
        "leave": "{name} (বাকি)",
    },
}
EXAMPLE = {
    "full_name": "Nusrat Jahan",
    "employee_code": "E-001",
    "email": "nusrat@example.com",
    "phone": "+880 1711-000000",
    "department": "Design / Motion",
    "job_title": "Senior designer",
    "employment_type": "Full time",
    "joined_on": "2024-01-15",
}


@dataclass
class Plan:
    row: parse.Row
    name: str
    employee: Employee | None = None
    values: dict[str, Any] = field(default_factory=dict)
    department: tuple[str, ...] | None = None
    branch_id: uuid.UUID | None = None
    leave: dict[uuid.UUID, Decimal] = field(default_factory=dict)
    changes: list[str] = field(default_factory=list)
    errors: list[CellError] = field(default_factory=list)

    @property
    def action(self) -> Action:
        if self.errors:
            return "error"
        if self.employee is None:
            return "create"
        return "update" if self.changes else "unchanged"


def _friendly(key: str, issue: Any) -> str:
    """Validation messages in words people use, not the validator's."""
    kind = issue.get("type", "")
    if key == "phone":
        return "Write the phone number with digits, spaces, + and - only."
    if key == "email":
        return "This doesn't look like an email address."
    if kind == "string_too_long":
        return f"Too long: use up to {issue.get('ctx', {}).get('max_length')} characters."
    return str(issue.get("msg", "Check this value.")).removeprefix("Value error, ")


def _require(ctx: Ctx) -> None:
    ctx.require(PEOPLE_MANAGE)
    if ctx.scope_department_id is not None:
        raise Forbidden("Owners and admins import people for the whole workspace.", code="workspace_wide")


def _leave_on(ctx: Ctx) -> bool:
    return ctx.entitlements is not None and "leave" in ctx.entitlements.modules


async def _leave_types(ctx: Ctx) -> list[LeaveType]:
    if not _leave_on(ctx):
        return []
    rows = await ctx.db.scalars(
        select(LeaveType).where(LeaveType.active.is_(True)).order_by(LeaveType.position, LeaveType.name)
    )
    return list(rows)


class _Departments:
    """The department tree by name, case-insensitively, including ones about to be made."""

    def __init__(self, rows: list[Department]) -> None:
        self.ids: dict[tuple[uuid.UUID | None, str], uuid.UUID] = {
            (d.parent_id, d.name.lower()): d.id for d in rows
        }

    def find(self, path: tuple[str, ...]) -> uuid.UUID | None:
        parent: uuid.UUID | None = None
        for name in path:
            found = self.ids.get((parent, name.lower()))
            if found is None:
                return None
            parent = found
        return parent

    def missing(self, path: tuple[str, ...]) -> list[tuple[str, ...]]:
        """The prefixes of `path` that don't exist yet, shortest first."""
        parent: uuid.UUID | None = None
        for i, name in enumerate(path):
            found = self.ids.get((parent, name.lower()))
            if found is None:
                return [path[: j + 1] for j in range(i, len(path))]
            parent = found
        return []


async def _plan(ctx: Ctx, data: bytes) -> tuple[parse.Sheet, list[Plan], _Departments, dict[str, LeaveType]]:
    kinds = await _leave_types(ctx)
    try:
        sheet = parse.read(data, [k.name for k in kinds])
    except parse.Problem as problem:
        raise Invalid(problem.message, code=problem.code) from None
    header = {c.field: c.header for c in sheet.columns if c.field and c.field != "leave"}
    by_name = {k.name: k for k in kinds}
    leave_header = {c.leave_type: c.header for c in sheet.columns if c.leave_type}
    if leave_header and not ctx.can(leave_access.MANAGE):
        raise Forbidden("You can't set leave balances. Remove the leave columns.", code="no_leave_permission")

    people = list(await ctx.db.scalars(select(Employee)))
    by_code = {e.employee_code.lower(): e for e in people if e.employee_code}
    by_email = {e.email.lower(): e for e in people if e.email}
    departments = _Departments(list(await ctx.db.scalars(select(Department))))
    branches = {b.name.lower(): b.id for b in await ctx.db.scalars(select(Branch))}

    plans: list[Plan] = []
    seen_codes: dict[str, int] = {}
    seen_emails: dict[str, int] = {}
    for row in sheet.rows:
        plan = Plan(row, row.cells.get("full_name", ""))
        plans.append(plan)

        def fail(column: str, message: str, plan: Plan = plan) -> None:
            plan.errors.append(
                CellError(column=header.get(column, leave_header.get(column, column)), message=message)
            )

        values: dict[str, Any] = {k: row.cells[k] for k in PROFILE if k in row.cells}
        if "employment_type" in values:
            kind = parse.parse_employment_type(values["employment_type"])
            if kind is None:
                fail("employment_type", "Use full time, part time, contract, intern or daily.")
                del values["employment_type"]
            else:
                values["employment_type"] = kind
        for key in DATES:
            if key in row.cells:
                parsed = parse.parse_date(row.cells[key])
                if parsed is None:
                    fail(key, "Write the date like 2024-01-15 or 15/01/2024.")
                else:
                    values[key] = parsed
        if not plan.name:
            fail("full_name", "Every person needs a name.")
        try:
            checked = EmployeeIn.model_validate({"full_name": plan.name or "-", **values})
        except ValidationError as error:
            for issue in error.errors():
                key = str(issue["loc"][0]) if issue["loc"] else "full_name"
                fail(key, _friendly(key, issue))
                values.pop(key, None)
        else:
            values = {k: getattr(checked, k) for k in values}
            if checked.email:
                values["email"] = checked.email.lower()

        # Who this is: an existing profile, matched by code and then by email.
        code = str(values.get("employee_code") or "").lower()
        email = str(values.get("email") or "").lower()
        if code and code in seen_codes:
            fail("employee_code", f"Line {seen_codes[code]} has the same code.")
        if email and email in seen_emails:
            fail("email", f"Line {seen_emails[email]} has the same email.")
        if code:
            seen_codes.setdefault(code, row.line)
        if email:
            seen_emails.setdefault(email, row.line)
        match_code, match_email = by_code.get(code), by_email.get(email)
        if match_code and match_email and match_code.id != match_email.id:
            fail(
                "email",
                f"This email belongs to {match_email.full_name}, but the code to {match_code.full_name}.",
            )
        plan.employee = match_code or match_email
        if plan.employee is not None and plan.employee.status != "active":
            fail("full_name", "This person has left. Bring them back on their profile first.")

        if "department" in row.cells:
            path = tuple(parse.department_path(row.cells["department"]))
            if not path:
                fail("department", "Write a department name.")
            elif any(len(part) > 120 for part in path):
                fail("department", "Department names can be up to 120 characters.")
            else:
                plan.department = path
        if "branch" in row.cells:
            branch = branches.get(row.cells["branch"].strip().lower())
            if branch is None:
                fail("branch", f"There's no branch called “{row.cells['branch']}”. Add it in Settings first.")
            else:
                plan.branch_id = branch
        for name, text in row.leave.items():
            leave_type = by_name[name]
            days = parse.parse_days(text)
            if leave_type.days_per_year is None:
                fail(name, f"{leave_type.name} has no limit, so there are no days left to set.")
            elif days is None:
                fail(name, "Write the days left, like 10 or 7.5.")
            else:
                plan.leave[leave_type.id] = days
        plan.values = values

    await _changes(ctx, plans, departments, by_name)
    return sheet, plans, departments, by_name


async def _changes(
    ctx: Ctx, plans: list[Plan], departments: _Departments, kinds: dict[str, LeaveType]
) -> None:
    """What would change for people who already have a profile."""
    existing = [p for p in plans if p.employee is not None and not p.errors]
    assert ctx.tenant is not None
    now = today(ctx.tenant.timezone)
    left = await balances(ctx.db, [p.employee for p in existing if p.employee], now.year, now)
    names = {k.id: k.name for k in kinds.values()}
    for plan in existing:
        employee = plan.employee
        assert employee is not None
        for key, value in plan.values.items():
            if getattr(employee, key) != value:
                plan.changes.append(key)
        if plan.department is not None and departments.find(plan.department) != employee.department_id:
            plan.changes.append("department")
        if plan.branch_id is not None and plan.branch_id != employee.branch_id:
            plan.changes.append("branch")
        available = {b.leave_type_id: b.available for b in left.get(employee.id, [])}
        for kind_id, days in plan.leave.items():
            if available.get(kind_id) is None or Decimal(str(available[kind_id])) != days:
                plan.changes.append(names[kind_id])


def _out(sheet: parse.Sheet, plans: list[Plan], departments: _Departments, committed: bool) -> ImportOut:
    new: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()  # "Design" and "design" are one department
    for plan in plans:
        if plan.department is not None and not plan.errors:
            for path in departments.missing(plan.department):
                key = tuple(part.lower() for part in path)
                if key not in seen:
                    seen.add(key)
                    new.append(path)
    return ImportOut(
        committed=committed,
        columns=[ColumnOut(header=c.header, field=c.field, leave_type=c.leave_type) for c in sheet.columns],
        rows=[
            RowOut(line=p.row.line, name=p.name, action=p.action, changes=p.changes, errors=p.errors)
            for p in plans
        ],
        create=sum(p.action == "create" for p in plans),
        update=sum(p.action == "update" for p in plans),
        unchanged=sum(p.action == "unchanged" for p in plans),
        errors=sum(p.action == "error" for p in plans),
        new_departments=[" / ".join(path) for path in new],
    )


async def preview(ctx: Ctx, data: bytes) -> ImportOut:
    _require(ctx)
    sheet, plans, departments, _ = await _plan(ctx, data)
    return _out(sheet, plans, departments, committed=False)


async def run(ctx: Ctx, data: bytes) -> ImportOut:
    """Import for real: everything in the file, or nothing."""
    _require(ctx)
    sheet, plans, departments, _ = await _plan(ctx, data)
    result = _out(sheet, plans, departments, committed=True)
    if result.errors:
        raise Invalid(
            "Some rows still have problems. Fix them in the file and try again.", code="import_has_errors"
        )
    assert ctx.tenant is not None
    await check_people_limit(ctx.db, ctx.tenant.id, adding=result.create)

    for path in [tuple(p.split(" / ")) for p in result.new_departments]:
        parent = departments.find(path[:-1]) if len(path) > 1 else None
        department = Department(id=uuid7(), name=path[-1], parent_id=parent)
        ctx.db.add(department)
        departments.ids[(parent, path[-1].lower())] = department.id
        await audit.record(
            ctx.db,
            "department.created",
            target_type="department",
            target_id=department.id,
            data={"name": department.name, "parent_id": parent, "source": "import"},
        )
    await ctx.db.flush()

    touched: list[Plan] = []
    for plan in plans:
        if plan.action == "unchanged":
            continue
        department_id = departments.find(plan.department) if plan.department is not None else None
        employee = plan.employee
        if employee is None:
            employee = Employee(id=uuid7(), **plan.values)
            plan.employee = employee
            ctx.db.add(employee)
        else:
            for key, value in plan.values.items():
                setattr(employee, key, value)
        if plan.department is not None:
            employee.department_id = department_id
        if plan.branch_id is not None:
            employee.branch_id = plan.branch_id
        touched.append(plan)
    await ctx.db.flush()
    for plan in touched:
        assert plan.employee is not None
        await audit.record(
            ctx.db,
            "person.created" if plan.action == "create" else "person.updated",
            target_type="person",
            target_id=plan.employee.id,
            data={"name": plan.employee.full_name, "source": "import", "changes": plan.changes},
        )

    # Leave: record the difference between what they have and what the file says.
    with_leave = [p for p in touched if p.leave]
    now = today(ctx.tenant.timezone)
    left = await balances(ctx.db, [p.employee for p in with_leave if p.employee], now.year, now)
    for plan in with_leave:
        assert plan.employee is not None
        available = {b.leave_type_id: b.available for b in left.get(plan.employee.id, [])}
        for kind_id, days in plan.leave.items():
            current = Decimal(str(available.get(kind_id) or 0))
            if days != current:
                ctx.db.add(
                    LeaveAdjustment(
                        employee_id=plan.employee.id,
                        leave_type_id=kind_id,
                        year=now.year,
                        days=days - current,
                        reason=REASON,
                        created_by=ctx.user.id,
                    )
                )
    await audit.record(
        ctx.db,
        "people.imported",
        target_type="workspace",
        target_id=ctx.tenant.id,
        data={
            "created": result.create,
            "updated": result.update,
            "departments": len(result.new_departments),
        },
    )
    await ctx.db.commit()
    return result


async def template(ctx: Ctx, lang: str) -> str:
    """A CSV to fill in: our headers, the workspace's leave types, and one example row."""
    _require(ctx)
    words = TEMPLATE.get(lang, TEMPLATE["en"])
    kinds = [k for k in await _leave_types(ctx) if k.days_per_year is not None]
    keys = [k for k in words if k != "leave"]
    headers = [words[k] for k in keys] + [words["leave"].format(name=k.name) for k in kinds]
    example = [EXAMPLE.get(k, "") for k in keys] + [
        f"{Decimal(k.days_per_year or 0).normalize():f}" for k in kinds
    ]
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([safe_cell(h) for h in headers])
    writer.writerow([safe_cell(v) for v in example])
    return "﻿" + out.getvalue()
