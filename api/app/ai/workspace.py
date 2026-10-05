"""A workspace's AI switch, terms, features and monthly allowance.

AI runs only when all of these hold: the server has a model (a Gemini key), the
workspace's owner switched it on and accepted the AI terms, an admin ticked the feature,
the person may use the assistant, and the month's questions aren't used up.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.ai import provider
from app.ai.features import FEATURES
from app.ai.provider import AIUnavailable, Reply
from app.core import audit
from app.core.errors import Forbidden, Invalid, PaymentRequired, TooManyRequests, Unavailable
from app.core.security import crypto
from app.core.time import today, utcnow
from app.modules.platform.ai_models import AIAllowance, AISettings, AIUsage
from app.modules.platform.catalog import AI_MANAGE, AI_USE
from app.modules.platform.deps import Ctx

COUNTED = ("ask", "brief", "write", "summary", "automation")


class AIStatusOut(BaseModel):
    # The server has a model configured.
    available: bool
    enabled: bool
    terms_accepted: bool
    can_use: bool
    can_manage: bool
    features: list[str]
    # Questions a month on this plan (None: no limit), and used so far this month.
    allowance: int | None
    used: int
    resets_on: date
    signal_people: bool = False
    # The workspace runs on its own Gemini key (no monthly allowance from us).
    own_key: bool = False
    own_key_hint: str | None = None


class AISettingsIn(BaseModel):
    enabled: bool
    accept_terms: bool = False
    features: list[str] = Field(default_factory=list, max_length=50)
    # None leaves it as it is.
    signal_people: bool | None = None


async def settings(ctx: Ctx) -> AISettings:
    row = await ctx.db.scalar(select(AISettings))
    return row or AISettings(enabled=False, features=[], signal_people=False)


async def allowance(ctx: Ctx) -> int | None:
    assert ctx.entitlements is not None
    row = await ctx.db.get(AIAllowance, ctx.entitlements.plan.key)
    return 0 if row is None else row.questions_per_month


def _month(ctx: Ctx) -> tuple[datetime, date]:
    assert ctx.tenant is not None
    now = today(ctx.tenant.timezone)
    first = now.replace(day=1)
    resets = (first + timedelta(days=32)).replace(day=1)
    start = datetime.combine(first, time(0), ZoneInfo(ctx.tenant.timezone))
    return start, resets


async def used(ctx: Ctx) -> int:
    start, _ = _month(ctx)
    count = await ctx.db.scalar(
        select(func.count())
        .select_from(AIUsage)
        .where(AIUsage.kind.in_(COUNTED), AIUsage.created_at >= start)
    )
    return int(count or 0)


async def status(ctx: Ctx) -> AIStatusOut:
    row = await settings(ctx)
    _, resets = _month(ctx)
    return AIStatusOut(
        available=provider.available() or bool(row.own_key_enc),
        enabled=row.enabled,
        terms_accepted=row.terms_accepted_at is not None,
        can_use=ctx.can(AI_USE),
        can_manage=ctx.can(AI_MANAGE),
        features=[f for f in row.features or [] if f in FEATURES],
        allowance=await allowance(ctx),
        used=await used(ctx),
        resets_on=resets,
        signal_people=bool(row.signal_people),
        own_key=bool(row.own_key_enc),
        own_key_hint=row.own_key_hint if row.own_key_enc else None,
    )


def _key_context(ctx: Ctx) -> str:
    return f"ai-key:{ctx.tenant_id}"


async def set_own_key(ctx: Ctx, key: str | None) -> AIStatusOut:
    """Owner only, on plans with company sign-in. None removes it."""
    if not ctx.is_owner:
        raise Forbidden("Only the workspace owner can change this.", code="owner_only")
    assert ctx.entitlements is not None
    if key is not None and not ctx.entitlements.feature("sso"):
        raise PaymentRequired(
            "Using your own AI key isn't included in this plan.", code="feature_not_in_plan"
        )
    row = await ctx.db.scalar(select(AISettings).with_for_update())
    if row is None:
        row = AISettings(tenant_id=ctx.tenant_id, enabled=False, features=[], signal_people=False)
        ctx.db.add(row)
    row.own_key_enc = crypto.encrypt(key, context=_key_context(ctx)) if key else None
    row.own_key_hint = key[-4:] if key else None
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "ai.own_key_set" if key else "ai.own_key_removed",
        target_type="workspace",
        target_id=ctx.tenant_id,
        data={"hint": row.own_key_hint},
    )
    await ctx.db.commit()
    return await status(ctx)


async def save(ctx: Ctx, body: AISettingsIn) -> AIStatusOut:
    ctx.require(AI_MANAGE)
    unknown = [f for f in body.features if f not in FEATURES]
    if unknown:
        raise Invalid(errors=[{"field": "features", "message": f"Unknown feature: {unknown[0]}"}])
    row = await ctx.db.scalar(select(AISettings).with_for_update())
    if row is None:
        row = AISettings(tenant_id=ctx.tenant_id, enabled=False, features=[], signal_people=False)
        ctx.db.add(row)
    if body.accept_terms and row.terms_accepted_at is None:
        if not ctx.is_owner:
            raise Forbidden("Only the workspace owner can accept the AI terms.", code="owner_only")
        row.terms_accepted_at = utcnow()
        row.terms_accepted_by = ctx.user.id
    if body.enabled and row.terms_accepted_at is None:
        raise Invalid("The owner needs to accept the AI terms first.", code="ai_terms_needed")
    before = {"enabled": row.enabled, "features": list(row.features or [])}
    row.enabled = body.enabled
    row.features = sorted(set(body.features))
    if body.signal_people is not None:
        row.signal_people = body.signal_people
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "ai.settings_changed",
        target_type="workspace",
        target_id=ctx.tenant_id,
        data={
            "before": before,
            "after": {"enabled": row.enabled, "features": row.features, "signal_people": row.signal_people},
        },
    )
    await ctx.db.commit()
    return await status(ctx)


async def require(ctx: Ctx, feature: str) -> provider.Model:
    """The model to use for `feature`, or the reason it can't be used, in plain words."""
    ctx.require(AI_USE)
    row = await settings(ctx)
    if row.own_key_enc:
        model = provider.with_key(crypto.decrypt(row.own_key_enc, context=_key_context(ctx)))
    else:
        try:
            model = provider.get_model()
        except AIUnavailable as exc:
            raise Unavailable(exc.message, code="ai_unavailable") from exc
    if not row.enabled or row.terms_accepted_at is None:
        raise Forbidden("The assistant is switched off in this workspace.", code="ai_off")
    if feature not in (row.features or []):
        raise Forbidden("This workspace hasn't switched on this kind of help.", code="ai_feature_off")
    if row.own_key_enc:
        return model
    limit = await allowance(ctx)
    if limit == 0:
        raise PaymentRequired("Your plan doesn't include the assistant.", code="ai_not_in_plan")
    if limit is not None and await used(ctx) >= limit:
        raise TooManyRequests(
            "This month's questions are used up. They reset on the 1st.", code="ai_allowance_used"
        )
    return model


async def record(ctx: Ctx, kind: str, model: str, replies: list[Reply]) -> None:
    assert ctx.membership is not None
    ctx.db.add(
        AIUsage(
            membership_id=ctx.membership.id,
            kind=kind,
            model=model,
            tokens_in=sum(r.tokens_in for r in replies),
            tokens_out=sum(r.tokens_out for r in replies),
        )
    )
