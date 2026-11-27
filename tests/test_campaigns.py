"""Campaigns: who is asked, what each answers, coverage by unit, and what an attestation is
allowed to count for."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren import reminders
from riskwren.compliance import assessments, evidence, scopes
from riskwren.compliance import packs as framework_packs
from riskwren.compliance.scopes import SCOPE
from riskwren.controls.service import CONTROL
from riskwren.core.clock import frozen_at
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import CampaignItem, Notice, TestResult
from riskwren.inventory import records
from riskwren.oversight import campaigns
from riskwren.people import accounts
from riskwren.reporting import service as reporting
from tests.people import ME, People
from tests.test_assessments import FOUND, start, the_test, world
from tests.test_evidence import add_evidence
from tests.test_risks import judge, raise_risk, who
from tests.test_scopes import state_of
from tests.test_treatment import add_control

Clients = Callable[[str | None], TestClient]
NOON = datetime(2026, 3, 2, 12, tzinfo=UTC)
OPERATES = {"operates": "yes", "statement_right": True, "evidence": "yes", "owner_right": True}


@pytest.fixture
def loaded(db: Database, people: People) -> None:
    with db.write(ME.actor) as session:
        framework_packs.install(session)


def owned(session, by, unit: int, name: str, owner: int, **more):  # type: ignore[no-untyped-def]
    control = add_control(session, by, unit, name, **more)
    records.set_owners(session, by, CONTROL, control, [{"account_id": owner, "kind": "owner"}])
    return control


def items_of(session, campaign) -> dict[str, CampaignItem]:  # type: ignore[no-untyped-def]
    rows = session.scalars(select(CampaignItem).where(CampaignItem.campaign_id == campaign.id))
    return {row.subject_name: row for row in rows}


def told(db: Database, account_id: int) -> list[str]:
    with db.read() as session:
        rows = session.scalars(
            select(Notice).where(Notice.account_id == account_id).order_by(Notice.id)
        )
        return [row.text for row in rows]


def test_a_campaign_asks_the_owners_and_tracks_who_has_answered(
    db: Database, people: People
) -> None:
    manager, steward, member = (who(db, people, role) for role in ("manager", "steward", "member"))
    hale, cancer = people.units["HALE"], people.units["CANCER"]
    with db.write(manager.actor) as session, frozen_at(NOON):
        owned(session, manager, hale, "Freezers alarmed", people.accounts["member"])
        owned(session, manager, hale, "Collection split", people.accounts["member"])
        owned(session, manager, cancer, "Doors locked", people.accounts["leader"])
        # A control whose only owner has left: there is nobody to ask, and that should show.
        owned(session, manager, cancer, "Nobody's control", people.accounts["auditor"])
        # Disabling an account now passes its records on (tests/test_tidy.py), so this is
        # set as an installation from before that would have it.
        accounts.get(session, people.accounts["auditor"]).status = "disabled"
        for values, fields in [
            ({"kind": "census", "name": "", "due_on": "soon"}, {"kind", "name", "due_on"}),
            ({"kind": "attestation", "name": "x", "due_on": "2026-03-01"}, {"due_on"}),
            ({"kind": "evidence", "name": "x", "due_on": "2026-04-01"}, {"wanted"}),
            ({"kind": "self_assessment", "name": "x", "due_on": "2026-04-01", "scope": "SCP-1"},
             {"scope"}),
        ]:  # fmt: skip
            with pytest.raises(Invalid) as caught:
                campaigns.launch(session, manager, values)
            assert set(caught.value.errors) == fields
        with pytest.raises(PermissionDenied):
            campaigns.launch(
                session, steward, {"kind": "attestation", "name": "x", "due_on": "2026-04-01"}
            )
        ask = {"kind": "attestation", "name": "Spring attestation", "due_on": "2026-04-01"}
        assert campaigns.preview(session, manager, ask) == {
            "items": 4, "people": 2, "nobody_to_ask": 1, "units": 2,
        }  # fmt: skip
        campaign = campaigns.launch(session, manager, ask)
        assert (campaign.ref, campaign.version_number, campaign.status) == ("CMP-0001", 1, "open")
        seen = campaigns.view(session, manager, campaign)
        assert seen["counts"] == {"pending": 4, "done": 0, "excused": 0, "asked": 4}
        assert seen["nobody_to_ask"] == 1 and seen["answered"] == 0
        assert seen["questionnaire"] == {
            "key": "control-attestation", "title": "Control attestation", "version": 1,
        }  # fmt: skip
    # One notice each, saying how many, and it is on their Home.
    assert told(db, people.accounts["member"])[-1] == (
        "You have been asked for 2 things in Spring attestation, by 2026-04-01"
    )
    with db.write(member.actor) as session, frozen_at(NOON):
        campaign = campaigns.find(session, manager, "CMP-0001")
        mine = [i for i in reporting.home(session, member)["items"] if i["kind"] == "campaign"]
        assert [(i["title"], i["due_on"].isoformat()) for i in mine] == [
            ("Attest CTL-0001 Freezers alarmed", "2026-04-01"),
            ("Attest CTL-0002 Collection split", "2026-04-01"),
        ]
        with pytest.raises(NotFound):  # those asked do not see the whole campaign
            campaigns.find(session, member, "CMP-0001")
        held = items_of(session, campaign)
        item, _ = campaigns.find_item(session, member, held["Freezers alarmed"].id)
        with pytest.raises(NotFound):
            campaigns.find_item(session, member, held["Doors locked"].id)  # someone else's
        asked = campaigns.item_detail(session, member, item, campaign)
        assert asked["can_answer"] and asked["questionnaire"]["document"]["sections"]
        assert asked["about"]["statement"] and asked["campaign"]["can_see"] is False

        with pytest.raises(Invalid) as caught:
            campaigns.answer(session, member, item, campaign, {"operates": "partly"})
        assert "difference" in caught.value.errors
        campaigns.answer(session, member, item, campaign, {"operates": "partly"}, complete=False)
        assert item.status == "pending" and item.response_id is not None  # a draft
        draft = campaigns.item_detail(session, member, item, campaign)["draft"]
        assert draft == {"operates": "partly"}
        campaigns.answer(
            session, member, item, campaign,
            {**OPERATES, "operates": "partly", "difference": "The alarm is off at night."},
        )  # fmt: skip
        assert (item.status, item.outcome, item.completed_by_name) == (
            "done", "partly", "Member Person",
        )  # fmt: skip
        with pytest.raises(Conflict):
            campaigns.answer(session, member, item, campaign, OPERATES)
        second, _ = campaigns.find_item(session, member, held["Collection split"].id)
        elsewhere = {**OPERATES, "owner_right": False, "owner_instead": "Whoever runs bay 3"}
        campaigns.answer(session, member, second, campaign, elsewhere)
    # What needs someone else is told to them: the assessor and the steward, not the asker.
    assert "Member Person says CTL-0001 Freezers alarmed only partly operates as described" in told(
        db, people.accounts["assessor"]
    )
    assert "Member Person says someone else should answer for CTL-0002 Collection split" in told(
        db, people.accounts["steward"]
    )

    with db.write(manager.actor) as session, frozen_at(NOON):
        campaign = campaigns.find(session, manager, "CMP-0001")
        seen = campaigns.view(session, manager, campaign)
        # The acceptance test: coverage by unit is the count of the list behind it.
        coverage = {row["unit"]["name"]: row for row in seen["coverage"]}
        for name, unit in (("Hale Lab", hale), ("Cancer Biology", cancer)):
            behind = [i for i in seen["items"] if i["org_unit_id"] == unit]
            assert coverage[name]["asked"] == len([i for i in behind if i["status"] != "excused"])
            assert coverage[name]["done"] == len([i for i in behind if i["status"] == "done"])
        assert (coverage["Hale Lab"]["answered"], coverage["Cancer Biology"]["answered"]) == (
            100,
            0,
        )
        assert seen["outcomes"] == {"partly": 1, "yes": 1} and seen["answered"] == 50
        assert (
            next(row["unit"]["name"] for row in seen["coverage"]) == "Cancer Biology"
        )  # least first

        assert campaigns.remind(session, manager, campaign) == 1  # only who still owes something
        held = items_of(session, campaign)
        with pytest.raises(Invalid):
            campaigns.excuse(session, manager, held["Nobody's control"], campaign, " ")
        campaigns.excuse(session, manager, held["Nobody's control"], campaign, "Being retired.")
        assert campaigns.view(session, manager, campaign)["counts"]["asked"] == 3
        campaigns.end(session, manager, campaign)
        with pytest.raises(Conflict):
            campaigns.remind(session, manager, campaign)
    assert told(db, people.accounts["leader"])[-1].startswith("Still waiting on you: 1 thing")
    with db.write(who(db, people, "leader").actor) as session, frozen_at(NOON):
        leader = who(db, people, "leader")
        campaign = campaigns.find(session, manager, "CMP-0001")
        item = items_of(session, campaign)["Doors locked"]
        with pytest.raises(Conflict):  # it has ended
            campaigns.answer(session, leader, item, campaign, OPERATES)
        assert reporting.home(session, leader)["items"] == [] or all(
            i["kind"] != "campaign" for i in reporting.home(session, leader)["items"]
        )


def test_an_attested_control_is_never_shown_as_verified(
    db: Database, loaded: None, people: People
) -> None:
    """The acceptance test. An owner's word puts nothing in verified, and can take it out."""
    manager, assessor, leader = (who(db, people, r) for r in ("manager", "assessor", "leader"))
    central_ref = ""

    def read(session):  # type: ignore[no-untyped-def]
        scope = records.load(session, assessor, SCOPE, central_ref)
        found = scopes.statement(session, assessor, scope, "nist-csf")
        row = next(r for r in found["requirements"] if r["code"] == "PR.DS-11")
        return state_of(found, "PR.DS-11"), row["controls"][0]["why"]

    def attest(session, operates: str) -> None:  # type: ignore[no-untyped-def]
        campaign = campaigns.launch(
            session, manager,
            {"kind": "attestation", "name": f"Attest {operates}", "scope": central_ref,
             "due_on": "2027-12-01"},
        )  # fmt: skip
        item = items_of(session, campaign)["Backups"]
        said = {**OPERATES, "operates": operates}
        if operates != "yes":
            said["difference"] = "Restores have not been tried since the storage refresh."
        campaigns.answer(session, leader, item, campaign, said)
        campaigns.end(session, manager, campaign)

    with frozen_at(datetime(2026, 1, 15, 12, tzinfo=UTC)), db.write(manager.actor) as session:
        central, _, backups, _factor = world(session, people, manager)
        central_ref = central.ref
        assert read(session) == ("in_place", "In place, with no test result that still holds")
        attest(session, "yes")
        state, why = read(session)
        assert state == "in_place"  # the owner says so, and that is all
        assert why.startswith("In place, and attested by its owner on 2026-01-15")
        shown = records.detail(session, manager, CONTROL, backups)["attested"]
        assert (shown["operates"], shown["by"]) == ("yes", "Leader Person")
        # Only a test, with evidence, makes it verified.
        made = start(session, manager, central)
        result = assessments.record(
            session, manager, the_test(session, made, backups), design="effective",
            operation="effective", note=FOUND,
        )  # fmt: skip
        item = add_evidence(
            session, manager, people.units["CANCER"], "Restore log",
            collected_on="2026-01-10", valid_until="2026-12-30",
        )  # fmt: skip
        evidence.set_subjects(session, manager, item, [backups.ref])
        result_id = result.id
    with frozen_at(datetime(2026, 1, 16, 12, tzinfo=UTC)), db.write(assessor.actor) as session:
        assessments.review(
            session, assessor, session.get(TestResult, result_id), confirm=True, note=None
        )
        assert read(session)[0] == "verified"
    with frozen_at(datetime(2026, 5, 4, 12, tzinfo=UTC)), db.write(manager.actor) as session:
        attest(session, "partly")  # since the test, its owner says otherwise
        state, why = read(session)
        assert state == "in_place" and "its owner said on 2026-05-04 that it only partly" in why
        assert why.startswith("Tested effective on 2026-01-16")


