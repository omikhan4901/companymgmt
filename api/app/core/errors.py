"""Errors as RFC 9457 problem details. Internals never reach the client."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm.exc import StaleDataError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("app.errors")

PROBLEM = "application/problem+json"


class AppError(Exception):
    status = 400
    code = "bad_request"
    title = "Bad request"

    def __init__(
        self,
        detail: str | None = None,
        *,
        code: str | None = None,
        errors: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail or self.title)
        self.detail = detail or self.title
        if code:
            self.code = code
        self.errors = errors
        self.headers = headers
        self.extra = extra or {}


class NotFound(AppError):
    status, code, title = 404, "not_found", "Not found"


class Unauthorized(AppError):
    status, code, title = 401, "unauthorized", "Please sign in"


class Forbidden(AppError):
    status, code, title = 403, "forbidden", "You don't have permission to do this"


class Conflict(AppError):
    status, code, title = 409, "conflict", "Conflict"


class PreconditionFailed(AppError):
    status, code, title = 412, "stale", "Someone else changed this. Reload and try again."


class Invalid(AppError):
    status, code, title = 422, "invalid", "Some fields need attention"


class PaymentRequired(AppError):
    status, code, title = 402, "plan_required", "Your plan doesn't include this"


class TooManyRequests(AppError):
    status, code, title = 429, "rate_limited", "Too many attempts. Please wait and try again."


class Gone(AppError):
    status, code, title = 410, "gone", "This no longer exists"


def _problem(
    request: Request,
    status: int,
    code: str,
    title: str,
    detail: str,
    errors: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"https://companymgmt.app/problems/{code}",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
        "request_id": getattr(request.state, "request_id", None),
    }
    if errors:
        body["errors"] = errors
    if extra:
        body.update(extra)
    return JSONResponse(body, status_code=status, media_type=PROBLEM, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return _problem(
            request, exc.status, exc.code, exc.title, exc.detail, exc.errors, exc.headers, exc.extra
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(p) for p in e.get("loc", ()) if p != "body"),
                "message": e.get("msg", "Invalid value"),
                "type": e.get("type", "value_error"),
            }
            for e in exc.errors()
        ]
        return _problem(request, 422, "invalid", Invalid.title, "Some fields need attention", errors)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed", 413: "too_large", 415: "unsupported"}
        return _problem(
            request,
            exc.status_code,
            code.get(exc.status_code, "http_error"),
            str(exc.detail),
            str(exc.detail),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(StaleDataError)
    async def _stale(request: Request, exc: StaleDataError) -> JSONResponse:
        return _problem(request, 412, "stale", PreconditionFailed.title, PreconditionFailed.title)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled error", extra={"request_id": getattr(request.state, "request_id", None)})
        return _problem(
            request, 500, "server_error", "Something went wrong", "Something went wrong on our side."
        )
