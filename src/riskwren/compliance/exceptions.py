"""Exceptions: approved, time-limited departures from a control, a requirement, or a
document.

Someone asks, saying why and what makes up for it. Someone with authority over the unit who
did not ask decides. An approved exception runs from one date to another and no longer;
while it is in force what it covers is shown as *excepted*, and the day after it ends the
state underneath is back, without anyone doing anything. Carrying on needs a new request.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session

from riskwren.access import roles
from riskwren.access.principal import Principal
from riskwren.compliance import frameworks
from riskwren.compliance.scopes import SCOPE
from riskwren.controls.service import CONTROL
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    Control,
    ExceptionRequest,
    Framework,
    Implementation,
    PolicyDocument,
    RecordOwner,
    Requirement,
    Scope,
    ScopeFramework,
)
from riskwren.db.refs import next_ref
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.registry import RecordType, find, register
from riskwren.people import notices
from riskwren.policy import documents
from riskwren.policy.documents import DOCUMENT
from riskwren.program import rules

KEY = "exception"
SOON = 30  # days before it ends at which an exception is flagged to whoever asked for it
TRUSTED = (roles.STEWARD, roles.LEADER, roles.MANAGER)
DECIDERS = (roles.LEADER, roles.MANAGER)


# --- Who may see it, ask, and decide -------------------------------------------------------


def _in(units: frozenset[int] | None, unit: int) -> bool:
    return units is None or unit in units


def can_see(session: Session, principal: Principal, item: ExceptionRequest) -> bool:
    if principal.reads_all or _in(principal.units_for(*TRUSTED), item.org_unit_id):
        return True
    me = principal.account_id
    if me is not None and me in (item.requested_by, item.created_by):
        return True
    if access.owner_kinds(session, EXCEPTION, item.id, me):
        return True
    if item.restricted:
        return False
    return _in(principal.units_for(roles.ASSESSOR), item.org_unit_id)


def visible(session: Session, principal: Principal) -> Any:
    if principal.reads_all:
        return None
    trusted = principal.units_for(*TRUSTED)
    if trusted is None:
        return None
    me = principal.account_id
    named = exists(
        select(RecordOwner.id).where(
            RecordOwner.record_type == KEY,
            RecordOwner.record_id == ExceptionRequest.id,
            RecordOwner.account_id == me,
        )
    )
    found: list[Any] = [named, ExceptionRequest.requested_by == me]
    if trusted:
        found.append(ExceptionRequest.org_unit_id.in_(trusted))
    assessed = principal.units_for(roles.ASSESSOR)
    ordinary = ExceptionRequest.restricted.is_(False)
    if assessed is None:
        found.append(ordinary)
    elif assessed:
        found.append(and_(ordinary, ExceptionRequest.org_unit_id.in_(assessed)))
    return or_(*found)


def can_decide(session: Session, principal: Principal, item: ExceptionRequest) -> bool:
    """A leader or a manager with authority over the unit, who did not ask for it."""
    me = principal.account_id
    has_authority = principal.leads_unit(item.org_unit_id) or principal.manages_unit(
        item.org_unit_id
    )
    return has_authority and (me is None or me != item.requested_by)


def _can_edit(session: Session, principal: Principal, item: ExceptionRequest) -> bool:
    """A request can be reworded by whoever asked, until it is decided."""
    return item.status == "requested" and (
        principal.account_id == item.requested_by
        or principal.manages_unit(item.org_unit_id)
        or principal.stewards_unit(item.org_unit_id)
    )


# --- Dates --------------------------------------------------------------------------------


def max_months(session: Session) -> int:
    return int(rules.get(session, "cadences").get("exception_max_months", 12))


def state_of(item: ExceptionRequest, today: date | None = None) -> str:
    """requested, refused, withdrawn, or, once approved: upcoming, in_force, expiring, expired."""
    if item.status != "approved":
        return item.status
    today = today or utc_now().date()
    if today < item.starts_on:
        return "upcoming"
    if today > item.expires_on:
        return "expired"
    return "expiring" if (item.expires_on - today).days <= SOON else "in_force"


def is_in_force(item: ExceptionRequest, today: date | None = None) -> bool:
    return state_of(item, today) in ("in_force", "expiring")


def _day(value: Any, field: str, errors: records.Errors) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        errors.add(field, "Give a date, as year-month-day.")
        return None


def _dates(
    session: Session, item: ExceptionRequest, values: Mapping[str, Any], errors: records.Errors
) -> None:
    if "starts_on" in values:
        item.starts_on = _day(values["starts_on"], "starts_on", errors) or utc_now().date()
    if "expires_on" in values:
        ends = _day(values["expires_on"], "expires_on", errors)
        if ends is None and "expires_on" not in errors:
            errors.add("expires_on", "Say when it ends. An exception is never open-ended.")
        elif ends is not None:
            item.expires_on = ends
    if item.starts_on is None or item.expires_on is None or errors:
        return
    longest = rules.add_months(item.starts_on, max_months(session))
    if item.expires_on <= item.starts_on:
        errors.add("expires_on", "It ends before it begins.")
    elif item.expires_on > longest:
        errors.add(
            "expires_on",
            f"An exception runs for at most {max_months(session)} months: "
            f"to {longest.isoformat()} at the latest. After that it is asked for again.",
        )


# --- The record type ----------------------------------------------------------------------


def _apply(
    session: Session, item: ExceptionRequest, values: Mapping[str, Any], errors: records.Errors,
    creating: bool,
) -> None:  # fmt: skip
    if not creating and item.status != "requested":
        errors.add("status", "This request has been decided. Ask again to change it.")
        return
    if "justification" in values or creating:
        why = records.text(values.get("justification"))
        if not why:
            errors.add("justification", "Say why the departure is needed.")
        else:
            item.justification = why
    if "compensating" in values:
        item.compensating = records.text(values["compensating"])
    if creating or {"starts_on", "expires_on"} & set(values):
        _dates(session, item, values, errors)


def subject_of(session: Session, principal: Principal, item: ExceptionRequest) -> dict[str, Any]:
    """What the exception covers, as much of it as the person may see."""
    if item.subject_type == "requirement":
        requirement = session.get(Requirement, item.subject_id)
        framework = session.get(Framework, requirement.framework_id) if requirement else None
        if requirement is None or framework is None:
            return {"type": "requirement", "name": "A requirement that is no longer on record"}
        return {
            "type": "requirement",
            "framework": {"key": framework.key, "title": framework.title},
            "code": requirement.code,
            "name": requirement.title or requirement.code,
        }
    if item.subject_type == "document":
        document = session.get(PolicyDocument, item.subject_id)
        if document is None:
            return {"type": "document", "name": "A document that is no longer on record"}
        return {
            **records.chip(DOCUMENT, document),
            "kind": document.kind,
            "open": access.can_see(session, principal, DOCUMENT, document),
        }
    control = session.get(Control, item.subject_id)
    if control is None:
        return {"type": "control", "name": "A control that is no longer on record"}
    return {
        **records.chip(CONTROL, control),
        "open": access.can_see(session, principal, CONTROL, control),
    }


def _scope_chip(session: Session, item: ExceptionRequest) -> dict[str, Any] | None:
    scope = session.get(Scope, item.scope_id) if item.scope_id else None
    return {"ref": scope.ref, "name": scope.name} if scope else None


def _cards(session: Session, rows: list[ExceptionRequest]) -> list[dict[str, Any]]:
    reader = Principal.for_command()
    return [
        {
            "status": row.status,
            "state": state_of(row),
            "subject": {
                key: value
                for key, value in subject_of(session, reader, row).items()
                if key != "open"
            },
            "scope": _scope_chip(session, row),
            "starts_on": row.starts_on,
            "expires_on": row.expires_on,
            "requested_by": row.requested_by_name,
            "requested_at": row.requested_at,
            "decided_by": row.decided_by_name,
        }
        for row in rows
    ]


def _detail(session: Session, principal: Principal, item: ExceptionRequest) -> dict[str, Any]:
    renews = session.get(ExceptionRequest, item.renews_id) if item.renews_id else None
    renewal = session.scalars(
        select(ExceptionRequest)
        .where(ExceptionRequest.renews_id == item.id, ExceptionRequest.status != "withdrawn")
        .order_by(ExceptionRequest.id.desc())
    ).first()
    mine = principal.account_id is not None and principal.account_id == item.requested_by
    state = state_of(item)
    return {
        "subject": subject_of(session, principal, item),
        "justification": item.justification,
        "compensating": item.compensating,
        "decided_at": item.decided_at,
        "decision_note": item.decision_note,
        "max_months": max_months(session),
        "renews": {"ref": renews.ref, "expires_on": renews.expires_on} if renews else None,
        "renewed_by": {"ref": renewal.ref, "status": renewal.status} if renewal else None,
        "can_act": {
            "decide": item.status == "requested" and can_decide(session, principal, item),
            "asked": mine,
            "withdraw": state in ("requested", "upcoming", "in_force", "expiring")
            and (mine or can_decide(session, principal, item)),
            "renew": state in ("in_force", "expiring", "expired")
            and renewal is None
            and may_ask(session, principal, item.org_unit_id, _subject_record(session, item)),
        },
    }


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    today = utc_now().date()
    approved = ExceptionRequest.status == "approved"
    state = filters.get("state")
    if state == "in_force":
        found += [
            approved,
            ExceptionRequest.starts_on <= today,
            ExceptionRequest.expires_on >= today,
        ]
    elif state == "expiring":
        found += [
            approved,
            ExceptionRequest.starts_on <= today,
            ExceptionRequest.expires_on >= today,
            ExceptionRequest.expires_on <= today + timedelta(days=SOON),
        ]
    elif state == "expired":
        found += [approved, ExceptionRequest.expires_on < today]
    elif state in ("requested", "refused", "withdrawn"):
        found.append(ExceptionRequest.status == state)
    if filters.get("scope"):
        try:
            scope = find(session, SCOPE, str(filters["scope"]))
        except NotFound:
            return [ExceptionRequest.id < 0]
        found.append(ExceptionRequest.scope_id == scope.id)
    if filters.get("document"):
        try:
            document = find(session, DOCUMENT, str(filters["document"]))
        except NotFound:
            return [ExceptionRequest.id < 0]
        found += [
            ExceptionRequest.subject_type == "document",
            ExceptionRequest.subject_id == document.id,
        ]
    if filters.get("about") in ("control", "requirement", "document"):
        found.append(ExceptionRequest.subject_type == filters["about"])
    if filters.get("framework"):
        from riskwren.db.models import Framework, Requirement

        found += [
            ExceptionRequest.subject_type == "requirement",
            ExceptionRequest.subject_id.in_(
                select(Requirement.id)
                .join(Framework, Framework.id == Requirement.framework_id)
                .where(Framework.key == str(filters["framework"]))
            ),
        ]
    return found


EXCEPTION = register(
    RecordType(
        KEY,
        ExceptionRequest,
        "EXC",
        "exceptions",
        "exception",
        "exceptions",
        is_thing=False,
        sorts=("updated_at", "name", "ref", "status", "expires_on"),
        extra={
            "apply": _apply,
            "cards": _cards,
            "detail": _detail,
            "conditions": _conditions,
            "can_see": can_see,
            "visible": visible,
            "can_edit": _can_edit,
            "history_labels": {
                "justification": "Why it is needed",
                "compensating": "What makes up for it",
                "starts_on": "From",
                "expires_on": "Until",
                "decision_note": "Decision note",
            },
            "history_quiet": (
                "decided_by", "decided_by_name", "decided_at", "requested_by",
                "requested_by_name", "requested_at", "subject_type", "subject_id", "scope_id",
                "renews_id",
            ),
        },
    )
)  # fmt: skip


# --- Asking -------------------------------------------------------------------------------


def _subject_record(session: Session, item: ExceptionRequest) -> Any:
    """The record whose keepers may ask: the document it departs from, the scope it applies
    in, or else the control."""
    if item.subject_type == "document":
        return (DOCUMENT, session.get(PolicyDocument, item.subject_id))
    if item.scope_id:
        return (SCOPE, session.get(Scope, item.scope_id))
    return (CONTROL, session.get(Control, item.subject_id))


def may_ask_document(
    session: Session, principal: Principal, document: PolicyDocument, scope: Scope | None = None
) -> bool:
    """Anyone who keeps a unit (its steward, leader, or manager) may ask to depart from a
    document, as may those who keep the document or the scope it would apply in. It is
    decided by a leader or manager of the document's own unit."""
    if principal.stewards or principal.leads or principal.manages_somewhere:
        return True
    if documents.can_edit(session, principal, document):
        return True
    return scope is not None and access.can_edit(session, principal, SCOPE, scope)


