"""A 30-person agency runs a week of work in the product, through the real API.

Nokshi Digital, a Dhaka agency: an owner, an admin, three department managers and their
teams. Over one working week (Sunday to Thursday) they clock in and out, plan client work
on boards and get it done, read the owner's announcement, acknowledge the code of
conduct, ask for leave and a time fix that their managers approve from the approvals
inbox, and welcome a new joiner whose onboarding checklist starts by itself.

    cd api && uv run python -m scripts.agency_week --api http://localhost:8000

`--leave-for-browser` stops just short of the end, so a browser test can finish the week:
one person still has to read the announcement and acknowledge the policy, and one leave
request is still waiting in a manager's inbox. `--json` prints the sign-in details as
JSON. The test suite plays the same week (tests/test_agency_week.py). Never run against
production.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import secrets
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

PASSWORD = "mango season on the rooftop 30"
DHAKA = ZoneInfo("Asia/Dhaka")
WEEKEND = {4, 5}  # Friday and Saturday
POLICY = b"%PDF-1.7\n% Nokshi Digital code of conduct\n"
HANDBOOK = b"%PDF-1.7\n% Nokshi Digital handbook\n"

OWNER = "Farzana Haque"
ADMIN = ("Shirin Akter", "shirin", "Operations")
MANAGERS = {
    "Client service": ("Tanvir Ahmed", "tanvir"),
    "Design": ("Nusrat Jahan", "nusrat"),
    "Tech": ("Arif Hossain", "arif"),
}
STAFF = {
    "Client service": [
        ("Mahmud Hasan", "mahmud"),
        ("Sadia Rahman", "sadia"),
        ("Imran Kabir", "imran"),
        ("Tasnim Ferdous", "tasnim"),
        ("Rakib Hasan", "rakib"),
        ("Jannatul Ferdous", "jannat"),
    ],
    "Design": [
        ("সুমাইয়া ইসলাম", "sumaiya"),
        ("Fahim Shahriar", "fahim"),
        ("Nabila Chowdhury", "nabila"),
        ("Zubair Alam", "zubair"),
        ("Lamia Haque", "lamia"),
        ("Ridwan Karim", "ridwan"),
        ("Afsana Mimi", "afsana"),
        ("Sabbir Rahman", "sabbir"),
    ],
    "Tech": [
        ("Shakil Ahmed", "shakil"),
        ("Rafsan Jani", "rafsan"),
        ("Moumita Das", "moumita"),
        ("Asif Iqbal", "asif"),
        ("Priyanka Saha", "priyanka"),
        ("Tanjim Hossain", "tanjim"),
        ("Ehsan Ul Haque", "ehsan"),
    ],
    "Operations": [
        ("Kamal Uddin", "kamal"),
        ("Rokeya Begum", "rokeya"),
        ("Habib Mia", "habib"),
    ],
}
JOINER = ("Mitu Chowdhury", "mitu", "Design")
# Who is left for the browser test to finish with, and whose leave is still waiting.
LAST_READER = "sumaiya"
WAITING_LEAVE = "fahim"

PROJECTS = [
    (
        "Tech",
        "Meghna Bank website refresh",
        "#0f766e",
        [
            ("Audit the current site", "shakil", "done"),
            ("Wireframes for the home page", "rafsan", "done"),
            ("Build the rates calculator", "moumita", "doing"),
            ("Set up staging", "asif", "done"),
            ("Accessibility pass", "priyanka", "todo"),
            ("Load test before launch", "tanjim", "todo"),
        ],
    ),
    (
        "Design",
        "Shapla Tea Eid campaign",
        "#b4235a",
        [
            ("Moodboard", "sumaiya", "done"),
            ("Key visual, three routes", "fahim", "done"),
            ("Facebook carousel", "nabila", "doing"),
            ("Billboard adaptation", "zubair", "doing"),
            ("Bangla copy for the TVC", "lamia", "done"),
            ("Print-ready files", "ridwan", "todo"),
        ],
    ),
    (
        "Client service",
        "Padma Foods social calendar",
        "#b45309",
        [
            ("Kick-off with the client", "mahmud", "done"),
            ("October content plan", "sadia", "done"),
            ("Approve the first ten posts", "imran", "doing"),
            ("Monthly report", "tasnim", "todo"),
            ("Boost budget sign-off", "rakib", "done"),
        ],
    ),
]


@dataclass
class Person:
    name: str
    username: str
    department: str
    client: httpx.AsyncClient
    token: str = ""
    employee_id: str = ""

    async def call(self, method: str, url: str, **kw: Any) -> Any:
        headers = {"authorization": f"Bearer {self.token}", **kw.pop("headers", {})}
        response = await self.client.request(method, url, headers=headers, **kw)
        if response.status_code >= 400:
            raise RuntimeError(f"{self.username}: {method} {url} -> {response.status_code} {response.text}")
        return response.json() if response.content else None

    async def get(self, url: str, **kw: Any) -> Any:
        return await self.call("GET", url, **kw)

    async def post(self, url: str, **kw: Any) -> Any:
        return await self.call("POST", url, **kw)


@dataclass
class Week:
    owner_email: str
    password: str
    workspace_code: str
    days: list[date]
    people: dict[str, Person] = field(default_factory=dict)
    documents: dict[str, str] = field(default_factory=dict)
    announcement_id: str = ""
    waiting_leave_id: str = ""

    def summary(self) -> dict[str, Any]:
        return {
            "owner": {"email": self.owner_email, "password": self.password, "name": OWNER},
            "workspace_code": self.workspace_code,
            "password": self.password,
            "people": {p.username: p.name for p in self.people.values() if p.username != "owner"},
            "last_reader": LAST_READER,
            "waiting_leave": WAITING_LEAVE,
            "waiting_manager": MANAGERS["Design"][1],
            "documents": self.documents,
        }


def working_days(today: date) -> list[date]:
    """This week's working days, Sunday to Thursday, up to today."""
    start = today - timedelta(days=(today.weekday() + 1) % 7)  # back to Sunday
    days = [start + timedelta(days=i) for i in range(5)]
    days = [d for d in days if d <= today]
    if not days:  # Friday or Saturday: last week
        days = [start - timedelta(days=7) + timedelta(days=i) for i in range(5)]
    return days


