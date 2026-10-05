"""Application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from sqlalchemy import text

from app.ai.routes import operator_router
from app.ai.routes import router as ai_router
from app.core.config import get_settings
from app.core.db import dispose_engine, open_session
from app.core.errors import install_error_handlers
from app.core.idempotency import IdempotencyMiddleware
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.outbox import FlushMiddleware
from app.modules.accounting.routes import router as accounting_router
from app.modules.announcements.routes import router as announcements_router
from app.modules.approvals.routes import router as approvals_router
from app.modules.attendance.routes import router as attendance_router
from app.modules.automations.routes import internal_router as automations_internal_router
from app.modules.automations.routes import router as automations_router
from app.modules.customers.routes import router as customers_router
from app.modules.documents.routes import router as documents_router
from app.modules.expenses.routes import router as expenses_router
from app.modules.imports.routes import router as imports_router
from app.modules.inventory.routes import router as inventory_router
from app.modules.leave.routes import router as leave_router
from app.modules.notifications.routes import internal_router as notifications_internal_router
from app.modules.notifications.routes import router as notifications_router
from app.modules.payroll.routes import router as payroll_router
from app.modules.people.routes import router as people_router
from app.modules.platform.deps import public
from app.modules.platform.internal import router as internal_router
from app.modules.platform.passkeys import router as passkeys_router
from app.modules.platform.routes_auth import plans_router
from app.modules.platform.routes_auth import router as auth_router
from app.modules.platform.routes_developers import router as developers_router
from app.modules.platform.routes_join import router as join_router
from app.modules.platform.routes_webhooks import router as webhooks_router
from app.modules.platform.routes_workspace import router as workspace_router
from app.modules.platform.scim import router as scim_router
from app.modules.platform.sso import router as sso_router
from app.modules.platform.support import router as support_router
from app.modules.privacy.routes import router as privacy_router
from app.modules.reports.routes import internal_router as reports_internal_router
from app.modules.reports.routes import router as reports_router
from app.modules.sales.routes import router as sales_router
from app.modules.sales.tills import router as tills_router
from app.modules.tasks.routes import router as tasks_router
from app.modules.welcome.routes import router as welcome_router

log = logging.getLogger("app")

ROUTERS = (
    auth_router,
    passkeys_router,
    plans_router,
    workspace_router,
    imports_router,
    people_router,
    attendance_router,
    leave_router,
    payroll_router,
    notifications_router,
    tasks_router,
    announcements_router,
    documents_router,
    approvals_router,
    reports_router,
    automations_router,
    sales_router,
    tills_router,
    customers_router,
    expenses_router,
    inventory_router,
    accounting_router,
    privacy_router,
    ai_router,
    operator_router,
    join_router,
    developers_router,
    webhooks_router,
    sso_router,
    scim_router,
    support_router,
    welcome_router,
    internal_router,
    notifications_internal_router,
    reports_internal_router,
    automations_internal_router,
)
ops_router = APIRouter(tags=["ops"])


@ops_router.get("/healthz")
async def healthz(_: None = Depends(public())) -> dict[str, str]:
    return {"status": "ok"}


@ops_router.get("/readyz")
async def readyz(_: None = Depends(public())) -> dict[str, str]:
    async with open_session() as db:
        await db.execute(text("SELECT 1"))
    return {"status": "ready"}


def api_routes() -> list[APIRoute]:
    """Every endpoint, flattened (used by the route audit and isolation tests)."""
    return [r for router in (*ROUTERS, ops_router) for r in router.routes if isinstance(r, APIRoute)]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.env)
    docs = settings.env in ("dev", "test")
    app = FastAPI(
        title="CompanyMgmt API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url=None,
        openapi_url="/v1/openapi.json",
    )
    install_error_handlers(app)
    # Innermost: deliver this request's outbox events before its response goes out.
    app.add_middleware(FlushMiddleware)
    # Replays need the request context (and its size limit) set up first.
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["authorization", "content-type", "x-cm-client", "if-match", "idempotency-key"],
        expose_headers=[
            "etag",
            "x-request-id",
            "retry-after",
            "content-disposition",
            "idempotent-replayed",
        ],
        max_age=600,
    )
    app.add_middleware(RequestContextMiddleware)

    for router in (*ROUTERS, ops_router):
        app.include_router(router)
    return app


app = create_app()
