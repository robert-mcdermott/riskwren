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

    def __init__(self, session: Session, record_type: RecordType, principal: Any = None) -> None:
        self.session = session
        # Whose history this is: a record they may not see is not named to them.
        self.principal = principal
        self._seen: dict[tuple[str, int], bool] = {}
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
        if kind not in ("unit", "account") and not self._may_see(kind, identifier):
            return "a record you cannot see"
        return self._names[kind].get(identifier, f"{words(kind).lower()} {identifier}")

    def _may_see(self, kind: str, identifier: Any) -> bool:
        if self.principal is None or not isinstance(identifier, int):
            return True
        if (kind, identifier) not in self._seen:
            from riskwren.inventory import access  # it builds on the registry, as this does

            row = self.session.get(TYPES[kind].model, identifier)
            self._seen[(kind, identifier)] = row is not None and access.can_see(
                self.session, self.principal, TYPES[kind], row
            )
        return self._seen[(kind, identifier)]

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
    described = bool(title)
    # Some operations change what is otherwise only ever changed by something already told
    # (a rating, by an assessment). Told under their own title, they show every line.
    loud = (event.context or {}).get("op") in record_type.extra.get("history_loud", ())
    if title and loud and event.action == "updated":
        lines = [
            {"field": field, "label": lookups.labels.get(field, words(field)),
             "before": lookups.value(field, old), "after": lookups.value(field, new)}
            for field, (old, new) in changes.items()
            if field not in HIDDEN
        ]  # fmt: skip
    elif title:
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
        "told": bool(described and not lines and event.action == "updated"),
    }


def for_record(
    session: Session,
    record_type: RecordType,
    record: Any,
    *,
    limit: int = 300,
    principal: Any = None,
) -> list[dict[str, Any]]:
    """The record's history, newest first. Permission to see it is the caller's to check;
    with ``principal``, the records it names that they may not see are not named."""
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
    lookups = Lookups(session, record_type, principal)
    hidden = record_type.extra.get("history_hidden", ())
    story = [
        entry(event, record_type, lookups) for event in events if event.subject_type not in hidden
    ]
    # A change that only copied what another entry already says (a rating onto its control,
    # an assessment onto its risk) is not told twice, unless the type says its own titled
    # changes are each worth telling (a result confirmed, in an assessment).
    keeps = bool(record_type.extra.get("history_keeps_titled"))
    return [
        {key: value for key, value in item.items() if key != "told"}
        for item in story
        if item["action"] != "updated" or item["lines"] or (keeps and item["told"])
    ]


# --- Every change, in one place -------------------------------------------------------------

PAGE = 100
# What happened, for events that are not a change to a record.
SAID = {
    "exported": "Exported a list",
    "evidence.downloaded": "Downloaded a file",
    "signed_in": "Signed in",
    "signed_out": "Signed out",
    "sign_in_failed": "Failed to sign in",
}


def _plain(event: Event) -> dict[str, Any]:
    """An event about something that is not a record: a sign-in, an export, a setting."""
    changes = event.changes or {}

    def now(field: str) -> Any:
        pair = changes.get(field) or [None, None]
        return pair[1] if pair[1] is not None else pair[0]

    title = SAID.get(event.action)
    if event.action == "exported":
        title = f"Exported {now('list')} as {str(now('format')).upper()}: {now('rows')} rows"
    elif title is None:
        what = words(event.subject_type).lower()
        verb = {"created": "Added", "updated": "Changed", "deleted": "Removed"}.get(event.action)
        title = f"{verb} {what}" if verb else f"{words(event.action.replace('.', ' '))}"
    lines = [
        {"field": field, "label": words(field), "before": _shown(old), "after": _shown(new)}
        for field, (old, new) in changes.items()
        if field not in HIDDEN and event.action == "updated"
    ]
    return {
        "id": event.id,
        "at": event.at,
        "actor": event.actor_label,
        "actor_kind": event.actor_kind,
        "action": event.action,
        "operation": str((event.context or {}).get("op", "")).rsplit(".", 1)[-1],
        "title": title,
        "lines": lines,
    }


