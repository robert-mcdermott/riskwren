"""Getting lists out, and records in: exports of every list, and imports from a spreadsheet."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from riskwren.access.policy import current
from riskwren.api.common import envelope, writing
from riskwren.api.routers.people import _csv
from riskwren.core.errors import Invalid
from riskwren.inventory import imports
from riskwren.reporting import exports

router = APIRouter(prefix="/api/v1", tags=["import and export"])
# An export is only ever a download: it is never drawn in the app's origin.
DOWNLOAD_HEADERS = {"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"}
NOT_FILTERS = {"format", "limit", "cursor"}


@router.get(
    "/exports/{kind}",
    summary="A list, as filtered, as CSV or JSON",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}, "application/json": {}}}},
)
def export_list(
    request: Request,
    kind: str,
    format: str = Query(default="csv", description="csv or json"),
) -> Response:
    """``kind`` is a list's own name: ``processes``, ``systems``, ``third-parties``,
    ``information``, ``risks``, ``controls``, ``scopes``, ``evidence``, ``assessments``,
    ``issues``, ``exceptions``, ``actions``, ``plans``, ``acceptances``, ``requirements``
    (with ``framework``), or ``statement`` (with ``scope`` and ``framework``). Every other
    parameter is a filter, the same ones that list takes. What comes back is what the asker
    may see, and taking it is recorded in the history."""
    principal = current(request)
    filters = {key: value for key, value in request.query_params.items() if key not in NOT_FILTERS}
    with writing(request, principal.actor) as session:
        text, media_type, name = exports.export(session, principal, kind, format, filters)
    return Response(
        content=text.encode("utf-8"),
        media_type=media_type,
        headers={**DOWNLOAD_HEADERS, "Content-Disposition": f'attachment; filename="{name}"'},
    )


def _mapping(given: str | None) -> dict[str, str | None] | None:
    if not given:
        return None
    try:
        found = json.loads(given)
    except ValueError:
        found = None
    if not isinstance(found, dict) or not all(
        isinstance(key, str) and (value is None or isinstance(value, str))
        for key, value in found.items()
    ):
        raise Invalid(
            "The columns were not understood.",
            {"mapping": "Send a JSON object of field names to column headings."},
        )
    return found


MAPPING = Query(
    default=None,
    description="A JSON object saying which column holds each field; the rest are guessed",
)


def _columns(request: Request, text: str, path: str) -> dict[str, Any]:
    return envelope(imports.columns(imports.record_type_for(path), text))


def _records(
    request: Request, text: str, path: str, mapping: str | None, dry_run: bool
) -> dict[str, Any]:
    principal = current(request)
    record_type = imports.record_type_for(path)
    with writing(request, principal.actor) as session:
        report = imports.run(
            session, principal, record_type, text, mapping=_mapping(mapping), dry_run=dry_run
        )
        if not report.applied:
            session.rollback()  # a dry run, or a file with problems, changes nothing
        return envelope(report.to_json())


@router.post(
    "/imports/records/{path}/columns", summary="Read a CSV's columns and match them to fields"
)
async def import_columns(request: Request, path: str) -> dict[str, Any]:
    """Send the CSV as the request body. Nothing is checked or changed: the answer says what
    columns the file has, and which field each is taken for."""
    return await run_in_threadpool(_columns, request, await _csv(request), path)


@router.post("/imports/records/{path}", summary="Import records from CSV")
async def import_records(
    request: Request, path: str, dry_run: bool = True, mapping: str | None = MAPPING
) -> dict[str, Any]:
    """``path`` is ``processes``, ``systems``, ``third-parties``, ``information``, ``risks``,
    or ``controls``. Send the CSV as the request body. With ``dry_run`` (the default) every
    row is checked and nothing is changed. Nothing is added unless every row can be."""
    return await run_in_threadpool(_records, request, await _csv(request), path, mapping, dry_run)


def _requirements(
    request: Request, text: str, key: str, mapping: str | None, dry_run: bool
) -> dict[str, Any]:
    from riskwren.compliance import frameworks

    principal = current(request)
    with writing(request, principal.actor) as session:
        framework = frameworks.by_key(session, key)
        report = imports.requirements(
            session, principal, framework, text, mapping=_mapping(mapping), dry_run=dry_run
        )
        if not report.applied:
            session.rollback()
        return envelope(report.to_json())


@router.post(
    "/imports/requirements/{key}/columns",
    summary="Read a CSV's columns and match them to a requirement's fields",
)
async def requirement_columns(request: Request, key: str) -> dict[str, Any]:
    text = await _csv(request)
    return await run_in_threadpool(lambda: envelope(imports.requirement_columns(text)))


@router.post("/imports/requirements/{key}", summary="Import a framework's requirements from CSV")
async def import_requirements(
    request: Request, key: str, dry_run: bool = True, mapping: str | None = MAPPING
) -> dict[str, Any]:
    """For one of the organization's own frameworks. Columns: a code, and optionally a title,
    the text, and the code of the requirement each sits under."""
    return await run_in_threadpool(
        _requirements, request, await _csv(request), key, mapping, dry_run
    )
