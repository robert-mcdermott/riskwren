"""Committee sessions: an agenda drawn from the register, the decision taken on each item, and
the minutes (OVS-09).

A session belongs to a committee and a unit, and is kept by its owners and by the unit's
leaders and managers. Its agenda is a list of items, each a record from the register or a
topic of its own. When the committee decides on an item, the decision is kept on the item,
shows on the record it was about, and is told to that record's owners.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import CommitteeItem, CommitteeSession
from riskwren.db.models.governance import OUTCOMES, SESSION_STATUSES
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.registry import TYPES, RecordType, find_any, register
from riskwren.people import notices

KEY = "committee_session"
OUTCOME_WORDS = {"noted": "Noted", "approved": "Approved", "declined": "Declined",
                 "deferred": "Deferred"}  # fmt: skip
SOON = 14  # days before a session at which its owners see it on Home


def can_add(principal: Principal, org_unit_id: int | None) -> bool:
    """A unit's leaders, and managers: those a committee answers to, and who run it."""
    return principal.leads_unit(org_unit_id) or principal.manages_unit(org_unit_id)


def can_edit(session: Session, principal: Principal, meeting: CommitteeSession) -> bool:
    if can_add(principal, meeting.org_unit_id):
        return True
    kinds = access.owner_kinds(session, SESSION, meeting.id, principal.account_id)
    return bool(kinds & set(access.EDITING_KINDS))


def _new(meeting: CommitteeSession) -> None:
    meeting.status = "planned"


def _apply(
    session: Session, meeting: CommitteeSession, values: Mapping[str, Any],
    errors: records.Errors, creating: bool,
) -> None:  # fmt: skip
    if "committee" in values or creating:
        committee = records.text(values.get("committee"))
        if not committee:
            errors.add("committee", "Say which committee meets.")
        elif len(committee) > 120:
            errors.add("committee", "Keep this to 120 characters.")
        else:
            meeting.committee = committee
    if "held_on" in values or creating:
        given = values.get("held_on")
        try:
            meeting.held_on = given if isinstance(given, date) else date.fromisoformat(str(given))
        except ValueError:
            errors.add("held_on", "Give the date it meets, as YYYY-MM-DD.")
    for field in ("attendees", "minutes"):
        if field in values:
            setattr(meeting, field, records.text(values.get(field)))


def _counts(session: Session, ids: list[int]) -> dict[int, tuple[int, int]]:
    rows = session.execute(
        select(CommitteeItem.session_id, func.count(), func.count(CommitteeItem.outcome))
        .where(CommitteeItem.session_id.in_(ids or [0]))
        .group_by(CommitteeItem.session_id)
    ).all()
    return {row[0]: (row[1], row[2]) for row in rows}


def _cards(session: Session, rows: list[CommitteeSession]) -> list[dict[str, Any]]:
    counted = _counts(session, [row.id for row in rows])
    return [
        {
            "committee": row.committee, "held_on": row.held_on, "status": row.status,
            "items": counted.get(row.id, (0, 0))[0], "decided": counted.get(row.id, (0, 0))[1],
        }
        for row in rows
    ]  # fmt: skip


def _subject(session: Session, principal: Principal, item: CommitteeItem) -> dict[str, Any] | None:
    if item.subject_type is None or item.subject_type not in TYPES:
        return None
    record_type = TYPES[item.subject_type]
    record = session.get(record_type.model, item.subject_id)
    if record is None:
        return {"type": item.subject_type, "name": "A record that is no longer on record",
                "open": False}  # fmt: skip
    if not access.can_see(session, principal, record_type, record):
        return {"type": item.subject_type, "name": "A record you do not have access to",
                "open": False}  # fmt: skip
    return {**records.chip(record_type, record), "open": True}


