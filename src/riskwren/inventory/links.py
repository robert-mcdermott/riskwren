"""Named relationships between records: what relies on what.

A link reads one way from the record it starts at and the other way from the record it
reaches, so each record shows both what it depends on and what depends on it.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.errors import Invalid, NotFound, PermissionDenied
from riskwren.db.models import RecordLink
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.registry import TYPES, RecordType
from riskwren.program import vocab


def kinds(session: Session) -> dict[str, dict[str, Any]]:
    return {item["key"]: item for item in vocab.get(session, "link_kinds")}


def kinds_between(session: Session, from_type: str, to_type: str) -> list[str]:
    return [
        key
        for key, item in kinds(session).items()
        if not item.get("retired") and [from_type, to_type] in item.get("between", [])
    ]


def add(
    session: Session,
    principal: Principal,
    from_type: RecordType,
    from_record: Any,
    relation: str,
    to_type: RecordType,
    to_record: Any,
    *,
    note: str | None = None,
) -> RecordLink:
    """Say that one record relies on, is supplied by, or otherwise stands in a named
    relationship to another."""
    if not access.can_edit(session, principal, from_type, from_record):
        raise PermissionDenied(f"You cannot edit this {from_type.label}.")
    if not access.can_see(session, principal, to_type, to_record):
        raise NotFound(f"There is no {to_type.label} {to_record.ref}.")
    problem = "The link was not added."
    if relation not in kinds_between(session, from_type.key, to_type.key):
        allowed = kinds_between(session, from_type.key, to_type.key)
        hint = f" Use one of: {', '.join(allowed)}." if allowed else ""
        message = f"A {from_type.label} cannot be linked to a {to_type.label} that way.{hint}"
        raise Invalid(problem, {"relation": message})
    if from_type is to_type and from_record.id == to_record.id:
        raise Invalid(problem, {"to": "A record cannot be linked to itself."})
    existing = session.scalars(
        select(RecordLink).where(
            RecordLink.from_type == from_type.key,
            RecordLink.from_id == from_record.id,
            RecordLink.relation == relation,
            RecordLink.to_type == to_type.key,
            RecordLink.to_id == to_record.id,
        )
    ).first()
    if existing is not None:
        raise Invalid(problem, {"to": "These two are already linked that way."})
    cleaned = records.text(note)
    if cleaned and len(cleaned) > 300:
        raise Invalid(problem, {"note": "Keep the note to 300 characters."})
    link = RecordLink(
        from_type=from_type.key,
        from_id=from_record.id,
        relation=relation,
        to_type=to_type.key,
        to_id=to_record.id,
        note=cleaned,
    )
    with audit.operation(session, f"{from_type.key}.link"):
        session.add(link)
        session.flush()
    return link


def remove(
    session: Session, principal: Principal, record_type: RecordType, record: Any, link_id: int
) -> None:
    """Take a link away. Whoever may edit the record at either end may do so."""
    link = session.get(RecordLink, link_id)
    ends = [(link.from_type, link.from_id), (link.to_type, link.to_id)] if link is not None else []
    if (record_type.key, record.id) not in ends:
        raise NotFound("There is no such link on this record.")
    if not access.can_edit(session, principal, record_type, record):
        raise PermissionDenied(f"You cannot edit this {record_type.label}.")
    with audit.operation(session, f"{record_type.key}.unlink"):
        session.delete(link)


def _load(session: Session, wanted: dict[str, set[int]]) -> dict[tuple[str, int], Any]:
    found: dict[tuple[str, int], Any] = {}
    for key, ids in wanted.items():
        record_type = TYPES.get(key)
        if record_type is None or not ids:
            continue
        model: Any = record_type.model
        for row in session.scalars(select(model).where(model.id.in_(ids))):
            found[(key, row.id)] = row
    return found


def of(
    session: Session, principal: Principal, record_type: RecordType, record: Any
) -> dict[str, Any]:
    """A record's links in both directions, each cut to what the person may see, with a count
    of those they may not."""
    rows = session.scalars(
        select(RecordLink)
        .where(
            or_(
                (RecordLink.from_type == record_type.key) & (RecordLink.from_id == record.id),
                (RecordLink.to_type == record_type.key) & (RecordLink.to_id == record.id),
            )
        )
        .order_by(RecordLink.id)
    ).all()
    wanted: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        wanted[row.from_type].add(row.from_id)
        wanted[row.to_type].add(row.to_id)
    loaded = _load(session, wanted)
    labels = kinds(session)
    setting = access.visibility(session)
    outgoing, incoming, hidden = [], [], 0
    for row in rows:
        forward = row.from_type == record_type.key and row.from_id == record.id
        other_key = (row.to_type, row.to_id) if forward else (row.from_type, row.from_id)
        other = loaded.get(other_key)
        other_type = TYPES.get(other_key[0])
        if other is None or other_type is None:
            continue
        if not access.can_see(session, principal, other_type, other, setting=setting):
            hidden += 1
            continue
        kind = labels.get(row.relation, {})
        entry = {
            "id": row.id,
            "relation": row.relation,
            "label": kind.get("label" if forward else "reverse", row.relation),
            "record": records.chip(other_type, other),
            "note": row.note,
        }
        (outgoing if forward else incoming).append(entry)
    return {"outgoing": outgoing, "incoming": incoming, "hidden": hidden}
