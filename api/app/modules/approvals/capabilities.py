"""Approval capabilities (see platform/capabilities.py)."""

from __future__ import annotations

from app.modules.approvals import service
from app.modules.approvals.schemas import InboxOut
from app.modules.platform.capabilities import NoInput, capability
from app.modules.platform.deps import Ctx


@capability(
    "approvals.pending",
    "Requests waiting for your decision (leave, time fixes), oldest first.",
    output=InboxOut,
    permission=None,
    module=None,
    route="GET /v1/approvals",
)
async def pending(ctx: Ctx, _: NoInput) -> InboxOut:
    return InboxOut(items=await service.pending(ctx))
