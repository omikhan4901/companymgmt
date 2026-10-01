"""Attendance request and response shapes, shared by the REST routes and capabilities."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.core.schema import In, Note, Out
from app.modules.attendance.models import AttendanceCorrection, AttendanceRecord


class RecordOut(Out):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str | None = None
    branch_id: uuid.UUID | None
    business_date: date
    clock_in_at: datetime
    clock_out_at: datetime | None
    minutes: int | None
    status: str
    source: str
    note: str | None
    in_geo: str | None = None
    in_distance_m: int | None = None
    in_accuracy_m: int | None = None
    in_latitude: float | None = None
    in_longitude: float | None = None
    out_geo: str | None = None
    out_distance_m: int | None = None
    out_accuracy_m: int | None = None
    out_latitude: float | None = None
    out_longitude: float | None = None
    version: int


class StatusOut(Out):
    employee_id: uuid.UUID
    employee_name: str
    open_record: RecordOut | None
    today_minutes: int
    forgot_clock_out: bool
    location_mode: str


class GeoIn(In):
    """A position from the device (browser Geolocation API)."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float = Field(ge=0, le=100_000)


class ClockIn(In):
    branch_id: uuid.UUID | None = None
    note: Note | None = None
    client_time: datetime | None = None
    location: GeoIn | None = None


class ClockOut(In):
    note: Note | None = None
    location: GeoIn | None = None


class SettingsOut(BaseModel):
    location_mode: Literal["off", "record", "require"]
    max_accuracy_m: int
    day_starts_at: time
    late_after_minutes: int
    branches_total: int
    branches_located: int


class SettingsIn(In):
    location_mode: Literal["off", "record", "require"]
    max_accuracy_m: int = Field(default=100, ge=10, le=1000)
    # Left out: unchanged.
    day_starts_at: time | None = None
    late_after_minutes: int | None = Field(default=None, ge=0, le=240)


class RecordIn(In):
    employee_id: uuid.UUID
    clock_in_at: datetime
    clock_out_at: datetime | None = None
    branch_id: uuid.UUID | None = None
    note: Note | None = None


class RecordPatch(In):
    clock_in_at: datetime | None = None
    clock_out_at: datetime | None = None
    note: Note | None = None


class CorrectionIn(In):
    kind: Literal["add", "change", "remove"]
    record_id: uuid.UUID | None = None
    clock_in_at: datetime | None = None
    clock_out_at: datetime | None = None
    reason: Annotated[str, StringConstraints(min_length=3, max_length=500, strip_whitespace=True)]


class CorrectionOut(Out):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str | None = None
    record_id: uuid.UUID | None
    kind: str
    proposed_clock_in_at: datetime | None
    proposed_clock_out_at: datetime | None
    reason: str
    status: str
    requested_by: uuid.UUID | None
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    decision_note: str | None
    created_at: datetime
    version: int


class DecisionIn(In):
    note: Annotated[str, StringConstraints(max_length=500)] | None = None


class DayOut(Out):
    date: date
    minutes: int
    records: int
    needs_review: int


class TimesheetRow(Out):
    employee_id: uuid.UUID
    employee_name: str
    days: list[DayOut]
    total_minutes: int
    days_present: int


class TimesheetOut(Out):
    month: str
    start: date
    end: date
    rows: list[TimesheetRow]


class PresentOut(Out):
    employee_id: uuid.UUID
    employee_name: str
    clock_in_at: datetime
    branch_id: uuid.UUID | None


def record_out(r: AttendanceRecord, name: str | None = None) -> RecordOut:
    out = RecordOut.model_validate(r)
    out.employee_name = name
    return out


def correction_out(c: AttendanceCorrection, name: str | None = None) -> CorrectionOut:
    out = CorrectionOut.model_validate(c)
    out.employee_name = name
    return out
