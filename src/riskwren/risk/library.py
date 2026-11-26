"""The risk library: reusable statements from which a risk can be started in one step."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from riskwren.core.errors import NotFound
from riskwren.db.models import RiskLibraryEntry
from riskwren.risk import categories


def load(session: Session, pack: dict[str, Any]) -> int:
    """Bring a risk-library pack in. Entries are matched by key, so loading a newer pack
    corrects wording without disturbing risks already started from it."""
    source = str(pack["pack"]["key"])
    have = {row.key: row for row in session.scalars(select(RiskLibraryEntry))}
    changed = 0
    for item in pack["risks"]:
        row = have.get(item["key"])
        values = {
            "category_key": item["category"],
            "title": item["title"],
            "cause": item["cause"],
            "event": item["event"],
            "consequence": item["consequence"],
            "suggested_controls": list(item.get("controls", [])),
            "source_pack": source,
        }
        if row is None:
            session.add(RiskLibraryEntry(key=item["key"], **values))
            changed += 1
        elif any(getattr(row, name) != value for name, value in values.items()):
            for name, value in values.items():
                setattr(row, name, value)
            changed += 1
    session.flush()
    return changed


def by_key(session: Session, key: str) -> RiskLibraryEntry:
    found = session.scalars(select(RiskLibraryEntry).where(RiskLibraryEntry.key == key)).first()
    if found is None:
        raise NotFound(f"There is no library risk {key!r}.")
    return found


def view(row: RiskLibraryEntry, tree: categories.Tree | None = None) -> dict[str, Any]:
    label = None
    if tree is not None:
        category = next((c for c in tree.rows if c.key == row.category_key), None)
        label = tree.label(category.id) if category else None
    return {
        "key": row.key,
        "category": row.category_key,
        "category_label": label,
        "title": row.title,
        "cause": row.cause,
        "event": row.event,
        "consequence": row.consequence,
        "suggested_controls": row.suggested_controls,
    }


def search(
    session: Session, *, query: str | None = None, category: str | None = None
) -> list[dict[str, Any]]:
    tree = categories.Tree(session)
    statement = select(RiskLibraryEntry).order_by(RiskLibraryEntry.id)
    if category:
        top = categories.by_key(session, category)
        keys = [row.key for row in tree.rows if row.id in tree.with_descendants(top.id)]
        statement = statement.where(RiskLibraryEntry.category_key.in_(keys))
    words = (query or "").strip().lower()
    if words:
        like = f"%{words}%"
        statement = statement.where(
            or_(
                func.lower(RiskLibraryEntry.title).like(like),
                func.lower(RiskLibraryEntry.cause).like(like),
                func.lower(RiskLibraryEntry.event).like(like),
                func.lower(RiskLibraryEntry.consequence).like(like),
            )
        )
    return [view(row, tree) for row in session.scalars(statement)]
