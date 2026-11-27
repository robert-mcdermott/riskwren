"""Due diligence: a questionnaire chosen by the tier, sent to a contact through a link that
needs no account and reaches nothing else, answered, reviewed with its concerns counted, and
concluded."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.core.clock import frozen_at, utc_now
from riskwren.core.errors import Conflict, Invalid, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import Event, Notice, RespondentLink, Response
from riskwren.inventory import history, records
from riskwren.inventory.registry import THIRD_PARTY
from riskwren.reporting import service as reporting
from riskwren.thirdparty import contacts, respondent, reviews, tiering
from riskwren.thirdparty.reviews import REVIEW
from tests.people import People
from tests.test_risks import who

Clients = Callable[[str | None], TestClient]
GOOD = {
    "security_contact": "Ana Ruiz, security@tallyfield.example",
    "certifications": ["soc2_type2"],
    "mfa": True, "encryption": True, "access_removed": True, "breach_notice": True,
    "return_destroy": True,
}  # fmt: skip
TIER_3 = {"information": "internal", "access": ["on_site"], "dependency": "little"}


def a_tiered_party(db: Database, people: People, answers: dict[str, Any] = TIER_3) -> str:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        party = records.create(session, steward, THIRD_PARTY, {
            "name": "Tallyfield Surveys", "kind": "service_provider",
            "org_unit_id": people.units["IMM"]})  # fmt: skip
        tiering.record(session, steward, party, answers, None, None)
        contacts.add(session, steward, party, {"name": "Ana Ruiz",
                     "email": "Ana@Tallyfield.example", "role": "Security lead"})  # fmt: skip
        return party.ref


def test_a_review_asks_the_questionnaire_its_tier_names(db: Database, people: People) -> None:
    ref = a_tiered_party(db, people)
    steward, member = who(db, people, "steward"), who(db, people, "member")
    with db.write(steward.actor) as session:
        party = records.load(session, steward, THIRD_PARTY, ref)
        assert party.tier == "tier_3"
        with pytest.raises(PermissionDenied):
            reviews.start(session, member, party, {})
        review = reviews.start(session, steward, party, {})
        assert review.ref.startswith("DDR-") and review.status == "draft"
        shown = records.detail(session, steward, REVIEW, review)
        assert shown["questionnaire"]["key"] == "due-diligence-short"
        assert shown["tier"] == "tier_3" and shown["third_party"]["ref"] == ref
        # A tier 4 third party has no questionnaire of its own; one must be chosen.
        plain = records.create(
            session,
            steward,
            THIRD_PARTY,
            {"name": "Cleanreach", "kind": "contractor", "org_unit_id": people.units["IMM"]},
        )
        tiering.record(session, steward, plain, {"information": "none", "access": ["no_access"],
                       "dependency": "little"}, None, None)  # fmt: skip
        with pytest.raises(Invalid) as caught:
            reviews.start(session, steward, plain, {})
        assert "questionnaire" in caught.value.errors
        chosen = reviews.start(session, steward, plain, {"questionnaire": "due-diligence-short"})
        assert chosen.status == "draft"


def test_a_contact_answers_through_the_link_and_through_nothing_else(
    db: Database, people: People
) -> None:
    ref = a_tiered_party(db, people)
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        party = records.load(session, steward, THIRD_PARTY, ref)
        contact = contacts.of(session, party)[0]
        assert contact.email == "ana@tallyfield.example"
        review = reviews.start(session, steward, party, {})
        token = reviews.send(session, steward, review, contact_id=contact.id, days=10)
        review_ref = review.ref
        # The token is never kept; only its digest is.
        kept = session.scalars(select(RespondentLink)).one()
        assert kept.token_hash == respondent.digest(token) and token not in kept.token_hash
        assert len(token) >= 40
        stored = session.scalars(select(Event.changes)).all()
        assert not any(token in str(changes) for changes in stored)
        # The link opens its own questionnaire, and only that.
        link = respondent.find(session, token)
        seen = respondent.view(session, link)
        assert seen["third_party"] == "Tallyfield Surveys" and seen["contact"] == "Ana Ruiz"
        assert seen["title"] == "Due diligence: short"
        assert set(seen) == {"organization", "asked_by", "third_party", "contact", "title",
                             "summary", "due_on", "expires_at", "document", "answers",
                             "saved_at", "files", "most_files"}  # fmt: skip
        for wrong in (None, "", "x" * 300, token[:-1] + ("A" if token[-1] != "A" else "B")):
            with pytest.raises(respondent.LinkRefused) as refused:
                respondent.find(session, wrong)
            assert refused.value.reason is None
    # Saving, then sending, as the contact: the history names them, by link.
    with db.read() as session:
        link = respondent.find(session, token)
        actor = respondent.actor_for(session, link)
    assert actor.label == "Ana Ruiz (Tallyfield Surveys), by link" and actor.id is None
    with db.write(actor) as session:
        link = respondent.find(session, token)
        respondent.save(session, link, {"mfa": False}, submit=False)
    with db.write(actor) as session:
        link = respondent.find(session, token)
        with pytest.raises(Invalid) as caught:
            respondent.save(session, link, {"mfa": False}, submit=True)
        assert "security_contact" in caught.value.errors
        respondent.save(session, link, {**GOOD, "mfa": False}, submit=True)
    with db.write(steward.actor) as session:
        # Once sent, the link opens nothing.
        with pytest.raises(respondent.LinkRefused) as refused:
            respondent.find(session, token)
        assert refused.value.reason == "used"
        review = reviews.find(session, review_ref)
        assert review.status == "answered"
        owed = reporting.home(session, steward)["items"]
        assert [i["kind"] for i in owed if i.get("ref") == review_ref] == ["review_answers"]
        shown = records.detail(session, steward, REVIEW, review)
        assert shown["answers"]["concerns"]["count"] == 1  # no second factor
        assert shown["answers"]["concerns"]["items"][0]["key"] == "mfa"
        assert shown["answers"]["concerns"]["scored"] == 6
        response = session.scalars(select(Response)).one()
        assert response.account_id is None and response.account_name == "Ana Ruiz"
        told = session.scalars(select(Notice.text)).all()
        assert any("Ana Ruiz of Tallyfield Surveys sent the answers" in text for text in told)
        titles = [entry["title"] for entry in history.for_record(session, REVIEW, review)]
        assert "Ana Ruiz sent the answers" in titles
        actors = {entry["actor"] for entry in history.for_record(session, REVIEW, review)}
        assert "Ana Ruiz (Tallyfield Surveys), by link" in actors
        # The conclusion is the reviewer's, with reasons where it is not plain approval.
        with pytest.raises(Invalid):
            reviews.conclude(session, steward, review, "conditions", None)
        reviews.conclude(session, steward, review, "conditions",
                         "Second factor for every account by the end of March.")  # fmt: skip
        assert review.status == "concluded"
        with pytest.raises(Conflict):
            reviews.send(session, steward, review, contact_id=review.contact_id)


def test_a_link_stops_when_it_expires_or_is_withdrawn_or_replaced(
    db: Database, people: People
) -> None:
    ref = a_tiered_party(db, people)
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        party = records.load(session, steward, THIRD_PARTY, ref)
        contact = contacts.of(session, party)[0]
        review = reviews.start(session, steward, party, {})
        first = reviews.send(session, steward, review, contact_id=contact.id, days=1)
        second = reviews.send(session, steward, review, contact_id=contact.id, days=1)
        with pytest.raises(respondent.LinkRefused) as refused:
            respondent.find(session, first)
        assert refused.value.reason == "withdrawn"
        assert respondent.find(session, second)
        with frozen_at(utc_now() + timedelta(days=1, minutes=1)):
            with pytest.raises(respondent.LinkRefused) as refused:
                respondent.find(session, second)
            assert refused.value.reason == "expired"
        reviews.withdraw(session, steward, review)
        with pytest.raises(respondent.LinkRefused):
            respondent.find(session, second)
        third = reviews.send(session, steward, review, contact_id=contact.id)
        reviews.cancel(session, steward, review, "The service was not bought.")
        with pytest.raises(respondent.LinkRefused):
            respondent.find(session, third)
        # A contact who has left is not sent anything.
        contacts.change(session, steward, contact, {"status": "left"})
        again = reviews.start(session, steward, party, {})
        with pytest.raises(Invalid):
            reviews.send(session, steward, again, contact_id=contact.id)


def test_the_link_through_the_api(as_role: Clients, people: People, db: Database) -> None:
    ref = a_tiered_party(db, people)
    steward, nobody = as_role("steward"), as_role(None)
    party = steward.get(f"/api/v1/third-parties/{ref}").json()["data"]
    contact = party["contacts"][0]
    made = steward.post(f"/api/v1/third-parties/{ref}/reviews", json={}).json()["data"]
    sent = steward.post(f"/api/v1/reviews/{made['ref']}/send", json={"contact_id": contact["id"]})
    assert sent.status_code == 200, sent.text
    url = sent.json()["meta"]["link"]["url"]
    assert "/respond#" in url and "?" not in url
    token = url.split("#", 1)[1]
    header = {respondent.HEADER: token}
    # Without an account: the link opens its questionnaire, and nothing else.
    shown = nobody.get("/api/v1/respond", headers=header)
    assert shown.status_code == 200 and shown.headers["cache-control"] == "no-store"
    assert shown.json()["data"]["title"] == "Due diligence: short"
    assert nobody.get(f"/api/v1/reviews/{made['ref']}", headers=header).status_code == 401
    assert nobody.get(f"/api/v1/third-parties/{ref}", headers=header).status_code == 401
    assert nobody.get("/api/v1/respond").status_code == 404
    assert nobody.get("/api/v1/respond", headers={respondent.HEADER: "nonsense"}).status_code == 404
    saved = nobody.put("/api/v1/respond", headers=header, json={"answers": {"mfa": True}})
    assert saved.status_code == 200, saved.text
    done = nobody.post("/api/v1/respond/submit", headers=header, json={"answers": GOOD})
    assert done.status_code == 200, done.text
    again = nobody.get("/api/v1/respond", headers=header)
    assert again.status_code == 410 and "no longer opens" in again.json()["detail"]
    review = steward.get(f"/api/v1/reviews/{made['ref']}").json()["data"]
    assert review["status"] == "answered" and review["answers"]["concerns"]["count"] == 0
    assert review["link"]["state"] == "used"
    concluded = steward.post(f"/api/v1/reviews/{made['ref']}/conclude",
                             json={"conclusion": "approved"})  # fmt: skip
    assert concluded.status_code == 200 and concluded.json()["data"]["status"] == "concluded"


def test_guessing_tokens_is_slowed(as_role: Clients, people: People) -> None:
    nobody = as_role(None)
    answers = [
        nobody.get("/api/v1/respond", headers={respondent.HEADER: f"guess-{n}"}).status_code
        for n in range(40)
    ]
    assert answers[0] == 404 and 429 in answers
