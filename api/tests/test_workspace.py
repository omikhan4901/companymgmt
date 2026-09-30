"""Workspace settings, modules, roles, members, staff accounts, invites, branches, audit."""

from __future__ import annotations

import httpx
import psycopg

from tests.helpers import (
    PASSWORD,
    Account,
    add_staff,
    if_match,
    invite_and_join,
    last_email,
    link_token,
    login,
    role_id,
    signup,
    verify_email,
)


def as_tenant(sql: psycopg.Connection, account: Account) -> psycopg.Connection:
    """Direct SQL in a workspace (row-level security applies to the owner role too)."""
    sql.execute("SELECT set_config('app.tenant_id', %s, false)", (account.tenant_id,))
    return sql


def end_trial(sql: psycopg.Connection, account: Account) -> None:
    as_tenant(sql, account).execute("UPDATE subscriptions SET trial_ends_at = now() - interval '1 day'")


async def test_workspace_settings(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    response = await owner.patch(
        "/v1/workspace",
        json={"name": "Rahim Enterprises", "timezone": "Europe/London", "ui_mode": "advanced"},
    )
    assert response.status_code == 200
    assert response.json()["timezone"] == "Europe/London"
    bad = await owner.patch("/v1/workspace", json={"timezone": "Nowhere/Land"})
    assert bad.status_code == 422
    audit = (await owner.get("/v1/audit", params={"action": "workspace.updated"})).json()["items"]
    assert audit[0]["data"]["after"]["name"] == "Rahim Enterprises"


async def test_employees_cannot_change_settings(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner)
    assert (await staff.patch("/v1/workspace", json={"name": "Mine now"})).status_code == 403
    assert (await staff.get("/v1/members")).status_code == 403
    assert (await staff.get("/v1/audit")).status_code == 403
    assert (await staff.get("/v1/workspace")).status_code == 200


async def test_modules_respect_requirements_and_plan(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client, business_type="office")
    assert (await owner.put("/v1/workspace/modules", json={"modules": ["attendance"]})).json() == [
        "attendance"
    ]
    assert (await owner.put("/v1/workspace/modules", json={"modules": ["payroll"]})).status_code == 422
    assert (await owner.put("/v1/workspace/modules", json={"modules": ["rocket"]})).status_code == 422
    # Switching attendance off hides it but keeps the data.
    assert (await owner.put("/v1/workspace/modules", json={"modules": []})).status_code == 200
    off = await owner.get("/v1/attendance/status")
    assert off.status_code == 402
    assert off.json()["code"] == "module_off"
    assert (await owner.put("/v1/workspace/modules", json={"modules": ["attendance"]})).status_code == 200
    assert (await owner.get("/v1/attendance/status")).status_code == 200


async def test_trial_ends_on_free_plan(client: httpx.AsyncClient, owner_sql: psycopg.Connection) -> None:
    owner = await signup(client)
    end_trial(owner_sql, owner)
    me = await owner.reload()
    plan = me["workspace"]["plan"]
    assert plan["key"] == "free"
    assert plan["status"] == "active"
    # Custom roles are a Growth feature.
    response = await owner.post("/v1/roles", json={"name": "Lead", "permissions": ["people.view"]})
    assert response.status_code == 402
    # Free includes one branch.
    assert (await owner.post("/v1/branches", json={"name": "Second"})).json()["code"] == "branch_limit"


async def test_read_only_workspace_blocks_writes_not_reads(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client)
    as_tenant(owner_sql, owner).execute("UPDATE subscriptions SET status = 'read_only'")
    blocked = await owner.post("/v1/departments", json={"name": "Sales"})
    assert blocked.status_code == 402
    assert blocked.json()["code"] == "workspace_read_only"
    assert (await owner.get("/v1/departments")).status_code == 200
    assert (
        await owner.get("/v1/attendance/export.csv", params={"from": "2026-01-01", "to": "2026-01-31"})
    ).status_code == 200


async def test_custom_roles(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    perms = (await owner.get("/v1/permissions")).json()
    assert any(p["key"] == "attendance.approve" for p in perms)
    unknown = await owner.post("/v1/roles", json={"name": "X", "permissions": ["people.fly"]})
    assert unknown.status_code == 422
    owner_only = await owner.post("/v1/roles", json={"name": "X", "permissions": ["billing.manage"]})
    assert owner_only.status_code == 422
    created = await owner.post(
        "/v1/roles", json={"name": "Shift lead", "permissions": ["attendance.view", "attendance.approve"]}
    )
    assert created.status_code == 201
    rid = created.json()["id"]
    updated = await owner.patch(f"/v1/roles/{rid}", json={"permissions": ["attendance.view"]})
    assert updated.json()["permissions"] == ["attendance.view"]
    builtin = await role_id(owner, "manager")
    assert (await owner.patch(f"/v1/roles/{builtin}", json={"name": "Boss"})).status_code == 403
    data, _ = await add_staff(owner, role="employee")
    member = data["member"]
    await owner.patch(
        f"/v1/members/{member['id']}", json={"role_id": rid}, headers=if_match(member["version"])
    )
    assert (await owner.delete(f"/v1/roles/{rid}")).json()["code"] == "role_in_use"


async def test_admins_cannot_escalate(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    admin = await invite_and_join(owner, role="admin")
    owner_role = await role_id(owner, "owner")
    staff, _ = await add_staff(owner)
    member = staff["member"]
    promote = await admin.patch(
        f"/v1/members/{member['id']}", json={"role_id": owner_role}, headers=if_match(member["version"])
    )
    assert promote.json()["code"] == "escalation"
    owner_member = owner.membership_id
    demote_owner = await admin.patch(
        f"/v1/members/{owner_member}", json={"role_id": await role_id(owner, "employee")}, headers=if_match(1)
    )
    assert demote_owner.json()["code"] == "owner_protected"
    self_edit = await admin.patch(
        f"/v1/members/{admin.membership_id}", json={"status": "disabled"}, headers=if_match(1)
    )
    assert self_edit.json()["code"] == "self_edit"
    # A manager can't create a role with more than they hold.
    manager = await invite_and_join(owner, role="manager")
    assert (
        await manager.post("/v1/roles", json={"name": "Mega", "permissions": ["people.manage"]})
    ).status_code == 403


async def test_last_owner_is_protected(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    second = await invite_and_join(owner, role="owner")
    response = await second.patch(
        f"/v1/members/{owner.membership_id}",
        json={"role_id": await role_id(owner, "admin")},
        headers=if_match(1),
    )
    assert response.status_code == 200
    # Now the second owner is the only one.
    promoted_back = await owner.patch(
        f"/v1/members/{second.membership_id}", json={"status": "disabled"}, headers=if_match(1)
    )
    assert promoted_back.status_code == 403
    alone = await second.delete(f"/v1/members/{owner.membership_id}")
    assert alone.status_code == 204


async def test_role_change_applies_on_next_request(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    staff_data, staff = await add_staff(owner, role="manager")
    assert (await staff.get("/v1/people")).status_code == 200
    member = staff_data["member"]
    response = await owner.patch(
        f"/v1/members/{member['id']}",
        json={"role_id": await role_id(owner, "employee")},
        headers=if_match(member["version"]),
    )
    assert response.status_code == 200
    assert (await staff.get("/v1/people")).status_code == 403


async def test_stale_member_edit_is_rejected(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    data, _ = await add_staff(owner)
    member = data["member"]
    url = f"/v1/members/{member['id']}"
    manager = await role_id(owner, "manager")
    assert (await owner.patch(url, json={"role_id": manager})).status_code == 428
    first = await owner.patch(url, json={"role_id": manager}, headers=if_match(member["version"]))
    assert first.status_code == 200
    stale = await owner.patch(
        url, json={"role_id": await role_id(owner, "cashier")}, headers=if_match(member["version"])
    )
    assert stale.status_code == 412


async def test_disabled_and_removed_members_lose_access(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    data, staff = await add_staff(owner)
    member = data["member"]
    await owner.patch(
        f"/v1/members/{member['id']}", json={"status": "disabled"}, headers=if_match(member["version"])
    )
    assert (await staff.get("/v1/workspace")).json()["code"] == "not_member"
    await owner.patch(
        f"/v1/members/{member['id']}", json={"status": "active"}, headers=if_match(member["version"] + 1)
    )
    assert (await staff.get("/v1/workspace")).status_code == 200
    assert (await owner.delete(f"/v1/members/{member['id']}")).status_code == 204
    assert (await staff.get("/v1/workspace")).status_code == 401
    listed = (await owner.get("/v1/members", params={"status": "removed"})).json()["items"]
    assert [m["id"] for m in listed] == [member["id"]]


async def test_staff_accounts(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    data, staff = await add_staff(owner, name="করিম", username="Karim.01")
    assert data["member"]["username"] == "karim.01"
    assert data["member"]["staff_account"] is True
    taken = await owner.post(
        "/v1/members/staff",
        json={"name": "Other", "username": "KARIM.01", "role_id": await role_id(owner, "employee")},
    )
    assert taken.status_code == 422
    bad = await owner.post(
        "/v1/members/staff",
        json={"name": "O", "username": "a b", "role_id": await role_id(owner, "employee")},
    )
    assert bad.status_code == 422
    # A new staff account must change its temporary password before doing anything.
    fresh = await owner.post(
        "/v1/members/staff",
        json={"name": "New", "username": "newbie", "role_id": await role_id(owner, "employee")},
    )
    temp = fresh.json()["temporary_password"]
    signed = await client.post(
        "/v1/auth/login",
        json={"workspace": owner.me["workspace"]["slug"], "username": "newbie", "password": temp},
    )
    token = signed.json()["access_token"]
    blocked = await client.get("/v1/workspace", headers={"authorization": f"Bearer {token}"})
    assert blocked.json()["code"] == "password_change_required"
    # Reset by an admin: old sessions end, a new temporary password works.
    reset = await owner.post(f"/v1/members/{data['member']['id']}/reset-password")
    assert reset.status_code == 200
    assert (await staff.get("/v1/workspace")).status_code == 401
    # Email accounts can't be reset this way.
    admin = await invite_and_join(owner, role="admin")
    assert (await owner.post(f"/v1/members/{admin.membership_id}/reset-password")).status_code == 422
    # Wrong workspace code: the same generic failure.
    wrong = await client.post(
        "/v1/auth/login", json={"workspace": "nope", "username": "karim.01", "password": PASSWORD}
    )
    assert wrong.json()["code"] == "bad_credentials"


async def test_invites(client: httpx.AsyncClient, owner_sql: psycopg.Connection) -> None:
    owner = await signup(client)
    employee = await role_id(owner, "employee")
    unverified = await owner.post("/v1/invites", json={"email": "new@example.com", "role_id": employee})
    assert unverified.json()["code"] == "email_unverified"
    await verify_email(owner)
    first = await owner.post(
        "/v1/invites", json={"email": "New@Example.com", "role_id": employee, "name": "Nabila"}
    )
    assert first.status_code == 201
    old_token = link_token(last_email("new@example.com"))
    second = await owner.post("/v1/invites", json={"email": "new@example.com", "role_id": employee})
    token = link_token(last_email("new@example.com"))
    assert (await client.get("/v1/invites/lookup", params={"token": old_token})).json()[
        "code"
    ] == "invite_invalid"
    lookup = await client.get("/v1/invites/lookup", params={"token": token})
    assert lookup.json()["account_exists"] is False
    no_password = await client.post("/v1/invites/accept", json={"token": token})
    assert no_password.status_code == 422
    accepted = await client.post(
        "/v1/invites/accept", json={"token": token, "name": "Nabila", "password": PASSWORD}
    )
    assert accepted.status_code == 200
    assert (
        await client.post("/v1/invites/accept", json={"token": token, "name": "N", "password": PASSWORD})
    ).json()["code"] == "invite_used"
    assert len((await owner.get("/v1/invites")).json()) == 0
    assert second.status_code == 201
    # Already a member.
    assert (await owner.post("/v1/invites", json={"email": "new@example.com", "role_id": employee})).json()[
        "code"
    ] == "already_member"
    # Expired and revoked invitations.
    third = await owner.post("/v1/invites", json={"email": "late@example.com", "role_id": employee})
    late_token = link_token(last_email("late@example.com"))
    as_tenant(owner_sql, owner).execute(
        "UPDATE invites SET expires_at = now() - interval '1 minute' WHERE email = 'late@example.com'"
    )
    assert (await client.get("/v1/invites/lookup", params={"token": late_token})).json()[
        "code"
    ] == "invite_expired"
    fourth = await owner.post("/v1/invites", json={"email": "gone@example.com", "role_id": employee})
    gone_token = link_token(last_email("gone@example.com"))
    assert (await owner.delete(f"/v1/invites/{fourth.json()['id']}")).status_code == 204
    assert (await client.get("/v1/invites/lookup", params={"token": gone_token})).json()[
        "code"
    ] == "invite_invalid"
    assert third.status_code == 201
    assert (await client.get("/v1/invites/lookup", params={"token": "garbage"})).status_code == 422


async def test_existing_user_joins_second_workspace_and_switches(client: httpx.AsyncClient) -> None:
    first = await signup(client, business="First")
    second_owner = await signup(client, business="Second")
    await verify_email(second_owner)
    await second_owner.post(
        "/v1/invites", json={"email": first.email, "role_id": await role_id(second_owner, "manager")}
    )
    token = link_token(last_email(first.email or ""))
    assert (await client.get("/v1/invites/lookup", params={"token": token})).json()["account_exists"] is True
    anonymous = await client.post("/v1/invites/accept", json={"token": token})
    assert anonymous.json()["code"] == "sign_in_to_accept"
    stranger = await signup(client, business="Third")
    wrong_user = await client.post("/v1/invites/accept", json={"token": token}, headers=stranger.headers)
    assert wrong_user.json()["code"] == "sign_in_to_accept"
    joined = await client.post("/v1/invites/accept", json={"token": token}, headers=first.headers)
    assert joined.status_code == 200
    account = await login(client, first.email or "")
    names = {w["name"] for w in account.me["workspaces"]}
    assert names == {"First", "Second"}
    target = next(w["id"] for w in account.me["workspaces"] if w["id"] != account.tenant_id)
    switched = await account.post("/v1/auth/switch", json={"tenant_id": target})
    assert switched.status_code == 200
    old_token_still_bound = await account.get("/v1/workspace")
    assert old_token_still_bound.status_code == 401
    account.token = switched.json()["access_token"]
    assert (await account.get("/v1/workspace")).json()["id"] == target


async def test_branches(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    branches = (await owner.get("/v1/branches")).json()
    assert [b["name"] for b in branches] == ["Main branch"]
    assert branches[0]["timezone"] == "Asia/Dhaka"
    second = await owner.post("/v1/branches", json={"name": "Chittagong", "timezone": "Asia/Dhaka"})
    assert second.status_code == 201
    assert (await owner.post("/v1/branches", json={"name": "chittagong"})).status_code == 422
    third = await owner.post("/v1/branches", json={"name": "London", "timezone": "Europe/London"})
    assert third.status_code == 201
    assert (await owner.post("/v1/branches", json={"name": "Fourth"})).json()["code"] == "branch_limit"
    b = third.json()
    closed = await owner.patch(
        f"/v1/branches/{b['id']}", json={"is_active": False}, headers=if_match(b["version"])
    )
    assert closed.status_code == 200
    main = branches[0]
    await owner.patch(f"/v1/branches/{second.json()['id']}", json={"is_active": False}, headers=if_match(1))
    last = await owner.patch(
        f"/v1/branches/{main['id']}", json={"is_active": False}, headers=if_match(main["version"])
    )
    assert last.json()["code"] == "last_branch"


async def test_audit_log_records_and_verifies(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client)
    await owner.post("/v1/departments", json={"name": "Sales"})
    await owner.post("/v1/branches", json={"name": "Two"})
    page = (await owner.get("/v1/audit", params={"limit": 2})).json()
    assert len(page["items"]) == 2
    assert page["next_cursor"]
    rest = (await owner.get("/v1/audit", params={"cursor": page["next_cursor"]})).json()["items"]
    actions = [e["action"] for e in page["items"] + rest]
    assert actions[-1] == "workspace.created"
    assert "department.created" in actions
    assert (await owner.get("/v1/audit/verify")).json() == {"ok": True, "first_bad_seq": None}
    # Someone with direct database access edits history: the chain shows it.
    owner_sql.execute("ALTER TABLE audit_events DISABLE TRIGGER audit_events_append_only")
    as_tenant(owner_sql, owner).execute(
        "UPDATE audit_events SET data = '{\"name\": \"Other\"}' WHERE action = 'department.created'"
    )
    owner_sql.execute("ALTER TABLE audit_events ENABLE TRIGGER audit_events_append_only")
    result = (await owner.get("/v1/audit/verify")).json()
    assert result["ok"] is False
    assert result["first_bad_seq"] == 2


async def test_audit_filters(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    dept = (await owner.post("/v1/departments", json={"name": "Sales"})).json()
    by_target = (
        await owner.get("/v1/audit", params={"target_type": "department", "target_id": dept["id"]})
    ).json()
    assert [e["action"] for e in by_target["items"]] == ["department.created"]
    mine = (await owner.get("/v1/audit", params={"actor": owner.me["id"]})).json()["items"]
    assert all(e["actor_user_id"] == owner.me["id"] for e in mine)
    assert all(e["actor_name"] == "Rahim Uddin" for e in mine)
