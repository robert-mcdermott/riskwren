"""Single sign-on on RiskWren's side: who the person from the identity provider is here, and
which roles their application roles or groups there give them.

It is optional. With no issuer configured nothing here is reached, and people sign in with
the accounts and passwords RiskWren holds."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping, Sequence
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from riskwren.access import roles
from riskwren.access.principal import Grant, Principal
from riskwren.auth.oidc import Challenge, SignInFailed
from riskwren.config import SsoConfig
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, PermissionDenied
from riskwren.db.models import (
    Account,
    Identity,
    Membership,
    OrgUnit,
    ProviderMapping,
    SignInRequest,
)
from riskwren.events import audit
from riskwren.people import accounts

log = logging.getLogger("riskwren.sso")
PROVIDER = Principal.for_command("Single sign-on")
KEEP = timedelta(minutes=10)
MAPPABLE = (*roles.GRANTABLE, roles.MEMBER)


def _hash(state: str) -> str:
    return hashlib.sha256(state.encode()).hexdigest()


# --- Round trips in flight ----------------------------------------------------------------


def remember(session: Session, challenge: Challenge, next_path: str) -> None:
    """Keep what is needed to finish a sign-in that has just been sent to the provider."""
    session.execute(delete(SignInRequest).where(SignInRequest.created_at < utc_now() - KEEP))
    session.add(
        SignInRequest(
            state_hash=_hash(challenge.state),
            nonce=challenge.nonce,
            verifier=challenge.verifier,
            next_path=next_path[:500],
            created_at=utc_now(),
        )
    )


def recall(session: Session, state: str) -> SignInRequest | None:
    """The round trip this answer belongs to, which is then forgotten: a state works once."""
    row = session.scalars(
        select(SignInRequest).where(SignInRequest.state_hash == _hash(state))
    ).first()
    if row is None:
        return None
    session.delete(row)
    session.flush()
    return row if row.created_at >= utc_now() - KEEP else None


# --- Mappings -----------------------------------------------------------------------------


def mappings(session: Session) -> list[ProviderMapping]:
    return list(
        session.scalars(
            select(ProviderMapping).order_by(ProviderMapping.claim_value, ProviderMapping.id)
        )
    )


def mapping_view(session: Session, row: ProviderMapping) -> dict[str, Any]:
    unit = session.get(OrgUnit, row.org_unit_id) if row.org_unit_id else None
    return {
        "id": row.id,
        "claim_value": row.claim_value,
        "role": row.role,
        "org_unit_id": row.org_unit_id,
        "unit_name": unit.name if unit else None,
        "accept_limit": row.accept_limit,
    }


def set_mappings(
    session: Session, principal: Principal, wanted: Sequence[Mapping[str, Any]]
) -> list[ProviderMapping]:
    """Replace the whole list of mappings. Each says: people with this application role or
    group at the provider get this role here."""
    if not principal.is_admin:
        raise PermissionDenied("Only an administrator can change single sign-on.")
    cleaned: list[tuple[str, str, int | None, str | None]] = []
    errors: dict[str, str] = {}
    for index, item in enumerate(wanted):
        where = f"mappings[{index}]"
        value = str(item.get("claim_value") or "").strip()
        role = str(item.get("role") or "")
        unit = int(item["org_unit_id"]) if item.get("org_unit_id") else None
        limit = str(item["accept_limit"]) if item.get("accept_limit") else None
        if not value or len(value) > 300:
            errors[where] = "Give the application role or group as the provider sends it."
        elif role not in MAPPABLE:
            errors[where] = f"Choose one of: {', '.join(MAPPABLE)}."
        elif role == roles.MEMBER:
            if unit is None or session.get(OrgUnit, unit) is None:
                errors[where] = "Choose the unit these people work in."
            else:
                cleaned.append((value, role, unit, None))
        else:
            try:
                accounts.check_grant(session, Grant(role, unit, limit))
            except Invalid as exc:
                errors[where] = " ".join(exc.errors.values()) or str(exc)
            else:
                cleaned.append((value, role, unit, limit))
    if errors:
        raise Invalid("The mappings were not saved.", errors)
    cleaned = list(dict.fromkeys(cleaned))
    have = {(m.claim_value, m.role, m.org_unit_id, m.accept_limit): m for m in mappings(session)}
    with audit.operation(session, "sso.mappings"):
        for key, row in have.items():
            if key not in cleaned:
                session.delete(row)
        for key in cleaned:
            if key not in have:
                session.add(
                    ProviderMapping(
                        claim_value=key[0],
                        role=key[1],
                        org_unit_id=key[2],
                        accept_limit=key[3],
                        created_at=utc_now(),
                    )
                )
        session.flush()
    return mappings(session)


def values_in(claims: Mapping[str, Any], claim: str) -> list[str] | None:
    """The person's application roles or groups, or None when the token does not say. That
    is not the same as having none: a provider leaves groups out when there are too many to
    list, and then nobody's roles should be taken away."""
    value = claims.get(claim)
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return None


