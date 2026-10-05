"""API keys and the workspace's network allowlist.

An API key acts as the member who made it, limited to the permissions chosen for it, and
never more than that member holds at the time of each call (demote or remove them and
their keys shrink or stop). The secret is shown once; only its hash is kept. Rotating a key
can keep the old secret working for a while, so systems can switch over without downtime.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, select

from app.core import audit, context, ipnet
from app.core import permissions as perms
from app.core.errors import Conflict, Forbidden, Invalid, NotFound, PaymentRequired
from app.core.schema import In
from app.core.security.tokens import hash_secret, new_secret
from app.core.spreadsheet import safe_cell
from app.core.time import utcnow
from app.modules.platform import catalog, workspaces
from app.modules.platform.catalog import AUDIT_VIEW, DEVELOPERS_MANAGE
from app.modules.platform.deps import API_KEY_PREFIX, Ctx, allow, people_only
from app.modules.platform.models import ApiKey, ApiKeyUsage, Membership, Subscription, Tenant, User

router = APIRouter(prefix="/v1", tags=["developers"])

KEY_DAYS_MAX = 730
GRACE_HOURS_MAX = 168


async def developer(ctx: Ctx = Depends(allow(DEVELOPERS_MANAGE))) -> Ctx:
    people_only(ctx)
    assert ctx.entitlements is not None
    if not ctx.entitlements.feature("api"):
        raise PaymentRequired("API access isn't included in this plan.", code="api_not_in_plan")
    return ctx


developer._access = "workspace"  # type: ignore[attr-defined]
developer._permission = DEVELOPERS_MANAGE  # type: ignore[attr-defined]
Developer = Depends(developer)


class GrantableOut(BaseModel):
    key: str
    label: str
    module: str


@router.get("/api-keys/permissions", response_model=list[GrantableOut])
async def grantable(ctx: Ctx = Developer) -> list[GrantableOut]:
    """What you can give a key: what you hold yourself, except owner-only powers."""
    mine = ctx.permissions - catalog.owner_only()
    return [GrantableOut(key=p.key, label=p.label, module=p.module) for p in perms.catalog() if p.key in mine]


Cidrs = Annotated[list[Annotated[str, StringConstraints(max_length=50)]], Field(max_length=ipnet.MAX_ENTRIES)]


def _cidrs(entries: list[str], field: str) -> list[str]:
    try:
        return ipnet.normalize(entries)
    except ValueError as exc:
        raise Invalid(errors=[{"field": field, "message": str(exc)}]) from exc


class ApiKeyIn(In):
    name: Annotated[str, StringConstraints(min_length=1, max_length=120, strip_whitespace=True)]
    permissions: list[Annotated[str, StringConstraints(max_length=60)]] = Field(min_length=1, max_length=200)
    rate_per_minute: int = Field(default=120, ge=10, le=1200)
    allowed_ips: Cidrs = Field(default_factory=list)
    # None = never expires.
    expires_in_days: int | None = Field(default=365, ge=1, le=KEY_DAYS_MAX)


class ApiKeyPatch(In):
    name: Annotated[str, StringConstraints(min_length=1, max_length=120, strip_whitespace=True)] | None = None
    permissions: list[Annotated[str, StringConstraints(max_length=60)]] | None = Field(
        default=None, min_length=1, max_length=200
    )
    rate_per_minute: int | None = Field(default=None, ge=10, le=1200)
    allowed_ips: Cidrs | None = None


class ApiKeyOut(BaseModel):
    id: uuid.UUID
    name: str
    hint: str
    permissions: list[str]
    rate_per_minute: int
    allowed_ips: list[str]
    member_name: str
    expires_at: datetime | None
    previous_expires_at: datetime | None
    last_used_at: datetime | None
    last_used_ip: str | None
    created_at: datetime
    revoked: bool
    # Only when it's made or rotated: the full key (never shown again).
    token: str | None = None


def _token(tenant_id: uuid.UUID) -> tuple[str, str]:
    secret = new_secret(30)
    return f"{API_KEY_PREFIX}{tenant_id.hex}_{secret}", secret


def _key_out(key: ApiKey, member: str, token: str | None = None) -> ApiKeyOut:
    return ApiKeyOut(
        id=key.id,
        name=key.name,
        hint=key.hint,
        permissions=sorted(key.permissions or []),
        rate_per_minute=key.rate_per_minute,
        allowed_ips=list(key.allowed_ips or []),
        member_name=member,
        expires_at=key.expires_at,
        previous_expires_at=key.previous_expires_at if key.previous_hash else None,
        last_used_at=key.last_used_at,
        last_used_ip=key.last_used_ip,
        created_at=key.created_at,
        revoked=key.revoked_at is not None,
        token=token,
    )


def _check_permissions(ctx: Ctx, wanted: list[str]) -> list[str]:
    grantable = ctx.permissions - catalog.owner_only()
    unknown = [p for p in wanted if p not in grantable]
    if unknown:
        raise Invalid(
            errors=[
                {"field": "permissions", "message": f"You can't give a key {', '.join(sorted(unknown))}."}
            ]
        )
    return sorted(set(wanted))


async def _member_name(ctx: Ctx, membership_id: uuid.UUID) -> str:
    name = await ctx.db.scalar(
        select(User.name)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.id == membership_id)
    )
    return name or ""


async def _load(ctx: Ctx, key_id: uuid.UUID) -> ApiKey:
    key = await ctx.db.scalar(select(ApiKey).where(ApiKey.id == key_id).with_for_update())
    if key is None:
        raise NotFound()
    return key


def _own_or_owner(ctx: Ctx, key: ApiKey) -> None:
    """Admins manage their own keys; the owner can manage (and revoke) anyone's."""
    if not ctx.is_owner and (ctx.membership is None or key.membership_id != ctx.membership.id):
        raise Forbidden(
            "Only the person who made this key, or the owner, can change it.", code="not_your_key"
        )


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_keys(ctx: Ctx = Developer) -> list[ApiKeyOut]:
    rows = (
        await ctx.db.execute(
            select(ApiKey, User.name)
            .join(Membership, Membership.id == ApiKey.membership_id)
            .join(User, User.id == Membership.user_id)
            .order_by(ApiKey.revoked_at.is_not(None), ApiKey.created_at.desc())
        )
    ).all()
    return [_key_out(key, name) for key, name in rows]


