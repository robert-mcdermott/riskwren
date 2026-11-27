"""Records that look like the same thing written down twice (INV-12).

Likeness is judged on names alone, by rules a person can follow: the same words in any
order, or nearly the same spelling. Nothing is merged or changed here. A pair is shown to
people who can look at both, and they say whether it is one thing or two.
"""

from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.db.models import NotDuplicate
from riskwren.events import audit
from riskwren.inventory import access
from riskwren.inventory.registry import TYPES, RecordType

SMALL_WORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "at",
        "by",
        "for",
        "from",
        "in",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
        "our",
        "its",
        "is",
        "are",
        "not",
        "no",
    ]
)
CLOSE = 0.88  # how alike two spellings must be to be called the same
LOOSE = 0.72  # while someone is still typing a name, cast wider
BUSY = 40  # a word on more records than this says nothing about any of them


def words(name: str) -> tuple[str, ...]:
    """The words of a name that carry meaning, in a fixed order."""
    found = re.findall(r"[a-z0-9]+", name.lower())
    return tuple(sorted({word for word in found if word not in SMALL_WORDS}))


def likeness(one: str, other: str) -> float:
    """From 0 to 1: how alike two names are."""
    first, second = words(one), words(other)
    if not first or not second:
        return 0.0
    if first == second:
        return 1.0
    shared = len(set(first) & set(second)) / len(set(first) | set(second))
    spelled = SequenceMatcher(None, " ".join(first), " ".join(second)).ratio()
    # Names of a single word are judged on spelling alone: one shared word is the whole of it.
    return spelled if min(len(first), len(second)) < 2 else max(spelled, shared)


def _candidates(
    session: Session, principal: Principal, record_type: RecordType
) -> list[tuple[int, str, str, int | None, str | None]]:
    """Every record of this kind the person may see that is still in use."""
    model: Any = record_type.model
    columns = [model.id, model.ref, model.name, model.org_unit_id]
    status = getattr(model, "status", None)
    statement = select(*columns, status if status is not None else model.ref)
    seen = access.visible(session, principal, record_type)
    if seen is not None:
        statement = statement.where(seen)
    if status is not None:
        live = record_type.extra.get("live_statuses", ("active", "open"))
        statement = statement.where(status.in_(live))
    return [tuple(row) for row in session.execute(statement.order_by(model.id))]  # type: ignore[misc]


def _dismissed(session: Session, record_type: RecordType) -> set[tuple[int, int]]:
    return {
        (row.low_id, row.high_id)
        for row in session.scalars(
            select(NotDuplicate).where(NotDuplicate.record_type == record_type.key)
        )
    }


def _same_thing(score: float, unit_a: int | None, unit_b: int | None, bar: float) -> bool:
    # Two units often keep a record each for the same thing, on purpose: the same risk in
    # two labs. Across units only the very same name counts.
    return score >= (bar if unit_a == unit_b else 1.0)


def similar(
    session: Session,
    principal: Principal,
    record_type: RecordType,
    name: str,
    *,
    unit: int | None = None,
    except_id: int | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Records already here that a new one with this name might be."""
    if len(words(name)) == 0 or len(name.strip()) < 4:
        return []
    ignored = _dismissed(session, record_type) if except_id else set()
    found = []
    for record_id, ref, other, other_unit, _ in _candidates(session, principal, record_type):
        if record_id == except_id:
            continue
        if except_id and (min(record_id, except_id), max(record_id, except_id)) in ignored:
            continue
        score = likeness(name, other)
        same_unit = unit is None or unit == other_unit
        if score >= (LOOSE if same_unit else 1.0):
            card = {"type": record_type.key, "ref": ref, "name": other,
                    "org_unit_id": other_unit, "likeness": round(score, 2)}  # fmt: skip
            found.append((score, card))
    found.sort(key=lambda each: (-each[0], each[1]["ref"]))
    return [each for _, each in found[:limit]]


def pairs(
    session: Session, principal: Principal, record_type: RecordType, *, limit: int = 100
) -> list[dict[str, Any]]:
    """Likely duplicates among the records of one kind, the most alike first."""
    rows = _candidates(session, principal, record_type)
    by_word: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        for word in words(row[2]):
            by_word[word].append(index)
    together: set[tuple[int, int]] = set()
    for members in by_word.values():
        if len(members) > BUSY:
            continue
        together.update((a, b) for at, a in enumerate(members) for b in members[at + 1 :])
    # Records with exactly the same words are compared however common the words are.
    same: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        same[words(row[2])].append(index)
    for members in same.values():
        together.update((a, b) for at, a in enumerate(members) for b in members[at + 1 :])
    ignored = _dismissed(session, record_type)
    found = []
    for a, b in together:
        one, other = rows[a], rows[b]
        if (one[0], other[0]) in ignored:
            continue
        score = likeness(one[2], other[2])
        if _same_thing(score, one[3], other[3], CLOSE):
            found.append(
                {
                    "type": record_type.key,
                    "likeness": round(score, 2),
                    "records": [
                        {"ref": each[1], "name": each[2], "org_unit_id": each[3]}
                        for each in (one, other)
                    ],
                }
            )
    found.sort(key=lambda pair: (-pair["likeness"], pair["records"][0]["ref"]))
    return found[:limit]


def everything(session: Session, principal: Principal) -> list[dict[str, Any]]:
    """Likely duplicates of every kind, for whoever keeps the record in order."""
    out = []
    for record_type in TYPES.values():
        if record_type.extra.get("no_duplicates"):
            continue
        found = pairs(session, principal, record_type)
        if found:
            out.append(
                {"type": record_type.key, "label": record_type.plural, "path": record_type.path,
                 "pairs": found}
            )  # fmt: skip
    return out


def dismiss(
    session: Session, principal: Principal, record_type: RecordType, one: Any, other: Any
) -> None:
    """Say that two records are different things, so the pair is not suggested again."""
    if one.id == other.id:
        raise Invalid("Nothing was changed.", {"refs": "Name two different records."})
    if not any(access.can_edit(session, principal, record_type, each) for each in (one, other)):
        raise PermissionDenied("Someone who can edit one of the two records says this.")
    low, high = sorted((one.id, other.id))
    already = session.scalars(
        select(NotDuplicate).where(
            NotDuplicate.record_type == record_type.key,
            NotDuplicate.low_id == low,
            NotDuplicate.high_id == high,
        )
    ).first()
    if already is not None:
        return
    with audit.operation(session, f"{record_type.key}.not_duplicate"):
        session.add(
            NotDuplicate(
                record_type=record_type.key, low_id=low, high_id=high,
                said_by_name=principal.name, created_at=utc_now(),
            )
        )  # fmt: skip
        session.flush()
