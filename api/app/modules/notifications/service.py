"""Who hears about what, and the inbox itself.

Modules don't call this: they emit domain events, and `subscribers` turns those into
notifications in the same transaction. Recipients are worked out here from roles and
department scope, so a scoped manager only hears about their own departments.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import func, literal, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.errors import Invalid, NotFound
from app.core.http import decode_cursor, encode_cursor
from app.core.time import utcnow
from app.modules.notifications.models import Notification
from app.modules.notifications.schemas import InboxOut, NotificationOut
from app.modules.people.access import subtree
from app.modules.platform import catalog
from app.modules.platform.deps import Ctx
from app.modules.platform.models import Membership, Role, User


async def holders(
    db: AsyncSession, permission: str, *, department_id: uuid.UUID | None = None
) -> list[uuid.UUID]:
    """Users of active members who hold `permission` and whose scope covers the department."""
    rows = (
        await db.execute(
            select(Membership.user_id, Membership.scope_department_id, Role)
            .join(Role, (Role.tenant_id == Membership.tenant_id) & (Role.id == Membership.role_id))
            .where(Membership.status == "active")
        )
    ).all()
    found: list[uuid.UUID] = []
    trees: dict[uuid.UUID, list[uuid.UUID]] = {}
    for user_id, scope, role in rows:
        if permission not in catalog.resolve(role.key, role.is_builtin, list(role.permissions or [])):
            continue
        if scope is not None:
            if department_id is None:
                continue
            if scope not in trees:
                trees[scope] = await subtree(db, scope)
            if department_id not in trees[scope]:
                continue
        found.append(user_id)
    return found


async def user_of(db: AsyncSession, membership_id: Any) -> uuid.UUID | None:
    if not membership_id:
        return None
    return await db.scalar(
        select(Membership.user_id).where(
            Membership.id == uuid.UUID(str(membership_id)), Membership.status == "active"
        )
    )


async def users_of(db: AsyncSession, membership_ids: Iterable[Any]) -> list[uuid.UUID]:
    ids = [uuid.UUID(str(m)) for m in membership_ids if m]
    if not ids:
        return []
    rows = await db.scalars(
        select(Membership.user_id).where(Membership.id.in_(ids), Membership.status == "active")
    )
    return list(rows)


async def notify(
    db: AsyncSession,
    event: events.Event,
    recipients: Iterable[uuid.UUID | None],
    *,
    link: str | None,
    data: dict[str, Any] | None = None,
) -> int:
    """One notification per recipient, never to the person who caused it."""
    people = {r for r in recipients if r is not None and r != event.actor_user_id}
    if not people:
        return 0
    actor = await db.get(User, event.actor_user_id) if event.actor_user_id else None
    now = utcnow()
    for user_id in sorted(people):
        db.add(
            Notification(
                tenant_id=event.tenant_id,
                user_id=user_id,
                kind=event.name,
                event_id=event.id,
                actor_name=actor.name if actor else None,
                subject_type=event.subject_type,
                subject_id=event.subject_id,
                link=link,
                data=event.data if data is None else data,
                created_at=now,
            )
        )
    return len(people)


def _out(row: Notification) -> NotificationOut:
    return NotificationOut(
        id=row.id,
        kind=row.kind,
        actor_name=row.actor_name,
        subject_type=row.subject_type,
        subject_id=row.subject_id,
        link=row.link,
        data=row.data,
        created_at=row.created_at,
        read_at=row.read_at,
    )


async def unread_count(ctx: Ctx) -> int:
    count = await ctx.db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == ctx.user.id, Notification.read_at.is_(None))
    )
    return count or 0


async def inbox(ctx: Ctx, *, unread_only: bool, cursor: str | None, limit: int) -> InboxOut:
    query = select(Notification).where(Notification.user_id == ctx.user.id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    after = decode_cursor(cursor)
    if after:
        try:
            point = (datetime.fromisoformat(str(after["t"])), uuid.UUID(str(after["id"])))
        except (KeyError, ValueError) as exc:
            raise Invalid("Bad cursor.", code="bad_cursor") from exc
        query = query.where(tuple_(Notification.created_at, Notification.id) < tuple_(*map(literal, point)))
    query = query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit + 1)
    rows = list((await ctx.db.scalars(query)).all())
    items = [_out(r) for r in rows[:limit]]
    last = items[-1] if items and len(rows) > limit else None
    next_cursor = encode_cursor({"t": last.created_at.isoformat(), "id": last.id}) if last else None
    return InboxOut(items=items, unread=await unread_count(ctx), next_cursor=next_cursor)


async def mark_read(ctx: Ctx, notification_id: uuid.UUID) -> None:
    row = await ctx.db.scalar(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == ctx.user.id)
    )
    if row is None:
        raise NotFound()
    if row.read_at is None:
        row.read_at = utcnow()
    await ctx.db.commit()


async def mark_all_read(ctx: Ctx) -> int:
    result = await ctx.db.execute(
        update(Notification)
        .where(Notification.user_id == ctx.user.id, Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )
    await ctx.db.commit()
    return int(result.rowcount or 0)  # type: ignore[attr-defined]
