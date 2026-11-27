"""Questionnaires as data (OVS-07).

A questionnaire is a document of sections and questions. A question may appear only when a
condition over earlier answers is true. Publishing a change makes a new version and leaves
the old ones as they were, and an answer is always read against the version it was given
to, so it reads as it was asked whatever the questionnaire says now.

The web app repeats ``showing`` (``js/core/questionnaire.js``) so that a form can react as it
is filled in. Both must pass ``tests/fixtures/questionnaire-cases.json``; the server's
answer is the one that counts.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core import conditions
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import Questionnaire, QuestionnaireVersion, Response
from riskwren.events import audit

TYPES = ("yes_no", "choice", "choices", "text", "long_text", "number", "date")
PURPOSES = ("attestation", "self_assessment", "completeness", "due_diligence", "review", "other")
KEY = re.compile(r"[a-z][a-z0-9_]{0,39}")
NAME = re.compile(r"[a-z][a-z0-9-]{1,59}")
TEXT_LIMIT, LONG_TEXT_LIMIT = 500, 10_000
MAX_SECTIONS, MAX_QUESTIONS, MAX_OPTIONS = 40, 300, 60
_MISSING = "Answer this question."


# --- The document -------------------------------------------------------------------------


def problems(document: Any) -> list[str]:
    """Everything wrong with a questionnaire's document. An empty list means it can be asked."""
    if not isinstance(document, Mapping) or not isinstance(document.get("sections"), list):
        return ["The document needs a list of sections."]
    found: list[str] = []
    sections = document["sections"]
    if not sections:
        found.append("Add at least one section.")
    if len(sections) > MAX_SECTIONS:
        found.append(f"Keep it to {MAX_SECTIONS} sections.")
    seen: set[str] = set()
    section_keys: set[str] = set()
    count = 0
    for s_index, section in enumerate(sections):
        where = f"Section {s_index + 1}"
        if not isinstance(section, Mapping):
            found.append(f"{where}: must be an object.")
            continue
        key = section.get("key")
        if not isinstance(key, str) or not KEY.fullmatch(key):
            found.append(f"{where}: needs a key of lower-case letters, digits, and underscores.")
        elif key in section_keys:
            found.append(f"{where}: the key {key} is used twice.")
        else:
            section_keys.add(key)
        if not isinstance(section.get("title"), str) or not section["title"].strip():
            found.append(f"{where}: needs a title.")
        found += _condition_problems(section.get("show_when"), seen, where)
        questions = section.get("questions")
        if not isinstance(questions, list) or not questions:
            found.append(f"{where}: needs at least one question.")
            continue
        for q_index, question in enumerate(questions):
            count += 1
            here = f"{where}, question {q_index + 1}"
            if not isinstance(question, Mapping):
                found.append(f"{here}: must be an object.")
                continue
            found += _question_problems(question, seen, here)
            if isinstance(question.get("key"), str):
                seen.add(question["key"])
    if count > MAX_QUESTIONS:
        found.append(f"Keep it to {MAX_QUESTIONS} questions.")
    return found


def _question_problems(question: Mapping[str, Any], seen: set[str], where: str) -> list[str]:
    found: list[str] = []
    key = question.get("key")
    if not isinstance(key, str) or not KEY.fullmatch(key):
        found.append(f"{where}: needs a key of lower-case letters, digits, and underscores.")
    elif key in seen:
        found.append(f"{where}: the key {key} is used twice.")
    if not isinstance(question.get("label"), str) or not question["label"].strip():
        found.append(f"{where}: needs the question itself.")
    kind = question.get("type")
    if kind not in TYPES:
        found.append(f"{where}: its type must be one of {', '.join(TYPES)}.")
    if kind in ("choice", "choices"):
        options = question.get("options")
        if not isinstance(options, list) or len(options) < 2:
            found.append(f"{where}: needs at least two options to choose from.")
        elif len(options) > MAX_OPTIONS:
            found.append(f"{where}: keep it to {MAX_OPTIONS} options.")
        else:
            keys = [o.get("key") if isinstance(o, Mapping) else None for o in options]
            if any(not isinstance(k, str) or not KEY.fullmatch(k) for k in keys):
                found.append(f"{where}: every option needs a key.")
            elif len(set(keys)) != len(keys):
                found.append(f"{where}: an option's key is used twice.")
            if any(
                not isinstance(o, Mapping)
                or not isinstance(o.get("label"), str)
                or not o["label"].strip()
                for o in options
            ):
                found.append(f"{where}: every option needs words.")
    elif question.get("options"):
        found.append(f"{where}: only a choice has options.")
    if "required" in question and not isinstance(question["required"], bool):
        found.append(f"{where}: required is true or false.")
    found += _condition_problems(question.get("show_when"), seen, where)
    return found