@router.post("/api-keys", response_model=ApiKeyOut, status_code=201)
async def create_key(body: ApiKeyIn, ctx: Ctx = Developer) -> ApiKeyOut:
    assert ctx.membership is not None
    granted = _check_permissions(ctx, body.permissions)
    token, secret = _token(ctx.tenant_id)
    key = ApiKey(
        name=body.name,
        hint=secret[:6],
        token_hash=hash_secret(secret),
        membership_id=ctx.membership.id,
        permissions=granted,
        rate_per_minute=body.rate_per_minute,
        allowed_ips=_cidrs(body.allowed_ips, "allowed_ips"),
        expires_at=utcnow() + timedelta(days=body.expires_in_days) if body.expires_in_days else None,
        created_by=ctx.user.id,
    )
    ctx.db.add(key)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "api_key.created",
        target_type="api_key",
        target_id=key.id,
        data={"name": key.name, "permissions": granted, "expires_at": key.expires_at},
    )
    await ctx.db.commit()
    return _key_out(key, ctx.user.name, token=token)


@router.patch("/api-keys/{key_id}", response_model=ApiKeyOut)
async def update_key(key_id: uuid.UUID, body: ApiKeyPatch, ctx: Ctx = Developer) -> ApiKeyOut:
    key = await _load(ctx, key_id)
    _own_or_owner(ctx, key)
    if key.revoked_at is not None:
        raise Invalid("This key was revoked.", code="api_key_revoked")
    changes: dict[str, object] = {}
    if body.name is not None:
        key.name = changes["name"] = body.name
    if body.permissions is not None:
        key.permissions = _check_permissions(ctx, body.permissions)
        changes["permissions"] = key.permissions
    if body.rate_per_minute is not None:
        key.rate_per_minute = changes["rate_per_minute"] = body.rate_per_minute
    if body.allowed_ips is not None:
        key.allowed_ips = _cidrs(body.allowed_ips, "allowed_ips")
        changes["allowed_ips"] = key.allowed_ips
    await audit.record(ctx.db, "api_key.updated", target_type="api_key", target_id=key.id, data=changes)
    await ctx.db.commit()
    return _key_out(key, await _member_name(ctx, key.membership_id))


class RotateIn(In):
    # How long the old secret keeps working (0 = stops now).
    grace_hours: int = Field(default=24, ge=0, le=GRACE_HOURS_MAX)


