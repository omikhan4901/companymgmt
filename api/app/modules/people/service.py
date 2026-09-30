"""People rules shared by the routes and other modules."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PaymentRequired
from app.modules.people.models import Department, Employee
from app.modules.platform import hooks
from app.modules.platform.deps import load_entitlements
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
