"""Other systems: tokens that act as a role, and webhooks told of named events. Administrators
only; a token or a webhook secret is shown once, when it is made."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import envelope, reading, writing
from riskwren.integration import tokens, webhooks

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
    events: list[str] = Field(
        description="*, a family such as issue.*, or names such as issue.close"
    )


class WebhookChange(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=1000)
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