def _condition_problems(condition: Any, seen: set[str], where: str) -> list[str]:
    """A condition must be well formed, and may look only at questions asked before it, so
    that showing and hiding never runs in a circle."""
    if condition in (None, {}):
        return []
    found = [f"{where}: {problem}" for problem in conditions.problems(condition, where="rule")]
    if found:
        return found
    for field in sorted(conditions.fields(condition)):
        head, _, key = field.partition(".")
        if head != "answers" or not key:
            found.append(
                f"{where}: a rule looks at an earlier answer, written answers.name, not {field}."
            )
        elif key.split(".")[0] not in seen:
            found.append(f"{where}: its rule looks at {key}, which is not asked before it.")
    return found


def visible(
    document: Mapping[str, Any], answers: Mapping[str, Any]
) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    """The questions that are showing, given the answers, as (section, question). A question
    depends only on questions before it, so callers that are cleaning answers pass the ones
    they have cleaned so far."""
    for section in document["sections"]:
        if not conditions.evaluate(section.get("show_when"), {"answers": answers}):
            continue
        for question in section["questions"]:
            if conditions.evaluate(question.get("show_when"), {"answers": answers}):
                yield section, question


def showing(document: Mapping[str, Any], answers: Mapping[str, Any]) -> tuple[list[str], dict]:
    """Which questions are showing, and the answers that count: those to questions that
    show. An answer to a question that an earlier answer has hidden is dropped, so that it
    cannot go on deciding what else is asked."""
    kept: dict[str, Any] = {}
    keys: list[str] = []
    for _section, question in visible(document, kept):
        key = question["key"]
        keys.append(key)
        if answers.get(key) not in (None, "", []):
            kept[key] = answers[key]
    return keys, kept


def _clean_one(question: Mapping[str, Any], value: Any) -> tuple[Any, str | None]:
    """An answer in its proper form, or what is wrong with it. None means not answered."""
    kind = question["type"]
    if value is None or value == "" or value == []:
        return None, None
    if kind in ("text", "long_text"):
        text = str(value).strip() if isinstance(value, str | int | float) else ""
        limit = TEXT_LIMIT if kind == "text" else LONG_TEXT_LIMIT
        if len(text) > limit:
            return None, f"Keep this to {limit} characters."
        return text or None, None
    allowed = [option["key"] for option in question.get("options", [])]
    if kind == "choice":
        return (value, None) if value in allowed else (None, "Choose one of the options.")
    if kind == "choices":
        if not isinstance(value, list) or any(item not in allowed for item in value):
            return None, "Choose from the options."
        return [key for key in allowed if key in value] or None, None  # in the document's order
    if kind == "yes_no":
        return (value, None) if isinstance(value, bool) else (None, "Answer yes or no.")
    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, int | float):
            return None, "Enter a number."
        return value, None
    try:
        return date.fromisoformat(str(value)).isoformat(), None
    except ValueError:
        return None, "Enter a date."


def clean(
    document: Mapping[str, Any], answers: Mapping[str, Any], *, complete: bool
) -> tuple[dict[str, Any], dict[str, str]]:
    """The answers that count, and what is wrong with the rest. With ``complete`` every
    required question that is showing must be answered."""
    cleaned: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for _section, question in visible(document, cleaned):
        key = question["key"]
        value, problem = _clean_one(question, answers.get(key))
        if problem:
            errors[key] = problem
        elif value is not None:
            cleaned[key] = value
        elif complete and question.get("required"):
            errors[key] = _MISSING
    return cleaned, errors