def test_other_kinds_ask_the_right_people_and_have_their_effect(
    db: Database, people: People
) -> None:
    manager, steward, member = (who(db, people, role) for role in ("manager", "steward", "member"))
    hale, immuno = people.units["HALE"], people.units["IMM"]
    with db.write(steward.actor) as session, frozen_at(NOON):
        risk = raise_risk(session, steward, hale)  # the steward raised it, and owns it
        judge(session, steward, risk, "inherent", 3, mission=3)
    with db.write(manager.actor) as session, frozen_at(NOON):
        risks = campaigns.launch(
            session, manager,
            {"kind": "self_assessment", "name": "Risks, spring", "due_on": "2026-04-01",
             "org_unit_id": immuno},
        )  # fmt: skip
        assert [(i.subject_ref, i.account_name) for i in items_of(session, risks).values()] == [
            ("RSK-0001", "Steward Person")
        ]
        units_ = campaigns.launch(
            session, manager, {"kind": "completeness", "name": "Records", "due_on": "2026-04-01"}
        )
        # A unit with a steward is asked; the steward is for Immunology only.
        assert [(i.subject_name, i.account_name) for i in items_of(session, units_).values()] == [
            ("Immunology", "Steward Person")
        ]
        with pytest.raises(Invalid) as caught:  # no systems are on record here
            campaigns.launch(
                session, manager, {"kind": "profile", "name": "x", "due_on": "2026-04-01"}
            )
        assert caught.value.errors == {"kind": "There is nobody to ask."}
    with db.write(steward.actor) as session, frozen_at(NOON):
        risks = campaigns.find(session, manager, "CMP-0001")
        item = next(iter(items_of(session, risks).values()))
        with pytest.raises(PermissionDenied):
            campaigns.answer(session, member, item, risks, {"relevant": True})
        campaigns.answer(
            session, steward, item, risks,
            {"relevant": True, "changed": ["controls"], "what_changed": "The alarm was replaced.",
             "controls_working": "yes", "rating_right": False,
             "rating_note": "Lower: the new alarm calls three people.", "plan": "none"},
        )  # fmt: skip
        assert item.outcome == "rating_not_right"
        units_ = campaigns.find(session, manager, "CMP-0002")
        check = next(iter(items_of(session, units_).values()))
        campaigns.answer(
            session, steward, check, units_,
            {"complete": "yes", "new_this_year": False, "retired": False, "owners_right": True,
             "unrecorded": True, "unrecorded_detail": "The minus-eighty in bay 3 is failing."},
        )  # fmt: skip
        assert check.outcome == "gaps"
    for_manager = told(db, people.accounts["manager"])
    assert "Steward Person says the rating of RSK-0001 Freezer failure is no longer right" in (
        for_manager
    )
    assert "Steward Person says the records of Immunology need attention" in for_manager


