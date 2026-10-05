"""Company sign-in (OpenID Connect) against a pretend provider, the workspace's own AI
key, and the audit log export."""

from __future__ import annotations

import itertools
import json
import time
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import psycopg
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core import safehttp
from tests.helpers import Account, if_match, invite_and_join, signup

ISSUER = "https://idp.example.com"
WEB = {"x-cm-client": "web"}


class Provider:
    """A tiny OpenID provider: discovery, keys, and a token endpoint."""

    def __init__(self) -> None:
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.claims: dict[str, Any] = {}
        self.nonce = ""
        self.token_requests: list[httpx.Request] = []

    def jwks(self) -> dict[str, Any]:
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        return {"keys": [{**jwk, "kid": "k1", "use": "sig", "alg": "RS256"}]}

    def id_token(self) -> str:
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "aud": "client-1",
            "sub": "user-123",
            "iat": now,
            "exp": now + 300,
            "nonce": self.nonce,
            "email": "nadia@acme.example",
            "email_verified": True,
            "name": "Nadia Rahman",
            **self.claims,
        }
        return jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": "k1"})

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/.well-known/openid-configuration":
            return httpx.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": f"{ISSUER}/authorize",
                    "token_endpoint": f"{ISSUER}/token",
                    "jwks_uri": f"{ISSUER}/jwks",
                },
            )
        if path == "/jwks":
            return httpx.Response(200, json=self.jwks())
        if path == "/token":
            self.token_requests.append(request)
            return httpx.Response(200, json={"id_token": self.id_token(), "access_token": "x"})
        return httpx.Response(404)


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> Provider:
    idp = Provider()

    async def public_dns(host: str, port: int) -> list[str]:
        return ["93.184.216.34"]

    monkeypatch.setattr(safehttp, "resolve", public_dns)
    monkeypatch.setattr(safehttp, "transport", httpx.MockTransport(idp.handle))
    return idp


def on_plan(sql: psycopg.Connection, account: Account, plan: str = "enterprise") -> None:
    sql.execute("SELECT set_config('app.tenant_id', %s, false)", (account.tenant_id,))
    sql.execute(
        "UPDATE subscriptions SET plan_key = %s, status = 'active', trial_plan_key = NULL "
        "WHERE tenant_id = %s",
        (plan, account.tenant_id),
    )


async def set_up(owner: Account, **extra: Any) -> dict[str, Any]:
    current = (await owner.get("/v1/sso/settings")).json()["connection"]
    headers = if_match(current["version"]) if current else {}
    response = await owner.put(
        "/v1/sso/settings",
        headers=headers,
        json={
            "issuer": ISSUER,
            "client_id": "client-1",
            "client_secret": "shh-secret",
            "domains": ["Acme.example"],
            **extra,
        },
    )
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


async def sign_in(client: httpx.AsyncClient, idp: Provider, slug: str) -> httpx.Response:
    started = await client.post("/v1/sso/start", json={"workspace": slug, "next": "/app/leave"})
    assert started.status_code == 200, started.text
    query = parse_qs(urlsplit(started.json()["url"]).query)
    assert query["code_challenge_method"] == ["S256"]
    idp.nonce = query["nonce"][0]
    return await client.post(
        "/v1/sso/callback", json={"state": query["state"][0], "code": "abc"}, headers=WEB
    )