def as_asked(document: Mapping[str, Any], answers: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The answers set out as they were asked: each question that showed, in order, with its
    own words and the words of whatever was chosen."""
    out: list[dict[str, Any]] = []
    for section, question in visible(document, answers):
        if not out or out[-1]["key"] != section["key"]:
            out.append({"key": section["key"], "title": section["title"], "questions": []})
        value = answers.get(question["key"])
        labels = {o["key"]: o["label"] for o in question.get("options", [])}
        if question["type"] == "yes_no" and value is not None:
            said: Any = "Yes" if value else "No"
        elif question["type"] == "choice":
            said = labels.get(value, value)
        elif question["type"] == "choices":
            said = [labels.get(item, item) for item in value or []]
        else:
            said = value
        out[-1]["questions"].append(
            {
                "key": question["key"],
                "label": question["label"],
                "type": question["type"],
                "value": value,
                "said": said,
            }
        )
    return out


# --- Keeping them -------------------------------------------------------------------------


def _require(principal: Principal) -> None:
    if not principal.configures:
        raise PermissionDenied("Only those who run the program can change a questionnaire.")


def find(session: Session, key: str) -> Questionnaire:
    row = session.scalars(select(Questionnaire).where(Questionnaire.key == key)).first()
    if row is None:
        raise NotFound(f"There is no questionnaire {key}.")
    return row


def version_of(
    session: Session, row: Questionnaire, number: int | None = None
) -> QuestionnaireVersion:
    found = session.scalars(
        select(QuestionnaireVersion).where(
            QuestionnaireVersion.questionnaire_id == row.id,
            QuestionnaireVersion.number == (number or row.current_version),
        )
    ).first()
    if found is None:
        raise NotFound(f"{row.title} has no version {number}.")
    return found


def all_(session: Session, *, purpose: str | None = None) -> list[Questionnaire]:
    query = select(Questionnaire).order_by(Questionnaire.title)
    if purpose:
        query = query.where(Questionnaire.purpose == purpose)
    return list(session.scalars(query))


def _check(values: Mapping[str, Any], *, new: bool) -> dict[str, str]:
    errors: dict[str, str] = {}
    if new and not NAME.fullmatch(str(values.get("key") or "")):
        errors["key"] = "A short name of lower-case letters, digits, and hyphens."
    title = str(values.get("title") or "").strip()
    if (new or "title" in values) and not 1 <= len(title) <= 200:
        errors["title"] = "Give it a title."
    if values.get("purpose") is not None and values["purpose"] not in PURPOSES:
        errors["purpose"] = f"Choose one of: {', '.join(PURPOSES)}."
    if new or "document" in values:
        found = problems(values.get("document"))
        if found:
            errors["document"] = " ".join(found[:12])
    return errors


def _publish(
    session: Session, row: Questionnaire, number: int, document: Mapping[str, Any],
    by: Principal | None, note: str | None,
) -> QuestionnaireVersion:  # fmt: skip
    version = QuestionnaireVersion(
        questionnaire_id=row.id, number=number, document=dict(document),
        note=(note or "").strip() or None, published_by=by.account_id if by else None,
        published_by_name=by.name if by else "RiskWren", published_at=utc_now(),
    )  # fmt: skip
    session.add(version)
    row.current_version = number
    session.flush()
    return version


def create(session: Session, principal: Principal, values: Mapping[str, Any]) -> Questionnaire:
    _require(principal)
    errors = _check(values, new=True)
    if errors:
        raise Invalid("The questionnaire was not saved.", errors)
    if session.scalars(select(Questionnaire.id).where(Questionnaire.key == values["key"])).first():
        raise Conflict(f"There is already a questionnaire called {values['key']}.")
    with audit.operation(session, "questionnaire.create"):
        row = Questionnaire(
            key=values["key"], title=str(values["title"]).strip(),
            summary=(str(values.get("summary") or "").strip() or None),
            purpose=values.get("purpose") or "other", origin="local",
            created_by=principal.account_id, created_at=utc_now(),
        )  # fmt: skip
        session.add(row)
        session.flush()
        _publish(session, row, 1, values["document"], principal, None)
    return row


def update(
    session: Session, principal: Principal, row: Questionnaire, changes: Mapping[str, Any]
) -> Questionnaire:
    """Change what a questionnaire is called or whether it is still used, and, if its
    document has changed, publish that as a new version. Earlier versions are untouched."""
    _require(principal)
    errors = _check(changes, new=False)
    if changes.get("status") is not None and changes["status"] not in ("active", "retired"):
        errors["status"] = "Active or retired."
    if errors:
        raise Invalid("The questionnaire was not saved.", errors)
    with audit.operation(session, "questionnaire.update"):
        if "title" in changes:
            row.title = str(changes["title"]).strip()
        if "summary" in changes:
            row.summary = str(changes["summary"] or "").strip() or None
        if changes.get("purpose") is not None:
            row.purpose = changes["purpose"]
        if changes.get("status") is not None:
            row.status = changes["status"]
        document = changes.get("document")
        if document is not None and document != version_of(session, row).document:
            row.origin = "local"  # it is the organization's own from here on
            _publish(session, row, row.current_version + 1, document, principal,
                     changes.get("note"))  # fmt: skip
        session.flush()
    return row


def view(session: Session, row: Questionnaire, number: int | None = None) -> dict[str, Any]:
    version = version_of(session, row, number)
    versions = session.scalars(
        select(QuestionnaireVersion)
        .where(QuestionnaireVersion.questionnaire_id == row.id)
        .order_by(QuestionnaireVersion.number.desc())
    ).all()
    return {
        **summary(row),
        "version": version.number,
        "document": version.document,
        "versions": [
            {
                "number": v.number,
                "note": v.note,
                "published_by": v.published_by_name,
                "published_at": v.published_at,
                "current": v.number == row.current_version,
            }
            for v in versions
        ],
    }


def summary(row: Questionnaire) -> dict[str, Any]:
    return {
        "key": row.key, "title": row.title, "summary": row.summary, "purpose": row.purpose,
        "status": row.status, "origin": row.origin, "current_version": row.current_version,
    }  # fmt: skip


def install(session: Session, packs: list[dict[str, Any]]) -> int:
    """Load the built-in questionnaires that are not here yet, and bring up to date those
    that are here unchanged. One the organization has edited is left alone."""
    changed = 0
    for pack in packs:
        found = problems(pack["document"])
        if found:
            raise Invalid(f"The built-in questionnaire {pack['key']} is not valid.",
                          {"document": " ".join(found)})  # fmt: skip
        row = session.scalars(select(Questionnaire).where(Questionnaire.key == pack["key"])).first()
        if row is None:
            row = Questionnaire(
                key=pack["key"], title=pack["title"], summary=pack.get("summary"),
                purpose=pack.get("purpose", "other"), origin="pack", created_at=utc_now(),
            )  # fmt: skip
            session.add(row)
            session.flush()
            _publish(session, row, 1, pack["document"], None, None)
            changed += 1
        elif row.origin == "pack" and version_of(session, row).document != pack["document"]:
            _publish(session, row, row.current_version + 1, pack["document"], None,
                     "Brought up to date with this release.")  # fmt: skip
            changed += 1
    return changed


# --- Answers ------------------------------------------------------------------------------


def answer(
    session: Session,
    principal: Principal,
    row: Questionnaire,
    answers: Mapping[str, Any],
    *,
    subject: tuple[str, int] | None = None,
    complete: bool = True,
    response: Response | None = None,
    version: QuestionnaireVersion | None = None,
) -> Response:
    """Keep someone's answers. A draft may be incomplete and is finished later; a submitted
    response is checked in full and cannot be changed afterwards. A draft begun under an
    earlier version is finished under that version: it is answered as it was asked."""
    if principal.account_id is None:
        raise PermissionDenied("Sign in to answer.")
    if response is not None:
        if response.account_id != principal.account_id:
            raise NotFound("There is no such response.")
        if response.status == "submitted":
            raise Conflict("These answers have been submitted and cannot be changed.")
        version = session.get(QuestionnaireVersion, response.version_id)
        assert version is not None
    else:
        if version is None:
            # A campaign asks everyone the version it was launched with; otherwise the
            # current one, of a questionnaire that is still in use.
            if row.status != "active":
                raise Conflict(f"{row.title} is no longer used.")
            version = version_of(session, row)
    cleaned, errors = clean(version.document, answers, complete=complete)
    if errors:
        raise Invalid("Some answers need another look.", errors)
    with audit.operation(session, "questionnaire.answer"):
        if response is None:
            response = Response(
                version_id=version.id, subject_type=subject[0] if subject else None,
                subject_id=subject[1] if subject else None, account_id=principal.account_id,
                account_name=principal.name, started_at=utc_now(),
            )  # fmt: skip
            session.add(response)
        response.answers = cleaned
        if complete:
            response.status, response.submitted_at = "submitted", utc_now()
        session.flush()
    return response


def get_response(session: Session, principal: Principal, response_id: int) -> Response:
    """A response, for whoever gave it and for those who run the program or read everything."""
    row = session.get(Response, response_id)
    if row is None or not (
        row.account_id == principal.account_id or principal.configures or principal.reads_all
    ):
        raise NotFound("There is no such response.")
    return row


def response_view(session: Session, response: Response) -> dict[str, Any]:
    version = session.get(QuestionnaireVersion, response.version_id)
    assert version is not None
    row = session.get(Questionnaire, version.questionnaire_id)
    assert row is not None
    return {
        "id": response.id,
        "questionnaire": summary(row),
        "version": version.number,
        "is_current_version": version.number == row.current_version,
        "status": response.status,
        "by": response.account_name,
        "started_at": response.started_at,
        "submitted_at": response.submitted_at,
        "answers": response.answers,
        "as_asked": as_asked(version.document, response.answers),
        "document": version.document if response.status == "draft" else None,
    }
