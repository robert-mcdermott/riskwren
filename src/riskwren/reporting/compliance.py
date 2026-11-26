"""The compliance dashboard: how ready each scope is, and what stands in the way (RPT-03).

Every figure is a count of records the person may see, paired with the filters of the list
that produces it, so a number can always be opened and read. Nothing here is stored: it is
worked out from the scopes, tests, evidence, issues, and exceptions as they stand today.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.compliance import scopes
from riskwren.compliance.assessments import ASSESSMENT
from riskwren.compliance.evidence import EVIDENCE
from riskwren.compliance.exceptions import EXCEPTION
from riskwren.compliance.issues import AGES, ISSUE
from riskwren.compliance.scopes import SCOPE, STATES
from riskwren.controls.service import CONTROL
from riskwren.db.models.compliance import SEVERITIES
from riskwren.inventory import records
from riskwren.inventory.registry import RecordType
from riskwren.program import vocab
from riskwren.reporting.service import count

READY = ("verified", "in_place")  # the states that count toward a scope being ready
MOST = 60  # scopes shown; beyond that the list of scopes is the place to look


def _figure(
    session: Session, principal: Principal, record_type: RecordType, **filters: Any
) -> dict[str, Any]:
    return {"count": count(session, principal, record_type, filters), "filters": filters}


def _readiness(session: Session, principal: Principal, unit: int | None) -> list[dict[str, Any]]:
    """Each scope against each framework it is held to: the count in every state."""
    asked: dict[str, Any] = {"status": "active"}
    if unit:
        asked["unit"] = unit
    rows, _ = records.search(session, principal, SCOPE, asked, sort="name", limit=MOST)
    out = []
    for scope in rows:
        open_issues = count(session, principal, ISSUE, {"status": "live", "about": scope.ref})
        for held in scopes.held_to(session, scope):
            found = scopes.statement(session, principal, scope, held["key"])
            counts = found["counts"]
            applicable = found["applicable"]
            ready = sum(counts[state] for state in READY)
            out.append(
                {
                    "scope": {"ref": scope.ref, "name": scope.name},
                    "org_unit_id": scope.org_unit_id,
                    "framework": {"key": held["key"], "title": held["title"]},
                    "counts": {key: counts[key] for key in STATES},
                    "applicable": applicable,
                    "ready": ready,
                    "share": round(100 * ready / applicable) if applicable else None,
                    "issues": open_issues,
                }
            )
    return out


def board(session: Session, principal: Principal, *, unit: int | None = None) -> dict[str, Any]:
    """Where compliance stands, for everything the person may see or for one unit and those
    beneath it."""
    within: dict[str, Any] = {"unit": unit} if unit else {}

    def figure(record_type: RecordType, **filters: Any) -> dict[str, Any]:
        return _figure(session, principal, record_type, **within, **filters)

    readiness = _readiness(session, principal, unit)
    severities = vocab.labels(session, "issue_severities")
    aging = [
        {
            "key": severity,
            "label": severities.get(severity, severity),
            "total": figure(ISSUE, status="live", severity=severity),
            "overdue": figure(ISSUE, status="live", severity=severity, overdue=True),
            "ages": [
                {"key": age, **figure(ISSUE, status="live", severity=severity, age=age)}
                for age in AGES
            ],
        }
        for severity in SEVERITIES
    ]
    sources = [
        {"key": item["key"], "label": item["label"],
         **figure(ISSUE, status="live", source_kind=item["key"])}
        for item in vocab.get(session, "issue_sources")
    ]  # fmt: skip
    worst, _ = records.search(
        session, principal, ISSUE, {**within, "status": "live", "overdue": True},
        sort="due_on", limit=8,
    )  # fmt: skip
    running, _ = records.search(
        session, principal, ASSESSMENT, {**within, "status": "in_progress"},
        sort="period_end", limit=8,
    )  # fmt: skip
    progress = records.cards(session, ASSESSMENT, list(running))
    waiting = sum(card["awaiting"] for card in progress)
    controls = {"status": "active"}
    totals = dict.fromkeys(STATES, 0)
    for row in readiness:
        for key, number in row["counts"].items():
            totals[key] += number
    return {
        "unit": unit,
        "readiness": readiness,
        "requirements": totals,
        "totals": {
            "issues_open": figure(ISSUE, status="live"),
            "issues_overdue": figure(ISSUE, status="live", overdue=True),
            "closures_waiting": figure(ISSUE, status="proposed"),
            "evidence_stale": figure(EVIDENCE, state="stale", status="active"),
            "exceptions_expiring": figure(EXCEPTION, state="expiring"),
            "exceptions_requested": figure(EXCEPTION, state="requested"),
            "controls_failing": figure(CONTROL, tested="failing", **controls),
            "results_waiting": {"count": waiting, "filters": {"status": "in_progress"}},
        },
        "issues": {"by_severity": aging, "by_source": [s for s in sources if s["count"]]},
        "worst_issues": records.cards(session, ISSUE, list(worst)),
        "evidence": [
            {"key": state, **figure(EVIDENCE, state=state, status="active")}
            for state in ("current", "expiring", "stale")
        ],
        "exceptions": [
            {"key": state, **figure(EXCEPTION, state=state)}
            for state in ("requested", "in_force", "expiring", "expired")
        ],
        "controls": {
            "total": figure(CONTROL, **controls),
            "by_test": [
                {"key": key, **figure(CONTROL, tested=key, **controls)}
                for key in ("effective", "failing", "none")
            ],
        },
        "assessments": progress,
        "ages": list(AGES),
    }
