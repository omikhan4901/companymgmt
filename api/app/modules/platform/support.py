"""Contact support from any screen, and product analytics for operators without any
personal data (event counts only)."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select, text

from app.core import context, outbox, ratelimit
from app.core.config import get_settings
from app.core.email import Mail, as_payload
from app.core.schema import In
from app.core.time import utcnow
from app.modules.platform.deps import Ctx, signed_in
from app.modules.platform.models import Tenant

router = APIRouter(prefix="/v1", tags=["support"])
log = logging.getLogger(__name__)

SUPPORT_RULE = ratelimit.Rule("support", 10, 3600)


class SupportIn(In):
    topic: Literal["question", "problem", "idea"]
    message: Annotated[str, StringConstraints(min_length=5, max_length=4000, strip_whitespace=True)]
    # The page they were on (a path in the app).
    page: Annotated[str | None, StringConstraints(max_length=300)] = None


class SupportOut(BaseModel):
    reference: str


@router.post("/support", response_model=SupportOut, status_code=202)
async def contact_support(body: SupportIn, ctx: Ctx = Depends(signed_in())) -> SupportOut:
    """Send a question, problem or idea to the team. The reply goes to your email."""
    await ratelimit.enforce(SUPPORT_RULE, str(ctx.user.id))
    settings = get_settings()
    reference = context.current().request_id or utcnow().strftime("%Y%m%d%H%M%S")
    lines = [
        f"From: {ctx.user.name} <{ctx.user.email or '@' + (ctx.user.username or '')}>",
        f"Workspace: {ctx.tenant.name} ({ctx.tenant.slug}), plan {ctx.entitlements.plan.key}"
        if ctx.tenant and ctx.entitlements
        else "Workspace: none",
        f"Role: {ctx.role.name if ctx.role else '-'}",
        f"Page: {body.page or '-'}",
        f"Reference: {reference}",
        "",
        body.message,
    ]
    if settings.support_email:
        outbox.enqueue(
            ctx.db,
            "email.send",
            as_payload(
                Mail(
                    to=settings.support_email,
                    subject=f"[{body.topic}] {body.message[:60]}",
                    text="\n".join(lines),
                    html=None,
                    reply_to=ctx.user.email,
                )
            ),
        )
    else:
        log.info("support request", extra={"reference": reference, "topic": body.topic})
    if ctx.user.email:
        outbox.enqueue(
            ctx.db,
            "email.send",
            as_payload(
                Mail(
                    to=ctx.user.email,
                    subject="We got your message",
                    text=f"Hi {ctx.user.name},\n\nThanks for writing. We'll reply to this address. "
                    f"Your reference is {reference}.\n\nYour message:\n{body.message}",
                    html=None,
                )
            ),
        )
    await ctx.db.commit()
    await outbox.dispatch(outbox.pending_ids(ctx.db) or None)
    return SupportOut(reference=reference)


class UsageRow(BaseModel):
    event: str
    count: int
    workspaces: int


class UsageOut(BaseModel):
    days: int
    workspaces_total: int
    workspaces_new: int
    events: list[UsageRow]


async def usage(ctx: Ctx, days: int) -> UsageOut:
    """How the product is used, across workspaces: event counts only, no names or content.
    (The operator route in `app.ai.routes` checks who may call it.)"""
    since = utcnow() - timedelta(days=days)
    rows = (
        await ctx.db.execute(
            text("SELECT name, events, workspaces FROM app_usage_counts(:since)"), {"since": since}
        )
    ).all()
    total = await ctx.db.scalar(select(func.count()).select_from(Tenant).where(Tenant.status == "active"))
    new = await ctx.db.scalar(select(func.count()).select_from(Tenant).where(Tenant.created_at >= since))
    return UsageOut(
        days=days,
        workspaces_total=int(total or 0),
        workspaces_new=int(new or 0),
        events=[UsageRow(event=r[0], count=int(r[1]), workspaces=int(r[2])) for r in rows],
    )
