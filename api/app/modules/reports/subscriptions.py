"""Getting the overview report by email, every week or every month.

The job runs once a day (Cloud Scheduler, see runbooks/deploy.md). On the first day of
the workspace's week it sends last week's report to weekly subscribers; on the first of
the month, last month's to monthly ones. Each report is worked out as the subscriber, so
it shows only what they could see in the app, and a member who has lost access to reports
simply gets nothing. A report is sent at most once a day per subscription.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import delete, select

from app.core import outbox
from app.core.db import open_session
from app.core.errors import AppError, Invalid
from app.core.time import local_date, utcnow
from app.modules.people.models import Department
from app.modules.platform.deps import Ctx, member_ctx
from app.modules.platform.models import Membership, Tenant, User
from app.modules.reports import access, emails
from app.modules.reports.models import ReportSubscription
from app.modules.reports.schemas import SubscriptionIn, SubscriptionOut
from app.modules.reports.service import _departments, overview

log = logging.getLogger(__name__)
FREQUENCIES = ("weekly", "monthly")


async def get(ctx: Ctx) -> SubscriptionOut:
    ctx.require(access.VIEW)
    assert ctx.membership is not None
    rows = list(
        await ctx.db.scalars(
            select(ReportSubscription).where(ReportSubscription.membership_id == ctx.membership.id)
        )
    )
    kinds = {r.frequency for r in rows}
    return SubscriptionOut(
        weekly="weekly" in kinds,
        monthly="monthly" in kinds,
        department_id=rows[0].department_id if rows else None,
        has_email=bool(ctx.user.email),
    )


async def save(ctx: Ctx, body: SubscriptionIn) -> SubscriptionOut:
    ctx.require(access.VIEW)
    assert ctx.membership is not None
    wanted = {f for f in FREQUENCIES if getattr(body, f)}
    if wanted and not ctx.user.email:
        raise Invalid("Add an email address to your account first.", code="no_email")
    await _departments(ctx, body.department_id)  # in scope, or 404
    await ctx.db.execute(
        delete(ReportSubscription).where(
            ReportSubscription.membership_id == ctx.membership.id,
            ReportSubscription.frequency.not_in(wanted or {""}),
        )
    )
    existing = {
        r.frequency: r
        for r in await ctx.db.scalars(
            select(ReportSubscription).where(ReportSubscription.membership_id == ctx.membership.id)
        )
    }
    for frequency in wanted:
        row = existing.get(frequency)
        if row is None:
            ctx.db.add(
                ReportSubscription(
                    membership_id=ctx.membership.id, frequency=frequency, department_id=body.department_id
                )
            )
        else:
            row.department_id = body.department_id
    await ctx.db.commit()
    return await get(ctx)


def period(frequency: str, day: date, week_start: int) -> tuple[date, date] | None:
    """The period to report on `day`, if a report is due then."""
    if frequency == "weekly" and day.isoweekday() == week_start:
        return day - timedelta(days=7), day - timedelta(days=1)
    if frequency == "monthly" and day.day == 1:
        last = day - timedelta(days=1)
        return last.replace(day=1), last
    return None


async def send_reports(now: datetime | None = None) -> int:
    """Queue the reports due today in each workspace's time zone. Returns emails queued."""
    now = now or utcnow()
    async with open_session() as db:
        tenant_ids = list(await db.scalars(select(Tenant.id).where(Tenant.status == "active")))
    sent = 0
    for tenant_id in tenant_ids:
        async with open_session(tenant_id) as db:
            tenant = await db.get(Tenant, tenant_id)
            assert tenant is not None
            day = local_date(now, tenant.timezone)
            rows = (
                await db.execute(
                    select(ReportSubscription, Membership, User)
                    .join(
                        Membership,
                        (Membership.tenant_id == ReportSubscription.tenant_id)
                        & (Membership.id == ReportSubscription.membership_id),
                    )
                    .join(User, User.id == Membership.user_id)
                    .where(Membership.status == "active", User.email.is_not(None))
                )
            ).all()
            for sub, membership, user in rows:
                due = period(sub.frequency, day, tenant.week_start)
                if due is None or sub.last_sent_on == day:
                    continue
                try:
                    ctx = await member_ctx(db, tenant, membership)
                    report = await overview(ctx, due[0], due[1], sub.department_id)
                except AppError:
                    log.info("report skipped", extra={"subscription": str(sub.id)})
                    continue
                scope = None
                if sub.department_id:
                    department = await db.get(Department, sub.department_id)
                    scope = department.name if department else None
                assert user.email is not None
                outbox.enqueue(
                    db,
                    "email.send",
                    emails.compose(
                        user.email, user.name, user.locale, tenant.name, sub.frequency, report, scope
                    ),
                    tenant_id=tenant.id,
                )
                sub.last_sent_on = day
                sent += 1
            ids = outbox.pending_ids(db)
            await db.commit()
        await outbox.dispatch(ids)
    return sent
