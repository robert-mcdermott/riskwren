"""Accounts, passwords, roles, and working out who a signed-in person is."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from riskwren.access import roles
from riskwren.access.principal import Grant, Principal
from riskwren.auth import passwords
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import Account, Credential, Membership, OrgUnit, RoleGrant, SessionToken
from riskwren.events import audit
from riskwren.people import units

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ACCEPT_LIMIT = re.compile(r"[a-z][a-z0-9_-]{0,39}")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _require_admin(principal: Principal) -> None:
    if not principal.is_admin:
        raise PermissionDenied("Only an administrator can manage accounts.")


def get(session: Session, account_id: int) -> Account:
    account = session.get(Account, account_id)
    if account is None:
        raise NotFound("There is no such account.")
    return account


def by_email(session: Session, email: str) -> Account | None:
    return session.scalars(select(Account).where(Account.email == normalize_email(email))).first()


def grants_of(session: Session, account_id: int) -> list[RoleGrant]:
    return list(
        session.scalars(
            select(RoleGrant).where(RoleGrant.account_id == account_id).order_by(RoleGrant.id)
        )
    )


def memberships_of(session: Session, account_id: int) -> list[Membership]:
    return list(
        session.scalars(
            select(Membership).where(Membership.account_id == account_id).order_by(Membership.id)
        )
    )


def active_admins(session: Session, *, excluding: int | None = None) -> int:
    statement = (
        select(func.count(func.distinct(Account.id)))
        .join(RoleGrant, RoleGrant.account_id == Account.id)
        .where(RoleGrant.role == roles.ADMIN, Account.status == "active")
    )
    if excluding is not None:
        statement = statement.where(Account.id != excluding)
    return session.execute(statement).scalar_one()


def has_password(session: Session, account_id: int) -> bool:
    return session.get(Credential, account_id) is not None


def principal_for(
    session: Session, account: Account, token: SessionToken | None = None
) -> Principal:
    """Who this account is for the purposes of permission checks."""
    grants = tuple(
        Grant(g.role, g.org_unit_id, g.accept_limit) for g in grants_of(session, account.id)
    )
    coverage: dict[str, frozenset[int] | None] = {}
    for role in roles.SCOPED:
        held = [g for g in grants if g.role == role]
        if not held:
            continue
        if any(g.org_unit_id is None for g in held):
            coverage[role] = None  # the whole organization
        else:
            coverage[role] = units.with_descendants(session, (g.org_unit_id for g in held))
    member_units = units.with_descendants(
        session, (m.org_unit_id for m in memberships_of(session, account.id))
    )
    return Principal(
        account_id=account.id,
        name=account.display_name,
        email=account.email,
        grants=grants,
        coverage=coverage,
        member_units=member_units,
        csrf_token=token.csrf_token if token else "",
        has_password=has_password(session, account.id),
        session_id=token.id if token else None,
    )


def create(
    session: Session,
    principal: Principal,
    *,
    email: str,
    display_name: str,
    title: str | None = None,
    password: str | None = None,
    grants: Sequence[Grant] = (),
) -> Account:
    """Add an account. With a password it can sign in at once; without one it is *invited*:
    it can be named on records, and becomes active when it is given a password or first
    signs in through the identity provider."""
    _require_admin(principal)
    email = normalize_email(email)
    display_name = display_name.strip()
    errors = {}
    if not EMAIL.match(email) or len(email) > 254:
        errors["email"] = "Enter an email address."
    if not display_name:
        errors["display_name"] = "Enter the person's name."
    if errors:
        raise Invalid("The account is not valid.", errors)
    if by_email(session, email):
        raise Conflict(f"There is already an account for {email}.")
    if password is not None:
        passwords.check_rules(password, email=email)
    account = Account(
        email=email,
        display_name=display_name,
        title=(title or "").strip() or None,
        status="active" if password is not None else "invited",
        created_at=utc_now(),
    )
    session.add(account)
    session.flush()
    if password is not None:
        session.add(
            Credential(
                account_id=account.id,
                password_hash=passwords.hash_password(password),
                changed_at=utc_now(),
            )
        )
    if grants:
        set_grants(session, principal, account, grants)
    session.flush()
    return account


def update(
    session: Session, principal: Principal, account: Account, changes: dict[str, Any]
) -> Account:
    """Change an account's details. People may change their own name, title, and time zone."""
    own = principal.account_id == account.id
    if not own:
        _require_admin(principal)
    if "display_name" in changes:
        name = str(changes["display_name"]).strip()
        if not name:
            raise Invalid("The account is not valid.", {"display_name": "Enter the person's name."})
        account.display_name = name
    if "title" in changes:
        account.title = (changes["title"] or "").strip() or None
    if "time_zone" in changes:
        account.time_zone = (changes["time_zone"] or "").strip() or None
    if "status" in changes and changes["status"] != account.status:
        _require_admin(principal)
        set_status(session, principal, account, changes["status"])
    session.flush()
    return account


