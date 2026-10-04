"""Reports over HTTP."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.modules.platform.deps import Ctx, allow
from app.modules.platform.internal import internal_only
from app.modules.reports import access, service, signals, subscriptions
from app.modules.reports.schemas import OverviewOut, SubscriptionIn, SubscriptionOut

router = APIRouter(prefix="/v1/reports", tags=["reports"])


@router.get("/overview", response_model=OverviewOut)
async def overview(
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to")],
    department_id: uuid.UUID | None = None,
    ctx: Ctx = Depends(allow(access.VIEW, module="people")),
) -> OverviewOut:
    return await service.overview(ctx, start, end, department_id)


@router.get("/subscription", response_model=SubscriptionOut)
async def get_subscription(ctx: Ctx = Depends(allow(access.VIEW, module="people"))) -> SubscriptionOut:
    return await subscriptions.get(ctx)


@router.put("/subscription", response_model=SubscriptionOut)
async def save_subscription(
    body: SubscriptionIn, ctx: Ctx = Depends(allow(access.VIEW, module="people"))
) -> SubscriptionOut:
    return await subscriptions.save(ctx, body)


# Called by Cloud Scheduler once a day with the internal token (see runbooks/deploy.md).
@router.get("/signals", response_model=signals.SignalsOut)
async def get_signals(ctx: Ctx = Depends(allow(access.VIEW, module="people"))) -> signals.SignalsOut:
    """Early-warning signals within your departments (when the workspace has them on)."""
    return await signals.signals(ctx)


@router.post("/signals/dismiss", status_code=204)
async def dismiss_signal(
    body: signals.DismissIn, ctx: Ctx = Depends(allow(access.VIEW, module="people"))
) -> Response:
    await signals.dismiss(ctx, body)
    return Response(status_code=204)


internal_router = APIRouter(prefix="/internal", tags=["internal"], include_in_schema=False)


@internal_router.post("/reports/send")
async def send(_: None = Depends(internal_only)) -> dict[str, int]:
    return {"emails": await subscriptions.send_reports()}
