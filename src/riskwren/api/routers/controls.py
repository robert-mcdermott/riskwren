"""Controls: the library, what is known of each control, and the risks each bears on."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import envelope, reading, writing
from riskwren.api.routers.inventory import (
    LIMIT,
    MINE,
    SORT,
    UNIT,
    ExternalRefBody,
    OwnersBody,
    Q,
    create_record,
    list_records,
    record_history,
    set_record_owners,
    show_record_plain,
    update_record,
)
from riskwren.compliance import crosswalk
from riskwren.controls import service as controls
from riskwren.controls.service import CONTROL
from riskwren.inventory import records
from riskwren.inventory.registry import find
from riskwren.risk.register import RISK

router = APIRouter(prefix="/api/v1", tags=["controls"])


class ControlBody(BaseModel):
    """A control. On a change, send only what changes, with the ``version`` you were editing."""

    version: int | None = None
    name: str | None = Field(default=None, max_length=400, description="A short title")
    statement: str | None = Field(default=None, description="Who does what, how often")
    objective: str | None = None
    summary: str | None = None
    org_unit_id: int | None = None
    kind: str | None = None
    nature: str | None = None
    frequency: str | None = None
    is_key: bool | None = None
    status: str | None = None
    tags: list[str] | None = None
    restricted: bool | None = None
    library_key: str | None = None
    external_refs: list[ExternalRefBody] | None = None


class RatingBody(BaseModel):
    design: str = Field(description="effective, partly, ineffective, or not_assessed")
    operation: str
    note: str = Field(description="What the rating rests on")


class LinkBody(BaseModel):
    control: str = Field(description="The control's reference, such as CTL-0007")
    reduces: str = Field(description="likelihood, impact, or both")
    reliance: str = Field(description="primary or supporting")
    note: str | None = None


@router.get("/control-library", summary="Common controls in plain words, to start a control from")
def show_library(
    request: Request,
    q: str | None = Q,
    keys: str | None = Query(default=None, description="Library keys, separated by commas"),
) -> dict[str, Any]:
    with reading(request) as session:
        wanted = [key for key in keys.split(",") if key] if keys is not None else None
        return envelope(controls.library(session, query=q, keys=wanted))


@router.get("/controls", summary="Find controls")
def list_controls(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    status: str | None = None,
    kind: str | None = None,
    nature: str | None = None,
    frequency: str | None = None,
    state: str | None = Query(
        default=None, description="effective, partly, ineffective, or not_assessed"
    ),
    is_key: bool = False,
    stale: bool = Query(default=False, description="Rated, but too long ago to rely on"),
    risk: str | None = Query(default=None, description="A risk's reference: the controls on it"),
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = SORT,
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = {
        "q": q, "unit": unit, "status": status, "kind": kind, "nature": nature,
        "frequency": frequency, "state": state, "is_key": is_key, "stale": stale, "risk": risk,
        "owner": owner, "mine": mine,
    }  # fmt: skip
    return list_records(request, CONTROL, filters, sort, limit, cursor)


@router.post("/controls", status_code=201, summary="Add a control")
def create_control(request: Request, body: ControlBody) -> dict[str, Any]:
    return create_record(request, CONTROL, body)


@router.get("/controls/{ref}", summary="One control, with its rating and the risks it bears on")
def show_control(request: Request, ref: str) -> dict[str, Any]:
    return show_record_plain(request, CONTROL, ref)


@router.patch("/controls/{ref}", summary="Change a control")
def update_control(request: Request, ref: str, body: ControlBody) -> dict[str, Any]:
    return update_record(request, CONTROL, ref, body)


@router.put("/controls/{ref}/owners", summary="Set a control's owners")
def set_control_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, CONTROL, ref, body)


@router.get("/controls/{ref}/history", summary="Everything that has happened to a control")
def control_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, CONTROL, ref)


@router.get("/controls/{ref}/ratings", summary="Every rating a control has had, newest first")
def list_ratings(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        control = records.load(session, principal, CONTROL, ref)
        return envelope(controls.ratings(session, control))


@router.post("/controls/{ref}/ratings", status_code=201, summary="Rate how well a control works")
def rate_control(request: Request, ref: str, body: RatingBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        control = records.load(session, principal, CONTROL, ref)
        controls.rate(
            session, principal, control, design=body.design, operation=body.operation,
            note=body.note,
        )  # fmt: skip
        return envelope(records.detail(session, principal, CONTROL, control))


class MappingBody(BaseModel):
    framework: str = Field(description="The framework's key, such as nist-csf")
    code: str = Field(description="The requirement's code, such as PR.AA-05")
    coverage: str = Field(default="partial", description="full or partial")
    note: str | None = None


@router.get("/controls/{ref}/requirements", summary="The requirements a control helps to satisfy")
def control_requirements(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        control = records.load(session, principal, CONTROL, ref)
        return envelope(crosswalk.of_control(session, principal, control))


@router.put("/controls/{ref}/requirements", summary="Map a control to a requirement, or change how")
def map_requirement(request: Request, ref: str, body: MappingBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        control = records.load(session, principal, CONTROL, ref)
        crosswalk.map_(
            session, principal, control, framework=body.framework, code=body.code,
            coverage=body.coverage, note=body.note,
        )  # fmt: skip
        return envelope(crosswalk.of_control(session, principal, control))


@router.post(
    "/controls/{ref}/requirements/suggested",
    summary="Map a control to everything the library suggests for it",
)
def map_suggested(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        control = records.load(session, principal, CONTROL, ref)
        added = crosswalk.apply_suggestions(session, principal, control)
        return envelope(crosswalk.of_control(session, principal, control), added=added)


@router.delete(
    "/controls/{ref}/requirements/{mapping_id}", summary="Take a requirement off a control"
)
def unmap_requirement(request: Request, ref: str, mapping_id: int) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        control = records.load(session, principal, CONTROL, ref)
        crosswalk.unmap(session, principal, control, mapping_id)
        return envelope(crosswalk.of_control(session, principal, control))


@router.get("/risks/{ref}/controls", summary="The controls on a risk, and what they suggest")
def risk_controls(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        risk = records.load(session, principal, RISK, ref)
        return envelope(controls.of_risk(session, principal, risk))


@router.put("/risks/{ref}/controls", summary="Link a control to a risk, or change how it bears")
def link_control(request: Request, ref: str, body: LinkBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        risk = records.load(session, principal, RISK, ref)
        control = find(session, CONTROL, body.control)
        controls.link(
            session, principal, risk, control, reduces=body.reduces, reliance=body.reliance,
            note=body.note,
        )  # fmt: skip
        return envelope(controls.of_risk(session, principal, risk))


@router.delete("/risks/{ref}/controls/{control_ref}", summary="Take a control off a risk")
def unlink_control(request: Request, ref: str, control_ref: str) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        risk = records.load(session, principal, RISK, ref)
        control = find(session, CONTROL, control_ref)
        controls.unlink(session, principal, risk, control)
        return envelope(controls.of_risk(session, principal, risk))
