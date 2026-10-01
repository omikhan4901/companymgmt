"""Tasks API: projects, tasks, board moves, checklists and comments.

Each route only checks who may call it and hands over to `service`.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.http import check_if_match, set_etag
from app.modules.platform.deps import Ctx, allow
from app.modules.tasks import access, onboarding, service
from app.modules.tasks.schemas import (
    ChecklistIn,
    ChecklistItemOut,
    ChecklistPatch,
    CommentIn,
    CommentOut,
    MoveIn,
    ProjectIn,
    ProjectOut,
    ProjectPatch,
    RunOut,
    StartIn,
    TaskDetail,
    TaskIn,
    TaskOut,
    TaskPatch,
    TemplateIn,
    TemplateOut,
)

onboarding.register_hooks()

router = APIRouter(prefix="/v1", tags=["tasks"])
MODULE = "tasks"
Self = Depends(allow(access.SELF, module=MODULE))


@router.get("/projects", response_model=list[ProjectOut])
async def list_projects(
    ctx: Ctx = Self, status: Literal["active", "archived", "all"] = "active"
) -> list[ProjectOut]:
    return await service.list_projects(ctx, status=status)


@router.post("/projects", response_model=ProjectOut, status_code=201)
async def create_project(
    body: ProjectIn, ctx: Ctx = Depends(allow(access.MANAGE, module=MODULE))
) -> ProjectOut:
    return await service.create_project(ctx, body)


@router.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project(project_id: uuid.UUID, response: Response, ctx: Ctx = Self) -> ProjectOut:
    project = await service.get_project(ctx, project_id)
    set_etag(response, project.version)
    return project


@router.patch("/projects/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectPatch,
    request: Request,
    response: Response,
    ctx: Ctx = Depends(allow(access.MANAGE, module=MODULE)),
) -> ProjectOut:
    check_if_match(request, (await service.get_project(ctx, project_id)).version)
    project = await service.update_project(ctx, project_id, body)
    set_etag(response, project.version)
    return project


@router.get("/tasks", response_model=list[TaskOut])
async def list_tasks(
    ctx: Ctx = Self,
    project_id: uuid.UUID | None = None,
    mine: bool = False,
    assignee_id: uuid.UUID | None = None,
    status: Literal["todo", "doing", "done", "open", "all"] = "all",
    due_before: date | None = None,
    limit: int = Query(default=500, ge=1, le=1000),
) -> list[TaskOut]:
    return await service.list_tasks(
        ctx,
        project_id=project_id,
        mine=mine,
        assignee_id=assignee_id,
        status=status,
        due_before=due_before,
        limit=limit,
    )


@router.get("/tasks/my-work", response_model=list[TaskOut])
async def my_work(ctx: Ctx = Self) -> list[TaskOut]:
    return await service.my_work(ctx)


@router.post("/tasks", response_model=TaskDetail, status_code=201)
async def create_task(body: TaskIn, ctx: Ctx = Self) -> TaskDetail:
    return await service.create_task(ctx, body)


@router.get("/tasks/{task_id}", response_model=TaskDetail)
async def get_task(task_id: uuid.UUID, response: Response, ctx: Ctx = Self) -> TaskDetail:
    task = await service.get_task(ctx, task_id)
    set_etag(response, task.version)
    return task


@router.patch("/tasks/{task_id}", response_model=TaskDetail)
async def update_task(
    task_id: uuid.UUID, body: TaskPatch, request: Request, response: Response, ctx: Ctx = Self
) -> TaskDetail:
    check_if_match(request, (await service.get_task(ctx, task_id)).version)
    task = await service.update_task(ctx, task_id, body)
    set_etag(response, task.version)
    return task


@router.post("/tasks/{task_id}/move", response_model=TaskOut)
async def move_task(task_id: uuid.UUID, body: MoveIn, ctx: Ctx = Self) -> TaskOut:
    return await service.move_task(ctx, task_id, body)


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: uuid.UUID, ctx: Ctx = Self) -> Response:
    await service.delete_task(ctx, task_id)
    return Response(status_code=204)


@router.post("/tasks/{task_id}/checklist", response_model=ChecklistItemOut, status_code=201)
async def add_item(task_id: uuid.UUID, body: ChecklistIn, ctx: Ctx = Self) -> ChecklistItemOut:
    return await service.add_item(ctx, task_id, body)


@router.patch("/tasks/{task_id}/checklist/{item_id}", response_model=ChecklistItemOut)
async def update_item(
    task_id: uuid.UUID, item_id: uuid.UUID, body: ChecklistPatch, ctx: Ctx = Self
) -> ChecklistItemOut:
    return await service.update_item(ctx, task_id, item_id, body)


@router.delete("/tasks/{task_id}/checklist/{item_id}", status_code=204)
async def delete_item(task_id: uuid.UUID, item_id: uuid.UUID, ctx: Ctx = Self) -> Response:
    await service.delete_item(ctx, task_id, item_id)
    return Response(status_code=204)


@router.get("/tasks/{task_id}/comments", response_model=list[CommentOut])
async def list_comments(task_id: uuid.UUID, ctx: Ctx = Self) -> list[CommentOut]:
    return await service.list_comments(ctx, task_id)


@router.post("/tasks/{task_id}/comments", response_model=CommentOut, status_code=201)
async def add_comment(task_id: uuid.UUID, body: CommentIn, ctx: Ctx = Self) -> CommentOut:
    return await service.add_comment(ctx, task_id, body)


@router.delete("/tasks/{task_id}/comments/{comment_id}", status_code=204)
async def delete_comment(task_id: uuid.UUID, comment_id: uuid.UUID, ctx: Ctx = Self) -> Response:
    await service.delete_comment(ctx, task_id, comment_id)
    return Response(status_code=204)


# ---- Onboarding checklists -------------------------------------------------------------


@router.get("/onboarding/templates", response_model=list[TemplateOut])
async def list_templates(ctx: Ctx = Depends(allow(access.MANAGE, module=MODULE))) -> list[TemplateOut]:
    return await onboarding.list_templates(ctx)


@router.post("/onboarding/templates", response_model=TemplateOut, status_code=201)
async def create_template(
    body: TemplateIn, ctx: Ctx = Depends(allow(access.MANAGE, module=MODULE))
) -> TemplateOut:
    return await onboarding.save_template(ctx, body)


@router.put("/onboarding/templates/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: uuid.UUID, body: TemplateIn, ctx: Ctx = Depends(allow(access.MANAGE, module=MODULE))
) -> TemplateOut:
    return await onboarding.save_template(ctx, body, template_id)


@router.delete("/onboarding/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: uuid.UUID, ctx: Ctx = Depends(allow(access.MANAGE, module=MODULE))
) -> Response:
    await onboarding.delete_template(ctx, template_id)
    return Response(status_code=204)


@router.get("/onboarding/runs", response_model=list[RunOut])
async def list_runs(ctx: Ctx = Self, mine: bool = False) -> list[RunOut]:
    return await onboarding.runs(ctx, mine=mine)


@router.post("/onboarding/runs", response_model=RunOut, status_code=201)
async def start_run(body: StartIn, ctx: Ctx = Depends(allow(access.MANAGE, module=MODULE))) -> RunOut:
    return await onboarding.start(ctx, body.employee_id, body.template_id, body.start_date)
