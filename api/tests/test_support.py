"""Contact support from the app, and operators' usage counts (nothing personal)."""

from __future__ import annotations

import httpx
import pytest

from app.core import email
from app.core.config import get_settings
from tests.helpers import signup
from tests.test_ai import enable_mfa


async def test_support_messages_reach_the_team_and_the_sender(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "support_email", "support@companymgmt.test")
    owner = await signup(client)
    email.sent.clear()
    sent = await owner.post(
        "/v1/support",
        json={"topic": "problem", "message": "Payslips show the wrong month.", "page": "/app/payroll"},
    )
    assert sent.status_code == 202, sent.text
    to_team = [m for m in email.sent if m.to == "support@companymgmt.test"]
    assert to_team
    assert to_team[0].reply_to == owner.email
    assert "/app/payroll" in to_team[0].text
    assert any(m.to == owner.email for m in email.sent)
    for _ in range(9):
        await owner.post("/v1/support", json={"topic": "idea", "message": "More please"})
    assert (await owner.post("/v1/support", json={"topic": "idea", "message": "One more"})).status_code == 429


async def test_usage_counts_are_for_operators_only(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await signup(client)
    operator = await signup(client, business="CompanyMgmt HQ")
    assert (await operator.get("/v1/operator/usage")).status_code == 403
    monkeypatch.setattr(get_settings(), "platform_operators", [operator.email])
    await enable_mfa(operator)
    usage = (await operator.get("/v1/operator/usage", params={"days": 7})).json()
    assert usage["workspaces_new"] >= 2
    joined = next(e for e in usage["events"] if e["event"] == "member.joined")
    assert joined["workspaces"] >= 2
    assert set(joined) == {"event", "count", "workspaces"}
