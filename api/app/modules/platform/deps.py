"""Who is calling, in which workspace, and what they may do.

Every route depends on exactly one of:
- `public()`: no sign-in needed (marked so the route audit test can tell it's deliberate),
- `signed_in()`: any signed-in user, workspace optional,
- `allow(permission, module=...)`: a member of the current workspace holding `permission`.

API keys (`Authorization: Bearer cmk_...`) work on `allow()` routes only: they act as the
member who made them, limited to the permissions chosen for the key. Account routes
(`signed_in()`) refuse them.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, Request
from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import context, ipnet, ratelimit
from app.core.db import get_db, set_tenant
from app.core.errors import Forbidden, Gone, PaymentRequired, TooManyRequests, Unauthorized
from app.core.security.tokens import decode_access_token, hash_secret
from app.modules.platform import catalog
from app.modules.platform.models import (
    ApiKey,
    ApiKeyUsage,
    AuthSession,
    Membership,
    Plan,
    Role,
    Subscription,
    Tenant,
    User,
)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# A deleted workspace can be restored by its owner for this long, then it's purged.
DELETION_GRACE = timedelta(days=30)
ADMIN_ROLES = ("owner", "admin")
LAST_SEEN_EVERY = timedelta(minutes=5)
API_KEY_PREFIX = "cmk_"


@dataclass
class Entitlements:
    plan: Plan
    status: str
    modules: frozenset[str]
    # Switched on but over the plan's limit: readable, not writable.
    locked_modules: frozenset[str]
    trial_ends_at: datetime | None = None

    @property
    def read_only(self) -> bool:
        return self.status in ("read_only", "canceled")

    def feature(self, key: str) -> Any:
        return (self.plan.features or {}).get(key)


@dataclass
class Ctx:
    db: AsyncSession
    user: User
    session: AuthSession
    method: str = "GET"
    tenant: Tenant | None = None
    membership: Membership | None = None
    role: Role | None = None
    permissions: frozenset[str] = frozenset()
    entitlements: Entitlements | None = None
    cache: dict[str, Any] = field(default_factory=dict)
    # Set when the caller used an API key rather than signing in.
    api_key: ApiKey | None = None

    @property
    def tenant_id(self) -> uuid.UUID:
        if self.tenant is None:
            raise Forbidden("Choose a workspace first.", code="no_workspace")
        return self.tenant.id

    def can(self, permission: str) -> bool:
        return permission in self.permissions

    def require(self, permission: str) -> None:
        if not self.can(permission):
            raise Forbidden()

    @property
    def is_owner(self) -> bool:
        return self.role is not None and self.role.is_builtin and self.role.key == "owner"

    @property
    def scope_department_id(self) -> uuid.UUID | None:
        """Scoped permissions apply only inside this department's subtree (None = all)."""
        return self.membership.scope_department_id if self.membership else None


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


async def load_entitlements(db: AsyncSession, tenant_id: uuid.UUID) -> Entitlements:
    sub = await db.scalar(select(Subscription).where(Subscription.tenant_id == tenant_id))
    if sub is None:
        raise Forbidden("This workspace has no plan.", code="no_plan")
    now = datetime.now(UTC)
    plan_key = sub.plan_key
    status = sub.status
    if sub.status == "trialing" and sub.trial_plan_key:
        if sub.trial_ends_at and sub.trial_ends_at > now:
            plan_key = sub.trial_plan_key
        else:
            status = "active"
    plan = await db.get(Plan, plan_key)
    assert plan is not None
    optional = [m for m in sub.modules if m in catalog.MODULES and not catalog.MODULES[m].core]
    limit = plan.max_modules
    allowed = optional if limit is None else optional[:limit]
    core = {k for k, m in catalog.MODULES.items() if m.core}
    return Entitlements(
        plan=plan,
        status=status,
        modules=frozenset(core | set(allowed)),
        locked_modules=frozenset(set(optional) - set(allowed)),
        trial_ends_at=sub.trial_ends_at if status == "trialing" else None,
    )