def at(day: date, hour: int, minute: int = 0) -> str:
    return datetime.combine(day, time(hour, minute), DHAKA).astimezone(UTC).isoformat()


def planned_leave(today: date, offset: int) -> date:
    """A working day early next March, so planned leave never trips over the year's end."""
    day = date(today.year + 1, 3, 1)
    while day.weekday() != 6:
        day += timedelta(days=1)
    day += timedelta(days=offset)
    while day.weekday() in WEEKEND:
        day += timedelta(days=1)
    return day


async def sign_in(client: httpx.AsyncClient, code: str, person: Person, temporary: str) -> None:
    response = await client.post(
        "/v1/auth/login", json={"workspace": code, "username": person.username, "password": temporary}
    )
    if response.status_code != 200:
        raise RuntimeError(f"{person.username}: sign-in -> {response.status_code} {response.text}")
    person.token = response.json()["access_token"]
    await person.post(
        "/v1/auth/password/change", json={"current_password": temporary, "new_password": PASSWORD}
    )
    me = await person.get("/v1/leave/balances")
    person.employee_id = str(me["employee_id"])


async def play_week(
    client: httpx.AsyncClient, *, leave_for_browser: bool = False, email: str | None = None
) -> Week:
    rng = random.Random(30)
    today = datetime.now(DHAKA).date()
    owner_email = email or f"farzana-{secrets.token_hex(3)}@nokshi.example"
    response = await client.post(
        "/v1/auth/signup",
        json={
            "name": OWNER,
            "email": owner_email,
            "password": PASSWORD,
            "business_name": "Nokshi Digital",
            "business_type": "office",
            "country": "BD",
            "timezone": "Asia/Dhaka",
            "locale": "en",
        },
    )
    if response.status_code != 201:
        raise RuntimeError(f"signup -> {response.status_code} {response.text}")
    owner = Person(OWNER, "owner", "", client, response.json()["access_token"])
    owner.employee_id = str((await owner.get("/v1/leave/balances"))["employee_id"])

    departments = {
        name: (await owner.post("/v1/departments", json={"name": name}))["id"]
        for name in ("Client service", "Design", "Tech", "Operations")
    }
    roles = {r["key"]: r["id"] for r in await owner.get("/v1/roles")}

    week = Week(owner_email, PASSWORD, "", working_days(today))
    week.people["owner"] = owner

    async def add(name: str, username: str, department: str, role: str) -> Person:
        # Admins see the whole workspace; everyone else belongs to (and managers run) a department.
        scope = None if role == "admin" else departments[department]
        added = await owner.post(
            "/v1/members/staff",
            json={"name": name, "username": username, "role_id": roles[role], "scope_department_id": scope},
        )
        week.workspace_code = added["workspace_code"]
        person = Person(name, username, department, client)
        await sign_in(client, week.workspace_code, person, added["temporary_password"])
        if scope is None:
            profile = await owner.get(f"/v1/people/{person.employee_id}")
            await owner.call(
                "PATCH",
                f"/v1/people/{person.employee_id}",
                json={"department_id": departments[department]},
                headers={"if-match": f'W/"{profile["version"]}"'},
            )
        week.people[username] = person
        return person

    admin = await add(*ADMIN, role="admin")
    managers = {dept: await add(name, user, dept, "manager") for dept, (name, user) in MANAGERS.items()}
    for dept, staff in STAFF.items():
        for name, user in staff:
            await add(name, user, dept, "employee")
    people = week.people

    # Sunday morning: the owner's note for the week, and the policies.
    note = await owner.post(
        "/v1/announcements",
        json={
            "title": "This week: Shapla Eid campaign and the Meghna launch",
            "body": "Two big deliveries this week. Ask your manager if you need help, and "
            "please read the updated code of conduct by Thursday.",
            "pinned": True,
        },
    )
    week.announcement_id = note["id"]
    for key, title, category, ack, data in (
        ("policy", "Code of conduct", "policy", True, POLICY),
        ("handbook", "Employee handbook", "handbook", False, HANDBOOK),
    ):
        doc = await admin.post(
            "/v1/documents", json={"title": title, "category": category, "requires_ack": ack}
        )
        await admin.post(
            f"/v1/documents/{doc['id']}/versions",
            params={"filename": f"{title.lower().replace(' ', '-')}.pdf"},
            content=data,
            headers={"content-type": "application/pdf"},
        )
        week.documents[key] = doc["id"]

    # The joiner's checklist starts by itself when they join on Wednesday.
    await admin.post(
        "/v1/onboarding/templates",
        json={
            "name": "First week at Nokshi",
            "automatic": True,
            "items": [
                {
                    "title": "Read the code of conduct",
                    "who": "joiner",
                    "due_days": 0,
                    "document_id": week.documents["policy"],
                },
                {"title": "Set up email, Figma and Slack", "who": "manager", "due_days": 0},
                {"title": "Lunch with the team", "who": "joiner", "due_days": 2},
            ],
        },
    )

    # Client work, planned by each department's manager.
    for dept, name, color, tasks in PROJECTS:
        manager = managers[dept]
        members = [p.employee_id for p in people.values() if p.department == dept]
        project = await manager.post(
            "/v1/projects",
            json={
                "name": name,
                "department_id": departments[dept],
                "member_ids": members,
                "color": color,
                "due_date": str(week.days[-1] + timedelta(days=7)),
            },
        )
        for i, (title, username, status) in enumerate(tasks):
            person = people[username]
            task = await manager.post(
                "/v1/tasks",
                json={
                    "title": title,
                    "project_id": project["id"],
                    "assignee_id": person.employee_id,
                    "due_date": str(week.days[min(i, len(week.days) - 1)]),
                    "priority": "high" if i == 0 else "normal",
                    "checklist": ["Brief", "Draft", "Review"] if i % 2 == 0 else [],
                },
            )
            if status != "todo":
                await person.post(f"/v1/tasks/{task['id']}/move", json={"status": "doing"})
                await person.post(f"/v1/tasks/{task['id']}/comments", json={"body": "On it."})
            if status == "done":
                for item in task["checklist"]:
                    await person.call(
                        "PATCH", f"/v1/tasks/{task['id']}/checklist/{item['id']}", json={"done": True}
                    )
                await person.post(f"/v1/tasks/{task['id']}/move", json={"status": "done"})

    # The week's attendance: most people in around nine; one phone dies on Monday.
    forgot = people["imran"]
    for day in week.days:
        for person in people.values():
            if person is forgot and day == week.days[min(1, len(week.days) - 1)]:
                continue
            if rng.random() < 0.04:
                continue
            start = at(day, rng.choice([8, 9, 9, 10]), rng.randint(0, 40))
            end = None if day == today else at(day, rng.choice([17, 18, 18, 19]), rng.randint(0, 50))
            body: dict[str, Any] = {"employee_id": person.employee_id, "clock_in_at": start}
            if end:
                body["clock_out_at"] = end
            elif datetime.fromisoformat(start) > datetime.now(UTC):
                continue
            await owner.post("/v1/attendance/records", json=body)

    # Leave and a time fix, decided by managers from the approvals inbox.
    kinds = {k["name"]: k["id"] for k in await owner.get("/v1/leave/types")}
    asks = [
        ("mahmud", "Casual leave", 0, "Sister's wedding"),
        ("shakil", "Casual leave", 1, "Family trip to Sylhet"),
        ("kamal", "Casual leave", 2, "Bank work"),
        (WAITING_LEAVE, "Casual leave", 3, "Doctor's appointment"),
    ]
    for username, kind, offset, reason in asks:
        day = planned_leave(today, offset)
        request = await people[username].post(
            "/v1/leave/requests",
            json={
                "leave_type_id": kinds[kind],
                "start_date": str(day),
                "end_date": str(day),
                "reason": reason,
            },
        )
        if username == WAITING_LEAVE:
            week.waiting_leave_id = request["id"]
    fix_day = week.days[min(1, len(week.days) - 1)]
    if fix_day < today:
        await forgot.post(
            "/v1/attendance/corrections",
            json={
                "kind": "add",
                "clock_in_at": at(fix_day, 9, 5),
                "clock_out_at": at(fix_day, 18, 0),
                "reason": "My phone died, so I couldn't clock in.",
            },
        )
    deciders = [managers["Client service"], managers["Tech"], admin, managers["Design"]]
    for decider in deciders:
        for item in (await decider.get("/v1/approvals"))["items"]:
            if leave_for_browser and item["id"] == week.waiting_leave_id:
                continue
            await decider.post(
                f"/v1/approvals/{item['kind']}/{item['id']}/approve", json={"note": "Approved."}
            )

    # Wednesday: a new designer joins.
    await add(*JOINER, role="employee")

    # By Thursday everyone has read the note and acknowledged the policy.
    for person in people.values():
        if leave_for_browser and person.username == LAST_READER:
            continue
        await person.post(f"/v1/announcements/{week.announcement_id}/read")
        await person.post(f"/v1/documents/{week.documents['policy']}/acknowledge")
    return week


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--email", default=None)
    parser.add_argument("--leave-for-browser", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    async with httpx.AsyncClient(base_url=args.api, timeout=60) as client:
        week = await play_week(client, leave_for_browser=args.leave_for_browser, email=args.email)
    summary = week.summary()
    if args.json:
        print(json.dumps(summary))
        return
    print(f"Owner: {week.owner_email} / {PASSWORD}")
    print(f"Everyone else: workspace {week.workspace_code}, their username (e.g. nusrat) / {PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
