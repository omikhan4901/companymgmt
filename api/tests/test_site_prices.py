"""The marketing site's price list must match the plans in the database."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

SITE_PLANS = Path(__file__).resolve().parents[2] / "web" / "src" / "data" / "plans.json"
FIELDS = (
    "key",
    "name",
    "price_month_cents",
    "price_year_cents",
    "included_people",
    "extra_person_cents",
    "max_people",
    "max_branches",
    "max_modules",
)


async def test_site_prices_match_database(client: httpx.AsyncClient) -> None:
    api_plans = (await client.get("/v1/plans")).json()
    site_plans = json.loads(SITE_PLANS.read_text())
    assert [{k: p[k] for k in FIELDS} for p in api_plans] == [{k: p[k] for k in FIELDS} for p in site_plans]
    for api_plan, site_plan in zip(api_plans, site_plans, strict=True):
        for feature in ("custom_roles", "api", "sso"):
            assert bool(api_plan["features"].get(feature)) == bool(site_plan["features"].get(feature))
