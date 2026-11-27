"""Reporting and triage (INC-01, INC-03).

Anyone signed in reports an incident, a near miss, or a concern in one short form: what
happened, when, and where. It goes to those who triage for its unit (managers, and assessors
for the unit, which includes a security team that assesses across the organization), who give
it a category, a severity, the records it concerns, and someone to handle it.

An incident is seen by those who need to: its reporter, its handlers, those who triage for
its unit, the leaders and stewards of its unit, and those who read everything; nobody else.
Its reporter sees what they reported, where it stands, and what is said to them, but not the
handling itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from riskwren.access import roles
from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import Account, Incident, IncidentMessage, IncidentSubject, RecordOwner
from riskwren.db.models.compliance import SEVERITIES
from riskwren.db.models.incidents import INCIDENT_KINDS, INCIDENT_STATUSES, INCIDENT_SUBJECTS
from riskwren.db.refs import next_ref
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.registry import RecordType, find_any, register
from riskwren.people import accounts, notices

KEY = "incident"
LIVE = ("reported", "handling")
KIND_LABELS = {"incident": "Incident", "near_miss": "Near miss", "concern": "Concern"}
# Those who see every incident in a unit they hold these roles for.
OVERSEERS = (roles.MANAGER, roles.ASSESSOR, roles.LEADER, roles.STEWARD)
LONGEST_MESSAGE = 10_000


# --- Who sees it, and who does what -------------------------------------------------------


def triages(principal: Principal, org_unit_id: int | None) -> bool:
    """Managers, and assessors for the unit (an assessor for the whole organization, such
    as a security team's, triages everywhere)."""
    return principal.assesses_unit(org_unit_id)


def handles(session: Session, principal: Principal, incident: Incident) -> bool:
    kinds = access.owner_kinds(session, INCIDENT, incident.id, principal.account_id)
    return bool(kinds & set(access.EDITING_KINDS))


def reported(principal: Principal, incident: Incident) -> bool:
    return principal.account_id is not None and incident.created_by == principal.account_id


def knows_all(session: Session, principal: Principal, incident: Incident) -> bool:
    """Whether the person sees the handling, not only the report: those who read
    everything, those who triage for its unit, its unit's leaders and stewards, and its
    handlers."""
    if principal.reads_all:
        return True
    units = principal.units_for(*OVERSEERS)
    if units is None or incident.org_unit_id in units:
        return True
    return bool(access.owner_kinds(session, INCIDENT, incident.id, principal.account_id))


def can_see(session: Session, principal: Principal, incident: Incident) -> bool:
    return reported(principal, incident) or knows_all(session, principal, incident)


def visible(session: Session, principal: Principal) -> Any:
    """The same rule as a condition, for lists, counts, and search."""
    if principal.reads_all:
        return None
    units = principal.units_for(*OVERSEERS)
    if units is None:
        return None
    me = principal.account_id
    named = exists(
        select(RecordOwner.id).where(
            RecordOwner.record_type == KEY,
            RecordOwner.record_id == Incident.id,
            RecordOwner.account_id == me,
        )
    )
    found: list[Any] = [named, Incident.created_by == me]
    if units:
        found.append(Incident.org_unit_id.in_(units))
    return or_(*found)


def can_add(principal: Principal, org_unit_id: int | None) -> bool:
    """Anyone signed in may report something, wherever it happened."""
    return principal.account_id is not None or principal.command


def can_edit(session: Session, principal: Principal, incident: Incident) -> bool:
    """Its handlers and those who triage for its unit correct it and name its handlers."""
    return triages(principal, incident.org_unit_id) or handles(session, principal, incident)


# --- The record type ----------------------------------------------------------------------


def _new(incident: Incident) -> None:
    incident.kind, incident.status, incident.anonymous = "incident", "reported", False


def _day(value: Any, field: str, errors: records.Errors) -> date | None:
    if value in (None, ""):
        return None
    try:
        day = value if isinstance(value, date) else date.fromisoformat(str(value))
    except ValueError:
        errors.add(field, "Give a date, as year-month-day.")
        return None
    if day > utc_now().date():
        errors.add(field, "That day has not come yet.")
        return None
    return day


def _apply(
    session: Session, incident: Incident, values: Mapping[str, Any], errors: records.Errors,
    creating: bool,
) -> None:  # fmt: skip
    if not creating and incident.status == "closed":
        errors.add("status", "This is closed. Reopen it to change it.")
        return
    if "kind" in values or creating:
        kind = values.get("kind") or "incident"
        if kind not in INCIDENT_KINDS:
            errors.add("kind", "Say whether it is an incident, a near miss, or a concern.")
        else:
            incident.kind = kind
    if "occurred_on" in values:
        incident.occurred_on = _day(values.get("occurred_on"), "occurred_on", errors)
    if "location" in values:
        location = records.text(values.get("location"))
        if location is not None and len(location) > 200:
            errors.add("location", "Keep it to 200 characters.")
        else:
            incident.location = location


def _cards(session: Session, rows: list[Incident]) -> list[dict[str, Any]]:
    return [
        {
            "kind": row.kind,
            "status": row.status,
            "category": row.category,
            "severity": row.severity,
            "occurred_on": row.occurred_on,
            "reported_at": row.created_at,
            "anonymous": row.anonymous,
            "triaged": row.triaged_at is not None,
            "closed_at": row.closed_at,
        }
        for row in rows
    ]


def subjects_of(session: Session, principal: Principal, incident: Incident) -> dict[str, Any]:
    """The records the incident concerns, as much as the person may see."""
    shown: list[dict[str, Any]] = []
    hidden = 0
    for link in session.scalars(
        select(IncidentSubject)
        .where(IncidentSubject.incident_id == incident.id)
        .order_by(IncidentSubject.id)
    ):
        record_type = _types().get(link.subject_type)
        subject = session.get(record_type.model, link.subject_id) if record_type else None
        if subject is None or record_type is None:
            continue
        if access.can_see(session, principal, record_type, subject):
            shown.append(records.chip(record_type, subject))
        else:
            hidden += 1
    return {"records": shown, "hidden": hidden}


def messages_of(
    session: Session, principal: Principal, incident: Incident, *, everything: bool
) -> list[dict[str, Any]]:
    statement = select(IncidentMessage).where(IncidentMessage.incident_id == incident.id)
    if not everything:
        statement = statement.where(IncidentMessage.shared.is_(True))
    return [
        {
            "id": row.id,
            "from_reporter": row.from_reporter,
            "shared": row.shared,
            "by": row.author_name,
            "at": row.created_at,
            "body": row.body,
            "mine": row.author_id is not None and row.author_id == principal.account_id,
        }
        for row in session.scalars(statement.order_by(IncidentMessage.created_at))
    ]


def _reporter(session: Session, incident: Incident) -> dict[str, Any] | None:
    if incident.anonymous or incident.created_by is None:
        return None
    account = session.get(Account, incident.created_by)
    return {"account_id": incident.created_by, "name": account.display_name if account else None}


def _detail(session: Session, principal: Principal, incident: Incident) -> dict[str, Any]:
    everything = knows_all(session, principal, incident)
    live = incident.status in LIVE
    triager = triages(principal, incident.org_unit_id)
    handler = handles(session, principal, incident)
    out: dict[str, Any] = {
        "occurred_on": incident.occurred_on,
        "location": incident.location,
        "everything": everything,
        "is_reporter": reported(principal, incident),
        "messages": messages_of(session, principal, incident, everything=everything),
        "can_act": {
            "triage": live and triager,
            "close": live and (triager or handler),
            "reopen": not live and triager,
            "message": live and (everything or reported(principal, incident)),
            "note": live and everything,
        },
    }
    if everything:
        out.update(
            reporter=_reporter(session, incident),
            triaged=(
                {"by": incident.triaged_by_name, "at": incident.triaged_at}
                if incident.triaged_at
                else None
            ),
            closure_note=incident.closure_note,
            subjects=subjects_of(session, principal, incident),
        )
    else:
        # What happened is the reporter's own; how it is handled is not.
        out["severity"] = None
    return out


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    status = filters.get("status")
    if status == "live":
        found.append(Incident.status.in_(LIVE))
    elif status in INCIDENT_STATUSES:
        found.append(Incident.status == status)
    if filters.get("reported_by_me"):
        found.append(Incident.created_by == principal.account_id)
    if filters.get("about"):
        try:
            record_type, subject = find_any(session, str(filters["about"]))
        except NotFound:
            return [Incident.id < 0]
        found.append(
            Incident.id.in_(
                select(IncidentSubject.incident_id).where(
                    IncidentSubject.subject_type == record_type.key,
                    IncidentSubject.subject_id == subject.id,
                )
            )
        )
    return found


def _history_title(event: Any, lookups: Any) -> str | None:
    changes = event.changes or {}

    def now(field: str) -> Any:
        pair = changes.get(field) or [None, None]
        return pair[1] if pair[1] is not None else pair[0]

    if event.subject_type == "incident_subject":
        name = lookups.name(now("subject_type"), now("subject_id"))
        return f"Now concerns {name}" if event.action == "created" else f"No longer concerns {name}"
    if event.subject_type == "incident_message" and event.action == "created":
        if now("from_reporter"):
            return "The reporter wrote"
        return "Wrote to the reporter" if now("shared") else "Added a note"
    return None


INCIDENT = register(
    RecordType(
        KEY,
        Incident,
        "INC",
        "incidents",
        "incident",
        "incidents",
        is_thing=False,
        sorts=("updated_at", "created_at", "name", "ref", "status"),
        filters=("kind", "category", "severity"),
        extra={
            "new": _new,
            "apply": _apply,
            "cards": _cards,
            "detail": _detail,
            "conditions": _conditions,
            "can_see": can_see,
            "visible": visible,
            "can_add": can_add,
            "can_edit": can_edit,
            "knows_all": knows_all,
            # Triage names who handles it, and each report is its own: none is a duplicate
            # to merge, and none waits on a steward to name its owner.
            "no_orphans": True,
            "no_duplicates": True,
            "live_statuses": LIVE,
            "history_title": _history_title,
            "history_vocabularies": {"category": "incident_categories"},
            "history_labels": {
                "occurred_on": "Happened on",
                "location": "Where",
                "triaged_at": "Triaged",
                "closure_note": "How it ended",
                "closed_at": "Closed",
            },
            "history_quiet": ("triaged_by", "triaged_by_name", "follow_up_hash", "anonymous"),
        },
    )
)


def _types() -> dict[str, RecordType]:
    from riskwren.inventory.registry import TYPES

    return {key: TYPES[key] for key in INCIDENT_SUBJECTS if key in TYPES}


# --- Reporting ----------------------------------------------------------------------------


def _home_unit(session: Session, principal: Principal) -> int | None:
    """Where something reported without a place is put until triage: the reporter's own
    unit, or the organization."""
    if principal.account_id is not None:
        for membership in accounts.memberships_of(session, principal.account_id):
            return membership.org_unit_id
    return top_unit(session)


def top_unit(session: Session) -> int | None:
    from riskwren.db.models import OrgUnit

    return session.scalars(
        select(OrgUnit.id).where(OrgUnit.parent_id.is_(None)).order_by(OrgUnit.id)
    ).first()


def create(
    session: Session,
    principal: Principal,
    values: Mapping[str, Any],
    *,
    anonymous: bool = False,
    follow_up_hash: str | None = None,
) -> Incident:
    """Report something. Its reporter is whoever reports it, unless it is reported without a
    name; it has no handler until it is triaged."""
    if not anonymous and not can_add(principal, None):
        raise PermissionDenied("Sign in to report something.")
    now = utc_now()
    incident = Incident(
        created_by=None if anonymous else principal.account_id,
        created_at=now,
        updated_at=now,
        tags=[],
        restricted=False,
        version=1,
    )
    _new(incident)
    errors = records.Errors()
    unit_given = values.get("org_unit_id")
    wanted = dict(values)
    if anonymous or unit_given in (None, ""):
        wanted["org_unit_id"] = top_unit(session) if anonymous else _home_unit(session, principal)
    records.apply_header(session, incident, wanted, errors, creating=True)
    _apply(session, incident, wanted, errors, creating=True)
    if not records.text(values.get("summary")):
        errors.add("summary", "Say what happened.")
    if errors:
        raise Invalid("The report was not sent.", errors)
    incident.anonymous = anonymous
    incident.follow_up_hash = follow_up_hash
    with audit.operation(session, "incident.report", anonymous=anonymous):
        incident.ref = next_ref(session, "INC")
        session.add(incident)
        session.flush()
    what = KIND_LABELS[incident.kind].lower()
    notices.tell_all(
        session,
        notices.holders(session, (roles.MANAGER, roles.ASSESSOR), incident.org_unit_id),
        "incident_reported",
        f"A new {what} to triage: {incident.ref}, {incident.name}",
        f"/incidents/{incident.ref}",
        by=None if anonymous else principal,
    )
    return incident


# --- Triage, closing, and reopening -------------------------------------------------------


def resolve_subjects(
    session: Session, principal: Principal, refs: list[str]
) -> tuple[set[tuple[str, int]], list[str]]:
    """The records named, by reference, and what is wrong with any of them."""
    problems: list[str] = []
    wanted: set[tuple[str, int]] = set()
    allowed = _types()
    for ref in dict.fromkeys(str(each).strip().upper() for each in refs if str(each).strip()):
        try:
            record_type, record = find_any(session, ref)
        except NotFound:
            problems.append(f"There is no record {ref}.")
            continue
        if record_type.key not in allowed or not access.can_see(
            session, principal, record_type, record
        ):
            problems.append(f"{ref} is not a record an incident can concern, or you cannot see it.")
            continue
        wanted.add((record_type.key, record.id))
    return wanted, problems


def set_subjects(
    session: Session, principal: Principal, incident: Incident, wanted: set[tuple[str, int]]
) -> None:
    """Make these the records the incident concerns. A record the person may not see stays:
    they cannot know it is there to take away."""
    allowed = _types()
    have = {
        (row.subject_type, row.subject_id): row
        for row in session.scalars(
            select(IncidentSubject).where(IncidentSubject.incident_id == incident.id)
        )
    }
    for key, row in have.items():
        record_type = allowed.get(key[0])
        record = session.get(record_type.model, key[1]) if record_type else None
        seen = record is not None and access.can_see(session, principal, record_type, record)
        if key not in wanted and seen:
            session.delete(row)
    for kind, identifier in sorted(wanted - set(have)):
        session.add(
            IncidentSubject(incident_id=incident.id, subject_type=kind, subject_id=identifier)
        )


def _set_handler(session: Session, incident: Incident, account_id: int) -> bool:
    """Make this person its handler, in place of any other; delegates stay. Returns whether
    the handler changed."""
    rows = session.scalars(
        select(RecordOwner).where(
            RecordOwner.record_type == KEY, RecordOwner.record_id == incident.id
        )
    ).all()
    owners = [row for row in rows if row.kind == records.OWNER]
    if [row.account_id for row in owners] == [account_id]:
        return False
    for row in owners:
        session.delete(row)
    for row in rows:
        if row.kind != records.OWNER and row.account_id == account_id:
            session.delete(row)
    session.flush()
    session.add(
        RecordOwner(
            record_type=KEY, record_id=incident.id, account_id=account_id, kind=records.OWNER
        )
    )
    return True


def triage(
    session: Session, principal: Principal, incident: Incident, values: Mapping[str, Any]
) -> Incident:
    """Give it a category, a severity, its unit, the records it concerns, and its handler."""
    if not triages(principal, incident.org_unit_id):
        raise PermissionDenied("Reports are triaged by managers and by assessors for the unit.")
    if incident.status not in LIVE:
        raise Conflict("This is closed. Reopen it to triage it again.")
    errors = records.Errors()
    category = records.choice(
        session, "incident_categories", values.get("category"), "category", errors, required=True
    )
    severity = records.text(values.get("severity"))
    if severity not in SEVERITIES:
        errors.add("severity", "Choose critical, high, moderate, or low.")
    unit_id = incident.org_unit_id
    if values.get("org_unit_id") not in (None, ""):
        unit_id = records.unit(session, values.get("org_unit_id"), errors) or unit_id
        if unit_id != incident.org_unit_id and not triages(principal, unit_id):
            errors.add("org_unit_id", "You triage only for units you assess.")
    handler = None
    raw = values.get("handler_id")
    if raw in (None, ""):
        errors.add("handler_id", "Name who handles it.")
    else:
        handler = session.get(Account, int(raw)) if str(raw).isdigit() else None
        if handler is None or handler.status == "disabled":
            errors.add("handler_id", "Choose someone whose account is not disabled.")
    wanted, problems = resolve_subjects(session, principal, list(values.get("subjects") or []))
    if problems:
        errors.add("subjects", " ".join(problems))
    if errors or handler is None or category is None:
        raise Invalid("It was not triaged.", errors)
    with audit.operation(session, "incident.triage"):
        set_subjects(session, principal, incident, wanted)
        first = incident.triaged_at is None
        incident.category, incident.severity, incident.org_unit_id = category, severity, unit_id
        incident.triaged_by, incident.triaged_by_name = principal.account_id, principal.name
        incident.triaged_at = utc_now()
        incident.status = "handling"
        changed = _set_handler(session, incident, handler.id)
        records.touch(session, incident)
        incident.updated_at = utc_now()
        session.flush()
    if changed:
        notices.tell(
            session, handler.id, "incident_handle",
            f"You handle {incident.ref}: {incident.name}", f"/incidents/{incident.ref}",
            by=principal,
        )  # fmt: skip
    if first and incident.created_by is not None:
        notices.tell(
            session, incident.created_by, "incident_update",
            f"What you reported is being handled: {incident.ref}", f"/incidents/{incident.ref}",
            by=principal,
        )  # fmt: skip
    return incident


def close(session: Session, principal: Principal, incident: Incident, note: Any) -> Incident:
    if not (triages(principal, incident.org_unit_id) or handles(session, principal, incident)):
        raise PermissionDenied("It is closed by its handlers, or by those who triage it.")
    if incident.status not in LIVE:
        raise Conflict("This is already closed.")
    said = records.text(note)
    if not said:
        raise Invalid("It was not closed.", {"note": "Say how it ended."})
    with audit.operation(session, "incident.close"):
        incident.status, incident.closure_note, incident.closed_at = "closed", said, utc_now()
        records.touch(session, incident)
    if incident.created_by is not None:
        notices.tell(
            session, incident.created_by, "incident_update",
            f"What you reported is closed: {incident.ref}", f"/incidents/{incident.ref}",
            by=principal,
        )  # fmt: skip
    return incident


def reopen(session: Session, principal: Principal, incident: Incident) -> Incident:
    if not triages(principal, incident.org_unit_id):
        raise PermissionDenied("It is reopened by those who triage it.")
    if incident.status in LIVE:
        raise Conflict("This is not closed.")
    with audit.operation(session, "incident.reopen"):
        incident.status = "handling" if incident.triaged_at else "reported"
        incident.closed_at = None
        records.touch(session, incident)
    return incident


# --- What is said -------------------------------------------------------------------------


def _body(value: Any) -> str:
    said = records.text(value)
    if not said:
        raise Invalid("Nothing was sent.", {"body": "Write something."})
    if len(said) > LONGEST_MESSAGE:
        raise Invalid("Nothing was sent.", {"body": f"Keep it to {LONGEST_MESSAGE} characters."})
    return said


def write(
    session: Session, principal: Principal, incident: Incident, body: Any, *, shared: bool
) -> IncidentMessage:
    """Write to the reporter (``shared``), or a note for those handling it. The reporter
    writes to those handling it."""
    said = _body(body)
    if incident.status not in LIVE:
        raise Conflict("This is closed. Reopen it to write about it.")
    everything = knows_all(session, principal, incident)
    from_reporter = reported(principal, incident) and not everything
    if not (everything or from_reporter):
        raise PermissionDenied("You cannot write about this.")
    if from_reporter:
        shared = True
    message = IncidentMessage(
        incident_id=incident.id, from_reporter=from_reporter, shared=shared,
        author_id=principal.account_id, author_name=principal.name, body=said,
        created_at=utc_now(),
    )  # fmt: skip
    with audit.operation(session, "incident.write"):
        session.add(message)
        records.touch(session, incident)
        incident.updated_at = utc_now()
        session.flush()
    href = f"/incidents/{incident.ref}"
    if from_reporter:
        notices.tell_all(
            session, notices.owners(session, KEY, incident.id), "incident_message",
            f"The reporter wrote about {incident.ref}", href, by=principal,
        )  # fmt: skip
    elif shared and incident.created_by is not None:
        notices.tell(
            session, incident.created_by, "incident_update",
            f"A message about what you reported: {incident.ref}", href, by=principal,
        )  # fmt: skip
    return message


def written_by_reporter(session: Session, incident: Incident, body: Any) -> IncidentMessage:
    """What a reporter without a name adds, through their code."""
    said = _body(body)
    if incident.status not in LIVE:
        raise Conflict("This is closed, so nothing more can be added to it.")
    message = IncidentMessage(
        incident_id=incident.id, from_reporter=True, shared=True, author_id=None,
        author_name="The reporter", body=said, created_at=utc_now(),
    )  # fmt: skip
    with audit.operation(session, "incident.write", anonymous=True):
        session.add(message)
        incident.updated_at = utc_now()
        session.flush()
    notices.tell_all(
        session, notices.owners(session, KEY, incident.id), "incident_message",
        f"The reporter wrote about {incident.ref}", f"/incidents/{incident.ref}",
    )  # fmt: skip
    return message


# --- What waits on someone ----------------------------------------------------------------


def waiting_on(session: Session, principal: Principal) -> list[tuple[Incident, str]]:
    """Reports to triage, and incidents the person handles that are not yet closed."""
    out: list[tuple[Incident, str]] = []
    if principal.assesses:
        units = principal.units_for(roles.MANAGER, roles.ASSESSOR)
        statement = select(Incident).where(Incident.status == "reported")
        if units is not None:
            statement = statement.where(Incident.org_unit_id.in_(units or [0]))
        for row in session.scalars(statement.order_by(Incident.created_at)):
            out.append((row, "triage"))
    if principal.account_id is not None:
        handled = select(RecordOwner.record_id).where(
            RecordOwner.record_type == KEY,
            RecordOwner.account_id == principal.account_id,
            RecordOwner.kind == records.OWNER,
        )
        for row in session.scalars(
            select(Incident)
            .where(Incident.id.in_(handled), Incident.status == "handling")
            .order_by(Incident.triaged_at)
        ):
            out.append((row, "handle"))
    return out
