"""Sign-up, sign-in, tokens, sessions, passwords, email verification, two-step verification."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import psycopg
import pyotp
import pytest

from app.core import email
from app.core.config import get_settings
from tests.helpers import (
    PASSWORD,
    WEB,
    Account,
    cookie,
    last_email,
    link_token,
    login,
    refresh_cookie,
    signup,
    verify_email,
)


async def test_signup_creates_workspace_and_signs_in(client: httpx.AsyncClient) -> None:
    owner = await signup(client, business="Cha Ghor 🍵", business_type="shop")
    ws = owner.me["workspace"]
    assert ws["name"] == "Cha Ghor 🍵"
    assert ws["role_key"] == "owner"
    assert ws["currency"] == "BDT"
    assert ws["fiscal_year_start_month"] == 7
    assert ws["ui_mode"] == "simple"
    assert ws["plan"]["key"] == "growth"
    assert ws["plan"]["status"] == "trialing"
    assert "attendance" in ws["plan"]["modules"]
    assert "people" in ws["plan"]["modules"]
    assert "workspace.delete" in ws["permissions"]
    assert owner.me["email_verified"] is False
    assert "Confirm" in last_email(owner.email or "").subject
    assert owner.refresh


async def test_refresh_cookie_is_locked_down(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/v1/auth/signup",
        json={
            "name": "A B",
            "email": "cookie@example.com",
            "password": PASSWORD,
            "business_name": "Shop",
            "business_type": "shop",
        },
    )
    header = next(h for h in response.headers.get_list("set-cookie") if h.startswith("cm_refresh="))
    lowered = header.lower()
    assert "httponly" in lowered
    assert "secure" in lowered
    assert "samesite=strict" in lowered
    assert "path=/v1/auth" in lowered


async def test_signup_rejects_duplicate_email_any_case(client: httpx.AsyncClient) -> None:
    await signup(client, email_addr="Dup@Example.com")
    response = await client.post(
        "/v1/auth/signup",
        json={
            "name": "X Y",
            "email": "dup@example.COM",
            "password": PASSWORD,
            "business_name": "Other",
            "business_type": "office",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "email"


@pytest.mark.parametrize(
    ("password", "fragment"),
    [("short", "at least 8"), ("password123", "too common"), ("rahimuddin-2026!", "name")],
)
async def test_signup_password_rules(client: httpx.AsyncClient, password: str, fragment: str) -> None:
    response = await client.post(
        "/v1/auth/signup",
        json={
            "name": "Rahimuddin",
            "email": "pw@example.com",
            "password": password,
            "business_name": "Shop",
            "business_type": "shop",
        },
    )
    assert response.status_code == 422
    assert any(fragment in e["message"] for e in response.json()["errors"])


async def test_signup_rejects_unknown_fields_and_bad_timezone(client: httpx.AsyncClient) -> None:
    base = {
        "name": "A B",
        "email": "x@example.com",
        "password": PASSWORD,
        "business_name": "S",
        "business_type": "shop",
    }
    assert (await client.post("/v1/auth/signup", json={**base, "is_admin": True})).status_code == 422
    assert (
        await client.post("/v1/auth/signup", json={**base, "timezone": "Mars/Olympus"})
    ).status_code == 422


async def test_unicode_names_survive(client: httpx.AsyncClient) -> None:
    owner = await signup(client, name="মোঃ আব্দুল করিম", business="রহিম স্টোর")
    assert owner.me["name"] == "মোঃ আব্দুল করিম"
    assert owner.me["workspace"]["name"] == "রহিম স্টোর"
    assert owner.me["workspace"]["slug"].startswith("ws-")


async def test_login_failures_look_the_same(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    wrong = await client.post("/v1/auth/login", json={"email": owner.email, "password": "nope-nope-nope"})
    unknown = await client.post(
        "/v1/auth/login", json={"email": "ghost@example.com", "password": "nope-nope-nope"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]
    assert wrong.json()["code"] == unknown.json()["code"] == "bad_credentials"


async def test_login_is_case_insensitive_and_returns_workspace(client: httpx.AsyncClient) -> None:
    owner = await signup(client, email_addr="Case@Example.com")
    again = await login(client, "CASE@example.com")
    assert again.tenant_id == owner.tenant_id


async def test_login_rate_limit_per_account(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    codes = [
        (
            await client.post("/v1/auth/login", json={"email": owner.email, "password": "wrong-password-x"})
        ).status_code
        for _ in range(11)
    ]
    assert codes[-1] == 429


async def test_captcha_required_after_failures(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import captcha

    owner = await signup(client)
    for _ in range(get_settings().captcha_after_failures):
        await client.post("/v1/auth/login", json={"email": owner.email, "password": "wrong-password-x"})
    monkeypatch.setattr(captcha, "enabled", lambda: True)

    async def fake_verify(token: str | None, ip: str | None) -> bool:
        return token == "ok"

    monkeypatch.setattr(captcha, "verify", fake_verify)
    blocked = await client.post("/v1/auth/login", json={"email": owner.email, "password": PASSWORD})
    assert blocked.json()["code"] == "captcha_required"
    passed = await client.post(
        "/v1/auth/login", json={"email": owner.email, "password": PASSWORD, "captcha_token": "ok"}
    )
    assert passed.status_code == 200


async def test_refresh_rotates_and_needs_client_header(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    no_header = await client.post("/v1/auth/refresh", headers=cookie(owner.refresh or ""))
    assert no_header.status_code == 403
    bad_origin = await client.post(
        "/v1/auth/refresh", headers={**WEB, "origin": "https://evil.test"} | cookie(owner.refresh or "")
    )
    assert bad_origin.status_code == 403
    first = await client.post("/v1/auth/refresh", headers=WEB | cookie(owner.refresh or ""))
    assert first.status_code == 200
    new_cookie = refresh_cookie(first)
    assert new_cookie
    assert new_cookie != owner.refresh
    # Two tabs refreshing at the same moment: the second gets a soft "already refreshed".
    race = await client.post("/v1/auth/refresh", headers=WEB | cookie(owner.refresh or ""))
    assert race.status_code == 409
    assert race.json()["code"] == "refresh_race"
    token = first.json()["access_token"]
    assert (await client.get("/v1/auth/me", headers={"authorization": f"Bearer {token}"})).status_code == 200


async def test_refresh_token_reuse_revokes_session(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await signup(client)
    first = await client.post("/v1/auth/refresh", headers=WEB | cookie(owner.refresh or ""))
    assert first.status_code == 200
    monkeypatch.setattr(get_settings(), "refresh_reuse_grace_seconds", -1)
    stolen = await client.post("/v1/auth/refresh", headers=WEB | cookie(owner.refresh or ""))
    assert stolen.status_code == 401
    # The whole session is gone, including the legitimate new token.
    legit = await client.post("/v1/auth/refresh", headers=WEB | cookie(refresh_cookie(first) or ""))
    assert legit.status_code == 401
    assert (await owner.get("/v1/auth/me")).status_code == 401
    assert "signed you out" in last_email(owner.email or "").subject


async def test_logout_ends_session(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    assert (await owner.post("/v1/auth/logout")).status_code == 204
    assert (await owner.get("/v1/auth/me")).status_code == 401
    again = await client.post("/v1/auth/refresh", headers=WEB | cookie(owner.refresh or ""))
    assert again.status_code == 401


async def test_forged_and_expired_tokens_are_rejected(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    claims = jwt.decode(owner.token, options={"verify_signature": False})
    none_alg = jwt.encode(claims, key="", algorithm="none")
    hs = jwt.encode(claims, key="x" * 32, algorithm="HS256")
    for token in (none_alg, hs, owner.token[:-4] + "AAAA", "garbage"):
        response = await client.get("/v1/auth/me", headers={"authorization": f"Bearer {token}"})
        assert response.status_code == 401, token
    assert (await client.get("/v1/auth/me")).status_code == 401


async def test_sessions_list_and_revoke(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    phone = await login(client, owner.email or "")
    sessions = (await owner.get("/v1/auth/sessions")).json()
    assert len(sessions) == 2
    assert sum(1 for s in sessions if s["current"]) == 1
    assert (await owner.post("/v1/auth/sessions/revoke-others")).status_code == 204
    assert (await phone.get("/v1/auth/me")).status_code == 401
    assert (await owner.get("/v1/auth/me")).status_code == 200
    other = await signup(client)
    other_session = (await other.get("/v1/auth/sessions")).json()[0]["id"]
    assert (await owner.delete(f"/v1/auth/sessions/{other_session}")).status_code == 404


async def test_password_change(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    phone = await login(client, owner.email or "")
    wrong = await owner.post(
        "/v1/auth/password/change", json={"current_password": "x", "new_password": "new pass 2026 ok"}
    )
    assert wrong.status_code == 422
    ok = await owner.post(
        "/v1/auth/password/change",
        json={"current_password": PASSWORD, "new_password": "a brand new passphrase"},
    )
    assert ok.status_code == 204
    assert (await phone.get("/v1/auth/me")).status_code == 401
    assert (await owner.get("/v1/auth/me")).status_code == 200
    assert "changed" in last_email(owner.email or "").subject
    await login(client, owner.email or "", "a brand new passphrase")


async def test_password_reset_flow(client: httpx.AsyncClient, owner_sql: psycopg.Connection) -> None:
    owner = await signup(client)
    unknown = await client.post("/v1/auth/password/forgot", json={"email": "nobody@example.com"})
    known = await client.post("/v1/auth/password/forgot", json={"email": owner.email})
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()
    token = link_token(last_email(owner.email or ""))
    weak = await client.post("/v1/auth/password/reset", json={"token": token, "password": "password"})
    assert weak.status_code == 422
    done = await client.post(
        "/v1/auth/password/reset", json={"token": token, "password": "reset passphrase ok"}
    )
    assert done.status_code == 204
    assert (await owner.get("/v1/auth/me")).status_code == 401
    reused = await client.post(
        "/v1/auth/password/reset", json={"token": token, "password": "another passphrase"}
    )
    assert reused.status_code == 422
    await login(client, owner.email or "", "reset passphrase ok")
    # Expired links don't work.
    await client.post("/v1/auth/password/forgot", json={"email": owner.email})
    token2 = link_token(last_email(owner.email or ""))
    owner_sql.execute(
        "UPDATE email_tokens SET expires_at = now() - interval '1 minute' WHERE used_at IS NULL"
    )
    expired = await client.post(
        "/v1/auth/password/reset", json={"token": token2, "password": "yet another phrase"}
    )
    assert expired.json()["code"] == "token_expired"


async def test_email_verification(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    bad = await client.post("/v1/auth/email/verify", json={"token": "nope"})
    assert bad.status_code == 422
    await verify_email(owner)
    assert owner.me["email_verified"] is True


def _code(secret: str, offset: int = 0) -> str:
    return pyotp.TOTP(secret).at(datetime.now(UTC) + timedelta(seconds=offset))


async def _enable_mfa(owner: Account) -> tuple[str, list[str]]:
    setup = await owner.post("/v1/auth/mfa/setup")
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    enable = await owner.post("/v1/auth/mfa/enable", json={"code": _code(secret)})
    assert enable.status_code == 200, enable.text
    return secret, enable.json()["recovery_codes"]


async def test_mfa_enable_and_login(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    secret, codes = await _enable_mfa(owner)
    assert len(codes) == 10
    assert (
        "turned on" in last_email(owner.email or "").subject.lower()
        or "on" in last_email(owner.email or "").text
    )
    step = await client.post("/v1/auth/login", json={"email": owner.email, "password": PASSWORD})
    assert step.json()["mfa_required"] is True
    assert step.json()["access_token"] is None
    challenge = step.json()["challenge"]
    bad = await client.post("/v1/auth/mfa/verify", json={"challenge": challenge, "code": "000000"})
    assert bad.status_code == 401
    # The code used to enable is spent; wait for the next step if needed.
    code = _code(secret, 30)
    good = await client.post("/v1/auth/mfa/verify", json={"challenge": challenge, "code": code})
    assert good.status_code == 200, good.text
    again = await client.post("/v1/auth/mfa/verify", json={"challenge": challenge, "code": code})
    assert again.status_code == 401


async def test_mfa_recovery_code_is_single_use(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, codes = await _enable_mfa(owner)
    for expected in (200, 401):
        challenge = (
            await client.post("/v1/auth/login", json={"email": owner.email, "password": PASSWORD})
        ).json()["challenge"]
        response = await client.post(
            "/v1/auth/mfa/verify", json={"challenge": challenge, "recovery_code": codes[0]}
        )
        assert response.status_code == expected


async def test_mfa_challenge_attempts_are_limited(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    await _enable_mfa(owner)
    challenge = (
        await client.post("/v1/auth/login", json={"email": owner.email, "password": PASSWORD})
    ).json()["challenge"]
    codes = [
        (
            await client.post("/v1/auth/mfa/verify", json={"challenge": challenge, "code": "123456"})
        ).status_code
        for _ in range(7)
    ]
    assert codes[-1] == 429


async def test_sensitive_actions_need_recent_sign_in(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client)
    await _enable_mfa(owner)
    owner_sql.execute("UPDATE auth_sessions SET reauth_at = now() - interval '1 hour'")
    stale = await owner.post("/v1/auth/mfa/disable")
    assert stale.json()["code"] == "reauth_required"
    assert (await owner.post("/v1/auth/reauth", json={"password": "wrong"})).status_code == 401
    assert (await owner.post("/v1/auth/reauth", json={"password": PASSWORD})).status_code == 204
    assert (await owner.post("/v1/auth/mfa/disable")).status_code == 204
    step = await client.post("/v1/auth/login", json={"email": owner.email, "password": PASSWORD})
    assert step.json()["mfa_required"] is False


async def test_profile_update(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    assert (await owner.patch("/v1/auth/me", json={"name": "নতুন নাম", "locale": "bn"})).status_code == 204
    me = await owner.reload()
    assert me["name"] == "নতুন নাম"
    assert me["locale"] == "bn"


async def test_verification_email_can_be_resent(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    before = len(email.sent)
    assert (await owner.post("/v1/auth/email/resend")).status_code == 202
    assert len(email.sent) == before + 1


async def test_plans_are_public(client: httpx.AsyncClient) -> None:
    plans = (await client.get("/v1/plans")).json()
    assert [p["key"] for p in plans] == ["free", "starter", "growth", "business", "enterprise"]
    assert plans[1]["price_month_cents"] == 900
    modules = (await client.get("/v1/modules")).json()
    assert any(m["key"] == "attendance" and m["available"] for m in modules)


def test_access_tokens_are_short_lived() -> None:
    from app.core.ids import uuid7
    from app.core.security.tokens import create_access_token, decode_access_token

    token, expires = create_access_token(uuid7(), uuid7(), None)
    assert expires - datetime.now(UTC) <= timedelta(minutes=get_settings().access_token_minutes, seconds=5)
    assert decode_access_token(token) is not None
    assert time.time() < expires.timestamp()
