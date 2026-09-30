"""Leave request and response shapes, shared by the REST routes and (later) AI tools."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.core.schema import In, Note, Out, ShortName

Color = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]
DaysIn = Annotated[Decimal, Field(ge=0, le=366, multiple_of=Decimal("0.5"))]
HalfDay = Literal["none", "morning", "afternoon"]
Weekday = Annotated[int, Field(ge=1, le=7)]


class LeaveTypeOut(Out):
    id: uuid.UUID
    name: str
    paid: bool
    days_per_year: float | None
    accrual: Literal["yearly", "monthly"]
    carry_over_max: float
    allow_half_day: bool
    calendar_days: bool
    prorate: bool
    active: bool
    color: str
    version: int


class LeaveTypeIn(In):
    name: ShortName
    paid: bool = True
    days_per_year: DaysIn | None = None
    accrual: Literal["yearly", "monthly"] = "yearly"
    carry_over_max: DaysIn = Decimal(0)
    allow_half_day: bool = True
    calendar_days: bool = False
    prorate: bool = True
    color: Color = "#6d28d9"


class LeaveTypePatch(In):
    name: ShortName | None = None
    paid: bool | None = None
    days_per_year: DaysIn | None = None
    # Set to make the type unlimited (days_per_year = null).
    unlimited: bool = False
    accrual: Literal["yearly", "monthly"] | None = None
    carry_over_max: DaysIn | None = None
    allow_half_day: bool | None = None
    calendar_days: bool | None = None
    prorate: bool | None = None
    active: bool | None = None
    color: Color | None = None


class PolicyOut(BaseModel):
    weekly_off: list[int]
    team_calendar: bool


class PolicyIn(In):
    weekly_off: list[Weekday] = Field(max_length=6)
    team_calendar: bool = True


class HolidayOut(Out):
    id: uuid.UUID
    day: date
    name: str
    branch_id: uuid.UUID | None


class HolidayIn(In):
    day: date
    name: ShortName
    branch_id: uuid.UUID | None = None


class BalanceOut(BaseModel):
    leave_type_id: uuid.UUID
    name: str
    paid: bool
    color: str
    unlimited: bool
    # This year's days (after joining-date share and monthly accrual so far).
    entitled: float
    # The full year's days for this person (what monthly accrual builds up to).
    full_year: float | None
    carried_over: float
    adjusted: float
    used: float
    pending: float
    available: float | None


class PersonBalances(BaseModel):
    employee_id: uuid.UUID
    employee_name: str
    year: int
    balances: list[BalanceOut]


class RequestIn(In):
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    half_day: HalfDay = "none"
    reason: Note | None = None
    # Asking for someone else needs leave.manage.
    employee_id: uuid.UUID | None = None


class QuoteOut(BaseModel):
    days: float
    available: float | None
    enough: bool
    # Days in the range that don't count (weekly off, holidays).
    skipped: list[date]


class RequestOut(Out):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str | None = None
    leave_type_id: uuid.UUID
    leave_type_name: str | None = None
    start_date: date
    end_date: date
    half_day: str
    days: float
    reason: str | None
    status: str
    requested_by: uuid.UUID | None
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    decision_note: str | None
    created_at: datetime
    version: int


class DecisionIn(In):
    note: Note | None = None


class CalendarEntry(BaseModel):
    employee_id: uuid.UUID
    employee_name: str
    start_date: date
    end_date: date
    half_day: str
    status: str
    # Hidden (None) for people who may only see that a colleague is away.
    leave_type_name: str | None
    color: str | None


class AdjustmentIn(In):
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    year: int = Field(ge=2000, le=2100)
    days: Annotated[Decimal, Field(ge=-366, le=366, multiple_of=Decimal("0.5"))]
    reason: Annotated[str, StringConstraints(min_length=3, max_length=300, strip_whitespace=True)]


class AdjustmentOut(Out):
    id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    year: int
    days: float
    reason: str
    created_by: uuid.UUID | None
    created_at: datetime
