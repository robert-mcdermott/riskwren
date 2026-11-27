"""Due diligence (TPR-03): asking a third party about itself, without giving it an account.

A review (``DDR``) is a questionnaire chosen by the third party's tier, sent to one of its
contacts through a link (``respondent.py``), answered, and then read by someone here who
records what they concluded. The answers the questionnaire marks as concerns are counted and
listed, so the reviewer sees at once what needs a second look; the conclusion is theirs.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    Questionnaire,
    QuestionnaireVersion,
    RecordOwner,
    RespondentLink,
    Response,
    ThirdParty,
    ThirdPartyContact,
    ThirdPartyReview,
)
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.registry import THIRD_PARTY, RecordType, register
from riskwren.oversight import questionnaires
from riskwren.people import notices
from riskwren.thirdparty import tiering

KEY = "third_party_review"
CONCLUSIONS = {
    "approved": "Approved",
    "conditions": "Approved with conditions",
    "declined": "Not approved",
}
LINK_DAYS, LONGEST_LINK_DAYS = 30, 90
ANSWER_DAYS = 21  # how long a contact is given to answer, unless another date is set
# The questionnaire each tier is asked, where a tiering table saved before this release
# does not say.
DUE_DILIGENCE = {
    "tier_1": "due-diligence-full",
    "tier_2": "due-diligence-standard",
    "tier_3": "due-diligence-short",
}


# --- Who may start and keep one --------------------------------------------------------------


def keeps(session: Session, principal: Principal, third_party: ThirdParty) -> bool:
    """Those who keep the third party, and assessors whose scope covers it: the same people
    who tier it."""
    return tiering.may_tier(session, principal, third_party)


def can_add(principal: Principal, org_unit_id: int | None) -> bool:
    return (
        principal.assesses_unit(org_unit_id)
        or principal.stewards_unit(org_unit_id)
        or principal.manages_unit(org_unit_id)
    )


def can_edit(session: Session, principal: Principal, review: ThirdPartyReview) -> bool:
    """Its owners and delegates, assessors whose scope covers it, and its unit's keepers."""
    if can_add(principal, review.org_unit_id):
        return True
    kinds = access.owner_kinds(session, REVIEW, review.id, principal.account_id)
    return bool(kinds & set(access.EDITING_KINDS))


def questionnaire_for(session: Session, tier: str | None) -> str | None:
    """The key of the questionnaire a third party of this tier is asked."""
    for each in tiering.tiers(session):
        if each["key"] == tier:
            return each.get("due_diligence", DUE_DILIGENCE.get(each["key"]))
    return None


# --- Its facts ------------------------------------------------------------------------------


def _new(review: ThirdPartyReview) -> None:
    review.status = "draft"


def _day(value: Any, field: str, errors: records.Errors) -> date | None:
    if value in (None, ""):
        return None
    try:
        return value if isinstance(value, date) else date.fromisoformat(str(value))
    except ValueError:
        errors.add(field, "Give a date as YYYY-MM-DD.")
        return None


def _apply(
    session: Session, review: ThirdPartyReview, values: Mapping[str, Any],
    errors: records.Errors, creating: bool,
) -> None:  # fmt: skip
    if review.status not in ("draft", None) and set(values) & {"third_party", "questionnaire"}:
        errors.add("questionnaire", "Once sent, what is asked stays as it was sent.")
        return
    if "third_party" in values or creating:
        ref = (records.text(values.get("third_party")) or "").upper()
        found = session.scalars(select(ThirdParty).where(ThirdParty.ref == ref)).first()
        if found is None:
            errors.add("third_party", f"There is no third party {ref or 'named'}.")
        elif found.status != "active":
            errors.add("third_party", f"{found.name} is retired.")
        else:
            review.third_party_id = found.id
            review.tier = found.tier
    if "questionnaire" in values or creating:
        key = records.text(values.get("questionnaire"))
        if key is None and review.third_party_id is not None:
            party = session.get(ThirdParty, review.third_party_id)
            key = questionnaire_for(session, party.tier if party else None)
        row = (
            session.scalars(select(Questionnaire).where(Questionnaire.key == key)).first()
            if key
            else None
        )
        if row is None:
            errors.add("questionnaire", "Choose the questionnaire to ask. A tier 4 third party "
                       "has none of its own.")  # fmt: skip
        elif row.status != "active":
            errors.add("questionnaire", f"{row.title} is no longer used.")
        else:
            review.questionnaire_id = row.id
    if "due_on" in values:
        review.due_on = _day(values.get("due_on"), "due_on", errors)


