"""Helpers for files people open in spreadsheet apps."""

from __future__ import annotations


def safe_cell(value: object) -> str:
    """Stop spreadsheet apps from running cell contents as formulas."""
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text
