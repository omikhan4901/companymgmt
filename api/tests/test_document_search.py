"""Document search: passages from what each person may read, in any language, from any
file that has text, and the assistant answering policy questions from them."""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

import httpx
import psycopg
from weasyprint import HTML

from app.ai import provider
from app.ai.fake import FakeModel
from app.modules.documents.text import extract, passages
from tests.helpers import Account
from tests.test_ai import switch_on
from tests.test_documents import make, office, upload


def docx(*paragraphs: str, extra: bytes = b"") -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = (
        extra
        + b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        + body.encode()
        + b"</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


async def search(account: Account, q: str) -> list[dict[str, Any]]:
    response = await account.get("/v1/documents/search", params={"q": q})
    assert response.status_code == 200, response.text
    found: list[dict[str, Any]] = response.json()
    return found


def test_text_comes_out_of_real_files() -> None:
    pdf = HTML(string="<h1>Leave policy</h1><p>Casual leave is ten days a year.</p>").write_pdf()
    assert pdf is not None
    assert "Casual leave is ten days a year." in extract("leave.pdf", pdf)
    assert extract("handbook.docx", docx("First line.", "Second line.")) == "First line.\nSecond line."
    assert extract("notes.md", "# ছুটি\n\nনৈমিত্তিক ছুটি দশ দিন।".encode()) == "# ছুটি\n\nনৈমিত্তিক ছুটি দশ দিন।"
    # Broken or hostile files just have no text.
    assert extract("broken.pdf", b"%PDF-1.7\nnot really") == ""
    assert extract("bomb.docx", docx("x", extra=b'<!DOCTYPE d [<!ENTITY a "aaaa">]>')) == ""
    assert extract("photo.png", b"\x89PNG") == ""
    # Long text becomes overlapping passages, cut at sentence ends where possible.
    long = " ".join(f"Sentence number {i} is here." for i in range(300))
    pieces = passages(long)
    assert len(pieces) > 5
    assert all(len(p) <= 900 for p in pieces)
    assert pieces[0].endswith(".")
    assert passages("") == []


async def test_people_find_passages_only_in_documents_they_can_read(client: httpx.AsyncClient) -> None:
    o = await office(client)
    owner = o["owner"]
    policy = await make(owner, "Work from home policy", category="policy")
    assert (
        await upload(owner, policy["id"], docx("Everyone may work from home two days a week."), "wfh.docx")
    ).status_code == 201
    secret = await make(owner, "Design pay bands", visibility="departments", visibility_ids=[o["design"]])
    await upload(owner, secret["id"], b"Senior designers earn from 90,000 a month from home.", "bands.txt")
    bangla = await make(owner, "ছুটির নিয়ম")
    await upload(owner, bangla["id"], "নৈমিত্তিক ছুটি বছরে দশ দিন।".encode(), "leave.md")

    found = await search(o["seller"], "home")
    assert [(p["title"], p["version"]) for p in found] == [("Work from home policy", 1)]
    assert found[0]["text"] == "Everyone may work from home two days a week."
    assert found[0]["link"] == f"/app/documents?doc={policy['id']}"
    designers = {p["title"] for p in await search(o["artist"], "home")}
    assert designers == {"Work from home policy", "Design pay bands"}
    assert [p["title"] for p in await search(o["seller"], "ছুটি")] == ["ছুটির নিয়ম"]
    assert await search(o["seller"], "nothing matches this") == []

    # A new version replaces the old text; archived documents can't be found.
    await upload(owner, policy["id"], docx("Hybrid work: three office days."), "wfh-v2.docx")
    assert await search(o["seller"], "two days") == []
    assert [p["version"] for p in await search(o["seller"], "hybrid")] == [2]
    current = (await owner.get(f"/v1/documents/{policy['id']}")).json()
    await owner.patch(
        f"/v1/documents/{policy['id']}",
        json={"archived": True},
        headers={"if-match": f'W/"{current["version"]}"'},
    )
    assert await search(o["seller"], "hybrid") == []
    assert (await o["seller"].get("/v1/documents/search", params={"q": ""})).status_code == 422


async def test_documents_from_before_search_are_indexed_when_needed(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    o = await office(client)
    doc = await make(o["owner"], "Code of conduct")
    await upload(o["owner"], doc["id"], b"Be kind to customers.", "conduct.txt")
    owner_sql.execute("DELETE FROM document_passages")
    assert [p["title"] for p in await search(o["seller"], "customers")] == ["Code of conduct"]


async def test_the_assistant_answers_policy_questions_from_passages(client: httpx.AsyncClient) -> None:
    o = await office(client)
    owner = o["owner"]
    doc = await make(owner, "Work from home policy", category="policy")
    await upload(owner, doc["id"], docx("Everyone may work from home two days a week."), "wfh.docx")
    model = FakeModel()
    provider.use_model(model)
    try:
        await switch_on(owner, ["ask"])
        await o["seller"].post("/v1/ai/ask", json={"question": "What is our work from home policy?"})
        _, _, offered = model.calls[-1]
        assert "documents.search" not in {t.name for t in offered}  # the documents feature is off
        await switch_on(owner, ["ask", "documents"])
        answer = (
            await o["seller"].post("/v1/ai/ask", json={"question": "What is our work from home policy?"})
        ).json()
        _, turns, _ = model.calls[-1]
        results = json.dumps([t.tool_result for t in turns if t.role == "tool"])
        assert "two days a week" in results
        assert answer["answer"]["sources"][0]["capability"] == "documents.search"
        assert "[1]" in answer["answer"]["text"]
    finally:
        provider.use_model(None)