def test_an_evidence_request_closes_when_the_evidence_is_attached(
    db: Database, people: People
) -> None:
    manager, member = who(db, people, "manager"), who(db, people, "member")
    hale = people.units["HALE"]
    with db.write(manager.actor) as session, frozen_at(NOON):
        control = owned(session, manager, hale, "Freezers alarmed", people.accounts["member"])
        old = add_evidence(session, manager, hale, "Last year's log", collected_on="2025-03-01")
        evidence.set_subjects(session, manager, old, [control.ref])
        campaign = campaigns.launch(
            session, manager,
            {"kind": "evidence", "name": "Alarm tests", "due_on": "2026-04-01",
             "wanted": "This quarter's alarm test log, signed."},
        )  # fmt: skip
        item = items_of(session, campaign)["Freezers alarmed"]
        with pytest.raises(Conflict):  # nothing to answer: it wants evidence
            campaigns.answer(session, member, item, campaign, {})
        assert campaigns.refresh(session, campaign) == 0  # what was there before does not count
    with db.write(member.actor) as session, frozen_at(datetime(2026, 3, 9, 12, tzinfo=UTC)):
        control = records.load(session, member, CONTROL, "CTL-0001")
        new = add_evidence(session, member, hale, "Alarm test log, Q1", collected_on="2026-03-09")
        evidence.set_subjects(session, manager, new, [control.ref])
    with db.write(manager.actor) as session, frozen_at(datetime(2026, 3, 9, 13, tzinfo=UTC)):
        assert campaigns.refresh_all(session) == 1
        campaign = campaigns.find(session, manager, "CMP-0001")
        item = items_of(session, campaign)["Freezers alarmed"]
        assert (item.status, item.outcome) == ("done", "attached") and item.evidence_id == new.id


