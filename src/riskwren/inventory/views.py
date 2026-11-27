"""Saved views: a list as someone filtered it, kept under a name (INV-10).

A view is the filters and the sort, never the rows. Sharing one shares a question, and each
person who opens it gets their own answer, cut to what they may see.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import SavedView

PATH = re.compile(r"^/[a-z0-9][a-z0-9/-]{0,78}$")
DROPPED = ("cursor",)  # where someone was in a list is not part of the question
MOST = 40  # for one person on one list


def may_share(principal: Principal) -> bool:
    """A shared view is on everyone's list, so it is for those who look after one."""
    return bool(
        principal.is_admin or principal.manages_somewhere or principal.stewards
        or principal.assesses or principal.reads_all
    )  # fmt: skip


def clean_query(query: str | None) -> str:
    pairs = [
        (key, value)
        for key, value in parse_qsl((query or "").lstrip("?"), keep_blank_values=False)
        if key not in DROPPED
    ]
    return urlencode(sorted(pairs))


def view(row: SavedView, principal: Principal) -> dict[str, Any]:
    mine = row.account_id == principal.account_id
    return {
        "id": row.id,
        "name": row.name,
        "path": row.path,
        "query": row.query,
        "href": f"{row.path}?{row.query}" if row.query else row.path,
        "shared": row.shared,
        "mine": mine,
        "by": row.owner_name,
        "can_change": mine or (row.shared and principal.is_admin),
    }


def listed(session: Session, principal: Principal, path: str | None = None) -> list[dict[str, Any]]:
    """The person's own views and the shared ones, their own first."""
    statement = select(SavedView).where(
        or_(SavedView.account_id == principal.account_id, SavedView.shared.is_(True))
    )
    if path:
        statement = statement.where(SavedView.path == path)
    rows = session.scalars(statement.order_by(SavedView.name, SavedView.id)).all()
    rows = sorted(rows, key=lambda row: (row.account_id != principal.account_id, row.name.lower()))
    return [view(row, principal) for row in rows]


def _checked(
    session: Session, principal: Principal, values: dict[str, Any], row: SavedView | None
) -> dict[str, Any]:
    errors: dict[str, str] = {}
    out: dict[str, Any] = {}
    if row is None or values.get("name") is not None:
        name = " ".join(str(values.get("name") or "").split())
        if not name:
            errors["name"] = "Give the view a name."
        elif len(name) > 80:
            errors["name"] = "Use 80 characters or fewer."
        out["name"] = name
    if row is None:
        path = str(values.get("path") or "")
        if not PATH.match(path):
            errors["path"] = "Name the list the view is of, such as /risks."
        out["path"] = path
    if row is None or values.get("query") is not None:
        query = clean_query(values.get("query"))
        if len(query) > 1000:
            errors["query"] = "These filters are too long to keep."
        out["query"] = query
    if values.get("shared") is not None:
        shared = bool(values["shared"])
        if shared and not may_share(principal):
            errors["shared"] = (
                "Sharing a view with everyone is for stewards, assessors, and managers."
            )
        out["shared"] = shared
    if errors:
        raise Invalid("The view was not saved.", errors)
    return out


def create(session: Session, principal: Principal, values: dict[str, Any]) -> SavedView:
    if principal.account_id is None:
        raise PermissionDenied("A view belongs to a person.")
    checked = _checked(session, principal, values, None)
    mine = session.scalars(
        select(SavedView).where(
            SavedView.account_id == principal.account_id, SavedView.path == checked["path"]
        )
    ).all()
    if any(row.name.lower() == checked["name"].lower() for row in mine):
        raise Invalid("The view was not saved.", {"name": "You have a view of that name here."})
    if len(mine) >= MOST:
        raise Conflict(f"You have {MOST} views of this list. Delete one to save another.")
    row = SavedView(
        account_id=principal.account_id,
        owner_name=principal.name,
        created_at=utc_now(),
        **{"shared": False, **checked},
    )
    session.add(row)
    session.flush()
    return row


def get(
    session: Session, principal: Principal, view_id: int, *, to_change: bool = False
) -> SavedView:
    row = session.get(SavedView, view_id)
    if row is None or not (row.shared or row.account_id == principal.account_id):
        raise NotFound("There is no such view.")
    if to_change and not view(row, principal)["can_change"]:
        raise PermissionDenied("Only whoever saved a view can change it.")
    return row


def update(
    session: Session, principal: Principal, row: SavedView, values: dict[str, Any]
) -> SavedView:
    if row.account_id != principal.account_id and set(values) - {"shared"}:
        raise PermissionDenied("Only whoever saved a view can change it.")
    for key, value in _checked(session, principal, values, row).items():
        setattr(row, key, value)
    session.flush()
    return row


def delete(session: Session, principal: Principal, row: SavedView) -> None:
    session.delete(row)
    session.flush()
