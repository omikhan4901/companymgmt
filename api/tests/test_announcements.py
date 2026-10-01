"""Announcements: who sees a post, who may post where, read receipts and notices."""

from __future__ import annotations

from typing import Any

import httpx

from tests.helpers import Account, add_staff, if_match, invite_and_join, signup


async def post(account: Account, title: str, **extra: Any) -> httpx.Response:
    return await account.post("/v1/announcements", json={"title": title, "body": f"{title}.", **extra})


async def titles(account: Account) -> list[str]:
    response = await account.get("/v1/announcements")
    assert response.status_code == 200, response.text
    return [a["title"] for a in response.json()]


async def office(client: httpx.AsyncClient) -> dict[str, Any]:
    owner = await signup(client)
    await owner.put("/v1/workspace/modules", json={"modules": ["attendance", "leave", "announcements"]})
    design = (await owner.post("/v1/departments", json={"name": "Design"})).json()
    print_ = (await owner.post("/v1/departments", json={"name": "Print", "parent_id": design["id"]})).json()
    sales = (await owner.post("/v1/departments", json={"name": "Sales"})).json()
    branch = (await owner.post("/v1/branches", json={"name": "Chittagong"})).json()
    lead = await invite_and_join(owner, role="manager", scope_department_id=design["id"])
    _, printer = await add_staff(owner, name="Printer", scope_department_id=print_["id"])
    _, seller = await add_staff(owner, name="Seller", scope_department_id=sales["id"])
    return {
        "owner": owner,
        "lead": lead,
        "printer": printer,
        "seller": seller,
        "design": design["id"],
        "print": print_["id"],
        "sales": sales["id"],
        "branch": branch["id"],
    }


async def test_posts_reach_their_audience(client: httpx.AsyncClient) -> None:
    o = await office(client)
    owner, lead, printer, seller = o["owner"], o["lead"], o["printer"], o["seller"]
    assert (await post(owner, "Eid holidays")).status_code == 201
    assert (
        await post(owner, "Design review", audience="departments", audience_ids=[o["design"]])
    ).status_code == 201
    assert (
        await post(owner, "Chittagong office", audience="branches", audience_ids=[o["branch"]])
    ).status_code == 201
    # Departments reach everything below them; branches only their people.
    assert await titles(printer) == ["Design review", "Eid holidays"]
    assert await titles(seller) == ["Eid holidays"]
    assert await titles(owner) == ["Chittagong office", "Design review", "Eid holidays"]
    # Pinned posts come first.
    first = (await owner.get("/v1/announcements")).json()[-1]
    pinned = await owner.patch(
        f"/v1/announcements/{first['id']}", json={"pinned": True}, headers=if_match(first["version"])
    )
    assert pinned.status_code == 200, pinned.text
    assert (await titles(seller))[0] == "Eid holidays"
    assert (await titles(printer))[0] == "Eid holidays"
    # A scoped manager posts only to their own departments.
    everyone = await post(lead, "To all")
    assert everyone.json()["errors"][0]["field"] == "audience"
    elsewhere = await post(lead, "To sales", audience="departments", audience_ids=[o["sales"]])
    assert elsewhere.status_code == 422
    assert (
        await post(lead, "Print run", audience="departments", audience_ids=[o["print"]])
    ).status_code == 201
    assert "Print run" in await titles(printer)
    # Staff don't post.
    assert (await post(seller, "Hi")).status_code == 403
    # Nobody sees what isn't addressed to them, even by id.
    hidden = next(a for a in (await owner.get("/v1/announcements")).json() if a["title"] == "Design review")
    assert (await seller.get(f"/v1/announcements/{hidden['id']}")).status_code == 404


async def test_read_receipts_and_unread_counts(client: httpx.AsyncClient) -> None:
    o = await office(client)
    owner, lead, printer = o["owner"], o["lead"], o["printer"]
    created = (await post(owner, "New hours", audience="departments", audience_ids=[o["design"]])).json()
    assert (created["reach"], created["read_count"]) == (2, 0)  # the lead and the printer
    assert (await printer.get("/v1/announcements/unread")).json() == {"unread": 1}
    assert (await printer.post(f"/v1/announcements/{created['id']}/read")).status_code == 204
    assert (await printer.post(f"/v1/announcements/{created['id']}/read")).status_code == 204
    assert (await printer.get("/v1/announcements/unread")).json() == {"unread": 0}
    seen = (await printer.get("/v1/announcements")).json()[0]
    assert seen["read"] is True
    assert seen["reach"] is None  # receipts are for the author and admins
    receipts = (await owner.get(f"/v1/announcements/{created['id']}/receipts")).json()
    assert (receipts["total"], receipts["read"]) == (2, 1)
    assert [(p["name"], p["read_at"] is not None) for p in receipts["people"]] == [
        ("Member Person", False),
        ("Printer", True),
    ]
    # A manager who didn't write it can't see its receipts.
    assert (await lead.get(f"/v1/announcements/{created['id']}/receipts")).status_code == 403
    # The audience was told.
    told = (await printer.get("/v1/notifications")).json()["items"]
    assert told[0]["kind"] == "announcement.published"
    assert told[0]["data"] == {"title": "New hours"}
    assert told[0]["link"] == f"/app/announcements?post={created['id']}"
    assert (await owner.get("/v1/notifications")).json()["items"] == []


async def test_editing_and_deleting(client: httpx.AsyncClient) -> None:
    o = await office(client)
    owner, lead = o["owner"], o["lead"]
    mine = (await post(lead, "Team lunch", audience="departments", audience_ids=[o["design"]])).json()
    assert mine["can_edit"] is True
    edited = await lead.patch(
        f"/v1/announcements/{mine['id']}", json={"body": "Friday at one."}, headers=if_match(mine["version"])
    )
    assert edited.json()["edited_at"] is not None
    stale = await lead.patch(f"/v1/announcements/{mine['id']}", json={"title": "x"}, headers=if_match(1))
    assert stale.status_code == 412
    theirs = (await post(owner, "All hands")).json()
    assert (await lead.delete(f"/v1/announcements/{theirs['id']}")).status_code == 403
    assert (await owner.delete(f"/v1/announcements/{mine['id']}")).status_code == 204
    assert await titles(lead) == ["All hands"]
