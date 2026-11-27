"""Coverage: an agreement names the third parties it is with and what it covers, and wherever
regulated information is shared with a third party and no agreement of a kind the program
requires covers it, every record involved shows a stop until one does."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from riskwren.compliance import agreements
from riskwren.compliance.agreements import AGREEMENT
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid
from riskwren.db.engine import Database
from riskwren.inventory import history, links, records
from riskwren.inventory.registry import INFORMATION, THIRD_PARTY
from riskwren.thirdparty import coverage
from riskwren.thirdparty.services import SERVICE
from tests.people import People
from tests.test_risks import who

Clients = Callable[[str | None], TestClient]


def sharing(db: Database, people: People) -> dict[str, str]:
    """A clinic's patient records, handled by a laboratory's testing service."""
    steward = who(db, people, "steward")
    imm = people.units["IMM"]
    with db.write(steward.actor) as session:
        records_ = records.create(session, steward, INFORMATION, {
            "name": "Patient records", "kind": "patient_records", "data_class": "restricted",
            "org_unit_id": imm})  # fmt: skip
        lab = records.create(
            session,
            steward,
            THIRD_PARTY,
            {
                "name": "Lakeshore Reference Laboratory",
                "kind": "service_provider",
                "org_unit_id": imm,
            },
        )
        testing = records.create(session, steward, SERVICE, {
            "name": "Reference testing", "kind": "laboratory", "org_unit_id": imm,
            "third_party": lab.ref})  # fmt: skip
        links.add(session, steward, SERVICE, testing, "handles", INFORMATION, records_)
        return {"info": records_.ref, "lab": lab.ref, "service": testing.ref}


def stops_on(session: Any, principal: Any, refs: dict[str, str]) -> dict[str, list[str]]:
    out = {}
    for key, record_type in (("info", INFORMATION), ("lab", THIRD_PARTY), ("service", SERVICE)):
        record = records.load(session, principal, record_type, refs[key])
        found = records.detail(session, principal, record_type, record)["stops"]
        out[key] = sorted(need["rule"] for stop in found for need in stop["needs"])
    return out


def an_agreement(session: Any, principal: Any, people: People, kind: str, **more: Any) -> Any:
    return records.create(session, principal, AGREEMENT, {
        "name": f"A {kind} agreement", "kind": kind, "parties": "The laboratory",
        "org_unit_id": people.units["IMM"], **more})  # fmt: skip


def test_every_record_shows_the_stop_until_an_agreement_of_a_required_kind_covers_it(
    db: Database, people: People
) -> None:
    refs = sharing(db, people)
    steward = who(db, people, "steward")
    both = ["health_information", "restricted"]
    with db.write(steward.actor) as session:
        assert stops_on(session, steward, refs) == {"info": both, "lab": both, "service": both}
        stop = coverage.stops_for(
            session,
            steward,
            "information",
            records.load(session, steward, INFORMATION, refs["info"]).id,
        )[0]
        assert stop["service"]["ref"] == refs["service"]
        assert "business associate agreement" in stop["needs"][0]["kinds_words"]
        # A contract with the laboratory covering the service meets the rule for restricted
        # information, and not the one for health information.
        contract = an_agreement(session, steward, people, "contract")
        coverage.set_parties(session, steward, contract, [refs["lab"]])
        agreements.set_coverage(session, steward, contract, [refs["service"]])
        one = ["health_information"]
        assert stops_on(session, steward, refs) == {"info": one, "lab": one, "service": one}
        # A business associate agreement that is not with the laboratory meets nothing.
        baa = an_agreement(session, steward, people, "business_associate")
        agreements.set_coverage(session, steward, baa, [refs["info"]])
        assert stops_on(session, steward, refs)["lab"] == one
        # With it, every stop goes, everywhere.
        coverage.set_parties(session, steward, baa, [refs["lab"]])
        assert stops_on(session, steward, refs) == {"info": [], "lab": [], "service": []}
        assert coverage.all_stops(session, steward) == []
        titles = [entry["title"] for entry in history.for_record(session, AGREEMENT, baa)]
        assert titles[0] == f"Now with {refs['lab']} Lakeshore Reference Laboratory"
        # One that has ended covers nothing, though it is still open.
        records.update(session, steward, AGREEMENT, baa, {
            "starts_on": (utc_now().date() - timedelta(days=400)).isoformat(),
            "ends_on": (utc_now().date() - timedelta(days=1)).isoformat()},
            version=baa.version)  # fmt: skip
        assert stops_on(session, steward, refs)["info"] == one
        agreements.close(session, steward, baa, "Ended.")
        assert stops_on(session, steward, refs)["service"] == one


def test_what_is_shared_directly_and_with_partners_needs_its_own_kinds(
    db: Database, people: People
) -> None:
    steward = who(db, people, "steward")
    imm = people.units["IMM"]
    with db.write(steward.actor) as session:
        cohort = records.create(session, steward, INFORMATION, {
            "name": "Cohort survey responses", "kind": "participant_data",
            "data_class": "confidential", "org_unit_id": imm})  # fmt: skip
        partner = records.create(
            session,
            steward,
            THIRD_PARTY,
            {"name": "Calder Bay University", "kind": "collaborator", "org_unit_id": imm},
        )
        links.add(session, steward, INFORMATION, cohort, "shared_with", THIRD_PARTY, partner)
        found = coverage.stops_for(session, steward, "third_party", partner.id)
        assert [([n["rule"] for n in s["needs"]], s["service"]) for s in found] == [
            (["participant_data"], None)
        ]
        memo = an_agreement(session, steward, people, "memorandum")
        coverage.set_parties(session, steward, memo, [partner.ref])
        agreements.set_coverage(session, steward, memo, [cohort.ref])
        found = coverage.stops_for(session, steward, "third_party", partner.id)
        assert [a["ref"] for a in found[0]["agreements"]] == [memo.ref]  # with it, not meeting it
        dua = an_agreement(session, steward, people, "data_use")
        coverage.set_parties(session, steward, dua, [partner.ref])
        agreements.set_coverage(session, steward, dua, [cohort.ref])
        assert coverage.stops_for(session, steward, "third_party", partner.id) == []
        # Retired information is no longer shared.
        records.update(session, steward, INFORMATION, cohort, {"status": "retired"},
                       version=cohort.version)  # fmt: skip
        assert coverage.shared(session) == []


def test_the_sharing_rules_are_checked_and_travel_with_the_program(
    db: Database, people: People
) -> None:
    from riskwren.program import packs, rules

    manager = who(db, people, "manager")
    with db.write(manager.actor) as session:
        table = rules.get(session, "sharing")
        assert coverage.problems(table) == []
        assert coverage.problems({"rules": [{"key": "x", "reason": "x", "when": {},
                                             "kinds": ["handshake"]}]})  # fmt: skip
        pack = packs.export(session)
        assert [rule["key"] for rule in pack["sharing"]["rules"]] == [
            "health_information",
            "participant_data",
            "controlled_data",
            "restricted",
        ]
        pack["sharing"]["rules"][0]["kinds"] = ["nonsense"]
        with pytest.raises(Invalid):
            packs.import_(session, manager, pack)


def test_coverage_through_the_api(as_role: Clients, people: People, db: Database) -> None:
    refs = sharing(db, people)
    steward, member = as_role("steward"), as_role("member")
    listed = member.get("/api/v1/coverage").json()["data"]
    assert [
        (s["information"]["ref"], [n["rule"] for n in s["needs"]]) for s in listed["stops"]
    ] == [(refs["info"], ["health_information", "restricted"])]
    made = steward.post("/api/v1/agreements", json={
        "name": "Business associate agreement", "kind": "business_associate",
        "parties": "Lakeshore", "org_unit_id": people.units["IMM"]}).json()["data"]  # fmt: skip
    assert steward.put(f"/api/v1/agreements/{made['ref']}/covers",
                       json={"covers": [refs["service"]]}).status_code == 200  # fmt: skip
    with_lab = steward.put(f"/api/v1/agreements/{made['ref']}/parties",
                           json={"parties": [refs["lab"]]})  # fmt: skip
    assert with_lab.status_code == 200
    assert [p["ref"] for p in with_lab.json()["data"]["with"]] == [refs["lab"]]
    assert (
        member.put(f"/api/v1/agreements/{made['ref']}/parties", json={"parties": []}).status_code
        == 404
    )  # fmt: skip
    assert member.get("/api/v1/coverage").json()["data"]["stops"] == []
    party = steward.get(f"/api/v1/third-parties/{refs['lab']}").json()["data"]
    assert [a["ref"] for a in party["agreements"]] == [made["ref"]] and party["stops"] == []
