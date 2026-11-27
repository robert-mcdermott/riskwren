"""The risk register: the program's rules, the library, risks, and their assessments."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import envelope, reading, writing
from riskwren.api.routers.inventory import (
    LIMIT,
    MINE,
    UNIT,
    ExternalRefBody,
    OwnersBody,
    Q,
    list_records,
    record_history,
    set_record_owners,
    values_of,
)
from riskwren.core import scoring
from riskwren.inventory import records
from riskwren.program import rules
from riskwren.risk import categories, library, program, register
from riskwren.risk import method as methods
from riskwren.risk.register import RISK
from riskwren.treatment import service as treatment

router = APIRouter(prefix="/api/v1", tags=["risks"])


class RiskBody(BaseModel):
    """A risk. On a change, send only what changes, with the ``version`` you were editing."""

    version: int | None = None
    name: str | None = Field(default=None, max_length=400, description="A short title")
    summary: str | None = None
    cause: str | None = None
    event: str | None = None
    consequence: str | None = None
    category: str | None = Field(default=None, description="The key of a risk category")
    org_unit_id: int | None = None
    status: str | None = None
    closed_reason: str | None = None
    tags: list[str] | None = None
    restricted: bool | None = None
    library_key: str | None = Field(
        default=None, description="The library entry it was started from"
    )
    external_refs: list[ExternalRefBody] | None = None


class AssessmentBody(BaseModel):
    kind: str = Field(description="inherent, residual, or target")
    likelihood: int
    impact_levels: dict[str, int | None] = Field(
        description="The level chosen on each impact dimension that applies"
    )
    rationale: str


class SubjectsBody(BaseModel):
    subjects: list[str] = Field(description="References of the records the risk concerns")


class ObjectivesBody(BaseModel):
    objectives: list[str] = Field(description="References of the objectives the risk threatens")


class EscalationBody(BaseModel):
    unit_id: int | None = Field(description="A unit above the risk's own; null takes it back down")
    reason: str | None = None


class CategoryBody(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    description: str | None = None
    appetite: str | None = None
    status: str | None = None
    move: str | None = Field(default=None, description="up or down, among those beside it")


def program_view(session: Any) -> dict[str, Any]:
    row = methods.current_row(session)
    method = methods.view(row)
    count = len(method["ratings"])
    for place, rating in enumerate(method["ratings"], 1):
        rating["ramp_level"] = scoring.ramp_level(place, count)
    return {
        "method": method,
        "categories": categories.Tree(session).view(),
        "cadences": rules.get(session, "cadences"),
        "authority": rules.get(session, "authority"),
    }


@router.get("/program", summary="How risks are rated: the method, the categories, and the rules")
def show_program(request: Request) -> dict[str, Any]:
    with reading(request) as session:
        return envelope(program_view(session))


@router.patch("/risk-categories/{key}", summary="Rename a risk category or change its appetite")
def update_category(request: Request, key: str, body: CategoryBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        category = categories.by_key(session, key)
        values = body.model_dump(exclude_unset=True)
        if values.pop("move", None):
            categories.move(session, principal, category, str(body.move))
        categories.update(session, principal, category, values)
        changed = register.refresh_category(session, category.id)
        return envelope(program_view(session)["categories"], risks_whose_standing_changed=changed)


class NewCategoryBody(BaseModel):
    name: str = Field(max_length=200)
    key: str | None = Field(default=None, description="Made from the name if absent")
    parent: str | None = Field(default=None, description="The key of the category above it")
    description: str | None = None
    appetite: str | None = Field(default=None, description="A rating; needed at the top")


@router.post("/risk-categories", status_code=201, summary="Add a risk category")
def add_category(request: Request, body: NewCategoryBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        categories.create(session, principal, body.model_dump())
        return envelope(program_view(session)["categories"])


class ProgramChange(BaseModel):
    """A change to what moves risks. Send only the parts that change, each of them whole."""

    method: dict[str, Any] | None = Field(default=None, description="The whole scoring method")
    appetites: dict[str, str | None] | None = Field(
        default=None, description="Category key to rating; null takes the one above"
    )
    cadences: dict[str, Any] | None = Field(default=None, description="The whole cadence table")


@router.post("/program/preview", summary="See which risks a change to the program would move")
def preview_program(request: Request, body: ProgramChange) -> dict[str, Any]:
    """Makes the change, lists every open risk whose rating, standing, or next review moved,
    and then undoes it. Nothing is changed, and what is listed is exactly what publishing
    the same change would move."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        found = program.change(session, principal, body.model_dump(exclude_none=True))
        session.rollback()
        return envelope(found, preview=True)


