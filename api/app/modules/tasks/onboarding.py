"""Onboarding checklists: templates, and runs started for new joiners.

A run turns a template into ordinary tasks (so they show up in My work, on boards and in
reminders), each due some days after the person's start date. Items for "the manager" go
to whoever runs the joiner's department. Items that point at a document are ticked off by
themselves when the joiner acknowledges that document.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit, events
from app.core.errors import Forbidden, Invalid, NotFound
from app.core.time import today, utcnow
from app.modules.people.access import ancestors
from app.modules.people.models import Employee
from app.modules.platform import catalog, hooks
from app.modules.platform.deps import Ctx
from app.modules.platform.models import Membership, Role, Tenant, User
from app.modules.tasks import access
from app.modules.tasks.models import OnboardingRun, OnboardingTemplate, Task
from app.modules.tasks.schemas import (
    RunOut,
    TemplateIn,
    TemplateOut,
)

STEP = 1024.0


def _template_out(t: OnboardingTemplate) -> TemplateOut:
    return TemplateOut.model_validate(t)


async def list_templates(ctx: Ctx) -> list[TemplateOut]:
    ctx.require(access.MANAGE)
    rows = await ctx.db.scalars(select(OnboardingTemplate).order_by(func.lower(OnboardingTemplate.name)))
    return [_template_out(t) for t in rows]


async def _template(ctx: Ctx, template_id: uuid.UUID) -> OnboardingTemplate:
    ctx.require(access.MANAGE)
    template = await ctx.db.get(OnboardingTemplate, template_id)
    if template is None:
        raise NotFound()
    return template


async def save_template(ctx: Ctx, body: TemplateIn, template_id: uuid.UUID | None = None) -> TemplateOut:
    ctx.require(access.MANAGE)
    if ctx.scope_department_id is not None:
        raise Forbidden("Owners and admins set up onboarding checklists.", code="workspace_wide")
    items = [i.model_dump(mode="json") for i in body.items]
    if template_id is None:
        template = OnboardingTemplate(
            name=body.name, automatic=body.automatic, items=items, created_by=ctx.user.id
        )
        ctx.db.add(template)
    else:
        template = await _template(ctx, template_id)
        template.name, template.automatic, template.items = body.name, body.automatic, items
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "onboarding.template_saved",
        target_type="onboarding_template",
        target_id=template.id,
        data={"name": template.name, "items": len(items), "automatic": template.automatic},
    )
    await ctx.db.commit()
    return _template_out(template)


async def delete_template(ctx: Ctx, template_id: uuid.UUID) -> None:
    template = await _template(ctx, template_id)
    if ctx.scope_department_id is not None:
        raise Forbidden("Owners and admins set up onboarding checklists.", code="workspace_wide")
    await ctx.db.delete(template)
    await audit.record(
        ctx.db,
        "onboarding.template_deleted",
        target_type="onboarding_template",
        target_id=template_id,
        data={},
    )
    await ctx.db.commit()


async def manager_for(db: AsyncSession, employee: Employee) -> Employee | None:
    """Who runs this person's department: the closest scoped manager above them, else an
    owner or admin. Never the person themselves."""
    rows = (
        await db.execute(
            select(Membership, Role)
            .join(Role, (Role.tenant_id == Membership.tenant_id) & (Role.id == Membership.role_id))
            .where(Membership.status == "active", Membership.id != employee.membership_id)
        )
    ).all()
    chain = await ancestors(db, employee.department_id)
    best: tuple[int, Membership] | None = None
    for membership, role in rows:
        if access.MANAGE not in catalog.resolve(role.key, role.is_builtin, list(role.permissions or [])):
            continue
        if membership.scope_department_id is None:
            rank = len(chain) + (0 if role.key == "owner" else 1)
        elif membership.scope_department_id in chain:
            rank = chain.index(membership.scope_department_id)
        else:
            continue
        if best is None or rank < best[0]:
            best = (rank, membership)
    if best is None:
        return None
    return await db.scalar(select(Employee).where(Employee.membership_id == best[1].id))


async def _start(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    template: OnboardingTemplate,
    employee: Employee,
    start: date,
    started_by: uuid.UUID | None,
) -> OnboardingRun:
    run = OnboardingRun(
        tenant_id=tenant_id,
        employee_id=employee.id,
        template_name=template.name,
        start_date=start,
        started_by=started_by,
    )
    db.add(run)
    await db.flush()
    manager = await manager_for(db, employee)
    top = await db.scalar(select(func.max(Task.position)).where(Task.project_id.is_(None))) or 0
    for i, item in enumerate(template.items or []):
        assignee = employee if item.get("who", "joiner") == "joiner" else manager
        document_id = item.get("document_id")
        task = Task(
            tenant_id=tenant_id,
            title=str(item.get("title", ""))[:200],
            description=str(item.get("notes") or "") or None,
            status="todo",
            priority="normal",
            assignee_id=assignee.id if assignee else None,
            due_date=start + timedelta(days=int(item.get("due_days") or 0)),
            position=top + (i + 1) * STEP,
            created_by=started_by,
            source="onboarding",
            onboarding_run_id=run.id,
            document_id=uuid.UUID(str(document_id)) if document_id else None,
        )
        db.add(task)
        await db.flush()
        if assignee is not None:
            await events.emit(
                db,
                "task.assigned",
                subject_type="task",
                subject_id=task.id,
                actor_user_id=started_by,
                data={
                    "title": task.title,
                    "project_id": None,
                    "project_name": None,
                    "due_date": task.due_date,
                    "assignee_id": assignee.id,
                    "assignee_membership_id": assignee.membership_id,
                    "creator_user_id": started_by,
                    "onboarding_for": employee.full_name,
                },
            )
    await audit.record(
        db,
        "onboarding.started",
        target_type="employee",
        target_id=employee.id,
        data={"template": template.name, "start_date": start, "items": len(template.items or [])},
        actor_user_id=started_by,
    )
    return run


async def start(ctx: Ctx, employee_id: uuid.UUID, template_id: uuid.UUID, start_date: date | None) -> RunOut:
    ctx.require(access.MANAGE)
    template = await ctx.db.get(OnboardingTemplate, template_id)
    employee = await ctx.db.get(Employee, employee_id)
    if template is None or employee is None or not await access.manages_person(ctx, employee):
        raise NotFound()
    if not template.items:
        raise Invalid("This checklist has no items yet.", code="empty_template")
    assert ctx.tenant is not None
    run = await _start(
        ctx.db,
        ctx.tenant.id,
        template,
        employee,
        start_date or employee.joined_on or today(ctx.tenant.timezone),
        ctx.user.id,
    )
    await ctx.db.commit()
    return (await _runs_out(ctx.db, [run], today(ctx.tenant.timezone)))[0]


async def _runs_out(db: AsyncSession, runs: list[OnboardingRun], now: date) -> list[RunOut]:
    if not runs:
        return []
    ids = [r.id for r in runs]
    counts = {
        row[0]: row[1:]
        for row in await db.execute(
            select(
                Task.onboarding_run_id,
                func.count(),
                func.count().filter(Task.status == "done"),
                func.count().filter((Task.status != "done") & (Task.due_date < now)),
            )
            .where(Task.onboarding_run_id.in_(ids))
            .group_by(Task.onboarding_run_id)
        )
    }
    names = dict(
        (
            await db.execute(
                select(Employee.id, Employee.full_name).where(Employee.id.in_({r.employee_id for r in runs}))
            )
        ).all()
    )
    out = []
    for r in runs:
        total, done, overdue = counts.get(r.id, (0, 0, 0))
        out.append(
            RunOut(
                id=r.id,
                employee_id=r.employee_id,
                employee_name=names.get(r.employee_id, ""),
                template_name=r.template_name,
                start_date=r.start_date,
                total=total,
                done=done,
                overdue=overdue,
            )
        )
    return out


async def runs(ctx: Ctx, *, mine: bool = False) -> list[RunOut]:
    """Checklists in progress: your own, or (for managers) everyone's in scope."""
    assert ctx.tenant is not None
    assert ctx.membership is not None
    query = select(OnboardingRun).order_by(OnboardingRun.start_date.desc(), OnboardingRun.created_at.desc())
    if mine or not ctx.can(access.MANAGE):
        me = await ctx.db.scalar(select(Employee).where(Employee.membership_id == ctx.membership.id))
        if me is None:
            return []
        query = query.where(OnboardingRun.employee_id == me.id)
        rows = list(await ctx.db.scalars(query))
    else:
        rows = [
            r
            for r in await ctx.db.scalars(query.limit(200))
            if await access.manages_person(ctx, await ctx.db.get(Employee, r.employee_id))
        ]
    return await _runs_out(ctx.db, rows, today(ctx.tenant.timezone))


