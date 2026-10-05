"""SCIM provisioning the way Okta and Entra drive it, and sandbox workspaces."""

from __future__ import annotations

from typing import Any

import httpx
import psycopg

from tests.helpers import Account, signup

SCIM = "application/scim+json"


def on_plan(sql: psycopg.Connection, account: Account, plan: str = "enterprise") -> None:
    sql.execute("SELECT set_config('app.tenant_id', %s, false)", (account.tenant_id,))
    sql.execute(
        "UPDATE subscriptions SET plan_key = %s, status = 'active', trial_plan_key = NULL "
        "WHERE tenant_id = %s",
        (plan, account.tenant_id),
    )


async def scim_key(owner: Account) -> dict[str, str]:
    key = await owner.post(
        "/v1/api-keys",
        json={"name": "Okta", "permissions": ["members.view", "members.invite", "members.manage"]},
    )
    assert key.status_code == 201, key.text
    return {"Authorization": f"Bearer {key.json()['token']}", "Content-Type": SCIM}


def user(email: str, **extra: Any) -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "userName": email,
        "name": {"givenName": "Nadia", "familyName": "Rahman"},
        "emails": [{"value": email, "primary": True}],
        "externalId": "00u1",
        "active": True,
        **extra,
    }


async def test_provisioning_lifecycle(client: httpx.AsyncClient, owner_sql: psycopg.Connection) -> None:
    owner = await signup(client)
    on_plan(owner_sql, owner)
    headers = await scim_key(owner)

    config = await client.get("/scim/v2/ServiceProviderConfig", headers=headers)
    assert config.json()["patch"]["supported"] is True

    created = await client.post("/scim/v2/Users", json=user("nadia@acme.example"), headers=headers)
    assert created.status_code == 201, created.text
    assert created.headers["content-type"].startswith(SCIM)
    member = created.json()
    assert (member["userName"], member["active"], member["displayName"]) == (
        "nadia@acme.example",
        True,
        "Nadia Rahman",
    )

    again = await client.post("/scim/v2/Users", json=user("nadia@acme.example"), headers=headers)
    assert again.status_code == 409

    found = await client.get(
        "/scim/v2/Users", params={"filter": 'userName eq "NADIA@acme.example"'}, headers=headers
    )
    assert found.json()["totalResults"] == 1
    by_external = await client.get(
        "/scim/v2/Users", params={"filter": 'externalId eq "00u1"'}, headers=headers
    )
    assert by_external.json()["Resources"][0]["id"] == member["id"]

    # Entra's way of switching someone off: no path, a value object.
    off = await client.patch(
        f"/scim/v2/Users/{member['id']}",
        json={
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": "Replace", "value": {"active": False}}],
        },
        headers=headers,
    )
    assert off.json()["active"] is False
    members = (await owner.get("/v1/members")).json()["items"]
    assert all(m["email"] != "nadia@acme.example" or m["status"] == "removed" for m in members)

    # Okta's way back on.
    on = await client.patch(
        f"/scim/v2/Users/{member['id']}",
        json={"Operations": [{"op": "replace", "path": "active", "value": "true"}]},
        headers=headers,
    )
    assert on.json()["active"] is True
    assert (await client.delete(f"/scim/v2/Users/{member['id']}", headers=headers)).status_code == 204
    assert (await client.get(f"/scim/v2/Users/{member['id']}", headers=headers)).json()["active"] is False
    assert (await client.get("/scim/v2/Users/not-an-id", headers=headers)).status_code == 404


async def test_the_owner_cant_be_deprovisioned(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client)
    on_plan(owner_sql, owner)
    headers = await scim_key(owner)
    listed = (await client.get("/scim/v2/Users", headers=headers)).json()["Resources"]
    owner_id = listed[0]["id"]
    refused = await client.delete(f"/scim/v2/Users/{owner_id}", headers=headers)
    assert refused.status_code == 403


async def test_scim_needs_the_plan(client: httpx.AsyncClient, owner_sql: psycopg.Connection) -> None:
    owner = await signup(client)
    on_plan(owner_sql, owner, "business")
    headers = await scim_key(owner)
    assert (await client.get("/scim/v2/Users", headers=headers)).status_code == 402


async def test_sandbox(client: httpx.AsyncClient, owner_sql: psycopg.Connection) -> None:
    owner = await signup(client)
    on_plan(owner_sql, owner, "business")
    made = await owner.post("/v1/workspace/sandbox")
    assert made.status_code == 201, made.text
    assert made.json()["name"].endswith("(sandbox)")
    assert (await owner.post("/v1/workspace/sandbox")).status_code == 409
