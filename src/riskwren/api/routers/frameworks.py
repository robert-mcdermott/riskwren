"""Frameworks: what the organization is held to, and the requirements of each."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import clamp_limit, decode_cursor, envelope, reading, writing
from riskwren.api.routers.inventory import paging
from riskwren.compliance import frameworks

router = APIRouter(prefix="/api/v1", tags=["frameworks"])


class FrameworkBody(BaseModel):
    """A framework of the organization's own. On a change, send only what changes."""

    title: str | None = Field(default=None, max_length=400)
    key: str | None = Field(
        default=None, description="A short key; made from the title if left out"
    )
    kind: str | None = Field(
        default=None, description="standard, regulation, agreement, or internal"
    )
    version: str | None = None
    publisher: str | None = Field(default=None, description="Who it comes from: a sponsor, a party")
    summary: str | None = None
    source_url: str | None = None
    status: str | None = Field(default=None, description="active or retired")


class RequirementBody(BaseModel):
    code: str | None = Field(default=None, description="A stable code, such as 4.2 or DUA-7")
    title: str | None = None
    text: str | None = Field(default=None, description="What is required")
    guidance: str | None = None
    parent: str | None = Field(default=None, description="The code of the requirement above it")
    is_citable: bool | None = Field(default=None, description="False for a heading")


class PasteBody(BaseModel):
    text: str = Field(description="One requirement to a line: a code, then what it requires")


CODE = Query(description="The requirement's code, such as AC-2 or 164.308(a)(1)(i)")


@router.get("/frameworks", summary="The frameworks on record")
def list_frameworks(request: Request, retired: bool = False) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        rows = frameworks.all_(session, retired=retired)
        return envelope([frameworks.view(session, principal, row) for row in rows])


@router.post("/frameworks", status_code=201, summary="Enter a framework of your own")
def create_framework(request: Request, body: FrameworkBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        made = frameworks.create(session, principal, body.model_dump(exclude_unset=True))
        return envelope(frameworks.view(session, principal, made))


@router.get("/frameworks/{key}", summary="One framework, with its source and baselines")
def show_framework(request: Request, key: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(frameworks.view(session, principal, frameworks.by_key(session, key)))


@router.patch("/frameworks/{key}", summary="Change a framework of your own, or retire any")
def update_framework(request: Request, key: str, body: FrameworkBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        framework = frameworks.by_key(session, key)
        frameworks.update(session, principal, framework, body.model_dump(exclude_unset=True))
        return envelope(frameworks.view(session, principal, framework))


@router.get(
    "/frameworks/{key}/requirements",
    summary="One level of a framework's tree, or the requirements that match",
)
def list_requirements(
    request: Request,
    key: str,
    parent: str | None = Query(default=None, description="A code; lists what is beneath it"),
    q: str | None = Query(default=None, description="Words to find in codes, titles, and text"),
    baseline: str | None = Query(default=None, description="A baseline's key"),
    limit: int | None = Query(default=None, ge=1, le=200),
    cursor: str | None = None,
) -> dict[str, Any]:
    current(request)
    size = clamp_limit(limit)
    offset = int((decode_cursor(cursor) or {}).get("offset", 0))
    with reading(request) as session:
        rows, total = frameworks.listing(
            session, frameworks.by_key(session, key), parent=parent, query=q, baseline=baseline,
            limit=size, offset=offset,
        )  # fmt: skip
    return envelope(rows, **paging(total, offset, size, len(rows)))


@router.post(
    "/frameworks/{key}/requirements", status_code=201, summary="Add a requirement to your own"
)
def add_requirement(request: Request, key: str, body: RequirementBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        framework = frameworks.by_key(session, key)
        row = frameworks.add_requirement(
            session, principal, framework, body.model_dump(exclude_unset=True)
        )
        return envelope(frameworks.detail(session, framework, row.code))


@router.post(
    "/frameworks/{key}/requirements/paste",
    summary="Add many requirements from pasted lines, after a dry run",
)
def paste_requirements(
    request: Request, key: str, body: PasteBody, dry_run: bool = True
) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        framework = frameworks.by_key(session, key)
        return envelope(frameworks.paste(session, principal, framework, body.text, dry_run=dry_run))


@router.get("/frameworks/{key}/requirement", summary="One requirement in full")
def show_requirement(request: Request, key: str, code: str = CODE) -> dict[str, Any]:
    current(request)
    with reading(request) as session:
        return envelope(frameworks.detail(session, frameworks.by_key(session, key), code))


@router.patch("/frameworks/{key}/requirement", summary="Change a requirement of your own")
def update_requirement(
    request: Request, key: str, body: RequirementBody, code: str = CODE
) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        framework = frameworks.by_key(session, key)
        row = frameworks.find(session, framework, code)
        frameworks.update_requirement(
            session, principal, framework, row, body.model_dump(exclude_unset=True)
        )
        return envelope(frameworks.detail(session, framework, row.code))


@router.delete("/frameworks/{key}/requirement", summary="Remove a requirement of your own")
def remove_requirement(request: Request, key: str, code: str = CODE) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        framework = frameworks.by_key(session, key)
        frameworks.remove_requirement(
            session, principal, framework, frameworks.find(session, framework, code)
        )
        return envelope({"removed": code})
