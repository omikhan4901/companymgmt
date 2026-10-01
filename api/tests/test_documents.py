"""Documents and policies: visibility, safe uploads and downloads, versions, acknowledgements."""

from __future__ import annotations

from typing import Any

import httpx

from tests.helpers import Account, add_staff, if_match, invite_and_join, role_id, signup

PDF = b"%PDF-1.7\n% a tiny test file\n"


async def make(owner: Account, title: str, **extra: Any) -> dict[str, Any]:
    response = await owner.post("/v1/documents", json={"title": title, **extra})
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def upload(
    account: Account, doc_id: str, data: bytes = PDF, filename: str = "policy.pdf", **params: Any
) -> httpx.Response:
    return await account.post(
        f"/v1/documents/{doc_id}/versions",
        params={"filename": filename, **params},
        content=data,
        headers={"content-type": "application/octet-stream"},
    )


async def titles(account: Account) -> list[str]:
    response = await account.get("/v1/documents")
    assert response.status_code == 200, response.text
    return sorted(d["title"] for d in response.json())


async def office(client: httpx.AsyncClient) -> dict[str, Any]:
    owner = await signup(client)
    await owner.put("/v1/workspace/modules", json={"modules": ["attendance", "leave", "documents"]})
    design = (await owner.post("/v1/departments", json={"name": "Design"})).json()
    sales = (await owner.post("/v1/departments", json={"name": "Sales"})).json()
    lead = await invite_and_join(owner, role="manager", scope_department_id=design["id"])
    _, artist = await add_staff(owner, name="Artist", scope_department_id=design["id"])
    _, seller = await add_staff(owner, name="Seller", scope_department_id=sales["id"])
    return {"owner": owner, "lead": lead, "artist": artist, "seller": seller, "design": design["id"]}


async def test_people_see_only_what_is_meant_for_them(client: httpx.AsyncClient) -> None:
    o = await office(client)
    owner, lead, artist, seller = o["owner"], o["lead"], o["artist"], o["seller"]
    handbook = await make(owner, "Handbook", category="handbook")
    brand = await make(owner, "Brand guide", visibility="departments", visibility_ids=[o["design"]])
    managers = await make(
        owner, "Managers' notes", visibility="roles", visibility_ids=[await role_id(owner, "manager")]
    )
    empty = await make(owner, "Draft")
    for doc in (handbook, brand, managers):
        assert (await upload(owner, doc["id"])).status_code == 201
    # A document without a file yet is the owner's draft.
    assert await titles(seller) == ["Handbook"]
    assert await titles(artist) == ["Brand guide", "Handbook"]
    assert await titles(lead) == ["Brand guide", "Handbook", "Managers' notes"]
    assert await titles(owner) == ["Brand guide", "Draft", "Handbook", "Managers' notes"]
    assert (await seller.get(f"/v1/documents/{brand['id']}")).status_code == 404
    assert (await seller.get(f"/v1/documents/{empty['id']}")).status_code == 404
    # Only managers of documents publish.
    assert (await seller.post("/v1/documents", json={"title": "Mine"})).status_code == 403
    assert (await upload(lead, handbook["id"])).status_code == 403
    # Archived documents disappear for readers.
    current = (await owner.get(f"/v1/documents/{brand['id']}")).json()
    archived = await owner.patch(
        f"/v1/documents/{brand['id']}", json={"archived": True}, headers=if_match(current["version"])
    )
    assert archived.status_code == 200, archived.text
    assert await titles(artist) == ["Handbook"]


async def test_uploads_are_checked_and_downloads_are_safe(client: httpx.AsyncClient) -> None:
    o = await office(client)
    owner, seller = o["owner"], o["seller"]
    doc = await make(owner, "Leave policy")
    # The name must match what the file really is.
    disguised = await upload(owner, doc["id"], b"<html><script>alert(1)</script>", "policy.pdf")
    assert disguised.json()["code"] == "file_type"
    page = await upload(owner, doc["id"], b"<html></html>", "page.html")
    assert page.json()["code"] == "file_type"
    assert (await upload(owner, doc["id"], b"", "empty.pdf")).json()["code"] == "file_empty"
    big = await upload(owner, doc["id"], b"%PDF-" + b"0" * (10 * 1024 * 1024), "big.pdf")
    assert big.json()["code"] == "file_too_large"
    sneaky = await upload(owner, doc["id"], PDF, "../../etc/নীতি.pdf", note="First version")
    assert sneaky.status_code == 201, sneaky.text
    current = sneaky.json()["current"]
    assert current["filename"] == "নীতি.pdf"
    assert (current["number"], current["note"], current["content_type"]) == (
        1,
        "First version",
        "application/pdf",
    )
    file = await seller.get(f"/v1/documents/{doc['id']}/versions/{current['id']}/file")
    assert file.status_code == 200
    assert file.content == PDF
    assert file.headers["content-disposition"].startswith("attachment;")
    assert "filename*=UTF-8''%E0%A6" in file.headers["content-disposition"]
    assert file.headers["x-content-type-options"] == "nosniff"
    # A second version becomes the current one; the first is still there.
    text = await upload(owner, doc["id"], "নতুন নিয়ম\n".encode(), "rules.txt")
    detail = text.json()
    assert detail["current"]["number"] == 2
    assert [v["number"] for v in detail["versions"]] == [2, 1]


async def test_acknowledgements_follow_the_current_version(client: httpx.AsyncClient) -> None:
    o = await office(client)
    owner, artist, seller = o["owner"], o["artist"], o["seller"]
    policy = await make(owner, "Code of conduct", category="policy", requires_ack=True)
    await upload(owner, policy["id"])
    # Everyone it's for is told, and it waits for them.
    told = (await artist.get("/v1/notifications")).json()["items"]
    assert told[0]["kind"] == "document.published"
    assert told[0]["data"]["requires_ack"] is True
    assert [d["title"] for d in (await artist.get("/v1/documents/to-acknowledge")).json()] == [
        "Code of conduct"
    ]
    acked = await artist.post(f"/v1/documents/{policy['id']}/acknowledge")
    assert acked.json()["acknowledged"] is True
    assert (await artist.post(f"/v1/documents/{policy['id']}/acknowledge")).status_code == 200
    assert (await artist.get("/v1/documents/to-acknowledge")).json() == []
    report = (await owner.get(f"/v1/documents/{policy['id']}/acknowledgements")).json()
    assert report["version_number"] == 1
    assert (report["total"], report["acknowledged"]) == (4, 1)
    assert (await seller.get(f"/v1/documents/{policy['id']}/acknowledgements")).status_code == 403
    listed = next(d for d in (await owner.get("/v1/documents")).json() if d["title"] == "Code of conduct")
    assert (listed["reach"], listed["ack_count"]) == (4, 1)
    # A new version asks again.
    await upload(owner, policy["id"], filename="conduct-v2.pdf")
    assert [d["title"] for d in (await artist.get("/v1/documents/to-acknowledge")).json()] == [
        "Code of conduct"
    ]
    # Documents that don't ask can't be acknowledged.
    plain = await make(owner, "Menu")
    await upload(owner, plain["id"])
    assert (await seller.post(f"/v1/documents/{plain['id']}/acknowledge")).json()["code"] == "no_ack_needed"