def _cards(session: Session, rows: list[ThirdPartyReview]) -> list[dict[str, Any]]:
    parties = {
        row.id: row
        for row in session.scalars(
            select(ThirdParty).where(ThirdParty.id.in_({r.third_party_id for r in rows} or {0}))
        )
    }
    asked = {
        row.id: row.title
        for row in session.scalars(
            select(Questionnaire).where(
                Questionnaire.id.in_({r.questionnaire_id for r in rows} or {0})
            )
        )
    }
    names = tiering.labels(session)
    return [
        {
            "status": row.status,
            "third_party": records.chip(THIRD_PARTY, parties[row.third_party_id])
            if row.third_party_id in parties else None,
            "tier": row.tier, "tier_label": names.get(row.tier or "", None),
            "questionnaire": asked.get(row.questionnaire_id),
            "due_on": row.due_on, "sent_at": row.sent_at, "answered_at": row.answered_at,
            "concluded_at": row.concluded_at, "conclusion": row.conclusion,
            "late": row.status == "sent" and row.due_on is not None
            and row.due_on < utc_now().date(),
        }
        for row in rows
    ]  # fmt: skip


# --- Concerns -------------------------------------------------------------------------------


def _marked(question: Mapping[str, Any]) -> bool:
    return "concern_if" in question or any(
        option.get("concern") for option in question.get("options", [])
    )


def _is_concern(question: Mapping[str, Any], value: Any) -> bool:
    if value is None:
        return False
    if "concern_if" in question:
        return value is question["concern_if"]
    concerning = {o["key"] for o in question.get("options", []) if o.get("concern")}
    chosen = value if isinstance(value, list) else [value]
    return bool(concerning & set(chosen))


def _said(question: Mapping[str, Any], value: Any) -> str:
    """The answer that is a concern, in the words it was chosen by."""
    if question["type"] == "yes_no":
        return "Yes" if value else "No"
    labels = {o["key"]: o["label"] for o in question.get("options", [])}
    chosen = value if isinstance(value, list) else [value]
    marked = [labels.get(k, k) for k in chosen if any(
        o["key"] == k and o.get("concern") for o in question.get("options", []))]  # fmt: skip
    return ", ".join(marked)


def concerns(document: Mapping[str, Any], answers: Mapping[str, Any]) -> dict[str, Any]:
    """The answers the questionnaire marks as concerns, and how many marked questions were
    answered: what the reviewer should look at first. It decides nothing."""
    found, scored = [], 0
    for section, question in questionnaires.visible(document, answers):
        if not _marked(question) or answers.get(question["key"]) is None:
            continue
        scored += 1
        value = answers[question["key"]]
        if _is_concern(question, value):
            found.append({"key": question["key"], "section": section["title"],
                          "label": question["label"], "said": _said(question, value)})  # fmt: skip
    return {"items": found, "scored": scored, "count": len(found)}


# --- Showing one ----------------------------------------------------------------------------


def live_link(session: Session, review: ThirdPartyReview) -> RespondentLink | None:
    return session.scalars(
        select(RespondentLink)
        .where(RespondentLink.subject_type == KEY, RespondentLink.subject_id == review.id)
        .order_by(RespondentLink.id.desc())
    ).first()


def link_state(link: RespondentLink | None) -> str | None:
    if link is None:
        return None
    if link.finished_at is not None:
        return "used"
    if link.revoked_at is not None:
        return "withdrawn"
    if link.expires_at <= utc_now():
        return "expired"
    return "live"


def response_of(session: Session, review: ThirdPartyReview) -> Response | None:
    return session.scalars(
        select(Response)
        .where(Response.subject_type == KEY, Response.subject_id == review.id)
        .order_by(Response.id.desc())
    ).first()


def contact_view(contact: ThirdPartyContact) -> dict[str, Any]:
    return {"id": contact.id, "name": contact.name, "email": contact.email, "role": contact.role,
            "phone": contact.phone, "status": contact.status}  # fmt: skip


