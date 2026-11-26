"""Scopes: a boundary, what it must meet, and how each control is done inside it."""

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
    OwnersBody,
    Q,
    create_record,
    list_records,
    record_history,
    set_record_owners,
    show_record,
    update_record,
)
from riskwren.compliance import scopes
from riskwren.compliance.scopes import SCOPE
from riskwren.controls.service import CONTROL
from riskwren.inventory import records
from riskwren.inventory.registry import find

router = APIRouter(prefix="/api/v1", tags=["scopes"])


class ScopeBody(BaseModel):
    """A scope. On a change, send only what changes, with the ``version`` you were editing."""

    version: int | None = None
    name: str | None = Field(default=None, max_length=400)
    summary: str | None = None
    boundary: str | None = Field(default=None, description="Where the scope begins and ends")
    org_unit_id: int | None = None
    offers_controls: bool | None = Field(
        default=None, description="Whether other scopes may inherit its controls"
    )
    status: str | None = None
    tags: list[str] | None = None
    restricted: bool | None = None


class MembersBody(BaseModel):
    records: list[str] = Field(default_factory=list, description="References, such as SYS-0003")
    units: list[int] = Field(default_factory=list, description="Unit ids")


class HeldBody(BaseModel):
    framework: str = Field(description="The framework's key")
    baseline: str | None = Field(default=None, description="A baseline's key, to start from")


class DecisionBody(BaseModel):
    framework: str
    code: str
    applicable: bool
    reason: str | None = Field(default=None, description="Needed to leave a requirement out")


class ImplementationBody(BaseModel):
    control: str = Field(description="The control's reference, such as CTL-0007")
    status: str | None = Field(
        default=None, description="planned, partly, in_place, or not_applicable"
    )
    responsibility: str | None = Field(default=None, description="Who answers for it here")
    statement: str | None = Field(default=None, description="How it is done here")


class InheritBody(BaseModel):
    implementation: int = Field(description="The id of the implementation another scope offers")
    inheritance: str = Field(description="inherited (whole) or shared")
    status: str | None = Field(default=None, description="Where this scope's own part stands")
    responsibility: str | None = None
    statement: str | None = Field(default=None, description="What this scope does as its part")


@router.get("/scopes", summary="Find scopes")
def list_scopes(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    status: str | None = None,
    framework: str | None = Query(default=None, description="A framework's key"),
    offers: bool = Query(default=False, description="Only scopes that offer their controls"),
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = SORT,
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = {"q": q, "unit": unit, "status": status, "framework": framework,
               "offers": offers, "owner": owner, "mine": mine}  # fmt: skip
    return list_records(request, SCOPE, filters, sort, limit, cursor)


@router.post("/scopes", status_code=201, summary="Add a scope")
def create_scope(request: Request, body: ScopeBody) -> dict[str, Any]:
    return create_record(request, SCOPE, body)


@router.get("/scopes/{ref}", summary="One scope, with its boundary and what it must meet")
def show_scope(request: Request, ref: str) -> dict[str, Any]:
    return show_record(request, SCOPE, ref)


@router.patch("/scopes/{ref}", summary="Change a scope")
def update_scope(request: Request, ref: str, body: ScopeBody) -> dict[str, Any]:
    return update_record(request, SCOPE, ref, body)


@router.put("/scopes/{ref}/owners", summary="Set a scope's owners")
def set_scope_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, SCOPE, ref, body)


@router.get("/scopes/{ref}/history", summary="Everything that has happened to a scope")
def scope_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, SCOPE, ref)