def _item(session: Session, principal: Principal, item: CommitteeItem) -> dict[str, Any]:
    subject = _subject(session, principal, item)
    hidden = subject is not None and not subject.get("open")
    return {
        "id": item.id,
        "position": item.position,
        "title": "An item about a record you do not have access to" if hidden else item.title,
        "note": None if hidden else item.note,
        "subject": subject,
        "outcome": item.outcome,
        "decision": None if hidden else item.decision,
        "decided_by": item.decided_by_name,
        "decided_at": item.decided_at,
    }


def items_of(
    session: Session, principal: Principal, meeting: CommitteeSession
) -> list[dict[str, Any]]:
    return [
        _item(session, principal, row)
        for row in session.scalars(
            select(CommitteeItem)
            .where(CommitteeItem.session_id == meeting.id)
            .order_by(CommitteeItem.position, CommitteeItem.id)
        )
    ]


def _detail(session: Session, principal: Principal, meeting: CommitteeSession) -> dict[str, Any]:
    editable = can_edit(session, principal, meeting)
    return {
        "attendees": meeting.attendees,
        "minutes": meeting.minutes,
        "items_list": items_of(session, principal, meeting),
        "can": {
            "edit": editable and meeting.status != "cancelled",
            "assess": False,
            "decide": editable and meeting.status != "cancelled",
        },
    }


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    model = CommitteeSession
    if filters.get("status") in SESSION_STATUSES:
        found.append(model.status == filters["status"])
    when = filters.get("when")
    today = utc_now().date()
    if when == "upcoming":
        found += [model.held_on >= today, model.status == "planned"]
    elif when == "past":
        found.append(model.held_on < today)
    if filters.get("about"):
        record_type, record = find_any(session, str(filters["about"]))
        found.append(
            model.id.in_(
                select(CommitteeItem.session_id).where(
                    CommitteeItem.subject_type == record_type.key,
                    CommitteeItem.subject_id == record.id,
                )
            )
        )
    return found


def _history_title(event: Any, lookups: Any) -> str | None:
    context = event.context or {}
    op = context.get("op")
    if event.subject_type == "committee_item":
        title = context.get("title") or "an item"
        if op == "session.decide":
            return f"Decided on {title}: {context.get('outcome') or 'recorded'}"
        if op == "session.move":
            return f"Moved {title} on the agenda"
        if event.action == "created":
            return f"Added {title} to the agenda"
        if event.action == "deleted":
            return f"Took {title} off the agenda"
        return f"Changed {title} on the agenda"
    if op == "session.held":
        return "Recorded that it was held"
    if op == "session.cancel":
        note = context.get("note")
        return f"Cancelled it: {note}" if note else "Cancelled it"
    return None


SESSION = register(
    RecordType(
        KEY,
        CommitteeSession,
        "SES",
        "sessions",
        "session",
        "sessions",
        is_thing=False,
        sorts=("updated_at", "name", "ref", "held_on", "status"),
        filters=("status",),
        extra={
            "new": _new,
            "apply": _apply,
            "cards": _cards,
            "detail": _detail,
            "conditions": _conditions,
            "can_add": can_add,
            "can_edit": can_edit,
            "add_refusal": "Sessions are added by a unit's leaders, or by a manager.",
            "live_statuses": ("planned", "held"),
            "history_title": _history_title,
            "history_keeps_titled": True,
            "history_labels": {
                "committee": "Committee",
                "held_on": "Meets on",
                "attendees": "Present",
                "minutes": "Minutes",
            },
            "history_quiet": (
                "position",
                "decided_by",
                "decided_by_name",
                "decided_at",
                "subject_type",
                "subject_id",
                "session_id",
            ),
        },
    )
)


# --- The agenda -----------------------------------------------------------------------------


def _editable(session: Session, principal: Principal, meeting: CommitteeSession) -> None:
    if not can_edit(session, principal, meeting):
        raise PermissionDenied(
            "A session is kept by its owners, and by its unit's leaders and managers."
        )
    if meeting.status == "cancelled":
        raise Conflict("This session was cancelled.")