def _files(session: Session, principal: Principal, review: ThirdPartyReview) -> list[Any]:
    """The reports the contact sent with the answers, as much as the person may see."""
    from riskwren.compliance import evidence
    from riskwren.thirdparty import respondent

    return [
        records.chip(evidence.EVIDENCE, item)
        for item in respondent.sent_files(session, review)
        if evidence.can_see(session, principal, item)
    ]


def _detail(session: Session, principal: Principal, review: ThirdPartyReview) -> dict[str, Any]:
    editable = can_edit(session, principal, review)
    party = session.get(ThirdParty, review.third_party_id)
    asked = session.get(Questionnaire, review.questionnaire_id)
    contact = session.get(ThirdPartyContact, review.contact_id) if review.contact_id else None
    link = live_link(session, review)
    response = response_of(session, review)
    answers: dict[str, Any] | None = None
    if response is not None:
        version = session.get(QuestionnaireVersion, response.version_id)
        assert version is not None
        answers = {
            "status": response.status, "by": response.account_name,
            "started_at": response.started_at, "submitted_at": response.submitted_at,
            "version": version.number,
            "as_asked": questionnaires.as_asked(version.document, response.answers),
            "concerns": concerns(version.document, response.answers)
            if response.status == "submitted" else None,
        }  # fmt: skip
    return {
        "third_party": records.chip(THIRD_PARTY, party) if party else None,
        "questionnaire": {"key": asked.key, "title": asked.title,
                          "version": review.version_number or asked.current_version}
        if asked else None,
        "contact": contact_view(contact) if contact else None,
        "link": None if link is None else {
            "state": link_state(link), "created_at": link.created_at,
            "expires_at": link.expires_at, "last_used_at": link.last_used_at,
        },
        "answers": answers,
        "files": _files(session, principal, review),
        "conclusion_label": CONCLUSIONS.get(review.conclusion or ""),
        "conclusion_note": review.conclusion_note,
        "concluded_by": review.concluded_by_name,
        "cancelled_note": review.cancelled_note,
        "can": {
            "edit": editable and review.status == "draft",
            "send": editable and review.status in ("draft", "sent"),
            "withdraw": editable and link_state(link) == "live",
            "conclude": editable and review.status == "answered",
            "cancel": editable and review.status in ("draft", "sent"),
        },
    }  # fmt: skip


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    model = ThirdPartyReview
    status = filters.get("status")
    if status in ("draft", "sent", "answered", "concluded", "cancelled"):
        found.append(model.status == status)
    elif status == "open":
        found.append(model.status.in_(("draft", "sent", "answered")))
    if filters.get("third_party"):
        found.append(model.third_party_id.in_(
            select(ThirdParty.id).where(ThirdParty.ref == str(filters["third_party"]).upper())
        ))  # fmt: skip
    if filters.get("late"):
        found += [model.status == "sent", model.due_on < utc_now().date()]
    return found


def _history_title(event: Any, lookups: Any) -> str | None:
    context = event.context or {}
    op = context.get("op")
    if op == "review.send":
        return f"Sent it to {context.get('contact')}, to answer by {context.get('due_on')}"
    if op == "review.withdraw":
        return "Withdrew the link"
    if op == "review.save":
        return "The answers were saved, to finish later"
    if op == "review.submit":
        return f"{context.get('contact')} sent the answers"
    if op == "review.conclude":
        note = context.get("note")
        return f"Concluded: {context.get('conclusion')}" + (f". {note}" if note else "")
    if op == "review.cancel":
        return "Cancelled it" + (f": {context['note']}" if context.get("note") else "")
    return None


REVIEW = register(
    RecordType(
        KEY,
        ThirdPartyReview,
        "DDR",
        "reviews",
        "review",
        "reviews",
        is_thing=False,
        sorts=("updated_at", "name", "ref", "due_on", "status"),
        filters=(),
        extra={
            "new": _new,
            "apply": _apply,
            "cards": _cards,
            "detail": _detail,
            "conditions": _conditions,
            "can_add": can_add,
            "can_edit": can_edit,
            "add_refusal": "A review is started by those who keep the third party, or an assessor.",
            "live_statuses": ("draft", "sent", "answered"),
            "history_title": _history_title,
            "history_keeps_titled": True,
            "history_labels": {
                "third_party_id": "Third party",
                "questionnaire_id": "Questionnaire",
                "contact_id": "Contact",
                "due_on": "Answers wanted by",
                "conclusion_note": "What was concluded",
            },
            "history_quiet": (
                "status",
                "sent_at",
                "answered_at",
                "concluded_at",
                "concluded_by",
                "concluded_by_name",
                "conclusion",
                "version_number",
                "cancelled_note",
                "tier",
            ),
            "history_hidden": ("respondent_link",),
        },
    )
)


