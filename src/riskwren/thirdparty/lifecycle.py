"""A relationship over time (TPR-07 to TPR-10): findings followed up with the third party,
review on the cadence its tier sets and when an event calls for it, and its end.

**Review.** A third party is next due for review its tier's months after its last concluded
review, or after it was first tiered if it has never been reviewed; a tier without a cadence
is reviewed only when something calls for it. An event (an incident at the supplier, a breach
notice, a change to what it does or who owns it) calls for a review at once, and says why;
concluding a review answers the call.

**Findings.** A concern from a review becomes an issue about the third party, raised from the
review, whose actions may belong to one of its contacts. The contact has no account: the
action's owner here follows it up, and its date is chased like any other.

**Offboarding.** Ending a relationship opens a checklist. Each step is recorded by someone
who keeps the third party, with what was done; when the last is recorded, the third party and
its services are retired.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    Offboarding,
    RecordOwner,
    Service,
    ThirdParty,
    ThirdPartyContact,
    ThirdPartyReview,
    TierAssessment,
)
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.program import rules
from riskwren.thirdparty import tiering

EVENTS = {
    "incident": "An incident at the third party",
    "breach_notice": "It told us of a breach",
    "service_change": "What it does for us changed",
    "ownership": "It changed hands",
    "finding": "A finding about it",
    "other": "Something else",
}
STEPS = (
    ("access", "Access removed", "Its accounts, remote access, and badges here are removed."),
    ("information", "Information returned or destroyed",
     "What it held of ours is returned, or destroyed with a certificate to say so."),
    ("agreements", "Agreements ended", "Its agreements are closed, or say what survives them."),
    ("attestation", "Its attestation recorded",
     "It has confirmed in writing that nothing of ours is kept."),
)  # fmt: skip
SOON = 30  # days before a review is due that its keepers are told


def may_keep(session: Session, principal: Principal, third_party: ThirdParty) -> bool:
    return tiering.may_tier(session, principal, third_party)


# --- When it is next reviewed ---------------------------------------------------------------


def months_for(session: Session, tier: str | None) -> int | None:
    for each in tiering.tiers(session):
        if each["key"] == tier:
            months = each.get("review_months")
            return int(months) if months else None
    return None


def last_concluded(session: Session, third_party: ThirdParty) -> ThirdPartyReview | None:
    return session.scalars(
        select(ThirdPartyReview)
        .where(
            ThirdPartyReview.third_party_id == third_party.id,
            ThirdPartyReview.status == "concluded",
        )
        .order_by(ThirdPartyReview.concluded_at.desc())
    ).first()


def _first_tiered(session: Session, third_party: ThirdParty) -> date | None:
    first = session.scalars(
        select(TierAssessment.assessed_at)
        .where(TierAssessment.third_party_id == third_party.id)
        .order_by(TierAssessment.id)
    ).first()
    return first.date() if first else None


def schedule(session: Session, third_party: ThirdParty) -> None:
    """Work out when it is next due for review, from its tier and its last concluded review,
    or sooner if an event has called for one."""
    months = months_for(session, third_party.tier)
    last = last_concluded(session, third_party)
    since = (
        last.concluded_at.date()
        if last and last.concluded_at
        else _first_tiered(session, third_party)
    )
    due = rules.add_months(since, months) if months and since else None
    called = third_party.next_review_on if third_party.review_called else None
    if called is not None:
        due = min(due, called) if due is not None else called  # an event's call stands
    if due != third_party.next_review_on:
        third_party.next_review_on = due


def call_review(
    session: Session, principal: Principal, third_party: ThirdParty, event: str,
    note: str | None,
) -> None:  # fmt: skip
    """Something has happened that calls for a review now, whatever the cadence says."""
    if not may_keep(session, principal, third_party):
        raise PermissionDenied("A review is called for by those who keep it, or an assessor.")
    if event not in EVENTS:
        raise Invalid("No review was called for.", {"event": "Say what happened."})
    said = records.text(note)
    if not said:
        raise Invalid("No review was called for.", {"note": "Say what happened, and when."})
    why = f"{EVENTS[event]}: {said}"
    with audit.operation(session, "third_party.call_review", why=why):
        third_party.review_called = why
        third_party.next_review_on = utc_now().date()
        records.touch(session, third_party)
        session.flush()


def after_review(session: Session, review: ThirdPartyReview) -> None:
    """A concluded review answers any call for one, and sets the next by the tier."""
    third_party = session.get(ThirdParty, review.third_party_id)
    if third_party is None:
        return
    third_party.review_called = None
    schedule(session, third_party)


def due_soon(session: Session, principal: Principal) -> list[ThirdParty]:
    """The third parties this person keeps whose review is due within a month, or late."""
    if principal.account_id is None:
        return []
    horizon = date.fromordinal(utc_now().date().toordinal() + SOON)
    return list(
        session.scalars(
            select(ThirdParty)
            .join(RecordOwner, and_(RecordOwner.record_type == "third_party",
                                    RecordOwner.record_id == ThirdParty.id))
            .where(
                RecordOwner.account_id == principal.account_id,
                RecordOwner.kind.in_(access.EDITING_KINDS),
                ThirdParty.status == "active",
                ThirdParty.next_review_on.is_not(None),
                ThirdParty.next_review_on <= horizon,
            )
            .order_by(ThirdParty.next_review_on, ThirdParty.ref)
            .distinct()
        )
    )  # fmt: skip


# --- Findings -------------------------------------------------------------------------------


def raise_finding(
    session: Session, principal: Principal, review: ThirdPartyReview, values: Mapping[str, Any]
) -> Any:
    """A concern from a review, raised as an issue about the third party."""
    from riskwren.compliance import issues
    from riskwren.db.models import Issue, IssueSubject

    third_party = session.get(ThirdParty, review.third_party_id)
    assert third_party is not None
    if not may_keep(session, principal, third_party):
        raise PermissionDenied(
            "A finding is raised by those who keep the third party, or an assessor."
        )
    if review.status not in ("answered", "concluded"):
        raise Conflict("A finding is raised from answers that are in.")
    wanted = {
        "name": values.get("name"), "summary": values.get("summary"),
        "severity": values.get("severity"), "source_kind": "review",
        "org_unit_id": third_party.org_unit_id, "owner_id": values.get("owner_id"),
    }  # fmt: skip
    with audit.operation(session, "review.finding", review=review.ref):
        issue: Issue = issues.create(session, principal, wanted)
        issue.source_type, issue.source_id = "third_party_review", review.id
        session.add(IssueSubject(issue_id=issue.id, subject_type="third_party",
                                 subject_id=third_party.id))  # fmt: skip
        session.flush()
    return issue


def contact_for_action(session: Session, issue: Any, contact_id: Any) -> ThirdPartyContact:
    """A contact an issue's action may belong to: one at a third party the issue is about."""
    from riskwren.db.models import IssueSubject

    try:
        contact = session.get(ThirdPartyContact, int(contact_id))
    except (TypeError, ValueError):
        contact = None
    about = set(
        session.scalars(
            select(IssueSubject.subject_id).where(
                IssueSubject.issue_id == issue.id, IssueSubject.subject_type == "third_party"
            )
        )
    )
    if contact is None or contact.third_party_id not in about:
        raise Invalid(
            "The action was not added.",
            {"contact_id": "Choose a contact at a third party the issue is about."},
        )
    if contact.status != "active":
        raise Invalid("The action was not added.", {"contact_id": f"{contact.name} has left."})
    return contact