def _apply(session: Session, account: Account, held: list[str]) -> None:
    """Make the account's roles from the provider exactly what the provider says. Roles
    granted in RiskWren are not touched."""
    rows = [m for m in mappings(session) if m.claim_value in set(held)]
    wanted = [Grant(m.role, m.org_unit_id, m.accept_limit) for m in rows if m.role != roles.MEMBER]
    try:
        accounts.set_grants(session, PROVIDER, account, wanted, source="provider")
    except Conflict:
        # The provider would leave nobody able to administer RiskWren. Keep the role and say so.
        log.warning("%s keeps the administrator role: they are the last one", account.email)
        keep = [Grant(roles.ADMIN), *[g for g in wanted if g.role != roles.ADMIN]]
        accounts.set_grants(session, PROVIDER, account, keep, source="provider")
    have = {m.org_unit_id for m in accounts.memberships_of(session, account.id)}
    for unit_id in dict.fromkeys(m.org_unit_id for m in rows if m.role == roles.MEMBER):
        if unit_id is not None and unit_id not in have:
            session.add(Membership(account_id=account.id, org_unit_id=unit_id, is_primary=not have))
            have.add(unit_id)
    session.flush()


# --- Signing in ---------------------------------------------------------------------------


def sign_in(session: Session, config: SsoConfig, claims: Mapping[str, Any]) -> Account:
    """The account for a person the provider has just vouched for: found by the provider's
    own name for them, joined to an existing account by a verified address, or created."""
    issuer, subject = config.issuer.rstrip("/"), str(claims["sub"])
    identity = session.scalars(
        select(Identity).where(Identity.issuer == issuer, Identity.subject == subject)
    ).first()
    address = claims.get("email") or (
        claims.get("preferred_username") if config.trust_email else None
    )
    email = accounts.normalize_email(str(address)) if address else None
    vouched = bool(email) and (config.trust_email or claims.get("email_verified") is True)

    if identity is not None:
        account = accounts.get(session, identity.account_id)
    else:
        if not vouched or email is None:
            raise SignInFailed(
                "the provider did not send an email address it vouches for, so the person "
                "cannot be matched or created (see trust_email in the configuration)"
            )
        existing = accounts.by_email(session, email)
        with audit.operation(session, "sso.first_sign_in"):
            if existing is not None:
                account = existing
            elif not config.create_accounts:
                raise SignInFailed(
                    f"there is no account for {email}, and accounts are not made at first "
                    "sign-in (see create_accounts in the configuration)"
                )
            else:
                name = str(claims.get("name") or "").strip() or email.split("@")[0]
                account = accounts.create(session, PROVIDER, email=email, display_name=name)
            session.add(
                Identity(
                    account_id=account.id,
                    issuer=issuer,
                    subject=subject,
                    email=email,
                    created_at=utc_now(),
                )
            )
            session.flush()
    if account.status == "disabled":
        raise SignInFailed(f"the account for {account.email} is disabled")
    if account.status == "invited":
        accounts.set_status(session, PROVIDER, account, "active")
    held = values_in(claims, config.roles_claim)
    if held is None and not _overflowed(claims, config.roles_claim):
        held = []  # the provider lists what a person has, and listed nothing for this one
    if held is None:
        log.warning(
            "%r was left out of the token for %s: roles left as they were",
            config.roles_claim, account.email,
        )  # fmt: skip
    else:
        _apply(session, account, held)
    return account


def _overflowed(claims: Mapping[str, Any], claim: str) -> bool:
    """Whether the provider says the claim was too long to send (Entra ID does this for
    groups, pointing elsewhere for the list)."""
    names = claims.get("_claim_names")
    return (isinstance(names, Mapping) and claim in names) or claims.get("hasgroups") is True
