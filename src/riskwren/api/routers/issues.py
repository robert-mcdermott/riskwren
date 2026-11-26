"""Issues, exceptions, and notices."""

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
    OwnersBody,
    Q,
    list_records,
    record_history,
    set_record_owners,
    show_record_plain,
    update_record,
)
from riskwren.compliance import exceptions, issues
from riskwren.compliance.exceptions import EXCEPTION
from riskwren.compliance.issues import ISSUE
from riskwren.inventory import records
from riskwren.people import notices
from riskwren.treatment import service as treatment

router = APIRouter(prefix="/api/v1", tags=["issues"])


class RequirementRef(BaseModel):
    framework: str
    code: str


class IssueBody(BaseModel):
    """An issue. On a change, send only what changes, with the ``version`` you had."""

    version: int | None = None
    name: str | None = Field(default=None, max_length=400)
    summary: str | None = Field(default=None, description="What is wrong, and how it was found")
    org_unit_id: int | None = None
    severity: str | None = Field(default=None, description="critical, high, moderate, or low")
    source_kind: str | None = Field(default=None, description="From the issue_sources vocabulary")
    owner_id: int | None = Field(default=None, description="Who is to put it right")
    subjects: list[str] | None = Field(
        default=None, description="References of the controls, scopes, and risks it is about"
    )
    requirements: list[RequirementRef] | None = None
    tags: list[str] | None = None
    restricted: bool | None = None


class SubjectsBody(BaseModel):
    subjects: list[str] = Field(default_factory=list)
    requirements: list[RequirementRef] = Field(default_factory=list)


class ActionBody(BaseModel):
    title: str
    owner_id: int
    due_on: str
    detail: str | None = None


class DueBody(BaseModel):
    due_on: str
    reason: str = Field(description="Why the date is moving")


class ClosureBody(BaseModel):
    note: str = Field(description="What was done to put it right")
    root_cause: str = Field(description="From the root_causes vocabulary")
    evidence: list[str] = Field(default_factory=list, description="References of evidence items")


class ConfirmBody(BaseModel):
    confirm: bool = Field(description="True to confirm it is put right; false to send it back")
    note: str | None = None


class ReasonBody(BaseModel):
    reason: str | None = None


class ExceptionBody(BaseModel):
    """A request for an exception. Name a control, or a requirement and the scope."""

    version: int | None = None
    name: str | None = Field(default=None, max_length=400)
    control: str | None = Field(default=None, description="The control's reference")
    requirement: RequirementRef | None = None
    scope: str | None = Field(default=None, description="The scope it applies in")
    justification: str | None = None
    compensating: str | None = Field(default=None, description="What makes up for it meanwhile")
    starts_on: str | None = None
    expires_on: str | None = None
    renews: str | None = Field(default=None, description="The exception this carries on from")


class DecisionBody(BaseModel):
    approve: bool
    note: str | None = None
    expires_on: str | None = Field(default=None, description="An earlier end, when approving")


class ReadBody(BaseModel):
    ids: list[int] | None = Field(default=None, description="Omit to mark every notice read")


def _dump(body: BaseModel) -> dict[str, Any]:
    values = body.model_dump(exclude_unset=True)
    values.pop("version", None)
    return values


# --- Issues -------------------------------------------------------------------------------


@router.get("/issues", summary="Find issues")
def list_issues(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    status: str | None = Query(
        default=None, description="open, proposed, closed, cancelled, or live"
    ),
    severity: str | None = None,
    source_kind: str | None = None,
    about: str | None = Query(default=None, description="A control, scope, or risk reference"),
    overdue: bool = False,
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = Query(default="due_on", description="A field name; prefix with - for descending"),
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = {"q": q, "unit": unit, "status": status, "severity": severity,
               "source_kind": source_kind, "about": about, "overdue": overdue, "owner": owner,
               "mine": mine}  # fmt: skip
    return list_records(request, ISSUE, filters, sort, limit, cursor)


@router.post("/issues", status_code=201, summary="Raise an issue")
def create_issue(request: Request, body: IssueBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        made = issues.create(session, principal, _dump(body))
        return envelope(records.detail(session, principal, ISSUE, made))


@router.get("/issues/{ref}", summary="One issue, with its actions")
def show_issue(request: Request, ref: str) -> dict[str, Any]:
    return show_record_plain(request, ISSUE, ref)


@router.patch("/issues/{ref}", summary="Change an issue")
def update_issue(request: Request, ref: str, body: IssueBody) -> dict[str, Any]:
    return update_record(request, ISSUE, ref, body)


@router.put("/issues/{ref}/owners", summary="Say who is to put an issue right")
def set_issue_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, ISSUE, ref, body)


@router.get("/issues/{ref}/history", summary="Everything that has happened to an issue")
def issue_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, ISSUE, ref)


def _act(request: Request, ref: str, change: Any) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        issue = records.load(session, principal, ISSUE, ref)
        change(session, principal, issue)
        return envelope(records.detail(session, principal, ISSUE, issue))


