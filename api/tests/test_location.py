"""Location-based attendance: branch areas, clock-in rules per mode, and what gets stored."""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from app.modules.attendance import geo
from tests.helpers import Account, add_staff, if_match, signup

# A tea stall near Shahbag, Dhaka. 0.001° of latitude is about 111 m.
SHOP = (23.738300, 90.395800)


def at(north_m: float, accuracy_m: float = 10, origin: tuple[float, float] = SHOP) -> dict[str, float]:
    return {"latitude": origin[0] + north_m / 111_195, "longitude": origin[1], "accuracy_m": accuracy_m}


async def first_branch(owner: Account) -> dict[str, Any]:
    branches: list[dict[str, Any]] = (await owner.get("/v1/branches")).json()
    return branches[0]


async def place_branch(
    owner: Account, radius: int = 150, where: tuple[float, float] = SHOP
) -> dict[str, Any]:
    branch = await first_branch(owner)
    response = await owner.patch(
        f"/v1/branches/{branch['id']}",
        json={"latitude": where[0], "longitude": where[1], "geofence_m": radius},
        headers=if_match(branch["version"]),
    )
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


async def set_mode(owner: Account, mode: str, max_accuracy_m: int = 100) -> None:
    response = await owner.put(
        "/v1/attendance/settings", json={"location_mode": mode, "max_accuracy_m": max_accuracy_m}
    )
    assert response.status_code == 200, response.text


# ---- The geometry ------------------------------------------------------------------------


def test_distance_is_accurate() -> None:
    north = geo.distance_m(SHOP[0], SHOP[1], SHOP[0] + 0.001, SHOP[1])
    assert 110 < north < 112
    assert geo.distance_m(*SHOP, *SHOP) == 0


def test_check_prefers_the_persons_branch_and_reports_the_nearest() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    sites = [geo.Site(a, SHOP[0], SHOP[1], 150), geo.Site(b, SHOP[0] + 0.0005, SHOP[1], 150)]
    here = geo.Point(SHOP[0] + 0.00025, SHOP[1], 5)
    assert geo.check(here, sites, max_accuracy_m=100, prefer=b).branch_id == b
    assert geo.check(here, sites, max_accuracy_m=100, prefer=a).branch_id == a
    far = geo.check(geo.Point(SHOP[0] + 0.01, SHOP[1], 5), sites, max_accuracy_m=100)
    assert far.result == "outside"
    assert far.branch_id == b
    assert far.distance_m is not None
    assert 1000 < far.distance_m < 1100
    assert geo.check(None, sites, max_accuracy_m=100).result == "no_fix"
    assert geo.check(here, [], max_accuracy_m=100).result == "no_site"


def test_accuracy_slack_is_capped() -> None:
    site = [geo.Site(uuid.uuid4(), SHOP[0], SHOP[1], 150)]

    def result(north_m: float, accuracy_m: float) -> str:
        return geo.check(
            geo.Point(SHOP[0] + north_m / 111_195, SHOP[1], accuracy_m), site, max_accuracy_m=100
        ).result

    # 180 m away with ±50 m: could be inside.
    assert result(180, 50) == "inside"
    # 400 m away with a vague ±5 km fix: the slack is capped at 100 m, so outside.
    assert result(400, 5000) == "outside"


# ---- Branch locations --------------------------------------------------------------------


