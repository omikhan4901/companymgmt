"""Shared request/response model settings and field types."""

from __future__ import annotations

import unicodedata
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def _clean_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value).strip()
    # Drop control characters except normal whitespace; keep ZWJ/ZWNJ (needed for Bangla).
    return "".join(ch for ch in value if unicodedata.category(ch) != "Cc" or ch in "\n\t")


def _non_empty(value: str) -> str:
    if not value:
        raise ValueError("This can't be empty.")
    return value


Text = Annotated[str, AfterValidator(_clean_text)]
Name = Annotated[str, Field(max_length=200), AfterValidator(_clean_text), AfterValidator(_non_empty)]
ShortName = Annotated[str, Field(max_length=120), AfterValidator(_clean_text), AfterValidator(_non_empty)]
Note = Annotated[str, Field(max_length=500), AfterValidator(_clean_text)]


class In(BaseModel):
    """Request bodies: unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid", str_max_length=5000)


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None
