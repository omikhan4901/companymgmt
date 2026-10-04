"""The assistant: off until chosen, never beyond what the asker may see, never writing."""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from app.ai import provider
from app.ai.fake import FakeModel
from app.ai.gemini import Gemini, simplify
from app.ai.provider import Reply, Tool, ToolCall, Turn
from app.core.config import get_settings
from tests.helpers import Account, add_staff, invite_and_join, signup
from tests.test_data_rights import enable_mfa

ALL = ["ask", "documents", "brief"]


@pytest.fixture
def fake() -> Iterator[FakeModel]:
    model = FakeModel()
    provider.use_model(model)
    yield model
    provider.use_model(None)


async def switch_on(owner: Account, features: list[str] | None = None) -> dict[str, Any]:
    response = await owner.put(
        "/v1/ai/settings", json={"enabled": True, "accept_terms": True, "features": features or ALL}
    )
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


async def ask(account: Account, question: str, **extra: Any) -> httpx.Response:
    return await account.post("/v1/ai/ask", json={"question": question, **extra})


def tool_results(model: FakeModel) -> list[Any]:
    """Every tool result the model was shown in its last question."""
    _, turns, _ = model.calls[-1]
    return [t.tool_result for t in turns if t.role == "tool"]


async def test_ai_is_off_until_the_server_and_the_owner_switch_it_on(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    status = (await owner.get("/v1/ai/status")).json()
    assert (status["available"], status["enabled"], status["features"]) == (False, False, [])
    assert (status["allowance"], status["used"]) == (500, 0)  # the Growth trial
    unavailable = await ask(owner, "How many people work here?")
    assert (unavailable.status_code, unavailable.json()["code"]) == (503, "ai_unavailable")

    provider.use_model(FakeModel())
    try:
        assert (await owner.get("/v1/ai/status")).json()["available"] is True
        off = await ask(owner, "How many people work here?")
        assert (off.status_code, off.json()["code"]) == (403, "ai_off")
        # Admins choose features, but only the owner accepts the AI terms.
        admin = await invite_and_join(owner, role="admin")
        refused = await admin.put("/v1/ai/settings", json={"enabled": True, "accept_terms": True})
        assert refused.json()["code"] == "owner_only"
        needs_terms = await owner.put("/v1/ai/settings", json={"enabled": True})
        assert needs_terms.json()["code"] == "ai_terms_needed"
        unknown = await owner.put(
            "/v1/ai/settings", json={"enabled": True, "accept_terms": True, "features": ["x"]}
        )
        assert unknown.status_code == 422
        await switch_on(owner, ["documents"])
        feature_off = await ask(owner, "Who works here?")
        assert (feature_off.status_code, feature_off.json()["code"]) == (403, "ai_feature_off")
        changed = await admin.put("/v1/ai/settings", json={"enabled": True, "features": ["ask"]})
        assert changed.json()["features"] == ["ask"]
        _, staff = await add_staff(owner)
        assert (await staff.put("/v1/ai/settings", json={"enabled": False})).status_code == 403
        assert (await staff.get("/v1/ai/status")).json()["can_use"] is True
        log = (await owner.get("/v1/audit")).json()["items"]
        assert "ai.settings_changed" in {e["action"] for e in log}
    finally:
        provider.use_model(None)


async def test_answers_come_from_what_the_asker_may_see(client: httpx.AsyncClient, fake: FakeModel) -> None:
    owner = await signup(client)
    kitchen = (await owner.post("/v1/departments", json={"name": "Kitchen"})).json()
    sales = (await owner.post("/v1/departments", json={"name": "Sales"})).json()
    await add_staff(owner, name="Cook Karim", scope_department_id=kitchen["id"])
    await add_staff(owner, name="Seller Salma", scope_department_id=sales["id"])
    manager = await invite_and_join(owner, role="manager", scope_department_id=kitchen["id"])
    _, staff = await add_staff(owner, name="Rafiq", scope_department_id=kitchen["id"])
    await switch_on(owner)

    answer = await ask(manager, "Show me the people in my team")
    assert answer.status_code == 200, answer.text
    seen = json.dumps(tool_results(fake))
    assert "Cook Karim" in seen
    assert "Seller Salma" not in seen  # another department
    body = answer.json()
    assert body["answer"]["sources"][0]["capability"] == "people.search"
    assert body["answer"]["sources"][0]["link"] == "/app/people"
    assert "[1]" in body["answer"]["text"]

    # Staff can't search people at all: the tool isn't even offered.
    await ask(staff, "Who works here?")
    _, _, offered = fake.calls[-1]
    names = {t.name for t in offered}
    assert "people.search" not in names
    assert "leave.balances" in names
    # Nothing that changes data is ever offered.
    assert not any(name.startswith("tasks.create") for name in names)


async def test_the_model_cannot_reach_past_its_tools(client: httpx.AsyncClient, fake: FakeModel) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner)
    await switch_on(owner)
    # A model that tries to write, or call something the person can't see, gets refused.
    fake.script = [
        Reply(tool_calls=[ToolCall("tasks.create", {"title": "Injected"}), ToolCall("payroll.runs", {})]),
        Reply(text="Done."),
    ]
    assert (await ask(staff, "Make me a task")).status_code == 200
    results = tool_results(fake)
    assert results == [
        {"error": "That tool isn't available to this person."},
        {"error": "That tool isn't available to this person."},
    ]
    assert (await owner.get("/v1/tasks")).json() == []
    # And a model that never stops asking for tools is cut off.
    fake.script = [Reply(tool_calls=[ToolCall("leave.balances", {})]) for _ in range(10)]
    stuck = (await ask(staff, "Loop")).json()
    assert stuck["answer"]["text"] == "I couldn't finish that one. Try asking in a simpler way."