@router.put("/scopes/{ref}/members", summary="Say what is inside a scope's boundary")
def set_members(request: Request, ref: str, body: MembersBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        scope = records.load(session, principal, SCOPE, ref)
        scopes.set_members(session, principal, scope, body.records, body.units)
        return envelope(records.detail(session, principal, SCOPE, scope))


@router.put(
    "/scopes/{ref}/frameworks", summary="Hold a scope to a framework, or change its baseline"
)
def hold_to(request: Request, ref: str, body: HeldBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        scope = records.load(session, principal, SCOPE, ref)
        scopes.hold_to(session, principal, scope, body.framework, body.baseline)
        return envelope(records.detail(session, principal, SCOPE, scope))


@router.delete("/scopes/{ref}/frameworks/{key}", summary="Take a framework off a scope")
def release_from(request: Request, ref: str, key: str) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        scope = records.load(session, principal, SCOPE, ref)
        scopes.release_from(session, principal, scope, key)
        return envelope(records.detail(session, principal, SCOPE, scope))


@router.get(
    "/scopes/{ref}/requirements",
    summary="A scope's statement of applicability for one framework",
)
def scope_requirements(
    request: Request,
    ref: str,
    framework: str = Query(description="The framework's key"),
    state: str | None = Query(default=None, description="gap, planned, in_place, or excluded"),
    q: str | None = None,
) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        scope = records.load(session, principal, SCOPE, ref)
        return envelope(
            scopes.statement(session, principal, scope, framework, state=state, query=q)
        )


@router.put(
    "/scopes/{ref}/requirements", summary="Say whether a requirement applies within a scope"
)
def decide(request: Request, ref: str, body: DecisionBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        scope = records.load(session, principal, SCOPE, ref)
        scopes.decide(
            session, principal, scope, framework=body.framework, code=body.code,
            applicable=body.applicable, reason=body.reason,
        )  # fmt: skip
        return envelope({"code": body.code, "applicable": body.applicable})


@router.get(
    "/scopes/{ref}/plan-of-action",
    summary="The open issues that bear on a scope, each with its milestones",
)
def scope_plan_of_action(request: Request, ref: str) -> dict[str, Any]:
    from riskwren.compliance import issues

    principal = current(request)
    with reading(request) as session:
        scope = records.load(session, principal, SCOPE, ref)
        return envelope(issues.plan_of_action(session, principal, scope))


@router.get("/scopes/{ref}/controls", summary="How each control is done within a scope")
def scope_controls(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        scope = records.load(session, principal, SCOPE, ref)
        return envelope(scopes.implementations(session, principal, scope))


@router.put("/scopes/{ref}/controls", summary="Use a control in a scope, or say where it stands")
def implement(request: Request, ref: str, body: ImplementationBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        scope = records.load(session, principal, SCOPE, ref)
        control = find(session, CONTROL, body.control)
        scopes.implement(
            session, principal, scope, control, status=body.status,
            responsibility=body.responsibility, statement=body.statement,
        )  # fmt: skip
        return envelope(scopes.implementations(session, principal, scope))


@router.get(
    "/scopes/{ref}/controls/candidates",
    summary="Controls that answer a scope's requirements and are not used in it yet",
)
def scope_candidates(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        scope = records.load(session, principal, SCOPE, ref)
        return envelope(scopes.candidates(session, principal, scope))


@router.get("/scopes/{ref}/controls/offered", summary="Controls other scopes offer to this one")
def scope_offers(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        scope = records.load(session, principal, SCOPE, ref)
        return envelope(scopes.offers(session, principal, scope))


@router.post("/scopes/{ref}/controls/inherited", summary="Inherit a control another scope offers")
def inherit(request: Request, ref: str, body: InheritBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        scope = records.load(session, principal, SCOPE, ref)
        scopes.inherit(
            session, principal, scope, body.implementation, inheritance=body.inheritance,
            status=body.status, responsibility=body.responsibility, statement=body.statement,
        )  # fmt: skip
        return envelope(scopes.implementations(session, principal, scope))


@router.delete(
    "/scopes/{ref}/controls/{implementation_id}", summary="Stop using a control in a scope"
)
def remove_implementation(request: Request, ref: str, implementation_id: int) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        scope = records.load(session, principal, SCOPE, ref)
        scopes.remove_implementation(session, principal, scope, implementation_id)
        return envelope(scopes.implementations(session, principal, scope))
