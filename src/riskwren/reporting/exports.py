"""Exports: any list, as filtered, as CSV or JSON (RPT-05).

An export is the list its reader could already see, by the same rule, in a form another
program can read. Taking one is recorded in the history. The CSV of a record list carries
the columns an import understands first, so a list exported from one installation can be
imported into another; the columns after them say what is known and are not read back.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable, Mapping
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.errors import Invalid, NotFound
from riskwren.events import audit
from riskwren.inventory import records
from riskwren.inventory.registry import BY_PATH, RecordType
from riskwren.people import units
from riskwren.treatment import service as treatment

MAX_ROWS = 50_000
FORMATS = {"csv": "text/csv; charset=utf-8", "json": "application/json"}
# What a record list says beyond what an import reads back, by record type: a column name,
# and where in the record's card it is found.
KNOWN: dict[str, list[tuple[str, str]]] = {
    "risk": [
        ("status", "status"), ("inherent_rating", "ratings.inherent.rating"),
        ("residual_rating", "ratings.residual.rating"), ("target_rating", "ratings.target.rating"),
        ("standing", "standing"), ("response", "response"), ("next_review_on", "next_review_on"),
    ],
    "control": [
        ("design", "design"), ("operation", "operation"), ("state", "state"),
        ("rated_at", "rated_at"), ("risks", "risks"),
    ],
    "scope": [("status", "status"), ("frameworks", "frameworks"), ("controls", "controls")],
    "document": [
        ("kind", "kind"), ("status", "status"), ("number", "version_in_force"),
        ("working", "new_version"), ("next_review_on", "next_review_on"),
        ("review_state", "review"), ("controls", "controls"), ("requirements", "requirements"),
    ],
    "indicator": [
        ("status", "status"), ("state", "state"), ("measure", "measure"),
        ("direction", "direction"), ("warn_at", "warn_at"), ("breach_at", "breach_at"),
        ("frequency", "frequency"), ("last_value", "last_value"),
        ("last_read_on", "last_read_on"), ("risks", "risks"),
    ],
    "evidence": [
        ("status", "status"), ("kind", "kind"), ("collected_on", "collected_on"),
        ("valid_until", "valid_until"), ("state", "state"), ("data_class", "data_class"),
        ("supports", "supports"),
    ],
    "assessment": [
        ("status", "status"), ("scope", "scope.ref"), ("framework", "framework.key"),
        ("lead", "lead.name"), ("period_start", "period_start"), ("period_end", "period_end"),
        ("tests", "tests"), ("counted", "counted"), ("awaiting", "awaiting"),
        ("failing", "failing"),
    ],
    "issue": [
        ("severity", "severity"), ("status", "status"), ("source_kind", "source_kind"),
        ("due_on", "due_on"), ("original_due_on", "original_due_on"), ("moved", "moved"),
        ("overdue", "overdue"), ("actions_done", "progress.done"),
        ("actions", "progress.total"), ("raised_at", "created_at"), ("closed_at", "closed_at"),
    ],
    "exception": [
        ("state", "state"), ("to", "subject.name"), ("scope", "scope.ref"),
        ("starts_on", "starts_on"), ("expires_on", "expires_on"),
        ("requested_by", "requested_by"), ("decided_by", "decided_by"),
    ],
}  # fmt: skip


def _dig(source: Mapping[str, Any], path: str) -> Any:
    found: Any = source
    for part in path.split("."):
        found = found.get(part) if isinstance(found, Mapping) else None
    return found


def importable(record_type: RecordType) -> list[str]:
    """The columns an import reads, in the order an export writes them."""
    names = ["ref", "name", "summary", "unit", "owners"]
    if record_type.key == "risk":
        names.append("category")
    names += [field.name for field in record_type.fields]
    if record_type.is_thing:
        names += ["criticality", "data_class", "status"]
    if record_type.key == "control":
        names.append("status")
    return [*names, "tags", "restricted", "external_refs"]


def _records(
    session: Session, principal: Principal, record_type: RecordType, filters: Mapping[str, Any]
) -> tuple[list[str], list[dict[str, Any]]]:
    sort = str(filters.get("sort") or "ref")
    rows, total = records.search(
        session, principal, record_type, filters, sort=sort, limit=MAX_ROWS, offset=0
    )
    if total > MAX_ROWS:
        raise Invalid(
            "That is too much to export at once.",
            {"filters": f"Narrow the list to {MAX_ROWS} rows or fewer."},
        )
    ids = [row.id for row in rows]
    cards = records.cards(session, record_type, list(rows))
    owners = records.owners_of(session, record_type, ids)
    elsewhere = records.external_refs_of(session, record_type, ids)
    codes = {unit.id: unit.code or unit.name for unit in units.all_units(session)}
    first = importable(record_type)
    extra = [pair for pair in KNOWN.get(record_type.key, []) if pair[0] not in first]
    out = []
    for row, card in zip(rows, cards, strict=True):
        item: dict[str, Any] = {}
        for name in first:
            if name == "unit":
                item[name] = codes.get(row.org_unit_id, "")
            elif name == "owners":
                item[name] = [
                    owner["email"]
                    if owner["kind"] == "owner"
                    else f"{owner['kind']}:{owner['email']}"
                    for owner in owners.get(row.id, [])
                ]
            elif name == "external_refs":
                item[name] = [
                    f"{ref['system']}:{ref['value']}" for ref in elsewhere.get(row.id, [])
                ]
            elif name == "category":
                item[name] = card.get("category")
            else:
                item[name] = getattr(row, name, None)
        for name, path in extra:
            item[name] = _dig(card, path)
        out.append(item)
    return [*first, *(name for name, _ in extra)], out


def _actions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> Any:
    rows, total = treatment.search_actions(session, principal, filters, limit=MAX_ROWS)
    columns = ["ref", "title", "detail", "owner", "due_on", "original_due_on", "moved", "status",
               "overdue", "for", "plan", "completed_at", "completion_note"]  # fmt: skip
    out = [
        {
            **{name: row.get(name) for name in columns},
            "owner": row["owner"]["name"],
            "moved": len(row["extensions"] or []),
            "for": (row.get("risk") or row.get("source") or {}).get("ref"),
        }
        for row in rows
    ]
    return columns, out, total


def _plans(session: Session, principal: Principal, filters: Mapping[str, Any]) -> Any:
    rows = treatment.search_plans(session, principal, filters)
    columns = ["ref", "objective", "risk", "risk_name", "residual_rating", "target_rating",
               "owner", "due_on", "status", "overdue", "actions_done", "actions"]  # fmt: skip
    out = [
        {
            **{name: row.get(name) for name in columns},
            "risk": row["risk"]["ref"],
            "risk_name": row["risk"]["name"],
            "residual_rating": row["risk"]["residual_rating"],
            "owner": row["owner"]["name"],
            "actions_done": row["progress"]["done"],
            "actions": row["progress"]["total"],
        }
        for row in rows
    ]
    return columns, out, len(out)


def _acceptances(session: Session, principal: Principal, filters: Mapping[str, Any]) -> Any:
    rows = treatment.search_acceptances(session, principal, filters)
    columns = ["risk", "risk_name", "rating_accepted", "appetite", "state", "accepted_by",
               "accepted_at", "expires_on", "rationale", "conditions", "withdrawn_at",
               "withdrawn_by", "withdrawn_reason"]  # fmt: skip
    out = [
        {
            **{name: row.get(name) for name in columns},
            "risk": row["risk"]["ref"],
            "risk_name": row["risk"]["name"],
        }
        for row in rows
    ]
    return columns, out, len(out)


def _requirements(session: Session, principal: Principal, filters: Mapping[str, Any]) -> Any:
    from riskwren.compliance import frameworks
    from riskwren.db.models import Requirement

    framework = frameworks.by_key(session, str(filters.get("framework") or ""))
    by_id = {
        row.id: row
        for row in session.scalars(
            select(Requirement).where(Requirement.framework_id == framework.id)
        )
    }
    rows = sorted(by_id.values(), key=lambda row: row.sequence)
    columns = ["code", "title", "text", "parent", "kind", "citable"]
    out = [
        {
            "code": row.code,
            "title": row.title,
            "text": row.text,
            "parent": by_id[row.parent_id].code if row.parent_id in by_id else None,
            "kind": row.kind,
            "citable": row.is_citable,
        }
        for row in rows
    ]
    return columns, out, len(out)


def _statement(session: Session, principal: Principal, filters: Mapping[str, Any]) -> Any:
    from riskwren.compliance import scopes
    from riskwren.compliance.scopes import SCOPE

    scope = records.load(session, principal, SCOPE, str(filters.get("scope") or ""))
    found = scopes.statement(
        session, principal, scope, str(filters.get("framework") or ""),
        state=filters.get("state") or None, query=filters.get("q") or None,
    )  # fmt: skip
    columns = ["code", "title", "applicable", "state", "underlying", "exception", "reason",
               "decided_by", "controls"]  # fmt: skip
    out = [
        {
            **{name: row.get(name) for name in columns},
            "exception": (row.get("exception") or {}).get("ref"),
            "controls": [f"{c['ref']} {c['name']} ({c['readiness']})" for c in row["controls"]],
        }
        for row in found["requirements"]
    ]
    return columns, out, len(out)


LISTS: dict[str, Callable[[Session, Principal, Mapping[str, Any]], Any]] = {
    "actions": _actions,
    "plans": _plans,
    "acceptances": _acceptances,
    "requirements": _requirements,
    "statement": _statement,
}


def kinds() -> list[str]:
    return [*BY_PATH, *LISTS]


def _cell(value: Any) -> str:
    """A value as a spreadsheet cell. Text that a spreadsheet would run as a formula is
    written with an apostrophe before it, which an import takes off again."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple)):
        return "; ".join(_text(item) for item in value)
    return _guard(_text(value))