async def test_conversations_are_private_and_can_be_forgotten(
    client: httpx.AsyncClient, fake: FakeModel
) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner)
    await switch_on(owner)
    first = (await ask(staff, "How many leave days do I have?")).json()
    conversation_id = first["conversation_id"]
    follow_up = await ask(staff, "And sick leave?", conversation_id=conversation_id)
    assert follow_up.json()["conversation_id"] == conversation_id
    # The earlier question is sent along as history.
    _, turns, _ = fake.calls[-1]
    assert turns[0].text == "How many leave days do I have?"
    listed = (await staff.get("/v1/ai/conversations")).json()
    assert [c["title"] for c in listed] == ["How many leave days do I have?"]
    detail = (await staff.get(f"/v1/ai/conversations/{conversation_id}")).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant", "user", "assistant"]
    # Not even the owner can read someone else's conversation, or continue it.
    assert (await owner.get(f"/v1/ai/conversations/{conversation_id}")).status_code == 404
    assert (await ask(owner, "hi", conversation_id=conversation_id)).status_code == 404
    other = await signup(client)
    await switch_on(other)
    assert (await other.get(f"/v1/ai/conversations/{conversation_id}")).status_code == 404
    assert (await staff.delete(f"/v1/ai/conversations/{conversation_id}")).status_code == 204
    assert (await staff.get("/v1/ai/conversations")).json() == []
    assert (await owner.get("/v1/ai/status")).json()["used"] == 2


