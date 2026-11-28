"""Fields of the organization's own (PLT-18): what a kind of record must also say here, such as
a cost center on a system or a contract owner on a third party.

The fields are part of the program, kept as the setting ``custom_fields``, and changed by those
who run the program. A value is kept on its record (``custom_value``), recorded in the record's
history, and shown with the record. A field that is taken away keeps its values, unshown, so
that bringing it back brings them back.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.db.models import CustomValue
from riskwren.events import audit
from riskwren.program import settings

SETTING = "custom_fields"
KINDS = {"text": "Text", "number": "A number", "date": "A date", "choice": "One of a list"}
# The kinds of record that may carry fields of their own.
TYPES = ("process", "system", "third_party", "service", "information", "site", "risk", "control")
MOST = 12
_KEY = re.compile(r"^[a-z][a-z0-9_]{1,39}$")


def all_(session: Session) -> dict[str, list[dict[str, Any]]]:
    found = settings.get(session, SETTING, {}) or {}
    return {key: found.get(key, []) for key in TYPES}


def of(session: Session, type_key: str) -> list[dict[str, Any]]:
    """The fields a kind of record carries, in order. None for a kind that cannot carry any."""
    if type_key not in TYPES:
        return []
    return all_(session)[type_key]


def problems(items: Any) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not isinstance(items, list) or len(items) > MOST:
        return {"fields": f"Give a list of no more than {MOST} fields."}
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            return {"fields": "Each field needs a key, a label, and a kind."}
        key, label = str(item.get("key", "")), str(item.get("label", "")).strip()
        if not _KEY.match(key):
            errors["fields"] = (f"“{key}” cannot be a key: use lowercase letters, digits, and "
                                "underscores, starting with a letter.")  # fmt: skip
        elif key in seen:
            errors["fields"] = f"The key {key} is used twice."
        elif not label or len(label) > 60:
            errors["fields"] = f"Give {key} a label of up to 60 characters."
        elif item.get("kind") not in KINDS:
            errors["fields"] = f"The kind of {key} is one of: {', '.join(KINDS)}."
        elif item.get("kind") == "choice":
            choices = item.get("choices")
            if (
                not isinstance(choices, list)
                or not 2 <= len(choices) <= 30
                or any(not isinstance(c, str) or not c.strip() or len(c) > 60 for c in choices)
                or len({c.strip() for c in choices}) != len(choices)
            ):
                errors["fields"] = (
                    f"Give {key} from 2 to 30 different choices of up to 60 characters."
                )
        elif len(str(item.get("help") or "")) > 200:
            errors["fields"] = f"Keep the help for {key} to 200 characters."
        seen.add(key)
    return errors


def _tidy(item: dict[str, Any]) -> dict[str, Any]:
    out = {"key": item["key"], "label": str(item["label"]).strip(), "kind": item["kind"]}
    if item["kind"] == "choice":
        out["choices"] = [choice.strip() for choice in item["choices"]]
    if str(item.get("help") or "").strip():
        out["help"] = str(item["help"]).strip()
    if item.get("required"):
        out["required"] = True
    return out


def save(session: Session, principal: Principal, type_key: str, items: Any) -> list[dict[str, Any]]:
    """Set the fields a kind of record carries."""
    if not principal.configures:
        raise PermissionDenied("Only those who run the program change its fields.")
    if type_key not in TYPES:
        raise Invalid(
            "Nothing was changed.", {"type": f"Fields can be added to: {', '.join(TYPES)}."}
        )
    errors = problems(items)
    if errors:
        raise Invalid("Nothing was changed.", errors)
    found = all_(session)
    found[type_key] = [_tidy(item) for item in items]
    with audit.operation(session, "program.fields", record_type=type_key):
        settings.put(session, SETTING, {key: value for key, value in found.items() if value})
    return found[type_key]


def _value(field: dict[str, Any], given: Any) -> tuple[Any, str | None]:
    """The value to keep, or why it cannot be kept. None takes the value away."""
    if given is None or (isinstance(given, str) and not given.strip()):
        return None, "This is needed." if field.get("required") else None
    kind = field["kind"]
    if kind == "number":
        if isinstance(given, bool):
            return None, "Give a number."
        try:
            number = float(given)
        except (TypeError, ValueError):
            return None, "Give a number."
        return (int(number) if number.is_integer() else number), None
    if kind == "date":
        try:
            return date.fromisoformat(str(given)).isoformat(), None
        except ValueError:
            return None, "Give a date as YYYY-MM-DD."
    text = str(given).strip()
    if kind == "choice" and text not in field.get("choices", []):
        return None, f"Choose one of: {', '.join(field.get('choices', []))}."
    if len(text) > 400:
        return None, "Keep this to 400 characters."
    return text, None


def clean(
    session: Session, type_key: str, given: Any, errors: Any, *, creating: bool
) -> dict[str, Any] | None:
    """Check what was given for a record's own fields. Returns the values to keep, key by key,
    with None for one to take away; errors are added under ``custom.KEY``."""
    fields = of(session, type_key)
    if not fields:
        if given:
            errors.add("custom", "This kind of record has no fields of the organization's own.")
        return None
    if not isinstance(given, dict):
        errors.add("custom", "Give the fields as an object of key and value.")
        return None
    known = {field["key"]: field for field in fields}
    for key in given:
        if key not in known:
            errors.add("custom", f"There is no field {key}.")
    out: dict[str, Any] = {}
    for key, field in known.items():
        if key not in given and not (creating and field.get("required")):
            continue
        value, problem = _value(field, given.get(key))
        if problem:
            errors.add(f"custom.{key}", problem)
        else:
            out[key] = value
    return out


def store(session: Session, type_key: str, record_id: int, wanted: dict[str, Any]) -> None:
    have = {
        row.field: row
        for row in session.scalars(
            select(CustomValue).where(
                CustomValue.record_type == type_key, CustomValue.record_id == record_id
            )
        )
    }
    for key, value in wanted.items():
        row = have.get(key)
        if value is None:
            if row is not None:
                session.delete(row)
        elif row is None:
            session.add(CustomValue(record_type=type_key, record_id=record_id, field=key,
                                    value=value))  # fmt: skip
        elif row.value != value:
            row.value = value
    session.flush()


def values_of(session: Session, type_key: str, ids: list[int]) -> dict[int, dict[str, Any]]:
    found: dict[int, dict[str, Any]] = {}
    if not ids or type_key not in TYPES:
        return found
    for row in session.scalars(
        select(CustomValue).where(
            CustomValue.record_type == type_key, CustomValue.record_id.in_(ids)
        )
    ):
        found.setdefault(row.record_id, {})[row.field] = row.value
    return found


def view(session: Session, type_key: str, record_id: int) -> list[dict[str, Any]]:
    """The record's own fields, each with its value, in the program's order."""
    fields = of(session, type_key)
    if not fields:
        return []
    values = values_of(session, type_key, [record_id]).get(record_id, {})
    return [{**field, "value": values.get(field["key"])} for field in fields]
