"""The shop pack: taxes the workspace sets, selling at the till (also offline), the cash
drawer, credit sales and dues, returns, voids, receipts, the period's tax totals, and
expenses with receipt photos and petty cash."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from tests.helpers import Account, add_staff, signup

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


async def shop(client: httpx.AsyncClient) -> dict[str, Any]:
    owner = await signup(client)
    await owner.put(
        "/v1/workspace/modules", json={"modules": ["attendance", "sales", "customers", "expenses"]}
    )
    vat = (
        await owner.post(
            "/v1/sales/tax-rates", json={"name": "VAT", "code": "VAT15", "percent": "15", "default": True}
        )
    ).json()
    tea = (
        await owner.post("/v1/sales/products", json={"name": "Tea", "price": 2000, "tax_rate_ids": []})
    ).json()
    cake = (await owner.post("/v1/sales/products", json={"name": "Cake", "price": 11500})).json()
    _, cashier = await add_staff(owner, name="Mitu", role="cashier")
    return {"owner": owner, "cashier": cashier, "vat": vat, "tea": tea, "cake": cake}


async def sale(account: Account, lines: list[dict[str, Any]], **extra: Any) -> httpx.Response:
    return await account.post("/v1/sales", json={"client_id": str(uuid.uuid4()), "lines": lines, **extra})


async def test_selling_at_the_till(client: httpx.AsyncClient) -> None:
    s = await shop(client)
    cashier = s["cashier"]
    assert s["cake"]["tax_rate_ids"] == [s["vat"]["id"]]  # the default rate
    # The drawer must be open to sell.
    closed = await sale(cashier, [{"product_id": s["tea"]["id"]}], paid_cash=2000)
    assert (closed.status_code, closed.json()["code"]) == (409, "drawer_closed")
    assert (await cashier.post("/v1/sales/drawer/open", json={"opening_float": 50000})).status_code == 201

    made = await sale(
        cashier,
        [{"product_id": s["tea"]["id"], "quantity": "2"}, {"product_id": s["cake"]["id"]}],
        paid_cash=20000,
    )
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["number"] == 1
    # Prices include VAT by default: cake 115.00 = 100.00 + 15.00 VAT; tea has no tax.
    assert (body["net"], body["tax"], body["total"], body["change"]) == (14000, 1500, 15500, 4500)
    assert body["lines"][1]["taxes"][0]["code"] == "VAT15"

    # A cashier can't change prices or see everyone's figures.
    cheaper = await sale(cashier, [{"product_id": s["cake"]["id"], "unit_price": 100}], paid_cash=100)
    assert (cheaper.status_code, cheaper.json()["code"]) == (403, "price_change")
    assert (
        await cashier.get("/v1/sales/summary", params={"from": "2026-01-01", "to": "2026-01-02"})
    ).status_code == 403
    short = await sale(cashier, [{"product_id": s["cake"]["id"]}], paid_cash=100)
    assert short.status_code == 422

    # Something not in the catalogue, typed in.
    loose = await sale(
        cashier, [{"name": "Loose biscuits", "unit_price": 500, "quantity": "0.5"}], paid_cash=500
    )
    # Prices include VAT, typed-in ones too: 2.50 in total, of which 15% VAT is 0.33.
    assert (loose.json()["total"], loose.json()["tax"]) == (250, 33)


async def test_offline_sales_are_kept_once(client: httpx.AsyncClient) -> None:
    s = await shop(client)
    owner = s["owner"]
    await owner.post("/v1/sales/drawer/open", json={})
    body = {
        "client_id": str(uuid.uuid4()),
        "lines": [{"product_id": s["tea"]["id"]}],
        "paid_cash": 2000,
        "sold_at": (datetime.now(UTC) - timedelta(minutes=30)).isoformat(),
    }
    first = await owner.post("/v1/sales", json=body)
    again = await owner.post("/v1/sales", json=body)
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["id"] == again.json()["id"]
    assert len((await owner.get("/v1/sales")).json()) == 1
    too_old = {**body, "client_id": str(uuid.uuid4()), "sold_at": "2020-01-01T00:00:00+00:00"}
    assert (await owner.post("/v1/sales", json=too_old)).status_code == 422


async def test_closing_the_drawer_counts_the_cash(client: httpx.AsyncClient) -> None:
    s = await shop(client)
    owner = s["owner"]
    await owner.post("/v1/sales/drawer/open", json={"opening_float": 10000})
    await sale(owner, [{"product_id": s["tea"]["id"]}], paid_cash=5000)  # 50 in, 30 change
    await owner.post("/v1/expenses", json={"amount": 1500, "paid_from": "drawer", "payee": "Milk"})
    drawer = (await owner.get("/v1/sales/drawer")).json()
    assert (drawer["cash_sales"], drawer["cash_expenses"], drawer["expected_cash"]) == (2000, 1500, 10500)
    closed = (await owner.post("/v1/sales/drawer/close", json={"counted_cash": 10400})).json()
    assert (closed["expected_cash"], closed["difference"]) == (10500, -100)
    assert (await owner.get("/v1/sales/drawer")).json() is None


async def test_credit_sales_dues_and_payments(client: httpx.AsyncClient) -> None:
    s = await shop(client)
    owner = s["owner"]
    await owner.post("/v1/sales/drawer/open", json={})
    karim = (
        await owner.post(
            "/v1/customers", json={"name": "Karim", "phone": "01711000000", "credit_limit": 20000}
        )
    ).json()
    credit = await sale(owner, [{"product_id": s["cake"]["id"]}], customer_id=karim["id"], paid_cash=1500)
    assert credit.status_code == 201, credit.text
    assert credit.json()["on_account"] == 10000
    assert (await owner.get(f"/v1/customers/{karim['id']}")).json()["balance"] == 10000
    over = await sale(
        owner, [{"product_id": s["cake"]["id"]}, {"product_id": s["cake"]["id"]}], customer_id=karim["id"]
    )
    assert (over.status_code, over.json()["code"]) == (422, "credit_limit")

    paid = await owner.post(f"/v1/customers/{karim['id']}/payments", json={"amount": 4000})
    assert paid.json()["balance"] == 6000
    owing = (await owner.get("/v1/customers", params={"owing": True})).json()
    assert [c["name"] for c in owing] == ["Karim"]
    statement = (await owner.get(f"/v1/customers/{karim['id']}/statement")).json()
    assert [(e["kind"], e["amount"], e["balance"]) for e in statement["entries"]] == [
        ("sale", 10000, 10000),
        ("payment", -4000, 6000),
    ]
    assert statement["closing"] == 6000


async def test_returns_and_voids(client: httpx.AsyncClient) -> None:
    s = await shop(client)
    owner = s["owner"]
    await owner.post("/v1/sales/drawer/open", json={})
    sold = (await sale(owner, [{"product_id": s["cake"]["id"], "quantity": "2"}], paid_cash=23000)).json()
    line = sold["lines"][0]["id"]
    back = await owner.post(
        f"/v1/sales/{sold['id']}/returns",
        json={"client_id": str(uuid.uuid4()), "lines": [{"line_id": line, "quantity": "1"}]},
    )
    assert back.status_code == 201, back.text
    assert (back.json()["kind"], back.json()["total"], back.json()["tax"]) == ("return", -11500, -1500)
    again = await owner.post(
        f"/v1/sales/{sold['id']}/returns",
        json={"client_id": str(uuid.uuid4()), "lines": [{"line_id": line, "quantity": "2"}]},
    )
    assert again.status_code == 422  # only one left
    assert (await owner.get(f"/v1/sales/{sold['id']}")).json()["lines"][0]["returned"] == "1.000"
    blocked = await owner.post(f"/v1/sales/{sold['id']}/void", json={"reason": "Mistake"})
    assert (blocked.status_code, blocked.json()["code"]) == (409, "has_returns")

    other = (await sale(owner, [{"product_id": s["tea"]["id"]}], paid_cash=2000)).json()
    voided = (await owner.post(f"/v1/sales/{other['id']}/void", json={"reason": "Typed twice"})).json()
    assert voided["status"] == "voided"

    today = datetime.now(UTC).date()
    summary = (
        await owner.get(
            "/v1/sales/summary",
            params={"from": str(today - timedelta(days=1)), "to": str(today + timedelta(days=1))},
        )
    ).json()
    assert summary["count"] == 1  # the void doesn't count
    assert summary["total"] == 23000 - 11500
    assert summary["returns"] == 11500
    [vat] = summary["taxes"]
    assert (vat["code"], vat["amount"], vat["taxable"]) == ("VAT15", 1500, 10000)


async def test_receipts_show_what_the_workspace_set(client: httpx.AsyncClient) -> None:
    s = await shop(client)
    owner = s["owner"]
    current = (await owner.get("/v1/sales/settings")).json()
    assert current["prices_include_tax"] is True
    saved = await owner.put(
        "/v1/sales/settings",
        json={
            "prices_include_tax": False,
            "cash_rounding": 100,
            "tax_id_label": "BIN",
            "tax_id": "000123456-0101",
            "receipt_footer": "Thank you!",
        },
    )
    assert saved.status_code == 200, saved.text
    await owner.post("/v1/sales/drawer/open", json={})
    sold = (await sale(owner, [{"product_id": s["cake"]["id"]}], paid_cash=20000)).json()
    # Prices now exclude VAT: 115.00 + 17.25 = 132.25, rounded to 132.00 for cash.
    assert (sold["tax"], sold["rounding"], sold["total"]) == (1725, -25, 13200)
    receipt = (await owner.get(f"/v1/sales/{sold['id']}/receipt")).json()
    assert (receipt["tax_id_label"], receipt["tax_id"], receipt["footer"]) == (
        "BIN",
        "000123456-0101",
        "Thank you!",
    )
    assert receipt["taxes"][0]["amount"] == 1725


async def test_expenses_with_receipts_and_petty_cash(client: httpx.AsyncClient) -> None:
    s = await shop(client)
    owner, cashier = s["owner"], s["cashier"]
    categories = (await owner.get("/v1/expenses/categories")).json()
    assert "Rent" in {c["name"] for c in categories}
    await owner.post("/v1/expenses/top-ups", json={"amount": 100000})
    mine = await cashier.post(
        "/v1/expenses", json={"amount": 2500, "category_id": categories[0]["id"], "payee": "Shop"}
    )
    assert mine.status_code == 201, mine.text
    expense = mine.json()
    photo = await cashier.put(
        f"/v1/expenses/{expense['id']}/receipt",
        params={"filename": "bill.png"},
        content=PNG,
        headers={"content-type": "application/octet-stream"},
    )
    assert photo.json()["has_receipt"] is True
    not_a_photo = await cashier.put(
        f"/v1/expenses/{expense['id']}/receipt",
        params={"filename": "bill.png"},
        content=b"<html>",
        headers={"content-type": "application/octet-stream"},
    )
    assert (not_a_photo.status_code, not_a_photo.json()["code"]) == (422, "receipt_type")
    download = await owner.get(f"/v1/expenses/{expense['id']}/receipt")
    assert download.content == PNG
    everything = (await owner.get("/v1/expenses")).json()
    assert (everything["total"], everything["petty_cash"]) == (2500, 97500)
    # A cashier sees only what they recorded, and can't delete.
    await owner.post("/v1/expenses", json={"amount": 9000, "payee": "Landlord"})
    assert [e["payee"] for e in (await cashier.get("/v1/expenses")).json()["items"]] == ["Shop"]
    assert (await cashier.delete(f"/v1/expenses/{expense['id']}")).status_code == 403
