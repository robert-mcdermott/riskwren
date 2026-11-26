"""Questionnaires: the documents, their versions, and answers to them."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import envelope, reading, writing
from riskwren.oversight import questionnaires

router = APIRouter(prefix="/api/v1", tags=["questionnaires"])


class QuestionnaireIn(BaseModel):
    key: str = Field(max_length=60)
    title: str = Field(max_length=200)
    summary: str | None = Field(default=None, max_length=2000)
    purpose: str | None = Field(default=None, max_length=24)
    document: dict[str, Any]


class QuestionnaireChange(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=2000)
    purpose: str | None = Field(default=None, max_length=24)
    status: str | None = Field(default=None, max_length=16)
    document: dict[str, Any] | None = None
    note: str | None = Field(default=None, max_length=1000)


class DocumentIn(BaseModel):
    document: dict[str, Any]
    answers: dict[str, Any] = Field(default_factory=dict)


class AnswersIn(BaseModel):
    answers: dict[str, Any]
    complete: bool = True
    response_id: int | None = None


@router.get("/questionnaires", summary="The questionnaires on record")
def list_(request: Request, purpose: str | None = None) -> dict[str, Any]:
    with reading(request) as session:
        return envelope(
            {
                "questionnaires": [
                    questionnaires.summary(row)
                    for row in questionnaires.all_(session, purpose=purpose)
                ],
                "purposes": list(questionnaires.PURPOSES),
                "types": list(questionnaires.TYPES),
            }
        )


@router.post("/questionnaires", summary="Add a questionnaire", status_code=201)
def create(request: Request, body: QuestionnaireIn) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = questionnaires.create(session, principal, body.model_dump())
        return envelope(questionnaires.view(session, row))


@router.post("/questionnaires/check", summary="Check a questionnaire without saving it")
def check(request: Request, body: DocumentIn) -> dict[str, Any]:
    """Says everything wrong with a document and, if nothing is, which questions the given
    answers would show. Nothing is saved."""
    found = questionnaires.problems(body.document)
    if found:
        return envelope({"problems": found, "showing": None})
    keys, kept = questionnaires.showing(body.document, body.answers)
    return envelope({"problems": [], "showing": keys, "kept": kept})


@router.get("/questionnaires/{key}", summary="One questionnaire, as it is or as it was")
def show(request: Request, key: str, version: int | None = None) -> dict[str, Any]:
    with reading(request) as session:
        return envelope(questionnaires.view(session, questionnaires.find(session, key), version))


@router.patch("/questionnaires/{key}", summary="Change a questionnaire")
def change(request: Request, key: str, body: QuestionnaireChange) -> dict[str, Any]:
    """A changed document is published as a new version. Earlier versions, and the answers
    given to them, are left as they were."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = questionnaires.find(session, key)
        questionnaires.update(session, principal, row, body.model_dump(exclude_unset=True))
        return envelope(questionnaires.view(session, row))


@router.post("/questionnaires/{key}/responses", summary="Answer a questionnaire")
def respond(request: Request, key: str, body: AnswersIn) -> dict[str, Any]:
    """With ``complete`` false the answers are kept as a draft. A draft is finished by sending
    its ``response_id`` again, and is answered under the version it was begun under."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = questionnaires.find(session, key)
        earlier = (
            questionnaires.get_response(session, principal, body.response_id)
            if body.response_id
            else None
        )
        response = questionnaires.answer(
            session, principal, row, body.answers, complete=body.complete, response=earlier
        )
        return envelope(questionnaires.response_view(session, response))


@router.get("/responses/{response_id}", summary="Answers, as they were asked")
def response(request: Request, response_id: int) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        found = questionnaires.get_response(session, principal, response_id)
        return envelope(questionnaires.response_view(session, found))
