"""Tokens for other systems (INT-02).

A token acts as a role, never as a person: an auditor's reading of everything, a manager's
running of the program, or an assessor's or a steward's work within a unit. It may be limited
to reading. It is shown once, when it is made, and only its SHA-256 digest is kept; it ends on
its date or when an administrator withdraws it. What it changes is recorded under its name.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from riskwren.access import roles
from riskwren.access.principal import EVERYWHERE, Grant, Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid, NotFound, PermissionDenied
from riskwren.db.models import ApiToken, OrgUnit
from riskwren.events import audit
from riskwren.events.actor import Actor
from riskwren.people import units

PREFIX = "rwt_"
# The roles a token may act as. Never an administrator's: accounts and the look stay with people.
ROLES = (roles.AUDITOR, roles.MANAGER, roles.ASSESSOR, roles.STEWARD, roles.MEMBER)
LONGEST_DAYS = 366
ACTOR_KIND = "token"  # what a token does is recorded as done by it
QUIET = timedelta(minutes=5)  # how often its last use is written down


def digest(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _require_admin(principal: Principal) -> None:
    if not principal.is_admin:
        raise PermissionDenied("Only an administrator issues and withdraws tokens.")


def view(row: ApiToken) -> dict[str, Any]:
    now = utc_now()
    state = "withdrawn" if row.revoked_at else "expired" if row.expires_at <= now else "active"
    return {
        "id": row.id, "name": row.name, "prefix": row.prefix, "role": row.role,
        "org_unit_id": row.org_unit_id, "read_only": row.read_only, "expires_at": row.expires_at,
        "created_by": row.created_by_name, "created_at": row.created_at,
        "last_used_at": row.last_used_at, "revoked_at": row.revoked_at, "state": state,
    }  # fmt: skip


def list_(session: Session, principal: Principal) -> list[dict[str, Any]]:
    _require_admin(principal)
    rows = session.scalars(
        select(ApiToken).order_by(ApiToken.created_at.desc(), ApiToken.id.desc())
    )
    return [view(row) for row in rows]


def issue(session: Session, principal: Principal, values: dict[str, Any]) -> tuple[ApiToken, str]:
    """Make a token. Returns it with the secret, which is never available again."""
    _require_admin(principal)
    errors: dict[str, str] = {}
    name = str(values.get("name") or "").strip()
    if not name or len(name) > 80:
        errors["name"] = "Name it for the system that will use it, in up to 80 characters."
    role = values.get("role")
    if role not in ROLES:
        errors["role"] = f"Choose one of: {', '.join(ROLES)}."
    unit_id = values.get("org_unit_id")
    if role == roles.STEWARD and unit_id is None:
        errors["org_unit_id"] = "A steward's token is for one unit."
    if unit_id is not None:
        if role not in (roles.MANAGER, roles.ASSESSOR, roles.STEWARD):
            errors["org_unit_id"] = (
                "Only a manager's, an assessor's, or a steward's token takes a unit."
            )
        elif session.get(OrgUnit, unit_id) is None:
            errors["org_unit_id"] = "There is no such unit."
    days = values.get("days")
    if not isinstance(days, int) or not 1 <= days <= LONGEST_DAYS:
        errors["days"] = f"Give it from 1 to {LONGEST_DAYS} days."
    if errors:
        raise Invalid("The token was not made.", errors)
    raw = PREFIX + secrets.token_urlsafe(30)
    now = utc_now()
    row = ApiToken(
        name=name, prefix=raw[:10], digest=digest(raw), role=role, org_unit_id=unit_id,
        read_only=bool(values.get("read_only", True)), expires_at=now + timedelta(days=days),
        created_by=principal.account_id, created_by_name=principal.name, created_at=now,
    )  # fmt: skip
    with audit.operation(session, "token.issue"):
        session.add(row)
        session.flush()
    return row, raw


def revoke(session: Session, principal: Principal, token_id: int) -> ApiToken:
    _require_admin(principal)
    row = session.get(ApiToken, token_id)
    if row is None:
        raise NotFound("There is no such token.")
    if row.revoked_at is None:
        with audit.operation(session, "token.revoke"):
            row.revoked_at = utc_now()
            row.revoked_by_name = principal.name
            session.flush()
    return row


def principal_for(session: Session, row: ApiToken) -> Principal:
    """Who a token is, for the purposes of permission checks: its role, and nobody."""
    grant = Grant(row.role, row.org_unit_id)
    coverage: dict[str, frozenset[int] | None] = {}
    if row.role in roles.SCOPED:
        coverage[row.role] = (
            EVERYWHERE if row.org_unit_id is None
            else units.with_descendants(session, [row.org_unit_id])
        )  # fmt: skip
    return Principal(
        # Never a person's: a number no account has, so that nothing is ever "theirs" by
        # creator, owner, or author. It is never stored (riskwren.db.guard).
        account_id=-row.id,
        name=f"API token {row.name}",
        grants=(grant,) if row.role != roles.MEMBER else (),
        coverage=coverage,
        has_password=False,
        token_id=row.id,
        read_only=row.read_only,
    )


def actor(principal: Principal) -> Actor:
    return Actor(ACTOR_KIND, None, principal.name)


def authenticate(session: Session, engine: Engine, raw: str) -> Principal | None:
    """The principal a bearer token stands for, or None if it is not one in force."""
    if not raw.startswith(PREFIX) or len(raw) > 200:
        return None
    row = session.scalars(select(ApiToken).where(ApiToken.digest == digest(raw))).first()
    now = utc_now()
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        return None
    if row.last_used_at is None or now - row.last_used_at > QUIET:
        with engine.begin() as conn:  # bookkeeping, outside the history
            conn.execute(update(ApiToken).where(ApiToken.id == row.id).values(last_used_at=now))
    return principal_for(session, row)
