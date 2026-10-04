"""Early-warning signals: off until chosen, within the viewer's departments, about people
only when the workspace says so, and dismissible."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from tests.helpers import Account, add_staff, signup
from tests.test_ai import switch_on


async def employee_id(account: Account) -> str:
    return str((await account.get("/v1/leave/balances")).json()["employee_id"])


async def signals(account: Account) -> dict[str, Any]:
    response = await account.get("/v1/reports/signals")
    assert response.status_code == 200, response.text
    found: dict[str, Any] = response.json()
    return found


async def test_signals_are_off_until_chosen_and_can_be_dismissed(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner)
    assert (await staff.get("/v1/reports/signals")).status_code == 403
    assert await signals(owner) == {"on": False, "people": False, "items": []}

    project = (await owner.post("/v1/projects", json={"name": "Shop fit-out"})).json()
    late = str(datetime.now(UTC).date() - timedelta(days=5))
    for title in ("Shelves", "Lights", "Paint", "Sign"):
        made = await owner.post(
            "/v1/tasks", json={"title": title, "project_id": project["id"], "due_date": late}
        )
        assert made.status_code == 201, made.text
    await switch_on(owner, ["ask", "signals"])
    found = await signals(owner)
    assert found["on"] is True
    [slipping] = [s for s in found["items"] if s["kind"] == "project_slipping"]
    assert slipping["subject"] == "Shop fit-out"
    assert slipping["values"] == {"overdue": 4, "open": 4}
    assert slipping["severity"] == "warning"

    assert (await owner.post("/v1/reports/signals/dismiss", json={"key": slipping["key"]})).status_code == 204
    assert [s for s in (await signals(owner))["items"] if s["kind"] == "project_slipping"] == []


async def test_workload_signals_about_people_need_the_workspace_to_choose_them(
    client: httpx.AsyncClient,
) -> None:
    owner = await signup(client)
    accounts = [(await add_staff(owner, name=name))[1] for name in ("Busy Bina", "Rafiq", "Salma", "Tariq")]
    busy, *others = accounts
    for i in range(12):
        await owner.post("/v1/tasks", json={"title": f"Order {i}", "assignee_id": await employee_id(busy)})
    for person in others:
        await owner.post("/v1/tasks", json={"title": "Sweep", "assignee_id": await employee_id(person)})
    await switch_on(owner, ["ask", "signals"])
    assert [s for s in (await signals(owner))["items"] if s["kind"] == "heavy_workload"] == []

    changed = await owner.put(
        "/v1/ai/settings",
        json={"enabled": True, "features": ["ask", "signals"], "signal_people": True},
    )
    assert changed.json()["signal_people"] is True
    found = await signals(owner)
    assert found["people"] is True
    [heavy] = [s for s in found["items"] if s["kind"] == "heavy_workload"]
    assert heavy["subject"] == "Busy Bina"
    assert heavy["values"]["open"] == 12
