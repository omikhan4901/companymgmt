"""Approval inbox shapes."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from app.core.schema import In, Note, Out

Kind = Literal["leave", "time_fix"]


class ApprovalItem(Out):
    kind: Kind
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str | None
    requested_at: datetime
    reason: str | None
    # Leave
    leave_type_name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    days: float | None = None
    half_day: str | None = None
    # Time fix
    fix_kind: str | None = None
    clock_in_at: datetime | None = None
    clock_out_at: datetime | None = None


class InboxOut(Out):
    items: list[ApprovalItem]


class CountOut(Out):
    count: int


class DecisionIn(In):
    note: Note | None = None


class DecisionOut(Out):
    kind: Kind
    id: uuid.UUID
    status: str
