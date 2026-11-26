"""Questionnaires: documents checked whole, questions that appear by condition, versions that
are never changed, and answers that read as they were asked."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import Event, Questionnaire, QuestionnaireVersion
from riskwren.oversight import questionnaires
from riskwren.program import packs
from tests.people import ME, People
from tests.test_risks import who

Clients = Callable[[str | None], TestClient]
ROOT = Path(__file__).resolve().parent.parent
SHARED = json.loads((ROOT / "tests/fixtures/questionnaire-cases.json").read_text("utf-8"))


def doc(*questions: dict, **more: object) -> dict:
    return {"sections": [{"key": "one", "title": "One", "questions": list(questions), **more}]}


ASKED = doc(
    {"key": "operates", "label": "Does it still operate?", "type": "choice", "required": True,
     "options": [{"key": "yes", "label": "Yes"}, {"key": "no", "label": "No"}]},
    {"key": "why", "label": "What is different?", "type": "long_text", "required": True,
     "show_when": {"field": "answers.operates", "op": "eq", "value": "no"}},
    {"key": "seen", "label": "When did you last look?", "type": "date"},
)  # fmt: skip


@pytest.fixture
def loaded(db: Database) -> None:
    with db.write(ME.actor) as session:
        packs.install(session, frameworks=False)


# --- Showing and hiding -------------------------------------------------------------------


@pytest.mark.parametrize("case", SHARED["cases"], ids=[c["name"] for c in SHARED["cases"]])
def test_the_shared_cases(case: dict) -> None:
    """The browser runs the same cases (tests/js/questionnaire.test.mjs)."""
    document = SHARED["documents"][case["questionnaire"]]
    assert questionnaires.showing(document, case["answers"]) == (case["keys"], case["kept"])


def test_what_shows_is_what_the_document_says() -> None:
    """Said here in full, so that the shared cases are not only the code agreeing with itself."""
    showing = questionnaires.showing
    assert showing(ASKED, {}) == (["operates", "seen"], {})
    assert showing(ASKED, {"operates": "no"})[0] == ["operates", "why", "seen"]
    # An answer to a question that is no longer showing is dropped.
    assert showing(ASKED, {"operates": "yes", "why": "left over"}) == (
        ["operates", "seen"], {"operates": "yes"},
    )  # fmt: skip
    risk = SHARED["documents"]["risk-self-assessment"]
    keys, kept = showing(risk, {"relevant": False, "changed": ["cause"], "plan": "late"})
    assert keys == ["relevant", "why_not"] and kept == {"relevant": False}
    profile = SHARED["documents"]["system-security-profile"]
    exposed = {"internet": True, "second_factor": "admins", "data": ["public"]}
    assert "second_factor_why" in showing(profile, exposed)[0]
    assert "second_factor_why" not in showing(profile, {**exposed, "internet": False})[0]


def test_answers_are_checked_against_what_is_showing() -> None:
    clean = questionnaires.clean
    assert clean(ASKED, {}, complete=False) == ({}, {})  # a draft may be empty
    assert clean(ASKED, {}, complete=True)[1] == {"operates": "Answer this question."}
    cleaned, errors = clean(ASKED, {"operates": "no"}, complete=True)
    assert errors == {"why": "Answer this question."}  # required once it shows
    cleaned, errors = clean(
        ASKED, {"operates": "yes", "why": "hidden", "seen": "2026-11-02"}, complete=True
    )
    assert (cleaned, errors) == ({"operates": "yes", "seen": "2026-11-02"}, {})
    wrong = clean(ASKED, {"operates": "maybe", "seen": "last week"}, complete=False)[1]
    assert wrong == {"operates": "Choose one of the options.", "seen": "Enter a date."}


@pytest.mark.parametrize(
    ("document", "complaint"),
    [
        ({}, "needs a list of sections"),
        ({"sections": []}, "at least one section"),
        (doc(), "at least one question"),
        (doc({"key": "Bad Key", "label": "x", "type": "text"}), "needs a key"),
        (doc({"key": "a", "label": " ", "type": "text"}), "needs the question itself"),
        (doc({"key": "a", "label": "x", "type": "essay"}), "its type must be one of"),
        (doc({"key": "a", "label": "x", "type": "choice"}), "at least two options"),
        (doc({"key": "a", "label": "x", "type": "text"}, {"key": "a", "label": "y", "type": "text"}),  # noqa: E501
         "used twice"),
        (doc({"key": "a", "label": "x", "type": "text",
              "show_when": {"field": "answers.later", "op": "answered"}},
             {"key": "later", "label": "y", "type": "text"}),
         "not asked before it"),
        (doc({"key": "a", "label": "x", "type": "text"},
             {"key": "b", "label": "y", "type": "text",
              "show_when": {"field": "account.role", "op": "eq", "value": "admin"}}),
         "looks at an earlier answer"),
        (doc({"key": "a", "label": "x", "type": "text"},
             {"key": "b", "label": "y", "type": "text", "show_when": {"field": "answers.a", "op": "is"}}),  # noqa: E501
         "`op` must be one of"),
        (doc({"key": "a", "label": "x", "type": "text", "show_when": "answers.a == 1"}),
         "must be an object"),
    ],
)  # fmt: skip
def test_a_document_is_checked_whole(document: dict, complaint: str) -> None:
    assert complaint in " ".join(questionnaires.problems(document))


# --- Keeping them -------------------------------------------------------------------------


def test_a_new_installation_has_the_built_in_questionnaires(db: Database, loaded: None) -> None:
    with db.write(ME.actor) as session:
        held = {row.key: row for row in questionnaires.all_(session)}
        assert set(held) == {
            "control-attestation", "risk-self-assessment", "unit-completeness",
            "system-security-profile",
        }  # fmt: skip
        assert all((row.origin, row.current_version) == ("pack", 1) for row in held.values())
        assert [r.key for r in questionnaires.all_(session, purpose="attestation")] == [
            "control-attestation"
        ]
        assert packs.install(session, frameworks=False)["questionnaires"] == 0  # safe to run again


def test_a_change_is_a_new_version_and_an_answer_reads_as_it_was_asked(
    db: Database, people: People
) -> None:
    """The acceptance test: an answer still reads as asked after the questionnaire changes."""
    manager, member = who(db, people, "manager"), who(db, people, "member")
    with db.write(manager.actor) as session:
        with pytest.raises(PermissionDenied):
            questionnaires.create(session, member, {"key": "x-y", "title": "X", "document": ASKED})
        with pytest.raises(Invalid) as caught:
            questionnaires.create(
                session, manager, {"key": "Bad Name", "title": "", "document": doc()}
            )
        assert set(caught.value.errors) == {"key", "title", "document"}
        row = questionnaires.create(
            session, manager,
            {"key": "freezer-check", "title": "Freezer check", "purpose": "attestation",
             "document": ASKED},
        )  # fmt: skip
        assert (row.origin, row.current_version) == ("local", 1)
        with pytest.raises(Conflict):
            questionnaires.create(
                session, manager, {"key": "freezer-check", "title": "Again", "document": ASKED}
            )
    with db.write(member.actor) as session:
        row = questionnaires.find(session, "freezer-check")
        with pytest.raises(Invalid) as caught:
            questionnaires.answer(session, member, row, {"operates": "no"})
        assert caught.value.errors == {"why": "Answer this question."}
        given = questionnaires.answer(
            session, member, row, {"operates": "no", "why": "The alarm is off at night."}
        )
        first = given.id
        with pytest.raises(Conflict):  # submitted answers are not changed
            questionnaires.answer(session, member, row, {"operates": "yes"}, response=given)

    changed = json.loads(json.dumps(ASKED))
    changed["sections"][0]["questions"][0]["label"] = "Is the freezer alarm working tonight?"
    changed["sections"][0]["questions"][0]["options"] = [
        {"key": "yes", "label": "It is"}, {"key": "no", "label": "It is not"},
        {"key": "unknown", "label": "Nobody has checked"},
    ]  # fmt: skip
    del changed["sections"][0]["questions"][1]  # the follow-up is no longer asked
    with db.write(manager.actor) as session:
        row = questionnaires.find(session, "freezer-check")
        questionnaires.update(session, manager, row, {"title": "Freezer alarm check"})
        assert row.current_version == 1  # a new name is not a new version
        questionnaires.update(
            session, manager, row, {"document": changed, "note": "Asked more plainly."}
        )
        questionnaires.update(
            session, manager, row, {"document": changed}
        )  # nothing new: no version
        seen = questionnaires.view(session, row)
        assert seen["version"] == 2 and [v["number"] for v in seen["versions"]] == [2, 1]
        assert seen["versions"][0]["note"] == "Asked more plainly."
        assert questionnaires.view(session, row, 1)["document"] == ASKED  # the old one is intact
        with pytest.raises(NotFound):
            questionnaires.view(session, row, 9)
        versions = session.execute(
            select(func.count())
            .select_from(QuestionnaireVersion)
            .where(QuestionnaireVersion.questionnaire_id == row.id)
        ).scalar_one()
        assert versions == 2
        told = session.scalars(
            select(Event).where(Event.subject_type == "questionnaire_version")
        ).all()
        assert {event.parent_type for event in told} == {"questionnaire"}  # in its history

    with db.read() as session:
        read = questionnaires.response_view(
            session, questionnaires.get_response(session, member, first)
        )
        assert (read["version"], read["is_current_version"]) == (1, False)
        [section] = read["as_asked"]
        assert [(q["label"], q["said"]) for q in section["questions"]] == [
            ("Does it still operate?", "No"),
            ("What is different?", "The alarm is off at night."),
            ("When did you last look?", None),  # asked, and left unanswered
        ]
        # Others do not read someone's answers; those who run the program do.
        with pytest.raises(NotFound):
            questionnaires.get_response(session, who(db, people, "steward"), first)
        assert questionnaires.get_response(session, manager, first).id == first
    with db.write(member.actor) as session:  # a new answer is to the new version
        row = questionnaires.find(session, "freezer-check")
        again = questionnaires.answer(session, member, row, {"operates": "unknown"})
        read = questionnaires.response_view(session, again)
        assert read["as_asked"][0]["questions"][0] == {
            "key": "operates", "label": "Is the freezer alarm working tonight?",
            "type": "choice", "value": "unknown", "said": "Nobody has checked",
        }  # fmt: skip


def test_a_draft_is_finished_under_the_version_it_was_begun_under(
    db: Database, people: People
) -> None:
    manager, member = who(db, people, "manager"), who(db, people, "member")
    with db.write(manager.actor) as session:
        questionnaires.create(
            session, manager, {"key": "check", "title": "Check", "document": ASKED}
        )
    with db.write(member.actor) as session:
        row = questionnaires.find(session, "check")
        draft = questionnaires.answer(session, member, row, {"operates": "no"}, complete=False)
        assert draft.status == "draft" and draft.submitted_at is None
        kept = draft.id
    with db.write(manager.actor) as session:
        row = questionnaires.find(session, "check")
        shorter = doc(ASKED["sections"][0]["questions"][0])
        questionnaires.update(session, manager, row, {"document": shorter})
    with db.write(member.actor) as session:
        row = questionnaires.find(session, "check")
        draft = questionnaires.get_response(session, member, kept)
        with pytest.raises(Invalid):  # the follow-up it was asked is still required of it
            questionnaires.answer(session, member, row, {"operates": "no"}, response=draft)
        done = questionnaires.answer(
            session, member, row, {"operates": "no", "why": "Unplugged."}, response=draft
        )
        assert done.status == "submitted"
        assert questionnaires.response_view(session, done)["version"] == 1
    with db.write(manager.actor) as session:
        row = questionnaires.find(session, "check")
        questionnaires.update(session, manager, row, {"status": "retired"})
    with db.write(member.actor) as session, pytest.raises(Conflict):
        questionnaires.answer(session, member, questionnaires.find(session, "check"), {})


def test_a_built_in_questionnaire_that_has_been_edited_is_left_alone(
    db: Database, loaded: None, people: People
) -> None:
    manager = who(db, people, "manager")
    with db.write(manager.actor) as session:
        row = questionnaires.find(session, "control-attestation")
        document = json.loads(json.dumps(questionnaires.view(session, row)["document"]))
        document["sections"][0]["title"] = "Our control"
        questionnaires.update(session, manager, row, {"document": document})
        assert (row.origin, row.current_version) == ("local", 2)
        other = session.scalars(
            select(Questionnaire).where(Questionnaire.key == "unit-completeness")
        ).one()
        pack = packs.builtin("questionnaires.json")["questionnaires"]
        newer = json.loads(json.dumps(pack))
        for item in newer:
            item["document"]["sections"][0]["title"] += " (revised)"
        assert questionnaires.install(session, newer) == 3  # the three nobody has touched
        assert row.current_version == 2 and other.current_version == 2
        assert questionnaires.view(session, other)["versions"][0]["published_by"] == "RiskWren"


def test_questionnaires_through_the_api(as_role: Clients, people: People, loaded: None) -> None:
    manager, member = as_role("manager"), as_role("member")
    listed = member.get("/api/v1/questionnaires").json()["data"]
    assert len(listed["questionnaires"]) == 4 and "yes_no" in listed["types"]
    shown = member.get("/api/v1/questionnaires/control-attestation").json()["data"]
    assert shown["version"] == 1 and shown["document"]["sections"][0]["key"] == "control"
    assert member.get("/api/v1/questionnaires/nothing").status_code == 404
    assert member.post("/api/v1/questionnaires/check", json={"document": ASKED}).status_code == 403

    bad = manager.post("/api/v1/questionnaires/check", json={"document": doc()}).json()["data"]
    assert bad["showing"] is None and "at least one question" in bad["problems"][0]
    tried = manager.post(
        "/api/v1/questionnaires/check", json={"document": ASKED, "answers": {"operates": "no"}}
    ).json()["data"]
    assert tried == {
        "problems": [], "showing": ["operates", "why", "seen"], "kept": {"operates": "no"},
    }  # fmt: skip
    made = manager.post(
        "/api/v1/questionnaires",
        json={"key": "freezer-check", "title": "Freezer check", "document": ASKED},
    )
    assert made.status_code == 201 and made.json()["data"]["origin"] == "local"
    refused = manager.patch("/api/v1/questionnaires/freezer-check", json={"document": doc()})
    assert refused.status_code == 422

    draft = member.post(
        "/api/v1/questionnaires/freezer-check/responses",
        json={"answers": {"operates": "no"}, "complete": False},
    ).json()["data"]
    assert draft["status"] == "draft" and draft["document"] == ASKED
    short = member.post(
        "/api/v1/questionnaires/freezer-check/responses",
        json={"answers": {"operates": "no"}, "response_id": draft["id"]},
    )
    assert short.status_code == 422
    assert short.json()["errors"][0]["location"] == ["why"]
    done = member.post(
        "/api/v1/questionnaires/freezer-check/responses",
        json={"answers": {"operates": "no", "why": "Unplugged."}, "response_id": draft["id"]},
    ).json()["data"]
    assert done["status"] == "submitted" and done["document"] is None
    read = member.get(f"/api/v1/responses/{done['id']}").json()["data"]
    assert read["as_asked"][0]["questions"][1]["said"] == "Unplugged."
    assert as_role("steward").get(f"/api/v1/responses/{done['id']}").status_code == 404
    assert as_role("auditor").get(f"/api/v1/responses/{done['id']}").status_code == 200
