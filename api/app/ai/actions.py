"""Actions: the assistant proposes, the person confirms.

When the model calls a capability that changes data, nothing runs. A proposal is saved
with the checked input and a plain preview, and the model is told it waits for the person.
Only the person who asked can confirm it, within an hour, and it then runs through
`invoke` as them, with their permissions at that moment, exactly like the REST API. The
change and the audit entry ("via the assistant") are saved together.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select

from app.ai import workspace
from app.core import audit
from app.core.errors import AppError, Conflict, Forbidden, NotFound
from app.core.time import utcnow
from app.modules.leave.models import LeaveRequest, LeaveType
from app.modules.people.models import Employee
from app.modules.platform.ai_models import Proposal
from app.modules.platform.capabilities import REGISTRY, Capability, invoke
from app.modules.platform.deps import Ctx, check_access
from app.modules.tasks.models import Project, Task

TTL = timedelta(hours=1)
FEATURE = "actions"
# Fields worth showing, in this order; ids are shown by name.
SHOWN = (
    "decision",
    "task_id",
    "request_id",
    "title",
    "body",
    "description",
    "assignee_id",
    "employee_id",
    "project_id",
    "leave_type_id",
    "start_date",
    "end_date",
    "half_day",
    "due_date",
    "no_due_date",
    "unassigned",
    "priority",
    "status",
    "audience",
    "pinned",
    "reason",
    "note",
    "checklist",
)
NAMES: dict[str, tuple[type[Any], str]] = {
    "assignee_id": (Employee, "full_name"),
    "employee_id": (Employee, "full_name"),
    "project_id": (Project, "name"),
    "task_id": (Task, "title"),
    "leave_type_id": (LeaveType, "name"),
}


class FieldOut(BaseModel):
    field: str
    value: str
    kind: str = "text"


class ActionOut(BaseModel):
    id: uuid.UUID
    capability: str
    label: str
    fields: list[FieldOut]
    status: str
    expires_at: str
    error: str | None
    link: str | None


async def _value(ctx: Ctx, field: str, value: Any) -> FieldOut | None:
    if value is None or value is False or value == [] or value == "":
        return None
    if field in NAMES:
        model, attr = NAMES[field]
        row = await ctx.db.get(model, uuid.UUID(str(value)))
        return FieldOut(field=field, value=str(getattr(row, attr)) if row else "?")
    if field == "request_id":
        request = await ctx.db.get(LeaveRequest, uuid.UUID(str(value)))
        if request is None:
            return FieldOut(field=field, value="?")
        person = await ctx.db.get(Employee, request.employee_id)
        name = person.full_name if person else "?"
        return FieldOut(field=field, value=f"{name}: {request.start_date} to {request.end_date}")
    if isinstance(value, date):
        return FieldOut(field=field, value=value.isoformat(), kind="date")
    if isinstance(value, list):
        return FieldOut(field=field, value="\n".join(str(v) for v in value), kind="list")
    if isinstance(value, bool):
        return FieldOut(field=field, value="yes", kind="flag")
    return FieldOut(field=field, value=str(value))


async def preview(ctx: Ctx, data: BaseModel) -> list[FieldOut]:
    given = {k: getattr(data, k) for k in data.model_fields_set}
    out = []
    for field in sorted(given, key=lambda f: SHOWN.index(f) if f in SHOWN else len(SHOWN)):
        shown = await _value(ctx, field, given[field])
        if shown is not None:
            out.append(shown)
    return out


async def propose(
    ctx: Ctx, cap: Capability, args: dict[str, Any], conversation_id: uuid.UUID | None
) -> tuple[Proposal, list[FieldOut]]:
    """Check the input and the person's access now (so the model hears about problems at
    once), and save the proposal. Raises AppError when it couldn't be done."""
    assert ctx.membership is not None
    check_access(ctx, cap.permission, module=cap.module, writing=True)
    data = cap.input.model_validate(args)
    fields = await preview(ctx, data)
    proposal = Proposal(
        membership_id=ctx.membership.id,
        conversation_id=conversation_id,
        capability=cap.name,
        args=data.model_dump(mode="json", by_alias=True, exclude_unset=True),
        preview=[f.model_dump() for f in fields],
        status="pending",
        expires_at=utcnow() + TTL,
    )
    ctx.db.add(proposal)
    await ctx.db.flush()
    return proposal, fields


def out(p: Proposal) -> ActionOut:
    expired = p.status == "pending" and p.expires_at <= utcnow()
    return ActionOut(
        id=p.id,
        capability=p.capability,
        label=REGISTRY[p.capability].summary if p.capability in REGISTRY else p.capability,
        fields=[FieldOut(**f) for f in p.preview or []],
        status="expired" if expired else p.status,
        expires_at=p.expires_at.isoformat(),
        error=p.error,
        link=p.link,
    )


def _link(capability: str, result: Any) -> str | None:
    if capability.startswith("tasks.") and isinstance(result, dict):
        task_id = result.get("task_id") or result.get("id")
        return f"/app/tasks?task={task_id}" if task_id else "/app/tasks"
    return {
        "leave.request": "/app/leave",
        "leave.decide": "/app/approvals",
        "announcements.post": "/app/announcements",
    }.get(capability)


async def _mine(ctx: Ctx, proposal_id: uuid.UUID, membership_id: uuid.UUID | None = None) -> Proposal:
    """The proposal, if it was made for this person. Pass `membership_id` after a rollback
    (the context's rows are expired then)."""
    if membership_id is None:
        assert ctx.membership is not None
        membership_id = ctx.membership.id
    found = await ctx.db.scalar(select(Proposal).where(Proposal.id == proposal_id).with_for_update())
    if found is None or found.membership_id != membership_id:
        raise NotFound()
    return found


async def confirm(ctx: Ctx, proposal_id: uuid.UUID) -> ActionOut:
    proposal = await _mine(ctx, proposal_id)
    if proposal.status != "pending":
        raise Conflict("This has already been decided.", code="action_decided")
    if proposal.expires_at <= utcnow():
        raise Conflict("This offer has expired. Ask the assistant again.", code="action_expired")
    row = await workspace.settings(ctx)
    if not row.enabled or FEATURE not in (row.features or []):
        raise Forbidden("Actions are switched off in this workspace.", code="ai_feature_off")
    pid, capability, args = proposal.id, proposal.capability, proposal.args
    conversation_id, mid = proposal.conversation_id, proposal.membership_id
    proposal.status = "done"
    proposal.decided_at = utcnow()
    await audit.record(
        ctx.db,
        "ai.action_confirmed",
        target_type="ai_proposal",
        target_id=pid,
        data={"capability": capability, "conversation_id": str(conversation_id) if conversation_id else None},
    )
    try:
        # The module commits the change, this status and the audit entry together.
        result = await invoke(ctx, capability, args, allow_writes=True)
    except AppError as exc:
        await ctx.db.rollback()
        failed = await _mine(ctx, pid, mid)
        failed.status = "failed"
        failed.decided_at = utcnow()
        failed.error = exc.detail
        await ctx.db.commit()
        return out(failed)
    done = await _mine(ctx, pid, mid)
    done.link = _link(capability, result)
    await ctx.db.commit()
    return out(done)


async def cancel(ctx: Ctx, proposal_id: uuid.UUID) -> ActionOut:
    proposal = await _mine(ctx, proposal_id)
    if proposal.status != "pending":
        raise Conflict("This has already been decided.", code="action_decided")
    proposal.status = "cancelled"
    proposal.decided_at = utcnow()
    await ctx.db.commit()
    return out(proposal)