def _text(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return str(value.get("title") or value.get("name") or value.get("ref") or "")
    return str(value)


def _guard(text: str) -> str:
    return f"'{text}" if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def unguard(text: str) -> str:
    """Undo ``_guard``: what an export wrote is read back as it was."""
    return text[1:] if text[:2] in ("'=", "'+", "'-", "'@") else text


def to_csv(columns: list[str], rows: list[dict[str, Any]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_cell(row.get(name)) for name in columns])
    return out.getvalue()


def to_json(kind: str, columns: list[str], rows: list[dict[str, Any]]) -> str:
    def plain(value: Any) -> Any:
        return value.isoformat() if isinstance(value, (date, datetime)) else str(value)

    return json.dumps({"list": kind, "columns": columns, "rows": rows}, indent=2, default=plain)


def export(
    session: Session, principal: Principal, kind: str, form: str, filters: Mapping[str, Any]
) -> tuple[str, str, str]:
    """A list as the person may see it, filtered as asked: its text, its media type, and a
    name for the file. Recorded in the history."""
    if form not in FORMATS:
        raise Invalid("The list was not exported.", {"format": "Use csv or json."})
    filters = {key: value for key, value in filters.items() if value not in (None, "")}
    for flag in ("mine", "overdue"):
        if flag in filters:
            filters[flag] = str(filters[flag]).lower() in ("true", "1", "yes")
    record_type = BY_PATH.get(kind)
    if record_type is not None:
        columns, rows = _records(session, principal, record_type, filters)
    elif kind in LISTS:
        columns, rows, total = LISTS[kind](session, principal, filters)
        if total > len(rows):
            raise Invalid(
                "That is too much to export at once.",
                {"filters": f"Narrow the list to {MAX_ROWS} rows or fewer."},
            )
    else:
        raise NotFound(f"There is no list called {kind!r}.")
    asked = {key: str(value) for key, value in sorted(filters.items()) if key != "sort"}
    audit.record(
        session, "exported", subject_kind="export",
        changes={"list": [None, kind], "format": [None, form], "rows": [None, len(rows)],
                 "filters": [None, asked]},
    )  # fmt: skip
    text = to_csv(columns, rows) if form == "csv" else to_json(kind, columns, rows)
    return text, FORMATS[form], f"riskwren-{kind}.{form}"
