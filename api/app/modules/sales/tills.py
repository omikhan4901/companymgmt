"""Shared tills: a manager registers a browser as a till once; cashiers then unlock it
with a short PIN instead of typing a password in front of customers.

- A PIN alone is useless: it only works together with a registered till's secret (kept
  in that browser), for members of the same workspace who may sell.
- Wrong PINs lock that cashier's PIN for 15 minutes after 5 tries; tills are also rate
  limited. PINs are argon2-hashed; obvious ones (1111, 1234) are refused.
- The session a PIN opens can only sell, look up customers and record expenses, lasts
  at most 12 hours, can't change the account, and ends when the till is revoked.
"""

from __future__ import annotations

import itertools
import re
import uuid
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit, context, ratelimit
from app.core.db import get_db, set_tenant
from app.core.errors import Forbidden, Invalid, NotFound, TooManyRequests, Unauthorized
from app.core.schema import In
from app.core.security import passwords
from app.core.security.tokens import hash_secret, new_secret
from app.core.time import utcnow
from app.modules.platform import catalog
from app.modules.platform.deps import Ctx, allow, people_only, public
from app.modules.platform.models import AuthSession, Membership, Role, Tenant, User
from app.modules.platform.routes_auth import TokenOut, _check_origin, _tokens
from app.modules.platform.tokens import log_event, start_session
from app.modules.sales import access
from app.modules.sales.models import CashierPin, Till

router = APIRouter(prefix="/v1", tags=["sales"])

TOKEN_PREFIX = "till_"  # noqa: S105 (a prefix, not a secret)
MAX_FAILURES = 5
LOCK = timedelta(minutes=15)
SESSION_HOURS = 12
TILL_RULE = ratelimit.Rule("till", 30, 60)
WEAK = re.compile(r"^(\d)\1+$")


def weak_pin(pin: str) -> bool:
    """All one digit, or a straight run up or down (1234, 9876)."""
    if WEAK.match(pin):
        return True
    steps = {int(b) - int(a) for a, b in itertools.pairwise(pin)}
    return steps in ({1}, {-1})


# ---- Managing tills (managers) ----------------------------------------------------------


class TillIn(In):
    name: Annotated[str, StringConstraints(min_length=1, max_length=80, strip_whitespace=True)]
    branch_id: uuid.UUID | None = None


class TillOut(BaseModel):
    id: uuid.UUID
    name: str
    branch_id: uuid.UUID | None
    hint: str
    last_seen_at: datetime | None
    revoked: bool
    # Only when it's registered: stored in that browser, never shown again.
    token: str | None = None


def _out(till: Till, token: str | None = None) -> TillOut:
    return TillOut(
        id=till.id,
        name=till.name,
        branch_id=till.branch_id,
        hint=till.hint,
        last_seen_at=till.last_seen_at,
        revoked=till.revoked_at is not None,
        token=token,
    )


Manage = Depends(allow(access.MANAGE, module=access.MODULE))


@router.get("/sales/tills", response_model=list[TillOut])
async def list_tills(ctx: Ctx = Manage) -> list[TillOut]:
    rows = await ctx.db.scalars(select(Till).order_by(Till.revoked_at.is_not(None), Till.created_at.desc()))
    return [_out(t) for t in rows]


@router.post("/sales/tills", response_model=TillOut, status_code=201)
async def register_till(body: TillIn, ctx: Ctx = Manage) -> TillOut:
    """Run this on the till itself: the browser keeps the returned token."""
    people_only(ctx)
    secret = new_secret(32)
    till = Till(
        name=body.name,
        branch_id=body.branch_id,
        token_hash=hash_secret(secret),
        hint=secret[:6],
        created_by=ctx.user.id,
    )
    ctx.db.add(till)
    await ctx.db.flush()
    await audit.record(
        ctx.db, "till.registered", target_type="till", target_id=till.id, data={"name": till.name}
    )
    await ctx.db.commit()
    return _out(till, f"{TOKEN_PREFIX}{ctx.tenant_id.hex}_{secret}")


