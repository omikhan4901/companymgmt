"""Easy onboarding: workspace addresses, join links, sample data and the checklist."""

from __future__ import annotations

from typing import Any

import httpx

from app.modules.platform.workspaces import slug_problem
from tests.helpers import add_staff, role_id, signup


def test_reserved_and_lookalike_addresses_are_refused() -> None:
    for bad in (
        "www",
        "admin",
        "api",
        "companymgmt",
        "c0mpanymgmt",
        "company-mgmt",
        "xn--abc",
        "a--b",
        "-shop",
        "s",
    ):
        assert slug_problem(bad), bad
    for good in ("cha-ghor", "dhaka-tea-2", "rahim-store"):
        assert slug_problem(good) is None, good


async def test_owners_change_the_address_and_old_ones_stay_theirs(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    other = await signup(client)
    old = (await owner.get("/v1/workspace")).json()["slug"]
    changed = await owner.put("/v1/workspace/address", json={"slug": "cha-ghor-dhaka"})
    assert changed.status_code == 200, changed.text
    assert changed.json()["previous"] == [old]
    found = (await client.get("/v1/public/workspace", params={"slug": "cha-ghor-dhaka"})).json()
    assert found["moved_to"] is None
    moved = (await client.get("/v1/public/workspace", params={"slug": old})).json()
    assert moved["moved_to"] == "cha-ghor-dhaka"
    # Nobody else can take the new or the old address.
    for slug in ("cha-ghor-dhaka", old):
        taken = await other.put("/v1/workspace/address", json={"slug": slug})
        assert (taken.status_code, taken.json()["code"]) == (409, "slug_taken")
    reserved = await other.put("/v1/workspace/address", json={"slug": "support"})
    assert reserved.status_code == 422
    admin_role = await role_id(owner, "admin")
    _, staff = await add_staff(owner, role="admin")
    refused = await staff.put("/v1/workspace/address", json={"slug": "new-name"})
    assert (refused.status_code, refused.json()["code"]) == (403, "owner_only")
    assert admin_role


async def test_join_links_let_people_make_their_own_staff_account(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    link = await owner.post(
        "/v1/join-links", json={"role_id": await role_id(owner, "employee"), "max_uses": 1, "days": 3}
    )
    assert link.status_code == 201, link.text
    token = link.json()["token"]
    assert token
    assert (await owner.get("/v1/join-links")).json()[0]["token"] is None  # shown once
    looked = (await client.get("/v1/join/lookup", params={"token": token})).json()
    assert looked["role"] == "Employee"
    joined = await client.post(
        "/v1/join",
        json={
            "token": token,
            "name": "Mina Akter",
            "username": "mina",
            "password": "tea and biscuits every day",
        },
    )
    assert joined.status_code == 201, joined.text
    signed = await client.post(
        "/v1/auth/login",
        json={
            "workspace": joined.json()["workspace_code"],
            "username": "mina",
            "password": "tea and biscuits every day",
        },
    )
    assert signed.status_code == 200, signed.text
    # Used up after one person.
    again = await client.post(
        "/v1/join",
        json={
            "token": token,
            "name": "Someone",
            "username": "someone",
            "password": "tea and biscuits every day",
        },
    )
    assert again.json()["code"] == "join_used_up"
    # Revoked links stop working, and bad tokens tell nothing.
    second = (await owner.post("/v1/join-links", json={"role_id": await role_id(owner, "employee")})).json()
    assert (await owner.delete(f"/v1/join-links/{second['id']}")).status_code == 204
    gone = await client.get("/v1/join/lookup", params={"token": second["token"]})
    assert gone.json()["code"] == "join_invalid"
    assert (await client.get("/v1/join/lookup", params={"token": "nonsense"})).json()[
        "code"
    ] == "join_invalid"


async def test_sample_data_comes_and_goes(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    await owner.put("/v1/workspace/modules", json={"modules": ["attendance", "tasks", "sales", "customers"]})
    added = await owner.post("/v1/welcome/sample-data")
    assert added.status_code == 201, added.text
    people = (await owner.get("/v1/people")).json()["items"]
    assert any(p["full_name"].endswith("(sample)") for p in people)
    assert (await owner.post("/v1/welcome/sample-data")).status_code == 409
    removed = (await owner.delete("/v1/welcome/sample-data")).json()
    assert removed == {"present": False, "records": 0}
    people = (await owner.get("/v1/people")).json()["items"]
    assert not any(p["full_name"].endswith("(sample)") for p in people)
    products: list[dict[str, Any]] = (await owner.get("/v1/sales/products")).json()
    assert not any(p["name"].endswith("(sample)") for p in products)


async def test_the_first_day_checklist(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    first = (await owner.get("/v1/welcome/checklist")).json()
    done = {i["key"]: i["done"] for i in first["items"]}
    assert done["team"] is False
    await add_staff(owner)
    done = {i["key"]: i["done"] for i in (await owner.get("/v1/welcome/checklist")).json()["items"]}
    assert done["team"] is True
    hidden = (await owner.put("/v1/welcome/checklist", json={"hidden": True})).json()
    assert hidden["dismissed"] is True
    _, staff = await add_staff(owner)
    assert (await staff.get("/v1/welcome/checklist")).status_code == 403
