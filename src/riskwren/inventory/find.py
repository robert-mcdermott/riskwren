"""One search across every kind of record (INV-10).

It asks each kind's own list for what matches, so what a person may see is decided by the
rule every list already uses. A search cannot return a record its searcher could not open.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.db.refs import parse_ref
from riskwren.inventory import records
from riskwren.inventory.registry import TYPES, RecordType

# The order the kinds are shown in when nothing else ranks them.
ORDER = (
    "risk", "control", "document", "agreement", "issue", "system", "process", "third_party",
    "information", "scope", "evidence", "assessment", "exception", "indicator",
)  # fmt: skip
ACTIONS = "action"
LOOKED_AT = 60  # of each kind, before ranking
SHORTEST = 2


def _rank(words: list[str], ref: str, name: str) -> int:
    """How well a record answers the words: lower is better."""
    ref, name = ref.lower(), name.lower()
    whole = " ".join(words)
    if ref == whole:
        return 0
    if name == whole:
        return 1
    if ref.startswith(whole) or name.startswith(whole):
        return 2
    starts = set(name.replace("-", " ").replace(":", " ").split())
    if all(any(part.startswith(word) for part in starts) for word in words):
        return 3
    if all(word in name for word in words):
        return 4
    return 5  # found in the summary, or in what another system calls it


def kinds() -> list[RecordType]:
    known = [TYPES[key] for key in ORDER if key in TYPES]
    return known + [each for each in TYPES.values() if each not in known]


def everywhere(
    session: Session,
    principal: Principal,
    query: str | None,
    *,
    only: str | None = None,
    each: int = 6,
) -> dict[str, Any]:
    """What matches, in groups by kind, the best of each first."""
    words = (query or "").lower().split()[:8]
    asked = " ".join(words)
    out: dict[str, Any] = {"query": asked, "groups": [], "total": 0, "best": None}
    if len(asked) < SHORTEST:
        return out
    exact = parse_ref(asked.upper()) if len(words) == 1 else None
    groups = []
    for record_type in kinds():
        if only and only != record_type.key:
            continue
        # A search looks everywhere, closed and retired records too.
        rows, total = records.search(
            session, principal, record_type, {"q": asked, "anywhere": True}, limit=LOOKED_AT
        )
        if not total:
            continue
        ranked = sorted(
            ((_rank(words, row.ref, row.name), -row.updated_at.timestamp(), row) for row in rows),
            key=lambda found: found[:2],
        )
        items = [
            {
                "type": record_type.key,
                "ref": row.ref,
                "name": row.name,
                "summary": (row.summary or "")[:200] or None,
                "org_unit_id": row.org_unit_id,
                "status": getattr(row, "status", None),
                "rank": rank,
            }
            for rank, _, row in ranked[:each]
        ]
        if exact and items[0]["rank"] == 0:
            out["best"] = {"type": record_type.key, "ref": items[0]["ref"]}
        groups.append(
            {
                "type": record_type.key,
                "label": record_type.plural,
                "path": record_type.path,
                "total": total,
                "items": items,
            }
        )
    if only in (None, ACTIONS):
        groups += _actions(session, principal, asked, words, each)
    # The kind holding the best answer comes first; kinds otherwise keep their order.
    groups.sort(key=lambda group: min(item["rank"] for item in group["items"]))
    out["groups"] = groups
    out["total"] = sum(group["total"] for group in groups)
    return out


def _actions(
    session: Session, principal: Principal, asked: str, words: list[str], each: int
) -> list[dict[str, Any]]:
    """Actions are not records with owners and a unit of their own, but people look for
    them by name all the same."""
    from riskwren.treatment import service as treatment

    if len(words) != 1 and not asked:
        return []
    rows, total = treatment.search_actions(session, principal, {"q": asked}, limit=each)
    if not total:
        return []
    return [
        {
            "type": ACTIONS,
            "label": "actions",
            "path": "actions",
            "total": total,
            "items": [
                {
                    "type": ACTIONS,
                    "ref": row["ref"],
                    "name": row["title"],
                    "summary": None,
                    "org_unit_id": None,
                    "status": row["status"],
                    "rank": _rank(words, row["ref"], row["title"]),
                }
                for row in rows
            ],
        }
    ]
