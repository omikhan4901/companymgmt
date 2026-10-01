"""People rules shared by the routes, capabilities and other modules."""

from __future__ import annotations

import uuid
from typing import Literal

from sqlalchemy import func, literal, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound, PaymentRequired
from app.core.http import decode_cursor, encode_cursor
from app.core.schema import Page
from app.modules.people.access import PEOPLE_VIEW, in_scope, scope_departments
from app.modules.people.models import Department, Employee
from app.modules.people.schemas import EmployeeOut, employee_out
from app.modules.platform import hooks
from app.modules.platform.deps import Ctx, load_entitlements
from app.modules.platform.models import Membership, User


async def check_people_limit(db: AsyncSession, tenant_id: uuid.UUID, adding: int = 1) -> None:
    entitlements = await load_entitlements(db, tenant_id)
    limit = entitlements.plan.max_people
    if limit is None:
        return
    active = await db.scalar(select(func.count()).select_from(Employee).where(Employee.status == "active"))
    if (active or 0) + adding > limit:
        raise PaymentRequired(
            f"Your plan includes {limit} people. Upgrade to add more.",
            code="people_limit",
            extra={"limit": limit},
        )


async def employee_for_membership(db: AsyncSession, membership_id: uuid.UUID) -> Employee | None:
    return await db.scalar(select(Employee).where(Employee.membership_id == membership_id))


async def search_people(
    ctx: Ctx,
    *,
    q: str | None = None,
    department_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    status: Literal["active", "inactive", "left", "all"] = "active",
    cursor: str | None = None,
    limit: int = 50,
) -> Page[EmployeeOut]:
    """People this member may see (their department subtree for scoped roles)."""
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
    items = [employee_out(e) for e in rows[:limit]]
    next_cursor = (
        encode_cursor({"n": items[-1].full_name.lower(), "id": items[-1].id}) if len(rows) > limit else None
    )
    return Page(items=items, next_cursor=next_cursor)


async def visible_employee(ctx: Ctx, employee_id: uuid.UUID, *, lock: bool = False) -> Employee:
    query = select(Employee).where(Employee.id == employee_id)
    if lock:
        query = query.with_for_update()
    employee = await ctx.db.scalar(query)
    if employee is None or not await in_scope(ctx, employee.department_id):
        raise NotFound()
    return employee


async def get_person(ctx: Ctx, employee_id: uuid.UUID) -> Employee:
    """Your own profile, or someone in your scope if you may see people."""
    own = ctx.membership is not None and await ctx.db.scalar(
        select(func.count())
        .select_from(Employee)
        .where(Employee.id == employee_id, Employee.membership_id == ctx.membership.id)
    )
    if own:
        found = await ctx.db.get(Employee, employee_id)
        assert found is not None
        return found
    ctx.require(PEOPLE_VIEW)
    return await visible_employee(ctx, employee_id)


async def _on_member_joined(db: AsyncSession, membership: Membership, user: User) -> None:
    """Every member gets a People profile (so they can clock in) unless they have one."""
    existing = await employee_for_membership(db, membership.id)
    if existing is not None:
        if existing.status != "active":
            await check_people_limit(db, membership.tenant_id)
            existing.status = "active"
            existing.left_on = None
        return
    await check_people_limit(db, membership.tenant_id)
    db.add(
        Employee(
            membership_id=membership.id,
            full_name=user.name,
            email=user.email,
            department_id=membership.scope_department_id,
        )
    )
    await db.flush()


async def _department_exists(db: AsyncSession, department_id: uuid.UUID) -> bool:
    return (
        await db.scalar(select(func.count()).select_from(Department).where(Department.id == department_id))
    ) == 1


def register_hooks() -> None:
    if _on_member_joined not in hooks.member_joined:
        hooks.member_joined.append(_on_member_joined)
    if _department_exists not in hooks.department_exists:
        hooks.department_exists.append(_department_exists)