def may_ask(session: Session, principal: Principal, org_unit_id: int, about: Any) -> bool:
    """An exception is asked for by those who keep the scope or the control it is about."""
    record_type, record = about
    if record_type is DOCUMENT:
        return record is not None and may_ask_document(session, principal, record)
    if principal.manages_unit(org_unit_id) or principal.stewards_unit(org_unit_id):
        return True
    return record is not None and access.can_edit(session, principal, record_type, record)


def request(session: Session, principal: Principal, values: Mapping[str, Any]) -> ExceptionRequest:
    """Ask for an exception to a control, to a requirement within a scope, or to a document.

    ``values``: ``control`` (a reference), ``requirement`` (``{"framework", "code"}``), or
    ``document`` (a reference), ``scope`` (a reference; needed for a requirement, and where an
    exception to a document applies, if it is given), ``justification``, ``compensating``,
    ``starts_on``, ``expires_on``, and ``renews`` (the exception this one carries on from).
    """
    errors = records.Errors()
    scope: Scope | None = None
    control: Control | None = None
    requirement: Requirement | None = None
    document: PolicyDocument | None = None
    earlier: ExceptionRequest | None = None
    if values.get("renews"):
        try:
            earlier = records.load(session, principal, EXCEPTION, str(values["renews"]))
        except NotFound:
            errors.add("renews", f"There is no exception {values['renews']}.")
        else:
            if earlier.status != "approved":
                errors.add("renews", "Only an approved exception can be renewed.")
    if earlier is not None and "renews" not in errors:
        scope = session.get(Scope, earlier.scope_id) if earlier.scope_id else None
        if earlier.subject_type == "control":
            control = session.get(Control, earlier.subject_id)
        elif earlier.subject_type == "document":
            document = session.get(PolicyDocument, earlier.subject_id)
        else:
            requirement = session.get(Requirement, earlier.subject_id)
    else:
        if values.get("scope"):
            try:
                scope = records.load(session, principal, SCOPE, str(values["scope"]))
            except NotFound as missing:
                errors.add("scope", str(missing))
        if values.get("control"):
            try:
                # A control a scope inherits is known there by name, whoever may open it, so
                # within a scope it is enough that the scope uses it (checked below).
                control = (
                    find(session, CONTROL, str(values["control"]))
                    if scope is not None
                    else records.load(session, principal, CONTROL, str(values["control"]))
                )
            except NotFound as missing:
                errors.add("control", str(missing))
        elif values.get("requirement"):
            given = values["requirement"]
            try:
                framework = frameworks.by_key(session, str(given.get("framework", "")))
                requirement = frameworks.find(session, framework, str(given.get("code", "")))
            except NotFound as missing:
                errors.add("requirement", str(missing))
        elif values.get("document"):
            try:
                document = records.load(session, principal, DOCUMENT, str(values["document"]))
            except NotFound as missing:
                errors.add("document", str(missing))
            else:
                if document.status != "active" or document.published_version_id is None:
                    errors.add("document", "Nothing of that document is in force to depart from.")
        elif "control" not in errors:
            errors.add(
                "control", "Say which control, requirement, or document it is an exception to."
            )
    if requirement is not None:
        held = (
            scope is not None
            and session.scalars(
                select(ScopeFramework.id).where(
                    ScopeFramework.scope_id == scope.id,
                    ScopeFramework.framework_id == requirement.framework_id,
                )
            ).first()
        )
        if scope is None:
            errors.add("scope", "An exception to a requirement is within a scope. Say which.")
        elif not held:
            errors.add("scope", "That scope is not held to the requirement's framework.")
    if control is not None and scope is not None:
        used = session.scalars(
            select(Implementation.id).where(
                Implementation.scope_id == scope.id, Implementation.control_id == control.id
            )
        ).first()
        if used is None:
            errors.add("scope", "That scope does not use the control.")
    now = utc_now()
    item = ExceptionRequest(
        status="requested",
        requested_by=principal.account_id,
        requested_by_name=principal.name,
        requested_at=now,
        starts_on=now.date(),
        tags=[],
        restricted=False,
        version=1,
        created_by=principal.account_id,
        created_at=now,
        updated_at=now,
    )
    _apply(session, item, {"starts_on": None, "expires_on": None, **values}, errors, creating=True)
    if errors:
        raise Invalid("The exception was not requested.", errors)
    assert control is not None or requirement is not None or document is not None
    if document is not None:
        # Departing from a document is for the leaders of the unit that keeps it to decide.
        owner_unit = document.org_unit_id
        if not may_ask_document(session, principal, document, scope):
            raise PermissionDenied(
                "An exception to a document is asked for by a unit's steward, leader, or "
                "manager, or by those who keep the document."
            )
    else:
        owner_unit = scope.org_unit_id if scope is not None else control.org_unit_id  # type: ignore[union-attr]
        about = (SCOPE, scope) if scope is not None else (CONTROL, control)
        if not may_ask(session, principal, owner_unit, about):
            raise PermissionDenied(
                "An exception is asked for by those who keep the scope or the control it is about."
            )
    if document is not None:
        item.subject_type, item.subject_id, covered = "document", document.id, document.name
    elif control is not None:
        item.subject_type, item.subject_id, covered = "control", control.id, control.name
    else:
        assert requirement is not None
        item.subject_type, item.subject_id = "requirement", requirement.id
        covered = f"{requirement.code} {requirement.title or ''}".strip()
    where = f" in {scope.name}" if scope is not None else ""
    item.name = (records.text(values.get("name")) or f"{covered}{where}")[:200]
    item.scope_id = scope.id if scope is not None else None
    item.org_unit_id = owner_unit
    item.renews_id = earlier.id if earlier is not None else None
    with audit.operation(session, "exception.request"):
        item.ref = next_ref(session, EXCEPTION.prefix)
        session.add(item)
        session.flush()
        if principal.person is not None:
            session.add(
                RecordOwner(
                    record_type=KEY, record_id=item.id, account_id=principal.person,
                    kind="owner",
                )
            )  # fmt: skip
        session.flush()
        notices.tell_all(
            session, notices.holders(session, DECIDERS, owner_unit), "exception",
            f"{principal.name} asks for an exception: {item.name} ({item.ref})",
            f"/exceptions/{item.ref}", by=principal,
        )  # fmt: skip
    return item


