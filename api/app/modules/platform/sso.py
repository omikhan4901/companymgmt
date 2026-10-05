"""Sign in with the company account (OpenID Connect).

Works with any OpenID Connect provider: Google Workspace, Microsoft Entra ID, Okta,
Auth0, JumpCloud, Keycloak. The workspace owner enters the provider's issuer address, a
client id and secret, and the company's email domains.

The flow (authorization code with PKCE, a one-time state and a nonce):
1. `POST /v1/sso/start` with the workspace address: we return the provider's sign-in URL.
2. The provider sends the person back to `<web>/sso/callback?code&state`; that page calls
   `POST /v1/sso/callback`, which swaps the code for an ID token over a server-to-server
   call, checks its signature (the provider's published keys), issuer, audience, expiry
   and nonce, and signs the person in.

People are matched by verified email. With auto-join on, people from the company's
domains who aren't members yet join with the default role. With "require" on, everyone
except the owner and staff without an email must sign in this way (checked on every
request, so it applies to sessions that were already open).

Provider addresses are fetched through `safehttp` (public HTTPS only).
"""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Any
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit, context, ratelimit, safehttp
from app.core.config import get_settings
from app.core.db import get_db, set_tenant
from app.core.errors import Forbidden, Invalid, NotFound, PaymentRequired, Unauthorized
from app.core.http import check_if_match
from app.core.schema import In
from app.core.security import crypto
from app.core.security.tokens import hash_secret
from app.core.time import utcnow
from app.modules.platform import catalog, hooks
from app.modules.platform.catalog import DEVELOPERS_MANAGE
from app.modules.platform.deps import Ctx, allow, people_only, public
from app.modules.platform.models import Membership, Role, SsoConnection, SsoState, Tenant, User
from app.modules.platform.routes_auth import TokenOut, _check_origin, _tokens
from app.modules.platform.tokens import log_event, start_session

router = APIRouter(prefix="/v1/sso", tags=["sso"])

STATE_MINUTES = 10
PROVIDER_REFRESH = timedelta(hours=24)
# Asymmetric algorithms only: never "none" or a shared secret.
ALGORITHMS = ("RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "EdDSA")
LEEWAY = 60
DOMAIN = re.compile(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+")


class SsoError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _seal_context(tenant_id: uuid.UUID) -> str:
    return f"sso:{tenant_id}"


def redirect_uri() -> str:
    return f"{get_settings().web_base_url.rstrip('/')}/sso/callback"


def _domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower()


async def discover(issuer: str) -> dict[str, Any]:
    """The provider's published settings, checked to belong to `issuer`."""
    url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    try:
        meta = await safehttp.get_json(url)
    except (safehttp.UnsafeAddress, httpx.HTTPError, ValueError) as exc:
        raise SsoError(f"Couldn't read the provider's settings from {url}.") from exc
    if not isinstance(meta, dict) or meta.get("issuer", "").rstrip("/") != issuer.rstrip("/"):
        raise SsoError("The provider's settings name a different issuer.")
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        value = meta.get(key)
        if not isinstance(value, str):
            raise SsoError(f"The provider's settings don't include {key}.")
        safehttp.check_url(value)
    keep = (
        "issuer",
        "authorization_endpoint",
        "token_endpoint",
        "jwks_uri",
        "token_endpoint_auth_methods_supported",
    )
    return {k: meta[k] for k in keep if k in meta}


async def _provider(db: AsyncSession, connection: SsoConnection) -> dict[str, Any]:
    fresh = connection.provider_fetched_at and utcnow() - connection.provider_fetched_at < PROVIDER_REFRESH
    if connection.provider and fresh:
        return connection.provider
    connection.provider = await discover(connection.issuer)
    connection.provider_fetched_at = utcnow()
    await db.flush()
    return connection.provider


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


# ---- Signing in ------------------------------------------------------------------------


class StartIn(In):
    workspace: Annotated[
        str, StringConstraints(min_length=3, max_length=40, to_lower=True, strip_whitespace=True)
    ]
    # Where to go in the app afterwards (a path, not an address).
    next: Annotated[str | None, StringConstraints(max_length=200, pattern=r"^/[A-Za-z0-9/_\-?=&.]*$")] = None


class StartOut(BaseModel):
    url: str


async def _connection_for(db: AsyncSession, slug: str) -> tuple[Tenant, SsoConnection]:
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == slug, Tenant.status == "active"))
    if tenant is None:
        raise NotFound()
    await set_tenant(db, tenant.id)
    connection = await db.get(SsoConnection, tenant.id)
    if connection is None or not connection.enabled:
        raise NotFound("This workspace doesn't use company sign-in.", code="sso_off")
    return tenant, connection


