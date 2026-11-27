"""Measures (RPT-06): figures with definitions, and their history.

A measure is defined once, here: what it counts, among which records, and whether fewer is
better. Its figure is the length of the list it opens, worked out by the same conditions the
list uses, so a figure and the records behind it cannot disagree (RPT-04). Each person sees
the figure for the records they may see.

Every day the scheduler takes a **snapshot** of each measure for the whole organization, so
each has a trend. A snapshot is bookkeeping, not history: it is kept outside the hash chain,
and taking one again on the same day replaces it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.db.models import MeasureSnapshot
from riskwren.inventory.registry import TYPES
from riskwren.reporting import service as reporting

GROUPS = {
    "risk": "Risk",
    "treatment": "Treatment",
    "compliance": "Compliance",
    "issues": "Issues and exceptions",
    "third_parties": "Third parties",
}
TREND_DAYS = 92  # a quarter


@dataclass(frozen=True)
class Measure:
    key: str
    group: str
    label: str
    counts: str  # what it counts, in words: the definition
    record_type: str  # whose list it opens; "action" for actions
    filters: dict[str, Any] = field(default_factory=dict)
    better: str = "lower"  # lower, higher, or neither
    special: Callable[[Session, Principal], int] | None = None
    path: str | None = None  # where the list is, when it is not the record type's own


def _stops(session: Session, principal: Principal) -> int:
    from riskwren.thirdparty import coverage

    return len(coverage.all_stops(session, principal))


CATALOG: tuple[Measure, ...] = (
    Measure("risks_open", "risk", "Open risks",
            "Risks on the register that are open, of every rating.", "risk",
            {"status": "open"}, better="neither"),
    Measure("risks_above_appetite", "risk", "Risks above appetite",
            "Open risks whose residual rating is above the appetite of their category.",
            "risk", {"status": "open", "above_appetite": True}),
    Measure("risks_needing_decision", "risk", "Risks needing a decision",
            "Open risks above appetite with no plan in force and no acceptance.", "risk",
            {"status": "open", "standing": "needs_decision"}),
    Measure("risks_review_overdue", "risk", "Risk reviews overdue",
            "Open risks whose next review date has passed.", "risk",
            {"status": "open", "overdue": True}),
    Measure("risks_in_doubt", "risk", "Ratings in doubt",
            "Open risks whose controls now suggest a worse residual rating than the one on "
            "record.", "risk", {"status": "open", "in_doubt": True}),
    Measure("actions_overdue", "treatment", "Actions overdue",
            "Open actions, from plans and issues, past their date.", "action",
            {"status": "open", "overdue": True}, path="actions"),
    Measure("controls_failing", "compliance", "Controls failing a test",
            "Controls in use whose test, still in date, found them less than effective: the "
            "same figure as on the compliance dashboard.", "control",
            {"status": "active", "tested": "failing"}),
    Measure("controls_unknown", "compliance", "Controls not assessed",
            "Controls in use whose design or operation nobody has assessed: unknown counts "
            "for nothing.", "control", {"status": "active", "state": "not_assessed"}),
    Measure("evidence_stale", "compliance", "Evidence past its date",
            "Items of evidence in use past the date they hold until.", "evidence",
            {"status": "active", "state": "stale"}),
    Measure("issues_open", "issues", "Open issues",
            "Issues raised and not yet closed or cancelled.", "issue", {"status": "live"}),
    Measure("issues_overdue", "issues", "Issues overdue",
            "Open issues past the date their severity set, or the date they were moved to.",
            "issue", {"status": "live", "overdue": True}),
    Measure("issues_critical", "issues", "Critical issues open",
            "Open issues of critical severity.", "issue",
            {"status": "live", "severity": "critical"}),
    Measure("exceptions_in_force", "issues", "Exceptions in force",
            "Approved exceptions between their start and their end.", "exception",
            {"state": "in_force"}, better="neither"),
    Measure("third_parties_untiered", "third_parties", "Third parties not tiered",
            "Third parties in use with no tier.", "third_party",
            {"status": "active", "tier": "none"}),
    Measure("third_party_reviews_overdue", "third_parties", "Third-party reviews overdue",
            "Third parties in use whose next review date has passed.", "third_party",
            {"status": "active", "review": "due"}),
    Measure("coverage_stops", "third_parties", "Sharing no agreement covers",
            "Information shared with a third party, directly or through a service, that "
            "needs an agreement no agreement meets.", "third_party",
            special=_stops, path="coverage"),
)  # fmt: skip
BY_KEY = {measure.key: measure for measure in CATALOG}


def value(session: Session, principal: Principal, measure: Measure) -> int:
    """The figure, for the records this person may see."""
    if measure.special is not None:
        return measure.special(session, principal)
    if measure.record_type == "action":
        from riskwren.treatment import service as treatment

        return treatment.search_actions(session, principal, dict(measure.filters), limit=1)[1]
    return reporting.count(session, principal, TYPES[measure.record_type], measure.filters)


def _path(measure: Measure) -> str:
    if measure.path:
        return measure.path
    return TYPES[measure.record_type].path


# --- Snapshots ------------------------------------------------------------------------------


def snapshot(session: Session, day: date | None = None) -> int:
    """Take the organization's figure for every measure on a day, replacing any taken
    earlier that day. Returns how many were taken."""
    day = day or utc_now().date()
    everyone = Principal.for_command("Measures")
    figures = {measure.key: value(session, everyone, measure) for measure in CATALOG}
    session.execute(delete(MeasureSnapshot).where(MeasureSnapshot.day == day))
    now = utc_now()
    for key, figure in figures.items():
        session.add(MeasureSnapshot(day=day, measure=key, value=figure, taken_at=now))
    session.flush()
    return len(figures)


def trends(session: Session, days: int = TREND_DAYS) -> dict[str, list[dict[str, Any]]]:
    since = utc_now().date() - timedelta(days=days)
    out: dict[str, list[dict[str, Any]]] = {measure.key: [] for measure in CATALOG}
    for row in session.scalars(
        select(MeasureSnapshot).where(MeasureSnapshot.day >= since).order_by(MeasureSnapshot.day)
    ):
        if row.measure in out:
            out[row.measure].append({"day": row.day, "value": row.value})
    return out


def overview(session: Session, principal: Principal) -> dict[str, Any]:
    """Every measure: its figure for this person, its definition, the list it opens, and
    the organization's trend over the last quarter."""
    history = trends(session)
    listed = []
    for measure in CATALOG:
        points = history.get(measure.key, [])
        listed.append({
            "key": measure.key, "group": measure.group, "group_label": GROUPS[measure.group],
            "label": measure.label, "counts": measure.counts, "better": measure.better,
            "value": value(session, principal, measure),
            "path": _path(measure), "filters": measure.filters,
            "trend": points,
            "change": (points[-1]["value"] - points[0]["value"]) if len(points) > 1 else None,
        })  # fmt: skip
    return {"measures": listed, "groups": GROUPS, "days": TREND_DAYS}