# --- Deciding -----------------------------------------------------------------------------


def decide(
    session: Session,
    principal: Principal,
    item: ExceptionRequest,
    *,
    approve: bool,
    note: str | None,
    expires_on: Any = None,
) -> ExceptionRequest:
    """Approve or refuse a request. Whoever asked does not decide. Approving may shorten it."""
    if item.status != "requested":
        raise Conflict("This request has already been decided.")
    if principal.account_id is not None and principal.account_id == item.requested_by:
        raise PermissionDenied("Nobody approves an exception they asked for.")
    if not can_decide(session, principal, item):
        raise PermissionDenied(
            "An exception is decided by a leader or a manager with authority over the unit."
        )
    errors = records.Errors()
    said = records.text(note)
    if not approve and not said:
        errors.add("note", "Say why it is refused.")
    if approve and expires_on not in (None, ""):
        _dates(session, item, {"expires_on": expires_on}, errors)
    if approve and not errors and item.expires_on < utc_now().date():
        errors.add("expires_on", "It would already have ended. Give a later date, or refuse it.")
    if errors:
        session.expire(item)
        raise Invalid("The decision was not recorded.", errors)
    with audit.operation(session, "exception.decide"):
        item.status = "approved" if approve else "refused"
        item.decided_by, item.decided_by_name = principal.account_id, principal.name
        item.decided_at, item.decision_note = utc_now(), said
        records.touch(session, item)
        session.flush()
        told = (
            f"{item.ref} was approved by {principal.name}, until {item.expires_on.isoformat()}"
            if approve
            else f"{item.ref} was refused by {principal.name}: {said}"
        )
        notices.tell(
            session, item.requested_by, "exception", told, f"/exceptions/{item.ref}", by=principal
        )
    return item


