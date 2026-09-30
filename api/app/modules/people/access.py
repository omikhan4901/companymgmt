"""People permissions and department-scope helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import permissions as perms
from app.modules.platform.deps import Ctx

PEOPLE_VIEW = perms.register("people.view", "See people's profiles", module="people", scoped=True)
PEOPLE_MANAGE = perms.register("people.manage", "Add and edit people", module="people", scoped=True)
DEPARTMENTS_MANAGE = perms.register("departments.manage", "Add and edit departments", module="people")


async def subtree(db: AsyncSession, root: uuid.UUID) -> list[uuid.UUID]:
    """A department and every department below it."""
    rows = await db.execute(
        text(
            """
            WITH RECURSIVE tree AS (
              SELECT id FROM departments WHERE id = :root
              UNION ALL
              SELECT d.id FROM departments d JOIN tree t ON d.parent_id = t.id
            )
            SELECT id FROM tree
            """
        ),
        {"root": root},
    )
    return [r[0] for r in rows]


async def ancestors(db: AsyncSession, department_id: uuid.UUID) -> list[uuid.UUID]:
    rows = await db.execute(
        text(
            """
            WITH RECURSIVE up AS (
              SELECT id, parent_id, 0 AS depth FROM departments WHERE id = :id
              UNION ALL
              SELECT d.id, d.parent_id, up.depth + 1 FROM departments d
              JOIN up ON d.id = up.parent_id WHERE up.depth < 100
            )
            SELECT id FROM up
            """
        ),
        {"id": department_id},
    )
    return [r[0] for r in rows]


async def scope_departments(ctx: Ctx) -> list[uuid.UUID] | None:
    """Departments this member's scoped permissions cover. None means the whole workspace."""
    if "scope" not in ctx.cache:
        root = ctx.scope_department_id
        ctx.cache["scope"] = None if root is None else await subtree(ctx.db, root)
    scope: list[uuid.UUID] | None = ctx.cache["scope"]
    return scope


async def in_scope(ctx: Ctx, department_id: uuid.UUID | None) -> bool:
    scope = await scope_departments(ctx)
    return scope is None or (department_id is not None and department_id in scope)
