"""Incidents: reporting, reporting without a name, and triage."""

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
    set_record_owners,
    show_record_plain,
    update_record,
)
from riskwren.events.actor import Actor
from riskwren.incidents import anonymous, reports
from riskwren.incidents.reports import INCIDENT
from riskwren.inventory import history, records

router = APIRouter(prefix="/api/v1", tags=["incidents"])


class ReportBody(BaseModel):
    """What happened, when, and where."""

    kind: str | None = Field(default=None, description="incident, near_miss, or concern")
    name: str | None = Field(default=None, max_length=400, description="What happened, in a line")
    summary: str | None = Field(default=None, max_length=20000, description="What happened")
    occurred_on: str | None = Field(default=None, description="When it happened, if known")
    location: str | None = Field(default=None, max_length=400, description="Where it happened")
    org_unit_id: int | None = Field(default=None, description="The unit it happened in")


class IncidentBody(BaseModel):
    """A correction. Send only what changes, with the ``version`` you had."""

    version: int | None = None
    kind: str | None = None
    name: str | None = Field(default=None, max_length=400)
    summary: str | None = Field(default=None, max_length=20000)
    occurred_on: str | None = None
    location: str | None = Field(default=None, max_length=400)
    tags: list[str] | None = None


class TriageBody(BaseModel):
    category: str | None = Field(
        default=None, description="From the incident_categories vocabulary"
    )
    severity: str | None = Field(default=None, description="critical, high, moderate, or low")
    org_unit_id: int | None = Field(default=None, description="Its unit, if it should move")
    subjects: list[str] = Field(default_factory=list, description="References of its records")
    handler_id: int | None = Field(default=None, description="Who handles it")


class CaseBody(BaseModel):
    restricted: bool = Field(description="True: only those named on it know it exists")
    members: list[int] = Field(
        default_factory=list, description="Accounts named on it, besides its handlers"
    )


class NoteBody(BaseModel):
    note: str | None = Field(default=None, description="How it ended")


class MessageBody(BaseModel):
    body: str = Field(max_length=20000)
    shared: bool = Field(default=True, description="Shared with the reporter, or a note")


class AnonymousSetting(BaseModel):
    open: bool


class CodeBody(BaseModel):
    code: str = Field(max_length=100, description="The follow-up code the reporter was given")


class CodeMessageBody(CodeBody):
    body: str = Field(max_length=20000)


# --- Incidents ----------------------------------------------------------------------------