# ---- Starting automatically, and ticking off documents ---------------------------------


async def _on_member_joined(db: AsyncSession, membership: Membership, user: User) -> None:
    template = await db.scalar(
        select(OnboardingTemplate)
        .where(OnboardingTemplate.automatic.is_(True))
        .order_by(OnboardingTemplate.created_at)
    )
    if template is None or not template.items:
        return
    employee = await db.scalar(select(Employee).where(Employee.membership_id == membership.id))
    if employee is None:
        return
    already = await db.scalar(
        select(func.count()).select_from(OnboardingRun).where(OnboardingRun.employee_id == employee.id)
    )
    if already:
        return
    tenant = await db.get(Tenant, membership.tenant_id)
    assert tenant is not None
    await _start(db, tenant.id, template, employee, employee.joined_on or today(tenant.timezone), None)


@events.on("document.acknowledged")
async def _tick_documents(db: AsyncSession, event: events.Event) -> None:
    """Reading a document the checklist asked for ticks that item off."""
    document_id = event.data.get("document_id")
    if not document_id or event.actor_user_id is None:
        return
    me = await db.scalar(
        select(Employee)
        .join(Membership, Membership.id == Employee.membership_id)
        .where(Membership.user_id == event.actor_user_id)
    )
    if me is None:
        return
    tasks = await db.scalars(
        select(Task).where(
            Task.document_id == uuid.UUID(str(document_id)), Task.assignee_id == me.id, Task.status != "done"
        )
    )
    for task in tasks:
        task.status = "done"
        task.completed_at = utcnow()


def register_hooks() -> None:
    from app.modules.people.service import register_hooks as people_hooks

    people_hooks()  # people create the profile first
    if _on_member_joined not in hooks.member_joined:
        hooks.member_joined.append(_on_member_joined)
