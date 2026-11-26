"""The risk taxonomy: a tree of categories, each with an appetite of its own or its parent's."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core import scoring
from riskwren.core.errors import Invalid, NotFound, PermissionDenied
from riskwren.db.models import RiskCategory
from riskwren.events import audit
from riskwren.risk import method as methods


def all_(session: Session) -> list[RiskCategory]:
    return list(
        session.scalars(select(RiskCategory).order_by(RiskCategory.position, RiskCategory.id))
    )


def by_key(session: Session, key: str) -> RiskCategory:
    found = session.scalars(select(RiskCategory).where(RiskCategory.key == key)).first()
    if found is None:
        raise NotFound(f"There is no risk category {key!r}.")
    return found


class Tree:
    """Every category, loaded once, with what each inherits from above."""

    def __init__(self, session: Session) -> None:
        self.rows = all_(session)
        self.by_id = {row.id: row for row in self.rows}

    def appetite(self, category_id: int | None) -> str | None:
        """The appetite in force for a category: its own, or the nearest set above it."""
        seen = 0
        while category_id is not None and seen < 20:
            row = self.by_id.get(category_id)
            if row is None:
                return None
            if row.appetite:
                return row.appetite
            category_id, seen = row.parent_id, seen + 1
        return None

    def path(self, category_id: int | None) -> list[RiskCategory]:
        """From the top of the tree down to this category."""
        found: list[RiskCategory] = []
        while category_id is not None and len(found) < 20:
            row = self.by_id.get(category_id)
            if row is None:
                break
            found.append(row)
            category_id = row.parent_id
        return found[::-1]

    def with_descendants(self, category_id: int) -> set[int]:
        found = {category_id}
        grew = True
        while grew:
            more = {row.id for row in self.rows if row.parent_id in found} - found
            grew = bool(more)
            found |= more
        return found

    def label(self, category_id: int | None) -> str:
        return " · ".join(row.name for row in self.path(category_id))

    def view(self) -> list[dict[str, Any]]:
        def node(row: RiskCategory) -> dict[str, Any]:
            return {
                "key": row.key,
                "name": row.name,
                "description": row.description,
                "appetite": row.appetite,
                "appetite_in_force": self.appetite(row.id),
                "status": row.status,
                "children": [node(c) for c in self.rows if c.parent_id == row.id],
            }

        return [node(row) for row in self.rows if row.parent_id is None]


def update(
    session: Session, principal: Principal, category: RiskCategory, changes: Mapping[str, Any]
) -> RiskCategory:
    """Rename a category, change its appetite, or retire it. A category in use is never
    removed: its risks keep it."""
    if not principal.configures:
        raise PermissionDenied("Only those who run the program can change the risk categories.")
    errors: dict[str, str] = {}
    if "name" in changes:
        name = str(changes["name"] or "").strip()
        if not name or len(name) > 120:
            errors["name"] = "Give the category a name of up to 120 characters."
        else:
            category.name = name
    if "description" in changes:
        category.description = str(changes["description"] or "").strip() or None
    if "appetite" in changes:
        appetite = changes["appetite"] or None
        ratings = scoring.rating_keys(methods.current(session))
        if appetite is not None and appetite not in ratings:
            errors["appetite"] = f"Choose one of the ratings: {', '.join(ratings)}."
        elif appetite is None and category.parent_id is None:
            errors["appetite"] = "A category at the top of the tree needs an appetite of its own."
        else:
            category.appetite = appetite
    if "status" in changes:
        if changes["status"] not in ("active", "retired"):
            errors["status"] = "Use active or retired."
        else:
            category.status = changes["status"]
    if errors:
        session.expire(category)
        raise Invalid("The category was not saved.", errors)
    with audit.operation(session, "risk_category.edit"):
        session.flush()
    return category
