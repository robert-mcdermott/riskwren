"""Links for people without accounts (security.md: "long random tokens, single-purpose,
expiring, and reach one form and nothing else").

A link is a token of 256 random bits. Only its digest is kept; the token itself is shown
once to whoever sends it and goes in the message to the contact. In the address it follows a
``#``, which a browser never sends to a server, so it is in nobody's logs and in no
``Referer``. The page sends it back in a header of its own.

A link reaches one thing: the questionnaire of the review it was made for, as that contact.
It stops working when it expires, when it is withdrawn, when another is sent in its place,
and once the answers have been sent with it. Nothing else in RiskWren is reachable with it.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid, RiskWrenError
from riskwren.db.models import (
    Questionnaire,
    RespondentLink,
    Response,
    ThirdParty,
    ThirdPartyContact,
    ThirdPartyReview,
)
from riskwren.events import audit
from riskwren.events.actor import Actor
from riskwren.oversight import questionnaires
from riskwren.program import branding

HEADER = "X-RiskWren-Link"
RESPONDENT = "respondent"  # the kind of actor a link's holder is, in the history


class LinkRefused(RiskWrenError):
    """A token that reaches nothing: unknown, expired, withdrawn, or already used. ``reason``
    says which, for a token that was once good; the holder of a good token already knows
    what it was for, so saying is no help to anyone guessing."""

    def __init__(self, reason: str | None) -> None:
        self.reason = reason
        super().__init__(
            {
                None: "This link does not lead anywhere. Check that the whole address was "
                "copied, or ask whoever sent it for a new one.",
                "expired": "This link has expired. Ask whoever sent it for a new one.",
                "withdrawn": "This link was withdrawn. Ask whoever sent it for a new one.",
                "used": "The answers were sent with this link, so it no longer opens the "
                "questionnaire. Thank you.",
            }[reason]
        )


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue(
    session: Session, principal: Principal, subject_type: str, subject_id: int,
    contact: ThirdPartyContact, *, days: int,
) -> str:  # fmt: skip
    """A new link to one thing, for one contact, withdrawing any earlier one."""
    revoke(session, subject_type, subject_id)
    token = secrets.token_urlsafe(32)
    now = utc_now()
    session.add(
        RespondentLink(
            token_hash=digest(token), purpose="review", subject_type=subject_type,
            subject_id=subject_id, contact_id=contact.id, created_by=principal.account_id,
            created_at=now, expires_at=now + timedelta(days=days), used_count=0,
        )
    )  # fmt: skip
    session.flush()
    return token


def revoke(session: Session, subject_type: str, subject_id: int) -> int:
    """Withdraw every link to the thing that still works. Returns how many."""
    now = utc_now()
    live = session.scalars(
        select(RespondentLink).where(
            RespondentLink.subject_type == subject_type,
            RespondentLink.subject_id == subject_id,
            RespondentLink.revoked_at.is_(None),
            RespondentLink.finished_at.is_(None),
        )
    ).all()
    for link in live:
        link.revoked_at = now
    session.flush()
    return len(live)


def find(session: Session, token: str | None) -> RespondentLink:
    """The link a token is for, if it still reaches its form."""
    if not token or len(token) > 200:
        raise LinkRefused(None)
    link = session.scalars(
        select(RespondentLink).where(RespondentLink.token_hash == digest(token.strip()))
    ).first()
    if link is None:
        raise LinkRefused(None)
    if link.finished_at is not None:
        raise LinkRefused("used")
    if link.revoked_at is not None:
        raise LinkRefused("withdrawn")
    if link.expires_at <= utc_now():
        raise LinkRefused("expired")
    return link


def actor_for(session: Session, link: RespondentLink) -> Actor:
    """Who acts through a link, as the history names them."""
    contact = session.get(ThirdPartyContact, link.contact_id)
    party = session.get(ThirdParty, contact.third_party_id) if contact else None
    name = contact.name if contact else "A contact"
    return Actor(RESPONDENT, None, f"{name} ({party.name if party else 'a third party'}), by link")


def _parts(session: Session, link: RespondentLink) -> tuple[Any, ...]:
    review = session.get(ThirdPartyReview, link.subject_id)
    contact = session.get(ThirdPartyContact, link.contact_id)
    if review is None or contact is None or link.subject_type != "third_party_review":
        raise LinkRefused(None)
    if review.status != "sent":
        raise LinkRefused("withdrawn")
    asked = session.get(Questionnaire, review.questionnaire_id)
    assert asked is not None
    version = questionnaires.version_of(session, asked, review.version_number)
    response = session.scalars(
        select(Response).where(
            Response.subject_type == "third_party_review", Response.subject_id == review.id,
            Response.status == "draft",
        )
    ).first()  # fmt: skip
    party = session.get(ThirdParty, review.third_party_id)
    return review, contact, asked, version, response, party


def view(session: Session, link: RespondentLink) -> dict[str, Any]:
    """What the holder of a link sees: who is asking, by when, and the questions. Nothing of
    the review beyond that, and nothing about anyone else."""
    review, contact, asked, version, response, party = _parts(session, link)
    from riskwren.db.models import Account

    sender = session.get(Account, link.created_by) if link.created_by else None
    brand = branding.load(session)
    return {
        "organization": brand.organization_name or brand.product_name,
        "asked_by": sender.display_name if sender else None,
        "third_party": party.name if party else None,
        "contact": contact.name,
        "title": asked.title,
        "summary": asked.summary,
        "due_on": review.due_on,
        "expires_at": link.expires_at,
        "document": version.document,
        "answers": response.answers if response else {},
        "saved_at": response.started_at if response else None,
        "files": [{"name": item.file_name} for item in sent_files(session, review)],
        "most_files": MAX_FILES,
    }


def save(session: Session, link: RespondentLink, answers: Any, *, submit: bool) -> dict[str, Any]:
    """Keep the answers given through a link: to finish later, or sent. Once sent, the link
    stops working and the review waits on whoever keeps it."""
    from riskwren.thirdparty import reviews

    review, contact, _asked, version, response, _party = _parts(session, link)
    if not isinstance(answers, dict):
        raise Invalid("The answers were not saved.", {"answers": "Send the answers by question."})
    cleaned, errors = questionnaires.clean(version.document, answers, complete=submit)
    if errors:
        raise Invalid("Some answers need another look.", errors)
    now = utc_now()
    op = "review.submit" if submit else "review.save"
    with audit.operation(session, op, contact=contact.name):
        if response is None:
            response = Response(
                version_id=version.id, subject_type="third_party_review", subject_id=review.id,
                account_id=None, contact_id=contact.id, account_name=contact.name,
                started_at=now, answers={},
            )  # fmt: skip
            session.add(response)
        response.answers = cleaned
        if submit:
            response.status, response.submitted_at = "submitted", now
            link.finished_at = now
            reviews.answered(session, review, contact)
        session.flush()
    # How often a link is used is bookkeeping, not history: these two are not audited.
    link.last_used_at, link.used_count = now, (link.used_count or 0) + 1
    session.flush()
    if submit:
        return {"sent": True}
    return {"sent": False, "saved_at": now}


MAX_FILES = 10  # reports a contact may send with one review


def sent_files(session: Session, review: ThirdPartyReview) -> list[Any]:
    """The reports sent with a review's answers, through any of its links."""
    from riskwren.db.models import Evidence, EvidenceLink

    return list(
        session.scalars(
            select(Evidence)
            .join(EvidenceLink, EvidenceLink.evidence_id == Evidence.id)
            .where(
                EvidenceLink.subject_type == "third_party_review",
                EvidenceLink.subject_id == review.id,
            )
            .order_by(Evidence.id)
        )
    )