@router.get("/incidents", summary="Find incidents, near misses, and concerns")
def list_incidents(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    status: str | None = Query(default=None, description="reported, handling, closed, or live"),
    kind: str | None = Query(default=None, description="incident, near_miss, or concern"),
    category: str | None = None,
    severity: str | None = None,
    about: str | None = Query(default=None, description="Those that concern this record"),
    reported: bool = Query(default=False, description="Only those I reported"),
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = SORT,
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = {
        "q": q, "unit": unit, "status": status, "kind": kind, "category": category,
        "severity": severity, "about": about, "reported_by_me": reported, "owner": owner,
        "mine": mine,
    }  # fmt: skip
    return list_records(request, INCIDENT, filters, sort, limit, cursor)


@router.post("/incidents", status_code=201, summary="Report an incident, a near miss, or a concern")
def report_incident(request: Request, body: ReportBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        incident = reports.create(session, principal, body.model_dump(exclude_unset=True))
        return envelope(records.detail(session, principal, INCIDENT, incident))


@router.get("/incidents/{ref}", summary="One incident, as much of it as you may see")
def show_incident(request: Request, ref: str) -> dict[str, Any]:
    return show_record_plain(request, INCIDENT, ref)


@router.patch("/incidents/{ref}", summary="Correct an incident")
def update_incident(request: Request, ref: str, body: IncidentBody) -> dict[str, Any]:
    return update_record(request, INCIDENT, ref, body)


@router.put("/incidents/{ref}/owners", summary="Set who handles an incident")
def set_incident_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, INCIDENT, ref, body)


def _act(request: Request, ref: str, act: Any) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        incident = records.load(session, principal, INCIDENT, ref)
        act(session, principal, incident)
        return envelope(records.detail(session, principal, INCIDENT, incident))


@router.post("/incidents/{ref}/triage", summary="Triage: category, severity, records, handler")
def triage_incident(request: Request, ref: str, body: TriageBody) -> dict[str, Any]:
    return _act(request, ref, lambda s, p, i: reports.triage(s, p, i, body.model_dump()))


@router.put("/incidents/{ref}/case", summary="Restrict an incident to those named on it")
def set_incident_case(request: Request, ref: str, body: CaseBody) -> dict[str, Any]:
    return _act(
        request, ref, lambda s, p, i: reports.set_case(s, p, i, body.restricted, body.members)
    )


@router.post("/incidents/{ref}/close", summary="Close an incident, saying how it ended")
def close_incident(request: Request, ref: str, body: NoteBody) -> dict[str, Any]:
    return _act(request, ref, lambda s, p, i: reports.close(s, p, i, body.note))


@router.post("/incidents/{ref}/reopen", summary="Reopen a closed incident")
def reopen_incident(request: Request, ref: str) -> dict[str, Any]:
    return _act(request, ref, reports.reopen)


@router.post("/incidents/{ref}/messages", status_code=201, summary="Write about an incident")
def write_about_incident(request: Request, ref: str, body: MessageBody) -> dict[str, Any]:
    return _act(request, ref, lambda s, p, i: reports.write(s, p, i, body.body, shared=body.shared))


@router.get("/incidents/{ref}/history", summary="Everything that has happened to an incident")
def incident_history(request: Request, ref: str) -> dict[str, Any]:
    """For those who see the handling: not for a reporter who sees only their report."""
    principal = current(request)
    with reading(request) as session:
        incident = records.load(session, principal, INCIDENT, ref)
        records.require_whole(session, principal, INCIDENT, incident)
        return envelope(history.for_record(session, INCIDENT, incident))


# --- Reporting without a name -------------------------------------------------------------


@router.get("/admin/anonymous-reporting", summary="Whether reporting without a name is open")
def show_anonymous_setting(request: Request) -> dict[str, Any]:
    with reading(request) as session:
        return envelope(anonymous.view_setting(session))


@router.put("/admin/anonymous-reporting", summary="Open or close reporting without a name")
def save_anonymous_setting(request: Request, body: AnonymousSetting) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        return envelope(anonymous.set_open(session, principal, body.open))


ANONYMOUS = Actor.system("Reported without a name")


@router.get("/anonymous-reports", summary="Whether a report can be made without a name (public)")
def anonymous_open(request: Request) -> dict[str, Any]:
    with reading(request) as session:
        return envelope({"open": anonymous.is_open(session)})


@router.post(
    "/anonymous-reports", status_code=201, summary="Report without a name (public, when open)"
)
def report_anonymously(request: Request, body: ReportBody) -> dict[str, Any]:
    """Nothing about who sent it is kept. The code in the answer is shown once: it is the
    only way back to the report."""
    with writing(request, ANONYMOUS) as session:
        incident, code = anonymous.report(session, body.model_dump(exclude_unset=True))
        return envelope({"ref": incident.ref, "code": code})


@router.post("/anonymous-reports/follow-up", summary="Follow up a report with its code (public)")
def follow_up_anonymous(request: Request, body: CodeBody) -> dict[str, Any]:
    with reading(request) as session:
        return envelope(anonymous.follow_up(session, body.code))


@router.post("/anonymous-reports/messages", summary="Add to a report through its code (public)")
def write_anonymously(request: Request, body: CodeMessageBody) -> dict[str, Any]:
    with writing(request, ANONYMOUS) as session:
        return envelope(anonymous.add(session, body.code, body.body))