def contacts_for_issue(session: Session, issue: Any) -> list[dict[str, Any]]:
    from riskwren.db.models import IssueSubject

    parties = session.scalars(
        select(ThirdParty)
        .join(IssueSubject, and_(IssueSubject.subject_type == "third_party",
                                 IssueSubject.subject_id == ThirdParty.id))
        .where(IssueSubject.issue_id == issue.id)
    ).all()  # fmt: skip
    out = []
    for party in parties:
        for contact in session.scalars(
            select(ThirdPartyContact)
            .where(
                ThirdPartyContact.third_party_id == party.id, ThirdPartyContact.status == "active"
            )
            .order_by(ThirdPartyContact.name)
        ):
            out.append({"id": contact.id, "name": contact.name, "third_party": party.name})
    return out


# --- Offboarding ----------------------------------------------------------------------------


def current_offboarding(session: Session, third_party: ThirdParty) -> Offboarding | None:
    return session.scalars(
        select(Offboarding)
        .where(Offboarding.third_party_id == third_party.id)
        .order_by(Offboarding.id.desc())
    ).first()


def start(session: Session, principal: Principal, third_party: ThirdParty, reason: Any
          ) -> Offboarding:  # fmt: skip
    """End the relationship: open the checklist."""
    if not may_keep(session, principal, third_party):
        raise PermissionDenied("A relationship is ended by those who keep it, or an assessor.")
    if third_party.status != "active":
        raise Conflict("It is retired already.")
    found = current_offboarding(session, third_party)
    if found is not None and found.status == "open":
        raise Conflict("Its offboarding is under way.")
    said = records.text(reason)
    if not said:
        raise Invalid("It was not started.", {"reason": "Say why the relationship ends."})
    with audit.operation(session, "third_party.offboard", reason=said):
        row = Offboarding(
            third_party_id=third_party.id, reason=said, status="open",
            steps=[{"key": key, "label": label, "help": help_, "done_at": None, "done_by": None,
                    "note": None} for key, label, help_ in STEPS],
            started_by_name=principal.name, started_at=utc_now(),
        )  # fmt: skip
        session.add(row)
        records.touch(session, third_party)
        session.flush()
    return row