@router.post("/start", response_model=StartOut)
async def start(body: StartIn, db: AsyncSession = Depends(get_db), _: None = Depends(public())) -> StartOut:
    await ratelimit.enforce(ratelimit.LOGIN_IP, context.current().ip or "unknown")
    tenant, connection = await _connection_for(db, body.workspace)
    try:
        provider = await _provider(db, connection)
    except SsoError as exc:
        raise Invalid(exc.message, code="sso_provider_error") from exc
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    db.add(
        SsoState(
            state_hash=hash_secret(state),
            tenant_id=tenant.id,
            nonce=nonce,
            verifier=verifier,
            next_path=body.next,
            expires_at=utcnow() + timedelta(minutes=STATE_MINUTES),
        )
    )
    await db.commit()
    query = urlencode(
        {
            "response_type": "code",
            "client_id": connection.client_id,
            "redirect_uri": redirect_uri(),
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": _challenge(verifier),
            "code_challenge_method": "S256",
        }
    )
    endpoint = provider["authorization_endpoint"]
    return StartOut(url=f"{endpoint}{'&' if '?' in endpoint else '?'}{query}")


async def exchange(connection: SsoConnection, provider: dict[str, Any], code: str, verifier: str) -> str:
    """Swap the code for an ID token (server to server)."""
    secret = crypto.decrypt(connection.client_secret_enc, context=_seal_context(connection.tenant_id))
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(),
        "code_verifier": verifier,
    }
    methods = provider.get("token_endpoint_auth_methods_supported") or ["client_secret_basic"]
    kwargs: dict[str, Any] = {"headers": {"Accept": "application/json"}}
    if "client_secret_basic" in methods:
        kwargs["auth"] = (connection.client_id, secret)
    else:
        form |= {"client_id": connection.client_id, "client_secret": secret}
    try:
        response = await safehttp.request("POST", provider["token_endpoint"], data=form, **kwargs)
        data = response.json() if response.status_code == 200 else {}
    except (safehttp.UnsafeAddress, httpx.HTTPError, ValueError) as exc:
        raise SsoError("Couldn't reach the sign-in provider.") from exc
    token = data.get("id_token") if isinstance(data, dict) else None
    if not isinstance(token, str):
        raise SsoError("The sign-in provider didn't confirm who you are.")
    return token


async def verify_id_token(
    connection: SsoConnection, provider: dict[str, Any], token: str, nonce: str
) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise SsoError("The sign-in provider sent something unreadable.") from exc
    algorithm = header.get("alg")
    if algorithm not in ALGORITHMS:
        raise SsoError("The sign-in provider used a signature we don't accept.")
    try:
        keys = jwt.PyJWKSet.from_dict(await safehttp.get_json(provider["jwks_uri"]))
    except (safehttp.UnsafeAddress, httpx.HTTPError, ValueError, jwt.PyJWTError) as exc:
        raise SsoError("Couldn't read the sign-in provider's keys.") from exc
    kid = header.get("kid")
    candidates = [k for k in keys.keys if kid is None or k.key_id == kid]
    if not candidates:
        raise SsoError("The sign-in provider used a key it doesn't publish.")
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            candidates[0].key,
            algorithms=[algorithm],
            audience=connection.client_id,
            issuer=provider["issuer"],
            leeway=LEEWAY,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise SsoError("The sign-in couldn't be confirmed. Try again.") from exc
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise SsoError("The sign-in couldn't be confirmed. Try again.")
    return claims


class CallbackIn(In):
    state: Annotated[str, StringConstraints(min_length=20, max_length=200)]
    code: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class CallbackOut(TokenOut):
    next: str | None = None


