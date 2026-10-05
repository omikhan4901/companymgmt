"""Inventory and the books end to end: stock follows sales, purchases cost stock in at a
weighted average, everything posts to balanced books, reports agree, and tax returns
fill from templates the workspace defines."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.core import outbox
from tests.helpers import Account, signup

MODULES = ["attendance", "sales", "customers", "expenses", "inventory", "accounting"]


async def books(client: httpx.AsyncClient) -> dict[str, Any]:
    owner = await signup(client)
    switched = await owner.put("/v1/workspace/modules", json={"modules": MODULES})
    assert switched.status_code == 200, switched.text
    vat = (
        await owner.post("/v1/sales/tax-rates", json={"name": "VAT", "code": "VAT15", "percent": "15"})
    ).json()
    rice = (
        await owner.post(
            "/v1/sales/products", json={"name": "Rice 1kg", "price": 11500, "tax_rate_ids": [vat["id"]]}
        )
    ).json()
    await owner.post("/v1/sales/drawer/open", json={})
    return {"owner": owner, "vat": vat, "rice": rice}


async def settle() -> None:
    """Deliver the outbox (postings run after the change is saved)."""
    for _ in range(4):
        await outbox.dispatch()


async def sell(owner: Account, product_id: str, quantity: str = "1", paid: int = 100000) -> dict[str, Any]:
    response = await owner.post(
        "/v1/sales",
        json={
            "client_id": str(uuid.uuid4()),
            "lines": [{"product_id": product_id, "quantity": quantity}],
            "paid_cash": paid,
        },
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


def today() -> str:
    # The workspace keeps its books in its own time zone (signup's default, Asia/Dhaka),
    # so "today" is Dhaka's date, not UTC's (they differ from 18:00 to 24:00 UTC).
    return str(datetime.now(ZoneInfo("Asia/Dhaka")).date())


async def test_stock_follows_purchases_sales_and_counts(client: httpx.AsyncClient) -> None:
    b = await books(client)
    owner, rice = b["owner"], b["rice"]
    supplier = (await owner.post("/v1/inventory/suppliers", json={"name": "Wholesaler"})).json()
    first = await owner.post(
        "/v1/inventory/purchases",
        json={
            "supplier_id": supplier["id"],
            "lines": [{"product_id": rice["id"], "quantity": "10", "unit_cost": "8000"}],
            "paid": 30000,
        },
    )
    assert first.status_code == 201, first.text
    await owner.post(
        "/v1/inventory/purchases",
        json={"lines": [{"product_id": rice["id"], "quantity": "10", "unit_cost": "9000"}], "paid": 90000},
    )
    [item] = (await owner.get("/v1/inventory/stock")).json()
    assert (item["quantity"], item["average_cost"]) == ("20.000", "8500.0000")
    suppliers = (await owner.get("/v1/inventory/suppliers")).json()
    assert suppliers[0]["balance"] == 50000

    await sell(owner, rice["id"], "3")
    [item] = (await owner.get("/v1/inventory/stock")).json()
    assert item["quantity"] == "17.000"

    counted = await owner.post(
        "/v1/inventory/counts", json={"lines": [{"product_id": rice["id"], "counted": "16"}]}
    )
    assert counted.json()["value"] == -8500
    moves = [m["kind"] for m in (await owner.get(f"/v1/inventory/items/{rice['id']}/movements")).json()]
    assert moves == ["count", "sale", "purchase", "purchase"]

    # Low stock tells the people who reorder.
    await owner.put(f"/v1/inventory/items/{rice['id']}", json={"track": True, "reorder_level": "15"})
    await sell(owner, rice["id"], "2")
    notes = (await owner.get("/v1/notifications")).json()["items"]
    assert any(n["kind"] == "stock.low" for n in notes)


async def test_everything_posts_to_balanced_books(client: httpx.AsyncClient) -> None:
    b = await books(client)
    owner, rice = b["owner"], b["rice"]
    await owner.post(
        "/v1/inventory/opening", json={"product_id": rice["id"], "quantity": "10", "unit_cost": "8000"}
    )
    sold = await sell(owner, rice["id"], "2")  # 230.00 incl. 30.00 VAT
    karim = (await owner.post("/v1/customers", json={"name": "Karim"})).json()
    await owner.post(
        "/v1/sales",
        json={
            "client_id": str(uuid.uuid4()),
            "lines": [{"product_id": rice["id"]}],
            "customer_id": karim["id"],
            "paid_cash": 0,
        },
    )
    await owner.post(f"/v1/customers/{karim['id']}/payments", json={"amount": 5000})
    await owner.post("/v1/expenses", json={"amount": 2000, "paid_from": "drawer", "payee": "Tea"})
    await owner.post(f"/v1/sales/{sold['id']}/void", json={"reason": "Test"})
    await settle()

    trial = (await owner.get("/v1/accounting/trial-balance", params={"as_of": today()})).json()
    assert trial["debit"] == trial["credit"]
    sheet = (await owner.get("/v1/accounting/balance-sheet", params={"as_of": today()})).json()
    assert sheet["balanced"] is True
    pl = (await owner.get("/v1/accounting/profit-and-loss", params={"from": today(), "to": today()})).json()
    # One sale stands (the other was voided): 100.00 sales, 80.00 cost, 20.00 tea.
    assert pl["total_income"] == 10000
    assert pl["total_expenses"] == 8000 + 2000
    assert pl["profit"] == 0

    # The books can be filled again from scratch without posting anything twice.
    assert (await owner.post("/v1/accounting/backfill")).json()["entries"] == 0


async def test_tax_returns_fill_from_the_workspaces_own_template(client: httpx.AsyncClient) -> None:
    b = await books(client)
    owner, rice, vat = b["owner"], b["rice"], b["vat"]
    await owner.post(
        "/v1/inventory/purchases",
        json={
            "lines": [
                {"product_id": rice["id"], "quantity": "10", "unit_cost": "8000", "tax_rate_id": vat["id"]}
            ],
            "paid": 92000,
        },
    )
    await sell(owner, rice["id"], "4")  # 460.00 incl. 60.00 VAT on 400.00
    await settle()
    template = await owner.post(
        "/v1/accounting/tax-returns",
        json={
            "name": "Monthly VAT",
            "boxes": [
                {"code": "1", "label": "Sales at 15%", "sources": [{"kind": "tax_base", "ids": [vat["id"]]}]},
                {"code": "2", "label": "Output VAT", "sources": [{"kind": "tax_amount", "ids": [vat["id"]]}]},
                {
                    "code": "3",
                    "label": "Input VAT",
                    "sources": [{"kind": "tax_amount", "ids": [vat["id"]], "side": "input"}],
                },
                {
                    "code": "4",
                    "label": "To pay",
                    "sources": [{"kind": "boxes", "ids": ["2"]}, {"kind": "boxes", "ids": ["3"], "sign": -1}],
                },
            ],
        },
    )
    assert template.status_code == 201, template.text
    filled = (
        await owner.get(
            f"/v1/accounting/tax-returns/{template.json()['id']}/fill",
            params={"from": today(), "to": today()},
        )
    ).json()
    assert {b["code"]: b["amount"] for b in filled["boxes"]} == {
        "1": 40000,
        "2": 6000,
        "3": 12000,
        "4": -6000,
    }
    # A box can only add up boxes above it.
    bad = await owner.post(
        "/v1/accounting/tax-returns",
        json={
            "name": "Bad",
            "boxes": [{"code": "1", "label": "x", "sources": [{"kind": "boxes", "ids": ["2"]}]}],
        },
    )
    assert bad.status_code == 422


async def test_entries_by_hand_and_locked_periods(client: httpx.AsyncClient) -> None:
    b = await books(client)
    owner = b["owner"]
    accounts = {a["role"]: a for a in (await owner.get("/v1/accounting/accounts")).json() if a["role"]}
    entry = {
        "entry_date": today(),
        "memo": "Owner put money in",
        "lines": [
            {"account_id": accounts["bank"]["id"], "debit": 500000},
            {"account_id": accounts["capital"]["id"], "credit": 500000},
        ],
    }
    assert (await owner.post("/v1/accounting/entries", json=entry)).status_code == 201
    lopsided = {**entry, "lines": [{**entry["lines"][0]}, {**entry["lines"][1], "credit": 1}]}
    assert (await owner.post("/v1/accounting/entries", json=lopsided)).status_code == 422
    yesterday = str(datetime.fromisoformat(today()).date() - timedelta(days=1))
    await owner.put("/v1/accounting/settings", json={"locked_until": yesterday})
    locked = await owner.post("/v1/accounting/entries", json={**entry, "entry_date": yesterday})
    assert (locked.status_code, locked.json()["code"]) == (409, "period_locked")
    book = (await owner.get("/v1/accounting/cash-book", params={"from": today(), "to": today()})).json()
    assert book["closing"] == 500000
