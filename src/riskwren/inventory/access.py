"""Who may see and change a record (see spec/security.md).

One rule, used everywhere: single records, lists, counts, and links all ask here, so they
always agree.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from riskwren.access import roles
from riskwren.access.principal import Principal
from riskwren.db.models import RecordOwner
from riskwren.inventory.registry import RecordType
from riskwren.program import settings

VISIBILITY_SETTING = "records.visibility"
# How much of the register of risks and controls an ordinary member sees. The inventory of
# processes, systems, and third parties is open to everyone signed in, whatever this says.
VISIBILITIES = {
    "open": "Everyone sees every risk and control that is not restricted",
    "unit": "People see the risks and controls of their own units, and any they are named on",
    "assigned": "People see only the risks and controls they are named on",
}
DEFAULT_VISIBILITY = "unit"
EDITING_KINDS = ("owner", "delegate")
# Roles that see a unit's restricted records, and roles that see only its ordinary ones.
TRUSTED = (roles.STEWARD, roles.LEADER, roles.MANAGER)
SCOPED = (*TRUSTED, roles.ASSESSOR)


def visibility(session: Session) -> str:
    value = settings.get(session, VISIBILITY_SETTING, DEFAULT_VISIBILITY)
    return value if value in VISIBILITIES else DEFAULT_VISIBILITY


def owner_kinds(
    session: Session, record_type: RecordType, record_id: int, account_id: int | None
) -> set[str]:
    if account_id is None:
        return set()
    return set(
        session.scalars(
            select(RecordOwner.kind).where(
                RecordOwner.record_type == record_type.key,
                RecordOwner.record_id == record_id,
                RecordOwner.account_id == account_id,
            )
        )
    )


def _in(units: frozenset[int] | None, org_unit_id: int | None) -> bool:
    return units is None or (org_unit_id is not None and org_unit_id in units)


def can_see(
    session: Session,
    principal: Principal,
    record_type: RecordType,
    record: Any,
    *,
    owned: bool | None = None,
    setting: str | None = None,
) -> bool:
    """Whether the person may know this record exists."""
    own_rule = record_type.extra.get("can_see")
    if own_rule is not None:
        return bool(own_rule(session, principal, record))
    if principal.reads_all:
        return True
    unit = record.org_unit_id
    if _in(principal.units_for(*TRUSTED), unit):
        return True
    if record.created_by is not None and record.created_by == principal.account_id:
        return True
    if owned is None:
        owned = bool(owner_kinds(session, record_type, record.id, principal.account_id))
    if owned:
        return True
    if record.restricted:
        return False
    if record_type.open or _in(principal.units_for(roles.ASSESSOR), unit):
        return True
    setting = setting or visibility(session)
    if setting == "open":
        return True
    return setting == "unit" and unit in principal.member_units


def visible(
    session: Session, principal: Principal, record_type: RecordType
) -> ColumnElement[bool] | None:
    """A condition that keeps only the records the person may see, or None for all of them."""
    own_rule = record_type.extra.get("visible")
    if own_rule is not None:
        return own_rule(session, principal)  # type: ignore[no-any-return]
    if principal.reads_all:
        return None
    trusted = principal.units_for(*TRUSTED)
    if trusted is None:
        return None
    model: Any = record_type.model
    me = principal.account_id
    owned = exists(
        select(RecordOwner.id).where(
            RecordOwner.record_type == record_type.key,
            RecordOwner.record_id == model.id,
            RecordOwner.account_id == me,
        )
    )
    conditions: list[ColumnElement[bool]] = [owned, model.created_by == me]
    if trusted:
        conditions.append(model.org_unit_id.in_(trusted))
    ordinary = model.restricted.is_(False)
    assessed = principal.units_for(roles.ASSESSOR)
    setting = visibility(session)
    if record_type.open or assessed is None or setting == "open":
        conditions.append(ordinary)
    else:
        seen = set(assessed)
        if setting == "unit":
            seen |= principal.member_units
        if seen:
            conditions.append(and_(ordinary, model.org_unit_id.in_(seen)))
    return or_(*conditions)


def can_add(principal: Principal, org_unit_id: int | None) -> bool:
    """Records are added by a unit's steward or by a manager."""
    return principal.manages_unit(org_unit_id) or principal.stewards_unit(org_unit_id)


def can_edit(session: Session, principal: Principal, record_type: RecordType, record: Any) -> bool:
    if principal.manages_unit(record.org_unit_id) or principal.stewards_unit(record.org_unit_id):
        return True
    kinds = owner_kinds(session, record_type, record.id, principal.account_id)
    return bool(kinds & set(EDITING_KINDS))


def can_assess(
    session: Session, principal: Principal, record_type: RecordType, record: Any
) -> bool:
    """Whether the person may record a judgment about this record: its editors, and the
    assessors whose scope covers it."""
    return principal.assesses_unit(record.org_unit_id) or can_edit(
        session, principal, record_type, record
    )