def _load_item(session: Session, meeting: CommitteeSession, item_id: int) -> CommitteeItem:
    item = session.get(CommitteeItem, item_id)
    if item is None or item.session_id != meeting.id:
        raise NotFound("That item is not on this session's agenda.")
    return item


def add_item(
    session: Session, principal: Principal, meeting: CommitteeSession, values: Mapping[str, Any]
) -> CommitteeItem:
    """Put a record from the register, or a topic of its own, on the agenda."""
    _editable(session, principal, meeting)
    errors = records.Errors()
    record_type: RecordType | None = None
    record: Any = None
    if values.get("record"):
        try:
            record_type, record = find_any(session, str(values["record"]).strip().upper())
        except NotFound as missing:
            errors.add("record", str(missing))
        else:
            if not access.can_see(session, principal, record_type, record):
                errors.add("record", f"There is no record {values['record']}.")
    title = records.text(values.get("title")) or (
        f"{record.ref} {record.name}" if record is not None else None
    )
    if not title:
        errors.add("title", "Say what the item is, or choose a record from the register.")
    elif len(title) > 300:
        errors.add("title", "Keep this to 300 characters.")
    if errors:
        raise Invalid("The item was not added.", errors)
    last = session.scalar(
        select(func.max(CommitteeItem.position)).where(CommitteeItem.session_id == meeting.id)
    )
    with audit.operation(session, "session.agenda", title=title):
        item = CommitteeItem(
            session_id=meeting.id, position=(last or 0) + 1,
            subject_type=record_type.key if record_type else None,
            subject_id=record.id if record is not None else None,
            title=title, note=records.text(values.get("note")),
        )  # fmt: skip
        session.add(item)
        records.touch(session, meeting)
        session.flush()
    return item


def change_item(
    session: Session, principal: Principal, meeting: CommitteeSession, item_id: int,
    values: Mapping[str, Any],
) -> CommitteeItem:  # fmt: skip
    _editable(session, principal, meeting)
    item = _load_item(session, meeting, item_id)
    with audit.operation(session, "session.agenda", title=item.title):
        if "title" in values:
            title = records.text(values.get("title"))
            if not title or len(title) > 300:
                raise Invalid("The item was not changed.", {"title": "Say what the item is."})
            item.title = title
        if "note" in values:
            item.note = records.text(values.get("note"))
        records.touch(session, meeting)
        session.flush()
    return item


def move_item(
    session: Session, principal: Principal, meeting: CommitteeSession, item_id: int, up: bool
) -> None:
    """Move an item one place up or down the agenda."""
    _editable(session, principal, meeting)
    item = _load_item(session, meeting, item_id)
    rows = list(
        session.scalars(
            select(CommitteeItem)
            .where(CommitteeItem.session_id == meeting.id)
            .order_by(CommitteeItem.position, CommitteeItem.id)
        )
    )
    at = rows.index(item)
    other = at - 1 if up else at + 1
    if not 0 <= other < len(rows):
        return
    with audit.operation(session, "session.move", title=item.title):
        rows[at], rows[other] = rows[other], rows[at]
        for place, row in enumerate(rows, start=1):
            row.position = place
        records.touch(session, meeting)
        session.flush()


def remove_item(
    session: Session, principal: Principal, meeting: CommitteeSession, item_id: int
) -> None:
    _editable(session, principal, meeting)
    item = _load_item(session, meeting, item_id)
    if item.outcome is not None:
        raise Conflict("A decision was taken on this item. It stays on the record.")
    with audit.operation(session, "session.agenda", title=item.title):
        session.delete(item)
        records.touch(session, meeting)
        session.flush()


# --- Deciding, and the meeting itself ---------------------------------------------------------


