"""What a record ought to say and does not yet (INV-12).

Each kind of record has a short list of expected facts. A fact is one condition, used three
ways: to say what one record is missing, to filter a list to the records missing it, and to
count them. Because it is the same condition each time, a count is always the length of the
list behind it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, exists, func, not_, or_, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.errors import Invalid
from riskwren.db.models import Account, RecordLink, RecordOwner
from riskwren.inventory.registry import TYPES, RecordType


@dataclass(frozen=True)
class Expected:
    """One fact a record should carry. ``lacking`` is true of a record that does not."""

    key: str
    label: str  # as it reads after "Missing: "
    lacking: Callable[[Any], Any]
    why: str = ""


def _blank(column: Any) -> Any:
    return or_(column.is_(None), func.trim(column) == "")


def _no_owner(record_type: RecordType) -> Callable[[Any], Any]:
    def lacking(model: Any) -> Any:
        return not_(
            exists(
                select(RecordOwner.id)
                .join(Account, Account.id == RecordOwner.account_id)
                .where(
                    RecordOwner.record_type == record_type.key,
                    RecordOwner.record_id == model.id,
                    RecordOwner.kind == "owner",
                    Account.status != "disabled",
                )
            )
        )

    return lacking


def _no_links(record_type: RecordType) -> Callable[[Any], Any]:
    def lacking(model: Any) -> Any:
        return not_(
            exists(
                select(RecordLink.id).where(
                    or_(
                        and_(
                            RecordLink.from_type == record_type.key, RecordLink.from_id == model.id
                        ),
                        and_(RecordLink.to_type == record_type.key, RecordLink.to_id == model.id),
                    )
                )
            )
        )

    return lacking


# The kinds of record that are described once and then relied on. An assessment, an issue,
# or an exception has a life of its own, and says what it lacks in its own words.
DESCRIBED = (
    "process", "system", "third_party", "information", "risk", "control", "indicator", "document",
    "agreement",
)  # fmt: skip


def expected(record_type: RecordType) -> list[Expected]:
    """What a record of this kind should say."""
    if record_type.key not in DESCRIBED:
        return []
    rules = [
        Expected("owner", "an owner who can sign in", _no_owner(record_type),
                 "Nobody answers for it."),
    ]  # fmt: skip
    if record_type.is_thing:
        rules.append(
            Expected("data_class", "the class of data it handles",
                     lambda model: model.data_class.is_(None),
                     "What it must be protected as is unknown.")
        )  # fmt: skip
        rules.append(
            Expected("links", "a link to anything else", _no_links(record_type),
                     "Nothing is known to rely on it, or it on anything.")
        )  # fmt: skip
    # A name, a kind, and a unit are asked for when a record is added. A summary is not
    # expected: many records are plain from their name, and a rule that nearly every record
    # fails tells nobody anything.
    if record_type.key == "system":
        rules.append(
            Expected("hosting", "where it is hosted", lambda model: model.hosting.is_(None),
                     "Who keeps it running, and where, is unknown.")
        )  # fmt: skip
    if record_type.key == "information":
        rules.append(
            Expected("held_in", "where it is held", lambda model: _blank(model.held_in),
                     "Nobody can say which systems to protect for its sake.")
        )  # fmt: skip
    rules += record_type.extra.get("expected", [])
    return rules


def _active(record_type: RecordType, model: Any) -> Any:
    """Only records still in use are expected to be complete."""
    status = getattr(model, "status", None)
    if status is None:
        return None
    live = record_type.extra.get("live_statuses", ("active", "open"))
    return status.in_(live)


def condition(session: Session, record_type: RecordType, key: str) -> Any:
    """What narrows a list to the records missing one fact, or (``any``) missing anything."""
    model: Any = record_type.model
    rules = expected(record_type)
    chosen = rules if key == "any" else [rule for rule in rules if rule.key == key]
    if not chosen:
        known = ", ".join(["any", *(rule.key for rule in rules)])
        raise Invalid(
            "The list could not be filtered.",
            {"missing": f"Use one of: {known}." if rules else "Nothing is expected of these."},
        )
    lacking = or_(*(rule.lacking(model) for rule in chosen))
    live = _active(record_type, model)
    return lacking if live is None else and_(live, lacking)


def missing_for(
    session: Session, record_type: RecordType, ids: Iterable[int]
) -> dict[int, list[dict[str, str]]]:
    """What each of these records is missing, in the order the facts are listed."""
    ids = list(ids)
    rules = expected(record_type)
    found: dict[int, list[dict[str, str]]] = {}
    if not ids or not rules:
        return found
    model: Any = record_type.model
    live = _active(record_type, model)
    for rule in rules:
        where = [model.id.in_(ids), rule.lacking(model)]
        if live is not None:
            where.append(live)
        for record_id in session.scalars(select(model.id).where(*where)):
            found.setdefault(record_id, []).append(
                {"key": rule.key, "label": rule.label, "why": rule.why}
            )
    return found


def summary(
    session: Session, principal: Principal, unit: int | None = None
) -> list[dict[str, Any]]:
    """For each kind of record, how many the person may see are missing something, and
    what. Each figure carries the filters of the list it counts."""
    from riskwren.inventory import records

    out = []
    scope: dict[str, Any] = {"unit": unit} if unit else {}
    for record_type in TYPES.values():
        rules = expected(record_type)
        if not rules:
            continue

        def count(filters: dict[str, Any], record_type: RecordType = record_type) -> int:
            return records.search(session, principal, record_type, filters, limit=1)[1]

        live = record_type.extra.get("live_filters", {"status": "active"})
        total = count({**scope, **live})
        if not total:
            continue
        figures = []
        for rule in rules:
            number = count({**scope, "missing": rule.key})
            if number:
                figures.append(
                    {"key": rule.key, "label": rule.label, "why": rule.why, "count": number,
                     "filters": {**scope, "missing": rule.key}}
                )  # fmt: skip
        out.append(
            {
                "type": record_type.key,
                "label": record_type.plural,
                "path": record_type.path,
                "total": total,
                "incomplete": count({**scope, "missing": "any"}),
                "filters": {**scope, "missing": "any"},
                "missing": figures,
            }
        )
    return out
