"""Location checks for clocking in and out.

A clock-in counts as "inside" when the reported position, allowing for the phone's stated
accuracy (capped, so a vague fix can't stretch the area), is within a branch's radius.

Browser location can be faked by a determined person; this check stops casual clock-ins
from home, and the saved distance and accuracy let managers spot anything odd.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from decimal import Decimal

EARTH_RADIUS_M = 6_371_008.8


@dataclass(frozen=True)
class Point:
    latitude: float
    longitude: float
    accuracy_m: float


@dataclass(frozen=True)
class Site:
    branch_id: uuid.UUID
    latitude: float
    longitude: float
    radius_m: int


@dataclass(frozen=True)
class Check:
    result: str  # inside | outside | no_fix | no_site
    branch_id: uuid.UUID | None = None
    distance_m: int | None = None


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (haversine), accurate to well under a metre at these ranges."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def check(
    point: Point | None, sites: list[Site], *, max_accuracy_m: int, prefer: uuid.UUID | None = None
) -> Check:
    """Compare a position with the branch areas.

    Returns the branch the person is at (the preferred one if they're inside several),
    or the nearest one with its distance when they're outside all of them.
    """
    if not sites:
        return Check("no_site")
    if point is None:
        return Check("no_fix")
    slack = min(max(point.accuracy_m, 0.0), float(max_accuracy_m))
    measured = sorted(
        ((distance_m(point.latitude, point.longitude, s.latitude, s.longitude), s) for s in sites),
        key=lambda pair: (pair[1].branch_id != prefer, pair[0]),
    )
    for dist, site in measured:
        if dist - slack <= site.radius_m:
            return Check("inside", site.branch_id, round(dist))
    dist, site = min(measured, key=lambda pair: pair[0])
    return Check("outside", site.branch_id, round(dist))


def rounded(value: float, places: int = 4) -> Decimal:
    """About 11 m of precision: enough to settle a dispute, not enough to pinpoint a desk."""
    return Decimal(str(round(value, places)))