@router.post("/api-keys/{key_id}/rotate", response_model=ApiKeyOut)
async def rotate_key(key_id: uuid.UUID, body: RotateIn, ctx: Ctx = Developer) -> ApiKeyOut:
    key = await _load(ctx, key_id)
    _own_or_owner(ctx, key)
    if key.revoked_at is not None:
        raise Invalid("This key was revoked.", code="api_key_revoked")
    token, secret = _token(ctx.tenant_id)
    if body.grace_hours:
        key.previous_hash = key.token_hash
        key.previous_expires_at = utcnow() + timedelta(hours=body.grace_hours)
    else:
        key.previous_hash = key.previous_expires_at = None
    key.token_hash = hash_secret(secret)
    key.hint = secret[:6]
    await audit.record(
        ctx.db,
        "api_key.rotated",
        target_type="api_key",
        target_id=key.id,
        data={"grace_hours": body.grace_hours},
    )
    await ctx.db.commit()
    return _key_out(key, await _member_name(ctx, key.membership_id), token=token)


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_key(key_id: uuid.UUID, ctx: Ctx = Developer) -> None:
    key = await _load(ctx, key_id)
    _own_or_owner(ctx, key)
    if key.revoked_at is None:
        key.revoked_at = utcnow()
        key.previous_hash = key.previous_expires_at = None
        await audit.record(ctx.db, "api_key.revoked", target_type="api_key", target_id=key.id, data={})
        await ctx.db.commit()


class UsageDay(BaseModel):
    day: date
    requests: int
    writes: int


@router.get("/api-keys/{key_id}/usage", response_model=list[UsageDay])
async def key_usage(
    key_id: uuid.UUID, days: Annotated[int, Query(ge=1, le=90)] = 30, ctx: Ctx = Developer
) -> list[UsageDay]:
    if await ctx.db.get(ApiKey, key_id) is None:
        raise NotFound()
    since = utcnow().date() - timedelta(days=days - 1)
    rows = await ctx.db.scalars(
        select(ApiKeyUsage)
        .where(ApiKeyUsage.key_id == key_id, ApiKeyUsage.day >= since)
        .order_by(ApiKeyUsage.day)
    )
    return [UsageDay(day=r.day, requests=r.requests, writes=r.writes) for r in rows]


# ---- Network allowlist -------------------------------------------------------------------


class AllowlistIn(In):
    entries: Cidrs


class AllowlistOut(BaseModel):
    entries: list[str]
    # Where you are now, so you can add it.
    your_ip: str | None


@router.get("/workspace/ip-allowlist", response_model=AllowlistOut)
async def get_allowlist(ctx: Ctx = Depends(allow(DEVELOPERS_MANAGE))) -> AllowlistOut:
    assert ctx.tenant is not None
    return AllowlistOut(entries=list(ctx.tenant.ip_allowlist or []), your_ip=context.current().ip)


@router.put("/workspace/ip-allowlist", response_model=AllowlistOut)
async def set_allowlist(body: AllowlistIn, ctx: Ctx = Depends(allow(DEVELOPERS_MANAGE))) -> AllowlistOut:
    """Only the owner, only on plans with company sign-in, and never in a way that locks
    the owner out (where they are now must be on the list)."""
    people_only(ctx)
    if not ctx.is_owner:
        raise Forbidden("Only the workspace owner can change this.", code="owner_only")
    assert ctx.entitlements is not None
    if not ctx.entitlements.feature("sso"):
        raise PaymentRequired(
            "Network restrictions aren't included in this plan.", code="feature_not_in_plan"
        )
    entries = _cidrs(body.entries, "entries")
    ip = context.current().ip
    if entries and not ipnet.allowed(ip, entries):
        raise Invalid(
            errors=[
                {
                    "field": "entries",
                    "message": f"Add where you are now ({ip}) so you don't lock yourself out.",
                }
            ]
        )
    tenant = await ctx.db.scalar(select(Tenant).where(Tenant.id == ctx.tenant_id).with_for_update())
    assert tenant is not None
    before = list(tenant.ip_allowlist or [])
    tenant.ip_allowlist = entries
    await audit.record(
        ctx.db,
        "workspace.ip_allowlist_changed",
        target_type="workspace",
        target_id=tenant.id,
        data={"from": before, "to": entries},
    )
    await ctx.db.commit()
    return AllowlistOut(entries=entries, your_ip=ip)


# ---- Audit log export ----------------------------------------------------------------------

EXPORT_MAX = 100_000
EXPORT_COLUMNS = (
    "seq",
    "occurred_at",
    "actor_user_id",
    "actor_name",
    "action",
    "target_type",
    "target_id",
    "data",
    "ip",
    "request_id",
    "prev_hash",
    "hash",
)