async def _person(
    db: AsyncSession, connection: SsoConnection, claims: dict[str, Any]
) -> tuple[User, Membership]:
    """The member this sign-in is for (made now when auto-join allows)."""
    email = str(claims.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise SsoError("Your company account has no email address.")
    if claims.get("email_verified") is False:
        raise SsoError("Your company account's email address isn't verified.")
    if _domain(email) not in (connection.domains or []):
        raise SsoError("Your email address isn't one of this company's domains.")
    user = await db.scalar(
        select(User).where(func.lower(User.email) == email, User.managed_tenant_id.is_(None))
    )
    if user is not None and user.disabled_at is not None:
        raise SsoError("This account is switched off.")
    membership = (
        await db.scalar(select(Membership).where(Membership.user_id == user.id)) if user is not None else None
    )
    if membership is not None and membership.status != "active":
        raise SsoError("You're no longer a member of this workspace.")
    if membership is not None and user is not None:
        return user, membership
    if not connection.auto_join:
        raise SsoError("You're not a member of this workspace yet. Ask an admin to invite you.")
    role = await _default_role(db, connection)
    now = utcnow()
    if user is None:
        name = str(claims.get("name") or email.split("@", 1)[0])[:120]
        user = User(email=email, email_verified_at=now, name=name, locale="en")
        db.add(user)
        await db.flush()
    elif user.email_verified_at is None:
        user.email_verified_at = now
    membership = Membership(user_id=user.id, role_id=role.id)
    db.add(membership)
    await db.flush()
    await hooks.run(hooks.member_joined, db, membership, user)
    await audit.record(
        db,
        "member.joined_by_sso",
        target_type="member",
        target_id=membership.id,
        data={"email": email, "role": role.key},
        actor_user_id=user.id,
    )
    return user, membership


async def _default_role(db: AsyncSession, connection: SsoConnection) -> Role:
    role = await db.get(Role, connection.default_role_id) if connection.default_role_id else None
    if role is None or (role.is_builtin and role.key == "owner"):
        role = await db.scalar(
            select(Role).where(Role.is_builtin.is_(True), Role.key == catalog.DEFAULT_ROLE)
        )
    assert role is not None
    return role


@router.post("/callback", response_model=CallbackOut)
async def callback(
    body: CallbackIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(public()),
) -> CallbackOut:
    _check_origin(request)
    await ratelimit.enforce(ratelimit.LOGIN_IP, context.current().ip or "unknown")
    state = await db.scalar(
        select(SsoState).where(SsoState.state_hash == hash_secret(body.state)).with_for_update()
    )
    if state is None or state.used_at is not None or state.expires_at <= utcnow():
        raise Unauthorized("This sign-in link expired. Start again.", code="sso_state_invalid")
    state.used_at = utcnow()
    await db.commit()
    # Plain values: a rollback below would expire the row.
    tenant_id, nonce, verifier, next_path = state.tenant_id, state.nonce, state.verifier, state.next_path
    await set_tenant(db, tenant_id)
    connection = await db.get(SsoConnection, tenant_id)
    if connection is None or not connection.enabled:
        raise Unauthorized(code="sso_off")
    try:
        provider = await _provider(db, connection)
        token = await exchange(connection, provider, body.code, verifier)
        claims = await verify_id_token(connection, provider, token, nonce)
        user, _membership = await _person(db, connection, claims)
    except SsoError as exc:
        await db.rollback()
        log_event(db, None, "sso.failed", tenant=str(tenant_id), reason=exc.message)
        await db.commit()
        raise Unauthorized(exc.message, code="sso_failed") from exc
    await set_tenant(db, tenant_id, user.id)
    # The provider checked who they are (and their second step, if it asks for one).
    issued = await start_session(db, user, tenant_id, mfa=True, method="sso")
    log_event(db, user.id, "sso.signed_in", tenant=str(tenant_id), subject=str(claims.get("sub")))
    tokens = await _tokens(db, response, issued)
    return CallbackOut(**tokens.model_dump(), next=next_path)


# ---- Settings -------------------------------------------------------------------------


class SsoIn(In):
    issuer: Annotated[str, StringConstraints(min_length=10, max_length=300, strip_whitespace=True)]
    client_id: Annotated[str, StringConstraints(min_length=1, max_length=300, strip_whitespace=True)]
    # Leave out to keep the saved one.
    client_secret: Annotated[str | None, StringConstraints(min_length=1, max_length=500)] = None
    domains: list[Annotated[str, StringConstraints(min_length=3, max_length=253)]] = Field(
        min_length=1, max_length=20
    )
    enabled: bool = True
    auto_join: bool = False
    default_role_id: uuid.UUID | None = None
    # Everyone except the owner and staff without an email must sign in this way.
    enforce: bool = False


class SsoOut(BaseModel):
    issuer: str
    client_id: str
    domains: list[str]
    enabled: bool
    auto_join: bool
    default_role_id: uuid.UUID | None
    enforce: bool
    redirect_uri: str
    provider_checked_at: datetime | None
    version: int


def _out(connection: SsoConnection, tenant: Tenant) -> SsoOut:
    return SsoOut(
        issuer=connection.issuer,
        client_id=connection.client_id,
        domains=list(connection.domains or []),
        enabled=connection.enabled,
        auto_join=connection.auto_join,
        default_role_id=connection.default_role_id,
        enforce=tenant.sso_enforced,
        redirect_uri=redirect_uri(),
        provider_checked_at=connection.provider_fetched_at,
        version=connection.version,
    )


class SsoSetupOut(BaseModel):
    """What to enter at the provider before saving."""

    redirect_uri: str
    connection: SsoOut | None


async def sso_admin(ctx: Ctx = Depends(allow(DEVELOPERS_MANAGE))) -> Ctx:
    people_only(ctx)
    assert ctx.entitlements is not None
    if not ctx.entitlements.feature("sso"):
        raise PaymentRequired("Company sign-in isn't included in this plan.", code="feature_not_in_plan")
    return ctx


sso_admin._access = "workspace"  # type: ignore[attr-defined]
sso_admin._permission = DEVELOPERS_MANAGE  # type: ignore[attr-defined]


@router.get("/settings", response_model=SsoSetupOut)
async def get_settings_(ctx: Ctx = Depends(sso_admin)) -> SsoSetupOut:
    assert ctx.tenant is not None
    connection = await ctx.db.get(SsoConnection, ctx.tenant_id)
    return SsoSetupOut(
        redirect_uri=redirect_uri(), connection=_out(connection, ctx.tenant) if connection else None
    )


def _domains(values: list[str]) -> list[str]:
    out = []
    for value in values:
        domain = value.strip().lower().lstrip("@")
        if not DOMAIN.fullmatch(domain):
            raise Invalid(errors=[{"field": "domains", "message": f"{value!r} isn't a domain."}])
        out.append(domain)
    return sorted(set(out))


@router.put("/settings", response_model=SsoOut)
async def save_settings(body: SsoIn, request: Request, ctx: Ctx = Depends(sso_admin)) -> SsoOut:
    """Owner only: a mistake here can lock people out. The provider is checked before saving."""
    if not ctx.is_owner:
        raise Forbidden("Only the workspace owner can change company sign-in.", code="owner_only")
    try:
        issuer = safehttp.check_url(body.issuer).rstrip("/")
        provider = await discover(issuer)
    except safehttp.UnsafeAddress as exc:
        raise Invalid(errors=[{"field": "issuer", "message": str(exc)}]) from exc
    except SsoError as exc:
        raise Invalid(errors=[{"field": "issuer", "message": exc.message}]) from exc
    if body.default_role_id is not None:
        role = await ctx.db.get(Role, body.default_role_id)
        if role is None or (role.is_builtin and role.key == "owner"):
            raise Invalid(errors=[{"field": "default_role_id", "message": "Choose a role other than owner."}])
    connection = await ctx.db.scalar(select(SsoConnection).with_for_update())
    if connection is not None:
        check_if_match(request, connection.version)
    elif body.client_secret is None:
        raise Invalid(errors=[{"field": "client_secret", "message": "Enter the client secret."}])
    if connection is None:
        connection = SsoConnection(tenant_id=ctx.tenant_id, version=0)
        ctx.db.add(connection)
    connection.issuer = issuer
    connection.client_id = body.client_id
    if body.client_secret is not None:
        connection.client_secret_enc = crypto.encrypt(
            body.client_secret, context=_seal_context(ctx.tenant_id)
        )
    connection.domains = _domains(body.domains)
    connection.enabled = body.enabled
    connection.auto_join = body.auto_join
    connection.default_role_id = body.default_role_id
    connection.provider, connection.provider_fetched_at = provider, utcnow()
    connection.version = (connection.version or 0) + 1
    tenant = await ctx.db.scalar(select(Tenant).where(Tenant.id == ctx.tenant_id).with_for_update())
    assert tenant is not None
    tenant.sso_enforced = body.enforce and body.enabled
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "sso.settings_changed",
        target_type="workspace",
        target_id=ctx.tenant_id,
        data={
            "issuer": issuer,
            "domains": connection.domains,
            "enabled": connection.enabled,
            "auto_join": connection.auto_join,
            "enforce": tenant.sso_enforced,
            "secret_changed": body.client_secret is not None,
        },
    )
    await ctx.db.commit()
    return _out(connection, tenant)


@router.delete("/settings", status_code=204)
async def remove_settings(ctx: Ctx = Depends(sso_admin)) -> None:
    if not ctx.is_owner:
        raise Forbidden("Only the workspace owner can change company sign-in.", code="owner_only")
    connection = await ctx.db.scalar(select(SsoConnection).with_for_update())
    if connection is None:
        return
    tenant = await ctx.db.scalar(select(Tenant).where(Tenant.id == ctx.tenant_id).with_for_update())
    assert tenant is not None
    tenant.sso_enforced = False
    await ctx.db.delete(connection)
    await audit.record(ctx.db, "sso.removed", target_type="workspace", target_id=ctx.tenant_id, data={})
    await ctx.db.commit()
