"""People and departments."""

from __future__ import annotations

import httpx
import psycopg
import pytest

from tests.helpers import add_staff, if_match, invite_and_join, role_id, signup


async def test_owner_has_a_profile(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    me = (await owner.get("/v1/people/me")).json()
    assert me["full_name"] == "Rahim Uddin"
    assert me["membership_id"] == owner.membership_id


async def test_department_tree_rules(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    ops = (await owner.post("/v1/departments", json={"name": "Operations"})).json()
    kitchen = (await owner.post("/v1/departments", json={"name": "Kitchen", "parent_id": ops["id"]})).json()
    night = (
        await owner.post("/v1/departments", json={"name": "Night shift", "parent_id": kitchen["id"]})
    ).json()
    # Same name under the same parent (any case) is refused; elsewhere it's fine.
    assert (
        await owner.post("/v1/departments", json={"name": "kitchen", "parent_id": ops["id"]})
    ).status_code == 422
    assert (await owner.post("/v1/departments", json={"name": "Kitchen"})).status_code == 201
    # No loops: a department can't move under itself or its descendants.
    for parent in (ops["id"], night["id"]):
        loop = await owner.patch(
            f"/v1/departments/{ops['id']}", json={"parent_id": parent}, headers=if_match(ops["version"])
        )
        assert loop.status_code == 422, parent
    moved = await owner.patch(
        f"/v1/departments/{night['id']}", json={"move_to_top": True}, headers=if_match(night["version"])
    )
    assert moved.json()["parent_id"] is None
    assert (await owner.delete(f"/v1/departments/{ops['id']}")).json()["code"] == "department_has_children"
    await owner.post("/v1/people", json={"full_name": "Cook", "department_id": kitchen["id"]})
    assert (await owner.delete(f"/v1/departments/{kitchen['id']}")).json()["code"] == "department_has_people"
    assert (await owner.delete(f"/v1/departments/{night['id']}")).status_code == 204
    listed = {d["name"]: d for d in (await owner.get("/v1/departments")).json()}
    assert listed["Kitchen"]["people"] in (0, 1)
    assert (await owner.post("/v1/departments", json={"name": "   "})).status_code == 422
    assert (
        await owner.post(
            "/v1/departments",
            json={"name": "X", "parent_id": owner.tenant_id},
        )
    ).status_code == 422


@pytest.mark.parametrize(
    "name",
    ["মোঃ আব্দুল করিম", "عبد الله بن محمد", "Zoë O'Brien-Łukasz", "李小龍", "🍵 Cha Wala", "A" * 200],
)
async def test_names_in_any_script(client: httpx.AsyncClient, name: str) -> None:
    owner = await signup(client)
    created = await owner.post("/v1/people", json={"full_name": name})
    assert created.status_code == 201, created.text
    assert created.json()["full_name"] == name
    found = (await owner.get("/v1/people", params={"q": name[:4]})).json()["items"]
    assert any(p["full_name"] == name for p in found)


async def test_person_validation(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    assert (await owner.post("/v1/people", json={"full_name": "A" * 201})).status_code == 422
    assert (
        await owner.post("/v1/people", json={"full_name": "X", "date_of_birth": "2999-01-01"})
    ).status_code == 422
    assert (await owner.post("/v1/people", json={"full_name": "X", "phone": "call me"})).status_code == 422
    assert (
        await owner.post("/v1/people", json={"full_name": "X", "employment_type": "slave"})
    ).status_code == 422
    first = await owner.post("/v1/people", json={"full_name": "X", "employee_code": "E-001"})
    assert first.status_code == 201
    assert (
        await owner.post("/v1/people", json={"full_name": "Y", "employee_code": "e-001"})
    ).status_code == 422
    # Search wildcards are literal.
    assert (await owner.get("/v1/people", params={"q": "%"})).json()["items"] == []


async def test_national_id_is_encrypted_and_masked(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client)
    person = (
        await owner.post("/v1/people", json={"full_name": "Jamal", "national_id": "19901234567890123"})
    ).json()
    assert person["national_id_last4"] == "0123"
    assert "national_id" not in person
    owner_sql.execute("SELECT set_config('app.tenant_id', %s, false)", (owner.tenant_id,))
    stored = owner_sql.execute(
        "SELECT national_id_enc FROM employees WHERE id = %s", (person["id"],)
    ).fetchone()
    assert stored is not None
    assert "19901234567890123" not in stored[0]
    audit = (await owner.get("/v1/audit", params={"target_id": person["id"]})).json()["items"]
    assert "19901234567890123" not in str(audit)


async def test_edit_person_with_concurrency(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    person = (await owner.post("/v1/people", json={"full_name": "Jamal", "phone": "+880 1711-000000"})).json()
    url = f"/v1/people/{person['id']}"
    assert (await owner.patch(url, json={"job_title": "Cook"})).status_code == 428
    first = await owner.patch(url, json={"job_title": "Cook"}, headers=if_match(person["version"]))
    assert first.status_code == 200
    assert first.headers["etag"] == 'W/"2"'
    # A second manager editing the same old version is told to reload.
    stale = await owner.patch(url, json={"job_title": "Chef"}, headers=if_match(person["version"]))
    assert stale.status_code == 412
    cleared = await owner.patch(url, json={"clear": ["phone"]}, headers=if_match(2))
    assert cleared.json()["phone"] is None
    left = await owner.patch(url, json={"status": "left"}, headers=if_match(3))
    assert left.json()["left_on"] is not None
    bad_dates = await owner.patch(url, json={"joined_on": "2030-01-01"}, headers=if_match(4))
    assert bad_dates.status_code == 422


async def test_people_limit(client: httpx.AsyncClient, owner_sql: psycopg.Connection) -> None:
    owner = await signup(client)
    owner_sql.execute("SELECT set_config('app.tenant_id', %s, false)", (owner.tenant_id,))
    owner_sql.execute("UPDATE subscriptions SET trial_ends_at = now() - interval '1 day'")
    for i in range(4):
        assert (await owner.post("/v1/people", json={"full_name": f"P{i}"})).status_code == 201
    over = await owner.post("/v1/people", json={"full_name": "Sixth"})
    assert over.status_code == 402
    assert over.json()["code"] == "people_limit"
    # Members count too: adding staff over the limit is refused as a whole.
    staff = await owner.post(
        "/v1/members/staff",
        json={"name": "S", "username": "sss", "role_id": await role_id(owner, "employee")},
    )
    assert staff.status_code == 402
    members = (await owner.get("/v1/members")).json()["items"]
    assert len(members) == 1


async def test_manager_sees_only_their_department(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    ops = (await owner.post("/v1/departments", json={"name": "Operations"})).json()
    kitchen = (await owner.post("/v1/departments", json={"name": "Kitchen", "parent_id": ops["id"]})).json()
    sales = (await owner.post("/v1/departments", json={"name": "Sales"})).json()
    cook = (await owner.post("/v1/people", json={"full_name": "Cook", "department_id": kitchen["id"]})).json()
    seller = (
        await owner.post("/v1/people", json={"full_name": "Seller", "department_id": sales["id"]})
    ).json()
    manager = await invite_and_join(owner, role="manager", scope_department_id=ops["id"])
    names = {p["full_name"] for p in (await manager.get("/v1/people")).json()["items"]}
    assert "Cook" in names
    assert "Seller" not in names
    assert (await manager.get(f"/v1/people/{seller['id']}")).status_code == 404
    assert (await manager.get(f"/v1/people/{cook['id']}")).status_code == 200
    # Managers can't add or move people outside their scope (people.manage isn't in the
    # built-in manager role at all).
    assert (
        await manager.post("/v1/people", json={"full_name": "New", "department_id": sales["id"]})
    ).status_code == 403


async def test_employee_sees_only_self(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    other = (await owner.post("/v1/people", json={"full_name": "Other"})).json()
    _, staff = await add_staff(owner)
    me = (await staff.get("/v1/people/me")).json()
    assert (await staff.get(f"/v1/people/{me['id']}")).status_code == 200
    assert (await staff.get(f"/v1/people/{other['id']}")).status_code == 403
    assert (await staff.get("/v1/people")).status_code == 403


async def test_people_pagination(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    for i in range(7):
        await owner.post("/v1/people", json={"full_name": f"Person {i:02d}"})
    seen: list[str] = []
    cursor = None
    while True:
        params = {"limit": 3, **({"cursor": cursor} if cursor else {})}
        page = (await owner.get("/v1/people", params=params)).json()
        seen += [p["full_name"] for p in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(seen) == 8
    assert seen == sorted(seen, key=str.lower)