# --- Its life -------------------------------------------------------------------------------


def start(
    session: Session, principal: Principal, third_party: ThirdParty, values: Mapping[str, Any]
) -> ThirdPartyReview:
    """Start a review of a third party: the questionnaire its tier asks, unless another is
    chosen. Its unit is the third party's."""
    if not keeps(session, principal, third_party):
        raise PermissionDenied(
            "A review is started by those who keep the third party, or by an assessor."
        )
    year = utc_now().year
    wanted = {
        "name": records.text(values.get("name")) or f"{third_party.name}: due diligence {year}",
        "summary": values.get("summary"),
        "org_unit_id": third_party.org_unit_id,
        "third_party": third_party.ref,
        "questionnaire": values.get("questionnaire"),
        "due_on": values.get("due_on"),
    }
    return records.create(session, principal, REVIEW, wanted, checked=True)


def _contact(session: Session, review: ThirdPartyReview, contact_id: Any) -> ThirdPartyContact:
    try:
        found = session.get(ThirdPartyContact, int(contact_id))
    except (TypeError, ValueError):
        found = None
    if found is None or found.third_party_id != review.third_party_id:
        raise Invalid("It was not sent.", {"contact_id": "Choose one of its contacts."})
    if found.status != "active":
        raise Invalid("It was not sent.", {"contact_id": f"{found.name} has left."})
    return found


def send(
    session: Session, principal: Principal, review: ThirdPartyReview, *, contact_id: Any,
    due_on: Any = None, days: Any = None,
) -> str:  # fmt: skip
    """Send the questionnaire to a contact: a new link, and any earlier one withdrawn. Returns
    the token, which is never stored and is shown to the sender once."""
    from riskwren.thirdparty import respondent

    if not can_edit(session, principal, review):
        raise PermissionDenied("A review is sent by its owners, or an assessor.")
    if review.status not in ("draft", "sent"):
        raise Conflict("Its answers are in. A new review asks again.")
    contact = _contact(session, review, contact_id)
    errors = records.Errors()
    answer_by = _day(due_on, "due_on", errors) if due_on not in (None, "") else None
    try:
        lasting = int(days) if days not in (None, "") else LINK_DAYS
    except (TypeError, ValueError):
        lasting = -1
    if not 1 <= lasting <= LONGEST_LINK_DAYS:
        errors.add("days", f"A link lasts from 1 to {LONGEST_LINK_DAYS} days.")
    today = utc_now().date()
    answer_by = answer_by or review.due_on or today + timedelta(days=min(ANSWER_DAYS, lasting))
    if answer_by < today and "due_on" not in errors:
        errors.add("due_on", "Give a date that has not passed.")
    if errors:
        raise Invalid("It was not sent.", errors)
    asked = session.get(Questionnaire, review.questionnaire_id)
    assert asked is not None
    if asked.status != "active" and review.version_number is None:
        raise Conflict(f"{asked.title} is no longer used. Choose another before sending.")
    with audit.operation(session, "review.send", contact=contact.name,
                         due_on=answer_by.isoformat()):  # fmt: skip
        token = respondent.issue(session, principal, KEY, review.id, contact, days=lasting)
        if review.version_number is None:
            review.version_number = asked.current_version
        review.status, review.contact_id, review.due_on = "sent", contact.id, answer_by
        review.sent_at = utc_now()
        records.touch(session, review)
        session.flush()
    return token


def withdraw(session: Session, principal: Principal, review: ThirdPartyReview) -> None:
    from riskwren.thirdparty import respondent

    if not can_edit(session, principal, review):
        raise PermissionDenied("A link is withdrawn by the review's owners, or an assessor.")
    link = live_link(session, review)
    if link_state(link) != "live":
        raise Conflict("There is no link in use to withdraw.")
    with audit.operation(session, "review.withdraw"):
        respondent.revoke(session, KEY, review.id)
        records.touch(session, review)


