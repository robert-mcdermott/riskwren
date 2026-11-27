"""Agreements: what the organization has promised others, with its dates (CMP-12).

An agreement is with someone (its parties), runs from one date to another, may need notice
some days before it ends, and covers systems, information, and scopes. The requirements it
imposes are a framework: one the organization entered from the agreement's terms, or a
published one the agreement names. Every scope that holds what an agreement covers is held
to that framework for as long as the agreement is open, and is said to be so because of it.

Its owners are warned before the date by which notice must be given, and before it ends. An
agreement that has ended stays open until someone closes it or records its new end date, so
that nothing it imposed drops out of the scopes unnoticed.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    Agreement,
    AgreementCoverage,
    Framework,
    RecordOwner,
    Requirement,
    Scope,
    ScopeFramework,
    ScopeMember,
)
from riskwren.db.models.agreements import AGREEMENT_KINDS, COVERED
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.completeness import Expected
from riskwren.inventory.registry import TYPES, RecordType, find, register

KEY = "agreement"
NOTICE_SOON = 30  # days before the notice date at which its owners are warned
ENDING_SOON = 60  # days before it ends at which its owners are warned
LONGEST_NOTICE = 730
KIND_WORDS = {
    "award": "Award terms", "data_use": "Data use agreement",
    "business_associate": "Business associate agreement", "contract": "Contract",
    "confidentiality": "Confidentiality agreement", "memorandum": "Memorandum of understanding",
    "other": "Agreement",
}  # fmt: skip


# --- Who may add and change one -----------------------------------------------------------


def can_add(principal: Principal, org_unit_id: int | None) -> bool:
    return (
        principal.stewards_unit(org_unit_id)
        or principal.leads_unit(org_unit_id)
        or principal.manages_unit(org_unit_id)
    )


def can_edit(session: Session, principal: Principal, agreement: Agreement) -> bool:
    """Its owners and delegates, and the steward, leader, or manager of its unit."""
    if can_add(principal, agreement.org_unit_id):
        return True
    kinds = access.owner_kinds(session, AGREEMENT, agreement.id, principal.account_id)
    return bool(kinds & set(access.EDITING_KINDS))


# --- Dates --------------------------------------------------------------------------------


def notice_on(agreement: Agreement) -> date | None:
    """The last day on which notice can be given, to end it or to keep it going."""
    if agreement.ends_on is None or not agreement.notice_days:
        return None
    return agreement.ends_on - timedelta(days=agreement.notice_days)


def state_of(agreement: Agreement, today: date | None = None) -> str:
    """closed, upcoming, ended, notice (its notice date is near), ending, or in_force."""
    today = today or utc_now().date()
    if agreement.status == "closed":
        return "closed"
    if agreement.starts_on is not None and agreement.starts_on > today:
        return "upcoming"
    if agreement.ends_on is not None and agreement.ends_on < today:
        return "ended"
    notice = notice_on(agreement)
    if notice is not None and today <= notice <= today + timedelta(days=NOTICE_SOON):
        return "notice"
    if agreement.ends_on is not None and agreement.ends_on <= today + timedelta(days=ENDING_SOON):
        return "ending"
    return "in_force"


def _day(value: Any, field: str, errors: records.Errors) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        errors.add(field, "Give a date as YYYY-MM-DD.")
        return None


# --- Its facts ----------------------------------------------------------------------------


def _new(agreement: Agreement) -> None:
    agreement.status, agreement.renews = "active", False


def _apply(
    session: Session, agreement: Agreement, values: Mapping[str, Any], errors: records.Errors,
    creating: bool,
) -> None:  # fmt: skip
    if "kind" in values or creating:
        kind = values.get("kind")
        if kind not in AGREEMENT_KINDS:
            errors.add("kind", "Say what kind of agreement it is.")
        else:
            agreement.kind = kind
    if "parties" in values or creating:
        parties = records.text(values.get("parties"))
        if not parties:
            errors.add("parties", "Say who it is with.")
        elif len(parties) > 300:
            errors.add("parties", "Keep this to 300 characters.")
        else:
            agreement.parties = parties
    if "reference" in values:
        reference = records.text(values.get("reference"))
        if reference and len(reference) > 120:
            errors.add("reference", "Keep this to 120 characters.")
        else:
            agreement.reference = reference
    if "url" in values:
        agreement.url = records.url(values.get("url"), "url", errors)
    for field in ("starts_on", "ends_on"):
        if field in values:
            setattr(agreement, field, _day(values.get(field), field, errors))
    if (
        agreement.starts_on is not None
        and agreement.ends_on is not None
        and agreement.ends_on < agreement.starts_on
        and "ends_on" not in errors
    ):
        errors.add("ends_on", "It cannot end before it starts.")
    if "notice_days" in values:
        given = values.get("notice_days")
        if given in (None, ""):
            agreement.notice_days = None
        else:
            try:
                days = int(given)
            except (TypeError, ValueError):
                days = -1
            if not 0 <= days <= LONGEST_NOTICE:
                errors.add("notice_days", f"Give a number of days from 0 to {LONGEST_NOTICE}.")
            else:
                agreement.notice_days = days or None
    if agreement.notice_days and agreement.ends_on is None and "notice_days" not in errors:
        errors.add("notice_days", "Notice is counted back from the date it ends. Give that date.")
    if "renews" in values and values.get("renews") is not None:
        agreement.renews = bool(values["renews"])
    if "framework" in values:
        key = records.text(values.get("framework"))
        if not key:
            agreement.framework_id = None
        else:
            framework = session.scalars(select(Framework).where(Framework.key == key)).first()
            if framework is None:
                errors.add("framework", f"There is no framework {key}.")
            elif framework.status != "active":
                errors.add("framework", f"{framework.title} is retired.")
            else:
                agreement.framework_id = framework.id


def _framework_chip(framework: Framework | None) -> dict[str, Any] | None:
    if framework is None:
        return None
    return {
        "key": framework.key, "title": framework.title, "kind": framework.kind,
        "requirements": framework.citable_count, "status": framework.status,
    }  # fmt: skip


def _cards(session: Session, rows: list[Agreement]) -> list[dict[str, Any]]:
    today = utc_now().date()
    ids = [row.id for row in rows] or [0]
    covered: dict[int, int] = {}
    for agreement_id in session.scalars(
        select(AgreementCoverage.agreement_id).where(AgreementCoverage.agreement_id.in_(ids))
    ):
        covered[agreement_id] = covered.get(agreement_id, 0) + 1
    frameworks = {
        row.id: row
        for row in session.scalars(
            select(Framework).where(
                Framework.id.in_([row.framework_id for row in rows if row.framework_id] or [0])
            )
        )
    }
    return [
        {
            "kind": row.kind,
            "parties": row.parties,
            "reference": row.reference,
            "status": row.status,
            "starts_on": row.starts_on,
            "ends_on": row.ends_on,
            "notice_on": notice_on(row),
            "renews": row.renews,
            "state": state_of(row, today),
            "framework": _framework_chip(frameworks.get(row.framework_id or 0)),
            "covers": covered.get(row.id, 0),
        }
        for row in rows
    ]


def covers(session: Session, principal: Principal, agreement: Agreement) -> dict[str, Any]:
    """What it covers, as much as the person may see; the rest is counted."""
    shown, hidden = [], 0
    for row in session.scalars(
        select(AgreementCoverage)
        .where(AgreementCoverage.agreement_id == agreement.id)
        .order_by(AgreementCoverage.subject_type, AgreementCoverage.id)
    ):
        record_type = TYPES[row.subject_type]
        record = session.get(record_type.model, row.subject_id)
        if record is None:
            continue
        if not access.can_see(session, principal, record_type, record):
            hidden += 1
            continue
        shown.append(records.chip(record_type, record))
    return {"records": shown, "hidden": hidden}


def scopes_holding(session: Session, agreement: Agreement) -> list[dict[str, Any]]:
    """The scopes bound by its terms: those it covers and those that hold what it covers,
    each saying whether it is held to them because of this agreement or already was."""
    from riskwren.compliance.scopes import SCOPE  # it builds on this module

    if agreement.framework_id is None or agreement.status != "active":
        return []
    bound = {
        scope_id for (scope_id, framework_id) in _wanted(session, only=agreement.id)
        if framework_id == agreement.framework_id
    }  # fmt: skip
    rows = {
        row.scope_id: row
        for row in session.scalars(
            select(ScopeFramework).where(
                ScopeFramework.framework_id == agreement.framework_id,
                ScopeFramework.scope_id.in_(bound or {0}),
            )
        )
    }
    found = []
    for scope in session.scalars(
        select(Scope).where(Scope.id.in_(bound or {0})).order_by(Scope.name)
    ):
        row = rows.get(scope.id)
        found.append({
            **records.chip(SCOPE, scope),
            "because": row is not None and row.agreement_id == agreement.id,
        })  # fmt: skip
    return found


def _detail(session: Session, principal: Principal, agreement: Agreement) -> dict[str, Any]:
    editable = can_edit(session, principal, agreement)
    framework = session.get(Framework, agreement.framework_id) if agreement.framework_id else None
    return {
        "url": agreement.url,
        "notice_days": agreement.notice_days,
        "closed_on": agreement.closed_on,
        "closed_note": agreement.closed_note,
        "kind_label": KIND_WORDS.get(agreement.kind, agreement.kind),
        "covered": covers(session, principal, agreement),
        "terms": _framework_chip(framework),
        "scopes": scopes_holding(session, agreement),
        "can": {
            "edit": editable and agreement.status == "active",
            "close": editable and agreement.status == "active",
            "reopen": editable and agreement.status == "closed",
        },
    }


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    model = Agreement
    today = utc_now().date()
    if filters.get("kind") in AGREEMENT_KINDS:
        found.append(model.kind == filters["kind"])
    # Open agreements unless closed ones are asked for: one closed binds nothing.
    status = filters.get("status")
    if status in ("active", "closed"):
        found.append(model.status == status)
    elif status != "all" and filters.get("state") != "closed" and not filters.get("anywhere"):
        found.append(model.status == "active")
    state = filters.get("state")
    active = model.status == "active"
    if state == "ended":
        found += [active, model.ends_on < today]
    elif state == "ending":
        found += [
            active,
            model.ends_on >= today,
            model.ends_on <= today + timedelta(days=ENDING_SOON),
        ]
    elif state == "upcoming":
        found += [active, model.starts_on > today]
    elif state == "in_force":
        found += [
            active,
            or_(model.starts_on.is_(None), model.starts_on <= today),
            or_(model.ends_on.is_(None), model.ends_on >= today),
        ]
    elif state == "closed":
        found.append(model.status == "closed")
    if filters.get("framework"):
        found.append(
            model.framework_id.in_(
                select(Framework.id).where(Framework.key == str(filters["framework"]))
            )
        )
    if filters.get("covers"):
        try:
            subject_type, subject = _subject(session, str(filters["covers"]))
        except NotFound:
            return [model.id < 0]
        found.append(
            exists(
                select(AgreementCoverage.id).where(
                    AgreementCoverage.agreement_id == model.id,
                    AgreementCoverage.subject_type == subject_type,
                    AgreementCoverage.subject_id == subject.id,
                )
            )
        )
    return found


def _covers_nothing(model: Any) -> Any:
    return ~exists(select(AgreementCoverage.id).where(AgreementCoverage.agreement_id == model.id))


def _history_title(event: Any, lookups: Any) -> str | None:
    context = event.context or {}
    op = context.get("op")
    if event.subject_type == "agreement_coverage":
        what = context.get("what") or "a record"
        return f"Now covers {what}" if event.action == "created" else f"No longer covers {what}"
    if op == "agreement.close":
        note = context.get("note")
        return f"Closed it: {note}" if note else "Closed it"
    if op == "agreement.reopen":
        return "Opened it again"
    return None


AGREEMENT = register(
    RecordType(
        KEY,
        Agreement,
        "AGR",
        "agreements",
        "agreement",
        "agreements",
        is_thing=False,
        sorts=("updated_at", "name", "ref", "kind", "ends_on"),
        filters=("kind",),
        extra={
            "new": _new,
            "apply": _apply,
            "cards": _cards,
            "detail": _detail,
            "conditions": _conditions,
            "can_add": can_add,
            "can_edit": can_edit,
            "updated": lambda session, principal, agreement: sync(session),
            "add_refusal": "Agreements are added by a unit's steward or leader, or by a manager.",
            "expected": [
                Expected(
                    "covers",
                    "what it covers",
                    _covers_nothing,
                    "Nobody can tell which systems, information, or scopes it binds.",
                ),
            ],
            "live_statuses": ("active",),
            "history_title": _history_title,
            "history_keeps_titled": True,
            "history_labels": {
                "kind": "Kind",
                "parties": "With",
                "reference": "Their reference",
                "url": "Where the signed copy is kept",
                "starts_on": "Starts",
                "ends_on": "Ends",
                "notice_days": "Notice (days)",
                "renews": "Renews by itself",
                "framework_id": "Its terms",
                "closed_note": "Why it was closed",
            },
            "history_quiet": ("status", "closed_on", "agreement_id", "subject_type", "subject_id"),
        },
    )
)


# --- What it covers -------------------------------------------------------------------------


def _subject(session: Session, ref: str) -> tuple[str, Any]:
    """A system, a body of information, or a scope, by its reference."""
    ref = ref.strip().upper()
    for key in COVERED:
        record_type = TYPES.get(key)
        if record_type is None or not ref.startswith(f"{record_type.prefix}-"):
            continue
        return key, find(session, record_type, ref)
    raise NotFound(f"{ref or 'That'} is not a system, a body of information, or a scope.")


def set_coverage(
    session: Session, principal: Principal, agreement: Agreement, refs: list[str]
) -> None:
    """Say everything it covers: the systems, information, and scopes, by reference."""
    if not can_edit(session, principal, agreement):
        raise PermissionDenied("An agreement is changed by its owners, or its unit's keepers.")
    if agreement.status != "active":
        raise Conflict("A closed agreement covers nothing. Open it again first.")
    errors = records.Errors()
    wanted: dict[tuple[str, int], str] = {}
    for ref in refs:
        try:
            subject_type, record = _subject(session, str(ref))
        except NotFound as missing:
            errors.add("covers", str(missing))
            continue
        if not access.can_see(session, principal, TYPES[subject_type], record):
            errors.add("covers", f"There is no {TYPES[subject_type].label} {ref}.")
            continue
        wanted[(subject_type, record.id)] = f"{record.ref} {record.name}"
    if errors:
        raise Invalid("What it covers was not changed.", errors)
    have = {
        (row.subject_type, row.subject_id): row
        for row in session.scalars(
            select(AgreementCoverage).where(AgreementCoverage.agreement_id == agreement.id)
        )
    }
    for key, row in have.items():
        if key not in wanted:
            record = session.get(TYPES[key[0]].model, key[1])
            what = f"{record.ref} {record.name}" if record else "a record"
            with audit.operation(session, "agreement.covers", what=what):
                session.delete(row)
                session.flush()
    for key, what in wanted.items():
        if key not in have:
            with audit.operation(session, "agreement.covers", what=what):
                session.add(
                    AgreementCoverage(
                        agreement_id=agreement.id, subject_type=key[0], subject_id=key[1]
                    )
                )
                session.flush()
    records.touch(session, agreement)
    sync(session)


def covering(
    session: Session, principal: Principal, subject_type: str, subject_id: int
) -> list[dict[str, Any]]:
    """The open agreements that cover a record, as much as the person may see."""
    rows = session.scalars(
        select(Agreement)
        .join(AgreementCoverage, AgreementCoverage.agreement_id == Agreement.id)
        .where(
            AgreementCoverage.subject_type == subject_type,
            AgreementCoverage.subject_id == subject_id,
            Agreement.status == "active",
        )
        .order_by(Agreement.ends_on, Agreement.name)
    ).all()
    today = utc_now().date()
    return [
        {**records.chip(AGREEMENT, row), "kind": row.kind, "ends_on": row.ends_on,
         "state": state_of(row, today)}
        for row in rows
        if access.can_see(session, principal, AGREEMENT, row)
    ]  # fmt: skip


# --- Closing --------------------------------------------------------------------------------


def close(session: Session, principal: Principal, agreement: Agreement, note: str | None) -> None:
    """It has ended, or been ended: what it imposed leaves the scopes that held it."""
    if not can_edit(session, principal, agreement):
        raise PermissionDenied("An agreement is closed by its owners, or its unit's keepers.")
    if agreement.status == "closed":
        raise Conflict("It is already closed.")
    said = records.text(note)
    if not said:
        raise Invalid(
            "It was not closed.", {"note": "Say why: it ended, was ended early, or was replaced."}
        )
    with audit.operation(session, "agreement.close", note=said):
        agreement.status, agreement.closed_on, agreement.closed_note = (
            "closed", utc_now().date(), said,
        )  # fmt: skip
        records.touch(session, agreement)
        session.flush()
    sync(session)


def reopen(session: Session, principal: Principal, agreement: Agreement) -> None:
    if not can_edit(session, principal, agreement):
        raise PermissionDenied("An agreement is opened again by its owners, or its unit's keepers.")
    if agreement.status != "closed":
        raise Conflict("It is open.")
    with audit.operation(session, "agreement.reopen"):
        agreement.status, agreement.closed_on = "active", None
        records.touch(session, agreement)
        session.flush()
    sync(session)


# --- What it imposes on scopes ------------------------------------------------------------


def _wanted(session: Session, only: int | None = None) -> dict[tuple[int, int], int]:
    """(scope, framework) → the agreement that imposes it: every open agreement with terms,
    on the scopes it covers and on those that hold what it covers. The oldest agreement is
    named where two impose the same framework."""
    wanted: dict[tuple[int, int], int] = {}
    live_scopes = set(session.scalars(select(Scope.id).where(Scope.status == "active")))
    for agreement in session.scalars(
        select(Agreement)
        .where(
            Agreement.status == "active",
            Agreement.framework_id.is_not(None),
            *([Agreement.id == only] if only is not None else []),
        )
        .order_by(Agreement.id)
    ):
        rows = session.scalars(
            select(AgreementCoverage).where(AgreementCoverage.agreement_id == agreement.id)
        ).all()
        scope_ids = {row.subject_id for row in rows if row.subject_type == "scope"}
        held = [(row.subject_type, row.subject_id) for row in rows if row.subject_type != "scope"]
        if held:
            scope_ids |= set(
                session.scalars(
                    select(ScopeMember.scope_id).where(
                        or_(*(
                            and_(ScopeMember.subject_type == kind, ScopeMember.subject_id == each)
                            for kind, each in held
                        ))
                    )
                )
            )  # fmt: skip
        for scope_id in sorted(scope_ids & live_scopes):
            assert agreement.framework_id is not None
            wanted.setdefault((scope_id, agreement.framework_id), agreement.id)
    return wanted


def sync(session: Session) -> dict[str, int]:
    """Hold every scope to what the agreements covering it impose, and release it from what
    an agreement no longer imposes. A framework a scope holds by its own decision is left as
    it is. Returns how many were added and released."""
    session.flush()
    wanted = _wanted(session)
    rows = {
        (row.scope_id, row.framework_id): row for row in session.scalars(select(ScopeFramework))
    }
    added = released = 0
    for key, row in rows.items():
        if row.agreement_id is None:
            continue  # the scope holds it by its own decision
        if key not in wanted:
            agreement = session.get(Agreement, row.agreement_id)
            framework = session.get(Framework, row.framework_id)
            with audit.operation(
                session, "agreement.scopes", agreement=agreement.ref if agreement else None,
                framework=framework.title if framework else None, held=False,
            ):  # fmt: skip
                _release(session, row)
            released += 1
        elif wanted[key] != row.agreement_id:
            row.agreement_id = wanted[key]
    for key, agreement_id in wanted.items():
        if key in rows:
            continue
        agreement = session.get(Agreement, agreement_id)
        framework = session.get(Framework, key[1])
        with audit.operation(
            session, "agreement.scopes", agreement=agreement.ref if agreement else None,
            framework=framework.title if framework else None, held=True,
        ):  # fmt: skip
            session.add(
                ScopeFramework(scope_id=key[0], framework_id=key[1], agreement_id=agreement_id)
            )
            session.flush()
        added += 1
    session.flush()
    return {"added": added, "released": released}


def _release(session: Session, row: ScopeFramework) -> None:
    """Take a framework off a scope with the decisions made about its requirements."""
    from riskwren.db.models import ScopeRequirement

    for decision in session.scalars(
        select(ScopeRequirement)
        .join(Requirement, Requirement.id == ScopeRequirement.requirement_id)
        .where(
            ScopeRequirement.scope_id == row.scope_id,
            Requirement.framework_id == row.framework_id,
        )
    ):
        session.delete(decision)
    session.delete(row)
    session.flush()


# --- What waits on people -------------------------------------------------------------------


def waiting_on(session: Session, principal: Principal) -> list[tuple[Agreement, str]]:
    """The open agreements this person owns whose notice date or end is near, or has
    passed, with which it is."""
    if principal.account_id is None:
        return []
    today = utc_now().date()
    rows = session.scalars(
        select(Agreement)
        .join(
            RecordOwner,
            and_(RecordOwner.record_type == KEY, RecordOwner.record_id == Agreement.id),
        )
        .where(
            RecordOwner.account_id == principal.account_id,
            RecordOwner.kind.in_(access.EDITING_KINDS),
            Agreement.status == "active",
        )
        .order_by(Agreement.ends_on, Agreement.ref)
        .distinct()
    ).all()
    return [
        (row, state)
        for row in rows
        if (state := state_of(row, today)) in ("notice", "ending", "ended")
    ]
