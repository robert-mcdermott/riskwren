"""Every change to an audited row becomes an event, automatically.

The session watches what the ORM is about to write. After each flush it turns the new,
changed, and deleted rows into events and appends them to the chain in the same
transaction. Services do not have to remember to log anything, and cannot forget.

Two things are refused, because they would change data without leaving an event:

* flushing changes on a session that has no actor;
* bulk ``insert``/``update``/``delete`` statements against an audited table.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import ORMExecuteState, Session

from riskwren.core.clock import utc_now
from riskwren.core.errors import AuditError
from riskwren.db.base import Base
from riskwren.events import chain
from riskwren.events.actor import Actor

CREATED = "created"
UPDATED = "updated"
DELETED = "deleted"
REDACTED = "[redacted]"


class AuditedSession(Session):
    """The only kind of session RiskWren uses."""


def subject_type(model: type[Base] | Base) -> str:
    cls = model if isinstance(model, type) else type(model)
    return getattr(cls, "__subject__", cls.__tablename__)


def _audited_tables() -> set[str]:
    return {
        mapper.local_table.name
        for mapper in Base.registry.mappers
        if mapper.class_.__audit__ and hasattr(mapper.local_table, "name")
    }


def _value(obj: Base, key: str, value: Any) -> Any:
    if value is None:
        return None
    return REDACTED if key in type(obj).__audit_redact__ else chain.jsonable(value)


def _changes(obj: Base, verb: str) -> dict[str, list[Any]]:
    state = inspect(obj)
    changes: dict[str, list[Any]] = {}
    skipped = type(obj).__audit_skip__
    for prop in state.mapper.column_attrs:
        key = prop.key
        if key in skipped:
            continue
        if verb == UPDATED:
            history = state.attrs[key].history
            if not history.has_changes():
                continue
            before = history.deleted[0] if history.deleted else None
            after = history.added[0] if history.added else None
            if before == after:
                continue
            changes[key] = [_value(obj, key, before), _value(obj, key, after)]
        else:
            current = getattr(obj, key)
            if current is None:
                continue
            shown = _value(obj, key, current)
            changes[key] = [None, shown] if verb == CREATED else [shown, None]
    return changes


def _parent_type(obj: Base | None, parent: tuple[str, str] | None) -> str | None:
    """The type of record a child row belongs to. ``@column`` reads it from the row itself,
    for children such as owners that can belong to any kind of record."""
    if obj is None or parent is None:
        return None
    return getattr(obj, parent[0][1:]) if parent[0].startswith("@") else parent[0]


def _row(session: Session, obj: Base, verb: str, changes: Mapping[str, Any]) -> dict[str, Any]:
    actor: Actor = session.info["actor"]
    parent = type(obj).__audit_parent__
    return {
        "actor_kind": actor.kind,
        "actor_id": actor.id,
        "actor_label": actor.label,
        "action": verb,
        "subject_type": subject_type(obj),
        "subject_id": getattr(obj, "id", None)
        if isinstance(getattr(obj, "id", None), int)
        else None,
        "subject_ref": getattr(obj, "ref", None),
        "parent_type": _parent_type(obj, parent),
        "parent_id": getattr(obj, parent[1], None) if parent else None,
        "changes": dict(changes),
        "context": chain.jsonable(session.info.get("context", {})),
    }


@event.listens_for(AuditedSession, "after_flush")
def _record_flush(session: Session, _flush_context: Any) -> None:
    pending: list[tuple[Base, str]] = []
    pending += [(o, CREATED) for o in session.new if isinstance(o, Base) and type(o).__audit__]
    pending += [
        (o, UPDATED)
        for o in session.dirty
        if isinstance(o, Base) and type(o).__audit__ and session.is_modified(o)
    ]
    pending += [(o, DELETED) for o in session.deleted if isinstance(o, Base) and type(o).__audit__]
    if not pending:
        return
    if "actor" not in session.info:
        raise AuditError(
            "Changes were flushed on a session with no actor. Write through Database.write()."
        )
    rows = []
    for obj, verb in pending:
        changes = _changes(obj, verb)
        if verb == UPDATED and not changes:
            continue
        rows.append(_row(session, obj, verb, changes))
    chain.append(session.connection(), utc_now(), rows)


@event.listens_for(AuditedSession, "do_orm_execute")
def _refuse_bulk_writes(state: ORMExecuteState) -> None:
    if state.is_select or not (state.is_insert or state.is_update or state.is_delete):
        return
    table = getattr(state.statement, "table", None)
    name = getattr(table, "name", None)
    if name in _audited_tables():
        raise AuditError(
            f"A bulk statement against `{name}` would change rows without recording events. "
            "Load the rows and change them through the session."
        )


def record(
    session: Session,
    action: str,
    subject: Base | None = None,
    *,
    subject_kind: str | None = None,
    changes: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
) -> None:
    """Append an event for something that is not a change to a row: a download, an export,
    a sign-in. ``subject`` is the record it concerns, if any."""
    if "actor" not in session.info:
        raise AuditError("An event needs an actor. Write through Database.write().")
    actor: Actor = session.info["actor"]
    parent = type(subject).__audit_parent__ if subject is not None else None
    merged = {**session.info.get("context", {}), **(context or {})}
    identifier = getattr(subject, "id", None)
    row = {
        "actor_kind": actor.kind,
        "actor_id": actor.id,
        "actor_label": actor.label,
        "action": action,
        "subject_type": subject_type(subject)
        if subject is not None
        else (subject_kind or "system"),
        "subject_id": identifier if isinstance(identifier, int) else None,
        "subject_ref": getattr(subject, "ref", None),
        "parent_type": _parent_type(subject, parent),
        "parent_id": getattr(subject, parent[1], None) if parent else None,
        "changes": chain.jsonable(dict(changes or {})),
        "context": chain.jsonable(merged),
    }
    session.flush()  # keep events in the order things happened
    chain.append(session.connection(), utc_now(), [row])


@contextmanager
def operation(session: Session, name: str, **context: Any) -> Iterator[None]:
    """Mark the changes made in a block as part of one named operation.

    Every event recorded inside carries ``op`` (and anything else given) in its context, so
    the history can say "submitted" or "decided" and not only which rows changed.
    """
    session.flush()
    previous = session.info.get("context", {})
    session.info["context"] = {**previous, "op": name, **context}
    try:
        yield
        session.flush()
    finally:
        session.info["context"] = previous
