"""Indicators: measures with thresholds, their readings, and the risks they warn of."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import envelope, reading, writing
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
    show_record,
    update_record,
)
from riskwren.inventory import records
from riskwren.risk import indicators
from riskwren.risk.indicators import INDICATOR
from riskwren.risk.register import RISK

router = APIRouter(prefix="/api/v1", tags=["indicators"])


class IndicatorBody(BaseModel):
    """An indicator. On a change, send only what changes, with the ``version`` you had."""

    version: int | None = None
    name: str | None = Field(default=None, max_length=400, description="What is measured")
    summary: str | None = None
    measure: str | None = Field(default=None, max_length=40, description="Counted in: %, days")
    source: str | None = Field(default=None, description="Where the number is read from")
    direction: str | None = Field(default=None, description="up if higher is worse, else down")
    warn_at: float | None = Field(default=None, description="The level at which to worry")
    breach_at: float | None = Field(default=None, description="The level that is too far")
    frequency: str | None = Field(default=None, description="weekly, monthly, quarterly, annually")
    org_unit_id: int | None = None
    status: str | None = None
    tags: list[str] | None = None
    restricted: bool | None = None


class ReadingBody(BaseModel):
    value: float
    read_on: str | None = Field(default=None, description="The day it was read; today if absent")
    note: str | None = Field(default=None, max_length=2000)


class RisksBody(BaseModel):
    risks: list[str] = Field(description="References of the risks it warns of, such as RSK-0007")


@router.get("/indicators", summary="Find indicators")
def list_indicators(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    status: str | None = None,
    state: str | None = Query(default=None, description="ok, warn, breach, or no_reading"),
    risk: str | None = Query(default=None, description="A risk it warns of"),
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = SORT,
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = {"q": q, "unit": unit, "status": status, "state": state, "risk": risk,
               "owner": owner, "mine": mine}  # fmt: skip
    return list_records(request, INDICATOR, filters, sort, limit, cursor)


@router.post("/indicators", status_code=201, summary="Add an indicator")
def create_indicator(request: Request, body: IndicatorBody) -> dict[str, Any]:
    return create_record(request, INDICATOR, body)


@router.get("/indicators/{ref}", summary="One indicator, with its readings and risks")
def show_indicator(request: Request, ref: str) -> dict[str, Any]:
    return show_record(request, INDICATOR, ref)


@router.patch("/indicators/{ref}", summary="Change an indicator")
def update_indicator(request: Request, ref: str, body: IndicatorBody) -> dict[str, Any]:
    return update_record(request, INDICATOR, ref, body)


@router.put("/indicators/{ref}/owners", summary="Set an indicator's owners")
def set_indicator_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, INDICATOR, ref, body)


@router.get("/indicators/{ref}/history", summary="Everything that has happened to an indicator")
def indicator_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, INDICATOR, ref)


@router.post("/indicators/{ref}/readings", summary="Record what an indicator stands at")
def record_reading(request: Request, ref: str, body: ReadingBody) -> dict[str, Any]:
    """A second reading for the same day corrects the first. A reading that takes the
    indicator past its limit tells its owners and flags the risks it warns of."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        indicator = records.load(session, principal, INDICATOR, ref)
        indicators.record_reading(
            session, principal, indicator, value=body.value, read_on=body.read_on, note=body.note
        )
        return envelope(records.detail(session, principal, INDICATOR, indicator))


@router.put("/indicators/{ref}/risks", summary="Say which risks an indicator warns of")
def set_risks(request: Request, ref: str, body: RisksBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        indicator = records.load(session, principal, INDICATOR, ref)
        indicators.set_risks(session, principal, indicator, body.risks)
        return envelope(records.detail(session, principal, INDICATOR, indicator))


@router.get("/risks/{ref}/indicators", summary="The indicators that warn of a risk")
def risk_indicators(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        risk = records.load(session, principal, RISK, ref)
        return envelope(indicators.of_risk(session, principal, risk))
