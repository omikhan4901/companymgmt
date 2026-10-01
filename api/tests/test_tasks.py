"""Tasks and projects: who sees and changes what, the board, checklists and comments."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import httpx

from app.core.time import today
from tests.helpers import Account, add_staff, if_match, invite_and_join, signup

TODAY = today("Asia/Dhaka")


async def me_id(account: Account) -> str:
    return str((await account.get("/v1/leave/balances")).json()["employee_id"])


async def make_project(owner: Account, name: str = "Website", **extra: Any) -> dict[str, Any]:
    response = await owner.post("/v1/projects", json={"name": name, **extra})
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def make_task(account: Account, title: str, **extra: Any) -> dict[str, Any]:
    response = await account.post("/v1/tasks", json={"title": title, **extra})
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def agency(client: httpx.AsyncClient) -> dict[str, Any]:
    owner = await signup(client)
    await owner.put("/v1/workspace/modules", json={"modules": ["attendance", "leave", "tasks"]})
    design = (await owner.post("/v1/departments", json={"name": "Design"})).json()
    sales = (await owner.post("/v1/departments", json={"name": "Sales"})).json()
    lead = await invite_and_join(owner, role="manager", scope_department_id=design["id"])
    _, artist = await add_staff(owner, name="Artist", scope_department_id=design["id"])
    _, seller = await add_staff(owner, name="Seller", scope_department_id=sales["id"])
    return {
        "owner": owner,
        "lead": lead,
        "artist": artist,
        "seller": seller,
        "design": design["id"],
        "sales": sales["id"],
        "artist_id": await me_id(artist),
        "seller_id": await me_id(seller),
        "lead_id": await me_id(lead),
    }


async def test_projects_are_seen_by_members_and_managers_in_scope(client: httpx.AsyncClient) -> None:
    a = await agency(client)
    owner, lead, artist, seller = a["owner"], a["lead"], a["artist"], a["seller"]
    brand = await make_project(owner, "Brand refresh", department_id=a["design"], member_ids=[a["artist_id"]])
    pitch = await make_project(owner, "Pitch", department_id=a["sales"], member_ids=[a["seller_id"]])
    assert [p["name"] for p in (await artist.get("/v1/projects")).json()] == ["Brand refresh"]
    assert [p["name"] for p in (await seller.get("/v1/projects")).json()] == ["Pitch"]
    # The design lead manages design projects without being a member, and nothing else.
    lead_view = (await lead.get("/v1/projects")).json()
    assert [(p["name"], p["can_manage"]) for p in lead_view] == [("Brand refresh", True)]
    assert (await lead.get(f"/v1/projects/{pitch['id']}")).status_code == 404
    assert {p["name"] for p in (await owner.get("/v1/projects")).json()} == {"Brand refresh", "Pitch"}
    # Only managers create projects, and a scoped one only in their departments.
    assert (await artist.post("/v1/projects", json={"name": "Mine"})).status_code == 403
    outside = await lead.post("/v1/projects", json={"name": "Elsewhere", "department_id": a["sales"]})
    assert outside.status_code == 422
    homeless = await lead.post("/v1/projects", json={"name": "Nowhere"})
    assert homeless.json()["errors"][0]["field"] == "department_id"
    assert (
        await lead.post("/v1/projects", json={"name": "Logo", "department_id": a["design"]})
    ).status_code == 201
    # Editing needs the version it started from.
    stale = await owner.patch(f"/v1/projects/{brand['id']}", json={"name": "X"}, headers=if_match(99))
    assert stale.status_code == 412
    renamed = await owner.patch(
        f"/v1/projects/{brand['id']}", json={"name": "Brand 2027"}, headers=if_match(brand["version"])
    )
    assert renamed.json()["name"] == "Brand 2027"


async def test_tasks_follow_their_project_and_assignee(client: httpx.AsyncClient) -> None:
    a = await agency(client)
    owner, lead, artist, seller = a["owner"], a["lead"], a["artist"], a["seller"]
    brand = await make_project(owner, "Brand", department_id=a["design"], member_ids=[a["artist_id"]])
    logo = await make_task(owner, "Logo", project_id=brand["id"], assignee_id=a["artist_id"], priority="high")
    assert logo["assignee"]["name"] == "Artist"
    # Only project members can be given project tasks.
    stranger = await owner.post(
        "/v1/tasks", json={"title": "Odd", "project_id": brand["id"], "assignee_id": a["seller_id"]}
    )
    assert stranger.json()["code"] == "not_a_member"
    # Members see and work on it; others don't see it at all.
    assert [
        t["title"] for t in (await artist.get("/v1/tasks", params={"project_id": brand["id"]})).json()
    ] == ["Logo"]
    assert (await seller.get(f"/v1/tasks/{logo['id']}")).status_code == 404
    assert (await seller.get("/v1/tasks", params={"project_id": brand["id"]})).status_code == 404
    assert (await lead.get(f"/v1/tasks/{logo['id']}")).status_code == 200
    # Personal to-dos: your own, and visible to whoever manages you.
    todo = await make_task(seller, "Call the printer")
    assert todo["assignee"]["name"] == "Seller"
    assert (await owner.get(f"/v1/tasks/{todo['id']}")).status_code == 200
    assert (await lead.get(f"/v1/tasks/{todo['id']}")).status_code == 404
    # Giving a task to someone you don't manage is refused.
    refused = await seller.post("/v1/tasks", json={"title": "For you", "assignee_id": a["artist_id"]})
    assert refused.json()["code"] == "cannot_assign"
    handed = await lead.post("/v1/tasks", json={"title": "Sketches", "assignee_id": a["artist_id"]})
    assert handed.status_code == 201
    mine = [t["title"] for t in (await artist.get("/v1/tasks/my-work")).json()]
    assert set(mine) == {"Logo", "Sketches"}


async def test_board_moves_and_completion(client: httpx.AsyncClient) -> None:
    a = await agency(client)
    owner, artist = a["owner"], a["artist"]
    brand = await make_project(owner, "Brand", department_id=a["design"], member_ids=[a["artist_id"]])
    first, second, third = [
        await make_task(artist, title, project_id=brand["id"]) for title in ("One", "Two", "Three")
    ]
    assert first["position"] < second["position"] < third["position"]
    # Three to the top, then Two after Three.
    await artist.post(f"/v1/tasks/{third['id']}/move", json={"status": "todo"})
    await artist.post(f"/v1/tasks/{second['id']}/move", json={"status": "todo", "after_id": third["id"]})
    column = (await artist.get("/v1/tasks", params={"project_id": brand["id"], "status": "todo"})).json()
    assert [t["title"] for t in column] == ["Three", "Two", "One"]
    done = (await artist.post(f"/v1/tasks/{first['id']}/move", json={"status": "done"})).json()
    assert done["status"] == "done"
    assert done["completed_at"] is not None
    bad = await artist.post(
        f"/v1/tasks/{second['id']}/move", json={"status": "doing", "after_id": third["id"]}
    )
    assert bad.json()["code"] == "bad_position"
    back = await artist.patch(
        f"/v1/tasks/{first['id']}", json={"status": "todo"}, headers=if_match(done["version"])
    )
    assert back.json()["completed_at"] is None
    project = (await owner.get(f"/v1/projects/{brand['id']}")).json()
    assert (project["open_tasks"], project["done_tasks"]) == (3, 0)


async def test_checklists_comments_and_overdue(client: httpx.AsyncClient) -> None:
    a = await agency(client)
    owner, artist, seller = a["owner"], a["artist"], a["seller"]
    task = await make_task(
        owner,
        "Brief",
        assignee_id=a["artist_id"],
        due_date=str(TODAY - timedelta(days=1)),
        checklist=["Read", "Sketch"],
    )
    assert task["overdue"] is True
    assert [i["text"] for i in task["checklist"]] == ["Read", "Sketch"]
    item = task["checklist"][0]
    ticked = await artist.patch(f"/v1/tasks/{task['id']}/checklist/{item['id']}", json={"done": True})
    assert ticked.json()["done"] is True
    await artist.post(f"/v1/tasks/{task['id']}/checklist", json={"text": "Send"})
    detail = (await artist.get(f"/v1/tasks/{task['id']}")).json()
    assert (detail["checklist_done"], detail["checklist_total"]) == (1, 3)
    said = await artist.post(f"/v1/tasks/{task['id']}/comments", json={"body": "On it"})
    assert said.status_code == 201
    comments = (await owner.get(f"/v1/tasks/{task['id']}/comments")).json()
    assert [(c["author_name"], c["body"], c["mine"]) for c in comments] == [("Artist", "On it", False)]
    # Only the author removes a comment; outsiders can't even read them.
    assert (await owner.delete(f"/v1/tasks/{task['id']}/comments/{said.json()['id']}")).status_code == 403
    assert (await seller.get(f"/v1/tasks/{task['id']}/comments")).status_code == 404
    assert (await artist.delete(f"/v1/tasks/{task['id']}/comments/{said.json()['id']}")).status_code == 204
    # The artist can't delete a task the owner gave them; the owner can.
    assert (await artist.delete(f"/v1/tasks/{task['id']}")).status_code == 403
    assert (await owner.delete(f"/v1/tasks/{task['id']}")).status_code == 204


async def test_people_hear_about_their_tasks(client: httpx.AsyncClient) -> None:
    a = await agency(client)
    owner, artist = a["owner"], a["artist"]
    brand = await make_project(owner, "Brand", department_id=a["design"], member_ids=[a["artist_id"]])
    joined = (await artist.get("/v1/notifications")).json()["items"]
    assert [n["kind"] for n in joined] == ["project.members_added"]
    assert joined[0]["link"] == f"/app/tasks?project={brand['id']}"
    task = await make_task(owner, "Logo", project_id=brand["id"], assignee_id=a["artist_id"])
    await owner.post(f"/v1/tasks/{task['id']}/comments", json={"body": "Make it pop"})
    kinds = [n["kind"] for n in (await artist.get("/v1/notifications")).json()["items"]]
    assert kinds[:2] == ["task.commented", "task.assigned"]
    await artist.post(f"/v1/tasks/{task['id']}/move", json={"status": "done"})
    told = (await owner.get("/v1/notifications")).json()["items"]
    assert told[0]["kind"] == "task.completed"
    assert told[0]["data"]["title"] == "Logo"


async def test_tasks_module_must_be_on(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    await owner.put("/v1/workspace/modules", json={"modules": ["attendance"]})
    assert (await owner.get("/v1/tasks")).status_code == 402