def set_status(session: Session, principal: Principal, account: Account, status: str) -> None:
    _require_admin(principal)
    if status not in ("active", "disabled"):
        raise Invalid("The account is not valid.", {"status": "Use active or disabled."})
    if status == "disabled":
        if principal.account_id == account.id:
            raise Conflict("You cannot disable your own account.")
        if active_admins(session, excluding=account.id) == 0 and _is_admin(session, account.id):
            raise Conflict("This is the last active administrator and cannot be disabled.")
        session.flush()
        _end_sessions(session, account.id)
    account.status = status


def _is_admin(session: Session, account_id: int) -> bool:
    return any(g.role == roles.ADMIN for g in grants_of(session, account_id))


def _end_sessions(session: Session, account_id: int, *, keep: int | None = None) -> None:
    from riskwren.auth import sessions

    sessions.revoke_all(session, account_id, keep=keep)


def set_password(
    session: Session,
    principal: Principal,
    account: Account,
    new_password: str,
    *,
    current_password: str | None = None,
) -> None:
    """Set a password. A person changing their own must give the current one; an
    administrator resetting someone else's need not. Other sessions of the account end."""
    own = principal.account_id == account.id
    credential = session.get(Credential, account.id)
    if own and not principal.command:
        if credential is not None and not passwords.verify_password(
            current_password or "", credential.password_hash
        ):
            raise Invalid(
                "The password was not changed.",
                {"current_password": "That is not your current password."},
            )
    else:
        _require_admin(principal)
    passwords.check_rules(new_password, email=account.email)
    hashed = passwords.hash_password(new_password)
    if credential is None:
        session.add(Credential(account_id=account.id, password_hash=hashed, changed_at=utc_now()))
    else:
        credential.password_hash = hashed
        credential.changed_at = utc_now()
    if account.status == "invited":
        account.status = "active"
    session.flush()
    _end_sessions(session, account.id, keep=principal.session_id if own else None)


def check_grant(session: Session, grant: Grant) -> None:
    errors = {}
    if grant.role not in roles.GRANTABLE:
        known = ", ".join(roles.GRANTABLE)
        errors["role"] = f"{grant.role!r} is not a role that can be granted. Use one of: {known}."
    elif grant.role in roles.SCOPED:
        if grant.org_unit_id is None:
            if grant.role in roles.UNIT_REQUIRED:
                errors["org_unit_id"] = (
                    f"A {grant.role} is a {grant.role} of a unit. Name the unit."
                )
        elif session.get(OrgUnit, grant.org_unit_id) is None:
            errors["org_unit_id"] = "There is no such unit."
    elif grant.org_unit_id is not None:
        errors["org_unit_id"] = f"The {grant.role} role is not scoped to a unit."
    if grant.accept_limit is not None:
        if grant.role != roles.LEADER:
            errors["accept_limit"] = "Only a leader has a limit on what they may accept."
        elif not ACCEPT_LIMIT.fullmatch(grant.accept_limit):
            errors["accept_limit"] = "Give the key of a rating, such as high."
    if errors:
        raise Invalid("The role is not valid.", errors)


