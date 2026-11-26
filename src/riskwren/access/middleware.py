"""Work out who is asking, before any route runs, and refuse requests from other sites."""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from riskwren.access.principal import Principal
from riskwren.api.problems import problem
from riskwren.auth import sessions
from riskwren.people import accounts

SAFE = {"GET", "HEAD", "OPTIONS"}
# Changes that need no CSRF token because there is no session yet, or it is being ended.
NO_TOKEN = {
    ("POST", "/api/v1/session"),
    ("POST", "/api/v1/session/demo"),
    ("DELETE", "/api/v1/session"),
}
MAX_BODY = 32 * 1024 * 1024  # a little over the largest file anyone may send


def _hosts(request: Request) -> set[str]:
    hosts = {request.headers.get("host", "")}
    forwarded = request.headers.get("x-forwarded-host", "")
    hosts.update(part.strip() for part in forwarded.split(",") if part.strip())
    return {host.lower() for host in hosts if host}


def check_origin(request: Request) -> None:
    """A change must come from RiskWren's own pages, not from another site in the browser."""
    if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
        raise HTTPException(403, "Requests from other sites are refused.")
    origin = request.headers.get("origin")
    if origin is None:
        return  # not a browser, or an old one; the CSRF token still applies
    if origin == "null" or urlsplit(origin).netloc.lower() not in _hosts(request):
        raise HTTPException(403, "Requests from other sites are refused.")


def _authenticate(request: Request) -> Principal | None:
    token = request.cookies.get(sessions.COOKIE)
    if not token:
        return None
    config = request.app.state.config.server
    database = request.app.state.db
    # A session's sliding expiry is bookkeeping, not history, so no actor is needed.
    with database.bookkeeping() as session:
        found = sessions.load(
            session, token, idle_hours=config.session_idle_hours, max_days=config.session_max_days
        )
        if found is None:
            return None
        row, account = found
        return accounts.principal_for(session, account, row)


def _prepare(request: Request) -> None:
    unsafe = request.method not in SAFE
    if unsafe:
        check_origin(request)
    principal = _authenticate(request)
    request.state.principal = principal
    if unsafe and principal is not None and (request.method, request.url.path) not in NO_TOKEN:
        sent = request.headers.get(sessions.CSRF_HEADER, "")
        if not sent or not hmac.compare_digest(sent, principal.csrf_token):
            raise HTTPException(403, "The request is missing its CSRF token. Reload the page.")


def install_access(app: FastAPI) -> None:
    @app.middleware("http")
    async def access(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.principal = None
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > MAX_BODY:
            return problem(413, "That is too large to send.", instance=request.url.path)
        if request.url.path.startswith("/api/"):
            try:
                await run_in_threadpool(_prepare, request)
            except HTTPException as exc:
                # Answered here, inside the header middleware, so refusals carry the headers.
                return problem(exc.status_code, str(exc.detail), instance=request.url.path)
        return await call_next(request)
