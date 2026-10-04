"""Building, changing and inspecting automations."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core import audit
from app.core.errors import Invalid, NotFound
from app.modules.automations import engine
from app.modules.automations.models import Automation, AutomationRun
from app.modules.automations.schemas import (
    EVENTS,
    AutomationIn,
    AutomationOut,
    AutomationPatch,
    AutomationRunOut,
    EventInfo,
    Recipients,
)
from app.modules.people.models import Department
from app.modules.platform.deps import Ctx
from app.modules.platform.models import Membership, Role, User

MAX_PER_WORKSPACE = 50


async def _out(ctx: Ctx, rows: list[Automation]) -> list[AutomationOut]:
    owners = {r.owner_membership_id for r in rows}
    names = (
        dict(
            (
                await ctx.db.execute(
                    select(Membership.id, User.name)
                    .join(User, User.id == Membership.user_id)
                    .where(Membership.id.in_(owners))
                )
            ).all()
        )
        if owners
        else {}
    )
    return [
        AutomationOut(
            id=r.id,
            name=r.name,
            enabled=r.enabled,
            trigger=engine.TRIGGER.validate_python(r.trigger),
            conditions=engine.CONDITIONS.validate_python(r.conditions or []),
            actions=engine.ACTIONS.validate_python(r.actions or []),
            owner_membership_id=r.owner_membership_id,
            owner_name=names.get(r.owner_membership_id),
            drafted_by_ai=r.drafted_by_ai,
            next_run_at=r.next_run_at,
            last_run_at=r.last_run_at,
            paused_reason=r.paused_reason,
            version=r.version,
        )
        for r in rows
    ]


async def _automation(ctx: Ctx, automation_id: uuid.UUID, *, lock: bool = False) -> Automation:
    query = select(Automation).where(Automation.id == automation_id)
    if lock:
        query = query.with_for_update()
    found = await ctx.db.scalar(query)
    if found is None:
        raise NotFound()
    return found


async def _check_people(ctx: Ctx, body: AutomationIn) -> None:
    """Everything an automation names must exist in this workspace."""
    specs: list[Recipients] = []
    for action in body.actions:
        spec = getattr(action, "to", None) or getattr(action, "assign_to", None)
        if spec is not None:
            specs.append(spec)
    for spec in specs:
        problem = None
        if spec.kind == "role" and await ctx.db.scalar(select(Role.id).where(Role.key == spec.role)) is None:
            problem = f"There's no role called {spec.role}."
        if spec.kind == "department" and await ctx.db.get(Department, spec.department_id) is None:
            problem = "That department doesn't exist."
        if spec.kind == "people":
            found = set(
                await ctx.db.scalars(select(Membership.id).where(Membership.id.in_(spec.membership_ids)))
            )
            if found != set(spec.membership_ids):
                problem = "Someone chosen isn't in this workspace."
        if problem:
            raise Invalid(errors=[{"field": "actions", "message": problem}])


async def list_automations(ctx: Ctx) -> list[AutomationOut]:
    rows = list(await ctx.db.scalars(select(Automation).order_by(Automation.created_at)))
    return await _out(ctx, rows)


async def get(ctx: Ctx, automation_id: uuid.UUID) -> AutomationOut:
    return (await _out(ctx, [await _automation(ctx, automation_id)]))[0]


async def create(ctx: Ctx, body: AutomationIn) -> AutomationOut:
    assert ctx.membership is not None
    assert ctx.tenant is not None
    count = len(list(await ctx.db.scalars(select(Automation.id))))
    if count >= MAX_PER_WORKSPACE:
        raise Invalid(f"A workspace can have up to {MAX_PER_WORKSPACE} automations.", code="too_many")
    await _check_people(ctx, body)
    row = Automation(
        name=body.name,
        enabled=body.enabled,
        trigger=body.trigger.model_dump(mode="json"),
        conditions=[c.model_dump(mode="json") for c in body.conditions],
        actions=[a.model_dump(mode="json") for a in body.actions],
        owner_membership_id=ctx.membership.id,
        created_by=ctx.user.id,
        drafted_by_ai=body.drafted_by_ai,
    )
    ctx.db.add(row)
    await engine.schedule(ctx.db, ctx.tenant, row)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "automation.created",
        target_type="automation",
        target_id=row.id,
        data={"name": row.name, "enabled": row.enabled, "drafted_by_ai": body.drafted_by_ai},
    )
    await ctx.db.commit()
    return await get(ctx, row.id)


async def replace(ctx: Ctx, automation_id: uuid.UUID, body: AutomationIn) -> AutomationOut:
    """Save the editor: the person saving becomes its owner (it runs as them)."""
    assert ctx.membership is not None
    assert ctx.tenant is not None
    row = await _automation(ctx, automation_id, lock=True)
    await _check_people(ctx, body)
    row.name = body.name
    row.enabled = body.enabled
    row.trigger = body.trigger.model_dump(mode="json")
    row.conditions = [c.model_dump(mode="json") for c in body.conditions]
    row.actions = [a.model_dump(mode="json") for a in body.actions]
    row.owner_membership_id = ctx.membership.id
    row.paused_reason = None
    await engine.schedule(ctx.db, ctx.tenant, row)
    await audit.record(
        ctx.db, "automation.changed", target_type="automation", target_id=row.id, data={"name": row.name}
    )
    await ctx.db.commit()
    return await get(ctx, row.id)


async def update(ctx: Ctx, automation_id: uuid.UUID, body: AutomationPatch) -> AutomationOut:
    """Rename, or switch on and off (switching on makes you its owner)."""
    assert ctx.membership is not None
    assert ctx.tenant is not None
    row = await _automation(ctx, automation_id, lock=True)
    if body.name is not None:
        row.name = body.name
    if body.enabled is not None and body.enabled != row.enabled:
        row.enabled = body.enabled
        if body.enabled:
            row.owner_membership_id = ctx.membership.id
            row.paused_reason = None
        await audit.record(
            ctx.db,
            "automation.switched_on" if body.enabled else "automation.paused",
            target_type="automation",
            target_id=row.id,
            data={"name": row.name},
        )
    await engine.schedule(ctx.db, ctx.tenant, row)
    await ctx.db.commit()
    return await get(ctx, row.id)


async def delete(ctx: Ctx, automation_id: uuid.UUID) -> None:
    row = await _automation(ctx, automation_id, lock=True)
    await audit.record(
        ctx.db, "automation.deleted", target_type="automation", target_id=row.id, data={"name": row.name}
    )
    await ctx.db.delete(row)
    await ctx.db.commit()


async def run_now(ctx: Ctx, automation_id: uuid.UUID) -> AutomationRunOut:
    """Try it once, now (scheduled automations only; events can't be faked)."""
    assert ctx.tenant is not None
    row = await _automation(ctx, automation_id, lock=True)
    if row.trigger.get("type") != "schedule":
        raise Invalid("Automations that start from an event run when the event happens.", code="event_only")
    record = await engine.run(ctx.db, ctx.tenant, row, "manual")
    return _run_out(record)


def _run_out(r: AutomationRun) -> AutomationRunOut:
    return AutomationRunOut(
        id=r.id, created_at=r.created_at, status=r.status, cause=r.cause, detail=r.detail or [], error=r.error
    )


async def runs(ctx: Ctx, automation_id: uuid.UUID) -> list[AutomationRunOut]:
    await _automation(ctx, automation_id)
    rows = await ctx.db.scalars(
        select(AutomationRun)
        .where(AutomationRun.automation_id == automation_id)
        .order_by(AutomationRun.created_at.desc())
        .limit(50)
    )
    return [_run_out(r) for r in rows]


def event_catalog() -> list[EventInfo]:
    return [EventInfo(name=name, about_a_person=key is not None) for name, key in EVENTS.items()]
