"""As of (RPT-09): any record, and the register, as it stood on a chosen date.

Nothing is kept for this: it is rebuilt from the history. Every change to a record's own
fields is an event holding each value before and after, so a record as it stood at the end
of a day is the record as it is now with every later change undone, newest first. A record
added after the day did not exist then. The same is done for who owned it.

What is rebuilt is what the history holds: a record's own fields and its owners. Bookkeeping
that is never in the history (a record's version, when it was last touched) is not shown,
and nor is a value the history keeps hidden. A field added by an upgrade has no events from
before the upgrade, so it shows the value it was given then.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid
from riskwren.db.models import Event
from riskwren.events import audit, chain
from riskwren.inventory import history, records
from riskwren.inventory.registry import TYPES, RecordType

OWNER = "record_owner"
# Fields a person reads; the rest of a record's columns are how it is kept.
NOT_SHOWN = {"id", "ref", "created_by", "created_at", "updated_at", "version"}
# The columns of each kind of register, after its reference and name.
COLUMNS: dict[str, tuple[str, ...]] = {
    "risk": ("status", "org_unit_id", "category_id", "residual_rating", "standing",
             "next_review_on"),
    "control": ("status", "org_unit_id", "design", "operation"),
    "issue": ("status", "org_unit_id", "severity", "due_on"),
    "exception": ("status", "org_unit_id", "starts_on", "ends_on"),
    "third_party": ("status", "org_unit_id", "tier", "criticality", "next_review_on"),
}  # fmt: skip
DEFAULT_COLUMNS = ("status", "org_unit_id")
# Which statuses count as live, by kind, for "what was open then".
LIVE = {
    "risk": ("open",),
    "issue": ("open", "proposed"),
    "third_party": ("active",),
    "control": ("active",),
}
MOST = 2000  # records a register shows


def cutoff(on: date) -> datetime:
    """The end of a day, in UTC: what had happened by then is in."""
    return datetime(on.year, on.month, on.day, tzinfo=UTC) + timedelta(days=1)


def day(value: date | None) -> date:
    today = utc_now().date()
    if value is None:
        return today
    if value > today:
        raise Invalid("That day has not happened yet.", {"on": "Choose today or a day before."})
    return value


def _columns(record: Any) -> list[str]:
    cls = type(record)
    left_out = cls.__audit_skip__ | cls.__audit_redact__
    return [prop.key for prop in inspect(cls).column_attrs if prop.key not in left_out]


def _undo(state: dict[str, Any], events: list[Event]) -> dict[str, Any] | None:
    """A record's fields with these events, newest first, undone. None if one of them is
    its creation: it did not exist before."""
    for event in events:
        if event.action == audit.CREATED:
            return None
        if event.action == audit.UPDATED:
            for field, pair in (event.changes or {}).items():
                if field in state and isinstance(pair, list) and len(pair) == 2:
                    state[field] = pair[0]
    return state


def _later(session: Session, subject_type: str, ids: list[int], on: date) -> dict[int, list[Event]]:
    """The events after the day about each record's own row, newest first."""
    found: dict[int, list[Event]] = defaultdict(list)
    for start in range(0, len(ids), 500):
        chunk = ids[start : start + 500]
        for event in session.scalars(
            select(Event)
            .where(
                Event.subject_type == subject_type,
                Event.subject_id.in_(chunk),
                Event.at >= cutoff(on),
            )
            .order_by(Event.id.desc())
        ):
            found[event.subject_id or 0].append(event)
    return found


def state(
    session: Session, record_type: RecordType, record: Any, on: date
) -> dict[str, Any] | None:
    """The record's own fields as they stood at the end of the day, as the history holds
    them, or None if it did not exist yet."""
    if record.created_at >= cutoff(on):
        return None
    now = {key: chain.jsonable(getattr(record, key)) for key in _columns(record)}
    events = _later(session, record_type.key, [record.id], on).get(record.id, [])
    return _undo(now, events)


def owners_then(
    session: Session, record_type: RecordType, record: Any, on: date
) -> list[dict[str, Any]]:
    """Who owned the record at the end of the day: those who own it now, with every later
    change of owners undone."""
    held = {
        (owner["account_id"], owner["kind"]): owner["name"]
        for owner in records.owners_of(session, record_type, [record.id]).get(record.id, [])
    }
    later = session.scalars(
        select(Event)
        .where(
            Event.subject_type == OWNER,
            Event.parent_type == record_type.key,
            Event.parent_id == record.id,
            Event.at >= cutoff(on),
        )
        .order_by(Event.id.desc())
    ).all()
    lookups = history.Lookups(session, record_type)
    for event in later:
        changes = event.changes or {}

        def side(field: str, index: int, changes: dict[str, Any] = changes) -> Any:
            pair = changes.get(field) or [None, None]
            return pair[index]

        if event.action == audit.CREATED:
            held.pop((side("account_id", 1), side("kind", 1)), None)
        elif event.action == audit.DELETED:
            account = side("account_id", 0)
            held[(account, side("kind", 0))] = lookups.name("account", account)
        elif event.action == audit.UPDATED and "kind" in changes:
            # The same person, held another way: find them under the later kind.
            for (account, kind), name in list(held.items()):
                if kind == side("kind", 1):
                    held.pop((account, kind))
                    held[(account, side("kind", 0))] = name
                    break
    return [
        {"account_id": account, "kind": kind, "kind_label": lookups.vocab("owner_kinds", kind),
         "name": name}
        for (account, kind), name in sorted(held.items(), key=lambda item: str(item[1]))
    ]  # fmt: skip


