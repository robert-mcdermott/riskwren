"""Agreements: awards, data use agreements, contracts, and the like, with their parties,
dates, what they cover, and the requirements they impose."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import envelope, writing
from riskwren.api.routers.inventory import (
    LIMIT,
    MINE,
    SORT,
    UNIT,
    OwnersBody,
    Q,
    create_record,
    list_records,
    record_history,
    set_record_owners,
    show_record_plain,
    update_record,
)
from riskwren.compliance import agreements
from riskwren.compliance.agreements import AGREEMENT
from riskwren.inventory import records

router = APIRouter(prefix="/api/v1", tags=["agreements"])


class AgreementBody(BaseModel):
    """An agreement. On a change, send only what changes, with the ``version`` you had."""

    version: int | None = None
    name: str | None = Field(default=None, max_length=400)
    summary: str | None = None
    kind: str | None = Field(
        default=None,
        description="award, data_use, business_associate, contract, confidentiality, "
        "memorandum, or other",
    )
    parties: str | None = Field(default=None, max_length=400, description="Who it is with")
    reference: str | None = Field(default=None, max_length=200, description="Their number for it")
    url: str | None = Field(default=None, description="Where the signed copy is kept")
    starts_on: str | None = None
    ends_on: str | None = Field(default=None, description="Leave out for one that runs on")
    notice_days: int | None = Field(
        default=None, description="Days before it ends by which notice must be given"
    )
    renews: bool | None = Field(default=None, description="Whether it carries on by itself")
    framework: str | None = Field(
        default=None, description="The key of the framework of the requirements it imposes"
    )
    org_unit_id: int | None = None
    tags: list[str] | None = None
    restricted: bool | None = None


class CoversBody(BaseModel):
    covers: list[str] = Field(description="The references of the systems, information, and scopes")


class CloseBody(BaseModel):
    note: str | None = Field(default=None, max_length=4000, description="Why it is closed")


def _act(request: Request, ref: str, act: Any) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        agreement = records.load(session, principal, AGREEMENT, ref)
        act(session, principal, agreement)
        return envelope(records.detail(session, principal, AGREEMENT, agreement))


@router.get("/agreements", summary="Find agreements")
def list_agreements(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    kind: str | None = Query(default=None, description="The kind of agreement"),
    status: str | None = Query(default=None, description="active (the default), closed, or all"),
    state: str | None = Query(
        default=None, description="in_force, ending, ended, upcoming, or closed"
    ),
    framework: str | None = Query(default=None, description="Those that impose this framework"),
    covers: str | None = Query(default=None, description="Those that cover this record"),
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = Query(default="ends_on", description=SORT.description),
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = {"q": q, "unit": unit, "kind": kind, "status": status, "state": state,
               "framework": framework, "covers": covers, "owner": owner, "mine": mine}  # fmt: skip
    return list_records(request, AGREEMENT, filters, sort, limit, cursor)


@router.post("/agreements", status_code=201, summary="Add an agreement")
def create_agreement(request: Request, body: AgreementBody) -> dict[str, Any]:
    return create_record(request, AGREEMENT, body)


@router.get("/agreements/{ref}", summary="One agreement: what it covers and what it imposes")
def show_agreement(request: Request, ref: str) -> dict[str, Any]:
    return show_record_plain(request, AGREEMENT, ref)


@router.patch("/agreements/{ref}", summary="Change an agreement, its dates, or its terms")
def update_agreement(request: Request, ref: str, body: AgreementBody) -> dict[str, Any]:
    return update_record(request, AGREEMENT, ref, body)


@router.put("/agreements/{ref}/owners", summary="Set an agreement's owners")
def set_agreement_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, AGREEMENT, ref, body)


@router.get("/agreements/{ref}/history", summary="Everything that has happened to an agreement")
def agreement_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, AGREEMENT, ref)


@router.put("/agreements/{ref}/covers", summary="Say what an agreement covers")
def set_covers(request: Request, ref: str, body: CoversBody) -> dict[str, Any]:
    """Every scope that holds what it covers is held to the framework it imposes."""
    return _act(request, ref, lambda s, p, a: agreements.set_coverage(s, p, a, body.covers))


@router.post("/agreements/{ref}/close", summary="Close an agreement that has ended")
def close_agreement(request: Request, ref: str, body: CloseBody) -> dict[str, Any]:
    """What it imposed leaves the scopes that held it because of it."""
    return _act(request, ref, lambda s, p, a: agreements.close(s, p, a, body.note))


@router.post("/agreements/{ref}/reopen", summary="Open a closed agreement again")
def reopen_agreement(request: Request, ref: str) -> dict[str, Any]:
    return _act(request, ref, agreements.reopen)
