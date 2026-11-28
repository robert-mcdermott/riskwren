"""Resilience: business impact analyses, recovery capabilities, and the check between them."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import envelope, reading, writing
from riskwren.inventory import records
from riskwren.inventory.registry import PROCESS, SYSTEM
from riskwren.resilience import (
    analyse,
    capability_view,
    overview,
    plans,
    process_view,
    record_capability,
)

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
    data_loss_hours: int = Field(
        default=0, description="How much information it can lose; none for a site"
    )
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
    from riskwren.inventory.registry import TYPES

    record_type = (
        SYSTEM if kind == "system" else _service_type() if kind == "service" else TYPES[kind]
    )
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


@router.get("/sites/{ref}/recovery", summary="How soon work at a site goes on again")
def show_site_recovery(request: Request, ref: str) -> dict[str, Any]:
    return _recovery(request, "site", ref, None)


@router.post("/sites/{ref}/recovery", status_code=201, summary="Say what a site can deliver")
def record_site_recovery(request: Request, ref: str, body: CapabilityBody) -> dict[str, Any]:
    return _recovery(request, "site", ref, body)


@router.get("/third-parties/{ref}/recovery", summary="What a third party can be back within")
def show_third_party_recovery(request: Request, ref: str) -> dict[str, Any]:
    return _recovery(request, "third_party", ref, None)


@router.post(
    "/third-parties/{ref}/recovery", status_code=201, summary="Say what a third party can deliver"
)
def record_third_party_recovery(request: Request, ref: str, body: CapabilityBody) -> dict[str, Any]:
    return _recovery(request, "third_party", ref, body)


# --- Continuity plans and exercises -------------------------------------------------------


class CoversBody(BaseModel):
    processes: list[str] = Field(default_factory=list, description="References of processes")


class ExerciseBody(BaseModel):
    kind: str = Field(description="tabletop, walkthrough, simulation, or full")
    held_on: str = Field(description="The day it was held")
    scenario: str = Field(max_length=20000, description="What was tried")
    participants: str | None = Field(default=None, max_length=8000)
    outcome: str = Field(max_length=20000, description="What happened")
    result: str = Field(description="met, partly, or not_met: its recovery objectives")
    achieved_hours: int | None = Field(default=None, description="How long recovery took")


class FindingBody(BaseModel):
    name: str | None = Field(default=None, max_length=400)
    summary: str | None = Field(default=None, max_length=20000)
    severity: str | None = None
    subjects: list[str] = Field(default_factory=list)
    owner_id: int | None = None


@router.get("/continuity", summary="Every continuity plan, and the processes none restores")
def continuity(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(plans.overview(session, principal))


@router.get("/continuity/{ref}", summary="A continuity plan: what it restores, whom to call")
def continuity_plan(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(plans.view(session, principal, plans.load(session, principal, ref)))


@router.put("/continuity/{ref}/covers", summary="Say which processes a plan restores")
def set_covers(request: Request, ref: str, body: CoversBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        document = plans.load(session, principal, ref)
        plans.set_covers(session, principal, document, body.processes)
        return envelope(plans.view(session, principal, document))


@router.post("/continuity/{ref}/exercises", status_code=201, summary="Record an exercise")
def record_exercise(request: Request, ref: str, body: ExerciseBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        document = plans.load(session, principal, ref)
        plans.record_exercise(session, principal, document, body.model_dump())
        return envelope(plans.view(session, principal, document))


@router.post(
    "/continuity/{ref}/exercises/{exercise_id}/issues",
    status_code=201,
    summary="Raise a finding of an exercise as an issue",
)
def raise_finding(
    request: Request, ref: str, exercise_id: int, body: FindingBody
) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        document = plans.load(session, principal, ref)
        plans.raise_finding(session, principal, document, exercise_id, body.model_dump())
        return envelope(plans.view(session, principal, document))


@router.get(
    "/continuity/{ref}/offline",
    summary="The plan in force as one file, for when the systems are down",
    response_class=Response,
)
def continuity_offline(request: Request, ref: str) -> Response:
    principal = current(request)
    with reading(request) as session:
        document = plans.load(session, principal, ref)
        data = plans.offline(session, principal, document)
        name = f"{document.ref}-continuity-plan.html"
    from riskwren.api.routers.evidence import DOWNLOAD_HEADERS

    return Response(
        data,
        media_type="text/html; charset=utf-8",
        headers={**DOWNLOAD_HEADERS, "Content-Disposition": f'attachment; filename="{name}"'},
    )