async def test_allowances_are_set_by_operators_and_announced(
    client: httpx.AsyncClient, fake: FakeModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await signup(client)
    admin = await invite_and_join(owner, role="admin")
    _, staff = await add_staff(owner)
    await switch_on(owner)
    operator = await signup(client, business="CompanyMgmt HQ")
    assert operator.email
    body = {"allowances": [{"plan_key": "growth", "questions_per_month": 1}]}
    # Not an operator, then an operator without two-step sign-in.
    assert (await operator.put("/v1/operator/ai-allowances", json=body)).status_code == 403
    monkeypatch.setattr(get_settings(), "platform_operators", [operator.email])
    refused = await operator.put("/v1/operator/ai-allowances", json=body)
    assert refused.json()["code"] == "mfa_required"
    await enable_mfa(operator)
    plans = (await operator.get("/v1/operator/ai-allowances")).json()
    assert [(p["plan_key"], p["questions_per_month"]) for p in plans][:3] == [
        ("free", 0),
        ("starter", 100),
        ("growth", 500),
    ]
    saved = await operator.put("/v1/operator/ai-allowances", json=body)
    assert saved.status_code == 200, saved.text
    # Owners and admins of every Growth workspace are told; staff aren't.
    for account, told in ((owner, True), (admin, True), (staff, False)):
        kinds = [n["kind"] for n in (await account.get("/v1/notifications")).json()["items"]]
        assert ("ai.allowance_changed" in kinds) is told
    # The new allowance applies straight away.
    assert (await ask(staff, "leave?")).status_code == 200
    used_up = await ask(staff, "leave again?")
    assert (used_up.status_code, used_up.json()["code"]) == (429, "ai_allowance_used")
    await operator.put(
        "/v1/operator/ai-allowances", json={"allowances": [{"plan_key": "growth", "questions_per_month": 0}]}
    )
    not_in_plan = await ask(staff, "leave?")
    assert (not_in_plan.status_code, not_in_plan.json()["code"]) == (402, "ai_not_in_plan")
    unknown = await operator.put("/v1/operator/ai-allowances", json={"allowances": [{"plan_key": "gold"}]})
    assert unknown.status_code == 422


# ---- The Gemini adapter -------------------------------------------------------------------


def test_schemas_are_reduced_to_what_gemini_understands() -> None:
    schema = {
        "$defs": {"Kind": {"type": "string", "enum": ["a", "b"], "title": "Kind"}},
        "type": "object",
        "title": "In",
        "additionalProperties": False,
        "properties": {
            "kind": {"$ref": "#/$defs/Kind"},
            "since": {"anyOf": [{"type": "string", "format": "date"}, {"type": "null"}], "default": None},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
        "required": ["kind"],
    }
    assert simplify(schema) == {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["a", "b"]},
            "since": {"type": "string", "nullable": True},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
        "required": ["kind"],
    }


async def test_gemini_requests_and_replies(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, Any]] = []

    def answer(request: httpx.Request) -> httpx.Response:
        sent.append(
            {
                "url": str(request.url),
                "key": request.headers.get("x-goog-api-key"),
                "body": json.loads(request.content),
            }
        )
        if request.url.path.endswith(":batchEmbedContents"):
            return httpx.Response(200, json={"embeddings": [{"values": [0.1, 0.2]}]})
        if len(sent) == 1:
            parts = [{"functionCall": {"name": "leave__balances", "args": {"year": 2026}}}]
        elif len(sent) == 2:
            parts = [{"text": "You have 7 days [1]."}]
        else:
            return httpx.Response(429, json={})
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": parts}}],
                "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 9},
            },
        )

    monkeypatch.setattr(get_settings(), "gemini_api_key", type(get_settings().gemini_api_key)("secret-key"))
    model = Gemini(transport=httpx.MockTransport(answer))
    tools = [
        Tool(
            "leave.balances",
            "Leave balances",
            {"type": "object", "properties": {"year": {"type": "integer"}}},
        )
    ]
    first = await model.generate("system", [Turn(role="user", text="Leave left?")], tools)
    assert first.tool_calls == [ToolCall("leave.balances", {"year": 2026})]
    assert (first.tokens_in, first.tokens_out) == (120, 9)
    turns = [
        Turn(role="user", text="Leave left?"),
        Turn(role="model", tool_calls=first.tool_calls),
        Turn(role="tool", tool_name="leave.balances", tool_result={"days": 7}),
    ]
    second = await model.generate("system", turns, tools)
    assert second.text == "You have 7 days [1]."
    request = sent[1]
    assert request["key"] == "secret-key"
    assert request["url"].endswith(f"models/{get_settings().gemini_model}:generateContent")
    assert request["body"]["systemInstruction"] == {"parts": [{"text": "system"}]}
    assert request["body"]["tools"][0]["functionDeclarations"][0]["name"] == "leave__balances"
    assert request["body"]["contents"][1] == {
        "role": "model",
        "parts": [{"functionCall": {"name": "leave__balances", "args": {"year": 2026}}}],
    }
    assert request["body"]["contents"][2]["parts"][0]["functionResponse"] == {
        "name": "leave__balances",
        "response": {"result": {"days": 7}},
    }
    with pytest.raises(provider.AIUnavailable, match="busy"):
        await model.generate("system", turns, tools)
    assert await model.embed(["hello"]) == [[0.1, 0.2]]


def test_a_gemini_key_is_all_it_takes(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    assert provider.available() is False
    monkeypatch.setattr(settings, "gemini_api_key", type(settings.gemini_api_key)("k"))
    assert provider.available() is True
    assert isinstance(provider.get_model(), Gemini)


async def test_conversations_stay_out_of_workspace_exports(
    client: httpx.AsyncClient, fake: FakeModel
) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner)
    await switch_on(owner)
    await ask(staff, "How many leave days do I have?")
    assert (await owner.post("/v1/auth/reauth", json={"password": owner.password})).status_code == 204
    export = await owner.get("/v1/privacy/workspace-export")
    assert export.status_code == 200, export.text
    names = zipfile.ZipFile(io.BytesIO(export.content)).namelist()
    assert "data/ai_usage.json" in names
    assert "data/ai_conversations.json" not in names
    assert "data/ai_messages.json" not in names
    mine = (await staff.get("/v1/privacy/my-data")).json()
    assert [c["title"] for c in mine["assistant_conversations"]] == ["How many leave days do I have?"]
    assert [m["role"] for m in mine["assistant_messages"]] == ["user", "assistant"]
