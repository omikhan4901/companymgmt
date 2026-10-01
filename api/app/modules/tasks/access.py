"""Task permissions and who may see or change what.

- Everyone with `tasks.self` works on their own tasks and on the tasks of projects they
  are a member of, and can keep personal to-dos.
- `tasks.manage` creates and runs projects and sees every task in the holder's
  department scope (a project's home department, or the assignee's department).
"""

from __future__ import annotations

import uuid

from app.core import permissions as perms
from app.core.errors import Forbidden
from app.modules.people.access import in_scope
from app.modules.people.models import Employee
from app.modules.platform.deps import Ctx
from app.modules.tasks.models import Project, Task

SELF = perms.register("tasks.self", "Work on your own tasks and your projects", module="tasks")
MANAGE = perms.register(
    "tasks.manage", "Create projects and manage every task in scope", module="tasks", scoped=True
)


async def manages_project(ctx: Ctx, project: Project) -> bool:
    if not ctx.can(MANAGE):
        return False
    if project.department_id is None:
        # Projects without a home department belong to people who manage everyone.
        return ctx.scope_department_id is None
    return await in_scope(ctx, project.department_id)


async def sees_project(ctx: Ctx, project: Project, me: Employee | None) -> bool:
    if me is not None and me.id in (project.member_ids or []):
        return True
    return await manages_project(ctx, project)


async def manages_person(ctx: Ctx, employee: Employee | None) -> bool:
    return employee is not None and ctx.can(MANAGE) and await in_scope(ctx, employee.department_id)


async def sees_task(
    ctx: Ctx, task: Task, project: Project | None, me: Employee | None, assignee: Employee | None
) -> bool:
    if task.created_by == ctx.user.id or (me is not None and task.assignee_id == me.id):
        return True
    if project is not None:
        return await sees_project(ctx, project, me)
    return await manages_person(ctx, assignee)


def require(condition: bool) -> None:
    if not condition:
        raise Forbidden()


def member_of(project: Project, employee_id: uuid.UUID | None) -> bool:
    return employee_id is not None and employee_id in (project.member_ids or [])
