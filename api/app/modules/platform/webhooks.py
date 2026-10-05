"""Signed webhooks: tell another system when something happens in the workspace.

- Only events in the public catalogue go out, under stable public names
  (`employee.onboarded`, not our internal `member.joined`), with thin payloads: ids and a
  few plain fields, never names, notes, salaries or contact details. Receivers fetch more
  with an API key, which checks permissions.
- Every delivery is signed: `CompanyMgmt-Signature: t=<unix time>,v1=<hex HMAC-SHA256 of
  "<t>.<body>">` with the endpoint's secret. Receivers should check it and refuse old `t`.
- Failed deliveries are retried with growing gaps for about a day and a half; every
  attempt is logged and can be sent again. An endpoint failing for too long is switched off.
- Requests only go to public internet addresses over HTTPS. The address is resolved and
  checked right before each send, and the connection goes to the checked address, so DNS
  tricks can't point us at internal services or cloud metadata.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events, safehttp
from app.core.config import get_settings
from app.core.db import open_session
from app.core.security import crypto
from app.core.security.tokens import new_secret
from app.core.time import utcnow
from app.modules.platform import hooks
from app.modules.platform.models import Membership, Tenant, User, WebhookDelivery, WebhookEndpoint

log = logging.getLogger(__name__)

SIGNATURE_HEADER = "CompanyMgmt-Signature"
# Minutes to wait before each retry; the first attempt is immediate.
BACKOFF_MINUTES = (1, 5, 30, 120, 360, 720, 1440)
MAX_ATTEMPTS = len(BACKOFF_MINUTES) + 1
# Switch an endpoint off after this many failed attempts in a row.
DISABLE_AFTER = 40
MAX_URL = safehttp.MAX_URL


@dataclass(frozen=True)
class Public:
    name: str
    description: str
    # Fields copied from the internal event; everything else is left out.
    fields: tuple[str, ...] = ()


# internal event -> public event
CATALOGUE: dict[str, Public] = {
    "member.joined": Public("employee.onboarded", "Someone joined the workspace.", ("membership_id",)),
    "member.removed": Public(
        "employee.offboarded", "Someone was removed from the workspace.", ("membership_id",)
    ),
    "leave.requested": Public(
        "leave.requested",
        "Leave was requested.",
        ("employee_id", "membership_id", "start_date", "end_date", "days"),
    ),
    "leave.approved": Public(
        "leave.approved",
        "Leave was approved.",
        ("employee_id", "membership_id", "start_date", "end_date", "days"),
    ),
    "leave.rejected": Public("leave.rejected", "Leave was turned down.", ("employee_id", "membership_id")),
    "leave.cancelled": Public("leave.cancelled", "Leave was cancelled.", ("employee_id", "membership_id")),
    "attendance.correction_approved": Public(
        "attendance.corrected", "An attendance correction was approved.", ()
    ),
    "task.assigned": Public("task.assigned", "A task was assigned.", ()),
    "document.published": Public("document.published", "A document or policy was published.", ()),
    "announcement.published": Public("announcement.published", "An announcement was posted.", ()),
    "payroll.finalized": Public("payroll.finalized", "A payroll run was finalised.", ("period", "headcount")),
    "sale.completed": Public("sale.completed", "A sale was made.", ("number", "total", "customer_id")),
    "sale.returned": Public("sale.returned", "Items were returned.", ("original_id", "total")),
    "sale.voided": Public("sale.voided", "A sale was voided.", ("number",)),
    "sales.drawer_closed": Public("drawer.closed", "A cash drawer was closed.", ()),
    "customer.paid": Public("customer.paid", "A customer paid towards their dues.", ("amount",)),
    "expense.recorded": Public("expense.recorded", "An expense was recorded.", ("amount", "category_id")),
    "purchase.received": Public(
        "purchase.received", "Stock was received from a supplier.", ("total", "paid", "supplier_id")
    ),
    "supplier.paid": Public("supplier.paid", "A supplier was paid.", ("supplier_id", "amount")),
    "stock.low": Public("stock.low", "An item fell to its reorder level.", ("quantity", "reorder_level")),
}
PUBLIC_EVENTS = {p.name: p for p in CATALOGUE.values()}
PING = "ping"


# ---- Addresses --------------------------------------------------------------------------

UnsafeAddress = safehttp.UnsafeAddress
check_url = safehttp.check_url


# ---- Signing ----------------------------------------------------------------------------


def sign(secret: str, body: bytes, timestamp: int) -> str:
    mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={mac}"


def verify(secret: str, body: bytes, header: str, *, tolerance: int = 300, now: int | None = None) -> bool:
    """What receivers do (the SDKs ship the same check)."""
    try:
        parts = dict(item.split("=", 1) for item in header.split(","))
        timestamp = int(parts["t"])
    except (KeyError, ValueError):
        return False
    if abs((now or int(time.time())) - timestamp) > tolerance:
        return False
    expected = sign(secret, body, timestamp).split("v1=", 1)[1]
    return hmac.compare_digest(expected, parts.get("v1", ""))


def new_signing_secret() -> str:
    return "whsec_" + new_secret(32)


def seal(endpoint_id: uuid.UUID, secret: str) -> str:
    return crypto.encrypt(secret, context=f"webhook:{endpoint_id}")


def unseal(endpoint: WebhookEndpoint) -> str:
    return crypto.decrypt(endpoint.secret_enc, context=f"webhook:{endpoint.id}")


# ---- Payloads ---------------------------------------------------------------------------


def payload_for(event: events.Event, occurred_at: datetime | None = None) -> dict[str, Any] | None:
    public = CATALOGUE.get(event.name)
    if public is None:
        return None
    return {
        "id": str(event.id),
        "type": public.name,
        "created_at": (occurred_at or utcnow()).isoformat(),
        "workspace_id": str(event.tenant_id),
        "subject": {"type": event.subject_type, "id": event.subject_id},
        "data": {k: event.data[k] for k in public.fields if k in event.data},
    }


def wants(endpoint: WebhookEndpoint, public_name: str) -> bool:
    chosen = endpoint.events or []
    return public_name == PING or "*" in chosen or public_name in chosen


# ---- Sending ----------------------------------------------------------------------------


async def _post(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str | None]:
    response = await safehttp.request("POST", url, content=body, headers=headers)
    return response.status_code, None


async def attempt(db: AsyncSession, endpoint: WebhookEndpoint, delivery: WebhookDelivery) -> None:
    """Send one delivery once, and record what happened (the caller commits)."""
    body = json.dumps(delivery.payload, separators=(",", ":"), sort_keys=True).encode()
    headers = {
        "Content-Type": "application/json",
        "User-Agent": f"{get_settings().app_name}-Webhooks/1",
        SIGNATURE_HEADER: sign(unseal(endpoint), body, int(time.time())),
        "CompanyMgmt-Event": delivery.event,
        "CompanyMgmt-Delivery": str(delivery.id),
    }
    started = time.perf_counter()
    error: str | None = None
    status: int | None = None
    try:
        status, error = await _post(endpoint.url, body, headers)
    except UnsafeAddress as exc:
        error = str(exc)
    except httpx.TimeoutException:
        error = "Timed out."
    except httpx.HTTPError as exc:
        error = f"Couldn't connect ({type(exc).__name__})."
    delivery.attempts += 1
    delivery.response_status = status
    delivery.response_ms = int((time.perf_counter() - started) * 1000)
    ok = status is not None and 200 <= status < 300
    if ok:
        delivery.status, delivery.error = "succeeded", None
        delivery.next_attempt_at = None
        delivery.finished_at = utcnow()
        endpoint.failures = 0
        return
    delivery.error = (error or f"The endpoint answered {status}.")[:300]
    endpoint.failures += 1
    if delivery.attempts >= MAX_ATTEMPTS:
        delivery.status, delivery.next_attempt_at, delivery.finished_at = "failed", None, utcnow()
    else:
        delivery.next_attempt_at = utcnow() + timedelta(minutes=BACKOFF_MINUTES[delivery.attempts - 1])
    if endpoint.failures >= DISABLE_AFTER and endpoint.active:
        endpoint.active = False
        endpoint.disabled_reason = "failing"
        await events.emit(
            db,
            "webhook.disabled",
            subject_type="webhook",
            subject_id=endpoint.id,
            data={"url": endpoint.url},
        )


def new_delivery(endpoint: WebhookEndpoint, payload: dict[str, Any]) -> WebhookDelivery:
    return WebhookDelivery(
        tenant_id=endpoint.tenant_id,
        endpoint_id=endpoint.id,
        event_id=uuid.UUID(payload["id"]),
        event=payload["type"],
        payload=payload,
        status="pending",
        next_attempt_at=utcnow(),
    )


@events.on("*", later=True)
async def fan_out(db: AsyncSession, event: events.Event) -> None:
    """After an event is saved: queue a delivery for every endpoint that wants it, and
    try each once straight away."""
    payload = payload_for(event)
    if payload is None:
        return
    endpoints = [
        e
        for e in await db.scalars(select(WebhookEndpoint).where(WebhookEndpoint.active.is_(True)))
        if wants(e, payload["type"])
    ]
    for endpoint in endpoints:
        delivery = new_delivery(endpoint, payload)
        db.add(delivery)
        await db.flush()
        await attempt(db, endpoint, delivery)


async def deliver_due(now: datetime | None = None, limit: int = 200) -> int:
    """Retry deliveries that are due, in every workspace. Returns attempts made."""
    now = now or utcnow()
    async with open_session() as db:
        tenant_ids = list(await db.scalars(select(Tenant.id).where(Tenant.status == "active")))
    sent = 0
    for tenant_id in tenant_ids:
        async with open_session(tenant_id) as db:
            rows = (
                await db.execute(
                    select(WebhookDelivery, WebhookEndpoint)
                    .join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id)
                    .where(
                        WebhookDelivery.status == "pending",
                        WebhookDelivery.next_attempt_at <= now,
                        WebhookEndpoint.active.is_(True),
                    )
                    .order_by(WebhookDelivery.next_attempt_at)
                    .limit(limit)
                    .with_for_update(of=WebhookDelivery, skip_locked=True)
                )
            ).all()
            for delivery, endpoint in rows:
                try:
                    await attempt(db, endpoint, delivery)
                except Exception:  # one bad endpoint mustn't stop the rest
                    log.exception("webhook delivery failed", extra={"delivery": str(delivery.id)})
                    delivery.next_attempt_at = now + timedelta(minutes=5)
                sent += 1
            await db.commit()
        if sent >= limit:
            break
    return sent


async def _removed(db: AsyncSession, membership: Membership, user: User) -> None:
    await events.emit(
        db,
        "member.removed",
        subject_type="member",
        subject_id=membership.id,
        data={"membership_id": membership.id},
    )


hooks.member_removed.append(_removed)