async def test_branch_location_is_saved_validated_and_cleared(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    placed = await place_branch(owner, radius=200)
    assert placed["latitude"] == SHOP[0]
    assert placed["longitude"] == SHOP[1]
    assert placed["geofence_m"] == 200
    half = await owner.patch(
        f"/v1/branches/{placed['id']}", json={"latitude": 23.7}, headers=if_match(placed["version"])
    )
    assert half.status_code == 422
    for bad in ({"latitude": 91, "longitude": 0}, {"geofence_m": 10}, {"geofence_m": 6000}):
        url = f"/v1/branches/{placed['id']}"
        response = await owner.patch(url, json=bad, headers=if_match(placed["version"]))
        assert response.status_code == 422, bad
    cleared = await owner.patch(
        f"/v1/branches/{placed['id']}", json={"clear_location": True}, headers=if_match(placed["version"])
    )
    assert cleared.status_code == 200
    assert cleared.json()["latitude"] is None
    created = await owner.post(
        "/v1/branches", json={"name": "Station Road", "latitude": 23.72, "longitude": 90.41, "geofence_m": 80}
    )
    assert created.status_code == 201
    assert created.json()["geofence_m"] == 80
    assert (await owner.post("/v1/branches", json={"name": "Half", "longitude": 90.4})).status_code == 422


# ---- Clocking in -------------------------------------------------------------------------


async def test_required_location_blocks_clock_in_away_from_work(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    status = (await owner.get("/v1/attendance/status")).json()
    assert status["location_mode"] == "require"
    await place_branch(owner)
    _, staff = await add_staff(owner)

    missing = await staff.post("/v1/attendance/clock-in", json={})
    assert missing.status_code == 422
    assert missing.json()["code"] == "location_required"

    far = await staff.post("/v1/attendance/clock-in", json={"location": at(2000)})
    assert far.status_code == 403
    body = far.json()
    assert body["code"] == "outside_area"
    assert 1900 < body["distance_m"] < 2100
    assert body["branch_name"] == "Main branch"

    vague = await staff.post("/v1/attendance/clock-in", json={"location": at(400, accuracy_m=800)})
    assert vague.status_code == 422
    assert vague.json()["code"] == "location_imprecise"

    ok = await staff.post("/v1/attendance/clock-in", json={"location": at(60, accuracy_m=12.7)})
    assert ok.status_code == 201, ok.text
    record = ok.json()
    assert record["in_geo"] == "inside"
    assert 55 <= record["in_distance_m"] <= 65
    assert record["in_accuracy_m"] == 13
    # Stored rounded to 4 decimals (about 11 m).
    assert record["in_latitude"] == round(at(60)["latitude"], 4)

    # Leaving from somewhere else is allowed, but flagged.
    out = await staff.post("/v1/attendance/clock-out", json={"location": at(900)})
    assert out.status_code == 200
    assert out.json()["out_geo"] == "outside"
    assert out.json()["out_distance_m"] > 800


async def test_clock_out_without_location_is_flagged_not_blocked(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    await place_branch(owner)
    assert (await owner.post("/v1/attendance/clock-in", json={"location": at(0)})).status_code == 201
    out = await owner.post("/v1/attendance/clock-out", json={})
    assert out.status_code == 200
    assert out.json()["out_geo"] == "no_fix"


async def test_record_mode_saves_but_never_blocks(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    await place_branch(owner)
    await set_mode(owner, "record")
    far = await owner.post("/v1/attendance/clock-in", json={"location": at(3000)})
    assert far.status_code == 201
    assert far.json()["in_geo"] == "outside"
    await owner.post("/v1/attendance/clock-out", json={})
    _, staff = await add_staff(owner)
    blind = await staff.post("/v1/attendance/clock-in", json={})
    assert blind.status_code == 201
    assert blind.json()["in_geo"] == "no_fix"


async def test_off_mode_stores_nothing(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    await place_branch(owner)
    await set_mode(owner, "off")
    record = (await owner.post("/v1/attendance/clock-in", json={"location": at(5000)})).json()
    assert record["in_geo"] is None
    assert record["in_latitude"] is None


async def test_unplaced_branches_do_not_block_anyone(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    settings = (await owner.get("/v1/attendance/settings")).json()
    assert settings == {
        "location_mode": "require",
        "max_accuracy_m": 100,
        "branches_total": 1,
        "branches_located": 0,
    }
    record = (await owner.post("/v1/attendance/clock-in", json={"location": at(5000)})).json()
    assert record["in_geo"] == "no_site"


async def test_clock_in_picks_the_branch_the_person_is_at(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    main = await place_branch(owner)
    far_away = {"name": "Station Road", "latitude": SHOP[0] + 0.02, "longitude": SHOP[1], "geofence_m": 100}
    station = (await owner.post("/v1/branches", json=far_away)).json()
    record = (await owner.post("/v1/attendance/clock-in", json={"location": at(2224)})).json()
    assert record["branch_id"] == station["id"]
    assert record["in_geo"] == "inside"
    await owner.post("/v1/attendance/clock-out", json={"location": at(2224)})
    # Choosing a branch means being at that branch.
    wrong = await owner.post("/v1/attendance/clock-in", json={"branch_id": main["id"], "location": at(2224)})
    assert wrong.status_code == 403
    assert wrong.json()["branch_name"] == "Main branch"


async def test_only_admins_change_location_settings(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner)
    assert (await staff.get("/v1/attendance/settings")).status_code == 200
    denied = await staff.put("/v1/attendance/settings", json={"location_mode": "off"})
    assert denied.status_code == 403
    assert (await owner.put("/v1/attendance/settings", json={"location_mode": "loud"})).status_code == 422
    await set_mode(owner, "record", 50)
    assert (await owner.get("/v1/attendance/settings")).json()["max_accuracy_m"] == 50
    audit = (await owner.get("/v1/audit", params={"action": "attendance.settings_changed"})).json()
    assert audit["items"][0]["data"]["after"]["location_mode"] == "record"