def parse_api_key(token: str) -> tuple[uuid.UUID, str] | None:
    """`cmk_<workspace id>_<secret>` -> (workspace id, secret)."""
    if not token.startswith(API_KEY_PREFIX):
        return None
    workspace, _, secret = token[len(API_KEY_PREFIX) :].partition("_")
    try:
        tenant_id = uuid.UUID(hex=workspace)
    except ValueError:
        return None
    if len(secret) < 20 or len(secret) > 100:
        return None
    return tenant_id, secret


async def _authenticate_key(request: Request, db: AsyncSession, token: str) -> Ctx:
    parsed = parse_api_key(token)
    if parsed is None:
        raise Unauthorized(code="api_key_invalid")
    tenant_id, secret = parsed
    await set_tenant(db, tenant_id)
    digest = hash_secret(secret)
    now = datetime.now(UTC)
    key = await db.scalar(
        select(ApiKey).where(
            or_(
                ApiKey.token_hash == digest,
                and_(ApiKey.previous_hash == digest, ApiKey.previous_expires_at > now),
            )
        )
    )
    if key is None or key.revoked_at is not None or (key.expires_at and key.expires_at <= now):
        raise Unauthorized("This API key isn't valid.", code="api_key_invalid")
    ip = context.current().ip
    if not ipnet.allowed(ip, list(key.allowed_ips or [])):
        raise Forbidden("This API key can't be used from this address.", code="ip_not_allowed")
    allowed, _, retry = await ratelimit.hit(ratelimit.Rule("api-key", key.rate_per_minute, 60), str(key.id))
    if not allowed:
        raise TooManyRequests(headers={"Retry-After": str(max(retry, 1))})
    membership = await db.scalar(select(Membership).where(Membership.id == key.membership_id))
    user = await db.get(User, membership.user_id) if membership else None
    if membership is None or membership.status != "active" or user is None or user.disabled_at:
        raise Unauthorized("The member this key belongs to has left.", code="api_key_owner_gone")
    writing = request.method not in SAFE_METHODS
    await db.execute(
        insert(ApiKeyUsage)
        .values(tenant_id=tenant_id, key_id=key.id, day=now.date(), requests=1, writes=int(writing))
        .on_conflict_do_update(
            index_elements=["key_id", "day"],
            set_={
                "requests": ApiKeyUsage.requests + 1,
                "writes": ApiKeyUsage.writes + int(writing),
            },
        )
    )
    if key.last_used_at is None or now - key.last_used_at > timedelta(minutes=1) or key.last_used_ip != ip:
        key.last_used_at, key.last_used_ip = now, ip
    await db.commit()
    info = context.current()
    info.user_id = user.id
    info.extra["api_key"] = str(key.id)
    # A stand-in session, never saved: API keys don't sign in.
    session = AuthSession(user_id=user.id, tenant_id=tenant_id, expires_at=now)
    return Ctx(db=db, user=user, session=session, method=request.method, api_key=key)


async def _authenticate(request: Request, db: AsyncSession) -> Ctx:
    token = _bearer(request)
    if token and token.startswith(API_KEY_PREFIX):
        return await _authenticate_key(request, db, token)
    claims = decode_access_token(token) if token else None
    if claims is None:
        raise Unauthorized()
    row = (
        await db.execute(
            select(AuthSession, User)
            .join(User, User.id == AuthSession.user_id)
            .where(AuthSession.id == claims.session_id)
        )
    ).first()
    now = datetime.now(UTC)
    if row is None:
        raise Unauthorized()
    session, user = row
    if (
        session.user_id != claims.user_id
        or session.revoked_at is not None
        or session.expires_at <= now
        or user.disabled_at is not None
        or session.tenant_id != claims.tenant_id
    ):
        raise Unauthorized(code="session_ended")
    if now - session.last_seen_at > LAST_SEEN_EVERY:
        await db.execute(update(AuthSession).where(AuthSession.id == session.id).values(last_seen_at=now))
        await db.commit()
    info = context.current()
    info.user_id = user.id
    return Ctx(db=db, user=user, session=session, method=request.method)


