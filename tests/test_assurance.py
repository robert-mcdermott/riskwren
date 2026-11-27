"""Assurance documents: reports and certificates about a third party, held as evidence with
their period and expiry, and read for what they cover, what they found, and what they leave
to the organization, joined to the controls that do it."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from riskwren.compliance import evidence as evidence_service
from riskwren.controls.service import CONTROL
from riskwren.core.clock import frozen_at, utc_now
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.db.engine import Database
from riskwren.inventory import records
from riskwren.inventory.registry import THIRD_PARTY
from riskwren.thirdparty import assurance, contacts, respondent, reviews, tiering
from riskwren.thirdparty.services import SERVICE
from tests.people import People
from tests.test_risks import who
from tests.test_treatment import add_control

Clients = Callable[[str | None], TestClient]
PDF = b"%PDF-1.7\n1 0 obj << >> endobj\ntrailer << >>\n%%EOF\n"


def a_supplier(db: Database, people: People) -> dict[str, str]:
    """A host with two services, a report that covers one of them, and a control here."""
    steward = who(db, people, "steward")
    imm = people.units["IMM"]
    with db.write(steward.actor) as session:
        party = records.create(
            session,
            steward,
            THIRD_PARTY,
            {"name": "Quillon Cloud", "kind": "service_provider", "org_unit_id": imm},
        )
        sign_in = records.create(session, steward, SERVICE, {
            "name": "Identity and sign-in", "kind": "software_service", "org_unit_id": imm,
            "third_party": party.ref})  # fmt: skip
        mail = records.create(session, steward, SERVICE, {
            "name": "Email", "kind": "software_service", "org_unit_id": imm,
            "third_party": party.ref})  # fmt: skip
        control = add_control(session, steward, imm, "Second factor for every account")
        today = utc_now().date()
        report = assurance.add(session, steward, party, {
            "name": "SOC 2 Type II report, 2026",
            "covers_from": (today - timedelta(days=400)).isoformat(),
            "covers_to": (today - timedelta(days=35)).isoformat(),
            "collected_on": (today - timedelta(days=20)).isoformat(),
            "valid_until": (today + timedelta(days=330)).isoformat()})  # fmt: skip
        return {"party": party.ref, "sign_in": sign_in.ref, "mail": mail.ref,
                "control": control.ref, "report": report.ref}  # fmt: skip


def a_review(**more: object) -> dict[str, object]:
    return {
        "kind": "soc2_type2", "issuer": "Wexford Assurance", "opinion": "qualified",
        "carve_outs": "The data centres it runs in are carved out.",
        "exceptions": [{"control": "CC6.2", "description": "Two leavers kept access for 40 days.",
                        "matters": True, "response": "Our own leavers are removed by us."}],
        "reliance": "partly", "note": "Access removal at the supplier is weak; ours covers it.",
        **more,
    }  # fmt: skip


def test_a_review_records_scope_exceptions_and_the_organizations_own_part(
    db: Database, people: People
) -> None:
    refs = a_supplier(db, people)
    steward, member = who(db, people, "steward"), who(db, people, "member")
    with db.write(steward.actor) as session:
        party = records.load(session, steward, THIRD_PARTY, refs["party"])
        report = assurance.find_document(session, refs["report"])
        duties = [{"text": "Customers require a second factor for their own users.",
                   "control": refs["control"], "status": "in_place"},
                  {"text": "Customers review their administrators each quarter.",
                   "status": "not_in_place"}]  # fmt: skip
        for wrong, field in [
            ({"kind": "brochure"}, "kind"),
            ({"reliance": "partly", "note": None}, "note"),
            ({"services": ["SVC-0999"]}, "services"),
            ({"responsibilities": [{"text": "x", "control": "CTL-0999"}]}, "responsibilities"),
            ({"responsibilities": [{"text": "x", "status": "in_place"}]}, "responsibilities"),
            ({"exceptions": [{"control": "CC1.1"}]}, "exceptions"),
        ]:
            with pytest.raises(Invalid) as caught:
                assurance.record(session, steward, report, party, a_review(**wrong))
            assert field in caught.value.errors, (wrong, caught.value.errors)
        with pytest.raises(PermissionDenied):
            assurance.record(session, member, report, party, a_review())
        wanted = a_review(services=[refs["sign_in"]], responsibilities=duties)
        made = assurance.record(session, steward, report, party, wanted)
        shown = assurance.view(session, steward, made, party)
        assert [row["ref"] for row in shown["covers"]] == [refs["sign_in"]]
        assert [row["ref"] for row in shown["misses"]] == [refs["mail"]]
        assert shown["exceptions"][0]["matters"] is True
        assert [(d["control"] or {}).get("ref") for d in shown["responsibilities"]] == [
            refs["control"], None]  # fmt: skip
        # The control shows what a third party's report leaves to it.
        control = records.load(session, steward, CONTROL, refs["control"])
        detail = records.detail(session, steward, CONTROL, control)
        relied = [
            (r["third_party"]["ref"], r["document"]["ref"]) for r in detail["responsibilities"]
        ]
        assert relied == [(refs["party"], refs["report"])]
        # Reviewing again supersedes, and the control follows the review in force.
        again = assurance.record(session, steward, report, party,
                                 a_review(reliance="relies", note=None))  # fmt: skip
        assert made.superseded_by == again.id
        assert records.detail(session, steward, CONTROL, control)["responsibilities"] == []


def test_a_report_past_its_expiry_no_longer_counts(db: Database, people: People) -> None:
    refs = a_supplier(db, people)
    steward, member = who(db, people, "steward"), who(db, people, "member")
    with db.write(steward.actor) as session:
        party = records.load(session, steward, THIRD_PARTY, refs["party"])
        report = assurance.find_document(session, refs["report"])
        assert assurance.standing(session, party)["current"] == 0  # not reviewed yet
        assurance.record(session, steward, report, party, a_review(reliance="relies", note=None))
        assert assurance.standing(session, party) == {"current": 1, "until": report.valid_until}
        listed = assurance.documents_of(session, steward, party)
        assert listed[0]["state"] == "current" and listed[0]["review"]["reliance"] == "relies"
        # A report is confidential: someone who merely sees the supplier does not see it.
        assert not evidence_service.can_see(session, member, report)
        assert assurance.documents_of(session, member, party) == []
        later = report.valid_until + timedelta(days=1)
        with frozen_at(utc_now().replace(year=later.year, month=later.month, day=later.day)):
            assert assurance.standing(session, party)["current"] == 0
            assert assurance.documents_of(session, steward, party)[0]["state"] == "stale"


def test_a_contact_sends_a_report_with_the_answers(
    as_role: Clients, people: People, db: Database
) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        party = records.create(session, steward, THIRD_PARTY, {
            "name": "Tallyfield Surveys", "kind": "service_provider",
            "org_unit_id": people.units["IMM"]})  # fmt: skip
        tiering.record(session, steward, party, {"information": "internal",
                       "access": ["on_site"], "dependency": "little"}, None, None)  # fmt: skip
        contact = contacts.add(session, steward, party,
                               {"name": "Ana Ruiz", "email": "ana@tallyfield.example"})  # fmt: skip
        review = reviews.start(session, steward, party, {})
        token = reviews.send(session, steward, review, contact_id=contact.id)
        party_ref, review_ref = party.ref, review.ref
    nobody = as_role(None)
    header = {respondent.HEADER: token}
    sent = nobody.post("/api/v1/respond/files", params={"name": "SOC 2 report.pdf"},
                       headers=header, content=PDF)  # fmt: skip
    assert sent.status_code == 201, sent.text
    assert sent.json()["data"]["name"] == "SOC 2 report.pdf"
    bad = nobody.post("/api/v1/respond/files", params={"name": "run.exe"}, headers=header,
                      content=b"MZ\x90\x00 not taken")  # fmt: skip
    assert bad.status_code == 422
    refused = nobody.post("/api/v1/respond/files", headers={respondent.HEADER: "nope"},
                          content=PDF)  # fmt: skip
    assert refused.status_code == 404
    shown = nobody.get("/api/v1/respond", headers=header).json()["data"]
    assert shown["files"] == [{"name": "SOC 2 report.pdf"}]
    # It arrives as evidence of the third party, owned by whoever keeps the review.
    keeper = as_role("steward")
    found = keeper.get(f"/api/v1/third-parties/{party_ref}/assurance").json()["data"]
    (document,) = found["documents"]
    assert document["has_file"] and document["review"] is None
    assert document["name"] == "SOC 2 report.pdf, from Tallyfield Surveys"
    item = keeper.get(f"/api/v1/evidence/{document['ref']}").json()["data"]
    assert [owner["name"] for owner in item["owners"]] == ["Steward Person"]
    assert as_role("member").get(f"/api/v1/evidence/{document['ref']}").status_code == 404
    with db.read() as session:
        assert [row.file_name for row in respondent.sent_files(
            session, reviews.find(session, review_ref))] == ["SOC 2 report.pdf"]  # fmt: skip


def test_assurance_through_the_api(as_role: Clients, people: People, db: Database) -> None:
    refs = a_supplier(db, people)
    steward, member = as_role("steward"), as_role("member")
    kinds = member.get("/api/v1/assurance-kinds").json()["data"]
    assert "soc2_type2" in kinds["kinds"] and "partly" in kinds["reliance"]
    path = f"/api/v1/third-parties/{refs['party']}/assurance"
    until = (date.today() + timedelta(days=700)).isoformat()
    made = steward.post(path, json={"name": "ISO/IEC 27001 certificate", "valid_until": until})
    assert made.status_code == 201, made.text
    assert member.post(path, json={"name": "x"}).status_code == 403
    reviewed = steward.post(f"{path}/{made.json()['data']['ref']}/reviews", json={
        "kind": "iso27001", "opinion": "none", "services": [refs["sign_in"], refs["mail"]],
        "reliance": "relies"})  # fmt: skip
    assert reviewed.status_code == 201, reviewed.text
    assert reviewed.json()["data"]["misses"] == []
    listed = steward.get(path).json()["data"]
    assert listed["standing"]["current"] == 1 and len(listed["documents"]) == 2
