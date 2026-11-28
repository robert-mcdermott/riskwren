"""The assistant's routes (INT-07), mounted only when ``[assistant]`` turns it on. While it is
off they do not exist, and nothing of the assistant is in the app."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from riskwren.access.policy import current
from riskwren.api.common import envelope
from riskwren.api.problems import problem
from riskwren.assistant import providers, service

router = APIRouter(prefix="/api/v1", tags=["assistant"])


class SummaryBody(BaseModel):
    ref: str = Field(max_length=32, description="The record to summarize")


class DraftRiskBody(BaseModel):
    description: str = Field(max_length=4000, description="What could go wrong, in your words")
    org_unit_id: int | None = Field(default=None, description="The unit it belongs to")


async def _ask(request: Request, task: str, **asked: Any) -> Any:
    principal = current(request)
    try:
        found = await service.ask(request.app, str(request.base_url), service.credentials(
            request.headers), principal, task, **asked)  # fmt: skip
    except service.AssistantRefused as said:
        return problem(429, str(said), instance=request.url.path)
    except providers.ProviderError as said:
        return problem(502, f"The assistant could not answer: {said}", instance=request.url.path)
    return envelope(found)


@router.post("/assistant/summary", summary="A summary of a record, by the assistant")
async def summarize(request: Request, body: SummaryBody) -> Any:
    """Written from what you may see, through the same tools the tool server offers, and from
    no data class the configuration keeps back. It is not saved on the record."""
    ref = body.ref.strip().upper()
    if not ref or len(ref) > 32 or not all(ch.isalnum() or ch == "-" for ch in ref):
        return problem(422, "Give a reference such as RSK-0042.", instance=request.url.path)
    return await _ask(request, "summarize", ref=ref)


@router.post("/assistant/draft-risk", summary="A risk drafted by the assistant from your words")
async def draft_risk(request: Request, body: DraftRiskBody) -> Any:
    """The assistant searches for a risk that already says the same, and otherwise keeps a
    draft for you to open in the ordinary form. Nothing is made until a person saves it."""
    text = body.description.strip()
    if len(text) < 20:
        return problem(422, "Say a little more: a sentence or two about what could go wrong.",
                       instance=request.url.path)  # fmt: skip
    unit = None
    if body.org_unit_id is not None:
        from riskwren.api.common import reading
        from riskwren.db.models import OrgUnit

        with reading(request) as session:
            row = session.get(OrgUnit, body.org_unit_id)
            unit = {"id": row.id, "name": row.name} if row else None
    return await _ask(request, "draft_risk", text=text, unit=unit)


@router.get("/admin/assistant", summary="How the assistant is set up, and its log")
async def assistant_settings(request: Request) -> Any:
    config = request.app.state.config.assistant
    entries = await run_in_threadpool(service.log, request.app.state.db)
    return envelope({
        "provider": config.provider, "model": config.model, "url": config.base_url,
        "key_env": config.key_env or None, "send": sorted(config.classes),
        "daily_limit": config.daily_limit, "time_limit_seconds": config.time_limit_seconds,
        "log": entries})  # fmt: skip


@router.post("/admin/assistant/check", summary="Check that the provider answers")
async def check_assistant(request: Request) -> Any:
    return await _ask(request, "check")
