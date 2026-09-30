"""People and departments API."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import EmailStr, StringConstraints, model_validator
from sqlalchemy import func, literal, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.errors import Conflict, Forbidden, Invalid, NotFound
from app.core.http import check_if_match, decode_cursor, encode_cursor, set_etag
from app.core.ids import uuid7
from app.core.schema import In, Name, Out, Page, ShortName
from app.core.security import crypto
from app.core.time import today
from app.modules.people.access import (
    DEPARTMENTS_MANAGE,
    PEOPLE_MANAGE,
    PEOPLE_VIEW,
    ancestors,
    in_scope,
    scope_departments,
)
from app.modules.people.models import EMPLOYMENT_TYPES, Department, Employee
from app.modules.people.service import check_people_limit, employee_for_membership, register_hooks
from app.modules.platform.deps import Ctx, allow
from app.modules.platform.models import Branch, Membership

register_hooks()

router = APIRouter(prefix="/v1", tags=["people"])

EmploymentType = Literal["full_time", "part_time", "contract", "intern", "daily"]
assert set(EMPLOYMENT_TYPES) == {"full_time", "part_time", "contract", "intern", "daily"}


# ---- Departments ------------------------------------------------------------------------


class DepartmentOut(Out):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    people: int
    version: int


class DepartmentIn(In):
    name: ShortName
    parent_id: uuid.UUID | None = None


class DepartmentPatch(In):
    name: ShortName | None = None
    parent_id: uuid.UUID | None = None
    move_to_top: bool = False


async def _department_counts(db: AsyncSession) -> dict[uuid.UUID, int]:
    rows = await db.execute(
        select(Employee.department_id, func.count())
        .where(Employee.status == "active", Employee.department_id.is_not(None))
        .group_by(Employee.department_id)
    )
    return {r[0]: r[1] for r in rows if r[0] is not None}


@router.get("/departments", response_model=list[DepartmentOut])
async def list_departments(ctx: Ctx = Depends(allow(None, module="people"))) -> list[DepartmentOut]:
    counts = await _department_counts(ctx.db)
    rows = await ctx.db.scalars(select(Department).order_by(func.lower(Department.name)))
    return [
        DepartmentOut(
            id=d.id, name=d.name, parent_id=d.parent_id, people=counts.get(d.id, 0), version=d.version
        )
        for d in rows
    ]


async def _sibling_name_free(
    db: AsyncSession, name: str, parent_id: uuid.UUID | None, exclude: uuid.UUID | None = None
) -> None:
    query = select(func.count()).select_from(Department).where(func.lower(Department.name) == name.lower())
    query = query.where(
        Department.parent_id.is_(None) if parent_id is None else Department.parent_id == parent_id
    )
    if exclude:
        query = query.where(Department.id != exclude)
    if await db.scalar(query):
        raise Invalid(
            errors=[{"field": "name", "message": "A department with this name already exists here."}]
        )


async def _existing_department(db: AsyncSession, department_id: uuid.UUID, field: str) -> Department:
    department = await db.get(Department, department_id)
    if department is None:
        raise Invalid(errors=[{"field": field, "message": "Unknown department."}])
    return department


@router.post("/departments", response_model=DepartmentOut, status_code=201)
async def create_department(
    body: DepartmentIn, ctx: Ctx = Depends(allow(DEPARTMENTS_MANAGE, module="people"))
) -> DepartmentOut:
    if body.parent_id is not None:
        await _existing_department(ctx.db, body.parent_id, "parent_id")
    await _sibling_name_free(ctx.db, body.name, body.parent_id)
    department = Department(name=body.name, parent_id=body.parent_id)
    ctx.db.add(department)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "department.created",
        target_type="department",
        target_id=department.id,
        data={"name": body.name, "parent_id": body.parent_id},
    )
    await ctx.db.commit()
    return DepartmentOut(
        id=department.id,
        name=department.name,
        parent_id=department.parent_id,
        people=0,
        version=department.version,
    )


@router.patch("/departments/{department_id}", response_model=DepartmentOut)
async def update_department(
    department_id: uuid.UUID,
    body: DepartmentPatch,
    request: Request,
    response: Response,
    ctx: Ctx = Depends(allow(DEPARTMENTS_MANAGE, module="people")),
) -> DepartmentOut:
    department = await ctx.db.scalar(
        select(Department).where(Department.id == department_id).with_for_update()
    )
    if department is None:
        raise NotFound()
    check_if_match(request, department.version)
    before = {"name": department.name, "parent_id": department.parent_id}
    new_parent = department.parent_id
    if body.move_to_top:
        new_parent = None
    elif body.parent_id is not None:
        await _existing_department(ctx.db, body.parent_id, "parent_id")
        # Moving under yourself or one of your descendants would make a loop.
        if department.id in await ancestors(ctx.db, body.parent_id):
            raise Invalid(
                errors=[{"field": "parent_id", "message": "A department can't be moved inside itself."}]
            )
        new_parent = body.parent_id
    new_name = body.name or department.name
    if new_name.lower() != department.name.lower() or new_parent != department.parent_id:
        await _sibling_name_free(ctx.db, new_name, new_parent, exclude=department.id)
    department.name = new_name
    department.parent_id = new_parent
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "department.updated",
        target_type="department",
        target_id=department.id,
        data={"before": before, "after": {"name": new_name, "parent_id": new_parent}},
    )
    await ctx.db.commit()
    set_etag(response, department.version)
    counts = await _department_counts(ctx.db)
    return DepartmentOut(
        id=department.id,
        name=department.name,
        parent_id=department.parent_id,
        people=counts.get(department.id, 0),
        version=department.version,
    )


@router.delete("/departments/{department_id}", status_code=204)
async def delete_department(
    department_id: uuid.UUID, ctx: Ctx = Depends(allow(DEPARTMENTS_MANAGE, module="people"))
) -> None:
    department = await ctx.db.scalar(
        select(Department).where(Department.id == department_id).with_for_update()
    )
    if department is None:
        raise NotFound()
    children = await ctx.db.scalar(
        select(func.count()).select_from(Department).where(Department.parent_id == department.id)
    )
    if children:
        raise Conflict("Move or delete the departments inside it first.", code="department_has_children")
    people = await ctx.db.scalar(
        select(func.count()).select_from(Employee).where(Employee.department_id == department.id)
    )
    if people:
        raise Conflict("Move the people in this department first.", code="department_has_people")
    scoped = await ctx.db.scalar(
        select(func.count())
        .select_from(Membership)
        .where(Membership.scope_department_id == department.id, Membership.status != "removed")
    )
    if scoped:
        raise Conflict(
            "Some members manage this department. Change their scope first.", code="department_in_scope"
        )
    await audit.record(
        ctx.db,
        "department.deleted",
        target_type="department",
        target_id=department.id,
        data={"name": department.name},
    )
    await ctx.db.delete(department)
    await ctx.db.commit()


# ---- People -----------------------------------------------------------------------------


class EmployeeOut(Out):
    id: uuid.UUID
    membership_id: uuid.UUID | None
    employee_code: str | None
    full_name: str
    preferred_name: str | None
    email: str | None
    phone: str | None
    department_id: uuid.UUID | None
    branch_id: uuid.UUID | None
    job_title: str | None
    employment_type: str
    status: str
    joined_on: date | None
    left_on: date | None
    date_of_birth: date | None
    national_id_last4: str | None
    notes: str | None
    created_at: datetime
    version: int


Code = Annotated[str, StringConstraints(max_length=40, strip_whitespace=True)]
Phone = Annotated[str, StringConstraints(max_length=40, pattern=r"^[0-9+()\-\s.]{3,40}$")]
NationalId = Annotated[str, StringConstraints(max_length=40, strip_whitespace=True)]
Title = Annotated[str, StringConstraints(max_length=120, strip_whitespace=True)]
Notes = Annotated[str, StringConstraints(max_length=5000)]


class EmployeeIn(In):
    full_name: Name
    preferred_name: ShortName | None = None
    employee_code: Code | None = None
    email: EmailStr | None = None
    phone: Phone | None = None
    department_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    job_title: Title | None = None
    employment_type: EmploymentType = "full_time"
    joined_on: date | None = None
    date_of_birth: date | None = None
    national_id: NationalId | None = None
    notes: Notes | None = None

    @model_validator(mode="after")
    def _dates(self) -> EmployeeIn:
        if self.date_of_birth and self.date_of_birth > today("Pacific/Kiritimati"):
            raise ValueError("Date of birth can't be in the future.")
        if self.date_of_birth and self.date_of_birth.year < 1900:
            raise ValueError("Check the date of birth.")
        return self


class EmployeePatch(In):
    full_name: Name | None = None
    preferred_name: ShortName | None = None
    employee_code: Code | None = None
    email: EmailStr | None = None
    phone: Phone | None = None
    department_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    job_title: Title | None = None
    employment_type: EmploymentType | None = None
    status: Literal["active", "inactive", "left"] | None = None
    joined_on: date | None = None
    left_on: date | None = None
    date_of_birth: date | None = None
    national_id: NationalId | None = None
    notes: Notes | None = None
    clear: list[
        Literal[
            "department_id",
            "branch_id",
            "employee_code",
            "email",
            "phone",
            "job_title",
            "preferred_name",
            "left_on",
            "date_of_birth",
            "national_id",
            "notes",
        ]
    ] = []


def _nid_context(employee_id: uuid.UUID) -> str:
    return f"employee:{employee_id}:national_id"


def _out(e: Employee) -> EmployeeOut:
    last4 = None
    if e.national_id_enc:
        try:
            last4 = crypto.decrypt(e.national_id_enc, context=_nid_context(e.id))[-4:]
        except (ValueError, KeyError):
            last4 = None
    return EmployeeOut(
        id=e.id,
        membership_id=e.membership_id,
        employee_code=e.employee_code,
        full_name=e.full_name,
        preferred_name=e.preferred_name,
        email=e.email,
        phone=e.phone,
        department_id=e.department_id,
        branch_id=e.branch_id,
        job_title=e.job_title,
        employment_type=e.employment_type,
        status=e.status,
        joined_on=e.joined_on,
        left_on=e.left_on,
        date_of_birth=e.date_of_birth,
        national_id_last4=last4,
        notes=e.notes,
        created_at=e.created_at,
        version=e.version,
    )


async def _validate_refs(ctx: Ctx, department_id: uuid.UUID | None, branch_id: uuid.UUID | None) -> None:
    if department_id is not None:
        await _existing_department(ctx.db, department_id, "department_id")
        if not await in_scope(ctx, department_id):
            raise Forbidden("You can only add people to your own department.", code="out_of_scope")
    elif await scope_departments(ctx) is not None:
        raise Invalid(errors=[{"field": "department_id", "message": "Choose a department."}])
    if branch_id is not None and await ctx.db.get(Branch, branch_id) is None:
        raise Invalid(errors=[{"field": "branch_id", "message": "Unknown branch."}])


async def _code_free(db: AsyncSession, code: str | None, exclude: uuid.UUID | None = None) -> None:
    if not code:
        return
    query = (
        select(func.count()).select_from(Employee).where(func.lower(Employee.employee_code) == code.lower())
    )
    if exclude:
        query = query.where(Employee.id != exclude)
    if await db.scalar(query):
        raise Invalid(errors=[{"field": "employee_code", "message": "Another person already has this code."}])


@router.get("/people", response_model=Page[EmployeeOut])
async def list_people(
    ctx: Ctx = Depends(allow(PEOPLE_VIEW, module="people")),
    q: Annotated[str | None, Query(max_length=100)] = None,
    department_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    status: Literal["active", "inactive", "left", "all"] = "active",
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> Page[EmployeeOut]:
    query = select(Employee)
    scope = await scope_departments(ctx)
    if scope is not None:
        query = query.where(Employee.department_id.in_(scope))
    if status != "all":
        query = query.where(Employee.status == status)
    if department_id:
        query = query.where(Employee.department_id == department_id)
    if branch_id:
        query = query.where(Employee.branch_id == branch_id)
    if q:
        like = f"%{q.strip().lower().replace('%', r'\%').replace('_', r'\_')}%"
        query = query.where(
            or_(
                func.lower(Employee.full_name).like(like),
                func.lower(Employee.preferred_name).like(like),
                func.lower(Employee.employee_code).like(like),
                func.lower(Employee.email).like(like),
                Employee.phone.like(like),
            )
        )
    after = decode_cursor(cursor)
    if after:
        query = query.where(
            tuple_(func.lower(Employee.full_name), Employee.id)
            > tuple_(literal(str(after["n"])), literal(uuid.UUID(str(after["id"]))))
        )
    rows = (
        await ctx.db.scalars(query.order_by(func.lower(Employee.full_name), Employee.id).limit(limit + 1))
    ).all()
    items = [_out(e) for e in rows[:limit]]
    next_cursor = (
        encode_cursor({"n": items[-1].full_name.lower(), "id": items[-1].id}) if len(rows) > limit else None
    )
    return Page(items=items, next_cursor=next_cursor)


@router.get("/people/me", response_model=EmployeeOut)
async def my_profile(ctx: Ctx = Depends(allow(None, module="people"))) -> EmployeeOut:
    assert ctx.membership is not None
    employee = await employee_for_membership(ctx.db, ctx.membership.id)
    if employee is None:
        raise NotFound("You don't have a profile in this workspace yet.")
    return _out(employee)


async def _visible_employee(ctx: Ctx, employee_id: uuid.UUID, *, lock: bool = False) -> Employee:
    query = select(Employee).where(Employee.id == employee_id)
    if lock:
        query = query.with_for_update()
    employee = await ctx.db.scalar(query)
    if employee is None or not await in_scope(ctx, employee.department_id):
        raise NotFound()
    return employee


@router.get("/people/{employee_id}", response_model=EmployeeOut)
async def get_person(
    employee_id: uuid.UUID, response: Response, ctx: Ctx = Depends(allow(None, module="people"))
) -> EmployeeOut:
    own = ctx.membership is not None and await ctx.db.scalar(
        select(func.count())
        .select_from(Employee)
        .where(Employee.id == employee_id, Employee.membership_id == ctx.membership.id)
    )
    if not own:
        ctx.require(PEOPLE_VIEW)
        employee = await _visible_employee(ctx, employee_id)
    else:
        found = await ctx.db.get(Employee, employee_id)
        assert found is not None
        employee = found
    set_etag(response, employee.version)
    return _out(employee)


@router.post("/people", response_model=EmployeeOut, status_code=201)
async def create_person(
    body: EmployeeIn, response: Response, ctx: Ctx = Depends(allow(PEOPLE_MANAGE, module="people"))
) -> EmployeeOut:
    await _validate_refs(ctx, body.department_id, body.branch_id)
    await _code_free(ctx.db, body.employee_code)
    await check_people_limit(ctx.db, ctx.tenant_id)
    data = body.model_dump(exclude={"national_id"})
    employee = Employee(id=uuid7(), **data)
    if body.national_id:
        employee.national_id_enc = crypto.encrypt(body.national_id, context=_nid_context(employee.id))
    employee.email = body.email.lower() if body.email else None
    ctx.db.add(employee)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "person.created",
        target_type="person",
        target_id=employee.id,
        data={"name": body.full_name, "department_id": body.department_id},
    )
    await ctx.db.commit()
    set_etag(response, employee.version)
    return _out(employee)


@router.patch("/people/{employee_id}", response_model=EmployeeOut)
async def update_person(
    employee_id: uuid.UUID,
    body: EmployeePatch,
    request: Request,
    response: Response,
    ctx: Ctx = Depends(allow(PEOPLE_MANAGE, module="people")),
) -> EmployeeOut:
    employee = await _visible_employee(ctx, employee_id, lock=True)
    check_if_match(request, employee.version)
    changes = body.model_dump(exclude_unset=True, exclude_none=True, exclude={"clear", "national_id"})
    for field in body.clear:
        changes[field if field != "national_id" else "national_id_enc"] = None
    new_department = changes.get("department_id", employee.department_id)
    new_branch = changes.get("branch_id", employee.branch_id)
    if "department_id" in changes or "branch_id" in changes:
        await _validate_refs(ctx, new_department, new_branch if "branch_id" in changes else None)
    if changes.get("employee_code"):
        await _code_free(ctx.db, changes["employee_code"], exclude=employee.id)
    if changes.get("status") == "active" and employee.status != "active":
        await check_people_limit(ctx.db, ctx.tenant_id)
    if changes.get("email"):
        changes["email"] = changes["email"].lower()
    if changes.get("status") == "left" and not changes.get("left_on") and not employee.left_on:
        assert ctx.tenant is not None
        changes["left_on"] = today(ctx.tenant.timezone)
    joined = changes.get("joined_on", employee.joined_on)
    left = changes.get("left_on", employee.left_on)
    if joined and left and left < joined:
        raise Invalid(
            errors=[{"field": "left_on", "message": "The leaving date is before the joining date."}]
        )
    before = {k: getattr(employee, k) for k in changes if k != "national_id_enc"}
    for key, value in changes.items():
        setattr(employee, key, value)
    if body.national_id:
        employee.national_id_enc = crypto.encrypt(body.national_id, context=_nid_context(employee.id))
    await ctx.db.flush()
    after = {k: v for k, v in changes.items() if k != "national_id_enc"}
    if body.national_id or "national_id_enc" in changes:
        after["national_id"] = "[changed]"
    await audit.record(
        ctx.db,
        "person.updated",
        target_type="person",
        target_id=employee.id,
        data={"before": before, "after": after},
    )
    await ctx.db.commit()
    set_etag(response, employee.version)
    return _out(employee)