def withdraw(
    session: Session, principal: Principal, item: ExceptionRequest, *, reason: str | None
) -> ExceptionRequest:
    """Take back a request, or end an approved exception early."""
    mine = principal.account_id is not None and principal.account_id == item.requested_by
    if not (mine or can_decide(session, principal, item)):
        raise PermissionDenied(
            "An exception is withdrawn by whoever asked for it, or by someone who could decide it."
        )
    if state_of(item) not in ("requested", "upcoming", "in_force", "expiring"):
        raise Conflict("There is nothing in force to withdraw.")
    why = records.text(reason)
    if item.status == "approved" and not why:
        raise Invalid("It was not withdrawn.", {"reason": "Say why it ends early."})
    with audit.operation(session, "exception.withdraw"):
        item.status = "withdrawn"
        item.decision_note = why or item.decision_note
        records.touch(session, item)
        session.flush()
        notices.tell(
            session, item.requested_by, "exception",
            f"{item.ref} was withdrawn by {principal.name}", f"/exceptions/{item.ref}",
            by=principal,
        )  # fmt: skip
    return item


# --- What is in force ---------------------------------------------------------------------


def chip(item: ExceptionRequest) -> dict[str, Any]:
    return {"ref": item.ref, "expires_on": item.expires_on, "state": state_of(item)}