@router.put("/issues/{ref}/subjects", summary="Say what an issue is about")
def set_issue_subjects(request: Request, ref: str, body: SubjectsBody) -> dict[str, Any]:
    return _act(request, ref, lambda s, p, i: issues.set_subjects(s, p, i, body.model_dump()))


@router.post("/issues/{ref}/actions", status_code=201, summary="Add an action to an issue")
def add_issue_action(request: Request, ref: str, body: ActionBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        issue = records.load(session, principal, ISSUE, ref)
        action = issues.add_action(
            session, principal, issue, title=body.title, owner_id=body.owner_id,
            due_on=body.due_on, detail=body.detail,
        )  # fmt: skip
        return envelope(treatment.action_view(session, principal, action))


@router.post("/issues/{ref}/due-date", summary="Move an issue's date, with the reason")
def move_issue_date(request: Request, ref: str, body: DueBody) -> dict[str, Any]:
    return _act(
        request, ref,
        lambda s, p, i: issues.reschedule(s, p, i, due_on=body.due_on, reason=body.reason),
    )  # fmt: skip


@router.post("/issues/{ref}/closure", summary="Propose that an issue is put right")
def propose_closure(request: Request, ref: str, body: ClosureBody) -> dict[str, Any]:
    return _act(
        request, ref,
        lambda s, p, i: issues.propose(
            s, p, i, note=body.note, root_cause=body.root_cause, evidence_refs=body.evidence
        ),
    )  # fmt: skip


@router.post("/issues/{ref}/validation", summary="Confirm an issue's closure, or send it back")
def validate_closure(request: Request, ref: str, body: ConfirmBody) -> dict[str, Any]:
    return _act(
        request, ref,
        lambda s, p, i: issues.validate(s, p, i, confirm=body.confirm, note=body.note),
    )  # fmt: skip


@router.post("/issues/{ref}/cancellation", summary="Withdraw an issue raised in error")
def cancel_issue(request: Request, ref: str, body: ReasonBody) -> dict[str, Any]:
    return _act(request, ref, lambda s, p, i: issues.cancel(s, p, i, reason=body.reason))


@router.post("/issues/{ref}/reopening", summary="Open a closed issue again")
def reopen_issue(request: Request, ref: str, body: ReasonBody) -> dict[str, Any]:
    return _act(request, ref, lambda s, p, i: issues.reopen(s, p, i, reason=body.reason))


# --- Exceptions ---------------------------------------------------------------------------


@router.get("/exceptions", summary="Find exceptions")
def list_exceptions(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    state: str | None = Query(
        default=None, description="requested, in_force, expired, refused, or withdrawn"
    ),
    scope: str | None = Query(default=None, description="A scope's reference"),
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = Query(
        default="expires_on", description="A field name; prefix with - for descending"
    ),
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = {"q": q, "unit": unit, "state": state, "scope": scope, "owner": owner, "mine": mine}
    return list_records(request, EXCEPTION, filters, sort, limit, cursor)


@router.post("/exceptions", status_code=201, summary="Ask for an exception")
def request_exception(request: Request, body: ExceptionBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        made = exceptions.request(session, principal, _dump(body))
        return envelope(records.detail(session, principal, EXCEPTION, made))


@router.get("/exceptions/{ref}", summary="One exception")
def show_exception(request: Request, ref: str) -> dict[str, Any]:
    return show_record_plain(request, EXCEPTION, ref)


@router.patch("/exceptions/{ref}", summary="Reword a request that has not been decided")
def update_exception(request: Request, ref: str, body: ExceptionBody) -> dict[str, Any]:
    return update_record(request, EXCEPTION, ref, body)


@router.get("/exceptions/{ref}/history", summary="Everything that has happened to an exception")
def exception_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, EXCEPTION, ref)


@router.post("/exceptions/{ref}/decision", summary="Approve or refuse an exception")
def decide_exception(request: Request, ref: str, body: DecisionBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        item = records.load(session, principal, EXCEPTION, ref)
        exceptions.decide(
            session, principal, item, approve=body.approve, note=body.note,
            expires_on=body.expires_on,
        )  # fmt: skip
        return envelope(records.detail(session, principal, EXCEPTION, item))


@router.post("/exceptions/{ref}/withdrawal", summary="Take back a request, or end one early")
def withdraw_exception(request: Request, ref: str, body: ReasonBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        item = records.load(session, principal, EXCEPTION, ref)
        exceptions.withdraw(session, principal, item, reason=body.reason)
        return envelope(records.detail(session, principal, EXCEPTION, item))


# --- Notices ------------------------------------------------------------------------------


@router.get("/notices", summary="What has been assigned to you or changed for you")
def list_notices(request: Request, unread: bool = False) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(
            notices.mine(session, principal, only_unread=unread),
            unread=notices.unread(session, principal),
        )


@router.get("/notices/count", summary="How many of your notices are unread")
def count_notices(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope({"unread": notices.unread(session, principal)})


@router.post("/notices/read", summary="Mark notices as read")
def read_notices(request: Request, body: ReadBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        marked = notices.mark_read(session, principal, body.ids)
        return envelope({"marked": marked, "unread": notices.unread(session, principal)})
