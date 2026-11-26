"""What each person owes, the heat map, and the risk dashboard."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from riskwren.access.policy import current
from riskwren.api.common import envelope, reading
from riskwren.api.routers.inventory import UNIT
from riskwren.reporting import service as reporting
from riskwren.treatment import service as treatment

router = APIRouter(prefix="/api/v1", tags=["reporting"])


@router.get("/home", summary="What the asker owes, overdue first")
def home(request: Request) -> dict[str, Any]:
    principal = current(request)
    treatment.catch_up(request.app.state.db)
    with reading(request) as session:
        return envelope(reporting.home(session, principal))


@router.get("/heat-map", summary="Open risks counted by likelihood and impact")
def heat_map(
    request: Request,
    kind: str = Query(default="residual", description="inherent, residual, or target"),
    unit: int | None = UNIT,
    category: str | None = Query(
        default=None, description="A category key; includes those beneath"
    ),
) -> dict[str, Any]:
    principal = current(request)
    treatment.catch_up(request.app.state.db)
    with reading(request) as session:
        return envelope(
            reporting.heat_map(session, principal, kind=kind, unit=unit, category=category)
        )


@router.get("/dashboard", summary="Where the register stands, each figure with its list's filters")
def dashboard(request: Request, unit: int | None = UNIT) -> dict[str, Any]:
    principal = current(request)
    treatment.catch_up(request.app.state.db)
    with reading(request) as session:
        return envelope(reporting.dashboard(session, principal, unit=unit))
