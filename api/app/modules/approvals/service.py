"""One inbox for everything waiting on the caller's decision.

Each kind of request stays owned by its module: the inbox lists what the caller may
decide (with that module's own permission, department scope and module switch) and
hands decisions back to the module's service. Nobody decides their own requests here;
owners still can from the module itself, where it's allowed.
"""

from __future__ import annotations

import uuid

from app.core.errors import NotFound
from app.modules.approvals.schemas import ApprovalItem, DecisionOut, Kind
from app.modules.attendance import access as attendance_access
from app.modules.attendance import service as attendance
from app.modules.leave import access as leave_access
from app.modules.leave import service as leave
from app.modules.platform.deps import Ctx, check_access


def _may(ctx: Ctx, permission: str, module: str) -> bool:
    modules = ctx.entitlements.modules if ctx.entitlements else frozenset()
    return module in modules and ctx.can(permission)


async def pending(ctx: Ctx) -> list[ApprovalItem]:
    """Oldest first: whoever has waited longest comes first."""
    items: list[ApprovalItem] = []
    if _may(ctx, leave_access.APPROVE, "leave"):
        own = await leave.employee_or_none(ctx)
        for r in await leave.list_requests(ctx, status="pending"):
            if own is not None and r.employee_id == own.id:
                continue
            items.append(
                ApprovalItem(
                    kind="leave",
                    id=r.id,
                    employee_id=r.employee_id,
                    employee_name=r.employee_name,
                    requested_at=r.created_at,
                    reason=r.reason,
                    leave_type_name=r.leave_type_name,
                    start_date=r.start_date,
                    end_date=r.end_date,
                    days=r.days,
                    half_day=r.half_day,
                )
            )
    if _may(ctx, attendance_access.APPROVE, "attendance"):
        for c in await attendance.list_corrections(ctx, status="pending"):
            if c.requested_by == ctx.user.id:
                continue
            items.append(
                ApprovalItem(
                    kind="time_fix",
                    id=c.id,
                    employee_id=c.employee_id,
                    employee_name=c.employee_name,
                    requested_at=c.created_at,
                    reason=c.reason,
                    fix_kind=c.kind,
                    clock_in_at=c.proposed_clock_in_at,
                    clock_out_at=c.proposed_clock_out_at,
                )
            )
    return sorted(items, key=lambda i: i.requested_at)


async def decide(ctx: Ctx, kind: Kind, item_id: uuid.UUID, *, approve: bool, note: str | None) -> DecisionOut:
    if kind == "leave":
        check_access(ctx, leave_access.APPROVE, module="leave", writing=True)
        result = await (leave.approve if approve else leave.reject)(ctx, item_id, note)
        return DecisionOut(kind=kind, id=result.id, status=result.status)
    if kind == "time_fix":
        check_access(ctx, attendance_access.APPROVE, module="attendance", writing=True)
        fixed = await (attendance.approve_correction if approve else attendance.reject_correction)(
            ctx, item_id, note
        )
        return DecisionOut(kind=kind, id=fixed.id, status=fixed.status)
    raise NotFound()
