"""Health and what the web app needs before anyone signs in."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from riskwren import TAGLINE, __version__
from riskwren.api.common import database, envelope, reading
from riskwren.db import migrate
from riskwren.demo.build import marker as demo_marker
from riskwren.program import branding

router = APIRouter(prefix="/api/v1", tags=["system"])


@router.get("/health/live", summary="Is the server process running?")
def live() -> dict[str, Any]:
    return envelope({"status": "ok"})


@router.get("/health/ready", summary="Can the server do its work?")
def ready(request: Request) -> JSONResponse:
    """The database answers and its schema is the one this version expects."""
    engine = database(request).engine
    state = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        if not migrate.is_current(engine):
            state = "outdated"
    except Exception:
        state = "unreachable"
    status = "ok" if state == "ok" else "degraded"
    body = envelope({"status": status, "database": state, "version": __version__})
    return JSONResponse(body, status_code=200 if status == "ok" else 503)


@router.get("/meta", summary="The product's name, version, and branding")
def meta(request: Request) -> dict[str, Any]:
    """What the web app needs before anyone signs in."""
    with reading(request) as session:
        brand = branding.public_view(branding.load(session))
        demo = demo_marker(session)
    sso = request.app.state.config.sso
    return envelope(
        {
            "product": {"name": brand["product_name"], "tagline": TAGLINE},
            "version": __version__,
            "branding": brand,
            "palettes": list(branding.PALETTES),
            # A demo says so, and names the sample people its sign-in page offers.
            "demo": {"built_on": demo["built_on"], "accounts": demo["accounts"]} if demo else None,
            # Single sign-on is optional. Nothing about it is said unless it is set up.
            "sso": {"label": sso.label, "local_sign_in": sso.local_sign_in}
            if sso.enabled
            else None,
        }
    )
