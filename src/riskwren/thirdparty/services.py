"""Services: what a third party provides, and what each reaches and handles (TPR-01).

A service is a record of the inventory beside its third party: the hosted application, the
maintenance contract, the tests sent out. The systems it reaches and the information it
handles are links, so they show on both sides and in the picture of connections, and
processes rely on services the way they rely on systems.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.errors import NotFound
from riskwren.db.models import Service, ThirdParty
from riskwren.inventory import access, records
from riskwren.inventory.registry import (
    THING_FILTERS,
    THING_SORTS,
    THIRD_PARTY,
    Field,
    RecordType,
    register,
)

KEY = "service"


def _provider(session: Session, ref: Any, errors: records.Errors) -> ThirdParty | None:
    given = records.text(ref)
    if not given:
        errors.add("third_party", "Say which third party provides it.")
        return None
    found = session.scalars(select(ThirdParty).where(ThirdParty.ref == given.upper())).first()
    if found is None:
        errors.add("third_party", f"There is no third party {given}.")
        return None
    return found


def _apply(
    session: Session, service: Service, values: Mapping[str, Any], errors: records.Errors,
    creating: bool,
) -> None:  # fmt: skip
    if "third_party" in values or creating:
        provider = _provider(session, values.get("third_party"), errors)
        if provider is not None:
            if provider.status != "active" and provider.id != service.third_party_id:
                errors.add("third_party", f"{provider.name} is retired.")
            else:
                service.third_party_id = provider.id


def _providers(session: Session, rows: list[Service]) -> dict[int, ThirdParty]:
    ids = {row.third_party_id for row in rows} or {0}
    return {tp.id: tp for tp in session.scalars(select(ThirdParty).where(ThirdParty.id.in_(ids)))}


def _cards(session: Session, rows: list[Service]) -> list[dict[str, Any]]:
    providers = _providers(session, rows)
    return [
        {"third_party": records.chip(THIRD_PARTY, providers[row.third_party_id])}
        if row.third_party_id in providers
        else {"third_party": None}
        for row in rows
    ]


def _detail(session: Session, principal: Principal, service: Service) -> dict[str, Any]:
    provider = session.get(ThirdParty, service.third_party_id)
    shown = provider is not None and access.can_see(session, principal, THIRD_PARTY, provider)
    return {"third_party": records.chip(THIRD_PARTY, provider) if shown else None}


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    given = records.text(filters.get("third_party"))
    if given:
        provider = session.scalars(select(ThirdParty.id).where(ThirdParty.ref == given.upper()))
        found.append(Service.third_party_id.in_(provider))
    return found


def _history_value(lookups: Any, field: str, value: Any) -> Any:
    if field == "third_party_id":
        return lookups.name("third_party", value)
    return None


SERVICE = register(
    RecordType(
        KEY,
        Service,
        "SVC",
        "services",
        "service",
        "services",
        fields=(Field("kind", "Kind", "choice", vocab="service_kinds", required=True),),
        open=True,
        sorts=THING_SORTS,
        filters=THING_FILTERS,
        extra={
            "apply": _apply,
            "cards": _cards,
            "detail": _detail,
            "conditions": _conditions,
            "history_labels": {"third_party_id": "Provided by"},
            "history_value": _history_value,
        },
    )
)


def of(session: Session, principal: Principal, third_party: ThirdParty) -> list[dict[str, Any]]:
    """What a third party provides, in use first, as much as the person may see."""
    rows = session.scalars(
        select(Service)
        .where(Service.third_party_id == third_party.id)
        .order_by(Service.status, Service.name)
    ).all()
    return [
        {**records.chip(SERVICE, row), "kind": row.kind, "data_class": row.data_class}
        for row in rows
        if access.can_see(session, principal, SERVICE, row)
    ]


def provider_of(session: Session, principal: Principal, ref: str) -> ThirdParty:
    """The third party a new service is for, if the person may see it."""
    found = session.scalars(
        select(ThirdParty).where(ThirdParty.ref == (records.text(ref) or "").upper())
    ).first()
    if found is None or not access.can_see(session, principal, THIRD_PARTY, found):
        raise NotFound(f"There is no third party {ref}.")
    return found
