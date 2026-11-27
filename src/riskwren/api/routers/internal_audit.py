"""Internal audit: the universe, the plans, and their engagements."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import envelope, reading, writing
from riskwren.internal_audit import engagements, plans, requests, universe

router = APIRouter(prefix="/api/v1", tags=["internal audit"])


class SayBody(BaseModel):
    """What audit says about an auditable thing. Send only what changes."""

    adjustment: int | None = Field(default=None, description="Points up or down, at most 30")
    adjustment_reason: str | None = Field(default=None, max_length=4000)
    last_audited_on: date | None = Field(default=None, description="An audit before RiskWren")
    last_audit_note: str | None = Field(default=None, max_length=4000)
    left_out: bool | None = None
    left_out_reason: str | None = Field(default=None, max_length=4000)


class PlanBody(BaseModel):
    name: str = Field(max_length=400)
    starts_on: date
    ends_on: date
    summary: str | None = Field(default=None, max_length=8000)


class EngagementBody(BaseModel):
    name: str = Field(max_length=400)
    kind: str = Field(description="unit, process, system, third_party, or scope")
    key: str = Field(description="A unit's id, or the record's reference")
    reason: str = Field(max_length=8000, description="Why it is in the plan")
    planned_start: date | None = None
    planned_end: date | None = None


class NoteBody(BaseModel):
    note: str | None = Field(default=None, max_length=4000)


class ReasonBody(BaseModel):
    reason: str = Field(max_length=4000)


@router.get("/audit/universe", summary="Everything worth auditing, ranked from the register")
def show_universe(
    request: Request,
    kind: str | None = Query(default=None, description="unit, process, system, ..."),
    left_out: bool = Query(default=False, description="Those left out of the universe"),
) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(universe.universe(session, principal, kind=kind, left_out=left_out))


@router.get("/audit/universe/{kind}/{key}", summary="One auditable thing and how it ranks")
def show_entity(request: Request, kind: str, key: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(universe.one(session, principal, kind, key))


@router.put("/audit/universe/{kind}/{key}", summary="Say what audit knows about a thing")
def say_entity(request: Request, kind: str, key: str, body: SayBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        values = body.model_dump(exclude_unset=True)
        return envelope(universe.say(session, principal, kind, key, values))


@router.get("/audit/plans", summary="The audit plans, the latest period first")
def list_plans(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(plans.listing(session, principal))


@router.post("/audit/plans", status_code=201, summary="Draft a plan for a period")
def create_plan(request: Request, body: PlanBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        plan = plans.create(session, principal, body.model_dump())
        return envelope(plans.view(session, principal, plan))


@router.get("/audit/plans/{ref}", summary="A plan, with each engagement and where it stands")
def show_plan(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        plan = plans.find(session, principal, ref)
        return envelope(plans.view(session, principal, plan))


@router.post("/audit/plans/{ref}/engagements", status_code=201, summary="Plan an engagement")
def plan_engagement(request: Request, ref: str, body: EngagementBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        plan = plans.find(session, principal, ref)
        plans.add_engagement(session, principal, plan, body.model_dump())
        return envelope(plans.view(session, principal, plan))


@router.post("/audit/plans/{ref}/approve", summary="Approve a draft plan")
def approve_plan(request: Request, ref: str, body: NoteBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        plan = plans.find(session, principal, ref)
        plans.approve(session, principal, plan, body.note)
        return envelope(plans.view(session, principal, plan))


@router.post("/audit/plans/{ref}/close", summary="Close a plan whose period is over")
def close_plan(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        plan = plans.find(session, principal, ref)
        plans.close(session, principal, plan)
        return envelope(plans.view(session, principal, plan))


@router.post("/engagements/{ref}/drop", summary="Drop a planned engagement, with the reason")
def drop_engagement(request: Request, ref: str, body: ReasonBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        engagement = plans.find_engagement(session, principal, ref)
        plans.drop(session, principal, engagement, body.reason)
        return envelope(plans.engagement_view(session, engagement))


@router.post("/engagements/{ref}/restore", summary="Put a dropped engagement back in the plan")
def restore_engagement(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        engagement = plans.find_engagement(session, principal, ref)
        plans.restore(session, principal, engagement)
        return envelope(plans.engagement_view(session, engagement))


# --- Engagements and workpapers ---------------------------------------------------------------


class StartBody(BaseModel):
    lead: int = Field(description="The lead auditor's account id")
    members: list[int] = Field(default_factory=list, description="The rest of the team")
    scope_note: str | None = Field(default=None, max_length=8000, description="What it covers")


class AdvanceBody(BaseModel):
    summary: str | None = Field(default=None, max_length=20000, description="For the report")
    opinion: str | None = Field(default=None, description="effective, needs_improvement, ...")


class StepBody(BaseModel):
    title: str = Field(max_length=400)
    procedure: str | None = Field(default=None, max_length=8000, description="What is to be done")


class WorkBody(BaseModel):
    done: str = Field(max_length=20000, description="What was done")
    found: str | None = Field(default=None, max_length=20000, description="What was found")
    evidence: list[str] = Field(default_factory=list, description="References of evidence")


class ReviewBody(BaseModel):
    note: str = Field(max_length=8000)


class AnswerBody(BaseModel):
    answer: str = Field(max_length=8000)


@router.get("/auditors", summary="The auditors, who may be on an engagement's team")
def list_auditors(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(engagements.auditors(session, principal))


@router.get(
    "/engagements/{ref}", summary="An engagement; its work only for its team until reported"
)
def show_engagement(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        engagement = plans.find_engagement(session, principal, ref)
        return envelope(engagements.view(session, principal, engagement))


@router.post("/engagements/{ref}/start", summary="Start a planned engagement with its team")
def start_engagement(request: Request, ref: str, body: StartBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        engagement = plans.find_engagement(session, principal, ref)
        engagements.start(session, principal, engagement, body.model_dump())
        return envelope(engagements.view(session, principal, engagement))


@router.post("/engagements/{ref}/advance", summary="Move an engagement to its next stage")
def advance_engagement(request: Request, ref: str, body: AdvanceBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        engagement = plans.find_engagement(session, principal, ref)
        engagements.advance(session, principal, engagement, body.model_dump())
        return envelope(engagements.view(session, principal, engagement))


@router.post("/engagements/{ref}/workpapers", status_code=201, summary="Add a step of the work")
def add_workpaper(request: Request, ref: str, body: StepBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        engagement = plans.find_engagement(session, principal, ref)
        engagements.add_step(session, principal, engagement, body.model_dump())
        return envelope(engagements.view(session, principal, engagement))


@router.put("/workpapers/{paper_id}", summary="Record what was done, found, and the evidence")
def record_work(request: Request, paper_id: int, body: WorkBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        paper, engagement = engagements.find_workpaper(session, principal, paper_id)
        engagements.record_work(session, principal, paper, engagement, body.model_dump())
        return envelope(engagements.view(session, principal, engagement))


@router.post("/workpapers/{paper_id}/sign-off", summary="Sign a workpaper off")
def sign_off(request: Request, paper_id: int) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        paper, engagement = engagements.find_workpaper(session, principal, paper_id)
        engagements.sign_off(session, principal, paper, engagement)
        return envelope(engagements.view(session, principal, engagement))


@router.post("/workpapers/{paper_id}/notes", status_code=201, summary="Add a review note")
def add_review_note(request: Request, paper_id: int, body: ReviewBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        paper, engagement = engagements.find_workpaper(session, principal, paper_id)
        engagements.add_note(session, principal, paper, engagement, body.note)
        return envelope(engagements.view(session, principal, engagement))


@router.post("/review-notes/{note_id}/answer", summary="Answer a review note")
def answer_review_note(request: Request, note_id: int, body: AnswerBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        note, engagement = engagements.find_note(session, principal, note_id)
        engagements.answer_note(session, principal, note, engagement, body.answer)
        return envelope(engagements.view(session, principal, engagement))


@router.post("/review-notes/{note_id}/clear", summary="Clear an answered review note")
def clear_review_note(request: Request, note_id: int) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        note, engagement = engagements.find_note(session, principal, note_id)
        engagements.clear_note(session, principal, note, engagement)
        return envelope(engagements.view(session, principal, engagement))


# --- Requests to the audited ------------------------------------------------------------------


class AskBody(BaseModel):
    what: str = Field(max_length=8000, description="What is needed")
    assignee: int = Field(description="The account id of the person asked")
    due_on: date


class RequestAnswerBody(BaseModel):
    answer: str | None = Field(default=None, max_length=20000)
    evidence: list[str] = Field(default_factory=list, description="References of evidence")


@router.post(
    "/engagements/{ref}/requests", status_code=201, summary="Ask the audited for something"
)
def ask_for(request: Request, ref: str, body: AskBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        engagement = plans.find_engagement(session, principal, ref)
        requests.ask(session, principal, engagement, body.model_dump())
        return envelope(engagements.view(session, principal, engagement))


@router.get("/audit/requests/{request_id}", summary="A request, for the person asked or the team")
def show_request(request: Request, request_id: int) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        found, engagement = requests.find(session, principal, request_id)
        return envelope(requests.view(session, principal, found, engagement))


@router.post("/audit/requests/{request_id}/answer", summary="Answer a request, with evidence")
def answer_request(request: Request, request_id: int, body: RequestAnswerBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        found, engagement = requests.find(session, principal, request_id)
        requests.answer(session, principal, found, body.model_dump())
        return envelope(requests.view(session, principal, found, engagement))


@router.post("/audit/requests/{request_id}/accept", summary="Accept the answer to a request")
def accept_request(request: Request, request_id: int) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        found, engagement = requests.find(session, principal, request_id)
        requests.accept(session, principal, found, engagement)
        return envelope(requests.view(session, principal, found, engagement))


@router.post(
    "/audit/requests/{request_id}/return", summary="Send an answer back, with what is missing"
)
def return_request(request: Request, request_id: int, body: ReasonBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        found, engagement = requests.find(session, principal, request_id)
        requests.send_back(session, principal, found, engagement, body.reason)
        return envelope(requests.view(session, principal, found, engagement))
