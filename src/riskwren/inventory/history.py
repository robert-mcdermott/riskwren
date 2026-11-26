"""A record's history, in words a person can read.

The events themselves are the record of what happened (``riskwren.events``). This turns them
into a timeline: who did what, and for each changed field, what it was and what it became.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from riskwren.db.models import Account, Event, OrgUnit
from riskwren.inventory import links
from riskwren.inventory.registry import TYPES, RecordType
from riskwren.program import vocab

LABELS = {
    "name": "Name",
    "summary": "Summary",
    "org_unit_id": "Unit",
    "status": "Status",
    "criticality": "Criticality",
    "data_class": "Data class",
    "tags": "Tags",
    "restricted": "Restricted",
}
HIDDEN = {"id", "ref", "created_by", "created_at"}
VOCABULARIES = {"criticality": "criticalities", "data_class": "data_classes"}
OPERATIONS = {
    "create": "Added",
    "edit": "Edited",
    "owners": "Changed the owners",
    "link": "Added a link",
    "unlink": "Removed a link",
}


def words(text: str) -> str:
    return text.replace("_", " ").capitalize()


class Lookups:
    """Names for the keys and ids that events hold, loaded when first needed."""

    def __init__(self, session: Session, record_type: RecordType) -> None:
        self.session = session
        self.labels = {**LABELS, **{field.name: field.label for field in record_type.fields}}
        self.vocabularies = {
            **VOCABULARIES,
            **{f.name: f.vocab for f in record_type.fields if f.vocab},
            **record_type.extra.get("history_vocabularies", {}),
        }
        self.labels.update(record_type.extra.get("history_labels", {}))
        self.special = record_type.extra.get("history_value")
        self._vocab: dict[str, dict[str, str]] = {}
        self._names: dict[str, dict[int, str]] = {}

    def vocab(self, name: str, key: Any) -> str:
        if name not in self._vocab:
            self._vocab[name] = vocab.labels(self.session, name)
        return self._vocab[name].get(str(key), words(str(key)))

    def name(self, kind: str, identifier: Any) -> str:
        if kind not in self._names:
            if kind == "unit":
                rows = self.session.execute(select(OrgUnit.id, OrgUnit.name)).all()
            elif kind == "account":
                rows = self.session.execute(select(Account.id, Account.display_name)).all()
            else:
                model: Any = TYPES[kind].model
                rows = self.session.execute(select(model.id, model.ref, model.name)).all()
                rows = [(row[0], f"{row[1]} {row[2]}") for row in rows]  # type: ignore[misc]
            self._names[kind] = {row[0]: row[1] for row in rows}
        return self._names[kind].get(identifier, f"{words(kind).lower()} {identifier}")

    def value(self, field: str, value: Any) -> Any:
        if value is None or value == "" or value == []:
            return None
        if self.special is not None:
            said = self.special(self, field, value)
            if said is not None:
                return said
        if field in self.vocabularies:
            if isinstance(value, list):
                return ", ".join(self.vocab(self.vocabularies[field], item) for item in value)
            return self.vocab(self.vocabularies[field], value)
        if field.endswith("unit_id"):
            return self.name("unit", value)
        if field.endswith("_by") or field == "owner_id":
            return self.name("account", value)
        if field in ("status", "standing", "response"):
            return words(str(value))
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, list):
            return ", ".join(str(item) for item in value)
        if isinstance(value, dict):
            return "; ".join(f"{words(k)}: {v}" for k, v in value.items() if v not in (None, ""))
        return value


def entry(event: Event, record_type: RecordType, lookups: Lookups) -> dict[str, Any]:
    changes = event.changes or {}
    lines: list[dict[str, Any]] = []
    operation = str((event.context or {}).get("op", "")).rsplit(".", 1)[-1]

    def now(field: str) -> Any:
        pair = changes.get(field) or [None, None]
        return pair[1] if pair[1] is not None else pair[0]

    describe = record_type.extra.get("history_title")
    title = describe(event, lookups) if describe else None
    if title:
        pass
    elif event.subject_type == "record_owner":
        person = lookups.name("account", now("account_id"))
        kind = lookups.vocab("owner_kinds", now("kind")).lower()
        verb = "Added" if event.action == "created" else "Removed"
        title = f"{verb} {person} as {kind}"
    elif event.subject_type == "record_link":
        kind = links.kinds(lookups.session).get(now("relation"), {})
        target = now("to_type")
        other = lookups.name(target, now("to_id")) if target in TYPES else "another record"
        label = str(kind.get("label", words(str(now("relation"))))).lower()
        title = (
            f"Now {label} {other}" if event.action == "created" else f"No longer {label} {other}"
        )
    elif event.subject_type == "external_ref":
        system = lookups.vocab("external_systems", now("system")).lower()
        verb = "Now also known as" if event.action == "created" else "No longer known as"
        title = f"{verb} {now('value')} ({system})"
    elif event.action == "created":
        title = f"Added this {record_type.label}"
    elif event.action == "updated":
        quiet = record_type.extra.get("history_quiet", ())
        for field, (old, new) in changes.items():
            if field in HIDDEN or (field in quiet and event.subject_type == record_type.key):
                continue
            lines.append(
                {
                    "field": field,
                    "label": lookups.labels.get(field, words(field)),
                    "before": lookups.value(field, old),
                    "after": lookups.value(field, new),
                }
            )
        title = (
            lines[0]["label"] + " changed"
            if len(lines) == 1
            else OPERATIONS.get(operation, "Edited")
        )
    else:
        title = words(event.action)
    return {
        "id": event.id,
        "at": event.at,
        "actor": event.actor_label,
        "actor_kind": event.actor_kind,
        "action": event.action,
        "operation": operation,
        "title": title,
        "lines": lines,
        "told": bool(describe and title and not lines and event.action == "updated"),
    }


def for_record(
    session: Session, record_type: RecordType, record: Any, *, limit: int = 300
) -> list[dict[str, Any]]:
    """The record's history, newest first. Permission to see it is the caller's to check."""
    events = session.scalars(
        select(Event)
        .where(
            or_(
                (Event.subject_type == record_type.key) & (Event.subject_id == record.id),
                (Event.parent_type == record_type.key) & (Event.parent_id == record.id),
            )
        )
        .order_by(Event.id.desc())
        .limit(limit)
    ).all()
    lookups = Lookups(session, record_type)
    story = [entry(event, record_type, lookups) for event in events]
    # A change that only copied what another entry already says (a rating onto its control,
    # an assessment onto its risk) is not told twice, unless the type says its own titled
    # changes are each worth telling (a result confirmed, in an assessment).
    keeps = bool(record_type.extra.get("history_keeps_titled"))
    return [
        {key: value for key, value in item.items() if key != "told"}
        for item in story
        if item["action"] != "updated" or item["lines"] or (keeps and item["told"])
    ]