def decide(
    session: Session, principal: Principal, meeting: CommitteeSession, item_id: int,
    outcome: str | None, decision: str | None,
) -> CommitteeItem:  # fmt: skip
    """Record what the committee decided on an item. The decision shows on the record it was
    about, and that record's owners are told."""
    _editable(session, principal, meeting)
    item = _load_item(session, meeting, item_id)
    errors = records.Errors()
    if outcome not in OUTCOMES:
        errors.add("outcome", "Say whether it was noted, approved, declined, or deferred.")
    said = records.text(decision)
    if outcome != "noted" and not said:
        errors.add("decision", "Say what was decided, and any condition or date with it.")
    if errors:
        raise Invalid("The decision was not recorded.", errors)
    assert outcome is not None
    word = OUTCOME_WORDS[outcome]
    with audit.operation(session, "session.decide", title=item.title, outcome=word):
        item.outcome, item.decision = outcome, said
        item.decided_by, item.decided_by_name = principal.account_id, principal.name
        item.decided_at = utc_now()
        records.touch(session, meeting)
        session.flush()
        if item.subject_type in TYPES and item.subject_id is not None:
            record_type = TYPES[item.subject_type]
            record = session.get(record_type.model, item.subject_id)
            if record is not None:
                text = f"{meeting.committee}, {meeting.held_on.isoformat()}: {word}"
                text += f". {said}" if said else ""
                notices.tell_all(
                    session, notices.owners(session, record_type.key, record.id), "decision",
                    f"{record.ref} {text}"[:500], f"/{record_type.path}/{record.ref}",
                    by=principal,
                )  # fmt: skip
    return item


def mark_held(session: Session, principal: Principal, meeting: CommitteeSession) -> None:
    _editable(session, principal, meeting)
    if meeting.status == "held":
        raise Conflict("It is already recorded as held.")
    with audit.operation(session, "session.held"):
        meeting.status = "held"
        records.touch(session, meeting)
        session.flush()


def cancel(
    session: Session, principal: Principal, meeting: CommitteeSession, note: str | None
) -> None:
    _editable(session, principal, meeting)
    decided = session.scalar(
        select(func.count(CommitteeItem.outcome)).where(CommitteeItem.session_id == meeting.id)
    )
    if decided:
        raise Conflict("Decisions were taken in this session. It was held.")
    with audit.operation(session, "session.cancel", note=records.text(note)):
        meeting.status = "cancelled"
        records.touch(session, meeting)
        session.flush()


# --- From the record's side, and for Home ---------------------------------------------------


def decisions_about(
    session: Session, principal: Principal, subject_type: str, subject_id: int
) -> list[dict[str, Any]]:
    """The decisions committees have taken on a record, newest first, in the sessions the
    person may see."""
    rows = session.execute(
        select(CommitteeItem, CommitteeSession)
        .join(CommitteeSession, CommitteeSession.id == CommitteeItem.session_id)
        .where(
            CommitteeItem.subject_type == subject_type,
            CommitteeItem.subject_id == subject_id,
            CommitteeItem.outcome.is_not(None),
        )
        .order_by(CommitteeSession.held_on.desc(), CommitteeItem.id.desc())
    ).all()
    return [
        {
            "session": {
                **records.chip(SESSION, meeting),
                "committee": meeting.committee,
                "held_on": meeting.held_on,
            },
            "outcome": item.outcome,
            "decision": item.decision,
            "decided_at": item.decided_at,
        }
        for item, meeting in rows
        if access.can_see(session, principal, SESSION, meeting)
    ]


def coming_up(session: Session, principal: Principal) -> list[CommitteeSession]:
    """Planned sessions within a fortnight that this person keeps."""
    if principal.account_id is None:
        return []
    today = utc_now().date()
    return [
        meeting
        for meeting in session.scalars(
            select(CommitteeSession)
            .where(
                CommitteeSession.status == "planned",
                CommitteeSession.held_on >= today,
                CommitteeSession.held_on <= today + timedelta(days=SOON),
            )
            .order_by(CommitteeSession.held_on)
        )
        if principal.account_id in notices.owners(session, KEY, meeting.id)
    ]
