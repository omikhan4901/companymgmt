"""Leave: defaults per country, counting days, balances, the approval flow and who sees what."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import httpx

from app.core.time import today
from app.modules.leave.models import LeaveType
from app.modules.leave.service import entitled
from tests.helpers import Account, add_staff, if_match, invite_and_join, signup

NEXT = today("Asia/Dhaka").year + 1


def sunday_in_march(year: int = NEXT) -> date:
    day = date(year, 3, 1)
    return day + timedelta(days=(7 - day.isoweekday()) % 7)


async def types(account: Account) -> dict[str, dict[str, Any]]:
    response = await account.get("/v1/leave/types")
    assert response.status_code == 200, response.text
    return {t["name"]: t for t in response.json()}


async def balance(account: Account, name: str, **params: Any) -> dict[str, Any]:
    response = await account.get("/v1/leave/balances", params={"year": NEXT, **params})
    assert response.status_code == 200, response.text
    return next(b for b in response.json()["balances"] if b["name"] == name)


async def ask(
    account: Account, kind: str, start: date, end: date | None = None, **extra: Any
) -> httpx.Response:
    type_id = (await types(account))[kind]["id"]
    body = {"leave_type_id": type_id, "start_date": str(start), "end_date": str(end or start), **extra}
    return await account.post("/v1/leave/requests", json=body)


async def employee_id(account: Account) -> str:
    return str((await account.get("/v1/leave/balances")).json()["employee_id"])


# ---- Defaults ----------------------------------------------------------------------------


async def test_bangladesh_workspace_starts_with_labour_act_defaults(client: httpx.AsyncClient) -> None:
    owner = await signup(client, country="BD")
    kinds = await types(owner)
    assert list(kinds) == ["Casual leave", "Sick leave", "Earned leave", "Maternity leave", "Unpaid leave"]
    assert kinds["Earned leave"]["accrual"] == "monthly"
    assert kinds["Earned leave"]["carry_over_max"] == 40
    assert kinds["Maternity leave"]["calendar_days"] is True
    assert kinds["Unpaid leave"]["days_per_year"] is None
    assert (await owner.get("/v1/leave/policy")).json() == {"weekly_off": [5], "team_calendar": True}


async def test_other_countries_get_a_general_set(client: httpx.AsyncClient) -> None:
    owner = await signup(client, country="GB", timezone="Europe/London")
    assert list(await types(owner)) == ["Annual leave", "Sick leave", "Unpaid leave"]
    assert (await owner.get("/v1/leave/policy")).json()["weekly_off"] == [6, 7]
    gulf = await signup(client, country="SA", timezone="Asia/Riyadh")
    assert (await gulf.get("/v1/leave/policy")).json()["weekly_off"] == [5, 6]


async def test_switching_leave_on_later_sets_it_up(client: httpx.AsyncClient) -> None:
    owner = await signup(client, business_type="shop")
    off = await owner.get("/v1/leave/types")
    assert off.status_code == 402
    assert off.json()["code"] == "module_off"
    response = await owner.put("/v1/workspace/modules", json={"modules": ["attendance", "leave"]})
    assert response.status_code == 200, response.text
    assert len(await types(owner)) == 5
    # Switching off and on again doesn't duplicate anything.
    await owner.put("/v1/workspace/modules", json={"modules": ["attendance"]})
    await owner.put("/v1/workspace/modules", json={"modules": ["attendance", "leave"]})
    assert len(await types(owner)) == 5


# ---- Counting days -----------------------------------------------------------------------


async def test_days_skip_the_weekly_off_and_holidays(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    sunday = sunday_in_march()
    tuesday, friday, saturday = (
        sunday + timedelta(days=2),
        sunday + timedelta(days=5),
        sunday + timedelta(days=6),
    )
    assert (
        await owner.post("/v1/leave/holidays", json={"day": str(tuesday), "name": "Holiday"})
    ).status_code == 201
    other = (await owner.post("/v1/branches", json={"name": "Station Road"})).json()
    wednesday = sunday + timedelta(days=3)
    await owner.post(
        "/v1/leave/holidays", json={"day": str(wednesday), "name": "Local", "branch_id": other["id"]}
    )
    casual = (await types(owner))["Casual leave"]["id"]
    quote = await owner.get(
        "/v1/leave/quote", params={"leave_type_id": casual, "from": str(sunday), "to": str(saturday)}
    )
    assert quote.status_code == 200, quote.text
    assert quote.json() == {
        "days": 5,
        "available": 10,
        "enough": True,
        "skipped": [str(tuesday), str(friday)],
    }
    maternity = await ask(owner, "Maternity leave", sunday, saturday)
    assert maternity.status_code == 201
    assert maternity.json()["days"] == 7


async def test_half_days_and_range_rules(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    sunday = sunday_in_march()
    half = await ask(owner, "Casual leave", sunday, half_day="morning")
    assert half.status_code == 201, half.text
    assert half.json()["days"] == 0.5
    cases = [
        (("Casual leave", sunday + timedelta(days=7), sunday + timedelta(days=8)), {"half_day": "afternoon"}),
        (("Maternity leave", sunday + timedelta(days=14), None), {"half_day": "morning"}),
        (("Casual leave", sunday + timedelta(days=1), sunday), {}),
        (("Casual leave", date(NEXT, 12, 30), date(NEXT + 1, 1, 2)), {}),
        (("Casual leave", date(NEXT + 1, 3, 1), None), {}),
    ]
    for (kind, start, end), extra in cases:
        response = await ask(owner, kind, start, end, **extra)
        assert response.status_code == 422, (kind, start, end, extra)
    crossing = await ask(owner, "Casual leave", date(NEXT, 12, 30), date(NEXT + 1, 1, 2))
    assert crossing.json()["code"] == "crosses_year"
    friday = sunday + timedelta(days=5)
    only_off = await ask(owner, "Casual leave", friday)
    assert only_off.json()["code"] == "no_working_days"


# ---- Balances ----------------------------------------------------------------------------


def kind(days: int | None, *, accrual: str = "yearly", prorate: bool = True) -> LeaveType:
    return LeaveType(days_per_year=None if days is None else Decimal(days), accrual=accrual, prorate=prorate)


def test_entitlement_share_and_accrual() -> None:
    year = 2030
    end = date(year, 12, 31)
    assert entitled(kind(10), None, year, end) == 10
    # Joined in July: half the year.
    assert entitled(kind(10), date(year, 7, 15), year, end) == 5
    # Rounded down to half days.
    assert entitled(kind(14), date(year, 10, 1), year, end) == Decimal("3.5")
    assert entitled(kind(10), date(year + 1, 1, 1), year, end) == 0
    assert entitled(kind(10, prorate=False), date(year, 12, 1), year, end) == 10
    # Monthly: earned month by month.
    assert entitled(kind(18, accrual="monthly"), None, year, date(year, 3, 10)) == Decimal("4.5")
    assert entitled(kind(18, accrual="monthly"), date(year, 2, 1), year, date(year, 3, 10)) == 3
    assert entitled(kind(18, accrual="monthly"), None, year, date(year - 1, 6, 1)) == 0
    assert entitled(kind(18, accrual="monthly"), None, year, date(year + 1, 6, 1)) == 18
    assert entitled(kind(None), None, year, end) == 0


async def test_balance_caps_requests_and_counts_pending(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    sunday = sunday_in_march()
    first = await ask(owner, "Casual leave", sunday, sunday + timedelta(days=6))
    assert first.status_code == 201
    assert first.json()["days"] == 6
    assert first.json()["status"] == "pending"
    casual = await balance(owner, "Casual leave")
    assert (casual["entitled"], casual["pending"], casual["used"], casual["available"]) == (10, 6, 0, 4)
    week_later = sunday + timedelta(days=7)
    too_much = await ask(owner, "Casual leave", week_later, week_later + timedelta(days=6))
    assert too_much.status_code == 422
    assert too_much.json()["code"] == "not_enough_balance"
    assert too_much.json()["available"] == 4
    overlap = await ask(owner, "Sick leave", sunday + timedelta(days=1))
    assert overlap.status_code == 409
    assert overlap.json()["code"] == "overlap"
    unpaid = await ask(owner, "Unpaid leave", week_later, week_later + timedelta(days=30))
    assert unpaid.status_code == 201
    unlimited = await balance(owner, "Unpaid leave")
    assert unlimited["unlimited"] is True
    assert unlimited["available"] is None


async def test_carry_over_and_adjustments(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    me = await employee_id(owner)
    kinds = await types(owner)
    earned = await balance(owner, "Earned leave")
    # Nothing taken this year: 18 days carried over (limit 40); none earned yet next year.
    assert (earned["carried_over"], earned["entitled"], earned["full_year"]) == (18, 0, 18)
    assert earned["available"] == 18
    assert (await balance(owner, "Casual leave"))["carried_over"] == 0
    cut = await owner.post(
        "/v1/leave/adjustments",
        json={
            "employee_id": me,
            "leave_type_id": kinds["Earned leave"]["id"],
            "year": NEXT - 1,
            "days": -10,
            "reason": "Taken before we used the app",
        },
    )
    assert cut.status_code == 201, cut.text
    assert (await balance(owner, "Earned leave"))["carried_over"] == 8
    bonus = await owner.post(
        "/v1/leave/adjustments",
        json={
            "employee_id": me,
            "leave_type_id": kinds["Casual leave"]["id"],
            "year": NEXT,
            "days": 2.5,
            "reason": "Worked on a holiday",
        },
    )
    assert bonus.status_code == 201
    casual = await balance(owner, "Casual leave")
    assert (casual["adjusted"], casual["available"]) == (2.5, 12.5)
    listed = (await owner.get("/v1/leave/adjustments", params={"year": NEXT})).json()
    assert [a["days"] for a in listed] == [2.5]
    for bad in (
        {"leave_type_id": kinds["Unpaid leave"]["id"], "days": 1},
        {"leave_type_id": kinds["Casual leave"]["id"], "days": 0},
        {"leave_type_id": kinds["Casual leave"]["id"], "days": 0.3},
    ):
        body = {"employee_id": me, "year": NEXT, "reason": "Testing", **bad}
        assert (await owner.post("/v1/leave/adjustments", json=body)).status_code == 422, bad


# ---- Asking, approving, cancelling -------------------------------------------------------


async def test_approval_flow(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    manager = await invite_and_join(owner, role="manager")
    _, staff = await add_staff(owner, name="Karim")
    sunday = sunday_in_march()
    request = (await ask(staff, "Sick leave", sunday, sunday + timedelta(days=1), reason="Fever")).json()
    assert request["employee_name"] == "Karim"
    assert request["leave_type_name"] == "Sick leave"

    assert (await staff.post(f"/v1/leave/requests/{request['id']}/approve", json={})).status_code == 403
    queue = (await manager.get("/v1/leave/requests", params={"status": "pending"})).json()
    assert [r["id"] for r in queue] == [request["id"]]
    approved = await manager.post(f"/v1/leave/requests/{request['id']}/approve", json={"note": "Get well"})
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    again = await manager.post(f"/v1/leave/requests/{request['id']}/reject", json={})
    assert again.json()["code"] == "already_decided"
    sick = await balance(staff, "Sick leave")
    assert (sick["used"], sick["pending"], sick["available"]) == (2, 0, 12)

    # A manager can't approve their own leave; the owner can.
    own = (await ask(manager, "Casual leave", sunday + timedelta(days=14))).json()
    denied = await manager.post(f"/v1/leave/requests/{own['id']}/approve", json={})
    assert denied.status_code == 403
    assert denied.json()["code"] == "self_approval"
    owners = (await ask(owner, "Casual leave", sunday + timedelta(days=14))).json()
    assert (await owner.post(f"/v1/leave/requests/{owners['id']}/approve", json={})).status_code == 200

    rejected = (await ask(staff, "Casual leave", sunday + timedelta(days=21))).json()
    response = await manager.post(f"/v1/leave/requests/{rejected['id']}/reject", json={"note": "Busy week"})
    assert response.json()["decision_note"] == "Busy week"

    # Future approved leave can still be cancelled by the person; the days come back.
    cancelled = await staff.post(f"/v1/leave/requests/{request['id']}/cancel", json={})
    assert cancelled.status_code == 200
    assert (await balance(staff, "Sick leave"))["available"] == 14
    closed = await staff.post(f"/v1/leave/requests/{request['id']}/cancel", json={})
    assert closed.status_code == 409

    audit = (await owner.get("/v1/audit", params={"action": "leave.approved"})).json()["items"]
    sick_approval = next(e["data"] for e in audit if e["data"]["employee"] == "Karim")
    assert sick_approval["type"] == "Sick leave"
    assert "reason" not in sick_approval


async def test_approval_rechecks_the_balance(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner)
    sunday = sunday_in_march()
    request = (await ask(staff, "Casual leave", sunday, sunday + timedelta(days=6))).json()
    casual = (await types(owner))["Casual leave"]
    await owner.patch(
        f"/v1/leave/types/{casual['id']}", json={"days_per_year": 3}, headers=if_match(casual["version"])
    )
    blocked = await owner.post(f"/v1/leave/requests/{request['id']}/approve", json={})
    assert blocked.status_code == 422
    assert blocked.json()["code"] == "not_enough_balance"


async def test_started_leave_is_cancelled_by_a_manager_not_the_person(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    await owner.put("/v1/leave/policy", json={"weekly_off": [], "team_calendar": True})
    _, staff = await add_staff(owner)
    now = today("Asia/Dhaka")
    request = (await ask(staff, "Unpaid leave", now)).json()
    await owner.post(f"/v1/leave/requests/{request['id']}/approve", json={})
    late = await staff.post(f"/v1/leave/requests/{request['id']}/cancel", json={})
    assert late.status_code == 409
    assert late.json()["code"] == "already_started"
    assert (await owner.post(f"/v1/leave/requests/{request['id']}/cancel", json={})).status_code == 200


async def test_managers_ask_for_others_within_their_department(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    kitchen = (await owner.post("/v1/departments", json={"name": "Kitchen"})).json()
    sales = (await owner.post("/v1/departments", json={"name": "Sales"})).json()
    manager = await invite_and_join(owner, role="manager", scope_department_id=kitchen["id"])
    _, cook = await add_staff(owner, name="Cook", scope_department_id=kitchen["id"])
    _, seller = await add_staff(owner, name="Seller", scope_department_id=sales["id"])
    sunday = sunday_in_march()
    cook_request = (await ask(cook, "Casual leave", sunday)).json()
    seller_request = (await ask(seller, "Casual leave", sunday)).json()

    queue = (await manager.get("/v1/leave/requests", params={"status": "pending"})).json()
    assert [r["employee_name"] for r in queue] == ["Cook"]
    outside = await manager.post(f"/v1/leave/requests/{seller_request['id']}/approve", json={})
    assert outside.status_code == 404
    assert (
        await manager.post(f"/v1/leave/requests/{cook_request['id']}/approve", json={})
    ).status_code == 200
    team = (await manager.get("/v1/leave/balances/team", params={"year": NEXT})).json()
    # The manager's own profile sits in the kitchen too.
    assert [p["employee_name"] for p in team] == ["Cook", "Member Person"]
    seller_id = await employee_id(seller)
    assert (await manager.get("/v1/leave/balances", params={"employee_id": seller_id})).status_code == 404

    # Asking on someone's behalf needs leave.manage (the owner has it; managers don't).
    for_seller = await ask(owner, "Sick leave", sunday + timedelta(days=7), employee_id=seller_id)
    assert for_seller.status_code == 201, for_seller.text
    assert for_seller.json()["employee_name"] == "Seller"
    cook_id = await employee_id(cook)
    assert (
        await ask(manager, "Sick leave", sunday + timedelta(days=7), employee_id=cook_id)
    ).status_code == 404


async def test_staff_only_see_their_own(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner)
    _, other = await add_staff(owner, name="Other")
    sunday = sunday_in_march()
    await ask(other, "Casual leave", sunday)
    await ask(staff, "Casual leave", sunday + timedelta(days=1))
    mine = (await staff.get("/v1/leave/requests")).json()
    assert [r["employee_name"] for r in mine] == ["Karim"]
    other_id = await employee_id(other)
    assert (await staff.get("/v1/leave/requests", params={"employee_id": other_id})).status_code == 404
    assert (await staff.get("/v1/leave/balances", params={"employee_id": other_id})).status_code == 404
    assert (await staff.get("/v1/leave/balances/team")).status_code == 403
    assert (await staff.get("/v1/leave/adjustments", params={"employee_id": other_id})).status_code == 404
    body = {"employee_id": other_id, "leave_type_id": (await types(staff))["Casual leave"]["id"]}
    assert (
        await staff.post("/v1/leave/adjustments", json={**body, "year": NEXT, "days": 5, "reason": "Me"})
    ).status_code == 403
    assert (
        await ask(staff, "Casual leave", sunday + timedelta(days=7), employee_id=other_id)
    ).status_code == 404


async def test_team_calendar_shows_who_is_away_not_why(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner)
    _, colleague = await add_staff(owner, name="Colleague")
    sunday = sunday_in_march()
    approved = (await ask(colleague, "Sick leave", sunday, sunday + timedelta(days=1))).json()
    await owner.post(f"/v1/leave/requests/{approved['id']}/approve", json={})
    await ask(colleague, "Casual leave", sunday + timedelta(days=7))
    await ask(staff, "Casual leave", sunday + timedelta(days=8))
    window = {"from": str(sunday), "to": str(sunday + timedelta(days=30))}

    seen = (await staff.get("/v1/leave/calendar", params=window)).json()
    assert [(e["employee_name"], e["leave_type_name"], e["status"]) for e in seen] == [
        ("Colleague", None, "approved"),
        ("Karim", "Casual leave", "pending"),
    ]
    full = (await owner.get("/v1/leave/calendar", params=window)).json()
    assert [(e["employee_name"], e["leave_type_name"]) for e in full] == [
        ("Colleague", "Sick leave"),
        ("Colleague", "Casual leave"),
        ("Karim", "Casual leave"),
    ]
    await owner.put("/v1/leave/policy", json={"weekly_off": [5], "team_calendar": False})
    alone = (await staff.get("/v1/leave/calendar", params=window)).json()
    assert [e["employee_name"] for e in alone] == ["Karim"]
    too_long = {"from": str(sunday), "to": str(sunday + timedelta(days=100))}
    assert (await staff.get("/v1/leave/calendar", params=too_long)).status_code == 422


# ---- Settings ----------------------------------------------------------------------------


async def test_leave_types_are_managed_by_admins(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner)
    body = {"name": "Study leave", "days_per_year": 5, "color": "#0f766e"}
    assert (await staff.post("/v1/leave/types", json=body)).status_code == 403
    created = await owner.post("/v1/leave/types", json=body)
    assert created.status_code == 201, created.text
    assert (await owner.post("/v1/leave/types", json={**body, "name": "study LEAVE"})).json()[
        "code"
    ] == "name_taken"
    assert (await owner.post("/v1/leave/types", json={**body, "color": "blue"})).status_code == 422
    study = created.json()
    url = f"/v1/leave/types/{study['id']}"
    assert (await owner.patch(url, json={"active": False})).status_code == 428
    stale = await owner.patch(url, json={"active": False}, headers=if_match(study["version"] + 5))
    assert stale.status_code == 412
    off = await owner.patch(url, json={"active": False}, headers=if_match(study["version"]))
    assert off.status_code == 200
    assert "Study leave" not in await types(staff)
    everything = (await owner.get("/v1/leave/types", params={"include_inactive": True})).json()
    assert "Study leave" in [t["name"] for t in everything]
    response = await owner.post(
        "/v1/leave/requests",
        json={
            "leave_type_id": study["id"],
            "start_date": str(sunday_in_march()),
            "end_date": str(sunday_in_march()),
        },
    )
    assert response.status_code == 422
    unlimited = await owner.patch(url, json={"unlimited": True}, headers=if_match(off.json()["version"]))
    assert unlimited.json()["days_per_year"] is None
    audit = (await owner.get("/v1/audit", params={"action": "leave.type_changed"})).json()["items"]
    assert len(audit) == 2


async def test_holidays_and_work_week(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner)
    day = {"day": f"{NEXT}-12-16", "name": "Victory Day"}
    assert (await staff.post("/v1/leave/holidays", json=day)).status_code == 403
    created = await owner.post("/v1/leave/holidays", json=day)
    assert created.status_code == 201
    assert (await owner.post("/v1/leave/holidays", json=day)).json()["code"] == "holiday_exists"
    unknown = {**day, "branch_id": "01900000-0000-7000-8000-000000000000"}
    assert (await owner.post("/v1/leave/holidays", json=unknown)).status_code == 422
    listed = (await staff.get("/v1/leave/holidays", params={"year": NEXT})).json()
    assert [h["name"] for h in listed] == ["Victory Day"]
    assert (await owner.delete(f"/v1/leave/holidays/{created.json()['id']}")).status_code == 204
    assert (await owner.delete(f"/v1/leave/holidays/{created.json()['id']}")).status_code == 404

    assert (await staff.put("/v1/leave/policy", json={"weekly_off": [5, 6]})).status_code == 403
    week = await owner.put("/v1/leave/policy", json={"weekly_off": [6, 5, 5], "team_calendar": True})
    assert week.json()["weekly_off"] == [5, 6]
    assert (await owner.put("/v1/leave/policy", json={"weekly_off": [0]})).status_code == 422
    assert (
        await owner.put("/v1/leave/policy", json={"weekly_off": [1, 2, 3, 4, 5, 6, 7]})
    ).status_code == 422