def in_force_for(
    session: Session, scope: Scope, today: date | None = None
) -> dict[str, dict[int, ExceptionRequest]]:
    """The exceptions that count in a scope today: to its requirements, and to the controls
    it uses, whether asked for here, for the control wherever it is relied on, or in the
    scope that provides it."""
    today = today or utc_now().date()
    providers: dict[int, int] = {}
    used = session.scalars(select(Implementation).where(Implementation.scope_id == scope.id)).all()
    for row in used:
        if row.inherits_from_id is not None:
            provider = session.get(Implementation, row.inherits_from_id)
            if provider is not None:
                providers[row.control_id] = provider.scope_id
    found: dict[str, dict[int, ExceptionRequest]] = {"requirement": {}, "control": {}}
    rows = session.scalars(
        select(ExceptionRequest)
        .where(
            ExceptionRequest.status == "approved",
            ExceptionRequest.starts_on <= today,
            ExceptionRequest.expires_on >= today,
            or_(
                ExceptionRequest.scope_id == scope.id,
                and_(
                    ExceptionRequest.subject_type == "control",
                    ExceptionRequest.subject_id.in_([row.control_id for row in used] or [0]),
                ),
            ),
        )
        .order_by(ExceptionRequest.expires_on)
    )
    for item in rows:
        if item.subject_type == "document":
            continue  # a departure from a document does not change how a scope stands
        if item.subject_type == "requirement":
            found["requirement"][item.subject_id] = item
        elif item.scope_id in (None, scope.id, providers.get(item.subject_id)):
            found["control"][item.subject_id] = item
    return found


def waiting_on(session: Session, principal: Principal) -> list[dict[str, Any]]:
    """Requests that wait for this person's decision, and their own exceptions about to end."""
    me = principal.account_id
    if me is None:
        return []
    found: list[dict[str, Any]] = []
    deciding = principal.units_for(*DECIDERS)
    if deciding is None or deciding:
        statement = select(ExceptionRequest).where(
            ExceptionRequest.status == "requested", ExceptionRequest.requested_by != me
        )
        if deciding is not None:
            statement = statement.where(ExceptionRequest.org_unit_id.in_(deciding))
        for item in session.scalars(statement.order_by(ExceptionRequest.requested_at).limit(25)):
            found.append({"kind": "decide", "exception": item})
    for item in session.scalars(
        select(ExceptionRequest).where(
            ExceptionRequest.requested_by == me, ExceptionRequest.status == "approved"
        )
    ):
        renewed = session.scalars(
            select(ExceptionRequest.id).where(
                ExceptionRequest.renews_id == item.id, ExceptionRequest.status != "withdrawn"
            )
        ).first()
        if state_of(item) == "expiring" and renewed is None:
            found.append({"kind": "renew", "exception": item})
    return found
