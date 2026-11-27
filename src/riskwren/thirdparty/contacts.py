"""Contacts at a third party: the people a questionnaire is sent to. They are not accounts,
and never sign in; a contact answers through a link made for one review."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid, NotFound, PermissionDenied
from riskwren.db.models import ThirdParty, ThirdPartyContact
from riskwren.events import audit
from riskwren.inventory import records
from riskwren.thirdparty import tiering

EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
STATUSES = ("active", "left")


def may_keep(session: Session, principal: Principal, third_party: ThirdParty) -> bool:
    return tiering.may_tier(session, principal, third_party)


def may_read(session: Session, principal: Principal, third_party: ThirdParty) -> bool:
    """Who sees a third party's contacts: those who keep it, assessors, and those who read
    everything. Everyone else sees that it has some."""
    return (
        principal.reads_all
        or principal.assesses_unit(third_party.org_unit_id)
        or may_keep(session, principal, third_party)
    )


def _check(values: Mapping[str, Any], contact: ThirdPartyContact, creating: bool) -> None:
    errors = records.Errors()
    if "name" in values or creating:
        name = records.text(values.get("name"))
        if not name or len(name) > 200:
            errors.add("name", "Give their name, in 200 characters or fewer.")
        else:
            contact.name = name
    if "email" in values or creating:
        email = (records.text(values.get("email")) or "").lower()
        if not EMAIL.fullmatch(email) or len(email) > 254:
            errors.add("email", "Give an email address.")
        else:
            contact.email = email
    for field, limit in (("role", 120), ("phone", 60)):
        if field in values:
            said = records.text(values.get(field))
            if said and len(said) > limit:
                errors.add(field, f"Keep this to {limit} characters.")
            else:
                setattr(contact, field, said)
    if "status" in values and values["status"] is not None:
        if values["status"] not in STATUSES:
            errors.add("status", "Active, or left.")
        else:
            contact.status = values["status"]
    if errors:
        raise Invalid("The contact was not saved.", errors)


def add(session: Session, principal: Principal, third_party: ThirdParty,
        values: Mapping[str, Any]) -> ThirdPartyContact:  # fmt: skip
    if not may_keep(session, principal, third_party):
        raise PermissionDenied("Contacts are kept by those who keep the third party, or assessors.")
    contact = ThirdPartyContact(
        third_party_id=third_party.id, status="active", created_at=utc_now()
    )
    _check(values, contact, True)
    with audit.operation(session, "third_party.contact", who=contact.name):
        session.add(contact)
        records.touch(session, third_party)
        session.flush()
    return contact


def change(session: Session, principal: Principal, contact: ThirdPartyContact,
           values: Mapping[str, Any]) -> ThirdPartyContact:  # fmt: skip
    party = session.get(ThirdParty, contact.third_party_id)
    assert party is not None
    if not may_keep(session, principal, party):
        raise PermissionDenied("Contacts are kept by those who keep the third party, or assessors.")
    with audit.operation(session, "third_party.contact", who=contact.name):
        _check(values, contact, False)
        records.touch(session, party)
        session.flush()
    return contact


def get(session: Session, contact_id: int) -> ThirdPartyContact:
    found = session.get(ThirdPartyContact, contact_id)
    if found is None:
        raise NotFound("There is no such contact.")
    return found


def of(session: Session, third_party: ThirdParty) -> list[ThirdPartyContact]:
    return list(
        session.scalars(
            select(ThirdPartyContact)
            .where(ThirdPartyContact.third_party_id == third_party.id)
            .order_by(ThirdPartyContact.status, ThirdPartyContact.name)
        )
    )
