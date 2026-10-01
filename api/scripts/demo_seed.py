"""Fills a demo workspace through the real API: people, departments, two weeks of
attendance, a pending correction, and leave (holidays, approved and waiting requests).
For screenshots, demo videos and trying the app.

    cd api && uv run python -m scripts.demo_seed --api http://localhost:8000

Prints the sign-in details at the end. Never run against production.
"""

from __future__ import annotations

import argparse
import random
import secrets
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

PASSWORD = "morning cha and biscuits 26"
DHAKA = ZoneInfo("Asia/Dhaka")

# Near Shahbag, Dhaka.
SHOP = (23.7383, 90.3958)

DEPARTMENTS = {"Kitchen": ["Tea counter", "Snacks"], "Front of house": [], "Delivery": []}
PEOPLE = [
    ("Karim Mia", "Tea counter", "Tea maker"),
    ("Salma Begum", "Snacks", "Cook"),
    ("মোঃ আব্দুল করিম", "Tea counter", "Helper"),
    ("Nusrat Jahan", "Front of house", "Cashier"),
    ("Jamal Hossain", "Delivery", "Rider"),
    ("Farhana Akter", "Front of house", "Server"),
    ("Rafiq Islam", "Snacks", "Cook"),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--email", default=f"demo-{secrets.token_hex(3)}@example.com")
    args = parser.parse_args()
    rng = random.Random(7)
    c = httpx.Client(base_url=args.api, timeout=30)

    r = c.post(
        "/v1/auth/signup",
        json={
            "name": "Rahim Uddin",
            "email": args.email,
            "password": PASSWORD,
            "business_name": "Rahim Tea House",
            "business_type": "restaurant",
            "country": "BD",
            "timezone": "Asia/Dhaka",
            "locale": "en",
        },
    )
    r.raise_for_status()
    h = {"authorization": f"Bearer {r.json()['access_token']}"}

    dept_ids: dict[str, str] = {}
    for parent, children in DEPARTMENTS.items():
        d = c.post("/v1/departments", json={"name": parent}, headers=h).json()
        dept_ids[parent] = d["id"]
        for child in children:
            dept_ids[child] = c.post(
                "/v1/departments", json={"name": child, "parent_id": d["id"]}, headers=h
            ).json()["id"]

    # Branch locations, so clock-ins are checked against a 150 m area around each.
    main = c.get("/v1/branches", headers=h).json()[0]
    c.patch(
        f"/v1/branches/{main['id']}",
        json={"latitude": SHOP[0], "longitude": SHOP[1], "geofence_m": 150},
        headers={**h, "if-match": f'W/"{main["version"]}"'},
    ).raise_for_status()
    c.post(
        "/v1/branches",
        json={"name": "Gulshan kiosk", "timezone": "Asia/Dhaka", "latitude": 23.7925, "longitude": 90.4078},
        headers=h,
    ).raise_for_status()

    roles = {r["key"]: r["id"] for r in c.get("/v1/roles", headers=h).json()}
    people: list[dict[str, str]] = []
    for i, (name, dept, title) in enumerate(PEOPLE):
        p = c.post(
            "/v1/people",
            json={
                "full_name": name,
                "department_id": dept_ids[dept],
                "job_title": title,
                "employee_code": f"E-{i + 1:03d}",
                "phone": f"+880 17{rng.randint(10, 99)}-{rng.randint(100000, 999999)}",
                "joined_on": f"2025-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            },
            headers=h,
        )
        p.raise_for_status()
        people.append(p.json())

    # Two weeks of shifts: mostly 8-9 hours, the odd late start, one night shift.
    today = datetime.now(DHAKA).date()
    for back in range(14, 0, -1):
        day = today - timedelta(days=back)
        if day.weekday() == 4:  # Friday off
            continue
        for person in people:
            if rng.random() < 0.08:
                continue
            night = person["job_title"] == "Rider" and back % 5 == 0
            start_hour = 21 if night else rng.choice([7, 8, 8, 9])
            start = datetime(day.year, day.month, day.day, start_hour, rng.randint(0, 25), tzinfo=DHAKA)
            end = start + timedelta(hours=rng.choice([8, 8, 9]), minutes=rng.randint(0, 40))
            c.post(
                "/v1/attendance/records",
                json={
                    "employee_id": person["id"],
                    "clock_in_at": start.astimezone(UTC).isoformat(),
                    "clock_out_at": end.astimezone(UTC).isoformat(),
                },
                headers=h,
            ).raise_for_status()

    # A staff member who clocks in today and asks for a fix.
    staff = c.post(
        "/v1/members/staff",
        json={"name": "Nadia Rahman", "username": "nadia", "password": PASSWORD, "role_id": roles["cashier"]},
        headers=h,
    ).json()
    workspace_code = staff["workspace_code"]
    s = c.post(
        "/v1/auth/login", json={"workspace": workspace_code, "username": "nadia", "password": PASSWORD}
    )
    sh = {"authorization": f"Bearer {s.json()['access_token']}"}
    c.post(
        "/v1/auth/password/change",
        json={"current_password": PASSWORD, "new_password": PASSWORD + "!"},
        headers=sh,
    )
    yesterday = datetime(today.year, today.month, today.day, 9, 0, tzinfo=DHAKA) - timedelta(days=1)
    c.post(
        "/v1/attendance/corrections",
        json={
            "kind": "add",
            "clock_in_at": yesterday.astimezone(UTC).isoformat(),
            "clock_out_at": (yesterday + timedelta(hours=8)).astimezone(UTC).isoformat(),
            "reason": "My phone battery died, so I couldn't clock in.",
        },
        headers=sh,
    )
    at_shop = {"latitude": SHOP[0] + 0.0003, "longitude": SHOP[1], "accuracy_m": 12}
    c.post("/v1/attendance/clock-in", json={"location": at_shop}, headers=sh).raise_for_status()

    # A few people are at work right now.
    for person in people[:4]:
        start = datetime.now(UTC) - timedelta(hours=rng.randint(1, 5), minutes=rng.randint(0, 50))
        c.post(
            "/v1/attendance/records",
            json={"employee_id": person["id"], "clock_in_at": start.isoformat()},
            headers=h,
        )

    seed_leave(c, h, sh, people, today)

    print(f"Owner: {args.email} / {PASSWORD}")
    print(f"Staff: workspace {workspace_code}, username nadia / {PASSWORD}!")


def working_day(start: date, ahead: int) -> date:
    """`ahead` working days after `start` (Friday is the weekly day off)."""
    day = start
    while ahead > 0:
        day += timedelta(days=1)
        if day.weekday() != 4:
            ahead -= 1
    return day


def seed_leave(
    c: httpx.Client, h: dict[str, str], sh: dict[str, str], people: list[dict[str, str]], today: date
) -> None:
    c.put("/v1/workspace/modules", json={"modules": ["attendance", "leave"]}, headers=h).raise_for_status()
    kinds = {k["name"]: k["id"] for k in c.get("/v1/leave/types", headers=h).json()}
    holidays = ((f"{today.year}-12-16", "Victory Day"), (f"{today.year + 1}-02-21", "Language Martyrs' Day"))
    for day, name in holidays:
        c.post("/v1/leave/holidays", json={"day": day, "name": name}, headers=h)

    def ask(person: dict[str, str], kind: str, start: date, end: date, reason: str, approve: bool) -> None:
        if start.year != end.year:
            return
        r = c.post(
            "/v1/leave/requests",
            json={
                "employee_id": person["id"],
                "leave_type_id": kinds[kind],
                "start_date": str(start),
                "end_date": str(end),
                "reason": reason,
            },
            headers=h,
        )
        if r.status_code == 201 and approve:
            c.post(f"/v1/leave/requests/{r.json()['id']}/approve", json={}, headers=h)

    karim, salma, _, nusrat, jamal, farhana, _ = people
    ask(salma, "Sick leave", today, today, "Fever", approve=True)
    ask(jamal, "Casual leave", working_day(today, 2), working_day(today, 3), "Sister's wedding", approve=True)
    trip = "Visiting family in Sylhet"
    ask(farhana, "Earned leave", working_day(today, 8), working_day(today, 12), trip, approve=True)
    ask(karim, "Casual leave", working_day(today, 5), working_day(today, 5), "Bank work", approve=False)
    ask(nusrat, "Unpaid leave", working_day(today, 15), working_day(today, 16), "Exam", approve=False)
    c.post(
        "/v1/leave/requests",
        json={
            "leave_type_id": kinds["Casual leave"],
            "start_date": str(working_day(today, 6)),
            "end_date": str(working_day(today, 6)),
            "reason": "Doctor's appointment for my mother.",
        },
        headers=sh,
    )


if __name__ == "__main__":
    main()