async def test_sso_needs_the_plan(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    assert (await owner.get("/v1/sso/settings")).status_code == 402


async def test_company_sign_in_end_to_end(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection, provider: Provider
) -> None:
    owner = await signup(client)
    on_plan(owner_sql, owner)
    saved = await set_up(owner)
    assert saved["domains"] == ["acme.example"]
    assert saved["redirect_uri"].endswith("/sso/callback")
    workspace = (await owner.get("/v1/workspace")).json()
    lookup = (await client.get("/v1/public/workspace", params={"slug": workspace["slug"]})).json()
    assert (lookup["sso"], lookup["sso_required"]) == (True, False)
    # Not a member and no auto-join: refused.
    refused = await sign_in(client, provider, workspace["slug"])
    assert (refused.status_code, refused.json()["code"]) == (401, "sso_failed")

    await set_up(owner, auto_join=True, client_secret=None)
    signed_in = await sign_in(client, provider, workspace["slug"])
    assert signed_in.status_code == 200, signed_in.text
    assert signed_in.json()["next"] == "/app/leave"
    token = signed_in.json()["access_token"]
    me = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    # The client secret went to the provider, not in the browser.
    assert provider.token_requests[-1].headers["authorization"].startswith("Basic ")

    # A state works once.
    started = await client.post("/v1/sso/start", json={"workspace": workspace["slug"]})
    state = parse_qs(urlsplit(started.json()["url"]).query)["state"][0]
    provider.nonce = parse_qs(urlsplit(started.json()["url"]).query)["nonce"][0]
    assert (
        await client.post("/v1/sso/callback", json={"state": state, "code": "x"}, headers=WEB)
    ).status_code == 200
    again = await client.post("/v1/sso/callback", json={"state": state, "code": "x"}, headers=WEB)
    assert again.json()["code"] == "sso_state_invalid"


async def test_tokens_that_dont_check_out_are_refused(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection, provider: Provider
) -> None:
    owner = await signup(client)
    on_plan(owner_sql, owner)
    await set_up(owner, auto_join=True)
    slug = (await owner.get("/v1/workspace")).json()["slug"]
    for bad in (
        {"aud": "someone-else"},
        {"iss": "https://evil.example.com"},
        {"exp": int(time.time()) - 3600},
        {"email": "nadia@other.example"},
        {"email_verified": False},
    ):
        provider.claims = bad
        response = await sign_in(client, provider, slug)
        assert response.status_code == 401, (bad, response.text)
    provider.claims = {}
    wrong_nonce = await client.post("/v1/sso/start", json={"workspace": slug})
    state = parse_qs(urlsplit(wrong_nonce.json()["url"]).query)["state"][0]
    provider.nonce = "not-the-one"
    assert (
        await client.post("/v1/sso/callback", json={"state": state, "code": "x"}, headers=WEB)
    ).status_code == 401


async def test_required_sso_shuts_the_password_door_except_for_the_owner(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection, provider: Provider
) -> None:
    owner = await signup(client)
    on_plan(owner_sql, owner)
    admin = await invite_and_join(owner, role="admin")
    assert (await admin.get("/v1/members")).status_code == 200
    await set_up(owner, enforce=True)
    blocked = await admin.get("/v1/members")
    assert (blocked.status_code, blocked.json()["code"]) == (403, "sso_required")
    assert (await owner.get("/v1/members")).status_code == 200


async def test_own_ai_key(client: httpx.AsyncClient, owner_sql: psycopg.Connection) -> None:
    owner = await signup(client)
    assert (await owner.put("/v1/ai/own-key", json={"key": "AIza" + "x" * 30})).status_code == 402
    on_plan(owner_sql, owner)
    status = (await owner.put("/v1/ai/own-key", json={"key": "AIza" + "x" * 30})).json()
    assert (status["own_key"], status["own_key_hint"], status["available"]) == (True, "xxxx", True)
    removed = (await owner.delete("/v1/ai/own-key")).json()
    assert removed["own_key"] is False


async def test_audit_export(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    await owner.post("/v1/branches", json={"name": "Uttara"})
    today = time.strftime("%Y-%m-%d", time.gmtime())
    jsonl = await owner.get("/v1/audit/export", params={"from": today, "to": today})
    assert jsonl.status_code == 200, jsonl.text
    lines = [json.loads(line) for line in jsonl.text.splitlines()]
    assert lines
    assert all(b["prev_hash"] == a["hash"] for a, b in itertools.pairwise(lines))
    csv = await owner.get("/v1/audit/export", params={"from": today, "to": today, "format": "csv"})
    assert csv.text.splitlines()[0].startswith("seq,occurred_at")
