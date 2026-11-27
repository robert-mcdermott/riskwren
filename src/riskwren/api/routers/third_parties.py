"""Third parties as a program: their services, their tiers, their contacts, and due diligence,
including the only routes a person without an account reaches beyond signing in."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from riskwren import mail as mailing
from riskwren.access.policy import current
from riskwren.api.common import database, envelope, reading, writing
from riskwren.api.problems import problem
from riskwren.api.routers.inventory import (
    LIMIT,
    MINE,
    SORT,
    UNIT,
    LinkBody,
    OwnersBody,
    Q,
    ThingBody,
    add_record_link,
    list_records,
    record_history,
    remove_record_link,
    set_record_owners,
    show_record,
    show_record_plain,
    thing_filters,
    update_record,
    values_of,
)
from riskwren.core.errors import NotFound, PermissionDenied
from riskwren.db.models import ThirdParty
from riskwren.inventory import access, records
from riskwren.inventory.registry import THIRD_PARTY
from riskwren.thirdparty import assurance, contacts, respondent, reviews, services, tiering
from riskwren.thirdparty.reviews import REVIEW
from riskwren.thirdparty.services import SERVICE

router = APIRouter(prefix="/api/v1", tags=["third parties"])


class ServiceBody(ThingBody):
    third_party: str | None = Field(
        default=None, description="The reference of the third party that provides it"
    )


class TieringBody(BaseModel):
    answers: dict[str, Any] = Field(description="The answers, by question key")
    tier: str | None = Field(
        default=None, description="The tier to record; the one the rules give if left out"
    )
    rationale: str | None = Field(
        default=None, max_length=4000, description="Why, where the tier differs from the rules'"
    )


# --- Services -----------------------------------------------------------------------------


@router.get("/services", summary="Find services")
def list_services(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    status: str | None = None,
    kind: str | None = None,
    criticality: str | None = None,
    data_class: str | None = None,
    third_party: str | None = None,
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = SORT,
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = thing_filters(
        q, unit, status, kind, criticality, data_class, owner, mine, third_party=third_party
    )
    return list_records(request, SERVICE, filters, sort, limit, cursor)


@router.post("/services", status_code=201, summary="Add a service a third party provides")
def create_service(request: Request, body: ServiceBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        # Whoever keeps the third party may say what it provides, in its unit or their own.
        provider = services.provider_of(session, principal, body.third_party or "")
        keeps = access.can_edit(session, principal, THIRD_PARTY, provider)
        values = values_of(body)
        if keeps and values.get("org_unit_id") is None:
            values["org_unit_id"] = provider.org_unit_id
        checked = keeps and values.get("org_unit_id") == provider.org_unit_id
        if not (checked or access.can_add(principal, values.get("org_unit_id"))):
            raise PermissionDenied(
                "A service is added by those who keep its third party, or a unit's steward."
            )
        record = records.create(session, principal, SERVICE, values, checked=True)
        return envelope(records.detail(session, principal, SERVICE, record))


@router.get("/services/{ref}", summary="One service, with what it reaches and handles")
def show_service(request: Request, ref: str) -> dict[str, Any]:
    return show_record(request, SERVICE, ref)


@router.patch("/services/{ref}", summary="Change a service")
def update_service(request: Request, ref: str, body: ServiceBody) -> dict[str, Any]:
    return update_record(request, SERVICE, ref, body)


@router.put("/services/{ref}/owners", summary="Set a service's owners")
def set_service_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, SERVICE, ref, body)


@router.post("/services/{ref}/links", status_code=201, summary="Link a service to a record")
def add_service_link(request: Request, ref: str, body: LinkBody) -> dict[str, Any]:
    return add_record_link(request, SERVICE, ref, body)


@router.delete("/services/{ref}/links/{link_id}", summary="Remove a link from a service")
def remove_service_link(request: Request, ref: str, link_id: int) -> dict[str, Any]:
    return remove_record_link(request, SERVICE, ref, link_id)


@router.get("/services/{ref}/history", summary="Everything that has happened to a service")
def service_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, SERVICE, ref)


# --- Tiering ------------------------------------------------------------------------------


@router.get("/tiers", summary="The program's tiers, with what each means and its rules")
def list_tiers(request: Request) -> dict[str, Any]:
    with reading(request) as session:
        return envelope(tiering.tiers(session))


@router.get(
    "/third-parties/{ref}/tiering",
    summary="A third party's tiering: the questions, what the inventory suggests, and its tierings",
)
def show_tiering(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        third_party = records.load(session, principal, THIRD_PARTY, ref)
        return envelope(tiering.view(session, principal, third_party))


@router.post(
    "/third-parties/{ref}/tiering",
    status_code=201,
    summary="Tier a third party: the answers, and the tier with a reason if it differs",
)
def record_tiering(request: Request, ref: str, body: TieringBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        third_party = records.load(session, principal, THIRD_PARTY, ref)
        tiering.record(session, principal, third_party, body.answers, body.tier, body.rationale)
        return envelope(tiering.view(session, principal, third_party))


# --- Contacts -----------------------------------------------------------------------------


class ContactBody(BaseModel):
    name: str | None = Field(default=None, max_length=400)
    email: str | None = Field(default=None, max_length=400)
    role: str | None = Field(default=None, max_length=400, description="Their role there")
    phone: str | None = Field(default=None, max_length=100)
    status: str | None = Field(default=None, description="active, or left")


@router.post(
    "/third-parties/{ref}/contacts", status_code=201, summary="Add a contact at a third party"
)
def add_contact(request: Request, ref: str, body: ContactBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        third_party = records.load(session, principal, THIRD_PARTY, ref)
        made = contacts.add(session, principal, third_party, body.model_dump(exclude_unset=True))
        return envelope(reviews.contact_view(made))


@router.patch("/contacts/{contact_id}", summary="Change a contact, or say they have left")
def change_contact(request: Request, contact_id: int, body: ContactBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        contact = contacts.get(session, contact_id)
        party = session.get(ThirdParty, contact.third_party_id)
        if party is None or not access.can_see(session, principal, THIRD_PARTY, party):
            raise NotFound("There is no such contact.")
        contacts.change(session, principal, contact, body.model_dump(exclude_unset=True))
        return envelope(reviews.contact_view(contact))


# --- Reviews ------------------------------------------------------------------------------


class ReviewBody(BaseModel):
    version: int | None = None
    name: str | None = Field(default=None, max_length=400)
    summary: str | None = None
    questionnaire: str | None = Field(default=None, description="The key of the questionnaire")
    due_on: str | None = Field(default=None, description="When the answers are wanted")
    tags: list[str] | None = None
    restricted: bool | None = None


class SendBody(BaseModel):
    contact_id: int = Field(description="The contact to send it to")
    due_on: str | None = Field(default=None, description="When the answers are wanted")
    days: int | None = Field(default=None, description="How long the link lasts, 1 to 90 days")


class ConcludeBody(BaseModel):
    conclusion: str = Field(description="approved, conditions, or declined")
    note: str | None = Field(default=None, max_length=8000)


class NoteBody(BaseModel):
    note: str | None = Field(default=None, max_length=4000)


@router.get("/reviews", summary="Find due diligence reviews")
def list_reviews(
    request: Request,
    q: str | None = Q,
    unit: int | None = UNIT,
    status: str | None = Query(default=None, description="A status, or open for those not done"),
    third_party: str | None = None,
    late: bool = False,
    owner: int | None = None,
    mine: bool = MINE,
    sort: str = SORT,
    limit: int | None = LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    filters = {"q": q, "unit": unit, "status": status, "third_party": third_party,
               "late": late, "owner": owner, "mine": mine}  # fmt: skip
    return list_records(request, REVIEW, filters, sort, limit, cursor)


@router.post(
    "/third-parties/{ref}/reviews", status_code=201, summary="Start a due diligence review"
)
def start_review(request: Request, ref: str, body: ReviewBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        third_party = records.load(session, principal, THIRD_PARTY, ref)
        made = reviews.start(session, principal, third_party, body.model_dump(exclude_unset=True))
        return envelope(records.detail(session, principal, REVIEW, made))


@router.get("/reviews/{ref}", summary="One review, with its link, answers, and concerns")
def show_review(request: Request, ref: str) -> dict[str, Any]:
    return show_record_plain(request, REVIEW, ref)


@router.patch("/reviews/{ref}", summary="Change a review not yet sent")
def update_review(request: Request, ref: str, body: ReviewBody) -> dict[str, Any]:
    return update_record(request, REVIEW, ref, body)


@router.put("/reviews/{ref}/owners", summary="Set a review's owners")
def set_review_owners(request: Request, ref: str, body: OwnersBody) -> dict[str, Any]:
    return set_record_owners(request, REVIEW, ref, body)


@router.get("/reviews/{ref}/history", summary="Everything that has happened to a review")
def review_history(request: Request, ref: str) -> dict[str, Any]:
    return record_history(request, REVIEW, ref)


def _base_url(request: Request) -> str:
    configured = request.app.state.config.server.base_url
    return (configured or str(request.base_url)).rstrip("/")


@router.post(
    "/reviews/{ref}/send", summary="Send the questionnaire to a contact through a new link"
)
def send_review(request: Request, ref: str, body: SendBody) -> dict[str, Any]:
    principal = current(request)
    config = request.app.state.config
    with writing(request, principal.actor) as session:
        review = records.load(session, principal, REVIEW, ref)
        token = reviews.send(session, principal, review, contact_id=body.contact_id,
                             due_on=body.due_on, days=body.days)  # fmt: skip
        url = f"{_base_url(request)}/respond#{token}"
        emailed = mailing.queue_link(session, config, review, url) if config.mail.enabled else False
        detail = records.detail(session, principal, REVIEW, review)
    # The address is shown this once, to whoever sent it. Only its digest is kept.
    return envelope(detail, link={"url": url, "emailed": emailed})


@router.post("/reviews/{ref}/withdraw", summary="Withdraw the link, so it no longer opens anything")
def withdraw_link(request: Request, ref: str) -> dict[str, Any]:
    return _act(request, ref, reviews.withdraw)


@router.post("/reviews/{ref}/conclude", summary="Record what was concluded from the answers")
def conclude_review(request: Request, ref: str, body: ConcludeBody) -> dict[str, Any]:
    return _act(request, ref, lambda s, p, r: reviews.conclude(s, p, r, body.conclusion, body.note))


@router.post("/reviews/{ref}/cancel", summary="Cancel a review not yet answered")
def cancel_review(request: Request, ref: str, body: NoteBody) -> dict[str, Any]:
    return _act(request, ref, lambda s, p, r: reviews.cancel(s, p, r, body.note))


def _act(request: Request, ref: str, act: Any) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        review = records.load(session, principal, REVIEW, ref)
        act(session, principal, review)
        return envelope(records.detail(session, principal, REVIEW, review))


# --- Answering through a link -------------------------------------------------------------
# The only routes a person without an account reaches beyond signing in. Each finds its link
# by the token in the header, and reaches nothing but that link's questionnaire.


class AnswersBody(BaseModel):
    answers: dict[str, Any] = Field(description="The answers, by question key")


def _client(request: Request) -> str:
    return request.client.host if request.client else ""


NO_STORE = {"Cache-Control": "no-store"}


def _refusal(request: Request, refused: respondent.LinkRefused) -> JSONResponse:
    # Gone, for a link that once worked; not found, for anything else.
    status = 404 if refused.reason is None else 410
    answer = problem(status, str(refused), instance=request.url.path)
    answer.headers.update(NO_STORE)
    return answer


def _guessing(request: Request) -> bool:
    """Too many unknown links from this address lately. They are counted as wrong
    passwords are."""
    from riskwren.auth import sessions as signins

    with reading(request) as session:
        return signins.throttled(session, f"link:{_client(request)}", limit=signins.THROTTLE_WIDE)


def _note_guess(request: Request) -> None:
    from riskwren.auth import sessions as signins

    with database(request).bookkeeping() as books:
        signins.note_failure(books, f"link:{_client(request)}")


def _token(request: Request) -> str | None:
    return request.headers.get(respondent.HEADER)


@router.get(
    "/respond", summary="What the holder of a link is asked (no account; the link in a header)"
)
def respond_view(request: Request) -> Any:
    if _guessing(request):
        return problem(429, "Too many attempts. Wait a few minutes and try again.",
                       instance=request.url.path)  # fmt: skip
    try:
        with reading(request) as session:
            found = respondent.view(session, respondent.find(session, _token(request)))
    except respondent.LinkRefused as refused:
        if refused.reason is None:
            _note_guess(request)
        return _refusal(request, refused)
    return JSONResponse(jsonable_encoder(envelope(found)), headers=NO_STORE)


@router.put(
    "/respond", summary="Save the answers to finish later (no account; the link in a header)"
)
def respond_save(request: Request, body: AnswersBody) -> Any:
    return _respond(request, body, submit=False)


@router.post("/respond/submit", summary="Send the answers (no account; the link in a header)")
def respond_submit(request: Request, body: AnswersBody) -> Any:
    return _respond(request, body, submit=True)


def _respond(request: Request, body: AnswersBody, *, submit: bool) -> Any:
    if _guessing(request):
        return problem(429, "Too many attempts. Wait a few minutes and try again.",
                       instance=request.url.path)  # fmt: skip
    token = _token(request)
    try:
        with reading(request) as session:
            actor = respondent.actor_for(session, respondent.find(session, token))
        # Found again inside the change, so a link withdrawn in between is refused.
        with database(request).write(actor) as session:
            done = respondent.save(session, respondent.find(session, token), body.answers,
                                   submit=submit)  # fmt: skip
    except respondent.LinkRefused as refused:
        if refused.reason is None:
            _note_guess(request)
        return _refusal(request, refused)
    return JSONResponse(jsonable_encoder(envelope(done)), headers=NO_STORE)


# --- Assurance documents ------------------------------------------------------------------


class ReportBody(BaseModel):
    name: str | None = Field(default=None, max_length=400)
    summary: str | None = None
    url: str | None = Field(default=None, description="Where it is kept, if not sent as a file")
    collected_on: str | None = Field(default=None, description="When it was received")
    covers_from: str | None = Field(default=None, description="The period it covers, from")
    covers_to: str | None = None
    valid_until: str | None = Field(default=None, description="When it stops counting")
    data_class: str | None = None


class AssuranceReviewBody(BaseModel):
    kind: str = Field(description="soc2_type2, iso27001, hitrust, pentest, and the like")
    issuer: str | None = Field(default=None, max_length=400)
    opinion: str | None = Field(default=None, description="unqualified, qualified, adverse, none")
    services: list[str] = Field(default_factory=list, description="The services it covers")
    carve_outs: str | None = Field(default=None, max_length=8000)
    exceptions: list[dict[str, Any]] = Field(default_factory=list)
    responsibilities: list[dict[str, Any]] = Field(
        default_factory=list, description="Each with text, control (a reference), and status"
    )
    reliance: str = Field(description="relies, partly, or cannot")
    note: str | None = Field(default=None, max_length=8000)


@router.get(
    "/assurance-kinds", summary="The kinds of report, opinions, and judgments a review uses"
)
def assurance_kinds(request: Request) -> dict[str, Any]:
    return envelope({
        "kinds": assurance.KINDS, "opinions": assurance.OPINIONS,
        "reliance": assurance.RELIANCE, "states": assurance.RESPONSIBILITY_STATES,
    })  # fmt: skip


@router.get("/third-parties/{ref}/assurance", summary="A third party's reports and certificates")
def show_assurance(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        third_party = records.load(session, principal, THIRD_PARTY, ref)
        return envelope({
            "documents": assurance.documents_of(session, principal, third_party),
            "standing": assurance.standing(session, third_party),
            "can_add": assurance.may_review(session, principal, third_party),
        })  # fmt: skip


@router.post("/third-parties/{ref}/assurance", status_code=201,
             summary="Add a report or certificate about a third party")  # fmt: skip
def add_report(request: Request, ref: str, body: ReportBody) -> dict[str, Any]:
    from riskwren.compliance.evidence import EVIDENCE

    principal = current(request)
    with writing(request, principal.actor) as session:
        third_party = records.load(session, principal, THIRD_PARTY, ref)
        item = assurance.add(session, principal, third_party, body.model_dump(exclude_unset=True))
        return envelope(records.detail(session, principal, EVIDENCE, item))


@router.post("/third-parties/{ref}/assurance/{document}/reviews", status_code=201,
             summary="Review a report: what it covers, found, and leaves to us")  # fmt: skip
def review_report(
    request: Request, ref: str, document: str, body: AssuranceReviewBody
) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        third_party = records.load(session, principal, THIRD_PARTY, ref)
        item = assurance.find_document(session, document)
        made = assurance.record(session, principal, item, third_party, body.model_dump())
        return envelope(assurance.view(session, principal, made, third_party))


@router.post(
    "/respond/files", summary="Send a report with the answers (no account; the link in a header)"
)
async def respond_file(
    request: Request,
    name: str | None = Query(default=None, description="The file's name", max_length=200),
) -> Any:
    from starlette.concurrency import run_in_threadpool

    data = await request.body()

    def keep() -> Any:
        if _guessing(request):
            return problem(429, "Too many attempts. Wait a few minutes and try again.",
                           instance=request.url.path)  # fmt: skip
        token = _token(request)
        try:
            with reading(request) as session:
                actor = respondent.actor_for(session, respondent.find(session, token))
            with database(request).write(actor) as session:
                done = respondent.attach(session, respondent.find(session, token),
                                         request.app.state.home.files, data, name)  # fmt: skip
        except respondent.LinkRefused as refused:
            if refused.reason is None:
                _note_guess(request)
            return _refusal(request, refused)
        return JSONResponse(jsonable_encoder(envelope(done)), status_code=201, headers=NO_STORE)

    return await run_in_threadpool(keep)
