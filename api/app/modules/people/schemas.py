"""People request and response shapes, shared by the REST routes and capabilities."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import EmailStr, StringConstraints, model_validator

from app.core.schema import In, Name, Out, ShortName
from app.core.security import crypto
from app.core.time import today
from app.modules.people.models import EMPLOYMENT_TYPES, Employee

EmploymentType = Literal["full_time", "part_time", "contract", "intern", "daily"]
assert set(EMPLOYMENT_TYPES) == {"full_time", "part_time", "contract", "intern", "daily"}


class DepartmentOut(Out):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    people: int
    version: int


class DepartmentIn(In):
    name: ShortName
    parent_id: uuid.UUID | None = None


class DepartmentPatch(In):
    name: ShortName | None = None
    parent_id: uuid.UUID | None = None
    move_to_top: bool = False


class EmployeeOut(Out):
    id: uuid.UUID
    membership_id: uuid.UUID | None
    employee_code: str | None
    full_name: str
    preferred_name: str | None
    email: str | None
    phone: str | None
    department_id: uuid.UUID | None
    branch_id: uuid.UUID | None
    job_title: str | None
    employment_type: str
    status: str
    joined_on: date | None
    left_on: date | None
    date_of_birth: date | None
    national_id_last4: str | None
    notes: str | None
    created_at: datetime
    version: int


Code = Annotated[str, StringConstraints(max_length=40, strip_whitespace=True)]
Phone = Annotated[str, StringConstraints(max_length=40, pattern=r"^[0-9+()\-\s.]{3,40}$")]
NationalId = Annotated[str, StringConstraints(max_length=40, strip_whitespace=True)]
Title = Annotated[str, StringConstraints(max_length=120, strip_whitespace=True)]
Notes = Annotated[str, StringConstraints(max_length=5000)]


class EmployeeIn(In):
    full_name: Name
    preferred_name: ShortName | None = None
    employee_code: Code | None = None
    email: EmailStr | None = None
    phone: Phone | None = None
    department_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    job_title: Title | None = None
    employment_type: EmploymentType = "full_time"
    joined_on: date | None = None
    date_of_birth: date | None = None
    national_id: NationalId | None = None
    notes: Notes | None = None

    @model_validator(mode="after")
    def _dates(self) -> EmployeeIn:
        if self.date_of_birth and self.date_of_birth > today("Pacific/Kiritimati"):
            raise ValueError("Date of birth can't be in the future.")
        if self.date_of_birth and self.date_of_birth.year < 1900:
            raise ValueError("Check the date of birth.")
        return self


class EmployeePatch(In):
    full_name: Name | None = None
    preferred_name: ShortName | None = None
    employee_code: Code | None = None
    email: EmailStr | None = None
    phone: Phone | None = None
    department_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    job_title: Title | None = None
    employment_type: EmploymentType | None = None
    status: Literal["active", "inactive", "left"] | None = None
    joined_on: date | None = None
    left_on: date | None = None
    date_of_birth: date | None = None
    national_id: NationalId | None = None
    notes: Notes | None = None
    clear: list[
        Literal[
            "department_id",
            "branch_id",
            "employee_code",
            "email",
            "phone",
            "job_title",
            "preferred_name",
            "left_on",
            "date_of_birth",
            "national_id",
            "notes",
        ]
    ] = []


def nid_context(employee_id: uuid.UUID) -> str:
    return f"employee:{employee_id}:national_id"


def employee_out(e: Employee) -> EmployeeOut:
    last4 = None
    if e.national_id_enc:
        try:
            last4 = crypto.decrypt(e.national_id_enc, context=nid_context(e.id))[-4:]
        except (ValueError, KeyError):
            last4 = None
    return EmployeeOut(
        id=e.id,
        membership_id=e.membership_id,
        employee_code=e.employee_code,
        full_name=e.full_name,
        preferred_name=e.preferred_name,
        email=e.email,
        phone=e.phone,
        department_id=e.department_id,
        branch_id=e.branch_id,
        job_title=e.job_title,
        employment_type=e.employment_type,
        status=e.status,
        joined_on=e.joined_on,
        left_on=e.left_on,
        date_of_birth=e.date_of_birth,
        national_id_last4=last4,
        notes=e.notes,
        created_at=e.created_at,
        version=e.version,
    )