def test_what_a_campaign_still_wants_is_reminded_of(db: Database, people: People) -> None:
    manager = who(db, people, "manager")
    with db.write(manager.actor) as session, frozen_at(NOON):
        owned(session, manager, people.units["HALE"], "Freezers alarmed", people.accounts["member"])
        campaigns.launch(
            session, manager,
            {"kind": "attestation", "name": "Spring attestation", "due_on": "2026-04-01"},
        )  # fmt: skip
    with frozen_at(datetime(2026, 3, 25, 9, tzinfo=UTC)), db.bookkeeping() as session:
        assert reminders.send(session)["reminders"] == 1
    assert told(db, people.accounts["member"])[-1] == (
        "Due in 7 days: Spring attestation: CTL-0001 Freezers alarmed"
    )
    with frozen_at(datetime(2026, 4, 9, 9, tzinfo=UTC)), db.bookkeeping() as session:
        assert reminders.send(session)["escalated"] == 1  # a week late: to the steward
    assert "now with you: Spring attestation" in told(db, people.accounts["steward"])[-1]


def test_campaigns_through_the_api(as_role: Clients, people: People, db: Database) -> None:
    manager = who(db, people, "manager")
    with db.write(manager.actor) as session:
        owned(session, manager, people.units["HALE"], "Freezers alarmed", people.accounts["member"])
    boss, member = as_role("manager"), as_role("member")
    listed = boss.get("/api/v1/campaigns").json()["data"]
    assert listed["campaigns"] == [] and listed["can_start"] and len(listed["kinds"]) == 5
    assert member.get("/api/v1/campaigns").json()["data"]["can_start"] is False
    ask = {"kind": "attestation", "name": "Attest", "due_on": "2099-01-01"}
    assert member.post("/api/v1/campaigns", json=ask).status_code == 403
    assert boss.post("/api/v1/campaigns/preview", json=ask).json()["data"]["items"] == 1
    made = boss.post("/api/v1/campaigns", json=ask)
    assert made.status_code == 201 and made.json()["data"]["ref"] == "CMP-0001"
    item = made.json()["data"]["items"][0]
    assert item["subject"]["href"] == "/controls/CTL-0001" and item["asked"] == "Member Person"
    assert member.get("/api/v1/campaigns/CMP-0001").status_code == 404
    assert as_role("auditor").get("/api/v1/campaigns/CMP-0001").status_code == 200

    asked = member.get(f"/api/v1/campaign-items/{item['id']}").json()["data"]
    assert asked["can_answer"] and asked["campaign"]["name"] == "Attest"
    assert as_role("steward").get(f"/api/v1/campaign-items/{item['id']}").status_code == 404
    short = member.post(f"/api/v1/campaign-items/{item['id']}/answer", json={"answers": {}})
    assert short.status_code == 422
    done = member.post(f"/api/v1/campaign-items/{item['id']}/answer", json={"answers": OPERATES})
    assert done.json()["data"]["status"] == "done"
    assert done.json()["data"]["as_asked"][0]["questions"][0]["said"] == "Yes"
    seen = boss.get("/api/v1/campaigns/CMP-0001").json()["data"]
    assert seen["answered"] == 100 and seen["outcomes"] == {"yes": 1}
    control = member.get("/api/v1/controls/CTL-0001").json()["data"]
    assert control["attested"]["operates"] == "yes" and control["attested"]["by"] == "Member Person"
    assert boss.post("/api/v1/campaigns/CMP-0001/close").json()["data"]["status"] == "closed"
    assert boss.post("/api/v1/campaigns/CMP-0001/cancel").status_code == 409