def _shown(value: Any) -> Any:
    if value is None or value == "" or value == []:
        return None
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (dict, list)):
        return str(value)[:300]
    return value


def everywhere(
    session: Session,
    *,
    principal: Any = None,
    actor: int | None = None,
    about: tuple[RecordType, Any] | None = None,
    kind: str | None = None,
    since: Any = None,
    until: Any = None,
    before: int | None = None,
    limit: int = PAGE,
) -> dict[str, Any]:
    """Every change, newest first, for those who may read everything: narrowed to a person,
    a record, a kind of record, or a span of dates. Each entry says which record it was."""
    conditions: list[Any] = []
    # A record type may hide some of its records even from those who read everything, as
    # a restricted case is hidden from all but those named on it; its events go with it.
    for key, record_type in TYPES.items():
        hide = record_type.extra.get("hidden")
        ids = hide(session, principal) if hide is not None and principal is not None else None
        if ids is None:
            continue
        conditions.append(
            or_(Event.subject_type != key, Event.subject_id.is_(None), Event.subject_id.not_in(ids))
        )
        conditions.append(
            or_(Event.parent_type.is_(None), Event.parent_type != key, Event.parent_id.not_in(ids))
        )
    if actor is not None:
        conditions += [Event.actor_kind == "account", Event.actor_id == actor]
    if about is not None:
        record_type, record = about
        conditions.append(
            or_(
                (Event.subject_type == record_type.key) & (Event.subject_id == record.id),
                (Event.parent_type == record_type.key) & (Event.parent_id == record.id),
            )
        )
    if kind == "records":
        known = list(TYPES)
        conditions.append(or_(Event.subject_type.in_(known), Event.parent_type.in_(known)))
    elif kind == "other":
        known = list(TYPES)
        conditions += [
            Event.subject_type.not_in(known),
            or_(Event.parent_type.is_(None), Event.parent_type.not_in(known)),
        ]
    elif kind:
        conditions.append(or_(Event.subject_type == kind, Event.parent_type == kind))
    if since is not None:
        conditions.append(Event.at >= since)
    if until is not None:
        conditions.append(Event.at < until)
    if before is not None:
        conditions.append(Event.id < before)
    lookups: dict[str, Lookups] = {}
    names: dict[tuple[str, int], dict[str, Any] | None] = {}

    def record_of(key: str, identifier: int | None) -> dict[str, Any] | None:
        if identifier is None or key not in TYPES:
            return None
        if (key, identifier) not in names:
            row = session.get(TYPES[key].model, identifier)
            names[(key, identifier)] = (
                {"type": key, "ref": row.ref, "name": row.name} if row is not None else None
            )
        return names[(key, identifier)]

    entries: list[dict[str, Any]] = []
    last: int | None = None
    more = False
    # Changes that only copy what another entry says are left out, so more are read than
    # are shown, a page at a time, until the page is full.
    cursor = before
    while len(entries) < limit:
        batch_conditions = [c for c in conditions if c is not None]
        if cursor is not None and cursor != before:
            batch_conditions.append(Event.id < cursor)
        events = session.scalars(
            select(Event).where(*batch_conditions).order_by(Event.id.desc()).limit(limit * 2)
        ).all()
        if not events:
            break
        for event in events:
            cursor = event.id
            key = (
                event.parent_type
                if event.parent_type in TYPES
                else event.subject_type
                if event.subject_type in TYPES
                else None
            )
            if key is None:
                item = _plain(event)
                record = None
            else:
                if key not in lookups:
                    lookups[key] = Lookups(session, TYPES[key], principal)
                item = entry(event, TYPES[key], lookups[key])
                keeps = bool(TYPES[key].extra.get("history_keeps_titled"))
                told = item.pop("told", False)
                if item["action"] == "updated" and not item["lines"] and not (keeps and told):
                    continue
                identifier = event.parent_id if event.parent_type in TYPES else event.subject_id
                record = record_of(key, identifier)
            if len(entries) == limit:
                more = True
                break
            entries.append({**item, "record": record, "kind": key or event.subject_type})
            last = event.id
        if more or len(events) < limit * 2:
            break
    return {"entries": entries, "next": last if more else None}
