"""A relationship over time: findings followed up with the third party, review on its tier's
cadence and when an event calls for it, offboarding, and subcontractors."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from riskwren.compliance import issues
from riskwren.compliance.issues import ISSUE
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, PermissionDenied
from riskwren.db.engine import Database
from riskwren.inventory import history, links, records
from riskwren.inventory.registry import THIRD_PARTY
from riskwren.program import rules
from riskwren.reporting import graph
from riskwren.reporting import service as reporting
from riskwren.thirdparty import contacts, lifecycle, respondent, reviews, tiering
from riskwren.thirdparty.services import SERVICE
from tests.people import People
from tests.test_due_diligence import GOOD
from tests.test_risks import who

Clients = Callable[[str | None], TestClient]
TIER_2 = {"information": "confidential", "access": ["remote"], "dependency": "slows"}
TIER_4 = {"information": "none", "access": ["no_access"], "dependency": "little"}


def a_party(session, steward, people: People, answers=TIER_2, name="Tallyfield Surveys"):  # type: ignore[no-untyped-def]
    party = records.create(
        session,
        steward,
        THIRD_PARTY,
        {"name": name, "kind": "service_provider", "org_unit_id": people.units["IMM"]},
    )
    tiering.record(session, steward, party, answers, None, None)
    return party


def answered(session, steward, party):  # type: ignore[no-untyped-def]
    who_ = {"name": "Ana Ruiz", "email": "ana@tallyfield.example"}
    contact = contacts.add(session, steward, party, who_)
    review = reviews.start(session, steward, party, {"questionnaire": "due-diligence-short"})
    token = reviews.send(session, steward, review, contact_id=contact.id)
    respondent.save(session, respondent.find(session, token), {**GOOD, "mfa": False}, submit=True)
    return review, contact


def test_a_third_party_is_due_on_its_tiers_cadence_and_at_once_when_an_event_calls(
    db: Database, people: People
) -> None:
    steward, member = who(db, people, "steward"), who(db, people, "member")
    today = utc_now().date()
    with db.write(steward.actor) as session:
        party = a_party(session, steward, people)
        # Never reviewed: due its tier's months after it was first tiered.
        assert party.next_review_on == rules.add_months(today, 24)
        quiet = a_party(session, steward, people, TIER_4, "Cleanreach")
        assert quiet.next_review_on is None  # tier 4 is reviewed only when called for
        review, _ = answered(session, steward, party)
        reviews.conclude(session, steward, review, "approved", None)
        assert party.next_review_on == rules.add_months(today, 24)
        # An event calls for a review now, and says why.
        with pytest.raises(PermissionDenied):
            lifecycle.call_review(session, member, party, "incident", "x")
        with pytest.raises(Invalid):
            lifecycle.call_review(session, steward, party, "incident", " ")
        lifecycle.call_review(session, steward, party, "breach_notice",
                              "Told us on 3 March of a misdirected export.")  # fmt: skip
        assert party.next_review_on == today
        assert party.review_called.startswith("It told us of a breach:")
        owed = [i for i in reporting.home(session, steward)["items"] if i.get("ref") == party.ref]
        assert [i["kind"] for i in owed] == ["third_party_review"]
        listed, total = records.search(session, steward, THIRD_PARTY, {"review": "due"})
        assert total == 1 and listed[0].ref == party.ref
        # Tiering again keeps the call; a higher tier brings the cadence in too.
        tiering.record(session, steward, party,
                       {**TIER_2, "information": "restricted"}, None, None)  # fmt: skip
        assert party.tier == "tier_1" and party.next_review_on == today
        # The next concluded review answers the call, and sets the next by the tier.
        again, _ = answered(session, steward, party)
        reviews.conclude(session, steward, again, "approved", None)
        assert party.review_called is None
        assert party.next_review_on == rules.add_months(today, 12)
        titles = [e["title"] for e in history.for_record(session, THIRD_PARTY, party)]
        assert any(t.startswith("Called for a review: It told us of a breach") for t in titles)


def test_a_finding_from_a_review_is_an_issue_whose_action_can_belong_to_a_contact(
    db: Database, people: People
) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        party = a_party(session, steward, people)
        review, contact = answered(session, steward, party)
        issue = lifecycle.raise_finding(
            session,
            steward,
            review,
            {"name": "No second factor for the survey host's staff", "severity": "high"},
        )
        assert issue.source_kind == "review" and issue.ref.startswith("ISS-")
        shown = records.detail(session, steward, ISSUE, issue)
        assert shown["source"] == {"review": {"ref": review.ref, "name": review.name}}
        assert [s["ref"] for s in shown["subjects"]["records"]] == [party.ref]
        assert [c["name"] for c in shown["contacts"]] == ["Ana Ruiz"]
        due = (utc_now().date() + timedelta(days=30)).isoformat()
        action = issues.add_action(
            session, steward, issue, title="Turn on a second factor for every account",
            owner_id=steward.account_id, due_on=due, contact_id=contact.id,
        )  # fmt: skip
        assert action.contact_id == contact.id
        listed = issues.actions_of(session, steward, issue)
        assert listed[0]["contact"] == {"name": "Ana Ruiz", "third_party": "Tallyfield Surveys"}
        # A contact at a third party the issue is not about cannot be given it.
        other = a_party(session, steward, people, name="Swiftcold Logistics")
        stranger = contacts.add(session, steward, other,
                                {"name": "Bo Lind", "email": "bo@swiftcold.example"})  # fmt: skip
        with pytest.raises(Invalid):
            issues.add_action(session, steward, issue, title="x", owner_id=steward.account_id,
                              due_on=due, contact_id=stranger.id)  # fmt: skip


def test_offboarding_retires_a_third_party_only_when_every_step_is_recorded(
    db: Database, people: People
) -> None:
    steward, member = who(db, people, "steward"), who(db, people, "member")
    with db.write(steward.actor) as session:
        party = a_party(session, steward, people)
        service = records.create(session, steward, SERVICE, {
            "name": "Hosted surveys", "kind": "software_service",
            "org_unit_id": people.units["IMM"], "third_party": party.ref})  # fmt: skip
        with pytest.raises(PermissionDenied):
            lifecycle.start(session, member, party, "x")
        with pytest.raises(Invalid):
            lifecycle.start(session, steward, party, "")
        lifecycle.start(session, steward, party, "Surveys move to the institute's own platform.")
        with pytest.raises(Conflict):
            lifecycle.start(session, steward, party, "Again.")
        keys = [key for key, _, _ in lifecycle.STEPS]
        for key in keys[:-1]:
            lifecycle.record_step(session, steward, party, key, f"Done: {key}.")
            assert party.status == "active" and service.status == "active"
        with pytest.raises(Conflict):
            lifecycle.record_step(session, steward, party, keys[0], "Twice.")
        with pytest.raises(Invalid):
            lifecycle.record_step(session, steward, party, keys[-1], "")
        lifecycle.record_step(session, steward, party, keys[-1], "Their letter of 2 March.")
        assert party.status == "retired" and service.status == "retired"
        assert party.next_review_on is None
        shown = records.detail(session, steward, THIRD_PARTY, party)["offboarding"]
        assert shown["status"] == "done" and all(step["done_by"] for step in shown["steps"])
        titles = [e["title"] for e in history.for_record(session, THIRD_PARTY, party)]
        assert "Recorded: Its attestation recorded. Their letter of 2 March." in titles


def test_a_subcontractor_appears_on_both_and_in_the_picture_of_connections(
    db: Database, people: People
) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        host = a_party(session, steward, people, name="Pellham Clinical Systems")
        cloud = a_party(session, steward, people, name="Quillon Cloud")
        links.add(session, steward, THIRD_PARTY, host, "subcontracts", THIRD_PARTY, cloud)
        mine = links.of(session, steward, THIRD_PARTY, cloud)
        assert [(row["label"], row["record"]["ref"]) for row in mine["incoming"]] == [
            ("Is a subcontractor of", host.ref)
        ]
        groups = {g["key"]: g for g in graph.around(session, steward, THIRD_PARTY, host)["groups"]}
        assert [r["ref"] for r in groups["subcontracts:out"]["records"]] == [cloud.ref]


def test_lifecycle_through_the_api(as_role: Clients, people: People, db: Database) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        party = a_party(session, steward, people)
        review, contact = answered(session, steward, party)
        ref, review_ref = party.ref, review.ref
    keeper, member = as_role("steward"), as_role("member")
    what = {"event": "incident", "note": "Ransomware at the host, 2 March."}
    called = keeper.post(f"/api/v1/third-parties/{ref}/call-review", json=what)
    assert called.status_code == 200 and called.json()["data"]["review_called"]
    assert member.post(f"/api/v1/third-parties/{ref}/call-review",
                       json={"event": "incident", "note": "x"}).status_code == 403  # fmt: skip
    found = keeper.post(f"/api/v1/reviews/{review_ref}/findings",
                        json={"name": "No second factor", "severity": "high"})  # fmt: skip
    assert found.status_code == 201, found.text
    issue = found.json()["data"]
    added = keeper.post(f"/api/v1/issues/{issue['ref']}/actions", json={
        "title": "Second factor everywhere", "owner_id": people.accounts["steward"],
        "due_on": (utc_now().date() + timedelta(days=20)).isoformat(),
        "contact_id": contact.id})  # fmt: skip
    assert added.status_code == 201 and added.json()["data"]["contact"]["name"] == "Ana Ruiz"
    started = keeper.post(f"/api/v1/third-parties/{ref}/offboarding",
                          json={"reason": "Moving in-house."})  # fmt: skip
    assert started.json()["data"]["offboarding"]["status"] == "open"
    step = keeper.post(f"/api/v1/third-parties/{ref}/offboarding/steps/access",
                       json={"note": "Accounts removed."})  # fmt: skip
    assert step.status_code == 200
    stopped = keeper.post(f"/api/v1/third-parties/{ref}/offboarding/cancel", json={"note": "No."})
    assert stopped.json()["data"]["offboarding"]["status"] == "cancelled"
