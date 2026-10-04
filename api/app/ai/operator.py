"""Platform operators: the people who run CompanyMgmt itself (not a workspace's admins).

They're listed in PLATFORM_OPERATORS and must use two-step sign-in. For now they set
how many questions a month each plan's workspaces may ask the assistant. Every change is
logged and tells the owners and admins of each affected workspace.
"""

from __future__ import annotations

import logging
import uuid

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core import events
from app.core.config import get_settings
from app.core.db import open_session
from app.core.errors import Forbidden, Invalid
from app.core.time import utcnow
from app.modules.platform.ai_models import AIAllowance
from app.modules.platform.deps import Ctx, load_entitlements
from app.modules.platform.models import Plan, Tenant

log = logging.getLogger(__name__)


class AllowanceOut(BaseModel):
    plan_key: str
    plan_name: str
    # None: no limit. 0: no AI on this plan.
    questions_per_month: int | None


class AllowanceIn(BaseModel):
    plan_key: str = Field(max_length=40)
    questions_per_month: int | None = Field(default=None, ge=0, le=1_000_000)


class AllowancesIn(BaseModel):
    allowances: list[AllowanceIn] = Field(min_length=1, max_length=20)


def is_operator(ctx: Ctx) -> bool:
    email = (ctx.user.email or "").lower()
    return bool(email) and email in get_settings().platform_operators


def require_operator(ctx: Ctx) -> None:
    if not is_operator(ctx):
        raise Forbidden()
    if ctx.user.totp_enabled_at is None:
        raise Forbidden("Turn on two-step sign-in to use operator tools.", code="mfa_required")


async def allowances(ctx: Ctx) -> list[AllowanceOut]:
    require_operator(ctx)
    plans = {p.key: p for p in await ctx.db.scalars(select(Plan))}
    rows = {a.plan_key: a for a in await ctx.db.scalars(select(AIAllowance))}
    return [
        AllowanceOut(
            plan_key=key,
            plan_name=plan.name,
            questions_per_month=rows[key].questions_per_month if key in rows else 0,
        )
        for key, plan in sorted(plans.items(), key=lambda kv: kv[1].sort)
    ]


async def save_allowances(ctx: Ctx, body: AllowancesIn) -> list[AllowanceOut]:
    require_operator(ctx)
    plans = {p.key: p for p in await ctx.db.scalars(select(Plan))}
    changed: dict[str, int | None] = {}
    for item in body.allowances:
        if item.plan_key not in plans:
            raise Invalid(errors=[{"field": "plan_key", "message": f"No plan called {item.plan_key}."}])
        row = await ctx.db.get(AIAllowance, item.plan_key)
        if row is None:
            row = AIAllowance(plan_key=item.plan_key)
            ctx.db.add(row)
        elif row.questions_per_month == item.questions_per_month:
            continue
        row.questions_per_month = item.questions_per_month
        row.updated_at = utcnow()
        row.updated_by = ctx.user.id
        changed[item.plan_key] = item.questions_per_month
    await ctx.db.commit()
    if changed:
        log.info("ai allowances changed", extra={"by": str(ctx.user.id), "changes": changed})
        await announce(changed, {k: plans[k].name for k in changed})
    return await allowances(ctx)


async def announce(changed: dict[str, int | None], names: dict[str, str]) -> int:
    """Tell each workspace on a changed plan. Returns how many workspaces were told."""
    async with open_session() as db:
        tenant_ids: list[uuid.UUID] = list(
            await db.scalars(select(Tenant.id).where(Tenant.status == "active"))
        )
    told = 0
    for tenant_id in tenant_ids:
        async with open_session(tenant_id) as db:
            plan = (await load_entitlements(db, tenant_id)).plan.key
            if plan not in changed:
                continue
            await events.emit(
                db,
                "ai.allowance_changed",
                subject_type="workspace",
                subject_id=tenant_id,
                data={"plan": names[plan], "questions": changed[plan]},
            )
            await db.commit()
            told += 1
    return told
