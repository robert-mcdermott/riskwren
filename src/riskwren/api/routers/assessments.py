"""Assessments: the tests planned in each, and what they found."""

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
    list_records,
    record_history,
    set_record_owners,
    update_record,
)
from riskwren.compliance import assessments
from riskwren.compliance.assessments import ASSESSMENT
from riskwren.controls.service import CONTROL
from riskwren.inventory import records
from riskwren.inventory.registry import find

router = APIRouter(prefix="/api/v1", tags=["assessments"])


class AssessmentBody(BaseModel):
    """An assessment. On a change, send only what changes, with the ``version`` you had."""

    version: int | None = None
    name: str | None = Field(default=None, max_length=400)
    summary: str | None = None
    scope: str | None = Field(default=None, description="The scope assessed, such as SCP-0001")
    framework: str | None = Field(default=None, description="A framework the scope is held to")
    controls: list[str] | None = Field(
        default=None, description="Particular controls to test; all of the scope's own if absent"
    )
    lead_id: int | None = None
    period_start: str | None = None
    period_end: str | None = None
    approach: str | None = None
    tags: list[str] | None = None
    restricted: bool | None = None


class TestBody(BaseModel):
    procedure: str | None = None
    method: str | None = Field(default=None, description="examine, interview, or test")
    assigned_to: int | None = None


class AddTestBody(BaseModel):
    control: str = Field(description="The control's reference")


class ResultBody(BaseModel):
    design: str = Field(description="effective, partly, or ineffective")
    operation: str
    note: str = Field(description="What was found")
    sample: str | None = Field(default=None, description="What was looked at")
    evidence: list[str] = Field(default_factory=list, description="References of evidence items")


class ReviewBody(BaseModel):
    confirm: bool = Field(description="True to confirm the result; false to return it")
    note: str | None = None


def _view(session: Any, principal: Any, assessment: Any) -> dict[str, Any]:
    return {
        **records.detail(session, principal, ASSESSMENT, assessment),
        "tests_list": assessments.tests_of(session, principal, assessment),
    }


@router.get("/assessments", summary="Find assessments")
def list_assessments(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    status: str | None = None,
    scope: str | None = Query(default=None, description="A scope's reference"),
    lead: int | None = None,
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = SORT,
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = {"q": q, "unit": unit, "status": status, "scope": scope, "lead": lead,
               "owner": owner, "mine": mine}  # fmt: skip
    return list_records(request, ASSESSMENT, filters, sort, limit, cursor)


@router.post("/assessments", status_code=201, summary="Start an assessment of a scope")
def create_assessment(request: Request, body: AssessmentBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        values = body.model_dump(exclude_unset=True)
        values.pop("version", None)
        made = assessments.create(session, principal, values)
        return envelope(_view(session, principal, made))


@router.get("/assessments/{ref}", summary="One assessment, with its tests")
def show_assessment(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(
            _view(session, principal, records.load(session, principal, ASSESSMENT, ref))
        )


@router.patch("/assessments/{ref}", summary="Change an assessment")
def update_assessment(request: Request, ref: str, body: AssessmentBody) -> dict[str, Any]:
    return update_record(request, ASSESSMENT, ref, body)


@router.put("/assessments/{ref}/owners", summary="Set an assessment's owners")
def set_assessment_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, ASSESSMENT, ref, body)


@router.get("/assessments/{ref}/history", summary="Everything that has happened in an assessment")
def assessment_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, ASSESSMENT, ref)


@router.post("/assessments/{ref}/tests", status_code=201, summary="Add a control to an assessment")
def add_test(request: Request, ref: str, body: AddTestBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        assessment = records.load(session, principal, ASSESSMENT, ref)
        assessments.add_test(session, principal, assessment, find(session, CONTROL, body.control))
        return envelope(_view(session, principal, assessment))


@router.post("/assessments/{ref}/completion", summary="Close an assessment whose tests all count")
def complete(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        assessment = records.load(session, principal, ASSESSMENT, ref)
        assessments.complete(session, principal, assessment)
        return envelope(_view(session, principal, assessment))


@router.post("/assessments/{ref}/cancellation", summary="Abandon an assessment")
def cancel(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        assessment = records.load(session, principal, ASSESSMENT, ref)
        assessments.cancel(session, principal, assessment)
        return envelope(_view(session, principal, assessment))


@router.patch("/tests/{test_id}", summary="Change how a control is to be tested, or by whom")
def update_test(request: Request, test_id: int, body: TestBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        test, _ = assessments.find_test(session, principal, test_id)
        assessments.update_test(session, principal, test, body.model_dump(exclude_unset=True))
        return envelope(assessments.view_of_test(session, principal, test))


@router.delete("/tests/{test_id}", summary="Take a control out of an assessment")
def remove_test(request: Request, test_id: int) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        test, _ = assessments.find_test(session, principal, test_id)
        assessments.remove_test(session, principal, test)
        return envelope({"removed": test_id})


@router.post("/tests/{test_id}/results", status_code=201, summary="Record what a test found")
def record_result(request: Request, test_id: int, body: ResultBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        test, _ = assessments.find_test(session, principal, test_id)
        assessments.record(
            session, principal, test, design=body.design, operation=body.operation,
            note=body.note, sample=body.sample, evidence_refs=body.evidence,
        )  # fmt: skip
        return envelope(assessments.view_of_test(session, principal, test))


@router.post("/results/{result_id}/review", summary="Confirm a test result, or return it")
def review_result(request: Request, result_id: int, body: ReviewBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        result, test, _ = assessments.find_result(session, principal, result_id)
        assessments.review(session, principal, result, confirm=body.confirm, note=body.note)
        return envelope(assessments.view_of_test(session, principal, test))