async def _bind_workspace(ctx: Ctx) -> None:
    tenant_id = ctx.session.tenant_id
    if tenant_id is None:
        raise Forbidden("Choose a workspace first.", code="no_workspace")
    tenant = await ctx.db.get(Tenant, tenant_id)
    if tenant is None:
        raise Unauthorized(code="session_ended")
    if tenant.status == "deleting":
        raise Gone(
            "This workspace is scheduled for deletion.",
            code="workspace_deleted",
            extra={"purge_after": ((tenant.deletion_requested_at or now_utc()) + DELETION_GRACE).isoformat()},
        )
    await set_tenant(ctx.db, tenant_id, ctx.user.id)
    row = (
        await ctx.db.execute(
            select(Membership, Role)
            .join(Role, (Role.tenant_id == Membership.tenant_id) & (Role.id == Membership.role_id))
            .where(Membership.user_id == ctx.user.id)
        )
    ).first()
    if row is None or row[0].status != "active":
        raise Forbidden("You're no longer a member of this workspace.", code="not_member")
    membership, role = row
    if not ipnet.allowed(context.current().ip, list(tenant.ip_allowlist or [])):
        raise Forbidden("This workspace can only be used from its company network.", code="ip_not_allowed")
    if (
        tenant.sso_enforced
        and ctx.api_key is None
        and ctx.session.method != "sso"
        and ctx.user.email
        and not (role.is_builtin and role.key == "owner")
    ):
        raise Forbidden(
            "This workspace signs in with your company account.",
            code="sso_required",
        )
    ctx.tenant = tenant
    ctx.membership = membership
    ctx.role = role
    ctx.permissions = catalog.resolve(role.key, role.is_builtin, list(role.permissions or []))
    ctx.entitlements = await load_entitlements(ctx.db, tenant_id)
    if ctx.api_key is not None:
        if not ctx.entitlements.feature("api"):
            raise PaymentRequired("API access isn't included in this plan.", code="api_not_in_plan")
        if ctx.api_key.membership_id != membership.id:
            raise Unauthorized(code="api_key_invalid")
        # Never more than the member has now; never owner-only powers.
        ctx.permissions = ctx.permissions & frozenset(ctx.api_key.permissions or []) - catalog.owner_only()
    info = context.current()
    info.tenant_id = tenant_id
    info.membership_id = membership.id


async def member_ctx(db: AsyncSession, tenant: Tenant, membership: Membership) -> Ctx:
    """A context for scheduled work done for a member, outside any request: the same
    permissions, department scope and modules they would have in the app. The session is
    a stand-in that is never saved."""
    await set_tenant(db, tenant.id, membership.user_id)
    user = await db.get(User, membership.user_id)
    role = await db.scalar(select(Role).where(Role.id == membership.role_id))
    assert user is not None
    assert role is not None
    return Ctx(
        db=db,
        user=user,
        session=AuthSession(user_id=user.id, tenant_id=tenant.id),
        tenant=tenant,
        membership=membership,
        role=role,
        permissions=catalog.resolve(role.key, role.is_builtin, list(role.permissions or [])),
        entitlements=await load_entitlements(db, tenant.id),
    )


def now_utc() -> datetime:
    return datetime.now(UTC)


def needs_mfa(ctx: Ctx) -> bool:
    """An owner or admin without two-step verification, in a workspace that requires it."""
    return bool(
        ctx.tenant is not None
        and ctx.tenant.require_admin_mfa
        and ctx.role is not None
        and ctx.role.is_builtin
        and ctx.role.key in ADMIN_ROLES
        and ctx.user.totp_enabled_at is None
    )


def check_access(ctx: Ctx, permission: str | None, *, module: str | None, writing: bool) -> None:
    """Everything a workspace call must pass: the module is on (and writable on this plan),
    the workspace isn't read-only, two-step verification when required, the permission.
    Shared by REST routes and capabilities, so both enforce exactly the same rules."""
    assert ctx.entitlements is not None
    if module is not None:
        if module in ctx.entitlements.locked_modules:
            if writing:
                raise PaymentRequired(
                    "Your plan has more modules switched on than it includes. "
                    "This one is read-only until you upgrade or switch another off.",
                    code="module_over_limit",
                )
        elif module not in ctx.entitlements.modules:
            raise PaymentRequired("This module is switched off.", code="module_off")
    if writing and ctx.entitlements.read_only:
        raise PaymentRequired(
            "This workspace is read-only. You can still view and export your data.",
            code="workspace_read_only",
        )
    if needs_mfa(ctx):
        raise Forbidden(
            "This workspace asks owners and admins to turn on two-step verification first.",
            code="mfa_setup_required",
        )
    if permission is not None:
        ctx.require(permission)


