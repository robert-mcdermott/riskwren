"""Policy documents: policies, standards, procedures, and guidelines, their versions, and the
approvals each version is published on."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import envelope, reading, writing
from riskwren.api.routers.evidence import DOWNLOAD_HEADERS, INERT
from riskwren.api.routers.inventory import (
    LIMIT,
    MINE,
    SORT,
    UNIT,
    OwnersBody,
    Q,
    list_records,
    record_history,
    set_record_owners,
    show_record_plain,
    update_record,
    values_of,
)
from riskwren.inventory import records
from riskwren.policy import documents
from riskwren.policy.documents import DOCUMENT

router = APIRouter(prefix="/api/v1", tags=["documents"])


class DocumentBody(BaseModel):
    """A document. On a change, send only what changes, with the ``version`` you had. On
    adding one, its first draft may be given as well."""

    version: int | None = None
    name: str | None = Field(default=None, max_length=400, description="Its title")
    summary: str | None = Field(default=None, description="What it is for, in a sentence or two")
    kind: str | None = Field(default=None, description="policy, standard, procedure, or guideline")
    parent: str | None = Field(default=None, description="The reference of what it implements")
    review_months: int | None = Field(default=None, description="Months between reviews")
    org_unit_id: int | None = None
    tags: list[str] | None = None
    restricted: bool | None = None
    form: str | None = Field(default=None, description="text, link, or file")
    body: str | None = Field(default=None, description="Its text, in a simple Markdown")
    url: str | None = Field(default=None, description="Where it is kept, if not here")


class DraftBody(BaseModel):
    """The draft's content. Send only what changes."""

    form: str | None = Field(default=None, description="text, link, or file")
    body: str | None = Field(default=None, description="Its text, in a simple Markdown")
    url: str | None = Field(default=None, description="Where it is kept, if not here")
    change_note: str | None = Field(default=None, description="What changed, and why")


class SubmitBody(BaseModel):
    approvers: list[int] = Field(description="The accounts asked to approve it")


class DecisionBody(BaseModel):
    decision: str = Field(description="approved, or returned")
    note: str | None = Field(default=None, max_length=4000, description="Why; needed to return")


class NoteBody(BaseModel):
    note: str | None = Field(default=None, max_length=4000)


