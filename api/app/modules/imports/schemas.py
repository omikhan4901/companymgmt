"""What an import preview (or a finished import) says about the file and each row."""

from __future__ import annotations

from typing import Literal

from app.core.schema import Out


class ColumnOut(Out):
    header: str
    # What the column fills in: a profile field, "leave" (then `leave_type`), or None if ignored.
    field: str | None
    leave_type: str | None = None


class CellError(Out):
    column: str
    message: str


class RowOut(Out):
    line: int
    name: str
    action: Literal["create", "update", "unchanged", "error"]
    # For updates: the columns whose values change.
    changes: list[str]
    errors: list[CellError]


class ImportOut(Out):
    committed: bool
    columns: list[ColumnOut]
    rows: list[RowOut]
    create: int
    update: int
    unchanged: int
    errors: int
    # Departments that will be (or were) created, as "Design / Motion".
    new_departments: list[str]
