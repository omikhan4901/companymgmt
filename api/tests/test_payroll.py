"""Payroll through the API: salaries, a full run from draft to paid, who sees what."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import psycopg

from app.core.time import today
from app.modules.payroll import calc
from tests.helpers import Account, add_staff, invite_and_join, signup

TK = 100
DHAKA = ZoneInfo("Asia/Dhaka")


def last_month() -> str:
    first = today("Asia/Dhaka").replace(day=1)
    previous = first - timedelta(days=1)
    return f"{previous.year:04d}-{previous.month:02d}"


def working_day(period: str, day: int) -> date:
    d = date(int(period[:4]), int(period[5:]), day)
    return d + timedelta(days=1) if d.isoweekday() == 5 else d


async def employee_id(account: Account) -> str:
    return str((await account.get("/v1/leave/balances")).json()["employee_id"])


async def set_salary(owner: Account, person: str, **extra: Any) -> dict[str, Any]:
    body = {
        "employee_id": person,
        "effective_from": "2024-01-01",
        "basic": 20_800 * TK,
        "house_rent": 10_400 * TK,
        "medical": 1_500 * TK,
        "conveyance": 1_000 * TK,
        **extra,
    }
    response = await owner.post("/v1/payroll/salaries", json=body)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


async def add_shift(owner: Account, person: str, day: date, hours: float) -> None:
    start = datetime(day.year, day.month, day.day, 9, 0, tzinfo=DHAKA)
    response = await owner.post(
        "/v1/attendance/records",
        json={
            "employee_id": person,
            "clock_in_at": start.isoformat(),
            "clock_out_at": (start + timedelta(hours=hours)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text


def line(slip: dict[str, Any], code: str) -> int | None:
    return next((x["amount"] for x in slip["lines"] if x["code"] == code), None)


def slip_for(run: dict[str, Any], name: str) -> dict[str, Any]:
    return next(s for s in run["payslips"] if s["employee_name"] == name)


# ---- Settings and salaries -------------------------------------------------------------


async def test_bangladesh_defaults_keep_tax_off(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    settings = (await owner.get("/v1/payroll/settings")).json()
    assert settings["currency"] == "BDT"
    assert (settings["overtime_divisor"], settings["overtime_multiplier"]) == (208, 2)
    assert (settings["bonus_percent"], settings["bonus_min_months"]) == (100, 12)
    assert settings["tax_enabled"] is False
    assert settings["tax_table"]["tax_free"] == 375_000 * TK
    assert settings["tax_table"]["exempt_fraction"] == "1/3"
    on_without_slabs = {**settings, "tax_enabled": True, "tax_table": {"slabs": []}}
    for key in ("currency", "version"):
        on_without_slabs.pop(key)
    assert (await owner.put("/v1/payroll/settings", json=on_without_slabs)).status_code == 422
    bad = {**on_without_slabs, "tax_table": {**settings["tax_table"], "exempt_fraction": "3/2"}}
    assert (await owner.put("/v1/payroll/settings", json=bad)).status_code == 422


async def test_salaries_keep_account_numbers_secret(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner)
    person = await employee_id(staff)
    saved = await set_salary(
        owner, person, payment_method="wallet", provider="bKash", account="017 1234 5678"
    )
    assert saved["account_last4"] == "5678"
    assert saved["monthly_total"] == 33_700 * TK
    assert "account" not in saved
    owner_sql.execute("SELECT set_config('app.tenant_id', %s, false)", (owner.tenant_id,))
    stored = owner_sql.execute(
        "SELECT account_enc FROM salary_structures WHERE id = %s", (saved["id"],)
    ).fetchone()
    assert stored is not None
    assert "01712345678" not in stored[0]
    # A raise from next year keeps the same wallet without typing it again.
    raised = await set_salary(
        owner,
        person,
        effective_from=f"{today('Asia/Dhaka').year + 1}-01-01",
        basic=25_000 * TK,
        payment_method="wallet",
        provider="bKash",
    )
    assert raised["account_last4"] == "5678"
    history = (await owner.get(f"/v1/payroll/salaries/{person}")).json()
    assert [h["basic"] for h in history] == [25_000 * TK, 20_800 * TK]
    current = (await owner.get("/v1/payroll/salaries")).json()
    assert [c["basic"] for c in current if c["employee_id"] == person] == [20_800 * TK]

    for bad in (
        {"basic": 0, "house_rent": 0, "medical": 0, "conveyance": 0},
        {"payment_method": "bank", "provider": None},
        {"payment_method": "bank", "provider": "City Bank", "account": "12ab"},
    ):
        response = await owner.post(
            "/v1/payroll/salaries", json={"employee_id": person, "effective_from": "2024-02-01", **bad}
        )
        assert response.status_code == 422, bad
    intern = await owner.post(
        "/v1/payroll/salaries",
        json={"employee_id": person, "effective_from": "2024-02-01", "note": "Unpaid internship"},
    )
    assert intern.status_code == 201
    assert (await staff.get("/v1/payroll/salaries")).status_code == 403
    assert (
        await staff.post(
            "/v1/payroll/salaries", json={"employee_id": person, "effective_from": "2024-03-01", "basic": 1}
        )
    ).status_code == 403


# ---- A month, from draft to paid -------------------------------------------------------


async def test_a_full_payroll_month(client: httpx.AsyncClient, owner_sql: psycopg.Connection) -> None:
    owner = await signup(client)
    accountant = await invite_and_join(owner, role="accountant")
    _, staff = await add_staff(owner, name="Karim")
    _, other = await add_staff(owner, name="Salma")
    karim, salma = await employee_id(staff), await employee_id(other)
    await set_salary(
        owner, karim, overtime=True, payment_method="bank", provider="City Bank", account="1234567890"
    )
    await set_salary(owner, salma, basic=5_000 * TK, house_rent=0, medical=0, conveyance=0)
    period = last_month()

    # Karim: one long day (2 h overtime) and one day of unpaid leave.
    await add_shift(owner, karim, working_day(period, 3), 10)
    kinds = {k["name"]: k["id"] for k in (await owner.get("/v1/leave/types")).json()}
    off = working_day(period, 12)
    leave = await staff.post(
        "/v1/leave/requests",
        json={"leave_type_id": kinds["Unpaid leave"], "start_date": str(off), "end_date": str(off)},
    )
    assert leave.status_code == 201, leave.text
    assert (await owner.post(f"/v1/leave/requests/{leave.json()['id']}/approve", json={})).status_code == 200
    # Salma: an advance bigger than her pay.
    advance = await owner.post(
        "/v1/payroll/loans",
        json={
            "employee_id": salma,
            "label": "Advance for rent",
            "principal": 8_000 * TK,
            "installment": 8_000 * TK,
            "start_period": period,
        },
    )
    assert advance.status_code == 201, advance.text

    created = await accountant.post("/v1/payroll/runs", json={"period": period})
    assert created.status_code == 201, created.text
    run = created.json()
    assert run["status"] == "draft"
    assert {m["employee_name"] for m in run["missing"]} == {"Rahim Uddin", "Member Person"}
    k = slip_for(run, "Karim")
    start, end = calc.period_bounds(period)
    days = (end - start).days + 1
    assert line(k, "basic") == 20_800 * TK
    assert line(k, "overtime") == 400 * TK  # 20,800 / 208 = 100 an hour, twice, two hours
    assert line(k, "unpaid_leave") == calc.money(Decimal(33_700 * TK) / days)
    assert k["overtime_minutes"] == 120
    assert k["unpaid_leave_days"] == 1
    assert k["account_last4"] == "7890"
    s = slip_for(run, "Salma")
    assert (s["gross"], s["net"], s["carried_forward"]) == (5_000 * TK, 0, 3_000 * TK)
    assert run["net"] == k["net"]

    # A one-off commission, then the totals follow.
    item = await accountant.post(
        f"/v1/payroll/runs/{run['id']}/items",
        json={"employee_id": karim, "kind": "earning", "label": "Sales commission", "amount": 1_250 * TK},
    )
    assert item.status_code == 201
    run = (await accountant.get(f"/v1/payroll/runs/{run['id']}")).json()
    assert line(slip_for(run, "Karim"), "item") == 1_250 * TK
    assert (await accountant.post("/v1/payroll/runs", json={"period": period})).json()["code"] == "run_exists"

    # Staff don't see drafts.
    assert (await staff.get(f"/v1/payroll/runs/{run['id']}")).status_code == 403
    assert (await staff.get("/v1/payroll/payslips")).json() == []

    submitted = await accountant.post(f"/v1/payroll/runs/{run['id']}/submit")
    assert submitted.json()["status"] == "review"
    frozen = await accountant.post(
        f"/v1/payroll/runs/{run['id']}/items",
        json={"employee_id": karim, "kind": "earning", "label": "Late", "amount": 1},
    )
    assert frozen.json()["code"] == "wrong_status"
    # The accountant prepares; only someone allowed to approve can finalize.
    assert (await accountant.post(f"/v1/payroll/runs/{run['id']}/finalize")).status_code == 403
    # Finalizing needs a recent sign-in.
    owner_sql.execute("UPDATE auth_sessions SET reauth_at = now() - interval '1 hour'")
    stale = await owner.post(f"/v1/payroll/runs/{run['id']}/finalize")
    assert stale.json()["code"] == "reauth_required"
    assert (await owner.post("/v1/auth/reauth", json={"password": owner.password})).status_code == 204
    final = await owner.post(f"/v1/payroll/runs/{run['id']}/finalize")
    assert final.status_code == 200, final.text
    assert final.json()["status"] == "finalized"

    # Salma's advance: what her pay couldn't cover carries to next month.
    loans = (
        await owner.get("/v1/payroll/loans", params={"employee_id": salma, "include_closed": True})
    ).json()
    by_label = {x["label"]: x for x in loans}
    # The full installment counts as repaid; what didn't fit is a new advance (owed once).
    assert (by_label["Advance for rent"]["outstanding"], by_label["Advance for rent"]["status"]) == (
        0,
        "closed",
    )
    carried = by_label[f"Carried from {period}"]
    assert (carried["principal"], carried["start_period"]) == (3_000 * TK, calc_next(period))

    mine = (await staff.get("/v1/payroll/payslips")).json()
    assert [(p["period"], p["employee_name"]) for p in mine] == [(period, "Karim")]
    assert (await staff.get(f"/v1/payroll/payslips/{mine[0]['id']}")).status_code == 200
    salma_slip = slip_for(final.json(), "Salma")["id"]
    assert (await staff.get(f"/v1/payroll/payslips/{salma_slip}")).status_code == 404

    sheet = await owner.get(f"/v1/payroll/runs/{run['id']}/transfers.csv")
    assert sheet.status_code == 200
    text = sheet.text
    assert "1234567890" in text
    assert "Salma" not in text  # nothing to pay
    assert (await owner.post(f"/v1/payroll/runs/{run['id']}/paid")).json()["status"] == "paid"
    assert (await owner.delete(f"/v1/payroll/runs/{run['id']}")).status_code == 409
    audit = (await owner.get("/v1/audit", params={"action": "payroll.finalized"})).json()["items"]
    assert audit[0]["data"]["period"] == period


def calc_next(period: str) -> str:
    year, month = int(period[:4]), int(period[5:])
    return f"{year + (month == 12):04d}-{month % 12 + 1:02d}"


async def test_whoever_prepares_cannot_finalize(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    admin = await invite_and_join(owner, role="admin")
    await set_salary(owner, await employee_id(owner))
    run = (await admin.post("/v1/payroll/runs", json={"period": last_month()})).json()
    await admin.post(f"/v1/payroll/runs/{run['id']}/submit")
    denied = await admin.post(f"/v1/payroll/runs/{run['id']}/finalize")
    assert denied.status_code == 403
    assert denied.json()["code"] == "self_approval"
    # Sent back for changes, then finalized by the owner.
    assert (await owner.post(f"/v1/payroll/runs/{run['id']}/reopen")).json()["status"] == "draft"
    assert (await owner.post(f"/v1/payroll/runs/{run['id']}/recompute")).status_code == 200
    await admin.post(f"/v1/payroll/runs/{run['id']}/submit")
    assert (await owner.post(f"/v1/payroll/runs/{run['id']}/finalize")).status_code == 200


async def test_runs_need_people_and_sensible_months(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    empty = (await owner.post("/v1/payroll/runs", json={"period": last_month()})).json()
    assert empty["headcount"] == 0
    assert (await owner.post(f"/v1/payroll/runs/{empty['id']}/submit")).json()["code"] == "empty_run"
    assert (await owner.delete(f"/v1/payroll/runs/{empty['id']}")).status_code == 204
    far = today("Asia/Dhaka").year + 2
    assert (await owner.post("/v1/payroll/runs", json={"period": f"{far}-01"})).status_code == 422
    assert (await owner.post("/v1/payroll/runs", json={"period": "2026-13"})).status_code == 422


async def test_managers_see_finalized_payslips_of_their_department(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    kitchen = (await owner.post("/v1/departments", json={"name": "Kitchen"})).json()
    sales = (await owner.post("/v1/departments", json={"name": "Sales"})).json()
    manager = await invite_and_join(owner, role="manager", scope_department_id=kitchen["id"])
    _, cook = await add_staff(owner, name="Cook", scope_department_id=kitchen["id"])
    _, seller = await add_staff(owner, name="Seller", scope_department_id=sales["id"])
    for person in (cook, seller):
        await set_salary(owner, await employee_id(person))
    run = (await owner.post("/v1/payroll/runs", json={"period": last_month()})).json()
    assert (await manager.get(f"/v1/payroll/runs/{run['id']}")).status_code == 404
    assert (await manager.get("/v1/payroll/runs")).json() == []
    await owner.post(f"/v1/payroll/runs/{run['id']}/submit")
    await owner.post(f"/v1/payroll/runs/{run['id']}/finalize")
    seen = (await manager.get(f"/v1/payroll/runs/{run['id']}")).json()
    assert [p["employee_name"] for p in seen["payslips"]] == ["Cook"]
    seller_slip = slip_for(run, "Seller")["id"]
    assert (await manager.get(f"/v1/payroll/payslips/{seller_slip}")).status_code == 404
    assert (await manager.get(f"/v1/payroll/runs/{run['id']}/transfers.csv")).status_code == 403
    assert (await manager.get("/v1/payroll/salaries")).status_code == 403


async def test_tax_and_bonus_when_switched_on(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    me = await employee_id(owner)
    await set_salary(
        owner, me, basic=60_000 * TK, house_rent=30_000 * TK, medical=6_000 * TK, conveyance=4_000 * TK
    )
    settings = (await owner.get("/v1/payroll/settings")).json()
    body = {k: v for k, v in settings.items() if k not in ("currency", "version")}
    on = await owner.put("/v1/payroll/settings", json={**body, "tax_enabled": True})
    assert on.status_code == 200, on.text
    run = (
        await owner.post(
            "/v1/payroll/runs", json={"period": last_month(), "bonus_label": "Eid-ul-Fitr bonus"}
        )
    ).json()
    slip = slip_for(run, "Rahim Uddin")
    assert line(slip, "bonus") == 60_000 * TK  # owner profile has no joining date: long service
    assert line(slip, "tax") is not None
    assert line(slip, "tax") > 0


async def test_five_hundred_people_in_seconds(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    """The plan's bar: a 500-person workspace runs payroll in under a minute."""
    owner = await signup(client)
    period = last_month()
    _, end = calc.period_bounds(period)
    owner_sql.execute("SELECT set_config('app.tenant_id', %s, false)", (owner.tenant_id,))
    owner_sql.execute(
        """
        INSERT INTO employees (id, tenant_id, full_name, employment_type, status, version)
        SELECT gen_random_uuid(), %s, 'Worker ' || n, 'full_time', 'active', 1 FROM generate_series(1, 500) n
        """,
        (owner.tenant_id,),
    )
    owner_sql.execute(
        """
        INSERT INTO salary_structures (id, tenant_id, employee_id, effective_from, pay_rule, basic,
          house_rent, medical, conveyance, other, rate, overtime, deduct_tax, payment_method, version)
        SELECT gen_random_uuid(), tenant_id, id, '2024-01-01', 'monthly', 1500000, 750000, 100000, 50000,
          0, 0, true, true, 'cash', 1
        FROM employees WHERE full_name LIKE 'Worker %%'
        """
    )
    owner_sql.execute(
        """
        INSERT INTO attendance_records (id, tenant_id, employee_id, business_date, clock_in_at, clock_out_at,
          minutes, status, source, version)
        SELECT gen_random_uuid(), e.tenant_id, e.id, d::date, d + interval '3 hours', d + interval '13 hours',
          600, 'closed', 'manual', 1
        FROM employees e, generate_series(%s::date - 9, %s::date, interval '1 day') d
        WHERE e.full_name LIKE 'Worker %%'
        """,
        (end, end),
    )
    started = datetime.now(DHAKA)
    response = await owner.post("/v1/payroll/runs", json={"period": period})
    elapsed = (datetime.now(DHAKA) - started).total_seconds()
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["headcount"] == 500
    # Ten 10-hour days: 20 hours of overtime at basic / 208, times 2.
    overtime = calc.money(Decimal(1_500_000) / 208 * 2 * 20)
    assert {line(s, "overtime") for s in run["payslips"] if s["employee_name"].startswith("Worker")} == {
        overtime
    }
    assert elapsed < 60, elapsed
