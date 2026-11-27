"""Risk analyses: a structured assessment that walks what is in a scope against a list of
threats, and raises or refreshes risks as it goes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
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
    list_records,
    record_history,
    set_record_owners,
    show_record_plain,
    update_record,
)
from riskwren.inventory import records
from riskwren.risk import analysis
from riskwren.risk.analysis import ANALYSIS

router = APIRouter(prefix="/api/v1", tags=["risk analyses"])


class StartBody(BaseModel):
    """What to look at, and against what. Name a scope, or a unit for everything it and the
    units beneath it hold; and library risks, whole categories of them, or both."""

    name: str | None = Field(default=None, max_length=400)
    summary: str | None = Field(default=None, description="Why it is being done, and how")
    scope: str | None = Field(default=None, description="A scope's reference, such as SCP-0002")
    org_unit_id: int | None = Field(default=None, description="The unit; a scope's own if absent")
    threats: list[str] | None = Field(default=None, description="Keys of library risks")
    categories: list[str] | None = Field(default=None, description="Keys of risk categories")
    restricted: bool | None = None


class AnalysisBody(BaseModel):
    """A change to an analysis. Send only what changes, with the ``version`` you had."""

    version: int | None = None
    name: str | None = Field(default=None, max_length=400)
    summary: str | None = None
    restricted: bool | None = None
    tags: list[str] | None = None


class AnswerBody(BaseModel):
    outcome: str = Field(description="not_applicable, covered, raised, or pending to take back")
    note: str | None = Field(default=None, max_length=4000, description="Why")
    risk: str | None = Field(default=None, description="For covered: the risk's reference")
    look_again: bool = Field(default=False, description="For covered: put its rating in doubt")
    name: str | None = Field(default=None, max_length=200, description="For raised: its title")


class NoteBody(BaseModel):
    note: str | None = Field(default=None, max_length=4000)


class CloseBody(BaseModel):
    conclusion: str | None = Field(default=None, description="What the analysis found")


@router.get("/risk-analyses", summary="Find risk analyses")
def list_analyses(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    status: str | None = None,
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = SORT,
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = {"q": q, "unit": unit, "status": status, "owner": owner, "mine": mine}
    return list_records(request, ANALYSIS, filters, sort, limit, cursor)


@router.post("/risk-analyses/preview", summary="How big an analysis would be")
def preview_analysis(request: Request, body: StartBody) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(analysis.preview(session, principal, body.model_dump(exclude_none=True)))


@router.post("/risk-analyses", status_code=201, summary="Start a risk analysis")
def start_analysis(request: Request, body: StartBody) -> dict[str, Any]:
    """One question is made for each thing against each threat. Nothing is added later, so
    the analysis says what it looked at on the day it started."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        made = analysis.start(session, principal, body.model_dump(exclude_none=True))
        return envelope(records.detail(session, principal, ANALYSIS, made))


@router.get("/risk-analyses/{ref}", summary="One analysis: its progress and what it found")
def show_analysis(request: Request, ref: str) -> dict[str, Any]:
    return show_record_plain(request, ANALYSIS, ref)


@router.patch("/risk-analyses/{ref}", summary="Rename or describe an analysis")
def update_analysis(request: Request, ref: str, body: AnalysisBody) -> dict[str, Any]:
    return update_record(request, ANALYSIS, ref, body)


@router.put("/risk-analyses/{ref}/owners", summary="Set who leads an analysis")
def set_analysis_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, ANALYSIS, ref, body)


@router.get("/risk-analyses/{ref}/history", summary="Everything that happened in an analysis")
def analysis_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, ANALYSIS, ref)


@router.get(
    "/risk-analyses/{ref}/assets/{subject}",
    summary="One thing in an analysis, with each threat and what might answer it",
)
def show_asset(request: Request, ref: str, subject: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        found = records.load(session, principal, ANALYSIS, ref)
        return envelope(analysis.asset(session, principal, found, subject))


@router.post("/risk-analyses/{ref}/items/{item_id}", summary="Answer one question")
def answer_item(request: Request, ref: str, item_id: int, body: AnswerBody) -> dict[str, Any]:
    """The threat does not apply to the thing; a risk on the register covers it; or a risk
    is raised for it, started from the library with the thing as what it concerns."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        found = records.load(session, principal, ANALYSIS, ref)
        item = analysis.find_item(session, found, item_id)
        analysis.consider(session, principal, found, item, body.model_dump())
        return envelope(analysis.asset(session, principal, found, item.subject_ref))


@router.post(
    "/risk-analyses/{ref}/assets/{subject}/rest",
    summary="Say none of the unanswered threats apply to one thing",
)
def answer_rest(request: Request, ref: str, subject: str, body: NoteBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        found = records.load(session, principal, ANALYSIS, ref)
        count = analysis.rest_do_not_apply(session, principal, found, subject, body.note)
        return envelope(analysis.asset(session, principal, found, subject), answered=count)


@router.post("/risk-analyses/{ref}/close", summary="Close an analysis, with what it found")
def close_analysis(request: Request, ref: str, body: CloseBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        found = records.load(session, principal, ANALYSIS, ref)
        analysis.close(session, principal, found, body.conclusion)
        return envelope(records.detail(session, principal, ANALYSIS, found))


@router.post("/risk-analyses/{ref}/reopen", summary="Reopen a closed analysis")
def reopen_analysis(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        found = records.load(session, principal, ANALYSIS, ref)
        analysis.reopen(session, principal, found)
        return envelope(records.detail(session, principal, ANALYSIS, found))
