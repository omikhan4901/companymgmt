"""The context builder: who is asking, in which workspace, with what reach.

Every AI request starts from the same `Ctx` as an API call; this turns it into the plain
facts a model needs (and logs need) without any access of its own: tenant, user, role,
permissions, department scope, branch, language, time zone and today's date there.
"""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel

from app.core.time import today
from app.modules.people.access import scope_departments
from app.modules.people.models import Department, Employee
from app.modules.people.service import employee_for_membership
from app.modules.platform.deps import Ctx


class RequestContext(BaseModel):
    tenant_id: uuid.UUID
    workspace: str
    country: str | None
    currency: str
    timezone: str
    today: date
    language: str
    user_id: uuid.UUID
    user_name: str
    role_key: str
    role_name: str
    permissions: list[str]
    modules: list[str]
    # "workspace": scoped permissions reach everyone; "department": only these departments.
    scope: str
    scope_department_ids: list[uuid.UUID] | None
    employee_id: uuid.UUID | None
    department: str | None
    branch_id: uuid.UUID | None


async def build_context(ctx: Ctx) -> RequestContext:
    assert ctx.tenant is not None
    assert ctx.role is not None
    assert ctx.membership is not None
    assert ctx.entitlements is not None
    employee: Employee | None = await employee_for_membership(ctx.db, ctx.membership.id)
    department = (
        await ctx.db.get(Department, employee.department_id) if employee and employee.department_id else None
    )
    scope = await scope_departments(ctx)
    return RequestContext(
        tenant_id=ctx.tenant.id,
        workspace=ctx.tenant.name,
        country=ctx.tenant.country,
        currency=ctx.tenant.currency,
        timezone=ctx.tenant.timezone,
        today=today(ctx.tenant.timezone),
        language=ctx.user.locale or ctx.tenant.locale,
        user_id=ctx.user.id,
        user_name=ctx.user.name,
        role_key=ctx.role.key,
        role_name=ctx.role.name,
        permissions=sorted(ctx.permissions),
        modules=sorted(ctx.entitlements.modules),
        scope="workspace" if scope is None else "department",
        scope_department_ids=scope,
        employee_id=employee.id if employee else None,
        department=department.name if department else None,
        branch_id=employee.branch_id if employee else None,
    )
