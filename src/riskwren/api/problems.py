"""RFC 9457 problem details for every API error."""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

import sqlalchemy.exc
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from riskwren.core.errors import (
    AuditError,
    Conflict,
    Invalid,
    NotFound,
    PermissionDenied,
    RiskWrenError,
    StoreError,
)

PROBLEM_JSON = "application/problem+json"
log = logging.getLogger("riskwren.api")


def problem(status: int, detail: str | None = None, **extra: Any) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": HTTPStatus(status).phrase,
        "status": status,
    }
    if detail:
        body["detail"] = detail
    body.update(extra)
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON)


def install_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else None
        response = problem(exc.status_code, detail, instance=request.url.path)
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"location": list(err.get("loc", ())), "message": err.get("msg", "")}
            for err in exc.errors()
        ]
        return problem(422, "The request is not valid.", errors=errors, instance=request.url.path)

    @app.exception_handler(NotFound)
    async def not_found(request: Request, exc: NotFound) -> JSONResponse:
        return problem(404, str(exc) or None, instance=request.url.path)

    @app.exception_handler(PermissionDenied)
    async def denied(request: Request, exc: PermissionDenied) -> JSONResponse:
        return problem(403, str(exc) or None, instance=request.url.path)

    @app.exception_handler(Conflict)
    async def conflict(request: Request, exc: Conflict) -> JSONResponse:
        return problem(409, str(exc), instance=request.url.path)

    @app.exception_handler(Invalid)
    async def invalid(request: Request, exc: Invalid) -> JSONResponse:
        errors = [
            {"location": [field], "message": message} for field, message in exc.errors.items()
        ]
        return problem(422, str(exc), errors=errors, instance=request.url.path)

    @app.exception_handler(StoreError)
    async def store_error(request: Request, exc: StoreError) -> JSONResponse:
        log.error("database unavailable: %s", exc)
        return problem(503, "The database is unavailable.", instance=request.url.path)

    @app.exception_handler(AuditError)
    async def audit_error(request: Request, exc: AuditError) -> JSONResponse:
        # A programming error, never the caller's: say nothing of the internals.
        log.error("refused an unaudited write on %s %s: %s", request.method, request.url.path, exc)
        return problem(500, "An unexpected error occurred.", instance=request.url.path)

    @app.exception_handler(RiskWrenError)
    async def riskwren_error(request: Request, exc: RiskWrenError) -> JSONResponse:
        return problem(400, str(exc), instance=request.url.path)

    @app.exception_handler(sqlalchemy.exc.OperationalError)
    @app.exception_handler(sqlalchemy.exc.InterfaceError)
    async def database_unreachable(request: Request, exc: Exception) -> JSONResponse:
        log.error("the database is unavailable on %s: %s", request.url.path, exc)
        return problem(
            503,
            "The database is unavailable. An administrator can check it with `riskwren doctor`.",
            instance=request.url.path,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return problem(500, "An unexpected error occurred.", instance=request.url.path)
