"""Notices: what has been assigned to a person, or changed for them (OVS-06).

A notice is a pointer for one person: a sentence and where to go. It is not the record of
what happened, which is in the history, and nobody else reads it. Nobody is told about what
they did themselves.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.db.models import Account, Notice, RecordOwner, RoleGrant
from riskwren.people import units

KEPT = 200  # how many of a person's notices are shown


def tell(
    session: Session,
    account_id: int | None,
    kind: str,
    text: str,
    href: str,
    *,
    by: Principal | None = None,
) -> bool:
    """Tell one person. Returns whether a notice was written."""
    if account_id is None or (by is not None and by.account_id == account_id):
        return False
    account = session.get(Account, account_id)
    if account is None or account.status == "disabled":
        return False
    session.add(
        Notice(
            account_id=account_id, kind=kind, text=text[:400], href=href[:200], created_at=utc_now()
        )
    )
    return True


def tell_all(
    session: Session,
    account_ids: Iterable[int | None],
    kind: str,
    text: str,
    href: str,
    *,
    by: Principal | None = None,
) -> int:
    return sum(tell(session, each, kind, text, href, by=by) for each in dict.fromkeys(account_ids))


def owners(session: Session, record_type: str, record_id: int) -> list[int]:
    """Whoever answers for a record: its owners and their delegates."""
    return list(
        session.scalars(
            select(RecordOwner.account_id).where(
                RecordOwner.record_type == record_type, RecordOwner.record_id == record_id
            )
        )
    )


def holders(session: Session, roles: Iterable[str], org_unit_id: int) -> list[int]:
    """Everyone who holds one of these roles over a unit: for it, for a unit above it, or
    for the whole organization."""
    above = [unit.id for unit in units.ancestors(session, org_unit_id)]
    within = {org_unit_id, *above}
    found = session.execute(
        select(RoleGrant.account_id, RoleGrant.org_unit_id).where(RoleGrant.role.in_(list(roles)))
    ).all()
    return list(dict.fromkeys(account for account, unit in found if unit is None or unit in within))


def unread(session: Session, principal: Principal) -> int:
    if principal.account_id is None:
        return 0
    return int(
        session.execute(
            select(func.count())
            .select_from(Notice)
            .where(Notice.account_id == principal.account_id, Notice.read_at.is_(None))
        ).scalar_one()
    )


def mine(
    session: Session, principal: Principal, *, only_unread: bool = False
) -> list[dict[str, Any]]:
    if principal.account_id is None:
        return []
    statement = select(Notice).where(Notice.account_id == principal.account_id)
    if only_unread:
        statement = statement.where(Notice.read_at.is_(None))
    rows = session.scalars(statement.order_by(Notice.id.desc()).limit(KEPT))
    return [
        {
            "id": row.id,
            "kind": row.kind,
            "text": row.text,
            "href": row.href,
            "created_at": row.created_at,
            "read": row.read_at is not None,
        }
        for row in rows
    ]


def mark_read(session: Session, principal: Principal, ids: list[int] | None = None) -> int:
    """Mark some of a person's notices as read, or all of them."""
    if principal.account_id is None:
        return 0
    statement = (
        update(Notice)
        .where(Notice.account_id == principal.account_id, Notice.read_at.is_(None))
        .values(read_at=utc_now())
    )
    if ids is not None:
        statement = statement.where(Notice.id.in_(ids or [0]))
    return int(session.execute(statement).rowcount or 0)
