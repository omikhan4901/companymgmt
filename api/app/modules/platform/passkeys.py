"""Passkeys (WebAuthn): sign in with a fingerprint, face or device PIN instead of a
password. Phishing-resistant: the browser only signs for our domain, and the private
key never leaves the person's device or password manager.

- Register (signed in, with a recent sign-in confirmation): `POST
  /v1/auth/passkeys/register/options`, then `POST /v1/auth/passkeys/register` with what
  the browser made.
- Sign in: `POST /v1/auth/passkeys/login/options` (no name needed: discoverable
  credentials), then `POST /v1/auth/passkeys/login`. Counts as two-step verification
  (something you have, plus the fingerprint/face/PIN the device checked).
- Challenges are single-use and expire after 5 minutes. The relying party is the web
  domain (so workspace subdomains share passkeys); origins are checked against the app's
  own addresses.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import parse_authentication_credential_json, parse_registration_credential_json
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.core import audit, context, ratelimit
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import Invalid, NotFound, Unauthorized
from app.core.schema import In
from app.core.time import utcnow
from app.modules.platform.deps import Ctx, public, signed_in
from app.modules.platform.models import Passkey, User, WebAuthnChallenge
from app.modules.platform.routes_auth import (
    TokenOut,
    _check_origin,
    _default_tenant,
    _tokens,
    require_recent_auth,
)
from app.modules.platform.tokens import log_event, start_session

router = APIRouter(prefix="/v1/auth/passkeys", tags=["auth"])

CHALLENGE_TTL = timedelta(minutes=5)
MAX_PASSKEYS = 10


def relying_party() -> tuple[str, str]:
    """(RP id, RP name): the web app's registrable domain."""
    settings = get_settings()
    host = urlsplit(settings.web_base_url).hostname or "localhost"
    return host, settings.app_name


def allowed_origins(request: Request) -> list[str]:
    """The app's own origins, plus the workspace address this request came from when it
    is a subdomain of the relying party."""
    settings = get_settings()
    rp_id, _ = relying_party()
    origins = {settings.web_base_url.rstrip("/"), *settings.cors_origins}
    origin = request.headers.get("origin", "")
    parts = urlsplit(origin)
    if parts.scheme == "https" and parts.hostname and parts.hostname.endswith("." + rp_id):
        origins.add(origin)
    return sorted(o for o in origins if o)


async def _challenge(
    db: AsyncSession, purpose: str, challenge: bytes, user_id: uuid.UUID | None
) -> uuid.UUID:
    row = WebAuthnChallenge(
        user_id=user_id, purpose=purpose, challenge=challenge, expires_at=utcnow() + CHALLENGE_TTL
    )
    db.add(row)
    await db.flush()
    return row.id


async def _take_challenge(db: AsyncSession, challenge_id: uuid.UUID, purpose: str) -> WebAuthnChallenge:
    row = await db.scalar(
        select(WebAuthnChallenge).where(WebAuthnChallenge.id == challenge_id).with_for_update()
    )
    if row is None or row.purpose != purpose or row.used_at is not None or row.expires_at <= utcnow():
        raise Unauthorized("This request expired. Try again.", code="passkey_challenge_invalid")
    row.used_at = utcnow()
    return row


class OptionsOut(BaseModel):
    challenge_id: uuid.UUID
    # PublicKeyCredentialCreationOptionsJSON / RequestOptionsJSON for the browser.
    options: dict[str, Any]


class PasskeyOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    last_used_at: datetime | None
    backed_up: bool


# ---- Managing your passkeys ----------------------------------------------------------------


@router.get("", response_model=list[PasskeyOut])
async def list_passkeys(ctx: Ctx = Depends(signed_in())) -> list[PasskeyOut]:
    rows = await ctx.db.scalars(
        select(Passkey).where(Passkey.user_id == ctx.user.id).order_by(Passkey.created_at)
    )
    return [
        PasskeyOut(
            id=p.id, name=p.name, created_at=p.created_at, last_used_at=p.last_used_at, backed_up=p.backed_up
        )
        for p in rows
    ]


@router.post("/register/options", response_model=OptionsOut)
async def register_options(ctx: Ctx = Depends(signed_in())) -> OptionsOut:
    require_recent_auth(ctx)
    existing = list(await ctx.db.scalars(select(Passkey).where(Passkey.user_id == ctx.user.id)))
    if len(existing) >= MAX_PASSKEYS:
        raise Invalid(f"You can have up to {MAX_PASSKEYS} passkeys.", code="too_many_passkeys")
    rp_id, rp_name = relying_party()
    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=rp_name,
        user_id=ctx.user.id.bytes,
        user_name=ctx.user.email or ctx.user.username or str(ctx.user.id),
        user_display_name=ctx.user.name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=p.credential_id) for p in existing],
    )
    challenge_id = await _challenge(ctx.db, "register", options.challenge, ctx.user.id)
    await ctx.db.commit()
    return OptionsOut(challenge_id=challenge_id, options=json.loads(options_to_json(options)))


class RegisterIn(In):
    challenge_id: uuid.UUID
    credential: dict[str, Any]
    name: Annotated[str, StringConstraints(min_length=1, max_length=80, strip_whitespace=True)] = "Passkey"


