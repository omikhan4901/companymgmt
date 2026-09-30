"""Tests run against a real Postgres (RLS can't be tested on anything else).

The schema is rebuilt once per run from the migrations; tables are emptied before each test.
Override the connections with TEST_DATABASE_URL / TEST_MIGRATIONS_DATABASE_URL (CI does).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

_APP_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://cm_app:cm_app@localhost:5432/companymgmt_test"
)
_OWNER_URL = os.environ.get(
    "TEST_MIGRATIONS_DATABASE_URL", "postgresql+psycopg://cm_owner:cm_owner@localhost:5432/companymgmt_test"
)
os.environ.update(
    {
        "ENV": "test",
        "DATABASE_URL": _APP_URL,
        "MIGRATIONS_DATABASE_URL": _OWNER_URL,
        "EMAIL_BACKEND": "memory",
        "INTERNAL_TOKEN": "test-internal-token",
        "TURNSTILE_SECRET": "",
        "CORS_ORIGINS": "https://app.test",
        "WEB_BASE_URL": "https://app.test",
    }
)

import httpx  # noqa: E402
import psycopg  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from app.core import email  # noqa: E402
from app.main import app  # noqa: E402
from app.models_registry import metadata  # noqa: E402

KEEP = {"plans"}


def owner_dsn() -> str:
    return _OWNER_URL.replace("postgresql+psycopg://", "postgresql://")


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    with psycopg.connect(owner_dsn(), autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conn.execute("CREATE SCHEMA public")
    config = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    config.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "migrations"))
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def _clean() -> None:
    tables = ", ".join(t for t in metadata.tables if t not in KEEP)
    with psycopg.connect(owner_dsn(), autocommit=True) as conn:
        conn.execute("SET app.allow_purge = 'on'")
        conn.execute(f"TRUNCATE {tables} RESTART IDENTITY CASCADE")
    email.sent.clear()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, client=("203.0.113.10", 51000))
    async with httpx.AsyncClient(transport=transport, base_url="https://api.test") as c:
        yield c


@pytest.fixture
def owner_sql() -> Iterator[psycopg.Connection]:
    """A superuser-free owner connection for checks the app itself can't do."""
    with psycopg.connect(owner_dsn(), autocommit=True) as conn:
        yield conn
