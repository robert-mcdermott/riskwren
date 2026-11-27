"""Third parties as a program: their services, and their tiers."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import envelope, reading, writing
from riskwren.api.routers.inventory import (
    LIMIT,
    MINE,
    SORT,
    UNIT,
    LinkBody,
    OwnersBody,
    Q,
    ThingBody,
    add_record_link,
    list_records,
    record_history,
    remove_record_link,
    set_record_owners,
    show_record,
    thing_filters,
    update_record,
    values_of,
)
from riskwren.core.errors import PermissionDenied
from riskwren.inventory import access, records
from riskwren.inventory.registry import THIRD_PARTY
from riskwren.thirdparty import services, tiering
from riskwren.thirdparty.services import SERVICE

router = APIRouter(prefix="/api/v1", tags=["third parties"])


class ServiceBody(ThingBody):
    third_party: str | None = Field(
        default=None, description="The reference of the third party that provides it"
    )


class TieringBody(BaseModel):
    answers: dict[str, Any] = Field(description="The answers, by question key")
    tier: str | None = Field(
        default=None, description="The tier to record; the one the rules give if left out"
    )
    rationale: str | None = Field(
        default=None, max_length=4000, description="Why, where the tier differs from the rules'"
    )


# --- Services -----------------------------------------------------------------------------


@router.get("/services", summary="Find services")
def list_services(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    status: str | None = None,
    kind: str | None = None,
    criticality: str | None = None,
    data_class: str | None = None,
    third_party: str | None = None,
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = SORT,
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = thing_filters(
        q, unit, status, kind, criticality, data_class, owner, mine, third_party=third_party
    )
    return list_records(request, SERVICE, filters, sort, limit, cursor)


@router.post("/services", status_code=201, summary="Add a service a third party provides")
def create_service(request: Request, body: ServiceBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        # Whoever keeps the third party may say what it provides, in its unit or their own.
        provider = services.provider_of(session, principal, body.third_party or "")
        keeps = access.can_edit(session, principal, THIRD_PARTY, provider)
        values = values_of(body)
        if keeps and values.get("org_unit_id") is None:
            values["org_unit_id"] = provider.org_unit_id
        checked = keeps and values.get("org_unit_id") == provider.org_unit_id
        if not (checked or access.can_add(principal, values.get("org_unit_id"))):
            raise PermissionDenied(
                "A service is added by those who keep its third party, or a unit's steward."
            )
        record = records.create(session, principal, SERVICE, values, checked=True)
        return envelope(records.detail(session, principal, SERVICE, record))


@router.get("/services/{ref}", summary="One service, with what it reaches and handles")
def show_service(request: Request, ref: str) -> dict[str, Any]:
    return show_record(request, SERVICE, ref)


@router.patch("/services/{ref}", summary="Change a service")
def update_service(request: Request, ref: str, body: ServiceBody) -> dict[str, Any]:
    return update_record(request, SERVICE, ref, body)


@router.put("/services/{ref}/owners", summary="Set a service's owners")
def set_service_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, SERVICE, ref, body)


@router.post("/services/{ref}/links", status_code=201, summary="Link a service to a record")
def add_service_link(request: Request, ref: str, body: LinkBody) -> dict[str, Any]:
    return add_record_link(request, SERVICE, ref, body)


@router.delete("/services/{ref}/links/{link_id}", summary="Remove a link from a service")
def remove_service_link(request: Request, ref: str, link_id: int) -> dict[str, Any]:
    return remove_record_link(request, SERVICE, ref, link_id)


@router.get("/services/{ref}/history", summary="Everything that has happened to a service")
def service_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, SERVICE, ref)


# --- Tiering ------------------------------------------------------------------------------


@router.get("/tiers", summary="The program's tiers, with what each means and its rules")
def list_tiers(request: Request) -> dict[str, Any]:
    with reading(request) as session:
        return envelope(tiering.tiers(session))


@router.get(
    "/third-parties/{ref}/tiering",
    summary="A third party's tiering: the questions, what the inventory suggests, and its tierings",
)
def show_tiering(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        third_party = records.load(session, principal, THIRD_PARTY, ref)
        return envelope(tiering.view(session, principal, third_party))


@router.post(
    "/third-parties/{ref}/tiering",
    status_code=201,
    summary="Tier a third party: the answers, and the tier with a reason if it differs",
)
def record_tiering(request: Request, ref: str, body: TieringBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        third_party = records.load(session, principal, THIRD_PARTY, ref)
        tiering.record(session, principal, third_party, body.answers, body.tier, body.rationale)
        return envelope(tiering.view(session, principal, third_party))