@router.delete("/sales/tills/{till_id}", status_code=204)
async def revoke_till(till_id: uuid.UUID, ctx: Ctx = Manage) -> None:
    till = await ctx.db.scalar(select(Till).where(Till.id == till_id).with_for_update())
    if till is None:
        raise NotFound()
    if till.revoked_at is None:
        till.revoked_at = utcnow()
        await ctx.db.execute(
            update(AuthSession)
            .where(AuthSession.device_id == till.id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=utcnow(), revoke_reason="till_revoked")
        )
        await audit.record(
            ctx.db, "till.revoked", target_type="till", target_id=till.id, data={"name": till.name}
        )
        await ctx.db.commit()


# ---- Your own PIN --------------------------------------------------------------------------


class PinIn(In):
    pin: Annotated[str, StringConstraints(pattern=r"^\d{4,8}$")]


class PinStatus(BaseModel):
    has_pin: bool
    locked_until: datetime | None = None


@router.get("/sales/my-pin", response_model=PinStatus)
async def my_pin(ctx: Ctx = Depends(allow(access.SELL, module=access.MODULE))) -> PinStatus:
    assert ctx.membership is not None
    row = await ctx.db.get(CashierPin, ctx.membership.id)
    return PinStatus(has_pin=row is not None, locked_until=row.locked_until if row else None)


@router.put("/sales/my-pin", response_model=PinStatus)
async def set_pin(body: PinIn, ctx: Ctx = Depends(allow(access.SELL, module=access.MODULE))) -> PinStatus:
    """Set (or change) your till PIN. Only from a full sign-in, not from a till."""
    people_only(ctx)
    if ctx.session.method == "pin":
        raise Forbidden("Sign in with your password to change your PIN.", code="till_session")
    if weak_pin(body.pin):
        raise Invalid(
            errors=[
                {"field": "pin", "message": "Choose a PIN that isn't a repeated digit or a straight run."}
            ]
        )
    assert ctx.membership is not None
    row = await ctx.db.get(CashierPin, ctx.membership.id)
    if row is None:
        row = CashierPin(membership_id=ctx.membership.id, pin_hash="")
        ctx.db.add(row)
    row.pin_hash = passwords.hash_password(body.pin)
    row.failures, row.locked_until = 0, None
    await audit.record(ctx.db, "till.pin_set", target_type="member", target_id=ctx.membership.id, data={})
    await ctx.db.commit()
    return PinStatus(has_pin=True)


@router.delete("/sales/my-pin", status_code=204)
async def remove_pin(ctx: Ctx = Depends(allow(access.SELL, module=access.MODULE))) -> None:
    people_only(ctx)
    assert ctx.membership is not None
    row = await ctx.db.get(CashierPin, ctx.membership.id)
    if row is not None:
        await ctx.db.delete(row)
        await ctx.db.commit()


# ---- At the till ---------------------------------------------------------------------------


async def _till(db: AsyncSession, token: str | None) -> tuple[Till, Tenant]:
    """The registered till this browser is (its token is in the X-Till-Token header)."""
    if not token or not token.startswith(TOKEN_PREFIX):
        raise Unauthorized("This device isn't registered as a till.", code="till_unknown")
    workspace, _, secret = token[len(TOKEN_PREFIX) :].partition("_")
    try:
        tenant_id = uuid.UUID(hex=workspace)
    except ValueError as exc:
        raise Unauthorized("This device isn't registered as a till.", code="till_unknown") from exc
    allowed, _, retry = await ratelimit.hit(TILL_RULE, f"{tenant_id}:{hash_secret(secret)[:16]}")
    if not allowed:
        raise TooManyRequests(headers={"Retry-After": str(max(retry, 1))})
    await set_tenant(db, tenant_id)
    till = await db.scalar(select(Till).where(Till.token_hash == hash_secret(secret)))
    tenant = await db.get(Tenant, tenant_id)
    if till is None or till.revoked_at is not None or tenant is None or tenant.status != "active":
        raise Unauthorized("This till was removed. Ask a manager to register it again.", code="till_unknown")
    return till, tenant


