"""Requests to the audited (AUD-05): what an engagement needs, asked of one person by a date,
and answered with words and evidence.

A request is made by the engagement's team while it is being planned or in fieldwork. The
person asked sees what is asked, by whom, and by when, on their home page, and nothing else of
the engagement. They answer with words and with evidence, chosen first from what is already on
file about the thing being audited, so that nothing kept already is asked for twice. The team
accepts the answer, or sends it back with the reason.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.compliance import evidence as evidence_service
from riskwren.compliance.evidence import EVIDENCE
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    Account,
    AuditRequest,
    Engagement,
    Evidence,
    EvidenceLink,
    Implementation,
)
from riskwren.events import audit
from riskwren.internal_audit import engagements
from riskwren.inventory import records

MOST_SUGGESTED = 20


def ask(
    session: Session, principal: Principal, engagement: Engagement, values: Mapping[str, Any]
) -> AuditRequest:
    if engagements.role_on(session, principal, engagement) is None:
        raise PermissionDenied("Only the engagement's team asks for things.")
    if engagement.status not in ("planning", "fieldwork"):
        raise Conflict("Requests are made while planning or during fieldwork.")
    errors = records.Errors()
    what = records.text(values.get("what"))
    if not what:
        errors.add("what", "Say what is needed.")
    person = session.get(Account, int(values.get("assignee") or 0))
    if person is None or person.status == "disabled":
        errors.add("assignee", "Name someone who can sign in.")
    due = values.get("due_on")
    try:
        due = due if isinstance(due, date) else date.fromisoformat(str(due))
    except ValueError:
        due = None
        errors.add("due_on", "Give a date, as year-month-day.")
    if due is not None and due < utc_now().date():
        errors.add("due_on", "The date has passed.")
    if errors or person is None or due is None:
        raise Invalid("Nothing was asked.", errors)
    with audit.operation(session, "audit_request.ask"):
        request = AuditRequest(
            engagement_id=engagement.id,
            what=str(what),
            assignee_id=person.id,
            due_on=due,
            status="open",
            evidence=[],
            asked_by=principal.account_id,
            asked_by_name=principal.name,
            asked_at=utc_now(),
        )
        session.add(request)
        session.flush()
    return request


def find(
    session: Session, principal: Principal, request_id: int
) -> tuple[AuditRequest, Engagement]:
    request = session.get(AuditRequest, request_id)
    engagement = session.get(Engagement, request.engagement_id) if request else None
    if (
        request is None
        or engagement is None
        or not (
            request.assignee_id == principal.account_id
            or engagements.may_see_work(session, principal, engagement)
        )
    ):
        raise NotFound(f"There is no request {request_id}.")
    return request, engagement


def on_file(session: Session, principal: Principal, engagement: Engagement) -> list[dict[str, Any]]:
    """The evidence already kept about the thing being audited, and, for a scope, about the
    controls it uses: what the person asked may answer with, before sending anything new."""
    subjects: list[tuple[str, int]] = [(engagement.subject_type, engagement.subject_id)]
    if engagement.subject_type == "scope":
        subjects += [
            ("control", control_id)
            for control_id in session.scalars(
                select(Implementation.control_id).where(
                    Implementation.scope_id == engagement.subject_id
                )
            )
        ]
    found: dict[int, Evidence] = {}
    for kind, identifier in subjects:
        for row in session.scalars(
            select(Evidence)
            .join(EvidenceLink, EvidenceLink.evidence_id == Evidence.id)
            .where(
                EvidenceLink.subject_type == kind,
                EvidenceLink.subject_id == identifier,
                Evidence.status == "active",
            )
        ):
            found[row.id] = row
    seen = [row for row in found.values() if evidence_service.can_see(session, principal, row)]
    seen.sort(key=lambda row: (evidence_service.state_of(row) == "stale", row.ref))
    cards = records.cards(session, EVIDENCE, seen[:MOST_SUGGESTED])
    return [
        {
            "ref": c["ref"],
            "name": c["name"],
            "state": c.get("state"),
            "valid_until": c.get("valid_until"),
        }
        for c in cards
    ]


def answer(
    session: Session, principal: Principal, request: AuditRequest, values: Mapping[str, Any]
) -> None:
    if request.assignee_id != principal.account_id:
        raise PermissionDenied("The request is answered by the person it was asked of.")
    if request.status != "open":
        raise Conflict("It has been answered already.")
    errors = records.Errors()
    words = records.text(values.get("answer"))
    refs = [str(each).strip().upper() for each in values.get("evidence") or [] if str(each).strip()]
    if not words and not refs:
        errors.add("answer", "Answer in words, with evidence, or both.")
    items = {
        row.ref: row
        for row in session.scalars(select(Evidence).where(Evidence.ref.in_(refs or [""])))
    }
    for ref in refs:
        item = items.get(ref)
        if item is None or not evidence_service.can_see(session, principal, item):
            errors.add("evidence", f"{ref} is not an item of evidence you can see.")
    if errors:
        raise Invalid("The request was not answered.", errors)
    with audit.operation(session, "audit_request.answer"):
        request.answer, request.evidence = words, list(dict.fromkeys(refs))
        request.status, request.answered_at = "answered", utc_now()


def accept(
    session: Session, principal: Principal, request: AuditRequest, engagement: Engagement
) -> None:
    if engagements.role_on(session, principal, engagement) is None:
        raise PermissionDenied("The engagement's team accepts answers.")
    if request.status != "answered":
        raise Conflict("Only an answer is accepted.")
    with audit.operation(session, "audit_request.accept"):
        request.status = "accepted"
        request.accepted_by_name, request.accepted_at = principal.name, utc_now()


def send_back(
    session: Session,
    principal: Principal,
    request: AuditRequest,
    engagement: Engagement,
    reason: Any,
) -> None:
    if engagements.role_on(session, principal, engagement) is None:
        raise PermissionDenied("The engagement's team sends answers back.")
    if request.status != "answered":
        raise Conflict("Only an answer is sent back.")
    why = records.text(reason)
    if not why:
        raise Invalid("It was not sent back.", {"reason": "Say what is still needed."})
    with audit.operation(session, "audit_request.return"):
        request.status, request.returned_reason = "open", why


def row(session: Session, request: AuditRequest) -> dict[str, Any]:
    person = session.get(Account, request.assignee_id)
    today = utc_now().date()
    return {
        "id": request.id,
        "what": request.what,
        "assignee": {
            "account_id": request.assignee_id,
            "name": person.display_name if person else "",
        },
        "due_on": request.due_on,
        "overdue": request.status == "open" and request.due_on < today,
        "status": request.status,
        "answer": request.answer,
        "evidence": request.evidence,
        "answered_at": request.answered_at,
        "returned_reason": request.returned_reason,
        "accepted_by": request.accepted_by_name,
        "accepted_at": request.accepted_at,
        "asked_by": request.asked_by_name,
        "asked_at": request.asked_at,
    }


def of_engagement(session: Session, engagement: Engagement) -> list[dict[str, Any]]:
    found = session.scalars(
        select(AuditRequest)
        .where(AuditRequest.engagement_id == engagement.id)
        .order_by(AuditRequest.due_on, AuditRequest.id)
    ).all()
    return [row(session, each) for each in found]


def view(
    session: Session, principal: Principal, request: AuditRequest, engagement: Engagement
) -> dict[str, Any]:
    mine = request.assignee_id == principal.account_id
    return {
        **row(session, request),
        "engagement": {"ref": engagement.ref, "name": engagement.name, "status": engagement.status},
        "mine": mine,
        "team": engagements.role_on(session, principal, engagement) is not None,
        "on_file": on_file(session, principal, engagement)
        if mine and request.status == "open"
        else [],
    }


def waiting_on(
    session: Session, principal: Principal
) -> list[tuple[AuditRequest, Engagement, str]]:
    """Requests a person is asked to answer, and answers waiting for a team they are on."""
    me = principal.account_id
    if me is None:
        return []
    found: list[tuple[AuditRequest, Engagement, str]] = []
    for request, engagement in session.execute(
        select(AuditRequest, Engagement)
        .join(Engagement, Engagement.id == AuditRequest.engagement_id)
        .where(AuditRequest.assignee_id == me, AuditRequest.status == "open")
    ):
        found.append((request, engagement, "answer"))
    from riskwren.db.models import EngagementMember

    for request, engagement in session.execute(
        select(AuditRequest, Engagement)
        .join(Engagement, Engagement.id == AuditRequest.engagement_id)
        .join(EngagementMember, EngagementMember.engagement_id == Engagement.id)
        .where(EngagementMember.account_id == me, AuditRequest.status == "answered")
    ):
        found.append((request, engagement, "review"))
    return found
