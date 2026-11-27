"""Strategic objectives and committee sessions."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import envelope, writing
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
    show_record_plain,
    update_record,
)
from riskwren.inventory import records
from riskwren.oversight import sessions
from riskwren.oversight.sessions import SESSION
from riskwren.risk import scenarios
from riskwren.risk.objectives import OBJECTIVE
from riskwren.risk.scenarios import SCENARIO

router = APIRouter(prefix="/api/v1", tags=["objectives and sessions"])


class ObjectiveBody(BaseModel):
    """An objective. On a change, send only what changes, with the ``version`` you had."""

    version: int | None = None
    name: str | None = Field(default=None, max_length=400)
    summary: str | None = None
    period: str | None = Field(default=None, max_length=200, description="Such as 2026 to 2030")
    measure: str | None = Field(default=None, description="How it is known to be met")
    status: str | None = Field(default=None, description="active, achieved, or retired")
    org_unit_id: int | None = None
    tags: list[str] | None = None
    restricted: bool | None = None


class SessionBody(BaseModel):
    """A committee session. On a change, send only what changes, with your ``version``."""

    version: int | None = None
    name: str | None = Field(default=None, max_length=400)
    summary: str | None = None
    committee: str | None = Field(default=None, max_length=200, description="Which committee")
    held_on: str | None = Field(default=None, description="The day it meets")
    attendees: str | None = None
    minutes: str | None = Field(default=None, description="In a simple Markdown")
    org_unit_id: int | None = None
    tags: list[str] | None = None
    restricted: bool | None = None


class ItemBody(BaseModel):
    record: str | None = Field(default=None, description="A record's reference")
    title: str | None = Field(default=None, max_length=400)
    note: str | None = Field(default=None, description="What the committee is asked")


class MoveBody(BaseModel):
    up: bool = Field(description="True to move it up the agenda, false to move it down")


class DecisionBody(BaseModel):
    outcome: str = Field(description="noted, approved, declined, or deferred")
    decision: str | None = Field(default=None, description="What was decided")


class NoteBody(BaseModel):
    note: str | None = Field(default=None, max_length=4000)


# --- Objectives -------------------------------------------------------------------------------


@router.get("/objectives", summary="Find objectives")
def list_objectives(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    status: str | None = Query(
        default=None, description="active, achieved, retired, or all; not retired by default"
    ),
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = Query(default="name", description=SORT.description),
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = {"q": q, "unit": unit, "status": status, "owner": owner, "mine": mine}
    return list_records(request, OBJECTIVE, filters, sort, limit, cursor)


@router.post("/objectives", status_code=201, summary="Add an objective")
def create_objective(request: Request, body: ObjectiveBody) -> dict[str, Any]:
    return create_record(request, OBJECTIVE, body)


@router.get("/objectives/{ref}", summary="One objective, with the risks that threaten it")
def show_objective(request: Request, ref: str) -> dict[str, Any]:
    return show_record_plain(request, OBJECTIVE, ref)


@router.patch("/objectives/{ref}", summary="Change an objective")
def update_objective(request: Request, ref: str, body: ObjectiveBody) -> dict[str, Any]:
    return update_record(request, OBJECTIVE, ref, body)


@router.put("/objectives/{ref}/owners", summary="Set an objective's owners")
def set_objective_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, OBJECTIVE, ref, body)


@router.get("/objectives/{ref}/history", summary="Everything that has happened to an objective")
def objective_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, OBJECTIVE, ref)


# --- Scenarios --------------------------------------------------------------------------------


class ScenarioBody(BaseModel):
    """A scenario. On a change, send only what changes, with the ``version`` you had."""

    version: int | None = None
    name: str | None = Field(default=None, max_length=400)
    summary: str | None = Field(default=None, description="What might happen, as a story")
    assumptions: str | None = None
    conclusion: str | None = None
    status: str | None = Field(default=None, description="draft, concluded, or retired")
    org_unit_id: int | None = None
    tags: list[str] | None = None
    restricted: bool | None = None


class TouchesBody(BaseModel):
    subjects: list[str] = Field(description="References of the risks and processes it touches")


@router.get("/scenarios", summary="Find scenarios")
def list_scenarios(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    status: str | None = Query(
        default=None, description="draft, concluded, retired, or all; not retired by default"
    ),
    risk: str | None = Query(default=None, description="Those that touch this risk or process"),
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = Query(default="name", description=SORT.description),
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = {"q": q, "unit": unit, "status": status, "risk": risk, "owner": owner, "mine": mine}
    return list_records(request, SCENARIO, filters, sort, limit, cursor)


@router.post("/scenarios", status_code=201, summary="Add a scenario")
def create_scenario(request: Request, body: ScenarioBody) -> dict[str, Any]:
    return create_record(request, SCENARIO, body)


@router.get("/scenarios/{ref}", summary="One scenario, with what it touches and its simulation")
def show_scenario(request: Request, ref: str) -> dict[str, Any]:
    return show_record_plain(request, SCENARIO, ref)


@router.patch("/scenarios/{ref}", summary="Change a scenario, or conclude it")
def update_scenario(request: Request, ref: str, body: ScenarioBody) -> dict[str, Any]:
    return update_record(request, SCENARIO, ref, body)


@router.put("/scenarios/{ref}/owners", summary="Set a scenario's owners")
def set_scenario_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, SCENARIO, ref, body)


@router.put("/scenarios/{ref}/subjects", summary="Say which risks and processes it touches")
def set_scenario_subjects(request: Request, ref: str, body: TouchesBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        scenario = records.load(session, principal, SCENARIO, ref)
        scenarios.set_subjects(session, principal, scenario, body.subjects)
        return envelope(records.detail(session, principal, SCENARIO, scenario))


@router.get("/scenarios/{ref}/history", summary="Everything that has happened to a scenario")
def scenario_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, SCENARIO, ref)


# --- Sessions ---------------------------------------------------------------------------------


def _act(request: Request, ref: str, act: Any) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        meeting = records.load(session, principal, SESSION, ref)
        act(session, principal, meeting)
        return envelope(records.detail(session, principal, SESSION, meeting))


@router.get("/sessions", summary="Find committee sessions")
def list_sessions(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    status: str | None = Query(default=None, description="planned, held, or cancelled"),
    when: str | None = Query(default=None, description="upcoming, or past"),
    about: str | None = Query(default=None, description="Those with this record on the agenda"),
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = Query(default="-held_on", description=SORT.description),
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = {"q": q, "unit": unit, "status": status, "when": when, "about": about,
               "owner": owner, "mine": mine}  # fmt: skip
    return list_records(request, SESSION, filters, sort, limit, cursor)


@router.post("/sessions", status_code=201, summary="Plan a committee session")
def create_session(request: Request, body: SessionBody) -> dict[str, Any]:
    return create_record(request, SESSION, body)


@router.get("/sessions/{ref}", summary="One session: its agenda, decisions, and minutes")
def show_session(request: Request, ref: str) -> dict[str, Any]:
    return show_record_plain(request, SESSION, ref)


@router.patch("/sessions/{ref}", summary="Change a session, its attendees, or its minutes")
def update_session(request: Request, ref: str, body: SessionBody) -> dict[str, Any]:
    return update_record(request, SESSION, ref, body)


@router.put("/sessions/{ref}/owners", summary="Set a session's owners")
def set_session_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, SESSION, ref, body)


@router.get("/sessions/{ref}/history", summary="Everything that has happened to a session")
def session_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, SESSION, ref)


@router.post("/sessions/{ref}/items", status_code=201, summary="Put an item on the agenda")
def add_item(request: Request, ref: str, body: ItemBody) -> dict[str, Any]:
    """A record from the register, by its reference, or a topic of its own."""
    return _act(request, ref, lambda s, p, m: sessions.add_item(s, p, m, body.model_dump()))


@router.patch("/sessions/{ref}/items/{item_id}", summary="Change an item on the agenda")
def change_item(request: Request, ref: str, item_id: int, body: ItemBody) -> dict[str, Any]:
    values = body.model_dump(exclude_unset=True)
    return _act(request, ref, lambda s, p, m: sessions.change_item(s, p, m, item_id, values))


@router.delete("/sessions/{ref}/items/{item_id}", summary="Take an item off the agenda")
def remove_item(request: Request, ref: str, item_id: int) -> dict[str, Any]:
    return _act(request, ref, lambda s, p, m: sessions.remove_item(s, p, m, item_id))


@router.post("/sessions/{ref}/items/{item_id}/move", summary="Move an item up or down")
def move_item(request: Request, ref: str, item_id: int, body: MoveBody) -> dict[str, Any]:
    return _act(request, ref, lambda s, p, m: sessions.move_item(s, p, m, item_id, body.up))


@router.post("/sessions/{ref}/items/{item_id}/decision", summary="Record what was decided")
def decide(request: Request, ref: str, item_id: int, body: DecisionBody) -> dict[str, Any]:
    """The decision shows on the record the item was about, and its owners are told."""
    return _act(
        request, ref,
        lambda s, p, m: sessions.decide(s, p, m, item_id, body.outcome, body.decision),
    )  # fmt: skip


@router.post("/sessions/{ref}/held", summary="Record that a session was held")
def mark_held(request: Request, ref: str) -> dict[str, Any]:
    return _act(request, ref, sessions.mark_held)


@router.post("/sessions/{ref}/cancel", summary="Cancel a session")
def cancel(request: Request, ref: str, body: NoteBody) -> dict[str, Any]:
    return _act(request, ref, lambda s, p, m: sessions.cancel(s, p, m, body.note))