@router.post("/program/publish", summary="Change the scoring method, appetite, or cadences")
def publish_program(request: Request, body: ProgramChange) -> dict[str, Any]:
    """A changed scoring method is published as a new version. Every open risk is read again
    under what is now in force; assessments keep the rating they were given."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        found = program.change(session, principal, body.model_dump(exclude_none=True))
        return envelope({**found, "program": program_view(session)}, preview=False)


@router.get("/risk-library", summary="Reusable risk statements to start a risk from")
def show_library(
    request: Request,
    q: str | None = Q,
    category: str | None = None,
    key: str | None = Query(default=None, description="One entry, by its key"),
) -> dict[str, Any]:
    with reading(request) as session:
        if key is not None:
            return envelope([library.view(library.by_key(session, key), categories.Tree(session))])
        return envelope(library.search(session, query=q, category=category))


@router.get("/risks", summary="Find risks")
def list_risks(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    at: int | None = Query(
        default=None, description="A unit's id: its own risks and those escalated to it"
    ),
    category: str | None = Query(
        default=None, description="A category key; includes those beneath"
    ),
    status: str | None = None,
    standing: str | None = None,
    residual_rating: str | None = None,
    inherent_rating: str | None = None,
    response: str | None = None,
    subject: str | None = Query(default=None, description="The reference of a record it concerns"),
    above_appetite: bool = False,
    overdue: bool = Query(default=False, description="Open risks whose review date has passed"),
    in_doubt: bool = False,
    added: str | None = Query(default=None, description="Raised in a period: FROM..TO"),
    inherent_likelihood: int | None = None,
    inherent_impact: int | None = None,
    residual_likelihood: int | None = None,
    residual_impact: int | None = None,
    target_likelihood: int | None = None,
    target_impact: int | None = None,
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = Query(default="-residual_rating", description="A field; start with - to reverse"),
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = {
        "q": q, "unit": unit, "at": at, "category": category, "status": status,
        "standing": standing, "residual_rating": residual_rating,
        "inherent_rating": inherent_rating, "response": response, "subject": subject,
        "above_appetite": above_appetite, "overdue": overdue, "in_doubt": in_doubt,
        "added": added,
        "inherent_likelihood": inherent_likelihood, "inherent_impact": inherent_impact,
        "residual_likelihood": residual_likelihood, "residual_impact": residual_impact,
        "target_likelihood": target_likelihood, "target_impact": target_impact,
        "owner": owner, "mine": mine,
    }  # fmt: skip
    treatment.catch_up(request.app.state.db)
    return list_records(request, RISK, filters, sort, limit, cursor)


@router.post("/risks", status_code=201, summary="Raise a risk")
def create_risk(request: Request, body: RiskBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        risk = register.create(session, principal, values_of(body))
        return envelope(records.detail(session, principal, RISK, risk))


@router.get("/risks/{ref}", summary="One risk, with its ratings and what it concerns")
def show_risk(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    treatment.catch_up(request.app.state.db)
    with reading(request) as session:
        risk = records.load(session, principal, RISK, ref)
        return envelope(records.detail(session, principal, RISK, risk))


@router.patch("/risks/{ref}", summary="Change a risk, close it, or reopen it")
def update_risk(request: Request, ref: str, body: RiskBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        risk = records.load(session, principal, RISK, ref)
        register.update(session, principal, risk, values_of(body), version=body.version)
        return envelope(records.detail(session, principal, RISK, risk))


@router.put("/risks/{ref}/owners", summary="Set a risk's owners")
def set_risk_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, RISK, ref, body)


@router.get("/risks/{ref}/history", summary="Everything that has happened to a risk")
def risk_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, RISK, ref)


@router.get("/risks/{ref}/assessments", summary="Every judgment made of a risk, newest first")
def list_assessments(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        risk = records.load(session, principal, RISK, ref)
        return envelope(
            register.assessments(session, risk), suggestion=register.suggestion(session, risk)
        )


@router.post("/risks/{ref}/assessments", status_code=201, summary="Assess a risk")
def assess_risk(request: Request, ref: str, body: AssessmentBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        risk = records.load(session, principal, RISK, ref)
        register.assess(
            session, principal, risk, kind=body.kind, likelihood=body.likelihood,
            impact_levels=body.impact_levels, rationale=body.rationale,
        )  # fmt: skip
        return envelope(records.detail(session, principal, RISK, risk))


@router.put("/risks/{ref}/subjects", summary="Say what a risk concerns")
def set_risk_subjects(request: Request, ref: str, body: SubjectsBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        risk = records.load(session, principal, RISK, ref)
        register.set_subjects(session, principal, risk, body.subjects)
        return envelope(records.detail(session, principal, RISK, risk))


@router.put("/risks/{ref}/objectives", summary="Say which objectives a risk threatens")
def set_risk_objectives(request: Request, ref: str, body: ObjectivesBody) -> dict[str, Any]:
    from riskwren.risk import objectives

    principal = current(request)
    with writing(request, principal.actor) as session:
        risk = records.load(session, principal, RISK, ref)
        objectives.set_objectives(session, principal, risk, body.objectives)
        return envelope(records.detail(session, principal, RISK, risk))


@router.put("/risks/{ref}/escalation", summary="Escalate a risk to a higher unit, or take it back")
def escalate_risk(request: Request, ref: str, body: EscalationBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        risk = records.load(session, principal, RISK, ref)
        register.escalate(session, principal, risk, body.unit_id, body.reason)
        return envelope(records.detail(session, principal, RISK, risk))
