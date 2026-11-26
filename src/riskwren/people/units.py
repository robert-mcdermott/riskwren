"""The organization's hierarchy of units."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import OrgUnit

DEFAULT_KINDS = ("organization", "division", "department", "center", "core", "lab", "office")


def _require_admin(principal: Principal) -> None:
    if not principal.is_admin:
        raise PermissionDenied("Only an administrator can change the organization's units.")


def all_units(session: Session) -> list[OrgUnit]:
    return list(session.scalars(select(OrgUnit).order_by(OrgUnit.name)))


def get(session: Session, unit_id: int) -> OrgUnit:
    unit = session.get(OrgUnit, unit_id)
    if unit is None:
        raise NotFound("There is no such unit.")
    return unit


def by_code(session: Session, code: str) -> OrgUnit | None:
    return session.scalars(select(OrgUnit).where(OrgUnit.code == code.strip())).first()


def children_map(units: Iterable[OrgUnit]) -> dict[int | None, list[OrgUnit]]:
    children: dict[int | None, list[OrgUnit]] = defaultdict(list)
    for unit in units:
        children[unit.parent_id].append(unit)
    return children


def with_descendants(session: Session, unit_ids: Iterable[int]) -> frozenset[int]:
    """The given units and every unit beneath them. The tree is small, so it is walked whole."""
    wanted = set(unit_ids)
    if not wanted:
        return frozenset()
    children = children_map(all_units(session))
    found: set[int] = set()
    stack = list(wanted)
    while stack:
        current = stack.pop()
        if current in found:
            continue
        found.add(current)
        stack.extend(child.id for child in children.get(current, ()))
    return frozenset(found)


def ancestors(session: Session, unit_id: int) -> list[OrgUnit]:
    """The units above this one, nearest first."""
    by_id = {unit.id: unit for unit in all_units(session)}
    chain: list[OrgUnit] = []
    current = by_id.get(unit_id)
    while current is not None and current.parent_id is not None and len(chain) < 64:
        current = by_id.get(current.parent_id)
        if current is not None:
            chain.append(current)
    return chain


def _clean(name: str, kind: str, code: str | None) -> tuple[str, str, str | None]:
    name, kind = name.strip(), kind.strip().lower()
    code = (code or "").strip() or None
    errors = {}
    if not name:
        errors["name"] = "A unit needs a name."
    if not kind:
        errors["kind"] = "A unit needs a kind."
    if errors:
        raise Invalid("The unit is not valid.", errors)
    return name, kind, code


def create(
    session: Session,
    principal: Principal,
    *,
    name: str,
    kind: str,
    code: str | None = None,
    parent_id: int | None = None,
) -> OrgUnit:
    _require_admin(principal)
    name, kind, code = _clean(name, kind, code)
    if code and by_code(session, code):
        raise Conflict(f"Another unit already has the code {code}.")
    if parent_id is None:
        if session.scalars(select(OrgUnit.id).where(OrgUnit.parent_id.is_(None))).first():
            raise Conflict("The organization already has a top unit. Choose a parent.")
    else:
        get(session, parent_id)
    unit = OrgUnit(
        name=name, kind=kind, code=code, parent_id=parent_id, status="active", created_at=utc_now()
    )
    session.add(unit)
    session.flush()
    return unit


def update(
    session: Session, principal: Principal, unit: OrgUnit, changes: dict[str, Any]
) -> OrgUnit:
    _require_admin(principal)
    name, kind, code = _clean(
        changes.get("name", unit.name),
        changes.get("kind", unit.kind),
        changes.get("code", unit.code),
    )
    if code and code != unit.code and by_code(session, code):
        raise Conflict(f"Another unit already has the code {code}.")
    if "parent_id" in changes and changes["parent_id"] != unit.parent_id:
        parent_id = changes["parent_id"]
        if parent_id is None:
            raise Conflict("Only the top unit has no parent.")
        get(session, parent_id)
        if parent_id in with_descendants(session, [unit.id]):
            raise Conflict("A unit cannot be moved beneath itself.")
        unit.parent_id = parent_id
    if "status" in changes:
        if changes["status"] not in ("active", "closed"):
            raise Invalid("The unit is not valid.", {"status": "Use active or closed."})
        unit.status = changes["status"]
    unit.name, unit.kind, unit.code = name, kind, code
    session.flush()
    return unit


def view(unit: OrgUnit) -> dict[str, Any]:
    return {
        "id": unit.id,
        "parent_id": unit.parent_id,
        "kind": unit.kind,
        "name": unit.name,
        "code": unit.code,
        "status": unit.status,
    }


def tree(session: Session) -> list[dict[str, Any]]:
    """The hierarchy as nested dictionaries, each level sorted by name."""
    children = children_map(all_units(session))

    def node(unit: OrgUnit) -> dict[str, Any]:
        return {**view(unit), "children": [node(child) for child in children.get(unit.id, ())]}

    return [node(root) for root in children.get(None, ())]
