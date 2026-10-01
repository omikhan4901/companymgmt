"""Tasks and projects. Routes and capabilities both call these functions.

Who sees what is decided in `access`; every function here starts from the caller's own
employee profile (`me`), which may be missing for an owner who isn't on the payroll.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from datetime import date

from sqlalchemy import ColumnElement, Select, and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit, events
from app.core.errors import Invalid, NotFound
from app.core.time import today, utcnow
from app.modules.people.access import scope_departments
from app.modules.people.models import Employee
from app.modules.people.service import employee_for_membership
from app.modules.platform import hooks
from app.modules.platform.deps import Ctx
from app.modules.platform.models import User
from app.modules.tasks import access
from app.modules.tasks.models import ChecklistItem, Project, Task, TaskComment
from app.modules.tasks.schemas import (
    ChecklistIn,
    ChecklistItemOut,
    ChecklistPatch,
    CommentIn,
    CommentOut,
    MoveIn,
    PersonRef,
    ProjectIn,
    ProjectOut,
    ProjectPatch,
    TaskDetail,
    TaskIn,
    TaskOut,
    TaskPatch,
)

STEP = 1024.0


# ---- Helpers ---------------------------------------------------------------------------


async def me(ctx: Ctx) -> Employee | None:
    if "tasks.me" not in ctx.cache:
        assert ctx.membership is not None
        ctx.cache["tasks.me"] = await employee_for_membership(ctx.db, ctx.membership.id)
    found: Employee | None = ctx.cache["tasks.me"]
    return found


async def _people(db: AsyncSession, ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, Employee]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    rows = await db.scalars(select(Employee).where(Employee.id.in_(wanted)))
    return {e.id: e for e in rows}


async def _user_names(db: AsyncSession, ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    rows = await db.execute(select(User.id, User.name).where(User.id.in_(wanted)))
    return {r[0]: r[1] for r in rows}


def _today(ctx: Ctx) -> date:
    assert ctx.tenant is not None
    return today(ctx.tenant.timezone)


async def _check_people(db: AsyncSession, ids: Sequence[uuid.UUID], field: str) -> None:
    if not ids:
        return
    found = set(await db.scalars(select(Employee.id).where(Employee.id.in_(ids), Employee.status != "left")))
    missing = [i for i in ids if i not in found]
    if missing:
        raise Invalid(errors=[{"field": field, "message": "Some of these people aren't in this workspace."}])


# ---- Projects ----------------------------------------------------------------------------


async def _project(ctx: Ctx, project_id: uuid.UUID, *, lock: bool = False) -> Project:
    query = select(Project).where(Project.id == project_id)
    if lock:
        query = query.with_for_update()
    project = await ctx.db.scalar(query)
    if project is None or not await access.sees_project(ctx, project, await me(ctx)):
        raise NotFound()
    return project


async def _project_out(ctx: Ctx, projects: Sequence[Project]) -> list[ProjectOut]:
    if not projects:
        return []
    ids = [p.id for p in projects]
    today_ = _today(ctx)
    counts = {
        row[0]: row[1:]
        for row in await ctx.db.execute(
            select(
                Task.project_id,
                func.count().filter(Task.status != "done"),
                func.count().filter(Task.status == "done"),
                func.count().filter(and_(Task.status != "done", Task.due_date < today_)),
            )
            .where(Task.project_id.in_(ids))
            .group_by(Task.project_id)
        )
    }
    people = await _people(ctx.db, [m for p in projects for m in (p.member_ids or [])])
    out = []
    for p in projects:
        open_, done, overdue = counts.get(p.id, (0, 0, 0))
        members = [PersonRef(id=m, name=people[m].full_name) for m in (p.member_ids or []) if m in people]
        out.append(
            ProjectOut(
                id=p.id,
                name=p.name,
                description=p.description,
                department_id=p.department_id,
                members=sorted(members, key=lambda r: r.name.lower()),
                status=p.status,
                color=p.color,
                due_date=p.due_date,
                open_tasks=open_,
                done_tasks=done,
                overdue_tasks=overdue,
                can_manage=await access.manages_project(ctx, p),
                version=p.version,
            )
        )
    return out


async def list_projects(ctx: Ctx, *, status: str = "active") -> list[ProjectOut]:
    query = select(Project).order_by(func.lower(Project.name))
    if status != "all":
        query = query.where(Project.status == status)
    mine = await me(ctx)
    scope = await scope_departments(ctx)
    if not ctx.can(access.MANAGE):
        if mine is None:
            return []
        query = query.where(Project.member_ids.contains([mine.id]))
    elif scope is not None:
        conditions: list[ColumnElement[bool]] = [Project.department_id.in_(scope)]
        if mine is not None:
            conditions.append(Project.member_ids.contains([mine.id]))
        query = query.where(or_(*conditions))
    return await _project_out(ctx, list(await ctx.db.scalars(query)))


async def get_project(ctx: Ctx, project_id: uuid.UUID) -> ProjectOut:
    return (await _project_out(ctx, [await _project(ctx, project_id)]))[0]


async def _check_department(ctx: Ctx, department_id: uuid.UUID | None) -> None:
    scope = await scope_departments(ctx)
    if department_id is None:
        if scope is not None:
            raise Invalid(errors=[{"field": "department_id", "message": "Choose one of your departments."}])
        return
    if not await hooks.valid_department(ctx.db, department_id) or (
        scope is not None and department_id not in scope
    ):
        raise Invalid(errors=[{"field": "department_id", "message": "Choose one of your departments."}])


async def create_project(ctx: Ctx, body: ProjectIn) -> ProjectOut:
    ctx.require(access.MANAGE)
    await _check_department(ctx, body.department_id)
    members = list(dict.fromkeys(body.member_ids))
    await _check_people(ctx.db, members, "member_ids")
    project = Project(
        name=body.name,
        description=body.description,
        department_id=body.department_id,
        member_ids=members,
        color=body.color,
        due_date=body.due_date,
        created_by=ctx.user.id,
    )
    ctx.db.add(project)
    await ctx.db.flush()
    await audit.record(
        ctx.db, "project.created", target_type="project", target_id=project.id, data={"name": project.name}
    )
    await _members_added(ctx, project, members)
    await ctx.db.commit()
    return await get_project(ctx, project.id)


async def _members_added(ctx: Ctx, project: Project, added: Sequence[uuid.UUID]) -> None:
    if not added:
        return
    people = await _people(ctx.db, added)
    await events.emit(
        ctx.db,
        "project.members_added",
        subject_type="project",
        subject_id=project.id,
        data={
            "project_name": project.name,
            "membership_ids": [people[i].membership_id for i in added if i in people],
        },
    )


async def update_project(ctx: Ctx, project_id: uuid.UUID, body: ProjectPatch) -> ProjectOut:
    project = await _project(ctx, project_id, lock=True)
    access.require(await access.manages_project(ctx, project))
    changes = body.model_dump(exclude_unset=True)
    if "department_id" in changes:
        await _check_department(ctx, body.department_id)
    added: list[uuid.UUID] = []
    if body.member_ids is not None:
        members = list(dict.fromkeys(body.member_ids))
        await _check_people(ctx.db, members, "member_ids")
        added = [m for m in members if m not in (project.member_ids or [])]
        changes["member_ids"] = members
    for key, value in changes.items():
        setattr(project, key, value)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "project.updated",
        target_type="project",
        target_id=project.id,
        data=body.model_dump(exclude_unset=True, mode="json"),
    )
    await _members_added(ctx, project, added)
    await ctx.db.commit()
    return await get_project(ctx, project.id)


# ---- Tasks ------------------------------------------------------------------------------


def _visible_tasks(ctx: Ctx, mine: Employee | None, scope: list[uuid.UUID] | None) -> Select[Task]:
    """Tasks the caller may see, as a query (mirrors access.sees_task)."""
    query = select(Task).outerjoin(Project, Project.id == Task.project_id)
    conditions: list[ColumnElement[bool]] = [Task.created_by == ctx.user.id]
    if mine is not None:
        conditions += [Task.assignee_id == mine.id, Project.member_ids.contains([mine.id])]
    if ctx.can(access.MANAGE):
        if scope is None:
            conditions.append(Project.id.is_not(None))
            conditions.append(Task.assignee_id.is_not(None))
        else:
            conditions.append(Project.department_id.in_(scope))
            in_scope = select(Employee.id).where(Employee.department_id.in_(scope))
            conditions.append(and_(Task.project_id.is_(None), Task.assignee_id.in_(in_scope)))
    return query.where(or_(*conditions))


async def _task_out(ctx: Ctx, tasks: Sequence[Task]) -> list[TaskOut]:
    if not tasks:
        return []
    ids = [t.id for t in tasks]
    checklist = {
        row[0]: (row[1], row[2])
        for row in await ctx.db.execute(
            select(ChecklistItem.task_id, func.count().filter(ChecklistItem.done), func.count())
            .where(ChecklistItem.task_id.in_(ids))
            .group_by(ChecklistItem.task_id)
        )
    }
    comments = dict(
        (
            await ctx.db.execute(
                select(TaskComment.task_id, func.count())
                .where(TaskComment.task_id.in_(ids))
                .group_by(TaskComment.task_id)
            )
        ).all()
    )
    projects = {
        p.id: p
        for p in await ctx.db.scalars(
            select(Project).where(Project.id.in_({t.project_id for t in tasks if t.project_id}))
        )
    }
    people = await _people(ctx.db, [t.assignee_id for t in tasks])
    creators = await _user_names(ctx.db, [t.created_by for t in tasks])
    today_ = _today(ctx)
    out = []
    for t in tasks:
        project = projects.get(t.project_id) if t.project_id else None
        assignee = people.get(t.assignee_id) if t.assignee_id else None
        done, total = checklist.get(t.id, (0, 0))
        out.append(
            TaskOut(
                id=t.id,
                title=t.title,
                description=t.description,
                project_id=t.project_id,
                project_name=project.name if project else None,
                status=t.status,
                priority=t.priority,
                assignee=PersonRef(id=assignee.id, name=assignee.full_name) if assignee else None,
                due_date=t.due_date,
                overdue=t.status != "done" and t.due_date is not None and t.due_date < today_,
                position=t.position,
                completed_at=t.completed_at,
                created_at=t.created_at,
                created_by_name=creators.get(t.created_by) if t.created_by else None,
                checklist_done=done,
                checklist_total=total,
                comments=comments.get(t.id, 0),
                can_delete=await _can_delete(ctx, t, project),
                onboarding=t.onboarding_run_id is not None,
                document_id=t.document_id,
                version=t.version,
            )
        )
    return out


async def _can_delete(ctx: Ctx, task: Task, project: Project | None) -> bool:
    if task.created_by == ctx.user.id:
        return True
    if project is not None:
        return await access.manages_project(ctx, project)
    assignee = await ctx.db.get(Employee, task.assignee_id) if task.assignee_id else None
    return await access.manages_person(ctx, assignee)


async def list_tasks(
    ctx: Ctx,
    *,
    project_id: uuid.UUID | None = None,
    mine: bool = False,
    assignee_id: uuid.UUID | None = None,
    status: str = "all",
    due_before: date | None = None,
    limit: int = 500,
) -> list[TaskOut]:
    me_ = await me(ctx)
    if project_id is not None:
        await _project(ctx, project_id)  # 404 unless visible
    query = _visible_tasks(ctx, me_, await scope_departments(ctx))
    if project_id is not None:
        query = query.where(Task.project_id == project_id)
    if mine:
        if me_ is None:
            return []
        query = query.where(Task.assignee_id == me_.id)
    if assignee_id is not None:
        query = query.where(Task.assignee_id == assignee_id)
    if status == "open":
        query = query.where(Task.status != "done")
    elif status != "all":
        query = query.where(Task.status == status)
    if due_before is not None:
        query = query.where(Task.due_date <= due_before)
    query = query.order_by(Task.status, Task.position, Task.created_at).limit(limit)
    return await _task_out(ctx, list(await ctx.db.scalars(query)))


async def my_work(ctx: Ctx) -> list[TaskOut]:
    """Your open tasks, the most pressing first (overdue, then by due date, then priority)."""
    tasks = await list_tasks(ctx, mine=True, status="open")
    rank = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
    return sorted(tasks, key=lambda t: (t.due_date is None, t.due_date or date.max, rank[t.priority]))


async def _task(ctx: Ctx, task_id: uuid.UUID, *, lock: bool = False) -> tuple[Task, Project | None]:
    query = select(Task).where(Task.id == task_id)
    if lock:
        query = query.with_for_update(of=Task)
    task = await ctx.db.scalar(query)
    if task is None:
        raise NotFound()
    project = await ctx.db.get(Project, task.project_id) if task.project_id else None
    assignee = await ctx.db.get(Employee, task.assignee_id) if task.assignee_id else None
    if not await access.sees_task(ctx, task, project, await me(ctx), assignee):
        raise NotFound()
    return task, project


async def get_task(ctx: Ctx, task_id: uuid.UUID) -> TaskDetail:
    task, _ = await _task(ctx, task_id)
    out = (await _task_out(ctx, [task]))[0]
    items = await ctx.db.scalars(
        select(ChecklistItem).where(ChecklistItem.task_id == task.id).order_by(ChecklistItem.position)
    )
    return TaskDetail(**out.model_dump(), checklist=[ChecklistItemOut.model_validate(i) for i in items])


async def _check_assignee(
    ctx: Ctx, project: Project | None, assignee_id: uuid.UUID | None
) -> Employee | None:
    """Project tasks go to project members; other tasks to yourself, or to someone you manage."""
    if assignee_id is None:
        return None
    mine = await me(ctx)
    person = await ctx.db.get(Employee, assignee_id)
    if person is None or person.status == "left":
        raise Invalid(errors=[{"field": "assignee_id", "message": "This person isn't in this workspace."}])
    if project is not None:
        if not access.member_of(project, assignee_id):
            raise Invalid(
                errors=[{"field": "assignee_id", "message": "Add this person to the project first."}],
                code="not_a_member",
            )
        return person
    if (mine is not None and mine.id == assignee_id) or await access.manages_person(ctx, person):
        return person
    raise Invalid(
        errors=[{"field": "assignee_id", "message": "You can only give tasks to people you manage."}],
        code="cannot_assign",
    )


async def _bottom(ctx: Ctx, project_id: uuid.UUID | None, status: str) -> float:
    query = select(func.max(Task.position)).where(Task.status == status)
    query = query.where(Task.project_id == project_id if project_id else Task.project_id.is_(None))
    top = await ctx.db.scalar(query)
    return (top or 0) + STEP


async def _emit(ctx: Ctx, name: str, task: Task, project: Project | None, **extra: object) -> None:
    assignee = await ctx.db.get(Employee, task.assignee_id) if task.assignee_id else None
    await events.emit(
        ctx.db,
        name,
        subject_type="task",
        subject_id=task.id,
        data={
            "title": task.title,
            "project_id": task.project_id,
            "project_name": project.name if project else None,
            "due_date": task.due_date,
            "assignee_id": task.assignee_id,
            "assignee_membership_id": assignee.membership_id if assignee else None,
            "creator_user_id": task.created_by,
            **extra,
        },
    )


async def create_task(ctx: Ctx, body: TaskIn) -> TaskDetail:
    mine = await me(ctx)
    project = None
    if body.project_id is not None:
        project = await _project(ctx, body.project_id)
        if project.status != "active":
            raise Invalid("This project is archived.", code="project_archived")
    if body.unassigned:
        assignee_id = None
    elif body.assignee_id is not None:
        assignee_id = body.assignee_id
    elif project is not None and not access.member_of(project, mine.id if mine else None):
        assignee_id = None  # a manager adding work to someone else's project
    else:
        assignee_id = mine.id if mine else None
    await _check_assignee(ctx, project, assignee_id)
    task = Task(
        project_id=body.project_id,
        title=body.title,
        description=body.description,
        status=body.status,
        priority=body.priority,
        assignee_id=assignee_id,
        due_date=body.due_date,
        position=await _bottom(ctx, body.project_id, body.status),
        completed_at=utcnow() if body.status == "done" else None,
        created_by=ctx.user.id,
    )
    ctx.db.add(task)
    await ctx.db.flush()
    for i, text in enumerate(body.checklist):
        ctx.db.add(ChecklistItem(task_id=task.id, text=text, position=(i + 1) * STEP))
    await audit.record(
        ctx.db, "task.created", target_type="task", target_id=task.id, data={"title": task.title}
    )
    if assignee_id is not None:
        await _emit(ctx, "task.assigned", task, project)
    await ctx.db.commit()
    return await get_task(ctx, task.id)


async def update_task(ctx: Ctx, task_id: uuid.UUID, body: TaskPatch) -> TaskDetail:
    task, project = await _task(ctx, task_id, lock=True)
    before_assignee, before_status = task.assignee_id, task.status
    if body.unassigned:
        task.assignee_id = None
    elif body.assignee_id is not None and body.assignee_id != task.assignee_id:
        await _check_assignee(ctx, project, body.assignee_id)
        task.assignee_id = body.assignee_id
    if body.title is not None:
        task.title = body.title
    if "description" in body.model_fields_set:
        task.description = body.description
    if body.no_due_date:
        task.due_date = None
    elif body.due_date is not None:
        task.due_date = body.due_date
    if body.priority is not None:
        task.priority = body.priority
    if body.status is not None and body.status != task.status:
        _set_status(task, body.status)
        task.position = await _bottom(ctx, task.project_id, body.status)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "task.updated",
        target_type="task",
        target_id=task.id,
        data=body.model_dump(exclude_unset=True, mode="json"),
    )
    await _after_change(ctx, task, project, before_assignee, before_status)
    await ctx.db.commit()
    return await get_task(ctx, task.id)


def _set_status(task: Task, status: str) -> None:
    task.status = status
    task.completed_at = utcnow() if status == "done" else None


async def _after_change(
    ctx: Ctx, task: Task, project: Project | None, before_assignee: uuid.UUID | None, before_status: str
) -> None:
    if task.assignee_id is not None and task.assignee_id != before_assignee:
        await _emit(ctx, "task.assigned", task, project)
    if task.status == "done" and before_status != "done":
        await _emit(ctx, "task.completed", task, project)


async def move_task(ctx: Ctx, task_id: uuid.UUID, body: MoveIn) -> TaskOut:
    """Drop a card in a column, after another card (or at the top)."""
    task, project = await _task(ctx, task_id, lock=True)
    before_status = task.status
    column = select(Task.position).where(Task.status == body.status, Task.id != task.id)
    column = column.where(
        Task.project_id == task.project_id if task.project_id else Task.project_id.is_(None)
    )
    if body.after_id is None:
        first = await ctx.db.scalar(column.order_by(Task.position).limit(1))
        position = (first if first is not None else STEP) - STEP
    else:
        after = await ctx.db.scalar(
            select(Task).where(Task.id == body.after_id, Task.project_id == task.project_id)
        )
        if after is None or after.status != body.status:
            raise Invalid("That card isn't in this column.", code="bad_position")
        following = await ctx.db.scalar(
            column.where(Task.position > after.position).order_by(Task.position).limit(1)
        )
        position = (after.position + following) / 2 if following is not None else after.position + STEP
    if body.status != task.status:
        _set_status(task, body.status)
    task.position = position
    await ctx.db.flush()
    await _after_change(ctx, task, project, task.assignee_id, before_status)
    await ctx.db.commit()
    return (await _task_out(ctx, [task]))[0]


async def delete_task(ctx: Ctx, task_id: uuid.UUID) -> None:
    task, project = await _task(ctx, task_id, lock=True)
    access.require(await _can_delete(ctx, task, project))
    await audit.record(
        ctx.db, "task.deleted", target_type="task", target_id=task.id, data={"title": task.title}
    )
    await ctx.db.execute(delete(Task).where(Task.id == task.id))
    await ctx.db.commit()


# ---- Checklists and comments -----------------------------------------------------------


async def add_item(ctx: Ctx, task_id: uuid.UUID, body: ChecklistIn) -> ChecklistItemOut:
    task, _ = await _task(ctx, task_id)
    top = await ctx.db.scalar(
        select(func.max(ChecklistItem.position)).where(ChecklistItem.task_id == task.id)
    )
    count = await ctx.db.scalar(
        select(func.count()).select_from(ChecklistItem).where(ChecklistItem.task_id == task.id)
    )
    if (count or 0) >= 100:
        raise Invalid("A checklist can have up to 100 items.", code="checklist_full")
    item = ChecklistItem(task_id=task.id, text=body.text, position=(top or 0) + STEP)
    ctx.db.add(item)
    await ctx.db.commit()
    return ChecklistItemOut.model_validate(item)


async def _item(ctx: Ctx, task_id: uuid.UUID, item_id: uuid.UUID) -> ChecklistItem:
    task, _ = await _task(ctx, task_id)
    item = await ctx.db.scalar(
        select(ChecklistItem).where(ChecklistItem.id == item_id, ChecklistItem.task_id == task.id)
    )
    if item is None:
        raise NotFound()
    return item


async def update_item(
    ctx: Ctx, task_id: uuid.UUID, item_id: uuid.UUID, body: ChecklistPatch
) -> ChecklistItemOut:
    item = await _item(ctx, task_id, item_id)
    if body.text is not None:
        item.text = body.text
    if body.done is not None:
        item.done = body.done
    await ctx.db.commit()
    return ChecklistItemOut.model_validate(item)


async def delete_item(ctx: Ctx, task_id: uuid.UUID, item_id: uuid.UUID) -> None:
    item = await _item(ctx, task_id, item_id)
    await ctx.db.delete(item)
    await ctx.db.commit()


async def list_comments(ctx: Ctx, task_id: uuid.UUID) -> list[CommentOut]:
    task, _ = await _task(ctx, task_id)
    rows = list(
        await ctx.db.scalars(
            select(TaskComment).where(TaskComment.task_id == task.id).order_by(TaskComment.created_at)
        )
    )
    names = await _user_names(ctx.db, [c.author_id for c in rows])
    return [
        CommentOut(
            id=c.id,
            author_name=names.get(c.author_id) if c.author_id else None,
            mine=c.author_id == ctx.user.id,
            body=c.body,
            created_at=c.created_at,
        )
        for c in rows
    ]


async def add_comment(ctx: Ctx, task_id: uuid.UUID, body: CommentIn) -> CommentOut:
    task, project = await _task(ctx, task_id)
    comment = TaskComment(task_id=task.id, author_id=ctx.user.id, body=body.body)
    ctx.db.add(comment)
    await ctx.db.flush()
    await _emit(ctx, "task.commented", task, project, excerpt=body.body[:140])
    await ctx.db.commit()
    return CommentOut(
        id=comment.id, author_name=ctx.user.name, mine=True, body=comment.body, created_at=comment.created_at
    )


async def delete_comment(ctx: Ctx, task_id: uuid.UUID, comment_id: uuid.UUID) -> None:
    task, _ = await _task(ctx, task_id)
    comment = await ctx.db.scalar(
        select(TaskComment).where(TaskComment.id == comment_id, TaskComment.task_id == task.id)
    )
    if comment is None:
        raise NotFound()
    access.require(comment.author_id == ctx.user.id)
    await ctx.db.delete(comment)
    await ctx.db.commit()