def _detail(request: Request, ref: str, act: Any) -> dict[str, Any]:
    """Load the document, do something to it, and answer with it as it now is."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        document = records.load(session, principal, DOCUMENT, ref)
        act(session, principal, document)
        return envelope(records.detail(session, principal, DOCUMENT, document))


@router.get("/documents", summary="Find documents")
def list_documents(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    kind: str | None = Query(default=None, description="policy, standard, procedure, guideline"),
    status: str | None = Query(default=None, description="active or retired"),
    state: str | None = Query(
        default=None,
        description="draft, in_review, approved, working, unpublished, due, or overdue",
    ),
    parent: str | None = Query(default=None, description="Those that implement this one"),
    awaiting_me: bool = Query(default=False, description="Waiting for my approval"),
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = SORT,
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = {"q": q, "unit": unit, "kind": kind, "status": status, "state": state,
               "parent": parent, "awaiting_me": awaiting_me, "owner": owner,
               "mine": mine}  # fmt: skip
    return list_records(request, DOCUMENT, filters, sort, limit, cursor)


@router.post("/documents", status_code=201, summary="Add a document, with its first draft")
def create_document(request: Request, body: DocumentBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        document = documents.create(session, principal, values_of(body))
        return envelope(records.detail(session, principal, DOCUMENT, document))


@router.get("/documents/{ref}", summary="One document: the version in force, and the one coming")
def show_document(request: Request, ref: str) -> dict[str, Any]:
    return show_record_plain(request, DOCUMENT, ref)


@router.patch("/documents/{ref}", summary="Change what a document is, or where it sits")
def update_document(request: Request, ref: str, body: DocumentBody) -> dict[str, Any]:
    return update_record(request, DOCUMENT, ref, body)


@router.put("/documents/{ref}/owners", summary="Set a document's owners")
def set_document_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, DOCUMENT, ref, body)


@router.get("/documents/{ref}/history", summary="Everything that has happened to a document")
def document_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, DOCUMENT, ref)


@router.post("/documents/{ref}/draft", status_code=201, summary="Start a new version")
def start_draft(request: Request, ref: str) -> dict[str, Any]:
    """The draft starts as a copy of the version in force."""
    return _detail(request, ref, documents.start_draft)


@router.patch("/documents/{ref}/draft", summary="Change the draft")
def save_draft(request: Request, ref: str, body: DraftBody) -> dict[str, Any]:
    values = body.model_dump(exclude_unset=True)
    return _detail(request, ref, lambda s, p, d: documents.save_draft(s, p, d, values))


@router.delete("/documents/{ref}/draft", summary="Discard the draft")
def discard_draft(request: Request, ref: str) -> dict[str, Any]:
    return _detail(request, ref, documents.discard)


@router.post("/documents/{ref}/draft/file", summary="Send a file as the draft's content")
async def upload_file(
    request: Request,
    ref: str,
    name: str | None = Query(default=None, description="The file's name", max_length=200),
) -> dict[str, Any]:
    """Send the file as the request body: PDF, Word, and the other kinds evidence takes, up
    to 25 MB."""
    from starlette.concurrency import run_in_threadpool

    data = await request.body()
    root = request.app.state.home.files

    def keep() -> dict[str, Any]:
        return _detail(
            request, ref, lambda s, p, d: documents.attach_file(s, p, d, root, data, name)
        )

    return await run_in_threadpool(keep)


@router.post("/documents/{ref}/draft/submit", summary="Send the draft to be approved")
def submit_draft(request: Request, ref: str, body: SubmitBody) -> dict[str, Any]:
    """None of the people named may be the one sending it, or the one who started it."""
    return _detail(request, ref, lambda s, p, d: documents.submit(s, p, d, body.approvers))


@router.post("/documents/{ref}/draft/decision", summary="Approve the draft, or return it")
def decide_draft(request: Request, ref: str, body: DecisionBody) -> dict[str, Any]:
    return _detail(
        request, ref, lambda s, p, d: documents.decide(s, p, d, body.decision, body.note)
    )


@router.post("/documents/{ref}/draft/withdraw", summary="Take the draft back from approval")
def withdraw_draft(request: Request, ref: str) -> dict[str, Any]:
    return _detail(request, ref, documents.withdraw)


@router.post("/documents/{ref}/draft/publish", summary="Publish the approved draft")
def publish_draft(request: Request, ref: str) -> dict[str, Any]:
    """It is numbered, put in force, and never changed again."""
    return _detail(request, ref, documents.publish)


@router.post("/documents/{ref}/review", summary="Review a document and keep it as it is")
def review_document(request: Request, ref: str, body: NoteBody) -> dict[str, Any]:
    return _detail(request, ref, lambda s, p, d: documents.review(s, p, d, body.note))


@router.post("/documents/{ref}/retire", summary="Take a document out of use")
def retire_document(request: Request, ref: str, body: NoteBody) -> dict[str, Any]:
    return _detail(request, ref, lambda s, p, d: documents.retire(s, p, d, body.note))


@router.post("/documents/{ref}/reinstate", summary="Put a retired document back in use")
def reinstate_document(request: Request, ref: str) -> dict[str, Any]:
    return _detail(request, ref, documents.reinstate)


@router.get("/documents/{ref}/versions/{version_id}", summary="One version of a document")
def show_version(request: Request, ref: str, version_id: int) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        document = records.load(session, principal, DOCUMENT, ref)
        version = documents.version_of(session, principal, document, version_id)
        return envelope(documents.version_view(session, principal, document, version))


@router.get("/documents/{ref}/compare", summary="Two versions side by side")
def compare_versions(
    request: Request,
    ref: str,
    older: int = Query(alias="from", description="A version's id"),
    newer: int = Query(alias="to", description="A version's id"),
) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        document = records.load(session, principal, DOCUMENT, ref)
        return envelope(documents.compare(session, principal, document, older, newer))


@router.get("/documents/{ref}/versions/{version_id}/file", summary="Download a version's file")
def download_file(request: Request, ref: str, version_id: int) -> Response:
    principal = current(request)
    with writing(request, principal.actor) as session:
        document = records.load(session, principal, DOCUMENT, ref)
        path, name, media_type = documents.download(
            session, principal, document, version_id, request.app.state.home.files
        )
    plain = name.encode("ascii", "ignore").decode().replace('"', "") or "file"
    disposition = f"attachment; filename=\"{plain}\"; filename*=UTF-8''{quote(name)}"
    return FileResponse(
        path,
        media_type=media_type if media_type in INERT else "application/octet-stream",
        headers={**DOWNLOAD_HEADERS, "Content-Disposition": disposition},
    )
