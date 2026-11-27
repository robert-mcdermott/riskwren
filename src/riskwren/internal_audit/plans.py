"""The audit plan (AUD-02): the engagements internal audit means to carry out in a period, each
with its reason, approved by a named person, and then tracked against.

A plan is drafted by auditors. It is approved by someone with the standing to approve it:
an auditor other than the one who drafted it, recording the approval of the audit committee,
or a leader of the whole organization. After approval an engagement can still be added,
and it says so; one that will not be done is dropped with a reason, never deleted.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access import roles
from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import AuditPlan, Engagement, OrgUnit
from riskwren.db.models.audit import ENGAGEMENT_STATUSES
from riskwren.db.refs import next_ref
from riskwren.events import audit
from riskwren.internal_audit import universe
from riskwren.inventory import records

STATUS_LABELS = {
    "planned": "Planned",
    "planning": "Planning",
    "fieldwork": "Fieldwork",
    "reporting": "Reporting",
    "reported": "Reported",
    "dropped": "Dropped",
}


def _day(value: Any, field: str, errors: records.Errors, *, required: bool) -> date | None:
    if value in (None, ""):
        if required:
            errors.add(field, "Give a date.")
        return None
    try:
        return value if isinstance(value, date) else date.fromisoformat(str(value))
    except ValueError:
        errors.add(field, "Give a date, as year-month-day.")
        return None


def may_approve(principal: Principal, plan: AuditPlan) -> bool:
    if principal.leads_all or principal.everywhere(roles.LEADER):
        return True
    return universe.may_work(principal) and principal.account_id != plan.created_by


def create(session: Session, principal: Principal, values: Mapping[str, Any]) -> AuditPlan:
    universe.require_work(principal)
    errors = records.Errors()
    name = records.text(values.get("name"))
    if not name:
        errors.add("name", "Name the plan, such as “Internal audit plan, 2027”.")
    starts = _day(values.get("starts_on"), "starts_on", errors, required=True)
    ends = _day(values.get("ends_on"), "ends_on", errors, required=True)
    if starts and ends and ends <= starts:
        errors.add("ends_on", "The period must end after it starts.")
    if errors or starts is None or ends is None:
        raise Invalid("The plan was not added.", errors)
    now = utc_now()
    with audit.operation(session, "audit_plan.create"):
        plan = AuditPlan(
            ref=next_ref(session, "APL"), name=str(name), starts_on=starts, ends_on=ends,
            summary=records.text(values.get("summary")), status="draft",
            created_by=principal.account_id, created_at=now, updated_at=now,
        )  # fmt: skip
        session.add(plan)
        session.flush()
    return plan


def find(session: Session, principal: Principal, ref: str) -> AuditPlan:
    universe.require_read(principal)
    plan = session.scalars(select(AuditPlan).where(AuditPlan.ref == ref.strip().upper())).first()
    if plan is None:
        raise NotFound(f"There is no audit plan {ref}.")
    return plan


def find_engagement(session: Session, principal: Principal, ref: str) -> Engagement:
    universe.require_read(principal)
    found = session.scalars(select(Engagement).where(Engagement.ref == ref.strip().upper())).first()
    if found is None:
        raise NotFound(f"There is no engagement {ref}.")
    return found


def approve(session: Session, principal: Principal, plan: AuditPlan, note: str | None) -> None:
    if plan.status != "draft":
        raise Conflict("Only a draft plan is approved.")
    if not may_approve(principal, plan):
        raise PermissionDenied(
            "A plan is approved by an auditor other than the one who drafted it, recording "
            "the committee's approval, or by a leader of the whole organization."
        )
    if not session.scalars(select(Engagement.id).where(Engagement.plan_id == plan.id)).first():
        raise Invalid("The plan has no engagements.", {"plan": "Add what the plan will do first."})
    with audit.operation(session, "audit_plan.approve"):
        plan.status = "approved"
        plan.approved_by, plan.approved_by_name = principal.account_id, principal.name
        plan.approved_at = utc_now()
        plan.approval_note = records.text(note)
        plan.updated_at = utc_now()
        plan.version += 1


def close(session: Session, principal: Principal, plan: AuditPlan) -> None:
    universe.require_work(principal)
    if plan.status != "approved":
        raise Conflict("Only an approved plan is closed.")
    with audit.operation(session, "audit_plan.close"):
        plan.status = "closed"
        plan.updated_at = utc_now()
        plan.version += 1


def add_engagement(
    session: Session, principal: Principal, plan: AuditPlan, values: Mapping[str, Any]
) -> Engagement:
    """Plan an engagement on one auditable thing, with the reason for it."""
    universe.require_work(principal)
    if plan.status == "closed":
        raise Conflict("A closed plan takes no more engagements.")
    errors = records.Errors()
    name = records.text(values.get("name"))
    if not name:
        errors.add("name", "Name the engagement, such as “Access management”.")
    reason = records.text(values.get("reason"))
    if not reason:
        errors.add("reason", "Say why it is in the plan.")
    kind, key = str(values.get("kind") or ""), str(values.get("key") or "")
    try:
        subject = universe.find(session, kind, key)
    except NotFound as missing:
        subject = None
        errors.add("key", str(missing))
    start = _day(values.get("planned_start"), "planned_start", errors, required=False)
    end = _day(values.get("planned_end"), "planned_end", errors, required=False)
    if start and end and end < start:
        errors.add("planned_end", "It must end on or after it starts.")
    for day, field in ((start, "planned_start"), (end, "planned_end")):
        if day and not plan.starts_on <= day <= plan.ends_on:
            errors.add(field, "Keep it within the plan's period.")
    if errors or subject is None:
        raise Invalid("The engagement was not added.", errors)
    now = utc_now()
    with audit.operation(session, "engagement.plan", plan=plan.ref):
        engagement = Engagement(
            ref=next_ref(session, "AUD"), name=str(name), plan_id=plan.id, subject_type=kind,
            subject_id=subject.id, reason=reason, planned_start=start, planned_end=end,
            status="planned", created_by=principal.account_id, created_at=now, updated_at=now,
        )  # fmt: skip
        session.add(engagement)
        plan.updated_at = now
        session.flush()
    return engagement


def drop(
    session: Session, principal: Principal, engagement: Engagement, reason: str | None
) -> None:
    universe.require_work(principal)
    if engagement.status in ("reported", "dropped"):
        raise Conflict("It is already reported or dropped.")
    why = records.text(reason)
    if not why:
        raise Invalid("It was not dropped.", {"reason": "Say why it will not be done."})
    with audit.operation(session, "engagement.drop"):
        engagement.status, engagement.dropped_reason = "dropped", why
        engagement.updated_at = utc_now()
        engagement.version += 1


def restore(session: Session, principal: Principal, engagement: Engagement) -> None:
    universe.require_work(principal)
    if engagement.status != "dropped":
        raise Conflict("Only a dropped engagement is restored.")
    with audit.operation(session, "engagement.restore"):
        engagement.status, engagement.dropped_reason = "planned", None
        engagement.updated_at = utc_now()
        engagement.version += 1


def engagement_view(session: Session, row: Engagement, facts: universe.Facts | None = None,
                    plan: AuditPlan | None = None) -> dict[str, Any]:  # fmt: skip
    subject = universe.find(session, row.subject_type, _key(session, row))
    facts = facts or universe.Facts(session)
    names = {u.id: u.name for u in session.execute(select(OrgUnit.id, OrgUnit.name))}
    entity = universe.entry(facts, row.subject_type, subject, names, utc_now().date())
    late = bool(plan and plan.approved_at and row.created_at > plan.approved_at)
    return {
        "ref": row.ref,
        "name": row.name,
        "status": row.status,
        "status_label": STATUS_LABELS[row.status],
        "reason": row.reason,
        "planned_start": row.planned_start,
        "planned_end": row.planned_end,
        "dropped_reason": row.dropped_reason,
        "reported_on": row.reported_on,
        "added_after_approval": late,
        "entity": {
            key: entity[key]
            for key in (
                "kind",
                "kind_label",
                "key",
                "ref",
                "name",
                "unit",
                "score",
                "band",
                "band_label",
            )
        },
        "version": row.version,
    }


def _key(session: Session, row: Engagement) -> str:
    if row.subject_type == "unit":
        return str(row.subject_id)
    model = universe.MODELS[row.subject_type]
    return str(session.get(model, row.subject_id).ref)


def view(session: Session, principal: Principal, plan: AuditPlan) -> dict[str, Any]:
    facts = universe.Facts(session)
    rows = session.scalars(
        select(Engagement).where(Engagement.plan_id == plan.id).order_by(
            Engagement.planned_start.is_(None), Engagement.planned_start, Engagement.ref)
    ).all()  # fmt: skip
    engagements = [engagement_view(session, row, facts, plan) for row in rows]
    counts = {key: sum(1 for e in engagements if e["status"] == key) for key in ENGAGEMENT_STATUSES}
    return {
        "ref": plan.ref,
        "name": plan.name,
        "starts_on": plan.starts_on,
        "ends_on": plan.ends_on,
        "summary": plan.summary,
        "status": plan.status,
        "approved_by": plan.approved_by_name,
        "approved_at": plan.approved_at,
        "approval_note": plan.approval_note,
        "engagements": engagements,
        "counts": counts,
        "statuses": STATUS_LABELS,
        "can": {
            "work": universe.may_work(principal) and plan.status != "closed",
            "approve": plan.status == "draft" and may_approve(principal, plan),
            "close": plan.status == "approved" and universe.may_work(principal),
        },
        "version": plan.version,
    }


def listing(session: Session, principal: Principal) -> dict[str, Any]:
    universe.require_read(principal)
    plans = session.scalars(select(AuditPlan).order_by(AuditPlan.starts_on.desc())).all()
    out = []
    for plan in plans:
        statuses = session.scalars(select(Engagement.status).where(Engagement.plan_id == plan.id))
        tally: dict[str, int] = {}
        for status in statuses:
            tally[status] = tally.get(status, 0) + 1
        out.append({
            "ref": plan.ref, "name": plan.name, "starts_on": plan.starts_on,
            "ends_on": plan.ends_on, "status": plan.status, "approved_by": plan.approved_by_name,
            "approved_at": plan.approved_at, "counts": tally,
        })  # fmt: skip
    return {"plans": out, "can_add": universe.may_work(principal), "statuses": STATUS_LABELS}
