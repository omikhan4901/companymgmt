"""Sessions and refresh-token rotation.

A session is one signed-in device. Each refresh token is single-use: using it returns a
new one. If a token that was already used shows up again (outside a short grace window
for two tabs refreshing at once), someone may have copied it, so the whole session is
revoked and the user is told by email.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import context, outbox
from app.core.config import get_settings
from app.core.errors import Conflict, Unauthorized
from app.core.security.tokens import create_access_token, hash_secret, new_secret
from app.modules.platform import emails
from app.modules.platform.models import AuthEvent, AuthSession, RefreshToken, User


@dataclass
class Issued:
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    session: AuthSession


def now() -> datetime:
    return datetime.now(UTC)


def log_event(db: AsyncSession, user_id: uuid.UUID | None, event: str, **data: object) -> None:
    info = context.current()
    db.add(
        AuthEvent(
            user_id=user_id,
            event=event,
            ip=info.ip,
            user_agent=(info.user_agent or "")[:300] or None,
            data={k: str(v) for k, v in data.items()},
        )
    )


async def _new_refresh(db: AsyncSession, session: AuthSession) -> str:
    settings = get_settings()
    secret = new_secret()
    expires = min(now() + timedelta(days=settings.refresh_idle_days), session.expires_at)
    db.add(RefreshToken(session_id=session.id, token_hash=hash_secret(secret), expires_at=expires))
    await db.flush()
    return secret


async def start_session(
    db: AsyncSession, user: User, tenant_id: uuid.UUID | None, *, mfa: bool, method: str = "password"
) -> Issued:
    settings = get_settings()
    info = context.current()
    session = AuthSession(
        user_id=user.id,
        tenant_id=tenant_id,
        expires_at=now() + timedelta(days=settings.refresh_absolute_days),
        ip=info.ip,
        user_agent=(info.user_agent or "")[:300] or None,
        mfa_at=now() if mfa else None,
        reauth_at=now(),
        method=method,
    )
    db.add(session)
    await db.flush()
    refresh = await _new_refresh(db, session)
    access, expires = create_access_token(user.id, session.id, tenant_id)
    log_event(db, user.id, "session.started", session=session.id, mfa=mfa, method=method)
    return Issued(access, expires, refresh, session)


def access_for(session: AuthSession) -> tuple[str, datetime]:
    return create_access_token(session.user_id, session.id, session.tenant_id)


async def revoke_session(db: AsyncSession, session_id: uuid.UUID, reason: str) -> None:
    await db.execute(
        update(AuthSession)
        .where(AuthSession.id == session_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now(), revoke_reason=reason)
    )


async def revoke_user_sessions(
    db: AsyncSession,
    user_id: uuid.UUID,
    reason: str,
    *,
    except_session: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
) -> None:
    query = update(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
    if except_session is not None:
        query = query.where(AuthSession.id != except_session)
    if tenant_id is not None:
        query = query.where(AuthSession.tenant_id == tenant_id)
    await db.execute(query.values(revoked_at=now(), revoke_reason=reason))


async def rotate(db: AsyncSession, secret: str) -> Issued:
    """Exchange a refresh token for a new one plus a new access token."""
    settings = get_settings()
    token = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_secret(secret)).with_for_update()
    )
    if token is None:
        raise Unauthorized(code="session_ended")
    session = await db.scalar(select(AuthSession).where(AuthSession.id == token.session_id).with_for_update())
    user = await db.get(User, session.user_id) if session else None
    if session is None or user is None:
        raise Unauthorized(code="session_ended")
    current = now()
    if token.used_at is not None:
        if current - token.used_at <= timedelta(seconds=settings.refresh_reuse_grace_seconds):
            # Another tab refreshed a moment ago; its new cookie is already set.
            raise Conflict("Already refreshed.", code="refresh_race")
        await revoke_session(db, session.id, "token_reuse")
        log_event(db, user.id, "session.token_reuse", session=session.id)
        if user.email:
            emails.send(
                db,
                "token_reuse",
                user.email,
                user.locale,
                name=user.name,
                link=emails.link("/forgot-password"),
            )
        pending = outbox.pending_ids(db)
        await db.commit()
        await outbox.dispatch(pending)
        raise Unauthorized(code="session_ended")
    if (
        session.revoked_at is not None
        or session.expires_at <= current
        or token.expires_at <= current
        or user.disabled_at is not None
    ):
        raise Unauthorized(code="session_ended")
    token.used_at = current
    refresh = await _new_refresh(db, session)
    access, expires = access_for(session)
    return Issued(access, expires, refresh, session)
