"""Extension points so higher modules can react to platform events in the same
transaction, without the platform importing them (keeps module layering one-way)."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.models import Membership, User

MemberHook = Callable[[AsyncSession, Membership, User], Awaitable[None]]

member_joined: list[MemberHook] = []
member_removed: list[MemberHook] = []

# Checks a department id exists in the current workspace (registered by People).
DepartmentCheck = Callable[[AsyncSession, uuid.UUID], Awaitable[bool]]
department_exists: list[DepartmentCheck] = []


async def valid_department(db: AsyncSession, department_id: uuid.UUID) -> bool:
    return all([await check(db, department_id) for check in department_exists]) and bool(department_exists)


async def run(hooks: list[MemberHook], db: AsyncSession, membership: Membership, user: User) -> None:
    for hook in hooks:
        await hook(db, membership, user)