@router.get("/audit/export", response_class=Response)
async def export_audit(
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to")],
    format: Annotated[str, Query(pattern="^(csv|jsonl)$")] = "jsonl",
    ctx: Ctx = Depends(allow(AUDIT_VIEW)),
) -> Response:
    """The audit log for a date range (UTC), with each entry's hash and the one before it,
    so the chain can be checked outside the app or fed to a SIEM."""
    if end < start or (end - start).days > 366:
        raise Invalid("Choose up to a year.", code="range_too_long")
    rows = (
        await ctx.db.execute(
            select(audit.AuditEvent, User.name)
            .outerjoin(User, User.id == audit.AuditEvent.actor_user_id)
            .where(
                audit.AuditEvent.occurred_at >= datetime.combine(start, datetime.min.time(), tzinfo=UTC),
                audit.AuditEvent.occurred_at
                < datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=UTC),
            )
            .order_by(audit.AuditEvent.seq)
            .limit(EXPORT_MAX + 1)
        )
    ).all()
    if len(rows) > EXPORT_MAX:
        raise Invalid("Too many entries; choose a shorter range.", code="range_too_long")
    records = [
        {
            "seq": e.seq,
            "occurred_at": e.occurred_at.isoformat(),
            "actor_user_id": str(e.actor_user_id) if e.actor_user_id else None,
            "actor_name": e.actor_label or name,
            "action": e.action,
            "target_type": e.target_type,
            "target_id": e.target_id,
            "data": e.data,
            "ip": e.ip,
            "request_id": e.request_id,
            "prev_hash": e.prev_hash,
            "hash": e.hash,
        }
        for e, name in rows
    ]
    await audit.record(
        ctx.db, "audit.exported", data={"from": start, "to": end, "format": format, "entries": len(records)}
    )
    await ctx.db.commit()
    filename = f"audit-{start}-{end}.{format}"
    if format == "jsonl":
        body = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records)
        media = "application/x-ndjson"
    else:
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(EXPORT_COLUMNS)
        for r in records:
            writer.writerow(
                [
                    safe_cell(
                        json.dumps(r[c], ensure_ascii=False, sort_keys=True) if c == "data" else r[c] or ""
                    )
                    for c in EXPORT_COLUMNS
                ]
            )
        body, media = out.getvalue(), "text/csv"
    return Response(
        content=body.encode(),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---- Sandbox ---------------------------------------------------------------------------------


class SandboxOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


@router.post("/workspace/sandbox", response_model=SandboxOut, status_code=201)
async def create_sandbox(ctx: Ctx = Developer) -> SandboxOut:
    """A separate workspace to try the API, webhooks and integrations without touching
    real data. Same plan features, never billed, one per workspace; you're its owner.
    Switch to it from the workspace menu; delete it like any workspace."""
    if not ctx.is_owner:
        raise Forbidden("Only the workspace owner can make a sandbox.", code="owner_only")
    tenant = ctx.tenant
    assert tenant is not None
    assert ctx.entitlements is not None
    if tenant.sandbox_of is not None:
        raise Invalid("This is already a sandbox.", code="sandbox_of_sandbox")
    existing = await ctx.db.scalar(
        select(func.count())
        .select_from(Tenant)
        .where(Tenant.sandbox_of == tenant.id, Tenant.status == "active")
    )
    if existing:
        raise Conflict("This workspace already has a sandbox.", code="sandbox_exists")
    plan_key = ctx.entitlements.plan.key
    modules = sorted(ctx.entitlements.modules | ctx.entitlements.locked_modules)
    parent_id = tenant.id
    sandbox = await workspaces.create_workspace(
        ctx.db,
        ctx.user,
        name=f"{tenant.name} (sandbox)"[:120],
        business_type=tenant.business_type,
        country=tenant.country,
        timezone=tenant.timezone,
        currency=tenant.currency,
        locale=tenant.locale,
    )
    sandbox.sandbox_of = parent_id
    subscription = await ctx.db.scalar(select(Subscription).where(Subscription.tenant_id == sandbox.id))
    assert subscription is not None
    subscription.plan_key, subscription.status = plan_key, "active"
    subscription.trial_plan_key = subscription.trial_ends_at = None
    subscription.modules = [m for m in modules if not catalog.MODULES[m].core]
    await audit.record(
        ctx.db,
        "workspace.sandbox_created",
        target_type="workspace",
        target_id=sandbox.id,
        data={"from": str(parent_id)},
    )
    await ctx.db.commit()
    return SandboxOut(id=sandbox.id, name=sandbox.name, slug=sandbox.slug)
