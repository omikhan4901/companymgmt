"""Early-warning signals: unusual changes a manager may want to look at.

Worked out from the same numbers as the reports, within the viewer's departments, with
plain statistics (a change against the group's own recent past, or an outlier against
colleagues). They describe what changed; they never judge anyone, and signals about
individual people are off unless the workspace chooses them. Each can be dismissed.
"""

from __future__ import annotations

import statistics
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.time import today
from app.modules.people.access import scope_departments
from app.modules.people.models import Department, Employee
from app.modules.platform.ai_models import AISettings
from app.modules.platform.deps import Ctx
from app.modules.reports import access
from app.modules.reports.models import SignalDismissal
from app.modules.reports.service import overview
from app.modules.tasks.models import Project, Task

FEATURE = "signals"
MAX_DEPARTMENTS = 15
DROP = 0.10  # ten percentage points
SNOOZE = timedelta(days=30)


class SignalOut(BaseModel):
    key: str
    kind: Literal["attendance_drop", "project_slipping", "project_due", "heavy_workload"]
    severity: Literal["notice", "warning"]
    subject: str
    link: str | None
    # The numbers behind it, for the sentence the app shows.
    values: dict[str, float | int | str] = Field(default_factory=dict)


class SignalsOut(BaseModel):
    on: bool
    people: bool
    items: list[SignalOut]


class DismissIn(BaseModel):
    key: str = Field(min_length=1, max_length=200)


def _on(ctx: Ctx, module: str) -> bool:
    return ctx.entitlements is not None and module in ctx.entitlements.modules


async def _attendance(ctx: Ctx, now: date) -> list[SignalOut]:
    scope = await scope_departments(ctx)
    query = select(Department.id, Department.name, func.count(Employee.id)).join(
        Employee, Employee.department_id == Department.id
    )
    if scope is not None:
        query = query.where(Department.id.in_(scope))
    rows = (
        await ctx.db.execute(
            query.where(Employee.status == "active")
            .group_by(Department.id, Department.name)
            .order_by(func.count(Employee.id).desc())
            .limit(MAX_DEPARTMENTS)
        )
    ).all()
    out = []
    for department_id, name, _ in rows:
        recent = (
            await overview(ctx, now - timedelta(days=30), now - timedelta(days=1), department_id)
        ).attendance
        before = (
            await overview(ctx, now - timedelta(days=120), now - timedelta(days=31), department_id)
        ).attendance
        if not recent or not before or recent.rate is None or before.rate is None or recent.expected < 20:
            continue
        drop = before.rate - recent.rate
        if drop < DROP:
            continue
        out.append(
            SignalOut(
                key=f"attendance_drop:{department_id}:{now:%Y-%m}",
                kind="attendance_drop",
                severity="warning" if drop >= 2 * DROP else "notice",
                subject=name,
                link=f"/app/reports?department={department_id}",
                values={"now": round(recent.rate * 100), "before": round(before.rate * 100)},
            )
        )
    return out


async def _projects(ctx: Ctx, now: date) -> list[SignalOut]:
    scope = await scope_departments(ctx)
    query = select(Project).where(Project.status == "active")
    if scope is not None:
        query = query.where(Project.department_id.in_(scope))
    projects = list(await ctx.db.scalars(query.limit(200)))
    if not projects:
        return []
    counts = {
        project_id: (int(open_), int(overdue))
        for project_id, open_, overdue in (
            await ctx.db.execute(
                select(
                    Task.project_id,
                    func.count(),
                    func.count().filter(Task.due_date < now),
                )
                .where(Task.project_id.in_([p.id for p in projects]), Task.status != "done")
                .group_by(Task.project_id)
            )
        ).all()
    }
    week = now.isocalendar()
    out = []
    for p in projects:
        open_, overdue = counts.get(p.id, (0, 0))
        link = f"/app/tasks?project={p.id}"
        if overdue >= 3 and overdue / max(open_, 1) >= 0.3:
            out.append(
                SignalOut(
                    key=f"project_slipping:{p.id}:{week.year}-{week.week}",
                    kind="project_slipping",
                    severity="warning" if overdue / max(open_, 1) >= 0.5 else "notice",
                    subject=p.name,
                    link=link,
                    values={"overdue": overdue, "open": open_},
                )
            )
        elif p.due_date and open_ and p.due_date <= now + timedelta(days=7):
            out.append(
                SignalOut(
                    key=f"project_due:{p.id}:{p.due_date}",
                    kind="project_due",
                    severity="warning" if p.due_date < now else "notice",
                    subject=p.name,
                    link=link,
                    values={"open": open_, "due": p.due_date.isoformat()},
                )
            )
    return out


async def _workload(ctx: Ctx, now: date) -> list[SignalOut]:
    scope = await scope_departments(ctx)
    query = (
        select(Employee.id, Employee.full_name, func.count(Task.id))
        .join(Task, Task.assignee_id == Employee.id)
        .where(Task.status != "done", Employee.status == "active")
        .group_by(Employee.id, Employee.full_name)
    )
    if scope is not None:
        query = query.where(Employee.department_id.in_(scope))
    rows = (await ctx.db.execute(query)).all()
    if len(rows) < 3:
        return []
    loads = [int(n) for _, _, n in rows]
    limit = max(8.0, statistics.mean(loads) + 2 * statistics.pstdev(loads))
    week = now.isocalendar()
    return [
        SignalOut(
            key=f"heavy_workload:{employee_id}:{week.year}-{week.week}",
            kind="heavy_workload",
            severity="notice",
            subject=name,
            link=f"/app/people?person={employee_id}",
            values={"open": int(n), "typical": round(statistics.median(loads))},
        )
        for employee_id, name, n in rows
        if n > limit
    ]


async def signals(ctx: Ctx) -> SignalsOut:
    ctx.require(access.VIEW)
    assert ctx.tenant is not None
    assert ctx.membership is not None
    row = await ctx.db.scalar(select(AISettings))
    if row is None or FEATURE not in (row.features or []):
        return SignalsOut(on=False, people=False, items=[])
    now = today(ctx.tenant.timezone)
    items: list[SignalOut] = []
    if _on(ctx, "attendance"):
        items += await _attendance(ctx, now)
    if _on(ctx, "tasks"):
        items += await _projects(ctx, now)
        if row.signal_people:
            items += await _workload(ctx, now)
    hidden = set(
        await ctx.db.scalars(
            select(SignalDismissal.key).where(
                SignalDismissal.membership_id == ctx.membership.id, SignalDismissal.until >= now
            )
        )
    )
    shown = [s for s in items if s.key not in hidden]
    shown.sort(key=lambda s: (s.severity != "warning", s.kind, s.subject))
    return SignalsOut(on=True, people=bool(row.signal_people), items=shown)


async def dismiss(ctx: Ctx, body: DismissIn) -> None:
    ctx.require(access.VIEW)
    assert ctx.tenant is not None
    assert ctx.membership is not None
    until = today(ctx.tenant.timezone) + SNOOZE
    found = await ctx.db.scalar(
        select(SignalDismissal).where(
            SignalDismissal.membership_id == ctx.membership.id, SignalDismissal.key == body.key
        )
    )
    if found:
        found.until = until
    else:
        ctx.db.add(SignalDismissal(membership_id=ctx.membership.id, key=body.key, until=until))
    await ctx.db.commit()