def answered(session: Session, review: ThirdPartyReview, contact: ThirdPartyContact) -> None:
    """The contact has sent the answers: tell whoever keeps the review."""
    review.status, review.answered_at = "answered", utc_now()
    records.touch(session, review)
    party = session.get(ThirdParty, review.third_party_id)
    notices.tell_all(
        session, notices.owners(session, KEY, review.id), "review",
        f"{contact.name} of {party.name if party else 'a third party'} sent the answers to "
        f"{review.ref} {review.name}",
        f"/reviews/{review.ref}",
    )  # fmt: skip


def conclude(
    session: Session, principal: Principal, review: ThirdPartyReview, conclusion: str,
    note: str | None,
) -> None:  # fmt: skip
    """Record what was concluded from the answers. With conditions, or not approved, says why."""
    if not can_edit(session, principal, review):
        raise PermissionDenied("A review is concluded by its owners, or an assessor.")
    if review.status != "answered":
        raise Conflict("A review is concluded once its answers are in.")
    if conclusion not in CONCLUSIONS:
        raise Invalid("It was not concluded.", {"conclusion": "Choose what was concluded."})
    said = records.text(note)
    if conclusion != "approved" and not said:
        raise Invalid(
            "It was not concluded.",
            {"note": "Say what the conditions are, or why it is not approved."},
        )
    with audit.operation(session, "review.conclude", conclusion=CONCLUSIONS[conclusion],
                         note=said):  # fmt: skip
        review.status, review.conclusion, review.conclusion_note = "concluded", conclusion, said
        review.concluded_at = utc_now()
        review.concluded_by, review.concluded_by_name = principal.account_id, principal.name
        records.touch(session, review)
        session.flush()


def cancel(session: Session, principal: Principal, review: ThirdPartyReview,
           note: str | None) -> None:  # fmt: skip
    from riskwren.thirdparty import respondent

    if not can_edit(session, principal, review):
        raise PermissionDenied("A review is cancelled by its owners, or an assessor.")
    if review.status not in ("draft", "sent"):
        raise Conflict("Only a review not yet answered can be cancelled.")
    said = records.text(note)
    with audit.operation(session, "review.cancel", note=said):
        respondent.revoke(session, KEY, review.id)
        review.status, review.cancelled_note = "cancelled", said
        records.touch(session, review)
        session.flush()


# --- What waits on people -------------------------------------------------------------------


def waiting_on(session: Session, principal: Principal) -> list[tuple[ThirdPartyReview, str]]:
    """The reviews this person keeps that wait on them: answers to read, or answers late."""
    if principal.account_id is None:
        return []
    from sqlalchemy import and_

    rows = session.scalars(
        select(ThirdPartyReview)
        .join(RecordOwner, and_(RecordOwner.record_type == KEY,
                                RecordOwner.record_id == ThirdPartyReview.id))
        .where(RecordOwner.account_id == principal.account_id,
               RecordOwner.kind.in_(access.EDITING_KINDS),
               ThirdPartyReview.status.in_(("sent", "answered")))
        .order_by(ThirdPartyReview.due_on, ThirdPartyReview.ref)
        .distinct()
    ).all()  # fmt: skip
    today = utc_now().date()
    out = []
    for row in rows:
        if row.status == "answered":
            out.append((row, "answered"))
        elif row.due_on is not None and row.due_on < today:
            out.append((row, "late"))
        elif link_state(live_link(session, row)) in ("expired", "withdrawn"):
            out.append((row, "no_link"))
    return out


def of(session: Session, principal: Principal, third_party: ThirdParty) -> list[dict[str, Any]]:
    """A third party's reviews, newest first, as much as the person may see."""
    rows = [
        row for row in session.scalars(
            select(ThirdPartyReview)
            .where(ThirdPartyReview.third_party_id == third_party.id)
            .order_by(ThirdPartyReview.id.desc())
        )
        if access.can_see(session, principal, REVIEW, row)
    ]  # fmt: skip
    cards = _cards(session, rows)
    return [{**records.chip(REVIEW, row), **card} for row, card in zip(rows, cards, strict=True)]


def find(session: Session, ref: str) -> ThirdPartyReview:
    found = session.scalars(
        select(ThirdPartyReview).where(ThirdPartyReview.ref == ref.strip().upper())
    ).first()
    if found is None:
        raise NotFound(f"There is no review {ref}.")
    return found