# ---- Dependencies used by routes -------------------------------------------------------

Dep = Callable[..., Awaitable[Ctx | None]]


def _no_api_key(ctx: Ctx) -> None:
    if ctx.api_key is not None:
        raise Forbidden("API keys can't be used for account settings.", code="api_key_not_allowed")


def people_only(ctx: Ctx) -> None:
    """For routes only a person may use (managing API keys, security settings)."""
    _no_api_key(ctx)


def public() -> Callable[[], Awaitable[None]]:
    async def dep() -> None:
        return None

    dep._access = "public"  # type: ignore[attr-defined]
    return dep


def signed_in(
    *, allow_password_change: bool = True, allow_deleted_workspace: bool = False
) -> Callable[..., Awaitable[Ctx]]:
    """`allow_deleted_workspace`: a session pointing at a workspace scheduled for deletion
    still works, without the workspace (so people can see what happened and restore it)."""

    async def dep(request: Request, db: AsyncSession = Depends(get_db)) -> Ctx:
        ctx = await _authenticate(request, db)
        _no_api_key(ctx)
        if ctx.user.must_change_password and not allow_password_change:
            raise Forbidden("Please set a new password first.", code="password_change_required")
        if ctx.session.tenant_id is not None:
            try:
                await _bind_workspace(ctx)
            except Gone:
                if not allow_deleted_workspace:
                    raise
                ctx.cache["pending_deletion"] = ctx.session.tenant_id
        return ctx

    dep._access = "signed_in"  # type: ignore[attr-defined]
    return dep


def allow(permission: str | None, *, module: str | None = None) -> Callable[..., Awaitable[Ctx]]:
    """A workspace member. `permission=None` means any member (e.g. clocking yourself in)."""

    async def dep(request: Request, db: AsyncSession = Depends(get_db)) -> Ctx:
        ctx = await _authenticate(request, db)
        if ctx.user.must_change_password:
            raise Forbidden("Please set a new password first.", code="password_change_required")
        await _bind_workspace(ctx)
        check_access(ctx, permission, module=module, writing=request.method not in SAFE_METHODS)
        return ctx

    dep._access = "workspace"  # type: ignore[attr-defined]
    dep._permission = permission  # type: ignore[attr-defined]
    return dep


def owner_of_deleted_workspace() -> Callable[..., Awaitable[Ctx]]:
    """The owner of the workspace this session points at, while it waits to be purged
    (every other route refuses a workspace scheduled for deletion)."""

    async def dep(request: Request, db: AsyncSession = Depends(get_db)) -> Ctx:
        ctx = await _authenticate(request, db)
        _no_api_key(ctx)
        tenant = await db.get(Tenant, ctx.session.tenant_id) if ctx.session.tenant_id else None
        if tenant is None or tenant.status != "deleting":
            raise Forbidden("This workspace isn't scheduled for deletion.", code="not_deleting")
        await set_tenant(db, tenant.id, ctx.user.id)
        row = (
            await db.execute(
                select(Membership, Role)
                .join(Role, (Role.tenant_id == Membership.tenant_id) & (Role.id == Membership.role_id))
                .where(Membership.user_id == ctx.user.id, Membership.status == "active")
            )
        ).first()
        if row is None or not (row[1].is_builtin and row[1].key == "owner"):
            raise Forbidden("Only the owner can restore this workspace.")
        ctx.tenant, ctx.membership, ctx.role = tenant, row[0], row[1]
        info = context.current()
        info.tenant_id = tenant.id
        info.membership_id = row[0].id
        return ctx

    dep._access = "workspace"  # type: ignore[attr-defined]
    dep._permission = catalog.WORKSPACE_DELETE  # type: ignore[attr-defined]
    return dep