class CashierOut(BaseModel):
    membership_id: uuid.UUID
    name: str


class TillInfo(BaseModel):
    till: str
    workspace: str
    cashiers: list[CashierOut]


async def _cashiers(db: AsyncSession) -> list[tuple[Membership, User, Role]]:
    rows = (
        await db.execute(
            select(Membership, User, Role)
            .join(CashierPin, CashierPin.membership_id == Membership.id)
            .join(User, User.id == Membership.user_id)
            .join(Role, (Role.tenant_id == Membership.tenant_id) & (Role.id == Membership.role_id))
            .where(Membership.status == "active", User.disabled_at.is_(None))
            .order_by(User.name)
        )
    ).all()
    return [
        (m, u, r)
        for m, u, r in rows
        if access.SELL in catalog.resolve(r.key, r.is_builtin, list(r.permissions or []))
    ]


@router.get("/till", response_model=TillInfo)
async def till_info(
    db: AsyncSession = Depends(get_db),
    x_till_token: str | None = Header(default=None),
    _: None = Depends(public()),
) -> TillInfo:
    """Who can unlock this till (names only)."""
    till, tenant = await _till(db, x_till_token)
    till.last_seen_at = utcnow()
    cashiers = [CashierOut(membership_id=m.id, name=u.name) for m, u, _r in await _cashiers(db)]
    await db.commit()
    return TillInfo(till=till.name, workspace=tenant.name, cashiers=cashiers)


class UnlockIn(In):
    membership_id: uuid.UUID
    pin: Annotated[str, StringConstraints(pattern=r"^\d{4,8}$")]


class UnlockOut(TokenOut):
    name: str
    expires_session_at: datetime = Field(description="When the cashier is signed out of the till")


@router.post("/till/unlock", response_model=UnlockOut)
async def unlock(
    body: UnlockIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    x_till_token: str | None = Header(default=None),
    _: None = Depends(public()),
) -> UnlockOut:
    _check_origin(request)
    till, tenant = await _till(db, x_till_token)
    found = {m.id: (m, u) for m, u, _r in await _cashiers(db)}
    pin = await db.scalar(
        select(CashierPin).where(CashierPin.membership_id == body.membership_id).with_for_update()
    )
    now = utcnow()
    if body.membership_id not in found or pin is None:
        # Same answer and cost as a wrong PIN: don't reveal who has one.
        passwords.verify_password(None, body.pin)
        raise Unauthorized("That PIN isn't right.", code="pin_wrong")
    if pin.locked_until and pin.locked_until > now:
        raise TooManyRequests(
            "Too many wrong PINs. Try again later or sign in with your password.",
            code="pin_locked",
            headers={"Retry-After": str(int((pin.locked_until - now).total_seconds()) + 1)},
        )
    member, user = found[body.membership_id]
    if not passwords.verify_password(pin.pin_hash, body.pin):
        pin.failures += 1
        if pin.failures >= MAX_FAILURES:
            pin.failures, pin.locked_until = 0, now + LOCK
            await audit.record(
                db, "till.pin_locked", target_type="member", target_id=member.id, data={"till": till.name}
            )
        await db.commit()
        raise Unauthorized("That PIN isn't right.", code="pin_wrong")
    pin.failures, pin.locked_until = 0, None
    till.last_seen_at = now
    await set_tenant(db, tenant.id, user.id)
    issued = await start_session(db, user, tenant.id, mfa=False, method="pin")
    issued.session.device_id = till.id
    issued.session.expires_at = now + timedelta(hours=SESSION_HOURS)
    log_event(db, user.id, "till.unlocked", till=str(till.id), ip=context.current().ip)
    tokens = await _tokens(db, response, issued)
    return UnlockOut(**tokens.model_dump(), name=user.name, expires_session_at=issued.session.expires_at)
