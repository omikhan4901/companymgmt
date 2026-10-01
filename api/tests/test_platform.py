"""Route access audit, HTTP hardening and core helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pyotp
import pytest

from app.core import permissions, ratelimit
from app.core.audit import compute_hash, redact
from app.core.http import decode_cursor, encode_cursor
from app.core.ids import uuid7
from app.core.security import crypto, passwords, totp
from app.main import api_routes
from app.modules.platform import catalog
from tests.helpers import signup


def _access(route: object) -> set[str]:
    marks = set()
    for dep in getattr(route, "dependant").dependencies:  # noqa: B009
        call = dep.call
        mark = getattr(call, "_access", None)
        if mark:
            marks.add(mark)
    return marks


def test_every_route_declares_who_may_call_it() -> None:
    missing = []
    for route in api_routes():
        if not _access(route):
            missing.append(f"{sorted(route.methods)} {route.path}")
    assert not missing, f"Routes without public()/signed_in()/allow(): {missing}"


def test_public_routes_are_the_expected_few() -> None:
    public = sorted(r.path for r in api_routes() if "public" in _access(r))
    assert public == sorted(
        [
            "/v1/auth/signup",
            "/v1/auth/login",
            "/v1/auth/mfa/verify",
            "/v1/auth/refresh",
            "/v1/auth/password/forgot",
            "/v1/auth/password/reset",
            "/v1/auth/email/verify",
            "/v1/plans",
            "/v1/modules",
            "/v1/invites/lookup",
            "/v1/invites/accept",
            "/healthz",
            "/readyz",
        ]
    )


def test_permissions_referenced_by_roles_exist() -> None:
    for role in catalog.BUILTIN_ROLES:
        for grant in role.grants:
            assert grant.startswith("*") or permissions.exists(grant), (role.key, grant)
    owner = catalog.resolve("owner", True, [])
    admin = catalog.resolve("admin", True, [])
    assert "workspace.delete" in owner
    assert "workspace.delete" not in admin
    assert admin < owner
    assert catalog.resolve("employee", True, []) == {
        "attendance.self",
        "leave.self",
        "payroll.self",
        "tasks.self",
        "announcements.read",
        "documents.read",
    }
    # Custom roles never get owner-only or unknown permissions.
    assert catalog.resolve("custom-x", False, ["billing.manage", "nope", "people.view"]) == {"people.view"}


async def test_security_headers(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]


async def test_cors_only_allows_the_web_app(client: httpx.AsyncClient) -> None:
    allowed = await client.options(
        "/v1/auth/refresh",
        headers={
            "origin": "https://app.test",
            "access-control-request-method": "POST",
            "access-control-request-headers": "x-cm-client",
        },
    )
    assert allowed.headers.get("access-control-allow-origin") == "https://app.test"
    assert allowed.headers.get("access-control-allow-credentials") == "true"
    denied = await client.options(
        "/v1/auth/refresh",
        headers={"origin": "https://evil.test", "access-control-request-method": "POST"},
    )
    assert "access-control-allow-origin" not in denied.headers


@pytest.mark.parametrize(
    ("body", "headers", "status"),
    [
        (b"{not json", {"content-type": "application/json"}, 422),
        (b'{"email": 5}', {"content-type": "application/json"}, 422),
        (b"x" * 1_000_001, {"content-type": "application/json"}, 413),
        (b"[" * 5000 + b"]" * 5000, {"content-type": "application/json"}, 422),
        ("‮\u0000".encode(), {"content-type": "text/plain"}, 422),
    ],
)
async def test_malformed_and_oversized_payloads(
    client: httpx.AsyncClient, body: bytes, headers: dict[str, str], status: int
) -> None:
    response = await client.post("/v1/auth/login", content=body, headers=headers)
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/problem+json")


async def test_unknown_route_is_a_clean_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/nope")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


async def test_internal_endpoints_need_the_secret(client: httpx.AsyncClient) -> None:
    assert (await client.post("/internal/outbox/dispatch")).status_code == 404
    wrong = await client.post("/internal/outbox/dispatch", headers={"x-internal-token": "guess"})
    assert wrong.status_code == 404
    ok = await client.post("/internal/outbox/dispatch", headers={"x-internal-token": "test-internal-token"})
    assert ok.status_code == 200
    daily = await client.post(
        "/internal/maintenance/daily", headers={"x-internal-token": "test-internal-token"}
    )
    assert daily.status_code == 200


async def test_health(client: httpx.AsyncClient) -> None:
    assert (await client.get("/healthz")).json() == {"status": "ok"}
    assert (await client.get("/readyz")).json() == {"status": "ready"}


async def test_workspace_without_session_workspace(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    # A route that needs a workspace fails cleanly for a token without one.
    response = await client.get("/v1/people", headers={"authorization": "Bearer x"})
    assert response.status_code == 401
    assert (await owner.get("/v1/workspace")).status_code == 200


# ---- Core helpers -----------------------------------------------------------------------


def test_uuid7_is_time_ordered_and_versioned() -> None:
    ids = [uuid7() for _ in range(200)]
    assert all(i.version == 7 for i in ids)
    assert all(i.variant == uuid.RFC_4122 for i in ids)
    assert len(set(ids)) == 200
    assert [i.int >> 80 for i in ids] == sorted(i.int >> 80 for i in ids)


def test_field_encryption_is_bound_to_its_context() -> None:
    token = crypto.encrypt("1990123456789", context="employee:1:national_id")
    assert "1990123456789" not in token
    assert crypto.decrypt(token, context="employee:1:national_id") == "1990123456789"
    with pytest.raises(Exception):  # noqa: B017, PT011
        crypto.decrypt(token, context="employee:2:national_id")
    assert crypto.encrypt("same", context="c") != crypto.encrypt("same", context="c")


def test_password_hashing() -> None:
    hashed = passwords.hash_password("পাসওয়ার্ড ১২৩৪ ok")
    assert hashed.startswith("$argon2id$")
    assert passwords.verify_password(hashed, "পাসওয়ার্ড ১২৩৪ ok")
    assert not passwords.verify_password(hashed, "wrong")
    assert not passwords.verify_password(None, "anything")
    assert not passwords.verify_password("not-a-hash", "anything")
    # Unicode that looks the same but is encoded differently still matches (NFKC).
    assert passwords.verify_password(passwords.hash_password("ﬁsh and chips 42"), "fish and chips 42")
    assert passwords.problems("x" * 200)
    assert not passwords.problems("a long and unusual phrase")


def test_totp_drift_and_replay() -> None:
    secret = totp.new_secret()
    code = pyotp.TOTP(secret).now()
    step = totp.verify(secret, code, last_step=None)
    assert step is not None
    assert totp.verify(secret, code, last_step=step) is None
    assert totp.verify(secret, "12345", last_step=None) is None
    assert totp.verify(secret, "abc123", last_step=None) is None
    codes = totp.new_recovery_codes()
    assert len(set(codes)) == 10
    assert totp.hash_recovery_code(codes[0].upper()) == totp.hash_recovery_code(codes[0])


def test_cursor_roundtrip_and_garbage() -> None:
    assert decode_cursor(encode_cursor({"n": "রহিম", "id": "x"})) == {"n": "রহিম", "id": "x"}
    assert decode_cursor(None) is None
    from app.core.errors import Invalid

    with pytest.raises(Invalid):
        decode_cursor("!!!")
    with pytest.raises(Invalid):
        decode_cursor(encode_cursor([1, 2]))  # type: ignore[arg-type]


def test_audit_hash_changes_with_any_field() -> None:
    base = {"action": "a", "data": {"x": 1}, "occurred_at": datetime(2026, 1, 1, tzinfo=UTC)}
    h = compute_hash("0" * 64, base)
    assert h == compute_hash("0" * 64, dict(base))
    assert h != compute_hash("0" * 64, {**base, "data": {"x": 2}})
    assert h != compute_hash("1" * 64, base)
    assert redact({"password": "p", "nested": [{"token": "t", "ok": 1}]}) == {
        "password": "[redacted]",
        "nested": [{"token": "[redacted]", "ok": 1}],
    }


async def test_rate_limit_window() -> None:
    rule = ratelimit.Rule("test", 2, 60)
    assert (await ratelimit.hit(rule, "k"))[0]
    assert (await ratelimit.hit(rule, "k"))[0]
    allowed, count, retry = await ratelimit.hit(rule, "k")
    assert not allowed
    assert count == 3
    assert 0 < retry <= 60
    await ratelimit.reset(rule, "k")
    assert await ratelimit.peek(rule, "k") == 0
