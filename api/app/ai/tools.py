"""Loads every module's capabilities into the registry and describes them as tools."""

from __future__ import annotations

from typing import Any

from app.modules.attendance import capabilities as _attendance  # noqa: F401
from app.modules.leave import capabilities as _leave  # noqa: F401
from app.modules.payroll import capabilities as _payroll  # noqa: F401
from app.modules.people import capabilities as _people  # noqa: F401
from app.modules.platform.capabilities import REGISTRY, visible
from app.modules.platform.deps import Ctx

__all__ = ["REGISTRY", "tool_specs"]


def tool_specs(ctx: Ctx) -> list[dict[str, Any]]:
    """The capabilities this person may use, with their schemas."""
    return [c.describe() for c in visible(ctx)]
