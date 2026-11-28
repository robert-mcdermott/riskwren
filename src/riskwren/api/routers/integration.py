"""Other systems: tokens that act as a role, and webhooks told of named events. Administrators
only; a token or a webhook secret is shown once, when it is made."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import envelope, reading, writing
from riskwren.integration import drafts, results, standing, tokens, webhooks

router = APIRouter(prefix="/api/v1", tags=["integration"])


class TokenBody(BaseModel):
    name: str = Field(max_length=200, description="What will use it")
    role: str = Field(description="auditor, manager, assessor, steward, or member")
    org_unit_id: int | None = Field(
        default=None,
        description="A unit, for a manager's, an assessor's, or a steward's token (a "
        "steward's needs one)",
    )
    read_only: bool = Field(default=True, description="Whether it may only read")
    days: int = Field(description="How many days it lasts, up to 366")


class WebhookBody(BaseModel):
    name: str = Field(max_length=200)
    url: str = Field(max_length=1000, description="An https:// address")
    format: str = Field(default="plain", description="plain, ticket, or chat")
    events: list[str] = Field(
        description="*, a family such as issue.*, or names such as issue.create"
    )


class WebhookChange(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=1000)
    format: str | None = None
    events: list[str] | None = None
    active: bool | None = None


@router.get("/admin/tokens", summary="Tokens for other systems")
def list_tokens(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(tokens.list_(session, principal), roles=list(tokens.ROLES))


@router.post("/admin/tokens", status_code=201, summary="Make a token; it is shown this once")
def issue_token(request: Request, body: TokenBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row, raw = tokens.issue(session, principal, body.model_dump())
        return envelope(tokens.view(row), token=raw)


@router.post("/admin/tokens/{token_id}/revoke", summary="Withdraw a token")
def revoke_token(request: Request, token_id: int) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        return envelope(tokens.view(tokens.revoke(session, principal, token_id)))


@router.get("/admin/webhooks", summary="Webhooks, with their latest deliveries")
def list_webhooks(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(
            webhooks.list_(session, principal),
            families=[{"key": key, "label": label} for key, label in webhooks.FAMILIES.items()],
        )


@router.post("/admin/webhooks", status_code=201, summary="Register a webhook")
def create_webhook(request: Request, body: WebhookBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row, secret = webhooks.create(session, principal, body.model_dump())
        return envelope(webhooks.view(row), secret=secret)


@router.patch("/admin/webhooks/{hook_id}", summary="Change, pause, or resume a webhook")
def change_webhook(request: Request, hook_id: int, body: WebhookChange) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        values = body.model_dump(exclude_none=True)
        return envelope(webhooks.view(webhooks.update(session, principal, hook_id, values)))


@router.delete("/admin/webhooks/{hook_id}", summary="Remove a webhook")
def remove_webhook(request: Request, hook_id: int) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        webhooks.remove(session, principal, hook_id)
        return envelope({"removed": hook_id})


@router.post("/admin/webhooks/{hook_id}/test", summary="Send a test message to a webhook")
def test_webhook(request: Request, hook_id: int) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        delivery = webhooks.test(session, principal, hook_id)
        return envelope({"queued": delivery.id})


# --- Results pushed in ------------------------------------------------------------------------


class ReportBody(BaseModel):
    kind: str = Field(description="result or evidence")
    outcome: str | None = Field(
        default=None, description="For a result: passed, partial, or failed"
    )
    title: str = Field(max_length=600, description="What was checked, or what the evidence is")
    detail: str | None = Field(default=None, max_length=8000)
    url: str | None = Field(default=None, max_length=1000, description="Where to see it")
    observed_at: str | None = Field(
        default=None, description="When, with its time zone; now if left out"
    )
    scope: str | None = Field(
        default=None, description="A scope that uses the control, by reference"
    )


class DecisionBody(BaseModel):
    note: str | None = Field(default=None, max_length=4000)
    severity: str | None = Field(default=None, description="For a failure: the issue's severity")
    owner_id: int | None = Field(default=None, description="For a failure: who puts it right")
    valid_until: str | None = Field(default=None, description="For evidence: until when it counts")


def _control(session: Any, principal: Any, ref: str) -> Any:
    from riskwren.controls.service import CONTROL
    from riskwren.inventory import records

    return records.load(session, principal, CONTROL, ref)


@router.post(
    "/controls/{ref}/reported",
    status_code=201,
    summary="Report a check or a piece of evidence onto a control, from another system",
)
def report_onto(request: Request, ref: str, body: ReportBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        control = _control(session, principal, ref)
        row = results.report(session, principal, control, body.model_dump())
        return envelope(results.view(session, row))


@router.get("/controls/{ref}/reported", summary="What other systems have said of a control")
def reported_of(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(results.of_control(session, principal, _control(session, principal, ref)))


@router.get("/reported", summary="What other systems have said, waiting for a person to confirm")
def reported_waiting(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(results.waiting(session, principal))


@router.post("/reported/{report_id}/confirm", summary="Confirm a report: a failure raises an issue")
def confirm_report(request: Request, report_id: int, body: DecisionBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = results.confirm(session, principal, results.load(session, principal, report_id),
                              body.model_dump())  # fmt: skip
        return envelope(results.view(session, row))


@router.post("/reported/{report_id}/set-aside", summary="Set a report aside, saying why")
def set_report_aside(request: Request, report_id: int, body: DecisionBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = results.set_aside(session, principal, results.load(session, principal, report_id),
                                body.note)  # fmt: skip
        return envelope(results.view(session, row))


# --- A reference others can check -------------------------------------------------------------


@router.get(
    "/standing/{kind}/{ref}",
    summary="Whether a third party, a scope, or an exception is in good standing",
)
def check_standing(request: Request, kind: str, ref: str) -> dict[str, Any]:
    """Yes or no, with the reasons by kind and nothing of the record's contents. A record the
    asker may not see is not found."""
    principal = current(request)
    with reading(request) as session:
        return envelope(standing.check(session, principal, kind, ref))


# --- Drafts ------------------------------------------------------------------------------------


class DraftBody(BaseModel):
    kind: str = Field(description="risk, issue, or control")
    values: dict[str, Any] = Field(
        description="The ordinary form's fields by name, and org_unit_id; at least a name"
    )
    why: str | None = Field(default=None, max_length=2000, description="What it rests on")


class UseBody(BaseModel):
    ref: str = Field(max_length=32, description="The record made from it")


class AsideBody(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


@router.post("/drafts", status_code=201, summary="Propose a risk, an issue, or a control")
def propose_draft(request: Request, body: DraftBody) -> dict[str, Any]:
    """Kept for a person to open in the ordinary form; nothing is made until they save it. A
    token that may only read may still propose one."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = drafts.propose(session, principal, body.kind, body.values, body.why)
        return envelope(drafts.view(session, principal, row))


@router.get("/drafts", summary="Drafts waiting for a person who may make them")
def list_drafts(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(drafts.waiting(session, principal))


@router.get("/drafts/{draft_id}", summary="One draft")
def show_draft(request: Request, draft_id: int) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(drafts.view(session, principal, drafts.load(session, principal, draft_id)))


@router.post("/drafts/{draft_id}/use", summary="Mark a draft as used, naming what was made")
def use_draft(request: Request, draft_id: int, body: UseBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = drafts.used(session, principal, drafts.load(session, principal, draft_id), body.ref)
        return envelope(drafts.view(session, principal, row))


@router.post("/drafts/{draft_id}/set-aside", summary="Set a draft aside, saying why")
def set_draft_aside(request: Request, draft_id: int, body: AsideBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = drafts.set_aside(session, principal, drafts.load(session, principal, draft_id),
                               body.note)  # fmt: skip
        return envelope(drafts.view(session, principal, row))
