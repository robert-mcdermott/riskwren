"""The portfolio (RPT-07, RPT-11): the register and compliance cut every way leadership asks.

By unit, by category, by framework, and by third party, over a chosen period, and issues by
root cause, source, and age, with a year of issues raised and closed month by month. As on
the dashboards, every figure is the count of a list the person may open, paired with the
filters that produce it, so a figure and the records behind it cannot disagree (RPT-04).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.compliance import scopes
from riskwren.compliance.exceptions import EXCEPTION
from riskwren.compliance.issues import AGES, ISSUE
from riskwren.compliance.scopes import SCOPE
from riskwren.core.clock import utc_now
from riskwren.db.models import Framework, OrgUnit, ScopeFramework
from riskwren.inventory import records
from riskwren.inventory.registry import THIRD_PARTY
from riskwren.program import vocab
from riskwren.reporting.service import count
from riskwren.risk import categories
from riskwren.risk.register import RISK

PERIODS = {
    "quarter": ("The last quarter", 92),
    "half": ("The last half year", 183),
    "year": ("The last year", 365),
}
VIEWS = ("unit", "category", "framework", "third_party", "causes")
READY = ("verified", "in_place")


def span(period: str) -> tuple[date, date]:
    days = PERIODS.get(period, PERIODS["quarter"])[1]
    today = utc_now().date()
    return today - timedelta(days=days), today


def as_range(start: date, end: date) -> str:
    """A period as a list filter reads it: ``2026-01-01..2026-03-31``, both days counted."""
    return f"{start.isoformat()}..{end.isoformat()}"


def parse_range(value: Any) -> tuple[date, date] | None:
    try:
        start, end = str(value).split("..", 1)
        return date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        return None


def _figure(
    session: Session, principal: Principal, record_type: Any, path: str, **filters: Any
) -> dict[str, Any]:
    return {
        "count": count(session, principal, record_type, filters),
        "path": path,
        "filters": filters,
    }


def _units(session: Session) -> list[OrgUnit]:
    """The units beneath the organization, or beneath its one root."""
    roots = session.scalars(select(OrgUnit).where(OrgUnit.parent_id.is_(None))).all()
    parent = roots[0].id if len(roots) == 1 else None
    if parent is None:
        return list(roots)
    return list(
        session.scalars(select(OrgUnit).where(OrgUnit.parent_id == parent).order_by(OrgUnit.name))
    )


def by_unit(session: Session, principal: Principal, period: str) -> dict[str, Any]:
    window = as_range(*span(period))
    rows = []
    for unit in _units(session):

        def risk(**f: Any) -> dict[str, Any]:
            return _figure(session, principal, RISK, "risks", unit=unit.id, **f)  # noqa: B023

        def issue(**f: Any) -> dict[str, Any]:
            return _figure(session, principal, ISSUE, "issues", unit=unit.id, **f)  # noqa: B023

        figures = {
            "risks": risk(status="open"),
            "above": risk(status="open", above_appetite=True),
            "decide": risk(status="open", standing="needs_decision"),
            "added": risk(added=window),
            "issues": issue(status="live"),
            "overdue": issue(status="live", overdue=True),
            "raised": issue(raised=window),
            "closed": issue(status="closed", closed=window),
            "exceptions": _figure(
                session, principal, EXCEPTION, "exceptions", unit=unit.id, state="in_force"
            ),
        }
        if any(figure["count"] for figure in figures.values()):
            rows.append({"key": str(unit.id), "label": unit.name, "figures": figures})
    return {
        "rows": rows,
        "columns": [
            ("risks", "Open risks"),
            ("above", "Above appetite"),
            ("decide", "Need a decision"),
            ("added", "Risks added"),
            ("issues", "Open issues"),
            ("overdue", "Issues overdue"),
            ("raised", "Issues raised"),
            ("closed", "Issues closed"),
            ("exceptions", "Exceptions in force"),
        ],
    }


def by_category(session: Session, principal: Principal, period: str) -> dict[str, Any]:
    window = as_range(*span(period))
    tree = categories.Tree(session)
    rows = []
    for top in (row for row in tree.rows if row.parent_id is None and row.status == "active"):

        def risk(**f: Any) -> dict[str, Any]:
            return _figure(session, principal, RISK, "risks", category=top.key, **f)  # noqa: B023

        figures = {
            "risks": risk(status="open"),
            "above": risk(status="open", above_appetite=True),
            "decide": risk(status="open", standing="needs_decision"),
            "doubt": risk(status="open", in_doubt=True),
            "overdue": risk(status="open", overdue=True),
            "added": risk(added=window),
        }
        if any(figure["count"] for figure in figures.values()):
            rows.append(
                {
                    "key": top.key,
                    "label": top.name,
                    "figures": figures,
                    "note": f"Appetite: {top.appetite}" if top.appetite else None,
                }
            )
    return {
        "rows": rows,
        "columns": [
            ("risks", "Open risks"),
            ("above", "Above appetite"),
            ("decide", "Need a decision"),
            ("doubt", "Ratings in doubt"),
            ("overdue", "Reviews overdue"),
            ("added", "Risks added"),
        ],
    }


def by_framework(session: Session, principal: Principal, period: str) -> dict[str, Any]:
    window = as_range(*span(period))
    held = session.execute(
        select(Framework, ScopeFramework.scope_id)
        .join(ScopeFramework, ScopeFramework.framework_id == Framework.id)
        .order_by(Framework.title)
    ).all()
    seen_scopes, _ = records.search(session, principal, SCOPE, {"status": "active"}, limit=200)
    visible = {scope.id: scope for scope in seen_scopes}
    frames: dict[str, dict[str, Any]] = {}
    for framework, scope_id in held:
        scope = visible.get(scope_id)
        if scope is None:
            continue
        entry = frames.setdefault(
            framework.key, {"framework": framework, "scopes": [], "applicable": 0, "ready": 0}
        )
        statement = scopes.statement(session, principal, scope, framework.key)
        entry["scopes"].append({"ref": scope.ref, "name": scope.name})
        entry["applicable"] += statement["applicable"]
        entry["ready"] += sum(statement["counts"][state] for state in READY)
    rows = []
    for key, entry in frames.items():

        def issue(**f: Any) -> dict[str, Any]:
            return _figure(session, principal, ISSUE, "issues", framework=key, **f)  # noqa: B023

        share = round(100 * entry["ready"] / entry["applicable"]) if entry["applicable"] else None
        rows.append(
            {
                "key": key,
                "label": entry["framework"].title,
                "scopes": entry["scopes"],
                "applicable": entry["applicable"],
                "ready": entry["ready"],
                "share": share,
                "figures": {
                    "issues": issue(status="live"),
                    "overdue": issue(status="live", overdue=True),
                    "raised": issue(raised=window),
                    "closed": issue(status="closed", closed=window),
                    "exceptions": _figure(
                        session, principal, EXCEPTION, "exceptions", framework=key, state="in_force"
                    ),
                },
            }
        )
    return {
        "rows": rows,
        "columns": [
            ("issues", "Open issues"),
            ("overdue", "Issues overdue"),
            ("raised", "Issues raised"),
            ("closed", "Issues closed"),
            ("exceptions", "Exceptions in force"),
        ],
    }


def by_third_party(session: Session, principal: Principal, period: str) -> dict[str, Any]:
    """The third parties with most at stake: those in the two highest tiers."""
    from riskwren.thirdparty import coverage, tiering

    window = as_range(*span(period))
    order = tiering.order(session)
    names = tiering.labels(session)
    wanted = order[:2]
    parties, _ = records.search(
        session, principal, THIRD_PARTY, {"status": "active"}, sort="tier", limit=200
    )
    stops: dict[int, int] = {}
    for found in coverage.stops(session):
        stops[found["sharing"].third_party.id] = stops.get(found["sharing"].third_party.id, 0) + 1
    rows = []
    for party in parties:
        if party.tier not in wanted:
            continue
        rows.append(
            {
                "key": party.ref,
                "label": party.name,
                "ref": party.ref,
                "note": names.get(party.tier or "", None),
                "next_review_on": party.next_review_on,
                "figures": {
                    "risks": _figure(
                        session, principal, RISK, "risks", status="open", subject=party.ref
                    ),
                    "issues": _figure(
                        session, principal, ISSUE, "issues", status="live", about=party.ref
                    ),
                    "raised": _figure(
                        session, principal, ISSUE, "issues", about=party.ref, raised=window
                    ),
                    "stops": {"count": stops.get(party.id, 0), "path": "coverage", "filters": {}},
                },
            }
        )
    return {
        "rows": rows,
        "columns": [
            ("risks", "Open risks"),
            ("issues", "Open issues"),
            ("raised", "Issues raised"),
            ("stops", "Sharing not covered"),
        ],
    }


def causes(session: Session, principal: Principal, period: str) -> dict[str, Any]:
    """Issues by why they happened, what found them, and how long they have been open, and a
    year of issues raised and closed, month by month."""
    start, end = span(period)
    window = as_range(start, end)

    def issue(**f: Any) -> dict[str, Any]:
        return _figure(session, principal, ISSUE, "issues", **f)

    causes_ = [
        {
            "key": item["key"],
            "label": item["label"],
            **issue(status="closed", closed=window, root_cause=item["key"]),
        }
        for item in vocab.get(session, "root_causes")
    ]
    sources = [
        {
            "key": item["key"],
            "label": item["label"],
            **issue(raised=window, source_kind=item["key"]),
        }
        for item in vocab.get(session, "issue_sources")
    ]
    ages = [{"key": key, "label": f"{key} days", **issue(status="live", age=key)} for key in AGES]
    months = []
    first = date(end.year, end.month, 1)
    for back in range(11, -1, -1):
        year, month = divmod(first.year * 12 + first.month - 1 - back, 12)
        begin = date(year, month + 1, 1)
        stop = date(year + (month + 1) // 12, (month + 1) % 12 + 1, 1) - timedelta(days=1)
        stop = min(stop, end)
        months.append(
            {
                "month": begin.isoformat(),
                "raised": issue(raised=as_range(begin, stop)),
                "closed": issue(status="closed", closed=as_range(begin, stop)),
            }
        )
    return {"root_causes": causes_, "sources": sources, "ages": ages, "months": months}


def view(session: Session, principal: Principal, by: str, period: str) -> dict[str, Any]:
    by = by if by in VIEWS else "unit"
    period = period if period in PERIODS else "quarter"
    start, end = span(period)
    build = {
        "unit": by_unit,
        "category": by_category,
        "framework": by_framework,
        "third_party": by_third_party,
        "causes": causes,
    }[by]
    return {
        "by": by,
        "period": period,
        "from": start,
        "to": end,
        "periods": {key: label for key, (label, _) in PERIODS.items()},
        **build(session, principal, period),
    }
