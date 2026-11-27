"""Findings and follow-up (AUD-06), and the report for the committee (AUD-09).

A finding is an issue in the one register everyone works from: raised by the engagement's
team during fieldwork or reporting, with its severity, what was found, and the manager who
answers for it. Its date follows from its severity like any other issue's. Management's action
plan is the issue's actions, each with an owner and a date. When management says it is put
right, it is internal audit, not the second line, that confirms it closed, or sends it back.

A finding is shared with management as soon as it is raised: that is how its action plan is
agreed before the report is issued. The rest of the engagement's work stays with its team.

The committee report gathers a plan's engagements with their opinions, the findings by
severity, open and closed, and the findings and actions past their date.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.compliance import issues
from riskwren.compliance.issues import ISSUE
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, PermissionDenied
from riskwren.db.models import Action, AuditPlan, Engagement, Issue, OrgUnit
from riskwren.db.models.compliance import SEVERITIES
from riskwren.events import audit
from riskwren.internal_audit import engagements, plans, universe
from riskwren.inventory import records
from riskwren.program import vocab
from riskwren.treatment import service as treatment


def _unit_of(session: Session, engagement: Engagement) -> int:
    if engagement.subject_type == "unit":
        return engagement.subject_id
    subject = session.get(universe.MODELS[engagement.subject_type], engagement.subject_id)
    return int(subject.org_unit_id)


def raise_finding(
    session: Session, principal: Principal, engagement: Engagement, values: Mapping[str, Any]
) -> Issue:
    if engagements.role_on(session, principal, engagement) is None:
        raise PermissionDenied("Only the engagement's team raises its findings.")
    if engagement.status not in ("fieldwork", "reporting"):
        raise Conflict("Findings are raised during fieldwork or reporting.")
    errors = records.Errors()
    owner = values.get("owner_id")
    if owner in (None, ""):
        errors.add("owner_id", "Name the manager who answers for putting it right.")
    if errors:
        raise Invalid("The finding was not raised.", errors)
    subjects = list(values.get("subjects") or [])
    if engagement.subject_type == "scope":
        scope = session.get(universe.MODELS["scope"], engagement.subject_id)
        subjects = [scope.ref, *subjects]
    # A finding is an issue like any other, raised on behalf of internal audit: auditors keep
    # no unit's records, so the register's own rule for who may raise one does not bind them.
    on_behalf = Principal.for_command(principal.name)
    with audit.operation(session, "engagement.finding", engagement=engagement.ref):
        issue = issues.create(
            session,
            on_behalf,
            {
                "name": values.get("name"),
                "summary": values.get("summary"),
                "severity": values.get("severity"),
                "org_unit_id": _unit_of(session, engagement),
                "source_kind": "audit",
                "subjects": list(dict.fromkeys(subjects)),
                "owner_id": owner,
            },
        )
        issue.source_type, issue.source_id = "engagement", engagement.id
        issue.created_by = principal.account_id
        session.flush()
    return issue


def of_engagement(
    session: Session, principal: Principal, engagement: Engagement
) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Issue)
        .where(Issue.source_type == "engagement", Issue.source_id == engagement.id)
        .order_by(Issue.ref)
    ).all()
    cards = records.cards(session, ISSUE, list(rows))
    return [
        {
            "ref": card["ref"],
            "name": card["name"],
            "severity": card["severity"],
            "status": card["status"],
            "due_on": card["due_on"],
            "overdue": card["overdue"],
            "progress": card.get("progress"),
        }
        for card in cards
    ]


def committee_report(session: Session, principal: Principal, plan: AuditPlan) -> dict[str, Any]:
    """A plan's engagements, the findings by severity, and what is past its date."""
    universe.require_read(principal)
    today = utc_now().date()
    labels = vocab.labels(session, "issue_severities")
    rows = session.scalars(
        select(Engagement).where(Engagement.plan_id == plan.id).order_by(Engagement.ref)
    ).all()
    facts = universe.Facts(session)
    found = session.scalars(
        select(Issue).where(
            Issue.source_type == "engagement", Issue.source_id.in_([r.id for r in rows] or [0])
        )
    ).all()
    by_engagement: dict[int, list[Issue]] = {}
    for issue in found:
        by_engagement.setdefault(issue.source_id or 0, []).append(issue)
    listed = []
    for row in rows:
        view = plans.engagement_view(session, row, facts, plan)
        mine = by_engagement.get(row.id, [])
        listed.append(
            {
                **{
                    k: view[k]
                    for k in ("ref", "name", "status", "status_label", "entity", "reported_on")
                },
                "opinion": engagements.OPINION_LABELS.get(row.opinion or ""),
                "findings": len(mine),
                "open": sum(1 for i in mine if i.status in issues.LIVE),
            }
        )
    severities = [
        {
            "key": key,
            "label": labels.get(key, key),
            "open": sum(1 for i in found if i.severity == key and i.status in issues.LIVE),
            "closed": sum(1 for i in found if i.severity == key and i.status == "closed"),
        }
        for key in SEVERITIES
    ]
    late = [i for i in found if i.status == "open" and i.due_on < today]
    actions = session.scalars(
        select(Action)
        .where(
            Action.source_type == "issue",
            Action.source_id.in_([i.id for i in found] or [0]),
            Action.status.in_(treatment.OPEN),
            Action.due_on < today,
        )
        .order_by(Action.due_on)
    ).all()
    units = {u.id: u.name for u in session.execute(select(OrgUnit.id, OrgUnit.name))}
    refs = {i.id: i.ref for i in found}
    return {
        "plan": {
            "ref": plan.ref,
            "name": plan.name,
            "starts_on": plan.starts_on,
            "ends_on": plan.ends_on,
            "status": plan.status,
            "approved_by": plan.approved_by_name,
            "approved_at": plan.approved_at,
        },
        "on": today,
        "engagements": listed,
        "counts": {
            key: sum(1 for e in listed if e["status"] == key) for key in plans.STATUS_LABELS
        },
        "statuses": plans.STATUS_LABELS,
        "severities": severities,
        "late_findings": [
            {
                "ref": i.ref,
                "name": i.name,
                "severity": labels.get(i.severity, i.severity),
                "due_on": i.due_on,
                "days": (today - i.due_on).days,
                "unit": units.get(i.org_unit_id),
            }
            for i in sorted(late, key=lambda i: i.due_on)
        ],
        "late_actions": [
            {
                "ref": a.ref,
                "title": a.title,
                "due_on": a.due_on,
                "days": (today - a.due_on).days,
                "finding": refs.get(a.source_id),
            }
            for a in actions
        ],
    }