def record_view(
    session: Session, principal: Principal, record_type: RecordType, ref: str, on: date | None
) -> dict[str, Any]:
    """A record as it stood on a day beside how it is now, field by field."""
    on = day(on)
    record = records.load(session, principal, record_type, ref)
    then = state(session, record_type, record, on)
    lookups = history.Lookups(session, record_type)
    now = {key: chain.jsonable(getattr(record, key)) for key in _columns(record)}
    hidden = set(record_type.extra.get("history_hidden", ()))
    fields = []
    for key in _columns(record):
        if key in NOT_SHOWN or key in hidden or key.endswith("_hash"):
            continue
        before = lookups.value(key, then.get(key)) if then is not None else None
        after = lookups.value(key, now.get(key))
        if before is None and after is None:
            continue
        fields.append(
            {
                "field": key,
                "label": lookups.labels.get(key, history.words(key)),
                "then": before,
                "now": after,
                "changed": then is not None and then.get(key) != now.get(key),
            }
        )
    since = session.scalars(
        select(Event.id).where(
            (
                (Event.subject_type == record_type.key) & (Event.subject_id == record.id)
                | (Event.parent_type == record_type.key) & (Event.parent_id == record.id)
            ),
            Event.at >= cutoff(on),
        )
    ).all()
    owners_now = records.owners_of(session, record_type, [record.id]).get(record.id, [])
    return {
        "type": record_type.key,
        "path": record_type.path,
        "label": record_type.label,
        "ref": record.ref,
        "name": record.name,
        "on": on,
        "existed": then is not None,
        "created_at": record.created_at,
        "fields": fields,
        "owners_then": owners_then(session, record_type, record, on) if then is not None else [],
        "owners_now": [
            {
                "account_id": owner["account_id"],
                "kind": owner["kind"],
                "kind_label": lookups.vocab("owner_kinds", owner["kind"]),
                "name": owner["name"],
            }
            for owner in owners_now
        ],
        "changes_since": len(since),
    }


def register(
    session: Session,
    principal: Principal,
    type_key: str,
    on: date | None,
    *,
    live_only: bool = True,
) -> dict[str, Any]:
    """A register as it stood at the end of a day: the records that existed then, each with
    its fields then and now. With ``live_only``, only those that were open or in use then."""
    record_type = TYPES.get(type_key)
    if record_type is None:
        raise Invalid("There is no such register.", {"type": f"One of: {', '.join(TYPES)}."})
    on = day(on)
    model: Any = record_type.model
    conditions = records.conditions_for(session, principal, record_type, {})
    rows = session.scalars(
        select(model)
        .where(*conditions, model.created_at < cutoff(on))
        .order_by(model.ref)
        .limit(MOST)
    ).all()
    later = _later(session, record_type.key, [row.id for row in rows], on)
    lookups = history.Lookups(session, record_type)
    columns = [key for key in COLUMNS.get(record_type.key, DEFAULT_COLUMNS) if hasattr(model, key)]
    live = LIVE.get(record_type.key)
    out = []
    for row in rows:
        now = {key: chain.jsonable(getattr(row, key)) for key in _columns(row)}
        then = _undo(dict(now), later.get(row.id, []))
        if then is None:
            continue
        if live_only and live and "status" in then and then["status"] not in live:
            continue
        out.append(
            {
                "ref": row.ref,
                "name": then.get("name") or row.name,
                "then": {key: lookups.value(key, then.get(key)) for key in columns},
                "now": {key: lookups.value(key, now.get(key)) for key in columns},
                "changed": [key for key in columns if then.get(key) != now.get(key)],
                "renamed": then.get("name") != now.get("name"),
            }
        )
    if record_type.key == "risk":
        out.sort(key=_by_rating(session))
    return {
        "type": record_type.key,
        "path": record_type.path,
        "label": record_type.label,
        "plural": record_type.plural,
        "on": on,
        "live_only": live_only,
        "columns": [
            {"key": key, "label": lookups.labels.get(key, history.words(key))} for key in columns
        ],
        "rows": out,
        "types": {key: TYPES[key].plural for key in COLUMNS if key in TYPES},
    }


def _by_rating(session: Session) -> Any:
    from riskwren.risk import method as methods

    places = {r["label"]: i for i, r in enumerate(methods.current(session)["ratings"], 1)}

    def key(row: dict[str, Any]) -> tuple[int, str]:
        return -places.get(row["then"].get("residual_rating") or "", 0), row["ref"]

    return key