@router.post("/register", response_model=PasskeyOut, status_code=201)
async def register(body: RegisterIn, request: Request, ctx: Ctx = Depends(signed_in())) -> PasskeyOut:
    require_recent_auth(ctx)
    challenge = await _take_challenge(ctx.db, body.challenge_id, "register")
    if challenge.user_id != ctx.user.id:
        raise Unauthorized(code="passkey_challenge_invalid")
    rp_id, _ = relying_party()
    try:
        verified = verify_registration_response(
            credential=parse_registration_credential_json(json.dumps(body.credential)),
            expected_challenge=challenge.challenge,
            expected_rp_id=rp_id,
            expected_origin=allowed_origins(request),
            require_user_verification=True,
        )
    except (InvalidRegistrationResponse, ValueError, KeyError) as exc:
        await ctx.db.commit()  # the challenge stays used
        raise Invalid("Your device's answer couldn't be checked. Try again.", code="passkey_invalid") from exc
    if await ctx.db.scalar(select(Passkey.id).where(Passkey.credential_id == verified.credential_id)):
        raise Invalid("This passkey is already registered.", code="passkey_exists")
    transports = (body.credential.get("response") or {}).get("transports") or []
    passkey = Passkey(
        user_id=ctx.user.id,
        credential_id=verified.credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        transports=[str(t) for t in transports][:8],
        name=body.name,
        backed_up=bool(verified.credential_backed_up),
    )
    ctx.db.add(passkey)
    await ctx.db.flush()
    log_event(ctx.db, ctx.user.id, "passkey.added", name=body.name)
    if ctx.session.tenant_id:
        await audit.record(
            ctx.db,
            "account.passkey_added",
            target_type="user",
            target_id=ctx.user.id,
            data={"name": body.name},
        )
    await ctx.db.commit()
    return PasskeyOut(
        id=passkey.id,
        name=passkey.name,
        created_at=passkey.created_at or utcnow(),
        last_used_at=None,
        backed_up=passkey.backed_up,
    )


@router.delete("/{passkey_id}", status_code=204)
async def remove(passkey_id: uuid.UUID, ctx: Ctx = Depends(signed_in())) -> None:
    require_recent_auth(ctx)
    passkey = await ctx.db.scalar(
        select(Passkey).where(Passkey.id == passkey_id, Passkey.user_id == ctx.user.id)
    )
    if passkey is None:
        raise NotFound()
    await ctx.db.delete(passkey)
    log_event(ctx.db, ctx.user.id, "passkey.removed", name=passkey.name)
    await ctx.db.commit()


# ---- Signing in ----------------------------------------------------------------------------


@router.post("/login/options", response_model=OptionsOut)
async def login_options(db: AsyncSession = Depends(get_db), _: None = Depends(public())) -> OptionsOut:
    await ratelimit.enforce(ratelimit.LOGIN_IP, context.current().ip or "unknown")
    rp_id, _name = relying_party()
    options = generate_authentication_options(
        rp_id=rp_id, user_verification=UserVerificationRequirement.REQUIRED
    )
    challenge_id = await _challenge(db, "login", options.challenge, None)
    await db.commit()
    return OptionsOut(challenge_id=challenge_id, options=json.loads(options_to_json(options)))


class LoginIn(In):
    challenge_id: uuid.UUID
    credential: dict[str, Any]
    # The workspace to open (code or id); otherwise the last one used.
    workspace: Annotated[str | None, StringConstraints(max_length=64)] = None


@router.post("/login", response_model=TokenOut)
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(public()),
) -> TokenOut:
    _check_origin(request)
    await ratelimit.enforce(ratelimit.LOGIN_IP, context.current().ip or "unknown")
    challenge = await _take_challenge(db, body.challenge_id, "login")
    try:
        credential = parse_authentication_credential_json(json.dumps(body.credential))
    except (ValueError, KeyError) as exc:
        await db.commit()
        raise Unauthorized("This passkey couldn't be checked.", code="passkey_invalid") from exc
    passkey = await db.scalar(
        select(Passkey).where(Passkey.credential_id == credential.raw_id).with_for_update()
    )
    user = await db.get(User, passkey.user_id) if passkey else None
    if passkey is None or user is None or user.disabled_at is not None:
        await db.commit()
        raise Unauthorized("This passkey isn't registered here.", code="passkey_unknown")
    rp_id, _name = relying_party()
    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge.challenge,
            expected_rp_id=rp_id,
            expected_origin=allowed_origins(request),
            credential_public_key=passkey.public_key,
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except InvalidAuthenticationResponse as exc:
        log_event(db, user.id, "login.failed", reason="passkey")
        await db.commit()
        raise Unauthorized("This passkey couldn't be checked.", code="passkey_invalid") from exc
    passkey.sign_count = verified.new_sign_count
    passkey.last_used_at = utcnow()
    tenant_id = await _default_tenant(db, user, body.workspace)
    issued = await start_session(db, user, tenant_id, mfa=True, method="passkey")
    log_event(db, user.id, "login.passkey", passkey=str(passkey.id))
    return await _tokens(db, response, issued)
