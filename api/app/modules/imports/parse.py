"""Reading a people spreadsheet saved as CSV: columns, cells, dates and numbers.

No database here. Headers can be in English or Bangla and in any order; anything we
don't recognise is reported and ignored rather than guessed at.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

MAX_ROWS = 1000
MAX_COLUMNS = 60
MAX_SIZE = 2 * 1024 * 1024

# Our field -> the headers people use for it.
COLUMNS: dict[str, tuple[str, ...]] = {
    "full_name": ("name", "full name", "employee name", "staff name", "নাম", "পূর্ণ নাম", "কর্মীর নাম"),
    "preferred_name": ("preferred name", "nickname", "ডাকনাম"),
    "employee_code": ("employee code", "code", "employee id", "staff id", "id", "কোড", "আইডি", "কর্মী আইডি"),
    "email": ("email", "e-mail", "email address", "ইমেইল", "ই-মেইল"),
    "phone": ("phone", "mobile", "phone number", "mobile number", "contact", "ফোন", "মোবাইল", "ফোন নম্বর"),
    "department": ("department", "dept", "team", "বিভাগ"),
    "branch": ("branch", "office", "location", "শাখা"),
    "job_title": ("job title", "title", "designation", "position", "পদবি", "পদবী"),
    "employment_type": ("employment type", "type", "চাকরির ধরন"),
    "joined_on": (
        "joined on",
        "joining date",
        "join date",
        "date of joining",
        "start date",
        "যোগদানের তারিখ",
        "যোগদান",
    ),
    "date_of_birth": ("date of birth", "birth date", "birthday", "dob", "জন্ম তারিখ"),
}
# Words after a leave type's name that still mean "days left", e.g. "Casual leave (days left)".
LEAVE_SUFFIXES = ("days left", "balance", "remaining", "left", "days", "বাকি", "অবশিষ্ট", "দিন বাকি")

EMPLOYMENT_TYPES = {
    "full time": "full_time",
    "full-time": "full_time",
    "fulltime": "full_time",
    "permanent": "full_time",
    "part time": "part_time",
    "part-time": "part_time",
    "contract": "contract",
    "contractual": "contract",
    "intern": "intern",
    "internship": "intern",
    "daily": "daily",
    "daily wage": "daily",
    "পূর্ণকালীন": "full_time",
    "খণ্ডকালীন": "part_time",
    "চুক্তিভিত্তিক": "contract",
    "ইন্টার্ন": "intern",
    "দৈনিক": "daily",
}

# Day before month, as Bangladesh writes dates; the preview shows how each was read.
DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%d-%b-%Y",
    "%d-%b-%y",
)
BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


class Problem(Exception):
    """The file as a whole can't be read."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass
class Column:
    header: str
    # One of COLUMNS' keys, "leave" (with `leave_type`), or None when ignored.
    field: str | None
    leave_type: str | None = None


@dataclass
class Row:
    line: int
    cells: dict[str, str] = field(default_factory=dict)
    leave: dict[str, str] = field(default_factory=dict)


@dataclass
class Sheet:
    columns: list[Column]
    rows: list[Row]


def normalise(header: str) -> str:
    text = header.strip().lower().replace("_", " ")
    text = re.sub(r"[*:]+$", "", text).strip()
    return re.sub(r"\s+", " ", text)


def decode(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise Problem(
            "We couldn't read this file's text. In Excel, choose Save As, then “CSV UTF-8”.",
            code="not_utf8",
        ) from None


def _leave_type(header: str, leave_types: list[str]) -> str | None:
    text = normalise(header)
    text = re.sub(r"[()\[\]]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for suffix in LEAVE_SUFFIXES:
        if text.endswith(" " + suffix):
            text = text[: -len(suffix) - 1].strip(" -\u2013:")
            break
    for name in leave_types:
        if normalise(name) == text:
            return name
    return None


def read(data: bytes, leave_types: list[str]) -> Sheet:
    """Columns and non-empty rows. `leave_types` are the names a column may match."""
    if len(data) > MAX_SIZE:
        raise Problem("The file can be up to 2 MB.", code="file_too_large")
    text = decode(data)
    if not text.strip():
        raise Problem("The file is empty.", code="empty_file")
    try:
        dialect: type[csv.Dialect] | csv.Dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    try:
        header = next(reader)
    except StopIteration:
        raise Problem("The file is empty.", code="empty_file") from None
    if len(header) > MAX_COLUMNS:
        raise Problem(f"Use up to {MAX_COLUMNS} columns.", code="too_many_columns")

    aliases = {alias: key for key, names in COLUMNS.items() for alias in names}
    columns: list[Column] = []
    seen: set[str] = set()
    for raw in header:
        key = aliases.get(normalise(raw))
        leave = None if key else _leave_type(raw, leave_types)
        target = key or (f"leave:{leave}" if leave else None)
        if target and target in seen:  # a second "Phone" column is ignored, not merged
            key, leave = None, None
        if target:
            seen.add(target)
        columns.append(Column(raw.strip(), key or ("leave" if leave else None), leave))
    if not any(c.field == "full_name" for c in columns):
        raise Problem("Add a “Name” column with each person's full name.", code="no_name_column")

    rows: list[Row] = []
    for line, values in enumerate(reader, start=2):
        if not any(v.strip() for v in values):
            continue
        if len(rows) >= MAX_ROWS:
            raise Problem(f"Import up to {MAX_ROWS} people at a time.", code="too_many_rows")
        row = Row(line)
        for column, value in zip(columns, values, strict=False):
            # A leading apostrophe marks text in spreadsheets (we write one before "+880…").
            value = value.strip().removeprefix("'").strip()
            if not value or column.field is None:
                continue
            if column.field == "leave" and column.leave_type:
                row.leave[column.leave_type] = value
            else:
                row.cells[column.field] = value
        rows.append(row)
    if not rows:
        raise Problem("There are no people in this file yet, only the header row.", code="no_rows")
    return Sheet(columns, rows)


def parse_date(text: str) -> date | None:
    value = re.sub(r"\s+", " ", text.translate(BANGLA_DIGITS).strip())
    # "2024-01-15 00:00:00", as some exports write dates.
    value = re.sub(r"[ T]00:00(:00)?$", "", value)
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC).date()
        except ValueError:
            continue
    return None


def parse_days(text: str) -> Decimal | None:
    value = text.translate(BANGLA_DIGITS).strip().replace(",", ".")
    try:
        days = Decimal(value)
    except InvalidOperation:
        return None
    if not days.is_finite() or days < 0 or days > 366 or days % Decimal("0.5") != 0:
        return None
    return days


def parse_employment_type(text: str) -> str | None:
    text = normalise(text)
    if text in EMPLOYMENT_TYPES:
        return EMPLOYMENT_TYPES[text]
    key = text.replace(" ", "_")
    return key if key in EMPLOYMENT_TYPES.values() else None


def department_path(text: str) -> list[str]:
    """ "Design / Motion" or "Design > Motion" -> ["Design", "Motion"]."""
    return [part.strip() for part in re.split(r"\s*[/>]\s*", text) if part.strip()]
