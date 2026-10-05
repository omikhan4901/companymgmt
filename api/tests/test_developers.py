"""The developer platform: API keys (scoped, rate limited, rotated, logged), the workspace
network allowlist, Idempotency-Key replays, and signed webhooks that never reach private
networks."""

from __future__ import annotations

import ipaddress
import json
from typing import Any

import httpx
import psycopg
import pytest

from app.core import ipnet, outbox, safehttp
from app.modules.platform import webhooks
from tests.helpers import Account, add_staff, signup


def on_plan(sql: psycopg.Connection, account: Account, plan: str = "business") -> None:
    sql.execute("SELECT set_config('app.tenant_id', %s, false)", (account.tenant_id,))
    sql.execute(
        "UPDATE subscriptions SET plan_key = %s, status = 'active', trial_plan_key = NULL "
        "WHERE tenant_id = %s",
        (plan, account.tenant_id),
    )


def key_headers(token: str, **extra: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", **extra}


async def make_key(owner: Account, **body: Any) -> dict[str, Any]:
    response = await owner.post(
        "/v1/api-keys", json={"name": "Payroll sync", "permissions": ["members.view"], **body}
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def test_keys_need_a_plan_with_the_api(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    response = await owner.post("/v1/api-keys", json={"name": "x", "permissions": ["members.view"]})
    assert (response.status_code, response.json()["code"]) == (402, "api_not_in_plan")


async def test_a_key_acts_as_its_maker_with_only_its_permissions(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client)
    on_plan(owner_sql, owner)
    key = await make_key(owner)
    token = key["token"]
    assert token.startswith("cmk_")
    assert key["hint"] == token.split("_", 2)[2][:6]

    members = await client.get("/v1/members", headers=key_headers(token))
    assert members.status_code == 200, members.text
    # Not given: changing settings.
    refused = await client.put("/v1/workspace/modules", json={"modules": []}, headers=key_headers(token))
    assert refused.status_code == 403
    # Account routes never take keys.
    me = await client.get("/v1/auth/sessions", headers=key_headers(token))
    assert (me.status_code, me.json()["code"]) == (403, "api_key_not_allowed")
    # Keys can't make keys.
    minted = await client.post(
        "/v1/api-keys", json={"name": "y", "permissions": ["members.view"]}, headers=key_headers(token)
    )
    assert minted.status_code == 403

    # Owner-only powers and permissions you don't hold can't be given.
    bad = await owner.post("/v1/api-keys", json={"name": "z", "permissions": ["billing.manage"]})
    assert bad.status_code == 422

    usage = (await owner.get(f"/v1/api-keys/{key['id']}/usage")).json()
    assert usage[-1]["requests"] >= 3
    listed = (await owner.get("/v1/api-keys")).json()
    assert listed[0]["last_used_at"] is not None
    assert "token" not in listed[0] or listed[0]["token"] is None


async def test_a_key_shrinks_with_its_maker(client: httpx.AsyncClient, owner_sql: psycopg.Connection) -> None:
    owner = await signup(client)
    on_plan(owner_sql, owner)
    member, admin = await add_staff(owner, role="admin")
    key = await make_key(admin)
    assert (await client.get("/v1/members", headers=key_headers(key["token"]))).status_code == 200
    removed = await owner.delete(f"/v1/members/{member['member']['id']}")
    assert removed.status_code == 204, removed.text
    gone = await client.get("/v1/members", headers=key_headers(key["token"]))
    assert (gone.status_code, gone.json()["code"]) == (401, "api_key_owner_gone")


async def test_rotation_keeps_the_old_secret_for_the_grace_period(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client)
    on_plan(owner_sql, owner)
    key = await make_key(owner)
    rotated = (await owner.post(f"/v1/api-keys/{key['id']}/rotate", json={"grace_hours": 1})).json()
    assert rotated["token"] != key["token"]
    for token in (key["token"], rotated["token"]):
        assert (await client.get("/v1/members", headers=key_headers(token))).status_code == 200
    again = (await owner.post(f"/v1/api-keys/{key['id']}/rotate", json={"grace_hours": 0})).json()
    assert (await client.get("/v1/members", headers=key_headers(rotated["token"]))).status_code == 401
    assert (await owner.delete(f"/v1/api-keys/{key['id']}")).status_code == 204
    assert (await client.get("/v1/members", headers=key_headers(again["token"]))).status_code == 401


async def test_keys_are_rate_limited_and_can_be_tied_to_networks(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client)
    on_plan(owner_sql, owner)
    limited = await make_key(owner, rate_per_minute=10)
    headers = key_headers(limited["token"])
    statuses = [(await client.get("/v1/members", headers=headers)).status_code for _ in range(11)]
    assert statuses[-1] == 429
    assert set(statuses[:-1]) == {200}

    # The test client calls from 203.0.113.10.
    elsewhere = await make_key(owner, allowed_ips=["198.51.100.0/24"])
    refused = await client.get("/v1/members", headers=key_headers(elsewhere["token"]))
    assert (refused.status_code, refused.json()["code"]) == (403, "ip_not_allowed")
    here = await make_key(owner, allowed_ips=["203.0.113.0/24"])
    assert (await client.get("/v1/members", headers=key_headers(here["token"]))).status_code == 200


async def test_workspace_allowlist_never_locks_the_owner_out(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client)
    on_plan(owner_sql, owner, "enterprise")
    lockout = await owner.put("/v1/workspace/ip-allowlist", json={"entries": ["198.51.100.0/24"]})
    assert lockout.status_code == 422
    saved = await owner.put("/v1/workspace/ip-allowlist", json={"entries": ["203.0.113.10"]})
    assert saved.json()["entries"] == ["203.0.113.10/32"]
    assert (await owner.get("/v1/members")).status_code == 200
    owner_sql.execute(
        "UPDATE tenants SET ip_allowlist = '[\"198.51.100.0/24\"]' WHERE id = %s", (owner.tenant_id,)
    )
    blocked = await owner.get("/v1/members")
    assert (blocked.status_code, blocked.json()["code"]) == (403, "ip_not_allowed")


async def test_idempotency_keys_replay_the_first_response(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client)
    on_plan(owner_sql, owner)
    key = await make_key(owner, permissions=["branches.manage", "members.view"])
    headers = key_headers(key["token"], **{"Idempotency-Key": "branch-1"})
    first = await client.post("/v1/branches", json={"name": "Uttara"}, headers=headers)
    assert first.status_code == 201, first.text
    again = await client.post("/v1/branches", json={"name": "Uttara"}, headers=headers)
    assert again.status_code == 201
    assert again.json() == first.json()
    assert again.headers["idempotent-replayed"] == "true"
    other = await client.post("/v1/branches", json={"name": "Banani"}, headers=headers)
    assert (other.status_code, other.json()["code"]) == (422, "idempotency_key_reused")
    # Signed-in people can use them too.
    mine = {"Idempotency-Key": "b2"}
    made = await owner.post("/v1/branches", json={"name": "Gulshan"}, headers=mine)
    assert (await owner.post("/v1/branches", json={"name": "Gulshan"}, headers=mine)).json() == made.json()


def test_addresses_must_be_public() -> None:
    for bad in (
        "http://example.com/hook",
        "https://localhost/hook",
        "https://10.0.0.5/hook",
        "https://169.254.169.254/latest/meta-data",
        "https://[::1]/hook",
        "https://[::ffff:127.0.0.1]/hook",
        "https://user:pw@example.com/hook",
        "https://example.com:6379/hook",
        "https://metadata.internal/hook",
    ):
        with pytest.raises(webhooks.UnsafeAddress):
            webhooks.check_url(bad)
    assert webhooks.check_url("https://Example.com") == "https://example.com/"
    for private in ("100.64.0.1", "192.168.1.1", "fd00::1", "224.0.0.1", "0.0.0.0"):  # noqa: S104
        assert not ipnet.is_public(ipaddress.ip_address(private))
    assert ipnet.is_public(ipaddress.ip_address("93.184.216.34"))


async def test_names_that_resolve_to_private_networks_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    async def rebinding(host: str, port: int) -> list[str]:
        return ["93.184.216.34", "127.0.0.1"]

    monkeypatch.setattr(safehttp, "resolve", rebinding)
    with pytest.raises(webhooks.UnsafeAddress):
        await safehttp.pinned_target("https://hooks.example.com/x")


def test_signatures() -> None:
    body = b'{"id":"1"}'
    header = webhooks.sign("whsec_abc", body, 1_700_000_000)
    assert webhooks.verify("whsec_abc", body, header, now=1_700_000_100)
    assert not webhooks.verify("whsec_abc", body + b" ", header, now=1_700_000_100)
    assert not webhooks.verify("whsec_other", body, header, now=1_700_000_100)
    # Too old: replayed.
    assert not webhooks.verify("whsec_abc", body, header, now=1_700_001_000)


async def test_webhooks_are_signed_thin_and_retried(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    received: list[httpx.Request] = []
    answers = iter([500, 200, 200, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(request)
        return httpx.Response(next(answers, 200))

    async def public_dns(host: str, port: int) -> list[str]:
        return ["93.184.216.34"]

    monkeypatch.setattr(safehttp, "transport", httpx.MockTransport(handler))
    monkeypatch.setattr(safehttp, "resolve", public_dns)

    owner = await signup(client)
    on_plan(owner_sql, owner)
    created = await owner.post(
        "/v1/webhooks", json={"url": "https://hooks.example.com/cm", "events": ["employee.onboarded"]}
    )
    assert created.status_code == 201, created.text
    endpoint = created.json()
    secret = endpoint["secret"]
    assert secret.startswith("whsec_")
    assert (await owner.get("/v1/webhooks")).json()[0]["secret"] is None

    ping = (await owner.post(f"/v1/webhooks/{endpoint['id']}/test")).json()
    assert ping["status"] == "failed"  # the first answer was a 500
    request = received[-1]
    # The connection goes to the checked address; the name rides in Host and SNI.
    assert request.url.host == "93.184.216.34"
    assert request.headers["host"] == "hooks.example.com"
    assert webhooks.verify(secret, request.content, request.headers["companymgmt-signature"])

    await add_staff(owner, name="Karim Mia")
    for _ in range(3):
        await outbox.dispatch()
    sent = json.loads(received[-1].content)
    assert sent["type"] == "employee.onboarded"
    assert set(sent["data"]) == {"membership_id"}
    assert "Karim" not in received[-1].content.decode()

    deliveries = (await owner.get(f"/v1/webhooks/{endpoint['id']}/deliveries")).json()
    assert deliveries[0]["status"] == "succeeded"
    resent = (await owner.post(f"/v1/webhooks/deliveries/{deliveries[0]['id']}/resend")).json()
    assert resent["event_id"] == deliveries[0]["event_id"]

    refused = await owner.post("/v1/webhooks", json={"url": "https://10.1.2.3/x", "events": ["*"]})
    assert refused.status_code == 422


async def test_failed_deliveries_back_off(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def public_dns(host: str, port: int) -> list[str]:
        return ["93.184.216.34"]

    monkeypatch.setattr(safehttp, "transport", httpx.MockTransport(lambda r: httpx.Response(503)))
    monkeypatch.setattr(safehttp, "resolve", public_dns)
    owner = await signup(client)
    on_plan(owner_sql, owner)
    endpoint = (
        await owner.post("/v1/webhooks", json={"url": "https://hooks.example.com/cm", "events": ["*"]})
    ).json()
    await add_staff(owner)
    for _ in range(3):
        await outbox.dispatch()
    [delivery] = (await owner.get(f"/v1/webhooks/{endpoint['id']}/deliveries")).json()
    assert (delivery["status"], delivery["attempts"], delivery["response_status"]) == ("pending", 1, 503)
    assert delivery["next_attempt_at"] is not None
    # Not due yet: nothing is sent.
    assert await webhooks.deliver_due() == 0
