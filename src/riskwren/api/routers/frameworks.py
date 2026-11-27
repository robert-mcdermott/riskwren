"""Frameworks: what the organization is held to, and the requirements of each."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import clamp_limit, decode_cursor, envelope, reading, writing
from riskwren.api.routers.inventory import paging
from riskwren.compliance import crosswalk, frameworks, packs, versions
from riskwren.controls.service import CONTROL
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.inventory import records
from riskwren.policy import governs

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
FROM = Query(alias="from", description="The key of the earlier version")


class PackBody(BaseModel):
    """A framework to load: one that ships, by its key, or a whole pack."""

    key: str | None = Field(default=None, description="The key of a pack that ships")
    pack: dict[str, Any] | None = Field(default=None, description="A whole framework pack")


class VersionBody(BaseModel):
    title: str = Field(max_length=400, description="The new version's title")
    version: str | None = Field(default=None, max_length=120, description="What it is called")


class SuggestionBody(BaseModel):
    control: str = Field(description="The control's reference")
    code: str = Field(description="The requirement's code in this framework")


@router.get("/framework-packs", summary="The frameworks that ship, and which are loaded")
def framework_packs(request: Request) -> dict[str, Any]:
    with reading(request) as session:
        have = {row.key for row in frameworks.all_(session, retired=True)}
        found = []
        for key in packs.AVAILABLE:
            head = packs.builtin(key)["pack"]
            found.append({
                "key": key, "title": head["title"], "version": head.get("version"),
                "summary": head.get("summary"), "follows": head.get("follows"),
                "loaded": key in have, "with_every_installation": key in packs.BUILTIN,
            })  # fmt: skip
        return envelope(found)


@router.post("/framework-packs", status_code=201, summary="Load a framework beside the others")
def load_pack(request: Request, body: PackBody) -> dict[str, Any]:
    """A pack that ships, by its key, or a whole pack: a publisher's new version, or a
    framework an organization keeps for itself. It is loaded beside what is there, never over
    it, and changes nothing that uses another."""
    principal = current(request)
    if not principal.configures:
        raise PermissionDenied("Only those who run the program load frameworks.")
    if bool(body.key) == bool(body.pack):
        raise Invalid("Nothing was loaded.", {"key": "Name a pack that ships, or give a pack."})
    with writing(request, principal.actor) as session:
        if body.key:
            if body.key not in packs.AVAILABLE:
                raise Invalid("Nothing was loaded.", {"key": f"No pack {body.key} ships."})
            pack = packs.builtin(body.key)
        else:
            pack = body.pack or {}
        made = packs.load(session, pack, account_id=principal.account_id)
        return envelope(frameworks.view(session, principal, made))


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
        framework = frameworks.by_key(session, key)
        return envelope({
            **frameworks.view(session, principal, framework),
            "versions": versions.versions(session, framework),
            "suggested": crosswalk.publisher_suggestions(session, principal, framework)["total"],
        })  # fmt: skip


@router.get("/frameworks/{key}/changes", summary="What changed from an earlier version")
def framework_changes(request: Request, key: str, earlier: str = FROM) -> dict[str, Any]:
    """Requirements added, changed, and withdrawn since the earlier version, and what uses the
    earlier one: the scopes held to it, the controls, exceptions, and documents mapped to what
    changed, and how many crosswalks a move would carry."""
    principal = current(request)
    with reading(request) as session:
        new = frameworks.by_key(session, key)
        old = frameworks.by_key(session, earlier)
        return envelope({
            **versions.changes(session, old, new),
            "affects": versions.affects(session, principal, old, new),
        })  # fmt: skip


@router.get("/frameworks/{key}/change", summary="One requirement in both versions")
def framework_change(
    request: Request, key: str, earlier: str = FROM, code: str = CODE
) -> dict[str, Any]:
    with reading(request) as session:
        new = frameworks.by_key(session, key)
        old = frameworks.by_key(session, earlier)
        return envelope(versions.compare_one(session, old, new, code))


@router.post(
    "/frameworks/{key}/versions", status_code=201, summary="Start a new version of your own"
)
def start_version(request: Request, key: str, body: VersionBody) -> dict[str, Any]:
    """A copy of a framework of the organization's own, beside it, to be edited."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        framework = frameworks.by_key(session, key)
        made = versions.start_version(session, principal, framework, body.model_dump())
        return envelope(frameworks.view(session, principal, made))


@router.get("/frameworks/{key}/suggestions", summary="Crosswalks a publisher's mapping suggests")
def suggestions(request: Request, key: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        framework = frameworks.by_key(session, key)
        return envelope(crosswalk.publisher_suggestions(session, principal, framework))


@router.post("/frameworks/{key}/suggestions/confirm", summary="Map a suggested crosswalk")
def confirm_suggestion(request: Request, key: str, body: SuggestionBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        framework = frameworks.by_key(session, key)
        control = records.load(session, principal, CONTROL, body.control)
        crosswalk.confirm_suggestion(session, principal, framework, control, body.code)
        return envelope(crosswalk.publisher_suggestions(session, principal, framework))


@router.post("/frameworks/{key}/suggestions/set-aside", summary="Set a suggestion aside")
def set_suggestion_aside(request: Request, key: str, body: SuggestionBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        framework = frameworks.by_key(session, key)
        control = records.load(session, principal, CONTROL, body.control)
        crosswalk.set_aside(session, principal, framework, control, body.code)
        return envelope(crosswalk.publisher_suggestions(session, principal, framework))


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
    mapped: bool | None = Query(
        default=None, description="true for those with a control, false for those with none"
    ),
    limit: int | None = Query(default=None, ge=1, le=200),
    cursor: str | None = None,
) -> dict[str, Any]:
    principal = current(request)
    size = clamp_limit(limit)
    offset = int((decode_cursor(cursor) or {}).get("offset", 0))
    with reading(request) as session:
        only = None if mapped is None else crosswalk.condition(session, principal, mapped=mapped)
        rows, total = frameworks.listing(
            session, frameworks.by_key(session, key), parent=parent, query=q, baseline=baseline,
            only=only, limit=size, offset=offset,
        )  # fmt: skip
        have = crosswalk.counts(session, principal, [row["id"] for row in rows])
        for row in rows:
            row["controls"] = have.get(row["id"], 0)
    return envelope(rows, **paging(total, offset, size, len(rows)))


@router.get(
    "/frameworks/{key}/coverage",
    summary="How many of a framework's requirements have a control mapped to them",
)
def framework_coverage(request: Request, key: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(crosswalk.coverage(session, principal, frameworks.by_key(session, key)))


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


@router.get("/frameworks/{key}/requirement", summary="One requirement in full, with its controls")
def show_requirement(request: Request, key: str, code: str = CODE) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        framework = frameworks.by_key(session, key)
        found = frameworks.detail(session, framework, code)
        row = frameworks.find(session, framework, code)
        return envelope({
            **found,
            **crosswalk.controls_of(session, principal, row),
            **governs.of_requirement(session, principal, row),
        })  # fmt: skip


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
