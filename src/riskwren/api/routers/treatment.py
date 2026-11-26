"""Treatment: responses, plans and their actions, and acceptance."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import clamp_limit, decode_cursor, envelope, reading, writing
from riskwren.api.routers.inventory import LIMIT, MINE, UNIT, Q, paging
from riskwren.core.errors import NotFound
from riskwren.inventory import access, records
from riskwren.risk.register import RISK
from riskwren.treatment import service as treatment

router = APIRouter(prefix="/api/v1", tags=["treatment"])


class ResponseBody(BaseModel):
    response: str = Field(description="reduce, accept, transfer, or avoid")
    rationale: str


class PlanBody(BaseModel):
    objective: str
    owner_id: int
    due_on: date
    target_rating: str | None = None


class CancelBody(BaseModel):
    reason: str


class ActionBody(BaseModel):
    title: str = Field(max_length=400)
    owner_id: int
    due_on: date
    detail: str | None = None


class ActionChange(BaseModel):
    """Send only what changes. Moving ``due_on`` needs a ``reason``."""

    status: str | None = None
    completion_note: str | None = None
    due_on: date | None = None
    reason: str | None = None
    title: str | None = Field(default=None, max_length=400)
    detail: str | None = None
    owner_id: int | None = None


class AcceptanceBody(BaseModel):
    rationale: str
    expires_on: date
    conditions: str | None = None


def _plan(session: Any, principal: Any, ref: str) -> Any:
    plan = treatment.find_plan(session, ref)
    if not access.can_see(session, principal, RISK, treatment.risk_of(session, plan)):
        raise NotFound(f"There is no treatment plan {ref}.")
    return plan


def _action(session: Any, principal: Any, ref: str) -> Any:
    action = treatment.find_action(session, ref)
    plan = session.get(treatment.TreatmentPlan, action.source_id)
    seen = plan is not None and access.can_see(
        session, principal, RISK, treatment.risk_of(session, plan)
    )
    if not seen and action.owner_id != principal.account_id:
        raise NotFound(f"There is no action {ref}.")
    return action


@router.get("/risks/{ref}/treatment", summary="What is being done about a risk")
def risk_treatment(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    treatment.catch_up(request.app.state.db)
    with reading(request) as session:
        risk = records.load(session, principal, RISK, ref)
        return envelope(treatment.of_risk(session, principal, risk))


@router.put("/risks/{ref}/response", summary="Record the response to a risk, and why")
def respond(request: Request, ref: str, body: ResponseBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        risk = records.load(session, principal, RISK, ref)
        treatment.respond(session, principal, risk, body.response, body.rationale)
        return envelope(treatment.of_risk(session, principal, risk))


@router.post("/risks/{ref}/plans", status_code=201, summary="Open a treatment plan for a risk")
def create_plan(request: Request, ref: str, body: PlanBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        risk = records.load(session, principal, RISK, ref)
        plan = treatment.create_plan(
            session, principal, risk, objective=body.objective, owner_id=body.owner_id,
            due_on=body.due_on, target_rating=body.target_rating,
        )  # fmt: skip
        return envelope(treatment.plan_view(session, principal, plan))


@router.post("/risks/{ref}/acceptances", status_code=201, summary="Accept a risk above appetite")
def accept(request: Request, ref: str, body: AcceptanceBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        risk = records.load(session, principal, RISK, ref)
        treatment.accept(
            session, principal, risk, rationale=body.rationale, expires_on=body.expires_on,
            conditions=body.conditions,
        )  # fmt: skip
        return envelope(treatment.of_risk(session, principal, risk))


@router.post("/acceptances/{acceptance_id}/withdrawal", summary="Withdraw an acceptance")
def withdraw(request: Request, acceptance_id: int, body: CancelBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        acceptance = treatment.find_acceptance(session, principal, acceptance_id)
        treatment.withdraw(session, principal, acceptance, body.reason)
        return envelope(treatment.acceptance_view(session, acceptance))


@router.get("/acceptances", summary="Acceptances of risks the asker may see")
def list_acceptances(
    request: Request,
    state: str | None = Query(default=None, description="in_force, expired, or withdrawn"),
    expiring_within: int | None = Query(default=None, ge=1, le=730, description="Days from today"),
    unit: int | None = UNIT,
    mine: bool = Query(default=False, description="Only those I gave"),
) -> dict[str, Any]:
    principal = current(request)
    filters = {"state": state, "expiring_within": expiring_within, "unit": unit, "mine": mine}
    with reading(request) as session:
        return envelope(treatment.search_acceptances(session, principal, filters))


@router.get("/plans", summary="Treatment plans for risks the asker may see")
def list_plans(
    request: Request,
    status: str | None = None,
    overdue: bool = False,
    unit: int | None = UNIT,
    mine: bool = Query(default=False, description="Only plans I own"),
) -> dict[str, Any]:
    principal = current(request)
    filters = {"status": status, "overdue": overdue, "unit": unit, "mine": mine}
    with reading(request) as session:
        return envelope(treatment.search_plans(session, principal, filters))


@router.get("/plans/{ref}", summary="One treatment plan, with its actions")
def show_plan(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(treatment.plan_view(session, principal, _plan(session, principal, ref)))


@router.post("/plans/{ref}/cancellation", summary="Cancel a treatment plan, with the reason")
def cancel_plan(request: Request, ref: str, body: CancelBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        plan = _plan(session, principal, ref)
        treatment.cancel_plan(session, principal, plan, body.reason)
        return envelope(treatment.plan_view(session, principal, plan))


@router.post("/plans/{ref}/actions", status_code=201, summary="Add an action to a plan")
def add_action(request: Request, ref: str, body: ActionBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        plan = _plan(session, principal, ref)
        treatment.add_action(
            session, principal, plan, title=body.title, owner_id=body.owner_id,
            due_on=body.due_on, detail=body.detail,
        )  # fmt: skip
        return envelope(treatment.plan_view(session, principal, plan))


@router.get("/actions", summary="Actions: one list of everything owed")
def list_actions(
    request: Request,
    q: str | None = Q,
    status: str | None = Query(default=None, description="open (not yet done), or a status"),
    overdue: bool = False,
    unit: int | None = UNIT,
    owner: int | None = None,
    mine: bool = MINE,
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    principal = current(request)
    size = clamp_limit(limit)
    offset = int((decode_cursor(cursor) or {}).get("offset", 0))
    filters = {
        "q": q, "status": status, "overdue": overdue, "unit": unit, "owner": owner, "mine": mine,
    }  # fmt: skip
    with reading(request) as session:
        rows, total = treatment.search_actions(
            session, principal, filters, limit=size, offset=offset
        )
    return envelope(rows, **paging(total, offset, size, len(rows)))


@router.patch("/actions/{ref}", summary="Progress, finish, reschedule, or reassign an action")
def update_action(request: Request, ref: str, body: ActionChange) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        action = _action(session, principal, ref)
        treatment.update_action(session, principal, action, body.model_dump(exclude_unset=True))
        return envelope(treatment.action_view(session, principal, action))
