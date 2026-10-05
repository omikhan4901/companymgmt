"""Webhook endpoints, their delivery log, test sends and resends."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select

from app.core import audit, ratelimit
from app.core.errors import Invalid, NotFound
from app.core.http import check_if_match
from app.core.ids import uuid7
from app.core.schema import In
from app.core.time import utcnow
from app.modules.platform import webhooks
from app.modules.platform.deps import Ctx
from app.modules.platform.models import WebhookDelivery, WebhookEndpoint
from app.modules.platform.routes_developers import Developer
from app.modules.platform.webhooks import PING, PUBLIC_EVENTS, UnsafeAddress

router = APIRouter(prefix="/v1/webhooks", tags=["developers"])
# Sends on demand (test, resend) per workspace: enough for debugging, not for flooding.
SEND_RULE = ratelimit.Rule("webhook-send", 60, 3600)

MAX_ENDPOINTS = 20

EventName = Annotated[str, StringConstraints(max_length=60)]


class WebhookEventInfo(BaseModel):
    name: str
    description: str
    fields: list[str]


@router.get("/events", response_model=list[WebhookEventInfo])
async def catalogue(ctx: Ctx = Developer) -> list[WebhookEventInfo]:
    return [
        WebhookEventInfo(name=p.name, description=p.description, fields=list(p.fields))
        for p in sorted(PUBLIC_EVENTS.values(), key=lambda p: p.name)
    ]


class EndpointIn(In):
    url: Annotated[str, StringConstraints(min_length=8, max_length=webhooks.MAX_URL)]
    description: Annotated[str | None, StringConstraints(max_length=200)] = None
    events: list[EventName] = Field(min_length=1, max_length=60)
    active: bool = True


class EndpointOut(BaseModel):
    id: uuid.UUID
    url: str
    description: str | None
    events: list[str]
    active: bool
    disabled_reason: str | None
    failures: int
    created_at: datetime
    version: int
    # Only when it's made or the secret is rolled.
    secret: str | None = None


def _out(endpoint: WebhookEndpoint, secret: str | None = None) -> EndpointOut:
    return EndpointOut(
        id=endpoint.id,
        url=endpoint.url,
        description=endpoint.description,
        events=list(endpoint.events or []),
        active=endpoint.active,
        disabled_reason=endpoint.disabled_reason,
        failures=endpoint.failures,
        created_at=endpoint.created_at,
        version=endpoint.version,
        secret=secret,
    )


def _clean(body: EndpointIn) -> tuple[str, list[str]]:
    try:
        url = webhooks.check_url(body.url)
    except UnsafeAddress as exc:
        raise Invalid(errors=[{"field": "url", "message": str(exc)}]) from exc
    chosen = sorted(set(body.events))
    unknown = [e for e in chosen if e != "*" and e not in PUBLIC_EVENTS]
    if unknown:
        raise Invalid(errors=[{"field": "events", "message": f"Unknown events: {', '.join(unknown)}."}])
    return url, ["*"] if "*" in chosen else chosen


async def _load(ctx: Ctx, endpoint_id: uuid.UUID) -> WebhookEndpoint:
    endpoint = await ctx.db.scalar(
        select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint_id).with_for_update()
    )
    if endpoint is None:
        raise NotFound()
    return endpoint


@router.get("", response_model=list[EndpointOut])
async def list_endpoints(ctx: Ctx = Developer) -> list[EndpointOut]:
    rows = await ctx.db.scalars(select(WebhookEndpoint).order_by(WebhookEndpoint.created_at))
    return [_out(e) for e in rows]


@router.post("", response_model=EndpointOut, status_code=201)
async def create_endpoint(body: EndpointIn, ctx: Ctx = Developer) -> EndpointOut:
    url, chosen = _clean(body)
    count = len(list(await ctx.db.scalars(select(WebhookEndpoint.id))))
    if count >= MAX_ENDPOINTS:
        raise Invalid(f"A workspace can have up to {MAX_ENDPOINTS} webhook endpoints.", code="too_many")
    endpoint_id = uuid7()
    secret = webhooks.new_signing_secret()
    endpoint = WebhookEndpoint(
        id=endpoint_id,
        url=url,
        description=body.description,
        events=chosen,
        active=body.active,
        secret_enc=webhooks.seal(endpoint_id, secret),
        created_by=ctx.user.id,
    )
    ctx.db.add(endpoint)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "webhook.created",
        target_type="webhook",
        target_id=endpoint.id,
        data={"url": url, "events": chosen},
    )
    await ctx.db.commit()
    return _out(endpoint, secret)


@router.put("/{endpoint_id}", response_model=EndpointOut)
async def update_endpoint(
    endpoint_id: uuid.UUID, body: EndpointIn, request: Request, ctx: Ctx = Developer
) -> EndpointOut:
    endpoint = await _load(ctx, endpoint_id)
    check_if_match(request, endpoint.version)
    url, chosen = _clean(body)
    endpoint.url, endpoint.description, endpoint.events = url, body.description, chosen
    if body.active and not endpoint.active:
        endpoint.failures, endpoint.disabled_reason = 0, None
    endpoint.active = body.active
    endpoint.version += 1
    await audit.record(
        ctx.db,
        "webhook.updated",
        target_type="webhook",
        target_id=endpoint.id,
        data={"url": url, "events": chosen, "active": body.active},
    )
    await ctx.db.commit()
    return _out(endpoint)


@router.delete("/{endpoint_id}", status_code=204)
async def delete_endpoint(endpoint_id: uuid.UUID, ctx: Ctx = Developer) -> None:
    endpoint = await _load(ctx, endpoint_id)
    await audit.record(
        ctx.db, "webhook.deleted", target_type="webhook", target_id=endpoint.id, data={"url": endpoint.url}
    )
    await ctx.db.delete(endpoint)
    await ctx.db.commit()


@router.post("/{endpoint_id}/secret", response_model=EndpointOut)
async def roll_secret(endpoint_id: uuid.UUID, ctx: Ctx = Developer) -> EndpointOut:
    """A new signing secret (the old one stops at once)."""
    endpoint = await _load(ctx, endpoint_id)
    secret = webhooks.new_signing_secret()
    endpoint.secret_enc = webhooks.seal(endpoint.id, secret)
    endpoint.version += 1
    await audit.record(ctx.db, "webhook.secret_rolled", target_type="webhook", target_id=endpoint.id, data={})
    await ctx.db.commit()
    return _out(endpoint, secret)


class DeliveryOut(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    event: str
    status: str
    attempts: int
    next_attempt_at: datetime | None
    response_status: int | None
    response_ms: int | None
    error: str | None
    created_at: datetime
    finished_at: datetime | None


def _delivery_out(d: WebhookDelivery) -> DeliveryOut:
    return DeliveryOut(
        id=d.id,
        event_id=d.event_id,
        event=d.event,
        status=d.status,
        attempts=d.attempts,
        next_attempt_at=d.next_attempt_at,
        response_status=d.response_status,
        response_ms=d.response_ms,
        error=d.error,
        created_at=d.created_at,
        finished_at=d.finished_at,
    )


@router.post("/{endpoint_id}/test", response_model=DeliveryOut)
async def send_test(endpoint_id: uuid.UUID, ctx: Ctx = Developer) -> DeliveryOut:
    """Send a `ping` now and show what came back."""
    await ratelimit.enforce(SEND_RULE, str(ctx.tenant_id))
    endpoint = await _load(ctx, endpoint_id)
    payload = {
        "id": str(uuid7()),
        "type": PING,
        "created_at": utcnow().isoformat(),
        "workspace_id": str(ctx.tenant_id),
        "subject": {"type": "webhook", "id": str(endpoint.id)},
        "data": {},
    }
    delivery = webhooks.new_delivery(endpoint, payload)
    ctx.db.add(delivery)
    await ctx.db.flush()
    await webhooks.attempt(ctx.db, endpoint, delivery)
    # A test is one try: don't keep retrying it.
    if delivery.status == "pending":
        delivery.status, delivery.next_attempt_at, delivery.finished_at = "failed", None, utcnow()
    await ctx.db.commit()
    return _delivery_out(delivery)


@router.get("/{endpoint_id}/deliveries", response_model=list[DeliveryOut])
async def list_deliveries(
    endpoint_id: uuid.UUID,
    status: Annotated[str | None, Query(pattern="^(pending|succeeded|failed)$")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ctx: Ctx = Developer,
) -> list[DeliveryOut]:
    query = select(WebhookDelivery).where(WebhookDelivery.endpoint_id == endpoint_id)
    if status:
        query = query.where(WebhookDelivery.status == status)
    rows = await ctx.db.scalars(query.order_by(WebhookDelivery.created_at.desc()).limit(limit))
    return [_delivery_out(d) for d in rows]


@router.post("/deliveries/{delivery_id}/resend", response_model=DeliveryOut)
async def resend(delivery_id: uuid.UUID, ctx: Ctx = Developer) -> DeliveryOut:
    """Send the same event again now (same event id, so receivers can tell it's a repeat)."""
    await ratelimit.enforce(SEND_RULE, str(ctx.tenant_id))
    original = await ctx.db.get(WebhookDelivery, delivery_id)
    if original is None:
        raise NotFound()
    endpoint = await _load(ctx, original.endpoint_id)
    delivery = webhooks.new_delivery(endpoint, original.payload)
    ctx.db.add(delivery)
    await ctx.db.flush()
    await webhooks.attempt(ctx.db, endpoint, delivery)
    await ctx.db.commit()
    return _delivery_out(delivery)
