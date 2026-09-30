"""Sign-up, sign-in, tokens, sessions, passwords, email verification and two-step
verification."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, Depends, Request, Response
from pydantic import EmailStr, Field, StringConstraints, model_validator
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import captcha, context, outbox, ratelimit
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import Forbidden, Invalid, NotFound, TooManyRequests, Unauthorized
from app.core.schema import In, Out, ShortName
from app.core.security import crypto, passwords, totp
from app.core.security.tokens import hash_secret, new_secret
from app.modules.platform import catalog, emails, workspaces
from app.modules.platform.deps import Ctx, public, signed_in
from app.modules.platform.models import (
    AuthChallenge,
    AuthSession,
    EmailToken,
    Plan,
    RecoveryCode,
    Tenant,
    User,
)
from app.modules.platform.tokens import (
    Issued,
    access_for,
    log_event,
    now,
    revoke_session,
    revoke_user_sessions,
    rotate,
    start_session,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])

REFRESH_COOKIE = "cm_refresh"
REFRESH_PATH = "/v1/auth"
CLIENT_HEADER = "x-cm-client"
VERIFY_HOURS = 48
RESET_MINUTES = 30
CHALLENGE_MINUTES = 5
LOGIN_FAILS = ratelimit.Rule("login-fail", 1_000_000, 900)

Password = Annotated[str, StringConstraints(min_length=1, max_length=passwords.MAX_LENGTH)]
Locale = Literal["en", "bn"]


# ---- Schemas ---------------------------------------------------------------------------


class TokenOut(Out):
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_at: datetime


class LoginOut(Out):
    mfa_required: bool = False
    challenge: str | None = None
    access_token: str | None = None
    token_type: str = "bearer"  # noqa: S105
    expires_at: datetime | None = None


class SignupIn(In):
    name: ShortName
    email: EmailStr
    password: Password
    business_name: ShortName
    business_type: Literal["shop", "restaurant", "retail", "office", "factory", "other"]
    team_size: Literal["1", "2-5", "6-20", "21-100", "100+"] | None = None
    country: Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")] | None = None
    timezone: Annotated[str, StringConstraints(max_length=64)] = "UTC"
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] | None = None
    locale: Locale = "en"
    captcha_token: str | None = Field(default=None, max_length=4096)


class LoginIn(In):
    email: EmailStr | None = None
    workspace: Annotated[str, StringConstraints(max_length=40)] | None = None
    username: Annotated[str, StringConstraints(max_length=40)] | None = None
    password: Password
    captcha_token: str | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def _one_identity(self) -> LoginIn:
        if bool(self.email) == bool(self.workspace and self.username):
            raise ValueError("Sign in with an email, or with a workspace code and username.")
        return self


class MfaVerifyIn(In):
    challenge: Annotated[str, StringConstraints(max_length=100)]
    code: Annotated[str, StringConstraints(max_length=12)] | None = None
    recovery_code: Annotated[str, StringConstraints(max_length=20)] | None = None


class SwitchIn(In):
    tenant_id: uuid.UUID


class ReauthIn(In):
    password: Password | None = None
    code: Annotated[str, StringConstraints(max_length=12)] | None = None


class PasswordChangeIn(In):
    current_password: Password
    new_password: Password


class ForgotIn(In):
    email: EmailStr
    captcha_token: str | None = Field(default=None, max_length=4096)


class ResetIn(In):
    token: Annotated[str, StringConstraints(max_length=200)]
    password: Password


class TokenIn(In):
    token: Annotated[str, StringConstraints(max_length=200)]


class CodeIn(In):
    code: Annotated[str, StringConstraints(max_length=12)]


class ProfileIn(In):
    name: ShortName | None = None
    locale: Locale | None = None


class MfaSetupOut(Out):
    secret: str
    otpauth_uri: str


class RecoveryCodesOut(Out):
    recovery_codes: list[str]


class SessionOut(Out):
    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime
    ip: str | None
    user_agent: str | None
    current: bool


class WorkspaceRef(Out):
    id: str
    name: str
    slug: str
    role: str


class PlanOut(Out):
    key: str
    name: str
    status: str
    trial_ends_at: datetime | None
    modules: list[str]
    locked_modules: list[str]
    max_people: int | None
    max_branches: int | None
    max_modules: int | None
    features: dict[str, object]


class CurrentWorkspace(Out):
    id: uuid.UUID
    name: str
    slug: str
    business_type: str
    ui_mode: str
    country: str | None
    currency: str
    timezone: str
    locale: str
    week_start: int
    fiscal_year_start_month: int
    role: str
    role_key: str
    permissions: list[str]
    plan: PlanOut
    membership_id: uuid.UUID
    scope_department_id: uuid.UUID | None


class MeOut(Out):
    id: uuid.UUID
    name: str
    email: str | None
    username: str | None
    email_verified: bool
    locale: str
    mfa_enabled: bool
    must_change_password: bool
    workspaces: list[WorkspaceRef]
    workspace: CurrentWorkspace | None


# ---- Helpers ---------------------------------------------------------------------------


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_absolute_days * 86400,
        path=REFRESH_PATH,
        httponly=True,
        secure=True,
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH, secure=True, httponly=True, samesite="strict")


def _check_origin(request: Request) -> None:
    """The refresh cookie is sent automatically, so its endpoints also require a custom
    header (forces a CORS preflight) and an allowed Origin when the browser sends one."""
    if request.headers.get(CLIENT_HEADER) != "web":
        raise Forbidden("Missing client header.", code="csrf")
    origin = request.headers.get("origin")
    if origin and origin not in get_settings().cors_origins:
        raise Forbidden("Origin not allowed.", code="csrf")


async def _tokens(db: AsyncSession, response: Response, issued: Issued) -> TokenOut:
    ids = outbox.pending_ids(db)
    await db.commit()
    await outbox.dispatch(ids)
    _set_refresh_cookie(response, issued.refresh_token)
    return TokenOut(access_token=issued.access_token, expires_at=issued.access_expires_at)


async def commit_and_dispatch(db: AsyncSession) -> None:
    ids = outbox.pending_ids(db)
    await db.commit()
    if ids:
        await outbox.dispatch(ids)


def _password_problems(password: str, *context_words: str | None) -> None:
    issues = passwords.problems(password, context=tuple(w for w in context_words if w))
    if issues:
        raise Invalid(errors=[{"field": "password", "message": m} for m in issues])


async def _default_tenant(db: AsyncSession, user: User, hint: str | None = None) -> uuid.UUID | None:
    if user.managed_tenant_id:
        return user.managed_tenant_id
    spaces = await workspaces.user_workspaces(db, user.id)
    ids = {s["id"] for s in spaces}
    if hint:
        for s in spaces:
            if hint in (s["id"], s["slug"]):
                return uuid.UUID(s["id"])
    last = await db.scalar(
        select(AuthSession.tenant_id)
        .where(AuthSession.user_id == user.id, AuthSession.tenant_id.is_not(None))
        .order_by(AuthSession.created_at.desc())
        .limit(1)
    )
    if last and str(last) in ids:
        return last
    return uuid.UUID(spaces[0]["id"]) if spaces else None


def _step_up_ok(ctx: Ctx) -> bool:
    stamp = ctx.session.reauth_at
    window = timedelta(minutes=get_settings().step_up_minutes)
    return stamp is not None and now() - stamp <= window


def require_recent_auth(ctx: Ctx) -> None:
    if not _step_up_ok(ctx):
        raise Forbidden("Please confirm it's you first.", code="reauth_required")


def _totp_secret(user: User) -> str | None:
    if not user.totp_secret_enc:
        return None
    return crypto.decrypt(user.totp_secret_enc, context=f"user:{user.id}:totp")


async def _check_totp(db: AsyncSession, user: User, code: str) -> bool:
    secret = _totp_secret(user)
    if secret is None:
        return False
    step = totp.verify(secret, code, last_step=user.totp_last_step)
    if step is None:
        return False
    user.totp_last_step = step
    return True


async def _use_recovery_code(db: AsyncSession, user: User, code: str) -> bool:
    row = await db.scalar(
        select(RecoveryCode)
        .where(
            RecoveryCode.user_id == user.id,
            RecoveryCode.code_hash == totp.hash_recovery_code(code),
            RecoveryCode.used_at.is_(None),
        )
        .with_for_update()
    )
    if row is None:
        return False
    row.used_at = now()
    return True


async def _new_email_token(db: AsyncSession, user: User, purpose: str, minutes: int) -> str:
    assert user.email
    secret = new_secret()
    db.add(
        EmailToken(
            user_id=user.id,
            purpose=purpose,
            email=user.email,
            token_hash=hash_secret(secret),
            expires_at=now() + timedelta(minutes=minutes),
        )
    )
    return secret


async def _send_verification(db: AsyncSession, user: User) -> None:
    secret = await _new_email_token(db, user, "verify", VERIFY_HOURS * 60)
    emails.send(
        db,
        "verify",
        user.email or "",
        user.locale,
        name=user.name,
        link=emails.link(f"/verify-email?token={secret}"),
    )


# ---- Sign-up and sign-in ---------------------------------------------------------------


@router.post("/signup", status_code=201, response_model=TokenOut)
async def signup(
    body: SignupIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(public()),
) -> TokenOut:
    info = context.current()
    count = await ratelimit.enforce(ratelimit.SIGNUP_IP, info.ip or "unknown")
    if count > 3 and not await captcha.verify(body.captcha_token, info.ip):
        raise Unauthorized("Please complete the check.", code="captcha_required")
    email = body.email.lower()
    _password_problems(body.password, body.name, email.split("@")[0], body.business_name)
    exists = await db.scalar(select(func.count()).select_from(User).where(func.lower(User.email) == email))
    if exists:
        # Don't reveal whether the email is registered beyond what sign-in already does.
        raise Invalid(
            errors=[
                {"field": "email", "message": "An account with this email already exists. Sign in instead."}
            ]
        )
    user = User(
        email=email,
        name=body.name,
        password_hash=passwords.hash_password(body.password),
        password_changed_at=now(),
        locale=body.locale,
    )
    db.add(user)
    await db.flush()
    tenant = await workspaces.create_workspace(
        db,
        user,
        name=body.business_name,
        business_type=body.business_type,
        country=body.country,
        timezone=body.timezone,
        currency=body.currency,
        locale=body.locale,
    )
    await _send_verification(db, user)
    log_event(db, user.id, "signup", tenant=tenant.id)
    issued = await start_session(db, user, tenant.id, mfa=False)
    return await _tokens(db, response, issued)


@router.post("/login", response_model=LoginOut)
async def login(
    body: LoginIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(public()),
) -> LoginOut:
    info = context.current()
    ip = info.ip or "unknown"
    identity = (body.email or f"{body.workspace}/{body.username}").lower()
    await ratelimit.enforce(ratelimit.LOGIN_IP, ip)
    await ratelimit.enforce(ratelimit.LOGIN_ACCOUNT, identity)
    settings = get_settings()
    failures = await ratelimit.peek(LOGIN_FAILS, identity)
    if failures >= settings.captcha_after_failures and not await captcha.verify(body.captcha_token, ip):
        raise Unauthorized("Please complete the check.", code="captcha_required")

    user: User | None
    tenant_hint: str | None = None
    if body.email:
        user = await db.scalar(
            select(User).where(func.lower(User.email) == body.email.lower(), User.managed_tenant_id.is_(None))
        )
    else:
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == (body.workspace or "").lower()))
        user = None
        if tenant is not None:
            user = await db.scalar(
                select(User).where(
                    User.managed_tenant_id == tenant.id,
                    func.lower(User.username) == (body.username or "").lower(),
                )
            )
            tenant_hint = str(tenant.id)

    ok = passwords.verify_password(user.password_hash if user else None, body.password)
    if not ok or user is None or user.disabled_at is not None:
        await ratelimit.hit(LOGIN_FAILS, identity)
        log_event(db, user.id if user else None, "login.failed")
        await db.commit()
        raise Unauthorized("The sign-in details are incorrect.", code="bad_credentials")

    await ratelimit.reset(LOGIN_FAILS, identity)
    if user.password_hash and passwords.needs_rehash(user.password_hash):
        user.password_hash = passwords.hash_password(body.password)

    if user.totp_enabled_at:
        secret = new_secret()
        db.add(
            AuthChallenge(
                user_id=user.id,
                token_hash=hash_secret(secret),
                tenant_hint=uuid.UUID(tenant_hint) if tenant_hint else None,
                expires_at=now() + timedelta(minutes=CHALLENGE_MINUTES),
            )
        )
        log_event(db, user.id, "login.mfa_challenge")
        await db.commit()
        return LoginOut(mfa_required=True, challenge=secret)

    log_event(db, user.id, "login.succeeded")
    issued = await start_session(db, user, await _default_tenant(db, user, tenant_hint), mfa=False)
    tokens = await _tokens(db, response, issued)
    return LoginOut(access_token=tokens.access_token, expires_at=tokens.expires_at)


@router.post("/mfa/verify", response_model=TokenOut)
async def mfa_verify(
    body: MfaVerifyIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(public()),
) -> TokenOut:
    challenge = await db.scalar(
        select(AuthChallenge).where(AuthChallenge.token_hash == hash_secret(body.challenge)).with_for_update()
    )
    if challenge is None or challenge.used_at is not None or challenge.expires_at <= now():
        raise Unauthorized("This sign-in expired. Please start again.", code="challenge_expired")
    allowed, _count, retry = await ratelimit.hit(ratelimit.MFA_SESSION, str(challenge.id))
    if not allowed or challenge.attempts >= 5:
        raise TooManyRequests(headers={"Retry-After": str(max(retry, 1))})
    user = await db.get(User, challenge.user_id)
    assert user is not None
    challenge.attempts += 1
    ok = False
    if body.code:
        ok = await _check_totp(db, user, body.code)
    elif body.recovery_code:
        ok = await _use_recovery_code(db, user, body.recovery_code)
        if ok:
            log_event(db, user.id, "mfa.recovery_code_used")
    if not ok:
        log_event(db, user.id, "mfa.failed")
        await db.commit()
        raise Unauthorized("That code didn't work.", code="bad_code")
    challenge.used_at = now()
    hint = str(challenge.tenant_hint) if challenge.tenant_hint else None
    log_event(db, user.id, "login.succeeded", mfa=True)
    issued = await start_session(db, user, await _default_tenant(db, user, hint), mfa=True)
    return await _tokens(db, response, issued)


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    cm_refresh: str | None = Cookie(default=None),
    _: None = Depends(public()),
) -> TokenOut:
    _check_origin(request)
    await ratelimit.enforce(ratelimit.REFRESH_IP, context.current().ip or "unknown")
    if not cm_refresh:
        raise Unauthorized(code="session_ended")
    issued = await rotate(db, cm_refresh)
    return await _tokens(db, response, issued)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    ctx: Ctx = Depends(signed_in()),
) -> Response:
    await revoke_session(ctx.db, ctx.session.id, "logout")
    log_event(ctx.db, ctx.user.id, "logout")
    await ctx.db.commit()
    response.status_code = 204
    _clear_refresh_cookie(response)
    return response


@router.post("/switch", response_model=TokenOut)
async def switch_workspace(body: SwitchIn, ctx: Ctx = Depends(signed_in())) -> TokenOut:
    spaces = await workspaces.user_workspaces(ctx.db, ctx.user.id)
    if str(body.tenant_id) not in {s["id"] for s in spaces}:
        raise Forbidden("You're not a member of that workspace.", code="not_member")
    if ctx.user.managed_tenant_id and ctx.user.managed_tenant_id != body.tenant_id:
        raise Forbidden(code="not_member")
    await ctx.db.execute(
        update(AuthSession).where(AuthSession.id == ctx.session.id).values(tenant_id=body.tenant_id)
    )
    ctx.session.tenant_id = body.tenant_id
    await ctx.db.commit()
    access, expires = access_for(ctx.session)
    return TokenOut(access_token=access, expires_at=expires)


@router.get("/me", response_model=MeOut)
async def me(ctx: Ctx = Depends(signed_in())) -> MeOut:
    user = ctx.user
    current = None
    if ctx.tenant and ctx.membership and ctx.role and ctx.entitlements:
        ent = ctx.entitlements
        current = CurrentWorkspace(
            id=ctx.tenant.id,
            name=ctx.tenant.name,
            slug=ctx.tenant.slug,
            business_type=ctx.tenant.business_type,
            ui_mode=ctx.tenant.ui_mode,
            country=ctx.tenant.country,
            currency=ctx.tenant.currency,
            timezone=ctx.tenant.timezone,
            locale=ctx.tenant.locale,
            week_start=ctx.tenant.week_start,
            fiscal_year_start_month=ctx.tenant.fiscal_year_start_month,
            role=ctx.role.name,
            role_key=ctx.role.key,
            permissions=sorted(ctx.permissions),
            membership_id=ctx.membership.id,
            scope_department_id=ctx.membership.scope_department_id,
            plan=PlanOut(
                key=ent.plan.key,
                name=ent.plan.name,
                status=ent.status,
                trial_ends_at=ent.trial_ends_at,
                modules=sorted(ent.modules),
                locked_modules=sorted(ent.locked_modules),
                max_people=ent.plan.max_people,
                max_branches=ent.plan.max_branches,
                max_modules=ent.plan.max_modules,
                features=ent.plan.features or {},
            ),
        )
    return MeOut(
        id=user.id,
        name=user.name,
        email=user.email,
        username=user.username,
        email_verified=user.email_verified_at is not None,
        locale=user.locale,
        mfa_enabled=user.totp_enabled_at is not None,
        must_change_password=user.must_change_password,
        workspaces=[WorkspaceRef(**w) for w in await workspaces.user_workspaces(ctx.db, user.id)],
        workspace=current,
    )


@router.patch("/me", status_code=204)
async def update_profile(body: ProfileIn, ctx: Ctx = Depends(signed_in())) -> None:
    if body.name is not None:
        ctx.user.name = body.name
    if body.locale is not None:
        ctx.user.locale = body.locale
    await ctx.db.commit()


# ---- Step-up, passwords, email --------------------------------------------------------


@router.post("/reauth", status_code=204)
async def reauth(body: ReauthIn, ctx: Ctx = Depends(signed_in())) -> None:
    await ratelimit.enforce(ratelimit.MFA_SESSION, f"reauth:{ctx.session.id}")
    ok = False
    if body.password is not None:
        ok = passwords.verify_password(ctx.user.password_hash, body.password)
    elif body.code is not None:
        ok = await _check_totp(ctx.db, ctx.user, body.code)
    if not ok:
        log_event(ctx.db, ctx.user.id, "reauth.failed")
        await ctx.db.commit()
        raise Unauthorized("That didn't match.", code="bad_credentials")
    await ctx.db.execute(update(AuthSession).where(AuthSession.id == ctx.session.id).values(reauth_at=now()))
    log_event(ctx.db, ctx.user.id, "reauth")
    await ctx.db.commit()


@router.post("/password/change", status_code=204)
async def change_password(body: PasswordChangeIn, ctx: Ctx = Depends(signed_in())) -> None:
    await ratelimit.enforce(ratelimit.MFA_SESSION, f"pwchange:{ctx.session.id}")
    user = ctx.user
    if not passwords.verify_password(user.password_hash, body.current_password):
        log_event(ctx.db, user.id, "password.change_failed")
        await ctx.db.commit()
        raise Invalid(errors=[{"field": "current_password", "message": "Your current password isn't right."}])
    if body.current_password == body.new_password:
        raise Invalid(errors=[{"field": "new_password", "message": "Choose a different password."}])
    _password_problems(body.new_password, user.name, (user.email or "").split("@")[0], user.username)
    user.password_hash = passwords.hash_password(body.new_password)
    user.password_changed_at = now()
    user.must_change_password = False
    await revoke_user_sessions(ctx.db, user.id, "password_changed", except_session=ctx.session.id)
    log_event(ctx.db, user.id, "password.changed")
    if user.email:
        emails.send(
            ctx.db,
            "password_changed",
            user.email,
            user.locale,
            name=user.name,
            link=emails.link("/forgot-password"),
        )
    await commit_and_dispatch(ctx.db)


@router.post("/password/forgot", status_code=202)
async def forgot_password(
    body: ForgotIn, db: AsyncSession = Depends(get_db), _: None = Depends(public())
) -> dict[str, str]:
    ip = context.current().ip or "unknown"
    await ratelimit.enforce(ratelimit.RESET_IP, ip)
    email = body.email.lower()
    allowed, _count, _retry = await ratelimit.hit(ratelimit.RESET_ACCOUNT, email)
    user = await db.scalar(
        select(User).where(func.lower(User.email) == email, User.managed_tenant_id.is_(None))
    )
    if allowed and user is not None and user.disabled_at is None:
        secret = await _new_email_token(db, user, "reset", RESET_MINUTES)
        emails.send(
            db,
            "reset",
            email,
            user.locale,
            name=user.name,
            link=emails.link(f"/reset-password?token={secret}"),
        )
        log_event(db, user.id, "password.reset_requested")
        await commit_and_dispatch(db)
    # Same answer whether or not the account exists.
    return {"status": "If an account exists for this email, we've sent a reset link."}


@router.post("/password/reset", status_code=204)
async def reset_password(
    body: ResetIn, db: AsyncSession = Depends(get_db), _: None = Depends(public())
) -> None:
    await ratelimit.enforce(ratelimit.RESET_IP, context.current().ip or "unknown")
    token = await db.scalar(
        select(EmailToken)
        .where(EmailToken.token_hash == hash_secret(body.token), EmailToken.purpose == "reset")
        .with_for_update()
    )
    if token is None or token.used_at is not None or token.expires_at <= now():
        raise Invalid("This reset link has expired. Ask for a new one.", code="token_expired")
    user = await db.get(User, token.user_id)
    if user is None or user.email is None or user.email.lower() != token.email.lower():
        raise Invalid("This reset link has expired. Ask for a new one.", code="token_expired")
    _password_problems(body.password, user.name, user.email.split("@")[0])
    user.password_hash = passwords.hash_password(body.password)
    user.password_changed_at = now()
    user.must_change_password = False
    token.used_at = now()
    # The link proves control of the mailbox.
    user.email_verified_at = user.email_verified_at or now()
    await db.execute(
        update(EmailToken)
        .where(EmailToken.user_id == user.id, EmailToken.purpose == "reset", EmailToken.used_at.is_(None))
        .values(used_at=now())
    )
    await revoke_user_sessions(db, user.id, "password_reset")
    log_event(db, user.id, "password.reset")
    await db.commit()


@router.post("/email/verify", status_code=204)
async def verify_email(
    body: TokenIn, db: AsyncSession = Depends(get_db), _: None = Depends(public())
) -> None:
    token = await db.scalar(
        select(EmailToken)
        .where(EmailToken.token_hash == hash_secret(body.token), EmailToken.purpose == "verify")
        .with_for_update()
    )
    if token is None or token.used_at is not None or token.expires_at <= now():
        raise Invalid("This link has expired. Send a new one from your account.", code="token_expired")
    user = await db.get(User, token.user_id)
    if user is None or (user.email or "").lower() != token.email.lower():
        raise Invalid("This link has expired. Send a new one from your account.", code="token_expired")
    token.used_at = now()
    user.email_verified_at = user.email_verified_at or now()
    log_event(db, user.id, "email.verified")
    await db.commit()


@router.post("/email/resend", status_code=202)
async def resend_verification(ctx: Ctx = Depends(signed_in())) -> dict[str, str]:
    await ratelimit.enforce(ratelimit.RESET_ACCOUNT, f"verify:{ctx.user.id}")
    if ctx.user.email and not ctx.user.email_verified_at:
        await _send_verification(ctx.db, ctx.user)
        await commit_and_dispatch(ctx.db)
    return {"status": "sent"}


# ---- Sessions --------------------------------------------------------------------------


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(ctx: Ctx = Depends(signed_in())) -> list[SessionOut]:
    rows = await ctx.db.scalars(
        select(AuthSession)
        .where(
            AuthSession.user_id == ctx.user.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now(),
        )
        .order_by(AuthSession.last_seen_at.desc())
    )
    return [
        SessionOut(
            id=s.id,
            created_at=s.created_at,
            last_seen_at=s.last_seen_at,
            ip=s.ip,
            user_agent=s.user_agent,
            current=s.id == ctx.session.id,
        )
        for s in rows
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def end_session(session_id: uuid.UUID, ctx: Ctx = Depends(signed_in())) -> None:
    owned = await ctx.db.scalar(
        select(AuthSession.id).where(AuthSession.id == session_id, AuthSession.user_id == ctx.user.id)
    )
    if owned is None:
        raise NotFound()
    await revoke_session(ctx.db, session_id, "user_revoked")
    log_event(ctx.db, ctx.user.id, "session.revoked", session=session_id)
    await ctx.db.commit()


@router.post("/sessions/revoke-others", status_code=204)
async def end_other_sessions(ctx: Ctx = Depends(signed_in())) -> None:
    await revoke_user_sessions(ctx.db, ctx.user.id, "user_revoked_all", except_session=ctx.session.id)
    log_event(ctx.db, ctx.user.id, "session.revoked_others")
    await ctx.db.commit()


# ---- Two-step verification -------------------------------------------------------------


@router.post("/mfa/setup", response_model=MfaSetupOut)
async def mfa_setup(ctx: Ctx = Depends(signed_in())) -> MfaSetupOut:
    require_recent_auth(ctx)
    if ctx.user.totp_enabled_at:
        raise Invalid("Two-step verification is already on.", code="mfa_enabled")
    secret = totp.new_secret()
    ctx.user.totp_pending_enc = crypto.encrypt(secret, context=f"user:{ctx.user.id}:totp-pending")
    await ctx.db.commit()
    account = ctx.user.email or f"{ctx.user.username}"
    return MfaSetupOut(secret=secret, otpauth_uri=totp.provisioning_uri(secret, account))


async def _issue_recovery_codes(db: AsyncSession, user: User) -> list[str]:
    await db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    codes = totp.new_recovery_codes()
    for code in codes:
        db.add(RecoveryCode(user_id=user.id, code_hash=totp.hash_recovery_code(code)))
    return codes


@router.post("/mfa/enable", response_model=RecoveryCodesOut)
async def mfa_enable(body: CodeIn, ctx: Ctx = Depends(signed_in())) -> RecoveryCodesOut:
    await ratelimit.enforce(ratelimit.MFA_SESSION, f"enable:{ctx.session.id}")
    user = ctx.user
    if not user.totp_pending_enc:
        raise Invalid("Start the setup again.", code="mfa_not_started")
    secret = crypto.decrypt(user.totp_pending_enc, context=f"user:{user.id}:totp-pending")
    step = totp.verify(secret, body.code, last_step=None)
    if step is None:
        raise Invalid(
            errors=[{"field": "code", "message": "That code didn't work. Check the time on your phone."}]
        )
    user.totp_secret_enc = crypto.encrypt(secret, context=f"user:{user.id}:totp")
    user.totp_pending_enc = None
    user.totp_enabled_at = now()
    user.totp_last_step = step
    codes = await _issue_recovery_codes(ctx.db, user)
    await ctx.db.execute(update(AuthSession).where(AuthSession.id == ctx.session.id).values(mfa_at=now()))
    log_event(ctx.db, user.id, "mfa.enabled")
    if user.email:
        emails.send(
            ctx.db,
            "mfa_changed",
            user.email,
            user.locale,
            name=user.name,
            state="turned on" if user.locale != "bn" else "চালু করা হয়েছে",
            link=emails.link("/forgot-password"),
        )
    await commit_and_dispatch(ctx.db)
    return RecoveryCodesOut(recovery_codes=codes)


@router.post("/mfa/disable", status_code=204)
async def mfa_disable(ctx: Ctx = Depends(signed_in())) -> None:
    require_recent_auth(ctx)
    user = ctx.user
    user.totp_secret_enc = None
    user.totp_pending_enc = None
    user.totp_enabled_at = None
    user.totp_last_step = None
    await ctx.db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    log_event(ctx.db, user.id, "mfa.disabled")
    if user.email:
        emails.send(
            ctx.db,
            "mfa_changed",
            user.email,
            user.locale,
            name=user.name,
            state="turned off" if user.locale != "bn" else "বন্ধ করা হয়েছে",
            link=emails.link("/forgot-password"),
        )
    await commit_and_dispatch(ctx.db)


@router.post("/mfa/recovery-codes", response_model=RecoveryCodesOut)
async def mfa_new_recovery_codes(ctx: Ctx = Depends(signed_in())) -> RecoveryCodesOut:
    require_recent_auth(ctx)
    if not ctx.user.totp_enabled_at:
        raise Invalid("Turn on two-step verification first.", code="mfa_off")
    codes = await _issue_recovery_codes(ctx.db, ctx.user)
    log_event(ctx.db, ctx.user.id, "mfa.recovery_codes_regenerated")
    await ctx.db.commit()
    return RecoveryCodesOut(recovery_codes=codes)


# ---- Plans (public, for the pricing page and onboarding) -------------------------------


class PublicPlan(Out):
    key: str
    name: str
    price_month_cents: int | None
    price_year_cents: int | None
    included_people: int | None
    extra_person_cents: int | None
    max_people: int | None
    max_branches: int | None
    max_modules: int | None
    storage_mb: int | None
    audit_retention_days: int | None
    features: dict[str, object]


plans_router = APIRouter(prefix="/v1", tags=["plans"])


@plans_router.get("/plans", response_model=list[PublicPlan])
async def list_plans(db: AsyncSession = Depends(get_db), _: None = Depends(public())) -> list[PublicPlan]:
    rows = await db.scalars(select(Plan).where(Plan.is_public.is_(True)).order_by(Plan.sort))
    return [PublicPlan.model_validate(p) for p in rows]


@plans_router.get("/modules")
async def list_modules(_: None = Depends(public())) -> list[dict[str, object]]:
    return [
        {"key": m.key, "name": m.name, "core": m.core, "requires": list(m.requires), "available": m.available}
        for m in catalog.MODULES.values()
    ]
