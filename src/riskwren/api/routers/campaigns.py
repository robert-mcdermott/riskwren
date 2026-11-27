"""Campaigns: asking a set of people for one thing by a date, and what each answered."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import envelope, reading, writing
from riskwren.oversight import campaigns

router = APIRouter(prefix="/api/v1", tags=["campaigns"])


class CampaignIn(BaseModel):
    kind: str = Field(max_length=24)
    name: str = Field(default="", max_length=200)
    summary: str | None = Field(default=None, max_length=2000)
    org_unit_id: int | None = None
    scope: str | None = Field(default=None, max_length=24)
    due_on: str = Field(default="", max_length=10)
    wanted: str | None = Field(default=None, max_length=2000)
    document: str | None = Field(default=None, max_length=24, description="For acknowledgment")


class AnswersIn(BaseModel):
    answers: dict[str, Any]
    complete: bool = True


class Excuse(BaseModel):
    note: str = Field(max_length=1000)


@router.get("/campaigns", summary="Campaigns you run or may read")
def list_(request: Request, status: str | None = None) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(
            {
                "campaigns": campaigns.search(session, principal, status=status),
                "kinds": [
                    {
                        "key": kind.key,
                        "label": kind.label,
                        "asks": kind.asks,
                        "by_scope": kind.by_scope,
                    }
                    for kind in campaigns.KINDS.values()
                ],
                "can_start": principal.assesses,
            }
        )


@router.post("/campaigns/preview", summary="Who a campaign would ask")
def preview(request: Request, body: CampaignIn) -> dict[str, Any]:
    """Counts what would be asked and of how many people. Nothing is started."""
    principal = current(request)
    with reading(request) as session:
        return envelope(campaigns.preview(session, principal, body.model_dump()))


@router.post("/campaigns", summary="Start a campaign", status_code=201)
def start(request: Request, body: CampaignIn) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        campaign = campaigns.launch(session, principal, body.model_dump())
        return envelope(campaigns.view(session, principal, campaign))


@router.get("/campaigns/{ref}", summary="One campaign: progress, coverage by unit, and items")
def show(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        campaign = campaigns.find(session, principal, ref)
        campaigns.refresh(session, campaign)  # evidence that has arrived closes its request
        return envelope(campaigns.view(session, principal, campaign))


@router.post("/campaigns/{ref}/remind", summary="Remind everyone who has not answered")
def remind(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        campaign = campaigns.find(session, principal, ref)
        return envelope({"reminded": campaigns.remind(session, principal, campaign)})


@router.post("/campaigns/{ref}/close", summary="Close a campaign, keeping what was answered")
def close(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        campaign = campaigns.find(session, principal, ref)
        campaigns.end(session, principal, campaign)
        return envelope(campaigns.view(session, principal, campaign))


@router.post("/campaigns/{ref}/cancel", summary="Cancel a campaign started in error")
def cancel(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        campaign = campaigns.find(session, principal, ref)
        campaigns.end(session, principal, campaign, cancel=True)
        return envelope(campaigns.view(session, principal, campaign))


@router.get("/campaign-items/{item_id}", summary="What one person is asked")
def item(request: Request, item_id: int) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        found, campaign = campaigns.find_item(session, principal, item_id)
        return envelope(campaigns.item_detail(session, principal, found, campaign))


@router.post("/campaign-items/{item_id}/answer", summary="Answer what you were asked")
def answer(request: Request, item_id: int, body: AnswersIn) -> dict[str, Any]:
    """With ``complete`` false the answers are kept as a draft and the item stays open."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        found, campaign = campaigns.find_item(session, principal, item_id)
        campaigns.answer(session, principal, found, campaign, body.answers, complete=body.complete)
        return envelope(campaigns.item_detail(session, principal, found, campaign))


@router.post("/campaign-items/{item_id}/excuse", summary="Take an item out of a campaign")
def excuse(request: Request, item_id: int, body: Excuse) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        found, campaign = campaigns.find_item(session, principal, item_id)
        campaigns.excuse(session, principal, found, campaign, body.note)
        return envelope(campaigns.item_view(session, principal, found))
