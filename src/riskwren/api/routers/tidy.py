"""Finding anything on record, and keeping the record in order: one search, saved views,
what records are missing, likely duplicates, and what a person held when they left."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import envelope, reading, writing
from riskwren.core.errors import Invalid
from riskwren.inventory import completeness, duplicates, find, records, views
from riskwren.inventory.registry import TYPES, RecordType, find_any
from riskwren.people import accounts, handover

router = APIRouter(prefix="/api/v1", tags=["find"])


def _type(key: str | None) -> RecordType:
    found = TYPES.get(key or "")
    if found is None:
        raise Invalid("That is not a kind of record.", {"type": f"Use one of: {', '.join(TYPES)}."})
    return found


@router.get("/search", summary="Search every kind of record")
def search(
    request: Request,
    q: str = Query(description="Words to look for; every word must be on the record"),
    type: str | None = Query(default=None, description="Only this kind, such as risk"),
    limit: int = Query(default=6, ge=1, le=50, description="How many of each kind"),
) -> dict[str, Any]:
    """Looks in names, references, summaries, and what a record is called elsewhere, across
    every kind of record and actions. Only what you may open is returned."""
    principal = current(request)
    with reading(request) as session:
        return envelope(find.everywhere(session, principal, q, only=type, each=limit))


class ViewBody(BaseModel):
    """A saved view. On a change, send only what changes."""

    name: str | None = Field(default=None, max_length=200)
    path: str | None = Field(default=None, description="The list it is of, such as /risks")
    query: str | None = Field(default=None, description="Its filters, as the address has them")
    shared: bool | None = Field(default=None, description="Whether everyone has it")


@router.get("/views", summary="Your saved views, and the shared ones")
def list_views(
    request: Request, path: str | None = Query(default=None, description="Of one list only")
) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(
            views.listed(session, principal, path), can_share=views.may_share(principal)
        )


@router.post("/views", status_code=201, summary="Save a view")
def save_view(request: Request, body: ViewBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = views.create(session, principal, body.model_dump(exclude_unset=True))
        return envelope(views.view(row, principal))


@router.patch("/views/{view_id}", summary="Rename, change, share, or stop sharing a view")
def change_view(request: Request, view_id: int, body: ViewBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = views.get(session, principal, view_id, to_change=True)
        views.update(session, principal, row, body.model_dump(exclude_unset=True))
        return envelope(views.view(row, principal))


@router.delete("/views/{view_id}", summary="Delete a view")
def delete_view(request: Request, view_id: int) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        views.delete(session, principal, views.get(session, principal, view_id, to_change=True))
        return envelope(None)


@router.get("/tidy", summary="What needs putting in order")
def tidy(
    request: Request,
    unit: int | None = Query(default=None, description="A unit's id, with every unit beneath"),
) -> dict[str, Any]:
    """What records are missing, likely duplicates, and what people who have left still
    hold, each cut to what you may see. Every count is the length of the list behind it."""
    principal = current(request)
    with reading(request) as session:
        return envelope(
            {
                "completeness": completeness.summary(session, principal, unit),
                "duplicates": duplicates.everything(session, principal),
                "handover": handover.waiting(session, principal),
            }
        )


@router.get("/similar", summary="Records that one with this name might already be")
def similar(
    request: Request,
    type: str = Query(description="The kind of record, such as issue"),
    name: str = Query(description="The name being given"),
    unit: int | None = Query(default=None, description="The unit it would belong to"),
    apart_from: str | None = Query(default=None, description="A reference to leave out"),
) -> dict[str, Any]:
    principal = current(request)
    record_type = _type(type)
    with reading(request) as session:
        skipped = None
        if apart_from:
            skipped = records.load(session, principal, record_type, apart_from).id
        return envelope(
            duplicates.similar(session, principal, record_type, name, unit=unit, except_id=skipped)
        )


class PairBody(BaseModel):
    refs: list[str] = Field(description="The two references, such as SYS-0004 and SYS-0019")


@router.post("/tidy/not-duplicates", summary="Say that two records are different things")
def not_duplicates(request: Request, body: PairBody) -> dict[str, Any]:
    principal = current(request)
    if len(body.refs) != 2:
        raise Invalid("Nothing was changed.", {"refs": "Name two records."})
    with writing(request, principal.actor) as session:
        first_type, _ = find_any(session, body.refs[0])
        one = records.load(session, principal, first_type, body.refs[0])
        other = records.load(session, principal, first_type, body.refs[1])
        duplicates.dismiss(session, principal, first_type, one, other)
        return envelope(None)


@router.get("/accounts/{account_id}/holdings", summary="What a person answers for")
def holdings(request: Request, account_id: int) -> dict[str, Any]:
    """Everything they are named on, and what was passed to a stand-in when their account
    was disabled, cut to what you may see."""
    principal = current(request)
    with reading(request) as session:
        return envelope(handover.holdings(session, principal, accounts.get(session, account_id)))


class HandoverItem(BaseModel):
    type: str
    id: int


class HandoverBody(BaseModel):
    to: int = Field(description="The account that takes it")
    only: list[HandoverItem] | None = Field(
        default=None, description="Only these; everything you may pass on if absent"
    )


@router.post("/accounts/{account_id}/handover", summary="Pass on what a person held")
def pass_on(request: Request, account_id: int, body: HandoverBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        account = accounts.get(session, account_id)
        only = [(each.type, each.id) for each in body.only] if body.only is not None else None
        moved = handover.pass_on(
            session, principal, account, accounts.get(session, body.to), only=only
        )
        return envelope({"passed_on": moved, **handover.holdings(session, principal, account)})