def set_grants(
    session: Session,
    principal: Principal,
    account: Account,
    wanted: Iterable[Grant],
    *,
    source: str = "local",
) -> list[RoleGrant]:
    """Make the account's roles from ``source`` exactly these. Roles from the other source
    (granted here, or mapped from the identity provider) are left alone."""
    _require_admin(principal)
    wanted = list(dict.fromkeys(wanted))
    for grant in wanted:
        check_grant(session, grant)
    existing = [g for g in grants_of(session, account.id) if g.source == source]
    others = [g for g in grants_of(session, account.id) if g.source != source]
    keeps_admin = any(g.role == roles.ADMIN for g in wanted) or any(
        g.role == roles.ADMIN for g in others
    )
    was_admin = any(g.role == roles.ADMIN for g in existing) or any(
        g.role == roles.ADMIN for g in others
    )
    if (
        was_admin
        and not keeps_admin
        and account.status == "active"
        and active_admins(session, excluding=account.id) == 0
    ):
        raise Conflict("This is the last active administrator; that role cannot be removed.")
    have = {(g.role, g.org_unit_id, g.accept_limit): g for g in existing}
    want = {(g.role, g.org_unit_id, g.accept_limit) for g in wanted}
    for key, row in have.items():
        if key not in want:
            session.delete(row)
    for grant in wanted:
        if (grant.role, grant.org_unit_id, grant.accept_limit) not in have:
            session.add(
                RoleGrant(
                    account_id=account.id,
                    role=grant.role,
                    org_unit_id=grant.org_unit_id,
                    accept_limit=grant.accept_limit,
                    source=source,
                    granted_by=principal.account_id,
                    granted_at=utc_now(),
                )
            )
    session.flush()
    return grants_of(session, account.id)


def set_memberships(
    session: Session, principal: Principal, account: Account, unit_ids: Sequence[int]
) -> None:
    """Say which units a person works in. The first is their primary unit."""
    _require_admin(principal)
    unit_ids = list(dict.fromkeys(unit_ids))
    for unit_id in unit_ids:
        units.get(session, unit_id)
    have = {m.org_unit_id: m for m in memberships_of(session, account.id)}
    for unit_id, row in have.items():
        if unit_id not in unit_ids:
            session.delete(row)
    for position, unit_id in enumerate(unit_ids):
        row = have.get(unit_id)
        if row is None:
            session.add(
                Membership(account_id=account.id, org_unit_id=unit_id, is_primary=position == 0)
            )
        elif row.is_primary != (position == 0):
            row.is_primary = position == 0
    session.flush()


def authenticate(session: Session, email: str, password: str) -> Account | None:
    """The active account these credentials belong to, or None. Unknown accounts take as
    long to refuse as wrong passwords."""
    account = by_email(session, email)
    credential = session.get(Credential, account.id) if account else None
    if account is None or credential is None or account.status != "active":
        passwords.burn_time(password)
        return None
    if not passwords.verify_password(password, credential.password_hash):
        return None
    return account


def note_sign_in(session: Session, account: Account, *, method: str) -> None:
    audit.record(session, "signed_in", account, context={"method": method})


def view(session: Session, account: Account) -> dict[str, Any]:
    return {
        "id": account.id,
        "email": account.email,
        "display_name": account.display_name,
        "title": account.title,
        "status": account.status,
        "time_zone": account.time_zone,
        "has_password": has_password(session, account.id),
        "roles": [
            {
                "role": g.role,
                "org_unit_id": g.org_unit_id,
                "accept_limit": g.accept_limit,
                "source": g.source,
            }
            for g in grants_of(session, account.id)
        ],
        "units": [
            {"org_unit_id": m.org_unit_id, "is_primary": m.is_primary, "title": m.title}
            for m in memberships_of(session, account.id)
        ],
    }


def search(session: Session, *, query: str = "", status: str | None = None) -> list[Account]:
    statement = select(Account).order_by(Account.display_name, Account.id)
    if query.strip():
        like = f"%{query.strip().lower()}%"
        statement = statement.where(
            func.lower(Account.display_name).like(like) | Account.email.like(like)
        )
    if status:
        statement = statement.where(Account.status == status)
    return list(session.scalars(statement))
