"""Evidence: items, the files behind them, and what each supports."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import FileResponse
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
from riskwren.compliance import evidence
from riskwren.compliance.evidence import EVIDENCE
from riskwren.inventory import records
from riskwren.inventory.registry import find, find_any

router = APIRouter(prefix="/api/v1", tags=["evidence"])

# A file is only ever a download. Nothing in it can run in the app's origin: it is sent as
# an attachment, under a policy that allows nothing, and the browser is told not to guess.
DOWNLOAD_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; sandbox",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
}
# Kinds a browser will not run. Everything else leaves as plain bytes.
INERT = {"application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp", "text/plain"}


class EvidenceBody(BaseModel):
    """An evidence item. On a change, send only what changes, with the ``version`` you had."""

    version: int | None = None
    name: str | None = Field(default=None, max_length=400, description="What it is, briefly")
    summary: str | None = None
    kind: str | None = Field(default=None, description="file, link, note, or attestation")
    url: str | None = None
    note: str | None = Field(default=None, description="What was seen, or what is attested to")
    data_class: str | None = None
    collected_on: str | None = Field(default=None, description="The day it was collected")
    covers_from: str | None = None
    covers_to: str | None = None
    valid_until: str | None = Field(
        default=None, description="The day it stops counting; a year after collection if absent"
    )
    org_unit_id: int | None = None
    status: str | None = None
    tags: list[str] | None = None
    restricted: bool | None = None


class SubjectsBody(BaseModel):
    subjects: list[str] = Field(description="References of controls and scopes, such as CTL-0007")


@router.get("/evidence", summary="Find evidence")
def list_evidence(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    status: str | None = None,
    kind: str | None = None,
    state: str | None = Query(default=None, description="current, expiring, or stale"),
    subject: str | None = Query(default=None, description="A control or scope it supports"),
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = SORT,
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = {"q": q, "unit": unit, "status": status, "kind": kind, "state": state,
               "subject": subject, "owner": owner, "mine": mine}  # fmt: skip
    return list_records(request, EVIDENCE, filters, sort, limit, cursor)


@router.post("/evidence", status_code=201, summary="Add an evidence item")
def create_evidence(request: Request, body: EvidenceBody) -> dict[str, Any]:
    return create_record(request, EVIDENCE, body)


@router.get("/evidence/{ref}", summary="One evidence item, with what it supports")
def show_evidence(request: Request, ref: str) -> dict[str, Any]:
    return show_record(request, EVIDENCE, ref)


@router.patch("/evidence/{ref}", summary="Change an evidence item")
def update_evidence(request: Request, ref: str, body: EvidenceBody) -> dict[str, Any]:
    return update_record(request, EVIDENCE, ref, body)


@router.put("/evidence/{ref}/owners", summary="Set an evidence item's owners")
def set_evidence_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, EVIDENCE, ref, body)


@router.get("/evidence/{ref}/history", summary="Everything that has happened to an evidence item")
def evidence_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, EVIDENCE, ref)


@router.put("/evidence/{ref}/subjects", summary="Say what an evidence item supports")
def set_subjects(request: Request, ref: str, body: SubjectsBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        item = records.load(session, principal, EVIDENCE, ref)
        evidence.set_subjects(session, principal, item, body.subjects)
        return envelope(records.detail(session, principal, EVIDENCE, item))


@router.post("/evidence/{ref}/file", summary="Send the file an evidence item holds")
async def upload_file(
    request: Request,
    ref: str,
    name: str | None = Query(default=None, description="The file's name", max_length=200),
) -> dict[str, Any]:
    """Send the file as the request body. Its type is judged by its content: PDF, common
    images, Word, Excel, and PowerPoint documents, and plain text, up to 25 MB."""
    from starlette.concurrency import run_in_threadpool

    data = await request.body()

    def keep() -> dict[str, Any]:
        principal = current(request)
        with writing(request, principal.actor) as session:
            item = records.load(session, principal, EVIDENCE, ref)
            evidence.attach_file(session, principal, item, request.app.state.home.files, data, name)
            return envelope(records.detail(session, principal, EVIDENCE, item))

    return await run_in_threadpool(keep)


@router.get("/evidence/{ref}/file", summary="Download the file an evidence item holds")
def download_file(request: Request, ref: str) -> Response:
    principal = current(request)
    with writing(request, principal.actor) as session:
        item = find(session, EVIDENCE, ref)
        path, name, media_type = evidence.download(
            session, principal, item, request.app.state.home.files
        )
    plain = name.encode("ascii", "ignore").decode().replace('"', "") or "file"
    disposition = f"attachment; filename=\"{plain}\"; filename*=UTF-8''{quote(name)}"
    return FileResponse(
        path,
        media_type=media_type if media_type in INERT else "application/octet-stream",
        headers={**DOWNLOAD_HEADERS, "Content-Disposition": disposition},
    )


@router.get("/evidence-for/{ref}", summary="The evidence attached to a control or a scope")
def evidence_for(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        record_type, subject = find_any(session, ref)
        if record_type.key not in evidence.SUBJECTS:
            return envelope({"items": [], "hidden": 0, "current": 0, "can_add": False})
        subject = records.load(session, principal, record_type, ref)
        return envelope(evidence.of_subject(session, principal, record_type, subject))
