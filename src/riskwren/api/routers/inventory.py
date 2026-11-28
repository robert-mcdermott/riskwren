"""The inventory: processes, systems, and third parties."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import (
    clamp_limit,
    decode_cursor,
    encode_cursor,
    envelope,
    reading,
    writing,
)
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.events import audit
from riskwren.inventory import access, history, links, records
from riskwren.inventory.registry import (
    INFORMATION,
    PROCESS,
    SITE,
    SYSTEM,
    THIRD_PARTY,
    RecordType,
    find_any,
)
from riskwren.program import settings, vocab

router = APIRouter(prefix="/api/v1", tags=["inventory"])


class ExternalRefBody(BaseModel):
    """What a record is called in another system."""

    system: str = Field(description="From the external_systems vocabulary")
    value: str = Field(max_length=200)


class ThingBody(BaseModel):
    """What every process, system, and third party has. On a change, send only what changes,
    with the ``version`` you were editing."""

    version: int | None = None
    name: str | None = Field(default=None, max_length=400)
    summary: str | None = None
    org_unit_id: int | None = None
    criticality: str | None = None
    data_class: str | None = None
    status: str | None = None
    tags: list[str] | None = None
    restricted: bool | None = None
    kind: str | None = None
    external_refs: list[ExternalRefBody] | None = None


class ProcessBody(ThingBody):
    purpose: str | None = None


class SystemBody(ThingBody):
    hosting: str | None = None
    lifecycle: str | None = None
    url: str | None = None


class ThirdPartyBody(ThingBody):
    website: str | None = None
    notes: str | None = None


class SiteBody(ThingBody):
    address: str | None = Field(default=None, max_length=300)


class InformationBody(ThingBody):
    held_in: str | None = Field(default=None, description="The systems and places it is kept")
    shared_with: str | None = None
    agreement: str | None = Field(default=None, description="What it is held or shared under")


class OwnersBody(BaseModel):
    owners: list[dict[str, Any]] = Field(description="Each with an account_id and a kind")


class LinkBody(BaseModel):
    relation: str = Field(description="The key of a kind of link, such as relies_on")
    to: str = Field(description="The reference of the record it reaches, such as SYS-0003")
    note: str | None = None


class VisibilityBody(BaseModel):
    visibility: str


@router.get("/vocabularies", summary="The lists of values records choose from")
def vocabularies(request: Request) -> dict[str, Any]:
    from riskwren.compliance import issues  # the clock each severity sets, beside its meaning

    with reading(request) as session:
        found = vocab.all_(session)
        found["issue_severities"] = [
            {**item, "due_days": issues.due_days(session, item["key"])}
            if item["key"] in issues.DUE_DAYS
            else item
            for item in found["issue_severities"]
        ]
        return envelope(found)


class VocabularyBody(BaseModel):
    items: list[dict[str, Any]] = Field(
        description="Every value, in order: key, label, description, and retired"
    )


@router.get("/admin/vocabularies", summary="Every vocabulary, with what may be changed in it")
def describe_vocabularies(request: Request) -> dict[str, Any]:
    with reading(request) as session:
        return envelope(vocab.describe(session))


@router.put("/vocabularies/{name}", summary="Rename, reorder, add to, or retire a vocabulary")
def save_vocabulary(request: Request, name: str, body: VocabularyBody) -> dict[str, Any]:
    """A value's key never changes, so renaming one never rewrites a record. A value in use
    is retired, not removed: records keep it and new ones cannot choose it."""
    principal = current(request)
    if not principal.configures:
        raise PermissionDenied("Only those who run the program can change a vocabulary.")
    with writing(request, principal.actor) as session:
        with audit.operation(session, "vocabulary.edit", vocabulary=name):
            items = vocab.edit(session, name, body.items)
            audit.record(session, "vocabulary.edit", subject_kind="program",
                         changes={name: [item["key"] for item in items]})  # fmt: skip
        return envelope(items)


@router.get("/admin/visibility", summary="How much of the register everyone can see")
def show_visibility(request: Request) -> dict[str, Any]:
    with reading(request) as session:
        return envelope({"visibility": access.visibility(session), "choices": access.VISIBILITIES})


@router.put("/admin/visibility", summary="Change how much of the register everyone can see")
def save_visibility(request: Request, body: VisibilityBody) -> dict[str, Any]:
    principal = current(request)
    if body.visibility not in access.VISIBILITIES:
        raise Invalid(
            "That is not one of the choices.",
            {"visibility": f"Use one of: {', '.join(access.VISIBILITIES)}."},
        )
    with writing(request, principal.actor) as session:
        settings.put(session, access.VISIBILITY_SETTING, body.visibility)
        return envelope({"visibility": body.visibility, "choices": access.VISIBILITIES})


# --- What every record type's routes do ---------------------------------------------------


def values_of(body: BaseModel) -> dict[str, Any]:
    values = body.model_dump(exclude_unset=True)
    values.pop("version", None)
    return values


def list_records(
    request: Request,
    record_type: RecordType,
    filters: dict[str, Any],
    sort: str,
    limit: int | None,
    cursor: str | None,
) -> dict[str, Any]:
    principal = current(request)
    size = clamp_limit(limit)
    offset = int((decode_cursor(cursor) or {}).get("offset", 0))
    # Every list can be cut to the records missing something expected of them.
    filters = {**filters, "missing": request.query_params.get("missing")}
    with reading(request) as session:
        rows, total = records.search(
            session, principal, record_type, filters, sort=sort, limit=size, offset=offset
        )
        data = records.cards(session, record_type, rows)
    return envelope(data, **paging(total, offset, size, len(rows)))


def paging(total: int, offset: int, size: int, shown: int) -> dict[str, Any]:
    """Where a page sits in its list, and the cursors of the pages either side."""
    following = offset + shown
    return {
        "total": total,
        "offset": offset,
        "next_cursor": encode_cursor({"offset": following}) if following < total else None,
        "prev_cursor": encode_cursor({"offset": max(0, offset - size)}) if offset > 0 else None,
    }


def show_record(request: Request, record_type: RecordType, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        record = records.load(session, principal, record_type, ref)
        data = records.detail(session, principal, record_type, record)
        data["links"] = links.of(session, principal, record_type, record)
        return envelope(data)


def show_record_plain(request: Request, record_type: RecordType, ref: str) -> dict[str, Any]:
    """One record of a type that is not joined to others by named links."""
    principal = current(request)
    with reading(request) as session:
        record = records.load(session, principal, record_type, ref)
        return envelope(records.detail(session, principal, record_type, record))


def create_record(request: Request, record_type: RecordType, body: BaseModel) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        record = records.create(session, principal, record_type, values_of(body))
        return envelope(records.detail(session, principal, record_type, record))


def update_record(request: Request, record_type: RecordType, ref: str, body: Any) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        record = records.load(session, principal, record_type, ref)
        records.update(
            session, principal, record_type, record, values_of(body), version=body.version
        )
        return envelope(records.detail(session, principal, record_type, record))


def set_record_owners(
    request: Request, record_type: RecordType, ref: str, body: OwnersBody
) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        record = records.load(session, principal, record_type, ref)
        records.set_owners(session, principal, record_type, record, body.owners)
        session.flush()
        return envelope(records.detail(session, principal, record_type, record))


def add_record_link(
    request: Request, record_type: RecordType, ref: str, body: LinkBody
) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        record = records.load(session, principal, record_type, ref)
        to_type, to_record = find_any(session, body.to)
        links.add(
            session, principal, record_type, record, body.relation, to_type, to_record,
            note=body.note,
        )  # fmt: skip
        return envelope(links.of(session, principal, record_type, record))


def remove_record_link(
    request: Request, record_type: RecordType, ref: str, link_id: int
) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        record = records.load(session, principal, record_type, ref)
        links.remove(session, principal, record_type, record, link_id)
        session.flush()
        return envelope(links.of(session, principal, record_type, record))


def record_history(request: Request, record_type: RecordType, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        record = records.load(session, principal, record_type, ref)
        return envelope(history.for_record(session, record_type, record))


def thing_filters(
    q: str | None,
    unit: int | None,
    status: str | None,
    kind: str | None,
    criticality: str | None,
    data_class: str | None,
    owner: int | None,
    mine: bool,
    **more: Any,
) -> dict[str, Any]:
    return {
        "q": q, "unit": unit, "status": status, "kind": kind, "criticality": criticality,
        "data_class": data_class, "owner": owner, "mine": mine, **more,
    }  # fmt: skip


Q = Query(default=None, description="Words to look for in the name, reference, or summary")
UNIT = Query(default=None, description="A unit's id; includes every unit beneath it")
SORT = Query(default="-updated_at", description="A field name; start with - for descending")
LIMIT = Query(default=None, ge=1, le=200)
MINE = Query(default=False, description="Only records I am named on")

# --- Processes ----------------------------------------------------------------------------


@router.get("/processes", summary="Find processes")
def list_processes(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    status: str | None = None,
    kind: str | None = None,
    criticality: str | None = None,
    data_class: str | None = None,
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = SORT,
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = thing_filters(q, unit, status, kind, criticality, data_class, owner, mine)
    return list_records(request, PROCESS, filters, sort, limit, cursor)


@router.post("/processes", status_code=201, summary="Add a process")
def create_process(request: Request, body: ProcessBody) -> dict[str, Any]:
    return create_record(request, PROCESS, body)


@router.get("/processes/{ref}", summary="One process, with its owners and links")
def show_process(request: Request, ref: str) -> dict[str, Any]:
    return show_record(request, PROCESS, ref)


@router.patch("/processes/{ref}", summary="Change a process")
def update_process(request: Request, ref: str, body: ProcessBody) -> dict[str, Any]:
    return update_record(request, PROCESS, ref, body)


@router.put("/processes/{ref}/owners", summary="Set a process's owners")
def set_process_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, PROCESS, ref, body)


@router.post("/processes/{ref}/links", status_code=201, summary="Link a process to a record")
def add_process_link(request: Request, ref: str, body: LinkBody) -> dict[str, Any]:
    return add_record_link(request, PROCESS, ref, body)


@router.delete("/processes/{ref}/links/{link_id}", summary="Remove a link from a process")
def remove_process_link(request: Request, ref: str, link_id: int) -> dict[str, Any]:
    return remove_record_link(request, PROCESS, ref, link_id)


@router.get("/processes/{ref}/history", summary="Everything that has happened to a process")
def process_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, PROCESS, ref)


# --- Systems ------------------------------------------------------------------------------


@router.get("/systems", summary="Find systems")
def list_systems(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    status: str | None = None,
    kind: str | None = None,
    criticality: str | None = None,
    data_class: str | None = None,
    hosting: str | None = None,
    lifecycle: str | None = None,
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = SORT,
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = thing_filters(
        q, unit, status, kind, criticality, data_class, owner, mine,
        hosting=hosting, lifecycle=lifecycle,
    )  # fmt: skip
    return list_records(request, SYSTEM, filters, sort, limit, cursor)


@router.post("/systems", status_code=201, summary="Add a system")
def create_system(request: Request, body: SystemBody) -> dict[str, Any]:
    return create_record(request, SYSTEM, body)


@router.get("/systems/{ref}", summary="One system, with its owners and links")
def show_system(request: Request, ref: str) -> dict[str, Any]:
    return show_record(request, SYSTEM, ref)


@router.patch("/systems/{ref}", summary="Change a system")
def update_system(request: Request, ref: str, body: SystemBody) -> dict[str, Any]:
    return update_record(request, SYSTEM, ref, body)


@router.put("/systems/{ref}/owners", summary="Set a system's owners")
def set_system_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, SYSTEM, ref, body)


@router.post("/systems/{ref}/links", status_code=201, summary="Link a system to a record")
def add_system_link(request: Request, ref: str, body: LinkBody) -> dict[str, Any]:
    return add_record_link(request, SYSTEM, ref, body)


@router.delete("/systems/{ref}/links/{link_id}", summary="Remove a link from a system")
def remove_system_link(request: Request, ref: str, link_id: int) -> dict[str, Any]:
    return remove_record_link(request, SYSTEM, ref, link_id)


@router.get("/systems/{ref}/history", summary="Everything that has happened to a system")
def system_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, SYSTEM, ref)


# --- Sites --------------------------------------------------------------------------------


@router.get("/sites", summary="Find sites")
def list_sites(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    status: str | None = None,
    kind: str | None = None,
    criticality: str | None = None,
    data_class: str | None = None,
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = SORT,
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = thing_filters(q, unit, status, kind, criticality, data_class, owner, mine)
    return list_records(request, SITE, filters, sort, limit, cursor)


@router.post("/sites", status_code=201, summary="Add a site")
def create_site(request: Request, body: SiteBody) -> dict[str, Any]:
    return create_record(request, SITE, body)


@router.get("/sites/{ref}", summary="One site, with its owners and links")
def show_site(request: Request, ref: str) -> dict[str, Any]:
    return show_record(request, SITE, ref)


@router.patch("/sites/{ref}", summary="Change a site")
def update_site(request: Request, ref: str, body: SiteBody) -> dict[str, Any]:
    return update_record(request, SITE, ref, body)


@router.put("/sites/{ref}/owners", summary="Set a site's owners")
def set_site_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, SITE, ref, body)


@router.post("/sites/{ref}/links", status_code=201, summary="Link a site to a record")
def add_site_link(request: Request, ref: str, body: LinkBody) -> dict[str, Any]:
    return add_record_link(request, SITE, ref, body)


@router.delete("/sites/{ref}/links/{link_id}", summary="Remove a link from a site")
def remove_site_link(request: Request, ref: str, link_id: int) -> dict[str, Any]:
    return remove_record_link(request, SITE, ref, link_id)


@router.get("/sites/{ref}/history", summary="Everything that has happened to a site")
def site_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, SITE, ref)


# --- Third parties ------------------------------------------------------------------------


@router.get("/third-parties", summary="Find third parties")
def list_third_parties(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    status: str | None = None,
    kind: str | None = None,
    criticality: str | None = None,
    data_class: str | None = None,
    tier: str | None = Query(default=None, description="A tier's key, or none for untiered"),
    review: str | None = Query(default=None, description="due: overdue; soon: within a month"),
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = SORT,
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = thing_filters(
        q, unit, status, kind, criticality, data_class, owner, mine, tier=tier, review=review
    )
    return list_records(request, THIRD_PARTY, filters, sort, limit, cursor)


@router.post("/third-parties", status_code=201, summary="Add a third party")
def create_third_party(request: Request, body: ThirdPartyBody) -> dict[str, Any]:
    return create_record(request, THIRD_PARTY, body)


@router.get("/third-parties/{ref}", summary="One third party, with its owners and links")
def show_third_party(request: Request, ref: str) -> dict[str, Any]:
    return show_record(request, THIRD_PARTY, ref)


@router.patch("/third-parties/{ref}", summary="Change a third party")
def update_third_party(request: Request, ref: str, body: ThirdPartyBody) -> dict[str, Any]:
    return update_record(request, THIRD_PARTY, ref, body)


@router.put("/third-parties/{ref}/owners", summary="Set a third party's owners")
def set_third_party_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, THIRD_PARTY, ref, body)


@router.post(
    "/third-parties/{ref}/links", status_code=201, summary="Link a third party to a record"
)
def add_third_party_link(request: Request, ref: str, body: LinkBody) -> dict[str, Any]:
    return add_record_link(request, THIRD_PARTY, ref, body)


@router.delete("/third-parties/{ref}/links/{link_id}", summary="Remove a link from a third party")
def remove_third_party_link(request: Request, ref: str, link_id: int) -> dict[str, Any]:
    return remove_record_link(request, THIRD_PARTY, ref, link_id)


@router.get("/third-parties/{ref}/history", summary="Everything that has happened to a third party")
def third_party_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, THIRD_PARTY, ref)


@router.get("/information", summary="Find information assets")
def list_information(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    status: str | None = None,
    kind: str | None = None,
    criticality: str | None = None,
    data_class: str | None = None,
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = SORT,
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = thing_filters(q, unit, status, kind, criticality, data_class, owner, mine)
    return list_records(request, INFORMATION, filters, sort, limit, cursor)


@router.post("/information", status_code=201, summary="Add an information asset")
def create_information(request: Request, body: InformationBody) -> dict[str, Any]:
    return create_record(request, INFORMATION, body)


@router.get("/information/{ref}", summary="One information asset, with its owners and links")
def show_information(request: Request, ref: str) -> dict[str, Any]:
    return show_record(request, INFORMATION, ref)


@router.patch("/information/{ref}", summary="Change an information asset")
def update_information(request: Request, ref: str, body: InformationBody) -> dict[str, Any]:
    return update_record(request, INFORMATION, ref, body)


@router.put("/information/{ref}/owners", summary="Set a information asset's owners")
def set_information_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, INFORMATION, ref, body)


@router.post(
    "/information/{ref}/links", status_code=201, summary="Link an information asset to a record"
)
def add_information_link(request: Request, ref: str, body: LinkBody) -> dict[str, Any]:
    return add_record_link(request, INFORMATION, ref, body)


@router.delete(
    "/information/{ref}/links/{link_id}", summary="Remove a link from an information asset"
)
def remove_information_link(request: Request, ref: str, link_id: int) -> dict[str, Any]:
    return remove_record_link(request, INFORMATION, ref, link_id)


@router.get(
    "/information/{ref}/history", summary="Everything that has happened to an information asset"
)
def information_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, INFORMATION, ref)
