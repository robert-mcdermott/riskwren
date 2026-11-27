"""Vocabularies: the lists of values an organization can rename, extend, and retire.

Records store a value's stable ``key``, never its label, so renaming a value never rewrites
history. Until an organization edits a vocabulary, the default program pack's are what it has.
"""

from __future__ import annotations

import json
import re
from importlib import resources
from typing import Any

from sqlalchemy.orm import Session

from riskwren.core.errors import Invalid
from riskwren.program import settings

DEFAULT_PACK = "default-program.json"


def default_pack() -> dict[str, Any]:
    """The built-in program pack, as shipped."""
    text = resources.files("riskwren.resources").joinpath("packs", DEFAULT_PACK).read_text("utf-8")
    return json.loads(text)


DEFAULTS: dict[str, list[dict[str, Any]]] = default_pack()["vocabularies"]
NAMES = tuple(DEFAULTS)


def _setting(name: str) -> str:
    return f"vocab.{name}"


def get(session: Session, name: str) -> list[dict[str, Any]]:
    """Every value of a vocabulary, in order, retired ones included."""
    if name not in DEFAULTS:
        raise KeyError(name)
    return settings.get(session, _setting(name), None) or [dict(item) for item in DEFAULTS[name]]


def all_(session: Session) -> dict[str, list[dict[str, Any]]]:
    return {name: get(session, name) for name in NAMES}


def keys(session: Session, name: str, *, active_only: bool = True) -> list[str]:
    return [item["key"] for item in get(session, name) if not (active_only and item.get("retired"))]


def labels(session: Session, name: str) -> dict[str, str]:
    return {item["key"]: item["label"] for item in get(session, name)}


def rank(session: Session, name: str, key: str | None) -> int:
    """Where a value sits in an ordered vocabulary (0 first); -1 if it is not in it."""
    order = keys(session, name, active_only=False)
    return order.index(key) if key in order else -1


def check(
    session: Session, name: str, key: str | None, field: str, *, required: bool = False
) -> None:
    """Raise ``Invalid`` unless ``key`` is a current value of the vocabulary."""
    if key in (None, ""):
        if required:
            raise Invalid("The record is not valid.", {field: "Choose a value."})
        return
    if key not in keys(session, name):
        raise Invalid("The record is not valid.", {field: f"{key!r} is not one of the choices."})


def check_many(session: Session, name: str, values: list[str] | None, field: str) -> list[str]:
    allowed = keys(session, name)
    chosen = list(dict.fromkeys(values or []))
    unknown = [value for value in chosen if value not in allowed]
    if unknown:
        raise Invalid(
            "The record is not valid.", {field: f"{unknown[0]!r} is not one of the choices."}
        )
    return chosen


# Lists whose values the software itself gives meaning to: a severity sets a clock, a kind
# of link says what it joins. Their names and meanings can be changed; values are added or
# taken away by a program pack.
LABELS_ONLY = ("issue_severities", "link_kinds", "control_frequencies", "owner_kinds")
# Values that are the default somewhere, and so cannot be retired.
KEPT = {
    "criticalities": {"moderate"},
    "lifecycles": {"in_service"},
    "issue_sources": {"observation", "test"},
    "unit_kinds": {"organization"},
}
KEY = re.compile(r"[a-z][a-z0-9_]{0,39}")


def describe(session: Session) -> list[dict[str, Any]]:
    """Every vocabulary with what may be done to it here."""
    return [
        {"name": name, "items": get(session, name), "labels_only": name in LABELS_ONLY,
         "kept": sorted(KEPT.get(name, ()))}
        for name in NAMES
    ]  # fmt: skip


def edit(session: Session, name: str, items: Any) -> list[dict[str, Any]]:
    """Change a vocabulary from the app: rename, describe, reorder, add, and retire. What a
    value's key is never changes, and what the software relies on stays."""
    if name not in DEFAULTS:
        raise Invalid("There is no such vocabulary.", {"name": name})
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise Invalid("The vocabulary is not valid.", {"items": "Send the whole list of values."})
    have = {item["key"]: item for item in get(session, name)}
    cleaned = []
    for item in items:
        key = str(item.get("key", "")).strip()
        if key not in have and not KEY.fullmatch(key):
            raise Invalid(
                "The vocabulary is not valid.",
                {"items": f"{key!r} is not a key: use lower-case letters, digits, underscores."},
            )
        if key not in have and name in LABELS_ONLY:
            raise Invalid(
                "The vocabulary is not valid.",
                {"items": "Values of this list are added by a program pack, not here."},
            )
        if item.get("retired") and key in KEPT.get(name, ()):
            raise Invalid(
                "The vocabulary is not valid.",
                {"items": f"{have[key]['label']} is what new records start with, so it stays."},
            )
        if item.get("retired") and name in LABELS_ONLY:
            raise Invalid(
                "The vocabulary is not valid.",
                {"items": "Values of this list cannot be retired here."},
            )
        # What the list holds beyond a name and a meaning stays as it was.
        merged = {**have.get(key, {}), "key": key, "label": str(item.get("label", "")).strip()}
        if "description" in item:
            merged["description"] = str(item.get("description") or "").strip()
        if item.get("retired"):
            merged["retired"] = True
        else:
            merged.pop("retired", None)
        cleaned.append(merged)
    if not any(not item.get("retired") for item in cleaned):
        raise Invalid("The vocabulary is not valid.", {"items": "Keep at least one value in use."})
    put(session, name, cleaned)
    return get(session, name)


def put(session: Session, name: str, items: list[dict[str, Any]]) -> None:
    """Replace a vocabulary. Keys already in use may be relabelled or retired, never removed:
    the caller is responsible for checking permission."""
    if name not in DEFAULTS:
        raise Invalid("There is no such vocabulary.", {"name": name})
    seen: set[str] = set()
    cleaned = []
    for item in items:
        key, label = str(item.get("key", "")).strip(), str(item.get("label", "")).strip()
        if not key or not label:
            raise Invalid(
                "The vocabulary is not valid.", {"items": "Every value needs a key and a label."}
            )
        if key in seen:
            raise Invalid(
                "The vocabulary is not valid.", {"items": f"The key {key!r} appears twice."}
            )
        seen.add(key)
        cleaned.append({**item, "key": key, "label": label})
    missing = [key for key in keys(session, name, active_only=False) if key not in seen]
    if missing:
        raise Invalid(
            "The vocabulary is not valid.",
            {"items": f"{missing[0]!r} is in use and cannot be removed. Retire it instead."},
        )
    settings.put(session, _setting(name), cleaned)
