"""Task capabilities (see platform/capabilities.py)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.platform.capabilities import NoInput, capability
from app.modules.platform.deps import Ctx
from app.modules.tasks import access, service
from app.modules.tasks.schemas import ProjectOut, TaskDetail, TaskIn, TaskOut

MODULE = "tasks"


@capability(
    "tasks.my_work",
    "Your open tasks, overdue and soonest due first.",
    output=list[TaskOut],
    permission=access.SELF,
    module=MODULE,
    route="GET /v1/tasks/my-work",
)
async def my_work(ctx: Ctx, _: NoInput) -> list[TaskOut]:
    return await service.my_work(ctx)


class TasksIn(BaseModel):
    project_id: uuid.UUID | None = None
    mine: bool = False
    assignee_id: uuid.UUID | None = None
    status: Literal["todo", "doing", "done", "open", "all"] = "all"
    due_before: date | None = Field(default=None, description="Due on or before this day")


@capability(
    "tasks.list",
    "Tasks you can see: in a project, for a person, by status or due date.",
    input=TasksIn,
    output=list[TaskOut],
    permission=access.SELF,
    module=MODULE,
    scoped=True,
    route="GET /v1/tasks",
)
async def tasks(ctx: Ctx, data: TasksIn) -> list[TaskOut]:
    return await service.list_tasks(
        ctx,
        project_id=data.project_id,
        mine=data.mine,
        assignee_id=data.assignee_id,
        status=data.status,
        due_before=data.due_before,
    )


class TaskRef(BaseModel):
    task_id: uuid.UUID


@capability(
    "tasks.get",
    "One task with its checklist.",
    input=TaskRef,
    output=TaskDetail,
    permission=access.SELF,
    module=MODULE,
    scoped=True,
    route="GET /v1/tasks/{task_id}",
)
async def task(ctx: Ctx, data: TaskRef) -> TaskDetail:
    return await service.get_task(ctx, data.task_id)


class ProjectsIn(BaseModel):
    status: Literal["active", "archived", "all"] = "active"


@capability(
    "tasks.projects",
    "Projects you're on (or manage), with open, done and overdue task counts.",
    input=ProjectsIn,
    output=list[ProjectOut],
    permission=access.SELF,
    module=MODULE,
    scoped=True,
    route="GET /v1/projects",
)
async def projects(ctx: Ctx, data: ProjectsIn) -> list[ProjectOut]:
    return await service.list_projects(ctx, status=data.status)


@capability(
    "tasks.create",
    "Create a task (for yourself, a project member, or someone you manage).",
    input=TaskIn,
    output=TaskDetail,
    permission=access.SELF,
    module=MODULE,
    kind="write",
    route="POST /v1/tasks",
)
async def create(ctx: Ctx, data: TaskIn) -> TaskDetail:
    return await service.create_task(ctx, data)
