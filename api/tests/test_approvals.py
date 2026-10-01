"""The approvals inbox: what's waiting on whom, and deciding from one place."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from tests.helpers import Account, add_staff, invite_and_join, signup
from tests.test_leave import sunday_in_march


async def ask_leave(account: Account, offset: int = 0) -> dict[str, Any]:
    types = (await account.get("/v1/leave/types")).json()
    casual = next(t["id"] for t in types if t["name"] == "Casual leave")
    day = str(sunday_in_march() + timedelta(days=offset))
    response = await account.post(
        "/v1/leave/requests",
        json={"leave_type_id": casual, "start_date": day, "end_date": day, "reason": "Family"},
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def ask_fix(account: Account) -> dict[str, Any]:
    start = datetime.now(UTC) - timedelta(days=2)
    response = await account.post(
        "/v1/attendance/corrections",
        json={
            "kind": "add",
            "clock_in_at": start.isoformat(),
            "clock_out_at": (start + timedelta(hours=8)).isoformat(),
            "reason": "Phone was dead",
        },
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def inbox(account: Account) -> list[dict[str, Any]]:
    response = await account.get("/v1/approvals")
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return items


async def test_the_inbox_gathers_what_each_person_may_decide(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    kitchen = (await owner.post("/v1/departments", json={"name": "Kitchen"})).json()
    sales = (await owner.post("/v1/departments", json={"name": "Sales"})).json()
    manager = await invite_and_join(owner, role="manager", scope_department_id=kitchen["id"])
    _, cook = await add_staff(owner, name="Cook", scope_department_id=kitchen["id"])
    _, seller = await add_staff(owner, name="Seller", scope_department_id=sales["id"])
    leave = await ask_leave(cook)
    fix = await ask_fix(cook)
    await ask_leave(seller, 1)
    await ask_leave(manager, 2)

    # Oldest first, both kinds, with what's needed to decide.
    mine = await inbox(manager)
    assert [(i["kind"], i["employee_name"]) for i in mine] == [("leave", "Cook"), ("time_fix", "Cook")]
    assert mine[0]["leave_type_name"] == "Casual leave"
    assert mine[0]["reason"] == "Family"
    assert mine[1]["fix_kind"] == "add"
    # The owner sees everyone's, including the manager's own request; not their own.
    names = sorted(i["employee_name"] for i in await inbox(owner))
    assert names == ["Cook", "Cook", "Member Person", "Seller"]
    assert (await manager.get("/v1/approvals/count")).json() == {"count": 2}
    # Staff have nothing to decide.
    assert await inbox(cook) == []

    # Deciding from the inbox is the same as deciding in the module.
    approved = await manager.post(f"/v1/approvals/leave/{leave['id']}/approve", json={"note": "Enjoy"})
    assert approved.json() == {"kind": "leave", "id": leave["id"], "status": "approved"}
    rejected = await manager.post(f"/v1/approvals/time_fix/{fix['id']}/reject", json={})
    assert rejected.json()["status"] == "rejected"
    assert await inbox(manager) == []
    told = [n["kind"] for n in (await cook.get("/v1/notifications")).json()["items"]]
    assert told[:2] == ["attendance.correction_rejected", "leave.approved"]
    # Decided once only, and only within scope.
    again = await manager.post(f"/v1/approvals/leave/{leave['id']}/reject", json={})
    assert again.status_code == 409
    seller_request = next(i for i in await inbox(owner) if i["employee_name"] == "Seller")
    outside = await manager.post(f"/v1/approvals/leave/{seller_request['id']}/approve", json={})
    assert outside.status_code == 404
    assert (
        await cook.post(f"/v1/approvals/leave/{seller_request['id']}/approve", json={})
    ).status_code == 403


async def test_switched_off_modules_stay_out_of_the_inbox(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner, name="Rahim")
    await ask_leave(staff)
    await ask_fix(staff)
    assert {i["kind"] for i in await inbox(owner)} == {"leave", "time_fix"}
    await owner.put("/v1/workspace/modules", json={"modules": ["attendance"]})
    assert {i["kind"] for i in await inbox(owner)} == {"time_fix"}
    unknown = await owner.post("/v1/approvals/expense/01a0f649-3e7d-766a-ac5e-86799ee886fd/approve", json={})
    assert unknown.status_code == 422
