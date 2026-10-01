"""Capabilities: the same answers (and the same refusals) as the REST routes they mirror.

The assistant (M6) only ever reaches data through capabilities, so for every person and
every read we check that a capability returns exactly what the API would have.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx
import pytest

from app.core.time import today
from app.modules.platform.capabilities import REGISTRY
from tests.helpers import Account, add_staff, invite_and_join, signup

NEXT = today("Asia/Dhaka").year + 1
MONTH = today("Asia/Dhaka").strftime("%Y-%m")


async def invoke(account: Account, name: str, data: dict[str, Any] | None = None) -> httpx.Response:
    return await account.post("/v1/ai/capabilities/invoke", json={"name": name, "input": data or {}})


async def same(account: Account, name: str, path: str, params: dict[str, Any] | None = None) -> Any:
    """Call the route and the capability; both must agree, success or not."""
    rest = await account.get(path, params=params or {})
    cap = await invoke(account, name, params)
    assert cap.status_code == rest.status_code, (name, rest.text, cap.text)
    if rest.status_code == 200:
        assert cap.json() == rest.json(), name
    else:
        assert cap.json()["code"] == rest.json()["code"], (name, rest.text, cap.text)
    return rest.json()


async def agency(client: httpx.AsyncClient) -> dict[str, Any]:
    owner = await signup(client)
    kitchen = (await owner.post("/v1/departments", json={"name": "Kitchen"})).json()
    sales = (await owner.post("/v1/departments", json={"name": "Sales"})).json()
    manager = await invite_and_join(owner, role="manager", scope_department_id=kitchen["id"])
    _, cook = await add_staff(owner, name="Cook", scope_department_id=kitchen["id"])
    _, seller = await add_staff(owner, name="Seller", scope_department_id=sales["id"])
    people = (await owner.get("/v1/people", params={"status": "all"})).json()
    items = people["items"] if isinstance(people, dict) else people
    ids = {p["full_name"]: p["id"] for p in items}
    types = (await owner.get("/v1/leave/types")).json()
    casual = next(t["id"] for t in types if t["name"] == "Casual leave")
    start = date(NEXT, 3, 3)
    await seller.post(
        "/v1/leave/requests",
        json={"leave_type_id": casual, "start_date": str(start), "end_date": str(start)},
    )
    await cook.post(
        "/v1/leave/requests",
        json={"leave_type_id": casual, "start_date": str(start), "end_date": str(start + timedelta(days=1))},
    )
    await cook.post("/v1/attendance/clock-in", json={})
    await owner.put(
        "/v1/workspace/modules",
        json={"modules": ["attendance", "leave", "payroll", "tasks", "announcements", "documents"]},
    )
    project = (
        await owner.post(
            "/v1/projects", json={"name": "Menu", "department_id": kitchen["id"], "member_ids": [ids["Cook"]]}
        )
    ).json()
    task = (
        await owner.post(
            "/v1/tasks", json={"title": "Prices", "project_id": project["id"], "assignee_id": ids["Cook"]}
        )
    ).json()
    await owner.post("/v1/announcements", json={"title": "Eid", "body": "Closed on Eid."})
    await owner.post(
        "/v1/announcements",
        json={
            "title": "Menu",
            "body": "New menu.",
            "audience": "departments",
            "audience_ids": [kitchen["id"]],
        },
    )
    kitchen_only = {"visibility": "departments", "visibility_ids": [kitchen["id"]]}
    for title, extra in (("Handbook", {}), ("Kitchen rules", kitchen_only)):
        doc = (await owner.post("/v1/documents", json={"title": title, "requires_ack": True, **extra})).json()
        await owner.post(
            f"/v1/documents/{doc['id']}/versions",
            params={"filename": "rules.pdf"},
            content=b"%PDF-1.7",
            headers={"content-type": "application/octet-stream"},
        )
    todo = (await seller.post("/v1/tasks", json={"title": "Call client"})).json()
    return {
        "project_id": project["id"],
        "task_id": task["id"],
        "todo_id": todo["id"],
        "owner": owner,
        "manager": manager,
        "cook": cook,
        "kitchen": kitchen["id"],
        "cook_id": ids["Cook"],
        "seller_id": ids["Seller"],
    }


async def test_capabilities_match_the_api_for_every_role(client: httpx.AsyncClient) -> None:
    a = await agency(client)
    year = {"year": NEXT}
    window = {"from": f"{NEXT}-03-01", "to": f"{NEXT}-03-31"}
    reads: list[tuple[str, str, dict[str, Any]]] = [
        ("people.search", "/v1/people", {}),
        ("people.search", "/v1/people", {"q": "Cook"}),
        ("people.search", "/v1/people", {"department_id": a["kitchen"], "status": "all"}),
        ("people.get", f"/v1/people/{a['cook_id']}", {"employee_id": a["cook_id"]}),
        ("people.get", f"/v1/people/{a['seller_id']}", {"employee_id": a["seller_id"]}),
        ("attendance.my_status", "/v1/attendance/status", {}),
        ("attendance.present", "/v1/attendance/present", {}),
        ("attendance.timesheet", "/v1/attendance/timesheet", {"month": MONTH}),
        ("attendance.timesheet", "/v1/attendance/timesheet", {"month": MONTH, "employee_id": a["seller_id"]}),
        ("leave.types", "/v1/leave/types", {}),
        ("leave.balances", "/v1/leave/balances", year),
        ("leave.balances", "/v1/leave/balances", {**year, "employee_id": a["seller_id"]}),
        ("leave.team_balances", "/v1/leave/balances/team", year),
        ("leave.requests", "/v1/leave/requests", {}),
        ("leave.requests", "/v1/leave/requests", {"status": "pending", **window}),
        ("leave.requests", "/v1/leave/requests", {"mine": True}),
        ("leave.calendar", "/v1/leave/calendar", window),
        ("payroll.my_payslips", "/v1/payroll/payslips", {}),
        ("payroll.runs", "/v1/payroll/runs", {}),
        ("notifications.inbox", "/v1/notifications", {}),
        ("tasks.my_work", "/v1/tasks/my-work", {}),
        ("announcements.feed", "/v1/announcements", {}),
        ("approvals.pending", "/v1/approvals", {}),
        ("documents.library", "/v1/documents", {}),
        ("documents.to_acknowledge", "/v1/documents/to-acknowledge", {}),
        ("announcements.feed", "/v1/announcements", {"limit": 1}),
        ("tasks.projects", "/v1/projects", {}),
        ("tasks.list", "/v1/tasks", {}),
        ("tasks.list", "/v1/tasks", {"project_id": a["project_id"], "status": "open"}),
        ("tasks.get", f"/v1/tasks/{a['task_id']}", {"task_id": a["task_id"]}),
        ("tasks.get", f"/v1/tasks/{a['todo_id']}", {"task_id": a["todo_id"]}),
        ("notifications.inbox", "/v1/notifications", {"unread": True, "limit": 1}),
        ("reports.overview", "/v1/reports/overview", {"from": f"{MONTH}-01", "to": f"{MONTH}-28"}),
        (
            "reports.overview",
            "/v1/reports/overview",
            {"from": f"{MONTH}-01", "to": f"{MONTH}-28", "department_id": a["kitchen"]},
        ),
    ]
    covered = set()
    for who in ("owner", "manager", "cook"):
        account: Account = a[who]
        for name, path, params in reads:
            if "{" in REGISTRY[name].route:  # type: ignore[operator]
                # Path parameters: the capability takes them as input, REST in the path.
                cap = await invoke(account, name, params)
                rest = await account.get(path)
                assert cap.status_code == rest.status_code, (who, name, rest.text, cap.text)
                if rest.status_code == 200:
                    assert cap.json() == rest.json()
            else:
                await same(account, name, path, params)
            covered.add(name)
    # Every read capability with a route is covered here.
    assert covered == {n for n, c in REGISTRY.items() if c.kind == "read" and c.route}
    # And the scoping really bites: the manager and the cook can't see the seller.
    seller = await invoke(a["manager"], "people.get", {"employee_id": a["seller_id"]})
    assert seller.status_code == 404
    team = (await invoke(a["cook"], "leave.team_balances", year)).json()
    assert team["code"] == "forbidden"


async def test_capability_list_follows_permissions_and_modules(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner, name="Rahim")
    mine = {c["name"] for c in (await staff.get("/v1/ai/capabilities")).json()}
    theirs = {c["name"] for c in (await owner.get("/v1/ai/capabilities")).json()}
    assert "leave.team_balances" in theirs
    assert "leave.team_balances" not in mine
    assert {"leave.balances", "attendance.my_status", "payroll.my_payslips"} <= mine
    spec = next(c for c in (await owner.get("/v1/ai/capabilities")).json() if c["name"] == "leave.calendar")
    assert spec["input_schema"]["required"] == ["from", "to"]
    assert spec["kind"] == "read"
    # Switching a module off removes its capabilities, and invoking them fails like the API.
    response = await owner.put("/v1/workspace/modules", json={"modules": ["attendance"]})
    assert response.status_code == 200, response.text
    left = {c["name"] for c in (await owner.get("/v1/ai/capabilities")).json()}
    assert not any(n.startswith("leave.") for n in left)
    rest = await owner.get("/v1/leave/types")
    cap = await invoke(owner, "leave.types")
    assert cap.status_code == rest.status_code == 402
    assert cap.json()["code"] == rest.json()["code"]


async def test_writes_and_bad_input_are_refused(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    types = (await owner.get("/v1/leave/types")).json()
    body = {"leave_type_id": types[0]["id"], "start_date": f"{NEXT}-03-03", "end_date": f"{NEXT}-03-03"}
    write = await invoke(owner, "leave.request", body)
    assert write.status_code == 422
    assert write.json()["code"] == "write_needs_confirmation"
    assert (await owner.get("/v1/leave/requests")).json() == []
    missing = await invoke(owner, "nothing.here")
    assert missing.status_code == 404
    bad = await invoke(owner, "attendance.timesheet", {"month": "March"})
    assert bad.status_code == 422
    assert bad.json()["errors"][0]["field"] == "month"
    named = await owner.post("/v1/ai/capabilities/invoke", json={"name": "../etc", "input": {}})
    assert named.status_code == 422


@pytest.mark.parametrize("role", ["owner", "manager"])
async def test_context_describes_the_caller(client: httpx.AsyncClient, role: str) -> None:
    owner = await signup(client, country="BD")
    kitchen = (await owner.post("/v1/departments", json={"name": "Kitchen"})).json()
    account = owner
    if role == "manager":
        account = await invite_and_join(owner, role="manager", scope_department_id=kitchen["id"])
    response = await account.get("/v1/ai/context")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["role_key"] == role
    assert data["timezone"] == "Asia/Dhaka"
    assert data["today"] == str(today("Asia/Dhaka"))
    assert "leave" in data["modules"]
    if role == "owner":
        assert data["scope"] == "workspace"
        assert data["scope_department_ids"] is None
    else:
        assert data["scope"] == "department"
        assert data["scope_department_ids"] == [kitchen["id"]]
        assert data["department"] == "Kitchen"


async def test_capabilities_stay_inside_the_workspace(client: httpx.AsyncClient) -> None:
    first = await signup(client)
    second = await signup(client)
    other = (await second.get("/v1/people")).json()
    items = other["items"] if isinstance(other, dict) else other
    response = await invoke(first, "people.get", {"employee_id": items[0]["id"]})
    assert response.status_code == 404
