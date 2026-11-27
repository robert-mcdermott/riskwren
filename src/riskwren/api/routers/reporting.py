"""What each person owes, the heat map, and the risk dashboard."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import envelope, reading, writing
from riskwren.api.routers.inventory import UNIT
from riskwren.inventory import records
from riskwren.reporting import service as reporting
from riskwren.treatment import service as treatment

router = APIRouter(prefix="/api/v1", tags=["reporting"])


@router.get("/home", summary="What the asker owes, overdue first")
def home(request: Request) -> dict[str, Any]:
    principal = current(request)
    treatment.catch_up(request.app.state.db)
    with reading(request) as session:
        return envelope(reporting.home(session, principal))


@router.get("/heat-map", summary="Open risks counted by likelihood and impact")
def heat_map(
    request: Request,
    kind: str = Query(default="residual", description="inherent, residual, or target"),
    unit: int | None = UNIT,
    category: str | None = Query(
        default=None, description="A category key; includes those beneath"
    ),
) -> dict[str, Any]:
    principal = current(request)
    treatment.catch_up(request.app.state.db)
    with reading(request) as session:
        return envelope(
            reporting.heat_map(session, principal, kind=kind, unit=unit, category=category)
        )


@router.get(
    "/compliance",
    summary="Where compliance stands: readiness by scope, issues, evidence, and exceptions",
)
def compliance_board(request: Request, unit: int | None = UNIT) -> dict[str, Any]:
    from riskwren.reporting import compliance

    principal = current(request)
    with reading(request) as session:
        return envelope(compliance.board(session, principal, unit=unit))


@router.get("/graph/{ref}", summary="A record and what it is connected to, in groups")
def graph_around(request: Request, ref: str) -> dict[str, Any]:
    from riskwren.inventory.registry import find_any
    from riskwren.reporting import graph

    principal = current(request)
    with reading(request) as session:
        record_type, found = find_any(session, ref)
        record = records.load(session, principal, record_type, found.ref)
        return envelope(graph.around(session, principal, record_type, record))


@router.get("/history", summary="Every change, newest first, for those who read everything")
def whole_history(
    request: Request,
    actor: int | None = Query(default=None, description="An account's id"),
    about: str | None = Query(default=None, description="A record's reference"),
    kind: str | None = Query(default=None, description="A kind of record, or other"),
    since: str | None = Query(default=None, description="From this date, year-month-day"),
    until: str | None = Query(default=None, description="Up to and including this date"),
    before: int | None = Query(default=None, description="The `next` of the page before"),
) -> dict[str, Any]:
    from datetime import UTC, date, datetime, timedelta

    from riskwren.core.errors import Invalid
    from riskwren.inventory import history
    from riskwren.inventory.registry import find_any

    def day(value: str | None, field: str, *, end: bool = False) -> datetime | None:
        if not value:
            return None
        try:
            found = date.fromisoformat(value)
        except ValueError:
            raise Invalid(
                "The dates were not understood.", {field: "Give a date, as year-month-day."}
            ) from None
        moment = datetime(found.year, found.month, found.day, tzinfo=UTC)
        return moment + timedelta(days=1) if end else moment

    with reading(request) as session:
        return envelope(
            history.everywhere(
                session,
                actor=actor,
                about=find_any(session, about) if about else None,
                kind=kind or None,
                since=day(since, "since"),
                until=day(until, "until", end=True),
                before=before,
            )
        )


@router.get("/dashboard", summary="Where the register stands, each figure with its list's filters")
def dashboard(request: Request, unit: int | None = UNIT) -> dict[str, Any]:
    principal = current(request)
    treatment.catch_up(request.app.state.db)
    with reading(request) as session:
        return envelope(reporting.dashboard(session, principal, unit=unit))


@router.get("/measures", summary="Every defined measure: what it counts, its figure, and its trend")
def show_measures(request: Request) -> dict[str, Any]:
    from riskwren.insight import measures

    principal = current(request)
    with reading(request) as session:
        return envelope(measures.overview(session, principal))


@router.get(
    "/portfolio", summary="Risk and compliance by unit, category, framework, or third party"
)
def show_portfolio(
    request: Request,
    by: str = Query(default="unit", description="unit, category, framework, third_party, causes"),
    period: str = Query(default="quarter", description="quarter, half, or year"),
) -> dict[str, Any]:
    from riskwren.insight import portfolio

    principal = current(request)
    with reading(request) as session:
        return envelope(portfolio.view(session, principal, by, period))


# --- Leadership reports -------------------------------------------------------------------


FIRST_DAY = Query(default=None, alias="from", description="The first day it covers")
LAST_DAY = Query(default=None, description="The last day it covers")


class LeadershipReportBody(BaseModel):
    title: str | None = Field(default=None, max_length=400, description="Its title")
    summary: str | None = Field(
        default=None, max_length=20000, description="What the issuer has to say about it"
    )
    from_: date | None = Field(
        default=None, alias="from", description="The first day it covers; after the last report"
    )
    to: date | None = Field(default=None, description="The last day it covers; today")


@router.get("/leadership-reports", summary="The leadership reports issued, the latest first")
def leadership_reports(request: Request) -> dict[str, Any]:
    from riskwren.insight import leadership

    principal = current(request)
    with reading(request) as session:
        return envelope(leadership.listing(session, principal))


@router.get(
    "/leadership-reports/next",
    summary="The next leadership report as it stands now: not stored until it is issued",
)
def next_leadership_report(
    request: Request,
    from_: date | None = FIRST_DAY,
    to: date | None = LAST_DAY,
) -> dict[str, Any]:
    from riskwren.insight import leadership

    principal = current(request)
    treatment.catch_up(request.app.state.db)
    with reading(request) as session:
        return envelope(leadership.draft(session, principal, from_, to))


@router.post(
    "/leadership-reports",
    status_code=201,
    summary="Issue a leadership report: what it says is frozen, with its fingerprint",
)
def issue_leadership_report(request: Request, body: LeadershipReportBody) -> dict[str, Any]:
    from riskwren.insight import leadership

    principal = current(request)
    treatment.catch_up(request.app.state.db)
    with writing(request, principal.actor) as session:
        report = leadership.issue(
            session, principal, title=body.title, summary=body.summary, start=body.from_,
            end=body.to,
        )  # fmt: skip
        return envelope(leadership.view(session, principal, report.ref))


@router.get(
    "/leadership-reports/{ref}",
    summary="A leadership report as it was issued, and whether its fingerprint verifies",
)
def leadership_report(request: Request, ref: str) -> dict[str, Any]:
    from riskwren.insight import leadership

    principal = current(request)
    with reading(request) as session:
        return envelope(leadership.view(session, principal, ref.strip().upper()))


# --- As of ------------------------------------------------------------------------------------

ON_DAY = Query(default=None, alias="on", description="The day; today if left out")


@router.get(
    "/as-of", summary="A register as it stood at the end of a day, rebuilt from the history"
)
def register_as_of(
    request: Request,
    type_: str = Query(default="risk", alias="type", description="risk, control, issue, ..."),
    on: date | None = ON_DAY,
    live: bool = Query(default=True, description="Only what was open or in use then"),
) -> dict[str, Any]:
    from riskwren.insight import as_of

    principal = current(request)
    with reading(request) as session:
        return envelope(as_of.register(session, principal, type_, on, live_only=live))


@router.get(
    "/as-of/{ref}", summary="A record as it stood at the end of a day, beside how it is now"
)
def record_as_of(request: Request, ref: str, on: date | None = ON_DAY) -> dict[str, Any]:
    from riskwren.insight import as_of
    from riskwren.inventory.registry import find_any

    principal = current(request)
    with reading(request) as session:
        record_type, _ = find_any(session, ref)
        return envelope(as_of.record_view(session, principal, record_type, ref, on))
