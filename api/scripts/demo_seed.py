"""Fills a demo workspace through the real API: people, departments, two weeks of
attendance, a pending correction. For screenshots, demo videos and trying the app.

    cd api && uv run python -m scripts.demo_seed --api http://localhost:8000

Prints the sign-in details at the end. Never run against production.
"""

from __future__ import annotations

import argparse
import random
import secrets
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

PASSWORD = "morning cha and biscuits 26"
DHAKA = ZoneInfo("Asia/Dhaka")

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

    c.post("/v1/branches", json={"name": "Gulshan kiosk", "timezone": "Asia/Dhaka"}, headers=h)

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
    c.post("/v1/attendance/clock-in", json={}, headers=sh)

    # A few people are at work right now.
    for person in people[:4]:
        start = datetime.now(UTC) - timedelta(hours=rng.randint(1, 5), minutes=rng.randint(0, 50))
        c.post(
            "/v1/attendance/records",
            json={"employee_id": person["id"], "clock_in_at": start.isoformat()},
            headers=h,
        )

    print(f"Owner: {args.email} / {PASSWORD}")
    print(f"Staff: workspace {workspace_code}, username nadia / {PASSWORD}!")


if __name__ == "__main__":
    main()
