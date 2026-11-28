"""Drafts (INT-06): what an assistant or another system proposes, made only by a person.

A draft is a record of its own, never a half-made risk, issue, or control. A person opens it in
the ordinary form, changes what they like, and saves it, so every rule that applies to a
record they make applies to this one; the draft is then marked as used, naming what was made.
Setting a draft aside, with why, leaves no record behind. A token that may only read may still
draft, because a draft changes nothing.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import Draft, OrgUnit
from riskwren.events import audit
from riskwren.inventory import access, records

# What each kind of draft may say: the fields of the ordinary form, and no others.
FIELDS: dict[str, dict[str, int]] = {
    "risk": {"name": 400, "summary": 4000, "cause": 4000, "event": 4000, "consequence": 4000,
             "category": 64},
    "issue": {"name": 300, "summary": 8000, "severity": 16, "source_kind": 32},
    "control": {"name": 400, "statement": 4000, "objective": 4000, "kind": 32,
                "nature": 32, "frequency": 32},
}  # fmt: skip
KINDS = tuple(FIELDS)
NEEDED = {"risk": "name", "issue": "name", "control": "name"}
STATUSES = ("waiting", "used", "set_aside")


def _record_type(kind: str) -> Any:
    if kind == "risk":
        from riskwren.risk.register import RISK

        return RISK
    if kind == "issue":
        from riskwren.compliance.issues import ISSUE

        return ISSUE
    from riskwren.controls.service import CONTROL

    return CONTROL


def may_make(principal: Principal, kind: str, org_unit_id: int | None) -> bool:
    """Who may turn a draft of this kind into a record: those with a role over its unit."""
    if principal.person is None:
        return False
    if access.can_add(principal, org_unit_id):
        return True
    return kind == "issue" and principal.assesses_unit(org_unit_id)


def view(session: Session, principal: Principal, row: Draft) -> dict[str, Any]:
    unit = session.get(OrgUnit, row.org_unit_id) if row.org_unit_id else None
    return {
        "id": row.id, "kind": row.kind, "values": row.values, "why": row.why,
        "source": row.source, "made_by": row.made_by_name, "made_at": row.made_at,
        "org_unit": {"id": unit.id, "name": unit.name} if unit else None,
        "status": row.status, "record_ref": row.record_ref,
        "decided_by": row.decided_by_name, "decided_at": row.decided_at,
        "decision_note": row.decision_note,
        "can": {"use": row.status == "waiting" and may_make(principal, row.kind, row.org_unit_id)},
    }  # fmt: skip


def _check(session: Session, kind: Any, values: Any, why: Any) -> dict[str, Any]:
    errors = records.Errors()
    if kind not in FIELDS:
        errors.add("kind", f"Draft one of: {', '.join(KINDS)}.")
        raise Invalid("The draft was not kept.", errors)
    if not isinstance(values, dict):
        errors.add("values", "Give the draft's fields by name.")
        raise Invalid("The draft was not kept.", errors)
    allowed = FIELDS[kind]
    clean: dict[str, Any] = {}
    for key, value in values.items():
        if key == "org_unit_id":
            continue
        if key not in allowed:
            errors.add(f"values.{key}", f"A {kind} draft does not say {key}.")
            continue
        said = records.text(value) if isinstance(value, str) else None
        if value is not None and said is None and not isinstance(value, str):
            errors.add(f"values.{key}", "Give it as text.")
        elif said and len(said) > allowed[key]:
            errors.add(f"values.{key}", f"Keep it to {allowed[key]:,} characters.")
        elif said:
            clean[key] = said
    if not clean.get(NEEDED[kind]):
        errors.add(f"values.{NEEDED[kind]}", "A draft needs at least a title.")
    unit = values.get("org_unit_id")
    if unit is not None and (not isinstance(unit, int) or session.get(OrgUnit, unit) is None):
        errors.add("values.org_unit_id", "There is no such unit.")
    said_why = records.text(why) if isinstance(why, str) else None
    if said_why and len(said_why) > 2000:
        errors.add("why", "Keep it to 2,000 characters.")
    if errors:
        raise Invalid("The draft was not kept.", errors)
    return {"values": clean, "org_unit_id": unit, "why": said_why}


def propose(
    session: Session,
    principal: Principal,
    kind: Any,
    values: Any,
    why: Any = None,
    source: str | None = None,
) -> Draft:
    """Keep a draft for a person to open. ``source`` names what drafted it."""
    clean = _check(session, kind, values, why)
    if principal.token_id is None and principal.person is None:
        raise PermissionDenied("A draft is proposed by a person's assistant or by a token.")
    by = source or principal.name.removeprefix("API token ")
    row = Draft(kind=kind, values=clean["values"], why=clean["why"], source=by[:200],
                org_unit_id=clean["org_unit_id"], made_by=principal.person,
                made_by_name=principal.name, made_at=utc_now(), status="waiting")  # fmt: skip
    with audit.operation(session, "draft.propose", kind=kind):
        session.add(row)
        session.flush()
    return row


def _visible(principal: Principal, row: Draft) -> bool:
    if principal.person is not None and row.made_by == principal.person:
        return True
    return may_make(principal, row.kind, row.org_unit_id) or (
        principal.token_id is not None and row.made_by is None
        and row.made_by_name == principal.name
    )  # fmt: skip


def waiting(session: Session, principal: Principal) -> list[dict[str, Any]]:
    """Drafts waiting for a person who may make them, or that this person asked for."""
    rows = session.scalars(
        select(Draft).where(Draft.status == "waiting").order_by(Draft.made_at.desc()).limit(300)
    ).all()
    return [view(session, principal, row) for row in rows if _visible(principal, row)]


def load(session: Session, principal: Principal, draft_id: int) -> Draft:
    row = session.get(Draft, draft_id)
    if row is None or not _visible(principal, row):
        raise NotFound("There is no such draft.")
    return row


def _may_decide(principal: Principal, row: Draft) -> None:
    if not may_make(principal, row.kind, row.org_unit_id):
        raise PermissionDenied("A person who may add this kind of record in its unit decides it.")
    if row.status != "waiting":
        raise Conflict("This draft has been decided already.")


def used(session: Session, principal: Principal, row: Draft, ref: Any) -> Draft:
    """Mark a draft as used: the person made the record, through the ordinary form, since the
    draft was proposed."""
    _may_decide(principal, row)
    record_type = _record_type(row.kind)
    made = None
    if isinstance(ref, str):
        made = session.scalars(
            select(record_type.model).where(record_type.model.ref == ref)
        ).first()
    if (
        made is None
        or made.created_by != principal.person
        or made.created_at < row.made_at
        or not access.can_see(session, principal, record_type, made)
    ):
        raise Invalid("The draft was not marked as used.",
                      {"ref": f"Name the {row.kind} you made from it."})  # fmt: skip
    with audit.operation(session, "draft.use", kind=row.kind, ref=made.ref):
        row.status, row.record_ref = "used", made.ref
        row.decided_by, row.decided_by_name, row.decided_at = (
            principal.person,
            principal.name,
            utc_now(),
        )
        session.flush()
    return row


def set_aside(session: Session, principal: Principal, row: Draft, note: Any) -> Draft:
    _may_decide(principal, row)
    said = records.text(note) if isinstance(note, str) else None
    if not said:
        raise Invalid("The draft was not set aside.", {"note": "Say why it is set aside."})
    with audit.operation(session, "draft.set_aside", kind=row.kind):
        row.status, row.decision_note = "set_aside", said[:2000]
        row.decided_by, row.decided_by_name, row.decided_at = (
            principal.person,
            principal.name,
            utc_now(),
        )
        session.flush()
    return row
