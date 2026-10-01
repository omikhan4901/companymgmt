"""Onboarding checklists: templates become tasks for the joiner and their manager."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx

from tests.helpers import Account, add_staff, invite_and_join, signup

TASKS_ON = {"modules": ["attendance", "leave", "tasks", "documents"]}


async def template(owner: Account, **extra: Any) -> dict[str, Any]:
    body = {
        "name": "First week",
        "items": [
            {"title": "Set up your email", "who": "joiner", "due_days": 0},
            {"title": "Introduce them to the team", "who": "manager", "due_days": 1},
            {"title": "Read the handbook", "who": "joiner", "due_days": 3, **extra.pop("doc", {})},
        ],
        **extra,
    }
    response = await owner.post("/v1/onboarding/templates", json=body)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def test_starting_a_checklist_creates_tasks_for_joiner_and_manager(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    await owner.put("/v1/workspace/modules", json=TASKS_ON)
    design = (await owner.post("/v1/departments", json={"name": "Design"})).json()
    lead = await invite_and_join(owner, role="manager", scope_department_id=design["id"])
    staff_data, staff = await add_staff(owner, name="New Joiner", scope_department_id=design["id"])
    joiner_id = str((await staff.get("/v1/leave/balances")).json()["employee_id"])
    first_week = await template(owner)
    start = date(2027, 3, 1)
    run = await owner.post(
        "/v1/onboarding/runs",
        json={"employee_id": joiner_id, "template_id": first_week["id"], "start_date": str(start)},
    )
    assert run.status_code == 201, run.text
    assert (run.json()["total"], run.json()["done"]) == (3, 0)
    mine = {t["title"]: t for t in (await staff.get("/v1/tasks/my-work")).json()}
    assert set(mine) == {"Set up your email", "Read the handbook"}
    assert mine["Read the handbook"]["due_date"] == str(start + timedelta(days=3))
    # The manager item goes to the person running the joiner's department.
    theirs = [t["title"] for t in (await lead.get("/v1/tasks/my-work")).json()]
    assert theirs == ["Introduce them to the team"]
    # Progress follows the tasks.
    email = mine["Set up your email"]
    await staff.post(f"/v1/tasks/{email['id']}/move", json={"status": "done"})
    [progress] = (await staff.get("/v1/onboarding/runs", params={"mine": True})).json()
    assert (progress["done"], progress["total"]) == (1, 3)
    assert [r["employee_name"] for r in (await lead.get("/v1/onboarding/runs")).json()] == ["New Joiner"]
    # Scoped managers start checklists for their people but don't edit the templates.
    assert (
        await lead.post("/v1/onboarding/templates", json={"name": "Mine", "items": []})
    ).status_code == 403
    assert (await staff.get("/v1/onboarding/templates")).status_code == 403
    assert staff_data["member"]["name"] == "New Joiner"


async def test_reading_a_document_ticks_the_item_off(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    await owner.put("/v1/workspace/modules", json=TASKS_ON)
    handbook = (await owner.post("/v1/documents", json={"title": "Handbook", "requires_ack": True})).json()
    await owner.post(
        f"/v1/documents/{handbook['id']}/versions",
        params={"filename": "handbook.pdf"},
        content=b"%PDF-1.7",
        headers={"content-type": "application/octet-stream"},
    )
    first_week = await template(owner, doc={"document_id": handbook["id"]})
    _, staff = await add_staff(owner, name="New Joiner")
    joiner_id = str((await staff.get("/v1/leave/balances")).json()["employee_id"])
    await owner.post("/v1/onboarding/runs", json={"employee_id": joiner_id, "template_id": first_week["id"]})
    read = next(t for t in (await staff.get("/v1/tasks/my-work")).json() if t["title"] == "Read the handbook")
    assert read["document_id"] == handbook["id"]
    await staff.post(f"/v1/documents/{handbook['id']}/acknowledge")
    assert (await staff.get(f"/v1/tasks/{read['id']}")).json()["status"] == "done"


async def test_automatic_checklists_start_when_someone_joins(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    await owner.put("/v1/workspace/modules", json=TASKS_ON)
    await template(owner, automatic=True)
    joiner = await invite_and_join(owner)
    titles = {t["title"] for t in (await joiner.get("/v1/tasks/my-work")).json()}
    assert titles == {"Set up your email", "Read the handbook"}
    # The owner gets the manager's part.
    assert "Introduce them to the team" in {t["title"] for t in (await owner.get("/v1/tasks/my-work")).json()}
