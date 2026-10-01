"""Domain events → notifications. Runs inside the transaction that made the change.

Requests go to the people who can decide them (in that person's department scope), and
decisions go back to the person they're about. Nobody is told about their own actions.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.modules.notifications.service import holders, notify, user_of, users_of

LEAVE = "/app/leave"
ATTENDANCE = "/app/attendance"
PAYROLL = "/app/payroll"
TASKS = "/app/tasks"
ANNOUNCEMENTS = "/app/announcements"


def _user(value: object) -> uuid.UUID | None:
    return uuid.UUID(str(value)) if value else None


async def _deciders(db: AsyncSession, event: events.Event, permission: str) -> list[uuid.UUID]:
    department = event.data.get("department_id")
    return await holders(db, permission, department_id=uuid.UUID(str(department)) if department else None)


@events.on("leave.requested")
async def leave_requested(db: AsyncSession, event: events.Event) -> None:
    # Asked on someone's behalf? They hear about it too.
    person = await user_of(db, event.data.get("membership_id"))
    await notify(db, event, [*await _deciders(db, event, "leave.approve"), person], link=LEAVE)


@events.on("leave.approved")
@events.on("leave.rejected")
async def leave_decided(db: AsyncSession, event: events.Event) -> None:
    await notify(db, event, [await user_of(db, event.data.get("membership_id"))], link=LEAVE)


@events.on("leave.cancelled")
async def leave_cancelled(db: AsyncSession, event: events.Event) -> None:
    person = await user_of(db, event.data.get("membership_id"))
    if person is not None and person == event.actor_user_id:
        # The person withdrew it: whoever would approve it no longer needs to.
        await notify(db, event, await _deciders(db, event, "leave.approve"), link=LEAVE)
    else:
        await notify(db, event, [person], link=LEAVE)


@events.on("attendance.correction_requested")
async def correction_requested(db: AsyncSession, event: events.Event) -> None:
    if event.data.get("status") != "pending":
        return  # applied straight away by someone allowed to
    await notify(db, event, await _deciders(db, event, "attendance.approve"), link=ATTENDANCE)


@events.on("attendance.correction_approved")
@events.on("attendance.correction_rejected")
async def correction_decided(db: AsyncSession, event: events.Event) -> None:
    await notify(db, event, [await user_of(db, event.data.get("membership_id"))], link=ATTENDANCE)


@events.on("payroll.submitted")
async def payroll_submitted(db: AsyncSession, event: events.Event) -> None:
    await notify(db, event, await holders(db, "payroll.approve"), link=PAYROLL)


@events.on("payroll.finalized")
async def payroll_finalized(db: AsyncSession, event: events.Event) -> None:
    # Everyone paid in the run hears that their payslip is ready, and nothing else:
    # the run's totals are not theirs to see.
    people = await users_of(db, event.data.get("membership_ids") or [])
    await notify(db, event, people, link=PAYROLL, data={"period": event.data.get("period")})


@events.on("task.assigned")
async def task_assigned(db: AsyncSession, event: events.Event) -> None:
    person = await user_of(db, event.data.get("assignee_membership_id"))
    await notify(db, event, [person], link=f"{TASKS}?task={event.subject_id}")


@events.on("task.commented")
async def task_commented(db: AsyncSession, event: events.Event) -> None:
    # The person doing it and the person who asked for it.
    people = [
        await user_of(db, event.data.get("assignee_membership_id")),
        _user(event.data.get("creator_user_id")),
    ]
    await notify(db, event, people, link=f"{TASKS}?task={event.subject_id}")


@events.on("task.completed")
async def task_completed(db: AsyncSession, event: events.Event) -> None:
    await notify(
        db, event, [_user(event.data.get("creator_user_id"))], link=f"{TASKS}?task={event.subject_id}"
    )


@events.on("project.members_added")
async def project_joined(db: AsyncSession, event: events.Event) -> None:
    people = await users_of(db, event.data.get("membership_ids") or [])
    await notify(
        db,
        event,
        people,
        link=f"{TASKS}?project={event.subject_id}",
        data={"project_name": event.data.get("project_name")},
    )


@events.on("announcement.published")
async def announced(db: AsyncSession, event: events.Event) -> None:
    people = await users_of(db, event.data.get("membership_ids") or [])
    await notify(
        db,
        event,
        people,
        link=f"{ANNOUNCEMENTS}?post={event.subject_id}",
        data={"title": event.data.get("title")},
    )
