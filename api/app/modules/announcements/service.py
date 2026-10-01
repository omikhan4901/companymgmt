"""Announcements: who sees a post, posting, read receipts.

A post reaches everyone, some branches, or some departments and everything below them.
People see posts addressed to them; owners and admins (unscoped posters) see all of them.
Read receipts count people who can sign in, since only they can read.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit, events
from app.core.errors import Forbidden, Invalid, NotFound
from app.core.time import utcnow
from app.modules.announcements import access
from app.modules.announcements.models import Announcement, AnnouncementRead
from app.modules.announcements.schemas import (
    AnnouncementIn,
    AnnouncementOut,
    AnnouncementPatch,
    AudienceRef,
    ReceiptOut,
    ReceiptsOut,
)
from app.modules.people.access import ancestors, scope_departments, subtree
from app.modules.people.models import Department, Employee
from app.modules.people.service import employee_for_membership
from app.modules.platform import hooks
from app.modules.platform.deps import Ctx
from app.modules.platform.models import Branch, Membership, User


async def _me(ctx: Ctx) -> Employee | None:
    if "announcements.me" not in ctx.cache:
        assert ctx.membership is not None
        ctx.cache["announcements.me"] = await employee_for_membership(ctx.db, ctx.membership.id)
    found: Employee | None = ctx.cache["announcements.me"]
    return found


def _unscoped_poster(ctx: Ctx) -> bool:
    return ctx.can(access.POST) and ctx.scope_department_id is None


async def _visible(ctx: Ctx) -> ColumnElement[bool]:
    """Posts addressed to the caller (or all of them, for unscoped posters)."""
    if _unscoped_poster(ctx):
        return Announcement.id.is_not(None)
    me = await _me(ctx)
    conditions: list[ColumnElement[bool]] = [
        Announcement.audience == "everyone",
        Announcement.author_id == ctx.user.id,
    ]
    if me is not None and me.branch_id is not None:
        conditions.append(
            and_(Announcement.audience == "branches", Announcement.audience_ids.contains([me.branch_id]))
        )
    above = await ancestors(ctx.db, me.department_id if me else None)
    if above:
        conditions.append(
            and_(Announcement.audience == "departments", Announcement.audience_ids.overlap(above))
        )
    return or_(*conditions)


def _can_edit(ctx: Ctx, post: Announcement) -> bool:
    return post.author_id == ctx.user.id or _unscoped_poster(ctx)


async def _reach_query(db: AsyncSession, post: Announcement) -> ColumnElement[bool]:
    """Employees the post is addressed to (active, with a login)."""
    base = and_(Employee.status == "active", Employee.membership_id.is_not(None))
    if post.audience == "branches":
        return and_(base, Employee.branch_id.in_(post.audience_ids))
    if post.audience == "departments":
        below: set[uuid.UUID] = set()
        for root in post.audience_ids:
            below.update(await subtree(db, root))
        return and_(base, Employee.department_id.in_(below))
    return base


async def _out(ctx: Ctx, posts: Sequence[Announcement]) -> list[AnnouncementOut]:
    if not posts:
        return []
    ids = [p.id for p in posts]
    mine = set(
        await ctx.db.scalars(
            select(AnnouncementRead.announcement_id).where(
                AnnouncementRead.announcement_id.in_(ids), AnnouncementRead.user_id == ctx.user.id
            )
        )
    )
    authors = dict(
        (
            await ctx.db.execute(
                select(User.id, User.name).where(User.id.in_({p.author_id for p in posts if p.author_id}))
            )
        ).all()
    )
    targets = {i for p in posts for i in p.audience_ids}
    names: dict[uuid.UUID, str] = {}
    if targets:
        names.update(
            (await ctx.db.execute(select(Branch.id, Branch.name).where(Branch.id.in_(targets)))).all()
        )
        names.update(
            (
                await ctx.db.execute(select(Department.id, Department.name).where(Department.id.in_(targets)))
            ).all()
        )
    out = []
    for p in posts:
        editable = _can_edit(ctx, p)
        reach = read_count = None
        if editable:
            reach, read_count = await _counts(ctx.db, p)
        out.append(
            AnnouncementOut(
                id=p.id,
                title=p.title,
                body=p.body,
                audience=p.audience,
                audience_names=[AudienceRef(id=i, name=names[i]) for i in p.audience_ids if i in names],
                pinned=p.pinned,
                published_at=p.published_at,
                edited_at=p.edited_at,
                author_name=authors.get(p.author_id) if p.author_id else None,
                read=p.id in mine or p.author_id == ctx.user.id,
                reach=reach,
                read_count=read_count,
                can_edit=editable,
                version=p.version,
            )
        )
    return out


async def _counts(db: AsyncSession, post: Announcement) -> tuple[int, int]:
    reach = await _reach_query(db, post)
    total = await db.scalar(select(func.count()).select_from(Employee).where(reach))
    read = await db.scalar(
        select(func.count())
        .select_from(Employee)
        .join(Membership, Membership.id == Employee.membership_id)
        .join(
            AnnouncementRead,
            and_(AnnouncementRead.announcement_id == post.id, AnnouncementRead.user_id == Membership.user_id),
        )
        .where(reach)
    )
    return total or 0, read or 0


async def feed(ctx: Ctx, *, limit: int = 30) -> list[AnnouncementOut]:
    query = (
        select(Announcement)
        .where(await _visible(ctx))
        .order_by(Announcement.pinned.desc(), Announcement.published_at.desc())
        .limit(limit)
    )
    return await _out(ctx, list(await ctx.db.scalars(query)))


async def unread_count(ctx: Ctx) -> int:
    read = select(AnnouncementRead.announcement_id).where(AnnouncementRead.user_id == ctx.user.id)
    count = await ctx.db.scalar(
        select(func.count())
        .select_from(Announcement)
        .where(
            await _visible(ctx),
            Announcement.id.not_in(read),
            or_(Announcement.author_id.is_(None), Announcement.author_id != ctx.user.id),
        )
    )
    return count or 0


async def _post(ctx: Ctx, post_id: uuid.UUID, *, lock: bool = False) -> Announcement:
    query = select(Announcement).where(Announcement.id == post_id, await _visible(ctx))
    if lock:
        query = query.with_for_update(of=Announcement)
    post = await ctx.db.scalar(query)
    if post is None:
        raise NotFound()
    return post


async def get(ctx: Ctx, post_id: uuid.UUID) -> AnnouncementOut:
    return (await _out(ctx, [await _post(ctx, post_id)]))[0]


async def _check_audience(ctx: Ctx, audience: str, ids: list[uuid.UUID]) -> list[uuid.UUID]:
    ids = list(dict.fromkeys(ids))
    scope = await scope_departments(ctx)
    if audience == "everyone":
        if scope is not None:
            raise Invalid(errors=[{"field": "audience", "message": "Post to your own departments."}])
        return []
    if not ids:
        raise Invalid(errors=[{"field": "audience_ids", "message": "Choose who should see this."}])
    if audience == "branches":
        if scope is not None:
            raise Invalid(errors=[{"field": "audience", "message": "Post to your own departments."}])
        found = set(await ctx.db.scalars(select(Branch.id).where(Branch.id.in_(ids))))
        if found != set(ids):
            raise Invalid(
                errors=[{"field": "audience_ids", "message": "Some of these branches don't exist."}]
            )
        return ids
    for department in ids:
        if not await hooks.valid_department(ctx.db, department) or (
            scope is not None and department not in scope
        ):
            raise Invalid(errors=[{"field": "audience_ids", "message": "Choose from your own departments."}])
    return ids


async def _publish_event(ctx: Ctx, post: Announcement) -> None:
    reach = await _reach_query(ctx.db, post)
    members = [m for m in await ctx.db.scalars(select(Employee.membership_id).where(reach)) if m]
    await events.emit(
        ctx.db,
        "announcement.published",
        subject_type="announcement",
        subject_id=post.id,
        data={"title": post.title, "membership_ids": members},
    )


async def create(ctx: Ctx, body: AnnouncementIn) -> AnnouncementOut:
    ctx.require(access.POST)
    targets = await _check_audience(ctx, body.audience, body.audience_ids)
    post = Announcement(
        title=body.title,
        body=body.body,
        audience=body.audience,
        audience_ids=targets,
        pinned=body.pinned,
        published_at=utcnow(),
        author_id=ctx.user.id,
    )
    ctx.db.add(post)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "announcement.published",
        target_type="announcement",
        target_id=post.id,
        data={"title": post.title, "audience": post.audience},
    )
    # The author has read their own post.
    ctx.db.add(AnnouncementRead(announcement_id=post.id, user_id=ctx.user.id, read_at=post.published_at))
    await _publish_event(ctx, post)
    await ctx.db.commit()
    return await get(ctx, post.id)


async def update(ctx: Ctx, post_id: uuid.UUID, body: AnnouncementPatch) -> AnnouncementOut:
    post = await _post(ctx, post_id, lock=True)
    if not _can_edit(ctx, post):
        raise Forbidden()
    if body.audience is not None or body.audience_ids is not None:
        audience = body.audience or post.audience
        post.audience_ids = await _check_audience(
            ctx, audience, body.audience_ids if body.audience_ids is not None else list(post.audience_ids)
        )
        post.audience = audience
    if body.title is not None:
        post.title = body.title
    if body.body is not None:
        post.body = body.body
    if body.pinned is not None:
        post.pinned = body.pinned
    if body.title is not None or body.body is not None:
        post.edited_at = utcnow()
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "announcement.updated",
        target_type="announcement",
        target_id=post.id,
        data=body.model_dump(exclude_unset=True, mode="json", exclude={"body"}),
    )
    await ctx.db.commit()
    return await get(ctx, post.id)


async def remove(ctx: Ctx, post_id: uuid.UUID) -> None:
    post = await _post(ctx, post_id, lock=True)
    if not _can_edit(ctx, post):
        raise Forbidden()
    await audit.record(
        ctx.db,
        "announcement.deleted",
        target_type="announcement",
        target_id=post.id,
        data={"title": post.title},
    )
    await ctx.db.execute(delete(Announcement).where(Announcement.id == post.id))
    await ctx.db.commit()


async def mark_read(ctx: Ctx, post_id: uuid.UUID) -> None:
    post = await _post(ctx, post_id)
    await ctx.db.execute(
        insert(AnnouncementRead)
        .values(tenant_id=post.tenant_id, announcement_id=post.id, user_id=ctx.user.id, read_at=utcnow())
        .on_conflict_do_nothing()
    )
    await ctx.db.commit()


async def receipts(ctx: Ctx, post_id: uuid.UUID) -> ReceiptsOut:
    post = await _post(ctx, post_id)
    if not _can_edit(ctx, post):
        raise Forbidden()
    reach = await _reach_query(ctx.db, post)
    rows = (
        await ctx.db.execute(
            select(Employee.id, Employee.full_name, Department.name, AnnouncementRead.read_at)
            .join(Membership, Membership.id == Employee.membership_id)
            .outerjoin(Department, Department.id == Employee.department_id)
            .outerjoin(
                AnnouncementRead,
                and_(
                    AnnouncementRead.announcement_id == post.id,
                    AnnouncementRead.user_id == Membership.user_id,
                ),
            )
            .where(reach)
            .order_by(AnnouncementRead.read_at.is_(None).desc(), func.lower(Employee.full_name))
        )
    ).all()
    people = [ReceiptOut(employee_id=r[0], name=r[1], department=r[2], read_at=r[3]) for r in rows]
    return ReceiptsOut(total=len(people), read=sum(1 for p in people if p.read_at), people=people)
