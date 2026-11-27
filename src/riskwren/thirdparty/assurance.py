"""Assurance documents (TPR-04): what independent reports say about a third party, read for
what they actually cover.

A report or a certificate is an item of evidence on the third party, with the period it
covers and the date it holds until; past that date it stops counting, and its owners are told
beforehand, as with any evidence. A **review** of it records what a careful reader notes: the
kind of report and who issued it, the opinion, which of the third party's services it covers
and which it does not, the parts carved out to others, each exception the auditor noted and
whether it matters here, and each responsibility the report leaves to the organization (in a
SOC report, the complementary user entity controls), joined to the control here that meets
it. What the report can be relied on for is the reviewer's judgment, kept with their name.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.compliance import evidence as evidence_service
from riskwren.compliance.evidence import EVIDENCE
from riskwren.controls.service import CONTROL
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    AssuranceResponsibility,
    AssuranceReview,
    Control,
    Evidence,
    EvidenceLink,
    Service,
    ThirdParty,
)
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.registry import THIRD_PARTY
from riskwren.thirdparty import tiering
from riskwren.thirdparty.services import SERVICE

KINDS = {
    "soc2_type2": "SOC 2 Type II report",
    "soc2_type1": "SOC 2 Type I report",
    "soc1_type2": "SOC 1 Type II report",
    "iso27001": "ISO/IEC 27001 certificate",
    "hitrust": "HITRUST certification",
    "fedramp": "FedRAMP authorization",
    "pci_aoc": "PCI DSS attestation of compliance",
    "pentest": "Penetration test summary",
    "bridge_letter": "Bridge letter",
    "other": "Other report or certificate",
}
OPINIONS = {
    "unqualified": "Unqualified: the controls were as described",
    "qualified": "Qualified: with exceptions the auditor thought material",
    "adverse": "Adverse",
    "none": "No opinion is given (a certificate, or a test summary)",
}
RELIANCE = {
    "relies": "Can be relied on",
    "partly": "Can be relied on, with gaps",
    "cannot": "Cannot be relied on",
}
RESPONSIBILITY_STATES = {
    "in_place": "In place here",
    "not_in_place": "Not in place here",
    "not_applicable": "Does not apply here",
}
MAX_ROWS = 60
SOON = 60  # days before a report's expiry at which it is shown as expiring


def may_review(session: Session, principal: Principal, third_party: ThirdParty) -> bool:
    return tiering.may_tier(session, principal, third_party)


# --- Documents ------------------------------------------------------------------------------


def add(
    session: Session, principal: Principal, third_party: ThirdParty, values: Mapping[str, Any]
) -> Evidence:
    """Record a report or certificate as evidence of the third party, in its unit."""
    if not may_review(session, principal, third_party):
        raise PermissionDenied(
            "Reports are added by those who keep the third party, or by an assessor."
        )
    wanted = {
        "name": values.get("name"),
        "summary": values.get("summary"),
        "kind": "link" if values.get("url") else "file",
        "url": values.get("url"),
        "org_unit_id": third_party.org_unit_id,
        "collected_on": values.get("collected_on"),
        "covers_from": values.get("covers_from"),
        "covers_to": values.get("covers_to"),
        "valid_until": values.get("valid_until"),
        "data_class": values.get("data_class") or "confidential",
    }
    item = records.create(session, principal, EVIDENCE, wanted, checked=True)
    with audit.operation(session, "evidence.attach"):
        session.add(EvidenceLink(evidence_id=item.id, subject_type="third_party",
                                 subject_id=third_party.id))  # fmt: skip
        session.flush()
    return item


def documents_of(
    session: Session, principal: Principal, third_party: ThirdParty
) -> list[dict[str, Any]]:
    """A third party's reports and certificates, newest first, each with how it stands and
    its latest review."""
    rows = session.scalars(
        select(Evidence)
        .join(EvidenceLink, EvidenceLink.evidence_id == Evidence.id)
        .where(
            EvidenceLink.subject_type == "third_party",
            EvidenceLink.subject_id == third_party.id,
            Evidence.status == "active",
        )
        .order_by(Evidence.valid_until.desc(), Evidence.id.desc())
    ).all()
    seen = [row for row in rows if evidence_service.can_see(session, principal, row)]
    reviews = {
        row.evidence_id: row
        for row in session.scalars(
            select(AssuranceReview).where(
                AssuranceReview.evidence_id.in_([row.id for row in seen] or [0]),
                AssuranceReview.superseded_by.is_(None),
            )
        )
    }
    out = []
    for row, card in zip(seen, records.cards(session, EVIDENCE, seen), strict=True):
        review = reviews.get(row.id)
        out.append({
            **card, "covers_from": row.covers_from, "covers_to": row.covers_to,
            "review": view(session, principal, review, third_party) if review else None,
        })  # fmt: skip
    return out


def standing(session: Session, third_party: ThirdParty) -> dict[str, Any]:
    """Whether anything independent can be relied on for it now: a report still in date whose
    latest review relies on it, wholly or with gaps."""
    today = utc_now().date()
    rows = session.execute(
        select(Evidence.valid_until, AssuranceReview.reliance)
        .join(EvidenceLink, EvidenceLink.evidence_id == Evidence.id)
        .join(AssuranceReview, AssuranceReview.evidence_id == Evidence.id)
        .where(
            EvidenceLink.subject_type == "third_party",
            EvidenceLink.subject_id == third_party.id,
            Evidence.status == "active",
            AssuranceReview.superseded_by.is_(None),
            AssuranceReview.third_party_id == third_party.id,
        )
    ).all()
    current = [until for until, reliance in rows if until >= today and reliance != "cannot"]
    return {"current": len(current), "until": max(current) if current else None}


# --- Reviewing one --------------------------------------------------------------------------


def _text(value: Any, limit: int) -> str | None:
    said = records.text(value)
    return said[:limit] if said else None


def _rows(value: Any, field: str, errors: records.Errors) -> list[Mapping[str, Any]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > MAX_ROWS:
        errors.add(field, f"Give a list of up to {MAX_ROWS}.")
        return []
    if not all(isinstance(row, Mapping) for row in value):
        errors.add(field, "Each one is an object.")
        return []
    return value


def record(
    session: Session, principal: Principal, item: Evidence, third_party: ThirdParty,
    values: Mapping[str, Any],
) -> AssuranceReview:  # fmt: skip
    """Review a report: what it is, what it covers and does not, what it found, what it
    leaves to the organization, and whether it can be relied on. A later review supersedes
    this one, and both stay."""
    if not may_review(session, principal, third_party):
        raise PermissionDenied(
            "A report is reviewed by those who keep the third party, or an assessor."
        )
    linked = session.scalars(
        select(EvidenceLink.id).where(
            EvidenceLink.evidence_id == item.id,
            EvidenceLink.subject_type == "third_party",
            EvidenceLink.subject_id == third_party.id,
        )
    ).first()
    if linked is None:
        raise NotFound(f"{item.ref} is not a report on {third_party.name}.")
    errors = records.Errors()
    kind = values.get("kind")
    if kind not in KINDS:
        errors.add("kind", "Say what kind of report or certificate it is.")
    opinion = values.get("opinion") or "none"
    if opinion not in OPINIONS:
        errors.add("opinion", "Choose the opinion it gives.")
    reliance = values.get("reliance")
    if reliance not in RELIANCE:
        errors.add("reliance", "Say whether it can be relied on.")
    note = _text(values.get("note"), 8000)
    if reliance in ("partly", "cannot") and not note:
        errors.add("note", "Say what it cannot be relied on for, and why.")
    offered = {row.id: row for row in session.scalars(
        select(Service).where(Service.third_party_id == third_party.id))}  # fmt: skip
    covered: list[int] = []
    for ref in values.get("services") or []:
        found = next((row for row in offered.values() if row.ref == str(ref).upper()), None)
        if found is None:
            errors.add("services", f"{ref} is not one of {third_party.name}'s services.")
        else:
            covered.append(found.id)
    exceptions = []
    for row in _rows(values.get("exceptions"), "exceptions", errors):
        what = _text(row.get("description"), 2000)
        if not what:
            errors.add("exceptions", "Each exception says what the auditor found.")
            continue
        exceptions.append({
            "control": _text(row.get("control"), 200), "description": what,
            "matters": bool(row.get("matters")), "response": _text(row.get("response"), 2000),
        })  # fmt: skip
    duties: list[tuple[str, int | None, str]] = []
    for row in _rows(values.get("responsibilities"), "responsibilities", errors):
        what = _text(row.get("text"), 2000)
        state = row.get("status") or "in_place"
        if not what:
            errors.add(
                "responsibilities", "Each responsibility says what the organization must do."
            )
            continue
        if state not in RESPONSIBILITY_STATES:
            errors.add("responsibilities", "Each is in place, not in place, or does not apply.")
            continue
        control_id = None
        if row.get("control"):
            control = session.scalars(
                select(Control).where(Control.ref == str(row["control"]).upper())
            ).first()
            if control is None or not access.can_see(session, principal, CONTROL, control):
                errors.add("responsibilities", f"There is no control {row['control']}.")
                continue
            control_id = control.id
        elif state == "in_place":
            errors.add("responsibilities", "Name the control that meets each one in place.")
            continue
        duties.append((what, control_id, state))
    if errors:
        raise Invalid("The review was not recorded.", errors)
    before = session.scalars(
        select(AssuranceReview).where(
            AssuranceReview.evidence_id == item.id, AssuranceReview.superseded_by.is_(None)
        )
    ).first()
    with audit.operation(session, "assurance.review", document=item.ref,
                         reliance=RELIANCE[reliance]):  # fmt: skip
        made = AssuranceReview(
            evidence_id=item.id, third_party_id=third_party.id, kind=kind,
            issuer=_text(values.get("issuer"), 200), opinion=opinion, services=covered,
            carve_outs=_text(values.get("carve_outs"), 4000), exceptions=exceptions,
            reliance=reliance, note=note, reviewed_by=principal.account_id,
            reviewed_by_name=principal.name, reviewed_at=utc_now(),
        )  # fmt: skip
        session.add(made)
        session.flush()
        for position, (what, control_id, state) in enumerate(duties):
            session.add(AssuranceResponsibility(
                review_id=made.id, third_party_id=third_party.id, position=position, text=what,
                control_id=control_id, status=state,
            ))  # fmt: skip
        if before is not None:
            before.superseded_by = made.id
        records.touch(session, item)
        session.flush()
    return made


def view(session: Session, principal: Principal, review: AssuranceReview,
         third_party: ThirdParty) -> dict[str, Any]:  # fmt: skip
    offered = session.scalars(
        select(Service).where(Service.third_party_id == third_party.id, Service.status == "active")
        .order_by(Service.name)
    ).all()  # fmt: skip
    covered = set(review.services or [])
    duties = session.scalars(
        select(AssuranceResponsibility)
        .where(AssuranceResponsibility.review_id == review.id)
        .order_by(AssuranceResponsibility.position)
    ).all()
    wanted = {d.control_id for d in duties if d.control_id} or {0}
    controls = {
        row.id: row
        for row in session.scalars(select(Control).where(Control.id.in_(wanted)))
        if access.can_see(session, principal, CONTROL, row)
    }
    return {
        "id": review.id,
        "kind": review.kind, "kind_label": KINDS.get(review.kind, review.kind),
        "issuer": review.issuer,
        "opinion": review.opinion, "opinion_label": OPINIONS.get(review.opinion, review.opinion),
        "covers": [records.chip(SERVICE, row) for row in offered if row.id in covered],
        "misses": [records.chip(SERVICE, row) for row in offered if row.id not in covered],
        "carve_outs": review.carve_outs,
        "exceptions": review.exceptions,
        "responsibilities": [
            {"text": d.text, "status": d.status,
             "status_label": RESPONSIBILITY_STATES[d.status],
             "control": records.chip(CONTROL, controls[d.control_id])
             if d.control_id in controls
             else None}
            for d in duties
        ],
        "reliance": review.reliance, "reliance_label": RELIANCE[review.reliance],
        "note": review.note, "by": review.reviewed_by_name, "at": review.reviewed_at,
    }  # fmt: skip


def for_control(session: Session, principal: Principal, control: Control) -> list[dict[str, Any]]:
    """The responsibilities third parties' reports leave to the organization that this
    control meets, from the reviews in force."""
    rows = session.execute(
        select(AssuranceResponsibility, AssuranceReview, Evidence, ThirdParty)
        .join(AssuranceReview, AssuranceReview.id == AssuranceResponsibility.review_id)
        .join(Evidence, Evidence.id == AssuranceReview.evidence_id)
        .join(ThirdParty, ThirdParty.id == AssuranceReview.third_party_id)
        .where(
            AssuranceResponsibility.control_id == control.id,
            AssuranceReview.superseded_by.is_(None),
            Evidence.status == "active",
        )
        .order_by(ThirdParty.name, AssuranceResponsibility.position)
    ).all()
    today = utc_now().date()
    return [
        {"text": duty.text, "status": duty.status,
         "third_party": records.chip(THIRD_PARTY, party),
         "document": records.chip(EVIDENCE, item), "kind_label": KINDS.get(review.kind),
         "in_date": item.valid_until >= today}
        for duty, review, item, party in rows
        if access.can_see(session, principal, THIRD_PARTY, party)
        and evidence_service.can_see(session, principal, item)
    ]  # fmt: skip


def _control_detail(
    earlier: Any,
) -> Any:
    """A control's page also lists what third parties' reports leave to it."""

    def detail(session: Session, principal: Principal, control: Control) -> dict[str, Any]:
        out = dict(earlier(session, principal, control)) if earlier else {}
        out["responsibilities"] = for_control(session, principal, control)
        return out

    return detail


CONTROL.extra["detail"] = _control_detail(CONTROL.extra.get("detail"))


def find_document(session: Session, ref: str) -> Evidence:
    found = session.scalars(select(Evidence).where(Evidence.ref == ref.strip().upper())).first()
    if found is None:
        raise NotFound(f"There is no report {ref}.")
    return found
