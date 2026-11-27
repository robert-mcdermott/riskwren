"""Resilience: business impact analyses, recovery capabilities, and the check between them."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import envelope, reading, writing
from riskwren.inventory import records
from riskwren.inventory.registry import PROCESS, SYSTEM
from riskwren.resilience import analyse, capability_view, overview, process_view, record_capability

router = APIRouter(prefix="/api/v1", tags=["resilience"])


class Impact(BaseModel):
    after: str = Field(description="4h, 1d, 3d, 1w, or 1m")
    level: int = Field(description="1 negligible to 5 severe")


class ImpactBody(BaseModel):
    impacts: list[Impact] = Field(default_factory=list, description="How much its loss hurts")
    recovery_hours: int = Field(description="How soon it must be back")
    data_loss_hours: int = Field(description="How much information it can afford to lose")
    minimum: str | None = Field(default=None, max_length=8000, description="The least it needs")
    note: str | None = Field(default=None, max_length=8000)


class CapabilityBody(BaseModel):
    recovery_hours: int = Field(description="What it can be restored within")
    data_loss_hours: int = Field(description="How much information it can lose")
    basis: str = Field(max_length=8000, description="What that rests on")


def _service_type() -> Any:
    from riskwren.thirdparty.services import SERVICE

    return SERVICE


@router.get("/resilience", summary="Processes with their recovery needs and every shortfall")
def show_resilience(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(overview(session, principal))


@router.get("/processes/{ref}/impact", summary="A process's business impact and its shortfalls")
def show_impact(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        process = records.load(session, principal, PROCESS, ref)
        return envelope(process_view(session, principal, process))


@router.post(
    "/processes/{ref}/impact", status_code=201, summary="Analyse a process's business impact"
)
def record_impact(request: Request, ref: str, body: ImpactBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        process = records.load(session, principal, PROCESS, ref)
        analyse(session, principal, process, body.model_dump())
        return envelope(process_view(session, principal, process))


def _recovery(request: Request, kind: str, ref: str, body: CapabilityBody | None) -> dict[str, Any]:
    record_type = SYSTEM if kind == "system" else _service_type()
    principal = current(request)
    if body is None:
        with reading(request) as session:
            subject = records.load(session, principal, record_type, ref)
            return envelope(capability_view(session, principal, kind, subject))
    with writing(request, principal.actor) as session:
        subject = records.load(session, principal, record_type, ref)
        record_capability(session, principal, kind, subject, body.model_dump())
        return envelope(capability_view(session, principal, kind, subject))


@router.get("/systems/{ref}/recovery", summary="What a system can be restored within")
def show_system_recovery(request: Request, ref: str) -> dict[str, Any]:
    return _recovery(request, "system", ref, None)


@router.post("/systems/{ref}/recovery", status_code=201, summary="Say what a system can deliver")
def record_system_recovery(request: Request, ref: str, body: CapabilityBody) -> dict[str, Any]:
    return _recovery(request, "system", ref, body)


@router.get("/services/{ref}/recovery", summary="What a service can be restored within")
def show_service_recovery(request: Request, ref: str) -> dict[str, Any]:
    return _recovery(request, "service", ref, None)


@router.post("/services/{ref}/recovery", status_code=201, summary="Say what a service can deliver")
def record_service_recovery(request: Request, ref: str, body: CapabilityBody) -> dict[str, Any]:
    return _recovery(request, "service", ref, body)
