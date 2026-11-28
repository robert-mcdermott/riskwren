"""Results pushed in (INT-04): what another system says of a control.

A scanner reports that a check passed or failed; a monitoring tool sends a piece of evidence.
Each is recorded with its source, shown on the control at once, and counts for nothing until a
person who assesses the control's unit, and does not own the control, confirms it: a failure
then raises an issue, and evidence is filed with the control. Setting one aside says why. A
report never replaces a person's result, and never changes a rating or readiness by itself.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import Control, Implementation, ReportedResult, Scope
from riskwren.events import audit
from riskwren.inventory import access, records

KINDS = ("result", "evidence")
OUTCOMES = ("passed", "partial", "failed")
REPORTERS = ("manager", "assessor", "steward")  # what a token must act as to report
STATUSES = ("reported", "confirmed", "set_aside")


def _control_type() -> Any:
    from riskwren.controls.service import CONTROL  # the controls build on the inventory

    return CONTROL


def view(session: Session, row: ReportedResult) -> dict[str, Any]:
    from riskwren.db.models import Evidence, Issue

    scope = session.get(Scope, row.scope_id) if row.scope_id else None
    issue = session.get(Issue, row.issue_id) if row.issue_id else None
    item = session.get(Evidence, row.evidence_id) if row.evidence_id else None
    control = session.get(Control, row.control_id)
    return {
        "id": row.id, "kind": row.kind, "outcome": row.outcome, "title": row.title,
        "detail": row.detail, "url": row.url, "observed_at": row.observed_at,
        "source": row.source, "reported_at": row.reported_at, "status": row.status,
        "control": {"ref": control.ref, "name": control.name} if control else None,
        "scope": {"ref": scope.ref, "name": scope.name} if scope else None,
        "decided_by": row.decided_by_name, "decided_at": row.decided_at,
        "decision_note": row.decision_note,
        "issue": {"ref": issue.ref, "name": issue.name} if issue else None,
        "evidence": {"ref": item.ref, "name": item.name} if item else None,
    }  # fmt: skip


def _check(session: Session, control: Control, values: dict[str, Any]) -> tuple[dict, Any]:
    errors = records.Errors()
    kind = values.get("kind")
    if kind not in KINDS:
        errors.add("kind", f"Use one of: {', '.join(KINDS)}.")
    outcome = values.get("outcome")
    if kind == "result" and outcome not in OUTCOMES:
        errors.add("outcome", f"Use one of: {', '.join(OUTCOMES)}.")
    if kind == "evidence" and outcome is not None:
        errors.add("outcome", "Evidence has no outcome.")
    title = records.text(values.get("title"))
    if not title or len(title) > 300:
        errors.add("title", "Say what was checked, in up to 300 characters.")
    detail = records.text(values.get("detail"))
    if detail and len(detail) > 4000:
        errors.add("detail", "Keep the detail to 4,000 characters.")
    url = records.url(values.get("url"), "url", errors, max_length=500)
    observed: datetime | None = None
    raw = values.get("observed_at")
    try:
        observed = datetime.fromisoformat(str(raw)) if raw else utc_now()
        if observed.tzinfo is None:
            raise ValueError
    except ValueError:
        errors.add("observed_at", "Give when it was observed, with its time zone.")
    if observed is not None and observed > utc_now() + timedelta(minutes=5):
        errors.add("observed_at", "That is in the future.")
    scope = None
    if values.get("scope"):
        scope = session.scalars(select(Scope).where(Scope.ref == values["scope"])).first()
        held = (
            scope is not None
            and session.scalars(
                select(Implementation.id).where(
                    Implementation.scope_id == scope.id, Implementation.control_id == control.id
                )
            ).first()
        )
        if not held:
            errors.add("scope", "Name a scope that uses this control.")
    if errors:
        raise Invalid("The report was not recorded.", errors)
    return {"kind": kind, "outcome": outcome, "title": title, "detail": detail, "url": url,
            "observed_at": observed}, scope  # fmt: skip


def report(
    session: Session, principal: Principal, control: Control, values: dict[str, Any]
) -> ReportedResult:
    """Record what another system says of a control. Only a token reports: a person records
    a result in an assessment, with a second pair of eyes."""
    if principal.token_id is None:
        raise PermissionDenied("Other systems report here, with a token. A person records a "
                               "result in an assessment.")  # fmt: skip
    if not any(principal.has(role) for role in REPORTERS):
        raise PermissionDenied("A token that reports acts as a manager, an assessor, or a steward.")
    if not access.can_see(session, principal, _control_type(), control):
        raise NotFound(f"There is no control {control.ref}.")
    clean, scope = _check(session, control, values)
    now = utc_now()
    row = ReportedResult(control_id=control.id, scope_id=scope.id if scope else None,
                         source=principal.name.removeprefix("API token ")[:120], reported_at=now,
                         status="reported", **clean)  # fmt: skip
    with audit.operation(session, "control.reported", source=row.source):
        session.add(row)
        session.flush()
    return row


def of_control(session: Session, principal: Principal, control: Control) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(ReportedResult)
        .where(ReportedResult.control_id == control.id)
        .order_by(ReportedResult.reported_at.desc(), ReportedResult.id.desc())
        .limit(50)
    ).all()
    return [view(session, row) for row in rows]


def waiting(session: Session, principal: Principal) -> list[dict[str, Any]]:
    """What waits for a person to confirm, among the controls this person assesses."""
    rows = session.scalars(
        select(ReportedResult)
        .where(ReportedResult.status == "reported")
        .order_by(ReportedResult.reported_at.desc())
        .limit(300)
    ).all()
    out = []
    for row in rows:
        control = session.get(Control, row.control_id)
        if control is not None and principal.assesses_unit(control.org_unit_id):
            out.append(view(session, row))
    return out


def load(session: Session, principal: Principal, report_id: int) -> ReportedResult:
    row = session.get(ReportedResult, report_id)
    control = session.get(Control, row.control_id) if row else None
    if (
        row is None
        or control is None
        or not access.can_see(session, principal, _control_type(), control)
    ):
        raise NotFound("There is no such report.")
    return row


def _may_decide(session: Session, principal: Principal, row: ReportedResult) -> Control:
    control = session.get(Control, row.control_id)
    assert control is not None
    if principal.person is None or not principal.assesses_unit(control.org_unit_id):
        raise PermissionDenied("An assessor or a manager for the control's unit decides this.")
    owns = access.owner_kinds(session, _control_type(), control.id, principal.person)
    if owns & set(access.EDITING_KINDS):
        raise PermissionDenied("Someone who does not own the control confirms what is said of it.")
    if row.status != "reported":
        raise Conflict("This report has been decided already.")
    return control


def confirm(
    session: Session, principal: Principal, row: ReportedResult, values: dict[str, Any]
) -> ReportedResult:
    """Confirm a report: a failure raises an issue on the control; evidence is filed with it;
    a pass is kept as confirmed."""
    from riskwren.compliance import evidence, issues

    control = _may_decide(session, principal, row)
    note = records.text(values.get("note"))
    with audit.operation(session, "control.report_confirmed", source=row.source):
        if row.kind == "result" and row.outcome in ("partial", "failed"):
            already = open_issue_for(session, control)
            if already is not None:
                # The same control found wanting again: one issue, as for failed tests.
                row.issue_id = already.id
            else:
                severity = values.get("severity") or (
                    "high" if row.outcome == "failed" else "moderate"
                )
                subjects = [control.ref] + (
                    [session.get(Scope, row.scope_id).ref] if row.scope_id else []
                )
                found = issues.create(session, principal, {
                    "name": f"{row.source}: {row.title}"[:300],
                    "summary": "\n\n".join(p for p in (row.detail, row.url) if p) or row.title,
                    "severity": severity, "org_unit_id": control.org_unit_id,
                    "source_kind": "security_test", "subjects": subjects,
                    "owner_id": values.get("owner_id")})  # fmt: skip
                row.issue_id = found.id
                if not values.get("owner_id"):
                    _to_control_owners(session, principal, found, control)
        elif row.kind == "evidence":
            until = values.get("valid_until") or (row.observed_at.date() + timedelta(days=365))
            item = records.create(session, principal, evidence.EVIDENCE, {
                "name": row.title, "kind": "link" if row.url else "note", "url": row.url,
                "note": row.detail or f"Reported by {row.source}.",
                "org_unit_id": control.org_unit_id,
                "collected_on": row.observed_at.date().isoformat(),
                "valid_until": str(until)})  # fmt: skip
            evidence.set_subjects(session, principal, item, [control.ref])
            row.evidence_id = item.id
        row.status, row.decision_note = "confirmed", note
        row.decided_by, row.decided_by_name, row.decided_at = (
            principal.person,
            principal.name,
            utc_now(),
        )
        session.flush()
    return row


def open_issue_for(session: Session, control: Control) -> Any:
    """The issue still open because this control was found wanting, by a test or by a report
    confirmed earlier, if there is one."""
    from riskwren.compliance import issues
    from riskwren.db.models import Issue

    by_test = issues.open_for_test(session, control)
    if by_test is not None:
        return by_test
    return session.scalars(
        select(Issue)
        .join(ReportedResult, ReportedResult.issue_id == Issue.id)
        .where(ReportedResult.control_id == control.id, Issue.status.in_(issues.LIVE))
        .order_by(Issue.id)
    ).first()


def _to_control_owners(
    session: Session, principal: Principal, issue: Any, control: Control
) -> None:
    """As a failed test's issue is: the control's owners put it right, and are told."""
    from riskwren.compliance import issues
    from riskwren.db.models import RecordOwner
    from riskwren.people import notices

    owners = list(
        session.scalars(
            select(RecordOwner.account_id).where(
                RecordOwner.record_type == _control_type().key,
                RecordOwner.record_id == control.id,
                RecordOwner.kind.in_(access.EDITING_KINDS),
            )
        )
    )
    if not owners:
        return  # nobody answers for the control: the confirmer keeps it
    issues._hand_to(session, issue, owners)
    notices.tell_all(
        session, owners, "issue",
        f"{issue.ref} was raised from what {control.name} was reported to show, and you own it",
        f"/issues/{issue.ref}", by=principal,
    )  # fmt: skip


def set_aside(
    session: Session, principal: Principal, row: ReportedResult, note: str | None
) -> ReportedResult:
    _may_decide(session, principal, row)
    said = records.text(note)
    if not said:
        raise Invalid("The report was not set aside.", {"note": "Say why it is set aside."})
    with audit.operation(session, "control.report_set_aside", source=row.source):
        row.status, row.decision_note = "set_aside", said
        row.decided_by, row.decided_by_name, row.decided_at = (
            principal.person,
            principal.name,
            utc_now(),
        )
        session.flush()
    return row
