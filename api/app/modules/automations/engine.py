"""Runs automations: on a schedule (the tick job, every 15 minutes) or after an event.

Each run happens as the automation's owner (`member_ctx`), so it can only do what they
could do in the app at that moment; tasks are created through the same capability as the
API. Runs are limited (an automation that runs too often pauses itself), each is
recorded, and events caused by a run are marked so they never start other automations.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import TypeAdapter
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import context, events
from app.core.db import open_session
from app.core.errors import AppError
from app.core.time import local_date, utcnow
from app.modules.attendance.models import AttendanceRecord
from app.modules.automations.access import MANAGE
from app.modules.automations.models import Automation, AutomationRun
from app.modules.automations.schemas import (
    EVENTS,
    PLACEHOLDER,
    Action,
    Condition,
    NotifyAction,
    Recipients,
    ScheduleTrigger,
    TaskAction,
    Trigger,
)
from app.modules.leave.models import LeavePolicy, LeaveRequest
from app.modules.notifications.service import notify
from app.modules.people.access import subtree
from app.modules.people.models import Employee
from app.modules.platform.capabilities import invoke
from app.modules.platform.deps import Ctx, member_ctx
from app.modules.platform.hooks import member_joined
from app.modules.platform.models import Membership, Role, Tenant, User
from app.modules.tasks import capabilities as _task_capabilities  # noqa: F401  (registers tasks.create)
from app.modules.tasks.models import Task

log = logging.getLogger(__name__)

PER_HOUR = 30
PER_DAY = 300
MAX_PEOPLE = 500
MAX_TASKS = 50
TRIGGER: TypeAdapter[Trigger] = TypeAdapter(Trigger)
ACTIONS: TypeAdapter[list[Action]] = TypeAdapter(list[Action])
CONDITIONS: TypeAdapter[list[Condition]] = TypeAdapter(list[Condition])


# --- when ------------------------------------------------------------------------------


def next_run(trigger: ScheduleTrigger, timezone: str, after: datetime, days_off: list[int]) -> datetime:
    """The first moment after `after` that the schedule fires, in UTC."""
    zone = ZoneInfo(timezone)
    hour, minute = (int(x) for x in trigger.time.split(":"))
    day = after.astimezone(zone).date()
    for _ in range(400):
        due = datetime.combine(day, time(hour, minute), zone)
        if due > after and _fires_on(trigger, day, days_off):
            return due.astimezone(ZoneInfo("UTC"))
        day += timedelta(days=1)
    raise ValueError("No run date within a year.")  # unreachable for valid triggers


def _fires_on(trigger: ScheduleTrigger, day: date, days_off: list[int]) -> bool:
    if trigger.every == "day":
        return True
    if trigger.every == "workdays":
        return day.isoweekday() not in days_off
    if trigger.every == "week":
        return day.isoweekday() == trigger.weekday
    return day.day == trigger.day


async def days_off(db: AsyncSession) -> list[int]:
    policy = await db.scalar(select(LeavePolicy))
    return list(policy.weekly_off) if policy else []


async def schedule(db: AsyncSession, tenant: Tenant, automation: Automation) -> None:
    """Work out `next_run_at` (none for event automations or when switched off)."""
    trigger = TRIGGER.validate_python(automation.trigger)
    if not automation.enabled or not isinstance(trigger, ScheduleTrigger):
        automation.next_run_at = None
        return
    automation.next_run_at = next_run(trigger, tenant.timezone, utcnow(), await days_off(db))


# --- whether ---------------------------------------------------------------------------


def matches(conditions: list[Condition], data: dict[str, Any]) -> bool:
    for c in conditions:
        value = data.get(c.field)
        if c.op == "contains":
            if c.value is None or str(c.value).lower() not in str(value or "").lower():
                return False
            continue
        if c.op in ("eq", "ne"):
            same = str(value).lower() == str(c.value).lower()
            if same != (c.op == "eq"):
                return False
            continue
        try:
            left, right = float(str(value)), float(c.value)
        except (TypeError, ValueError):
            return False
        if (c.op == "gte" and left < right) or (c.op == "lte" and left > right):
            return False
    return True


# --- who -------------------------------------------------------------------------------


@dataclass
class Person:
    membership_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    count: int = 0


async def _people(db: AsyncSession, membership_ids: list[uuid.UUID] | None = None) -> list[Person]:
    query = (
        select(Membership.id, Membership.user_id, User.name)
        .join(User, User.id == Membership.user_id)
        .where(Membership.status == "active")
    )
    if membership_ids is not None:
        if not membership_ids:
            return []
        query = query.where(Membership.id.in_(membership_ids))
    return [Person(m, u, n) for m, u, n in (await db.execute(query.order_by(User.name))).all()]


async def recipients(ctx: Ctx, spec: Recipients, event: events.Event | None, today: date) -> list[Person]:
    db = ctx.db
    if spec.kind == "everyone":
        found = await _people(db)
    elif spec.kind == "role":
        ids = await db.scalars(
            select(Membership.id)
            .join(Role, and_(Role.tenant_id == Membership.tenant_id, Role.id == Membership.role_id))
            .where(Role.key == spec.role)
        )
        found = await _people(db, list(ids))
    elif spec.kind == "department":
        assert spec.department_id is not None
        departments = await subtree(db, spec.department_id)
        ids = await db.scalars(
            select(Employee.membership_id).where(
                Employee.department_id.in_(departments), Employee.membership_id.is_not(None)
            )
        )
        found = await _people(db, [i for i in ids if i])
    elif spec.kind == "people":
        found = await _people(db, spec.membership_ids)
    elif spec.kind == "subject":
        key = EVENTS.get(event.name) if event else None
        raw = event.data.get(key) if event and key else None
        found = await _people(db, [uuid.UUID(str(raw))]) if raw else []
    elif spec.kind == "overdue_tasks":
        rows = (
            await db.execute(
                select(Employee.membership_id, func.count())
                .join(Task, Task.assignee_id == Employee.id)
                .where(Task.status != "done", Task.due_date < today, Employee.membership_id.is_not(None))
                .group_by(Employee.membership_id)
            )
        ).all()
        counts = {m: n for m, n in rows if m}
        found = await _people(db, list(counts))
        for p in found:
            p.count = counts[p.membership_id]
    else:  # not_clocked_in
        if ctx.entitlements is None or "attendance" not in ctx.entitlements.modules:
            return []
        start = datetime.combine(today, time(0), ZoneInfo(ctx.tenant.timezone if ctx.tenant else "UTC"))
        came = select(AttendanceRecord.employee_id).where(
            AttendanceRecord.clock_in_at >= start, AttendanceRecord.clock_in_at < start + timedelta(days=1)
        )
        away = select(LeaveRequest.employee_id).where(
            LeaveRequest.status == "approved",
            LeaveRequest.start_date <= today,
            LeaveRequest.end_date >= today,
        )
        ids = await db.scalars(
            select(Employee.membership_id).where(
                Employee.status == "active",
                Employee.membership_id.is_not(None),
                Employee.id.not_in(came),
                Employee.id.not_in(away),
            )
        )
        found = await _people(db, [i for i in ids if i])
    return found[:MAX_PEOPLE]


# --- what ------------------------------------------------------------------------------


def render(template: str, person: Person | None, event: events.Event | None) -> str:
    def value(match: re.Match[str]) -> str:
        key = match.group(1)
        if key == "name" and person:
            return person.name
        if key == "count" and person:
            return str(person.count)
        if key.startswith("event.") and event:
            found = event.data.get(key.removeprefix("event."))
            return "" if found is None else str(found)
        return match.group(0)

    return PLACEHOLDER.sub(value, template)


async def _notify(
    ctx: Ctx, automation: Automation, action: NotifyAction, event: events.Event | None, today: date
) -> dict[str, Any]:
    people = await recipients(ctx, action.to, event, today)
    if not people:
        return {"action": "notify", "count": 0}
    message = await events.emit(
        ctx.db,
        "automation.message",
        subject_type="automation",
        subject_id=automation.id,
        data={"name": automation.name},
    )
    # Not "from" anyone: the owner gets their own automation's messages too.
    message.actor_user_id = None
    sent = 0
    for person in people:
        text = render(action.message, person, event)[:500]
        sent += await notify(
            ctx.db, message, [person.user_id], link=None, data={"title": text, "automation": automation.name}
        )
    return {"action": "notify", "count": sent}


async def _tasks(
    ctx: Ctx, automation: Automation, action: TaskAction, event: events.Event | None, today: date
) -> dict[str, Any]:
    assert ctx.membership is not None
    if action.assign_to is None:
        members = [ctx.membership.id]
    else:
        members = [p.membership_id for p in await recipients(ctx, action.assign_to, event, today)]
    employees = {
        m: e
        for e, m in (
            await ctx.db.execute(
                select(Employee.id, Employee.membership_id).where(Employee.membership_id.in_(members))
            )
        ).all()
    }
    created = []
    for membership_id in members[:MAX_TASKS]:
        employee_id = employees.get(membership_id)
        if employee_id is None:
            continue
        person = Person(membership_id, uuid.uuid4(), "")
        body: dict[str, Any] = {
            "title": render(action.title, person, event)[:200],
            "description": render(action.description, person, event) if action.description else None,
        }
        if membership_id != ctx.membership.id:
            body["assignee_id"] = str(employee_id)
        if action.due_in_days is not None:
            body["due_date"] = str(today + timedelta(days=action.due_in_days))
        task = await invoke(ctx, "tasks.create", body, allow_writes=True)
        created.append(task["id"])
    return {"action": "create_task", "count": len(created), "task_ids": created}


# --- running ---------------------------------------------------------------------------


async def _pause(automation: Automation, reason: str) -> None:
    automation.enabled = False
    automation.next_run_at = None
    automation.paused_reason = reason


async def _too_often(db: AsyncSession, automation: Automation) -> bool:
    now = utcnow()
    recent = (
        await db.execute(
            select(
                func.count().filter(AutomationRun.created_at >= now - timedelta(hours=1)),
                func.count(),
            ).where(
                AutomationRun.automation_id == automation.id,
                AutomationRun.created_at >= now - timedelta(days=1),
                AutomationRun.status != "limited",
            )
        )
    ).one()
    return int(recent[0]) >= PER_HOUR or int(recent[1]) >= PER_DAY


async def run(
    db: AsyncSession, tenant: Tenant, automation: Automation, cause: str, event: events.Event | None = None
) -> AutomationRun:
    """Run one automation now and record it. Commits."""
    record = AutomationRun(automation_id=automation.id, cause=cause, event_id=event.id if event else None)
    owner = await db.get(Membership, automation.owner_membership_id)
    if owner is None or owner.status != "active":
        await _pause(automation, "Its owner is no longer in the workspace.")
        record.status, record.error = "skipped", automation.paused_reason
    elif await _too_often(db, automation):
        await _pause(automation, "It ran too many times in a short while, so it was paused.")
        record.status, record.error = "limited", automation.paused_reason
    else:
        ctx = await member_ctx(db, tenant, owner)
        if not ctx.can(MANAGE):
            await _pause(automation, "Its owner can no longer manage automations.")
            record.status, record.error = "skipped", automation.paused_reason
        else:
            await _execute(ctx, tenant, automation, record, event)
    automation.last_run_at = utcnow()
    db.add(record)
    await db.commit()
    return record


async def _execute(
    ctx: Ctx, tenant: Tenant, automation: Automation, record: AutomationRun, event: events.Event | None
) -> None:
    assert ctx.membership is not None
    today = local_date(utcnow(), tenant.timezone)
    previous = context.current()
    context.bind(
        context.RequestInfo(
            request_id=f"automation-{automation.id}",
            user_id=ctx.user.id,
            tenant_id=tenant.id,
            membership_id=ctx.membership.id,
            extra={"via": "automation"},
        )
    )
    token = events.origin.set(f"automation:{automation.id}")
    detail: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        for action in ACTIONS.validate_python(automation.actions):
            try:
                if isinstance(action, NotifyAction):
                    detail.append(await _notify(ctx, automation, action, event, today))
                else:
                    detail.append(await _tasks(ctx, automation, action, event, today))
            except AppError as exc:
                errors.append(exc.detail)
                detail.append({"action": action.type, "error": exc.detail})
    finally:
        events.origin.reset(token)
        context.bind(previous)
    record.detail = detail
    record.status = "failed" if errors else "ok"
    record.error = "; ".join(errors)[:2000] if errors else None


# --- triggers --------------------------------------------------------------------------


async def on_event(db: AsyncSession, event: events.Event) -> None:
    """After any catalogued event: run the automations that start from it."""
    if str(event.data.get("origin") or "").startswith("automation:"):
        return
    tenant = await db.get(Tenant, event.tenant_id)
    if tenant is None or tenant.status != "active":
        return
    found = list(
        await db.scalars(
            select(Automation).where(
                Automation.enabled.is_(True), Automation.trigger["event"].astext == event.name
            )
        )
    )
    for automation in found:
        if not matches(CONDITIONS.validate_python(automation.conditions or []), event.data):
            continue
        try:
            await run(db, tenant, automation, event.name, event)
        except Exception:  # one broken automation mustn't stop the others
            log.exception("automation failed", extra={"automation": str(automation.id)})
            await db.rollback()


for _name in EVENTS:
    events.on(_name, later=True)(on_event)


async def _joined(db: AsyncSession, membership: Membership, user: User) -> None:
    """Someone joined: an event automations can start from ("welcome new joiners")."""
    await events.emit(
        db,
        "member.joined",
        subject_type="member",
        subject_id=membership.id,
        data={"membership_id": membership.id, "name": user.name},
    )


member_joined.append(_joined)


async def tick(now: datetime | None = None) -> int:
    """Run every scheduled automation that is due, in every workspace. Returns runs."""
    now = now or utcnow()
    async with open_session() as db:
        tenant_ids = list(await db.scalars(select(Tenant.id).where(Tenant.status == "active")))
    ran = 0
    for tenant_id in tenant_ids:
        async with open_session(tenant_id) as db:
            tenant = await db.get(Tenant, tenant_id)
            assert tenant is not None
            due = list(
                await db.scalars(
                    select(Automation)
                    .where(Automation.enabled.is_(True), Automation.next_run_at <= now)
                    .order_by(Automation.next_run_at)
                    .limit(100)
                )
            )
            for automation in due:
                try:
                    await run(db, tenant, automation, "schedule")
                except Exception:
                    log.exception("automation failed", extra={"automation": str(automation.id)})
                    await db.rollback()
                    automation = await db.get(Automation, automation.id) or automation
                await schedule(db, tenant, automation)
                await db.commit()
                ran += 1
    return ran