def attach(
    session: Session, link: RespondentLink, root: Any, data: bytes, name: str | None
) -> dict[str, Any]:
    """Keep a report the contact sends with the answers: stored like any evidence file, as
    evidence of the third party and of the review, owned by whoever keeps the review, to be
    read and reviewed here. Its kind is judged by its content, as any upload's is."""
    from riskwren.access.principal import Principal
    from riskwren.compliance.evidence import EVIDENCE
    from riskwren.db.models import EvidenceLink, RecordOwner, StoredFile
    from riskwren.files import store
    from riskwren.inventory import records
    from riskwren.people import notices
    from riskwren.program import rules

    review, contact, _asked, _version, _response, party = _parts(session, link)
    if len(sent_files(session, review)) >= MAX_FILES:
        raise Invalid(
            "The file was not taken.",
            {"file": f"Up to {MAX_FILES} files can be sent with one review."},
        )
    digest, kind = store.save(root, data)
    stored = session.scalars(select(StoredFile).where(StoredFile.sha256 == digest)).first()
    if stored is None:
        stored = StoredFile(sha256=digest, size=len(data), media_type=kind.media_type,
                            extension=kind.extension, created_at=utc_now())  # fmt: skip
        session.add(stored)
        session.flush()
    called = store.safe_name(name, kind)
    today = utc_now().date()
    who = Principal(None, f"{contact.name} ({party.name if party else 'a third party'}), by link")
    with audit.operation(session, "review.file", contact=contact.name, file=called):
        item = records.create(session, who, EVIDENCE, {
            "name": f"{called}, from {party.name if party else 'a third party'}",
            "summary": f"Sent by {contact.name} with the answers to {review.ref}. Review it to "
                       "say what it is, what it covers, and until when it holds.",
            "kind": "file", "org_unit_id": review.org_unit_id, "collected_on": today,
            "valid_until": rules.add_months(today, 12), "data_class": "confidential",
        }, checked=True)  # fmt: skip
        item.file_id, item.file_name = stored.id, called
        session.add(EvidenceLink(evidence_id=item.id, subject_type="third_party_review",
                                 subject_id=review.id))  # fmt: skip
        if party is not None:
            session.add(EvidenceLink(evidence_id=item.id, subject_type="third_party",
                                     subject_id=party.id))  # fmt: skip
        keepers = notices.owners(session, "third_party_review", review.id)
        for account_id in keepers:
            session.add(RecordOwner(record_type="evidence", record_id=item.id,
                                    account_id=account_id, kind="owner"))  # fmt: skip
        session.flush()
    return {"name": called, "size": len(data)}
