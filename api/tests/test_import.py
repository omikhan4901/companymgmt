"""Spreadsheet import: people, departments and leave balances from a CSV, previewed first."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.modules.imports import parse
from tests.helpers import Account, add_staff, invite_and_join, signup

CSV = {"content-type": "text/csv"}


async def send(
    account: Account, text: str, *, commit: bool = False, encoding: str = "utf-8"
) -> httpx.Response:
    return await account.post(
        "/v1/people/import", params={"commit": commit}, content=text.encode(encoding), headers=CSV
    )


async def preview(account: Account, text: str) -> dict[str, Any]:
    response = await send(account, text)
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


async def people(account: Account) -> dict[str, dict[str, Any]]:
    items = (await account.get("/v1/people", params={"limit": 200})).json()["items"]
    return {p["full_name"]: p for p in items}


async def days_left(account: Account, employee_id: str, kind: str) -> float:
    balances = (await account.get("/v1/leave/balances", params={"employee_id": employee_id})).json()
    return float(next(b["available"] for b in balances["balances"] if b["name"] == kind))


# ---- Reading files ----------------------------------------------------------------------


def test_headers_in_english_or_bangla_and_any_order() -> None:
    text = "ইমেইল;নাম;বিভাগ;Casual leave (days left);Favourite colour\nrina@example.com;রিনা;Design;7.5;Blue\n"
    sheet = parse.read(text.encode(), ["Casual leave", "Sick leave"])
    assert [(c.field, c.leave_type) for c in sheet.columns] == [
        ("email", None),
        ("full_name", None),
        ("department", None),
        ("leave", "Casual leave"),
        (None, None),
    ]
    [row] = sheet.rows
    assert row.line == 2
    assert row.cells == {"email": "rina@example.com", "full_name": "রিনা", "department": "Design"}
    assert row.leave == {"Casual leave": "7.5"}


def test_excel_files_with_a_bom_or_utf16_are_read() -> None:
    for data in ("﻿Name\nKarim\n".encode(), "Name\tPhone\nKarim\t017\n".encode("utf-16")):
        assert parse.read(data, []).rows[0].cells["full_name"] == "Karim"


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (b"", "empty_file"),
        (b"Email\nx@example.com\n", "no_name_column"),
        (b"Name\n\n,\n", "no_rows"),
        ("Name\nKarim\n".encode("cp1252") + b"\xe9\xff\n", "not_utf8"),
        (b"Name\n" + b"Karim\n" * (parse.MAX_ROWS + 1), "too_many_rows"),
    ],
)
def test_files_we_cant_read_say_why(data: bytes, code: str) -> None:
    with pytest.raises(parse.Problem) as problem:
        parse.read(data, [])
    assert problem.value.code == code


def test_dates_days_and_types_are_read_the_way_people_write_them() -> None:
    assert parse.parse_date("2024-01-15") == date(2024, 1, 15)
    assert parse.parse_date("15/01/2024") == date(2024, 1, 15)
    assert parse.parse_date("১৫/০১/২০২৪") == date(2024, 1, 15)
    assert parse.parse_date("15 Jan 2024") == date(2024, 1, 15)
    assert parse.parse_date("2024-01-15 00:00:00") == date(2024, 1, 15)
    assert parse.parse_date("01/15/2024") is None  # month first is not how Bangladesh writes it
    assert parse.parse_days("7.5") == Decimal("7.5")
    assert parse.parse_days("\u09ed,\u09eb")  # Bangla digits, decimal comma == Decimal("7.5")
    assert parse.parse_days("7.3") is None
    assert parse.parse_days("-1") is None
    assert parse.parse_days("NaN") is None
    assert parse.parse_employment_type("Part-time") == "part_time"
    assert parse.parse_employment_type("চুক্তিভিত্তিক") == "contract"
    assert parse.parse_employment_type("full_time") == "full_time"
    assert parse.parse_employment_type("sometimes") is None
    assert parse.department_path(" Design / Motion ") == ["Design", "Motion"]
    assert parse.department_path("Sales > Dhaka") == ["Sales", "Dhaka"]


# ---- Preview and import -------------------------------------------------------------------


async def test_preview_shows_every_problem_and_saves_nothing(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    before = await people(owner)
    text = (
        "Name,Employee code,Email,Department,Branch,Joined on,Employment type,"
        "Casual leave (days left),Notes\n"
        "Nusrat Jahan,E-1,nusrat@example.com,Design / Motion,,2024-01-15,Full time,7.5,ignored\n"
        ",E-2,,,,,,,\n"
        "Fahim,E-1,not-an-email,Design,Uttara,31/02/2024,sometimes,7.3,\n"
    )
    result = await preview(owner, text)
    assert (result["create"], result["errors"], result["committed"]) == (1, 2, False)
    assert result["new_departments"] == ["Design", "Design / Motion"]
    assert [c["field"] for c in result["columns"]][-2:] == ["leave", None]
    first, empty, broken = result["rows"]
    assert (first["action"], first["errors"]) == ("create", [])
    assert empty["errors"] == [{"column": "Name", "message": "Every person needs a name."}]
    messages = {e["column"]: e["message"] for e in broken["errors"]}
    assert set(messages) == {
        "Employee code",
        "Email",
        "Branch",
        "Joined on",
        "Employment type",
        "Casual leave (days left)",
    }
    assert messages["Employee code"] == "Line 2 has the same code."
    assert messages["Email"] == "This doesn't look like an email address."
    assert "Settings" in messages["Branch"]
    # Nothing saved, and importing a file with problems is refused.
    assert await people(owner) == before
    refused = await send(owner, text, commit=True)
    assert refused.status_code == 422
    assert refused.json()["code"] == "import_has_errors"
    assert await people(owner) == before


async def test_importing_creates_people_departments_and_balances(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    text = (
        "Name,Code,Email,Department,Job title,Joined on,Casual leave (days left),Sick leave\n"
        "Nusrat Jahan,E-1,Nusrat@Example.com,Design / Motion,Designer,15/01/2024,7.5,14\n"
        "Fahim Shahriar,E-2,,Design,Designer,,10,\n"
        "সুমাইয়া ইসলাম,E-3,,Sales,,,,\n"
    )
    done = await send(owner, text, commit=True)
    assert done.status_code == 200, done.text
    assert (done.json()["create"], done.json()["committed"]) == (3, True)
    found = await people(owner)
    nusrat = found["Nusrat Jahan"]
    assert (nusrat["employee_code"], nusrat["email"], nusrat["joined_on"]) == (
        "E-1",
        "nusrat@example.com",
        "2024-01-15",
    )
    departments = {d["name"]: d for d in (await owner.get("/v1/departments")).json()}
    assert departments["Motion"]["parent_id"] == departments["Design"]["id"]
    assert nusrat["department_id"] == departments["Motion"]["id"]
    assert found["Fahim Shahriar"]["department_id"] == departments["Design"]["id"]
    assert await days_left(owner, nusrat["id"], "Casual leave") == 7.5
    assert await days_left(owner, nusrat["id"], "Sick leave") == 14
    assert await days_left(owner, found["Fahim Shahriar"]["id"], "Casual leave") == 10
    adjustments = (await owner.get("/v1/leave/adjustments", params={"employee_id": nusrat["id"]})).json()
    assert {a["reason"] for a in adjustments} == {"Days left set by a spreadsheet import"}
    log = (await owner.get("/v1/audit")).json()["items"]
    assert "people.imported" in {e["action"] for e in log}

    # Importing the same file again changes nothing; an edited one updates in place.
    again = await preview(owner, text)
    assert (again["create"], again["update"], again["unchanged"]) == (0, 0, 3)
    edited = text.replace("Designer,15/01/2024,7.5", "Lead designer,15/01/2024,5")
    changed = await preview(owner, edited)
    [update] = [r for r in changed["rows"] if r["action"] == "update"]
    assert (update["name"], update["changes"]) == ("Nusrat Jahan", ["job_title", "Casual leave"])
    assert (await send(owner, edited, commit=True)).status_code == 200
    assert (await people(owner))["Nusrat Jahan"]["job_title"] == "Lead designer"
    assert await days_left(owner, nusrat["id"], "Casual leave") == 5
    assert len(await people(owner)) == 4  # the owner and three


async def test_people_are_matched_by_code_then_email(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    await send(
        owner, "Name,Code,Email\nKarim,E-7,karim@example.com\nSalma,E-8,salma@example.com\n", commit=True
    )
    by_email = await preview(owner, "Name,Email,Phone\nKarim Mia,KARIM@example.com,01711000000\n")
    assert by_email["rows"][0]["action"] == "update"
    assert by_email["rows"][0]["changes"] == ["full_name", "phone"]
    mixed = await preview(owner, "Name,Code,Email\nKarim,E-7,salma@example.com\n")
    assert mixed["rows"][0]["errors"][0]["message"] == "This email belongs to Salma, but the code to Karim."


async def test_leave_columns_need_the_leave_module_and_a_limit(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    unlimited = await preview(owner, "Name,Unpaid leave\nKarim,3\n")
    assert (
        unlimited["rows"][0]["errors"][0]["message"]
        == "Unpaid leave has no limit, so there are no days left to set."
    )
    await owner.put("/v1/workspace/modules", json={"modules": ["attendance"]})
    off = await preview(owner, "Name,Casual leave\nKarim,3\n")
    assert off["columns"][1]["field"] is None
    assert off["rows"][0]["action"] == "create"


async def test_template_lists_the_workspace_leave_types(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    response = await owner.get("/v1/people/import/template")
    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="people-import.csv"'
    header = response.text.lstrip("﻿").splitlines()[0]
    assert header.startswith("Name,Employee code,Email")
    assert "Casual leave (days left)" in header
    assert "Unpaid leave" not in header
    # The template itself imports cleanly.
    result = await preview(owner, response.text)
    assert (result["create"], result["errors"]) == (1, 0)
    bangla = (await owner.get("/v1/people/import/template", params={"lang": "bn"})).text
    assert bangla.lstrip("﻿").startswith("নাম,কোড,ইমেইল")
    assert (await preview(owner, bangla))["errors"] == 0


async def test_only_owners_and_admins_import(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    sales = (await owner.post("/v1/departments", json={"name": "Sales"})).json()
    manager = await invite_and_join(owner, role="admin", scope_department_id=sales["id"])
    _, staff = await add_staff(owner)
    scoped = await send(manager, "Name\nKarim\n")
    assert (scoped.status_code, scoped.json()["code"]) == (403, "workspace_wide")
    assert (await send(staff, "Name\nKarim\n")).status_code == 403
    assert (await staff.get("/v1/people/import/template")).status_code == 403
    too_big = await owner.post(
        "/v1/people/import", content=b"Name\n" + b"x" * (parse.MAX_SIZE + 10), headers=CSV
    )
    assert too_big.status_code in (413, 422)


async def test_the_plan_limit_applies_to_the_whole_file(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    rows = "".join(f"Person {i}\n" for i in range(60))
    response = await send(owner, "Name\n" + rows, commit=True)
    assert response.status_code == 402
    assert response.json()["code"] == "people_limit"
    assert len(await people(owner)) == 1


async def test_departments_are_matched_whatever_their_case(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    text = "Name,Department\nKarim,Design / Motion\nSalma,design / motion\nRafiq,DESIGN\n"
    result = await preview(owner, text)
    assert result["new_departments"] == ["Design", "Design / Motion"]
    assert (await send(owner, text, commit=True)).status_code == 200
    names = sorted(d["name"] for d in (await owner.get("/v1/departments")).json())
    assert names == ["Design", "Motion"]
    found = await people(owner)
    assert found["Karim"]["department_id"] == found["Salma"]["department_id"]