def record_step(
    session: Session, principal: Principal, third_party: ThirdParty, key: str, note: Any
) -> Offboarding:
    """Record that a step is done, with what was done. The last one retires the third party
    and its services."""
    if not may_keep(session, principal, third_party):
        raise PermissionDenied("Offboarding is recorded by those who keep it, or an assessor.")
    row = current_offboarding(session, third_party)
    if row is None or row.status != "open":
        raise Conflict("No offboarding is under way.")
    said = records.text(note)
    if not said:
        raise Invalid("The step was not recorded.", {"note": "Say what was done."})
    steps = [dict(step) for step in row.steps]
    step = next((each for each in steps if each["key"] == key), None)
    if step is None:
        raise NotFound(f"There is no step {key}.")
    if step["done_at"]:
        raise Conflict(f"{step['label']} is recorded already.")
    with audit.operation(session, "third_party.offboard_step", step=step["label"], note=said):
        step.update(done_at=utc_now().isoformat(), done_by=principal.name, note=said)
        row.steps = steps
        session.flush()
        if all(each["done_at"] for each in steps):
            row.status, row.finished_at = "done", utc_now()
            third_party.status, third_party.next_review_on = "retired", None
            for service in session.scalars(
                select(Service).where(Service.third_party_id == third_party.id,
                                      Service.status == "active")):  # fmt: skip
                service.status = "retired"
                records.touch(session, service)
        records.touch(session, third_party)
        session.flush()
    return row


def cancel(session: Session, principal: Principal, third_party: ThirdParty, note: Any) -> None:
    if not may_keep(session, principal, third_party):
        raise PermissionDenied("Offboarding is changed by those who keep it, or an assessor.")
    row = current_offboarding(session, third_party)
    if row is None or row.status != "open":
        raise Conflict("No offboarding is under way.")
    with audit.operation(session, "third_party.offboard_cancel", note=records.text(note)):
        row.status = "cancelled"
        records.touch(session, third_party)
        session.flush()


def offboarding_view(row: Offboarding | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "status": row.status, "reason": row.reason, "steps": row.steps,
        "started_by": row.started_by_name, "started_at": row.started_at,
        "finished_at": row.finished_at,
    }  # fmt: skip


def install() -> None:
    """Issues may be about a third party, as findings are."""
    from riskwren.compliance import issues
    from riskwren.inventory.registry import THIRD_PARTY

    issues.SUBJECTS.setdefault("third_party", THIRD_PARTY)
