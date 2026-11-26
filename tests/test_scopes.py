"""Scopes: a boundary, the frameworks it is held to, applicability with reasons,
implementations, inherited controls, and the statement of applicability. And information
assets, the fourth kind of inventory record."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.compliance import packs, scopes
from riskwren.compliance.scopes import SCOPE
from riskwren.controls.service import CONTROL
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import Event, ScopeRequirement
from riskwren.inventory import history, links, records
from riskwren.inventory.registry import INFORMATION, SYSTEM, THIRD_PARTY
from tests.conftest import TESTER
from tests.people import People
from tests.test_risks import who
from tests.test_treatment import add_control

Clients = Callable[[str | None], TestClient]


@pytest.fixture
def loaded(db: Database, people: People) -> None:
    with db.write(TESTER) as session:
        packs.install(session)


def add_scope(session, by, unit: int, name: str, **more):  # type: ignore[no-untyped-def]
    return records.create(session, by, SCOPE, {"name": name, "org_unit_id": unit, **more})


def state_of(found: dict, code: str) -> str:  # type: ignore[type-arg]
    return next(row["state"] for row in found["requirements"] if row["code"] == code)


# --- Information assets ---------------------------------------------------------------------


def test_information_is_recorded_and_linked_like_the_rest_of_the_inventory(
    db: Database, people: People
) -> None:
    steward = who(db, people, "steward")
    hale = people.units["HALE"]
    with db.write(steward.actor) as session:
        data = records.create(
            session, steward, INFORMATION,
            {"name": "Cohort survey responses", "kind": "participant_data", "org_unit_id": hale,
             "criticality": "high", "data_class": "restricted",
             "held_in": "The cohort database.", "agreement": "Consent form version 4"},
        )  # fmt: skip
        assert data.ref == "INF-0001"
        store = records.create(
            session, steward, SYSTEM,
            {"name": "Cohort database", "kind": "data_store", "org_unit_id": hale},
        )  # fmt: skip
        trust = records.create(
            session, steward, THIRD_PARTY,
            {"name": "Open Cohort Trust", "kind": "collaborator", "org_unit_id": hale},
        )  # fmt: skip
        links.add(session, steward, SYSTEM, store, "holds", INFORMATION, data)
        links.add(session, steward, INFORMATION, data, "shared_with", THIRD_PARTY, trust)
        with pytest.raises(Invalid):
            links.add(session, steward, INFORMATION, data, "relies_on", SYSTEM, store)
        seen = links.of(session, steward, INFORMATION, data)
        told = {(e["label"], e["record"]["ref"]) for e in seen["outgoing"] + seen["incoming"]}
        assert told == {("Is held in", store.ref), ("Is shared with", trust.ref)}
        with pytest.raises(Invalid) as bad:
            records.create(
                session, steward, INFORMATION, {"name": "x", "kind": "gossip", "org_unit_id": hale}
            )
        assert "kind" in bad.value.errors
    with db.read() as session:
        # Open, like the rest of the inventory: a member of another unit can find it.
        member = who(db, people, "member")
        assert (
            records.detail(session, member, INFORMATION, data)["held_in"] == "The cohort database."
        )


# --- A scope --------------------------------------------------------------------------------


def test_a_scope_has_a_boundary_and_is_held_to_frameworks(
    db: Database, loaded: None, people: People
) -> None:
    steward, member = who(db, people, "steward"), who(db, people, "member")
    hale = people.units["HALE"]
    with db.write(steward.actor) as session:
        scope = add_scope(session, steward, hale, "The enclave", boundary="Racks 4 to 6.")
        assert scope.ref == "SCP-0001" and not scope.offers_controls
        store = records.create(
            session,
            steward,
            SYSTEM,
            {"name": "Enclave storage", "kind": "platform", "org_unit_id": hale},
        )
        scopes.set_members(session, steward, scope, [store.ref], [hale])
        scopes.hold_to(session, steward, scope, "nist-800-53", "moderate")
        scopes.hold_to(session, steward, scope, "nist-800-171", None)
        with pytest.raises(Invalid) as bad:
            scopes.hold_to(session, steward, scope, "nist-csf", "moderate")
        assert "baseline" in bad.value.errors
        with pytest.raises(Invalid):
            scopes.set_members(session, steward, scope, ["RSK-0001"], [])
        with pytest.raises(PermissionDenied):
            scopes.hold_to(session, member, scope, "nist-csf", None)
        seen = records.detail(session, steward, SCOPE, scope)
        assert seen["members"]["units"][0]["id"] == hale
        assert [r["ref"] for r in seen["members"]["records"]] == [store.ref]
        assert [(h["key"], h["baseline"] and h["baseline"]["key"]) for h in seen["held_to"]] == [
            ("nist-800-171", None), ("nist-800-53", "moderate"),
        ]  # fmt: skip
        scopes.hold_to(session, steward, scope, "nist-800-53", "low")  # a change of baseline
        scopes.release_from(session, steward, scope, "nist-800-171")
        assert [h["key"] for h in scopes.held_to(session, scope)] == ["nist-800-53"]
        told = [item["title"] for item in history.for_record(session, SCOPE, scope)]
        assert told  # the boundary and the frameworks are part of the scope's history


def test_leaving_a_requirement_out_needs_a_reason_and_a_baseline_is_the_starting_point(
    db: Database, loaded: None, people: People
) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        scope = add_scope(session, steward, people.units["HALE"], "Clinic systems")
        scopes.hold_to(session, steward, scope, "nist-800-53", "low")
        found = scopes.statement(session, steward, scope, "nist-800-53")
        assert found["applicable"] == 149 and found["counts"]["gap"] == 149
        assert found["baseline"]["key"] == "low"
        # Outside the baseline, and nobody has said otherwise: not listed at all.
        assert "AC-2(3)" not in {row["code"] for row in found["requirements"]}

        with pytest.raises(Invalid) as bad:
            scopes.decide(session, steward, scope, framework="nist-800-53", code="AC-18",
                          applicable=False, reason="  ")  # fmt: skip
        assert "reason" in bad.value.errors
        scopes.decide(session, steward, scope, framework="nist-800-53", code="AC-18",
                      applicable=False, reason="The clinic has no wireless network.")  # fmt: skip
        scopes.decide(session, steward, scope, framework="nist-800-53", code="AC-2(3)",
                      applicable=True, reason=None)  # fmt: skip
        with pytest.raises(Invalid) as heading:
            scopes.decide(session, steward, scope, framework="nist-800-53", code="AC",
                          applicable=False, reason="x")  # fmt: skip
        assert "heading" in heading.value.errors["code"]
        with pytest.raises(NotFound):
            scopes.decide(session, steward, scope, framework="nist-csf", code="GV.OC-01",
                          applicable=False, reason="x")  # fmt: skip

        found = scopes.statement(session, steward, scope, "nist-800-53")
        assert found["applicable"] == 149 and found["counts"]["excluded"] == 1
        left_out = next(row for row in found["requirements"] if row["code"] == "AC-18")
        assert (left_out["state"], left_out["reason"]) == (
            "excluded", "The clinic has no wireless network.",
        )  # fmt: skip
        assert left_out["decided_by"] == steward.name and left_out["in_baseline"]
        brought_in = next(row for row in found["requirements"] if row["code"] == "AC-2(3)")
        assert brought_in["applicable"] and not brought_in["in_baseline"]
        only = scopes.statement(session, steward, scope, "nist-800-53", state="excluded")
        assert [row["code"] for row in only["requirements"]] == ["AC-18"]

        # Putting a decision back to where the scope started leaves nothing behind.
        scopes.decide(session, steward, scope, framework="nist-800-53", code="AC-18",
                      applicable=True, reason=None)  # fmt: skip
        scopes.decide(session, steward, scope, framework="nist-800-53", code="AC-2(3)",
                      applicable=False, reason="Not needed after all.")  # fmt: skip
        assert session.scalars(select(ScopeRequirement)).first() is None
        events = session.scalars(
            select(Event).where(Event.subject_type == "scope_requirement").order_by(Event.id)
        ).all()
        assert [e.action for e in events] == ["created", "created", "deleted", "deleted"]


def test_a_requirement_is_a_gap_until_a_control_that_answers_it_is_used_and_in_place(
    db: Database, loaded: None, people: People
) -> None:
    steward = who(db, people, "steward")
    hale = people.units["HALE"]
    with db.write(steward.actor) as session:
        scope = add_scope(session, steward, hale, "Clinic systems")
        scopes.hold_to(session, steward, scope, "nist-csf", None)
        factor = add_control(session, steward, hale, "Second factor", library_key="second_factor")
        review = add_control(
            session, steward, hale, "Access reviewed", library_key="access_reviewed"
        )
        leave = add_control(
            session, steward, hale, "Leavers", library_key="access_removed_on_leaving"
        )
        offered = scopes.candidates(session, steward, scope)
        assert {c["ref"]: c["answers"] for c in offered} == {
            factor.ref: 1, review.ref: 1, leave.ref: 3,
        }  # fmt: skip
        first = scopes.statement(session, steward, scope, "nist-csf")
        assert state_of(first, "PR.AA-05") == "gap"
        # In the order of the document, not the order the rows were written.
        assert [row["code"] for row in first["requirements"]][:6] == [
            "GV.OC-01", "GV.OC-02", "GV.OC-03", "GV.OC-04", "GV.OC-05", "GV.OV-01",
        ]  # fmt: skip

        with pytest.raises(Invalid) as bad:
            scopes.implement(session, steward, scope, review, status="done")
        assert "status" in bad.value.errors
        scopes.implement(session, steward, scope, review, status="in_place",
                         responsibility="Clinic manager", statement="Reviewed each March.")  # fmt: skip
        found = scopes.statement(session, steward, scope, "nist-csf")
        assert state_of(found, "PR.AA-05") == "in_place"
        assert found["counts"] == {
            "failing": 0, "gap": 105, "planned": 0, "in_place": 1, "verified": 0, "excluded": 0,
        }  # fmt: skip
        # A second control answering the same requirement, not yet in place, holds it back.
        scopes.implement(session, steward, scope, leave, status="partly")
        found = scopes.statement(session, steward, scope, "nist-csf")
        assert state_of(found, "PR.AA-05") == "planned" and state_of(found, "PR.AA-01") == "planned"
        row = next(r for r in found["requirements"] if r["code"] == "PR.AA-05")
        assert [(c["ref"], c["standing"]) for c in row["controls"]] == [
            (review.ref, "in_place"), (leave.ref, "partly"),
        ]  # fmt: skip
        # A control marked as not applicable here answers nothing.
        scopes.implement(session, steward, scope, leave, status="not_applicable")
        found = scopes.statement(session, steward, scope, "nist-csf")
        assert state_of(found, "PR.AA-05") == "in_place" and state_of(found, "PR.AA-01") == "gap"
        assert [c["ref"] for c in scopes.candidates(session, steward, scope)] == [factor.ref]
        held = scopes.implementations(session, steward, scope)
        assert held["candidates"] == 1 and held["can_edit"]
        assert [(c["control"]["ref"], c["status"]) for c in held["controls"]] == [
            (review.ref, "in_place"), (leave.ref, "not_applicable"),
        ]  # fmt: skip
        leave_id = next(c["id"] for c in held["controls"] if c["control"]["ref"] == leave.ref)
        scopes.remove_implementation(session, steward, scope, leave_id)
        assert len(scopes.implementations(session, steward, scope)["controls"]) == 1


def test_a_scope_inherits_what_another_offers_and_cannot_say_where_it_stands(
    db: Database, loaded: None, people: People
) -> None:
    manager, steward = who(db, people, "manager"), who(db, people, "steward")
    hale, cancer = people.units["HALE"], people.units["CANCER"]
    with db.write(manager.actor) as session:
        central = add_scope(session, manager, cancer, "Central computing")
        backups = add_control(session, manager, cancer, "Backups", library_key="backups_tested")
        identity = add_control(
            session, manager, cancer, "Second factor", library_key="second_factor"
        )
        private = add_control(session, manager, cancer, "Kept to ourselves")
        for control in (backups, identity, private):
            scopes.implement(session, manager, central, control, status="in_place",
                             responsibility="Infrastructure team")  # fmt: skip
        enclave = add_scope(session, manager, hale, "The enclave")
        scopes.hold_to(session, manager, enclave, "nist-csf", None)
        # Nothing is on offer until the provider says so.
        assert scopes.offers(session, manager, enclave) == []
        provided = scopes.implementations(session, manager, central)["controls"]
        ids = {c["control"]["ref"]: c["id"] for c in provided}
        with pytest.raises(NotFound):
            scopes.inherit(session, manager, enclave, ids[backups.ref], inheritance="inherited")
        records.update(
            session, manager, SCOPE, central, {"offers_controls": True}, version=central.version
        )
        assert {o["control"]["ref"] for o in scopes.offers(session, manager, enclave)} == set(ids)

        scopes.inherit(session, manager, enclave, ids[backups.ref], inheritance="inherited")
        with pytest.raises(Invalid) as part:
            scopes.inherit(session, manager, enclave, ids[identity.ref], inheritance="shared")
        assert set(part.value.errors) == {"status", "statement"}
        scopes.inherit(
            session, manager, enclave, ids[identity.ref], inheritance="shared", status="partly",
            statement="The enclave enrols its own administrators.",
        )  # fmt: skip
        with pytest.raises(Invalid):
            scopes.inherit(session, manager, central, ids[backups.ref], inheritance="inherited")

        held = {
            c["control"]["ref"]: c
            for c in scopes.implementations(session, manager, enclave)["controls"]
        }
        assert held[backups.ref]["inheritance"] == "inherited"
        assert held[backups.ref]["standing"] == "in_place"
        assert held[backups.ref]["provider"]["scope"]["name"] == "Central computing"
        assert held[backups.ref]["provider"]["responsibility"] == "Infrastructure team"
        # Shared: only as far along as the weaker half.
        assert held[identity.ref]["standing"] == "partly"
        found = scopes.statement(session, manager, enclave, "nist-csf")
        assert (
            state_of(found, "PR.DS-11") == "in_place" and state_of(found, "PR.AA-03") == "planned"
        )
        answering = next(r for r in found["requirements"] if r["code"] == "PR.DS-11")["controls"][0]
        assert (
            answering["inheritance"] == "inherited" and answering["provider"]["ref"] == central.ref
        )

        # The inheriting scope cannot say where a control it inherits whole stands.
        with pytest.raises(Invalid) as whole:
            scopes.implement(session, manager, enclave, backups, status="planned")
        assert "inherited whole" in whole.value.errors["status"]
        # When the provider's control slips, everyone who inherits it shows it the same day.
        scopes.implement(session, manager, central, backups, status="partly",
                         responsibility="Infrastructure team")  # fmt: skip
        found = scopes.statement(session, manager, enclave, "nist-csf")
        assert state_of(found, "PR.DS-11") == "planned"
        assert scopes.implementations(session, manager, central)["controls"][0]["relied_on_by"] == 1

        # A provider cannot let go of what others rely on.
        with pytest.raises(Conflict):
            scopes.remove_implementation(session, manager, central, ids[backups.ref])
        with pytest.raises(Invalid) as relied:
            records.update(
                session,
                manager,
                SCOPE,
                central,
                {"offers_controls": False},
                version=central.version,
            )
        assert "offers_controls" in relied.value.errors

    # The steward of the enclave's unit cannot open central computing's controls, and still
    # sees whose control the enclave relies on and how well it is known to work.
    with db.read() as session:
        enclave = records.load(session, steward, SCOPE, enclave.ref)
        seen = {
            c["control"]["name"]: c
            for c in scopes.implementations(session, steward, enclave)["controls"]
        }
        assert seen["Backups"]["control"]["open"] is False
        assert seen["Backups"]["control"]["state"] == "not_assessed"
        with pytest.raises(NotFound):
            records.load(session, steward, CONTROL, backups.ref)


def test_the_api_keeps_a_scope_and_gives_its_statement_of_applicability(
    as_role: Clients, db: Database, loaded: None, people: People
) -> None:
    steward = as_role("steward")
    made = steward.post(
        "/api/v1/scopes", json={"name": "Clinic systems", "org_unit_id": people.units["HALE"]}
    )
    assert made.status_code == 201
    ref = made.json()["data"]["ref"]
    base = f"/api/v1/scopes/{ref}"
    held = steward.put(f"{base}/frameworks", json={"framework": "hipaa-security"})
    assert [h["key"] for h in held.json()["data"]["held_to"]] == ["hipaa-security"]
    control = steward.post(
        "/api/v1/controls",
        json={"name": "Logging", "statement": "Watched.", "kind": "detective",
              "org_unit_id": people.units["HALE"], "library_key": "logging_monitoring"},
    ).json()["data"]["ref"]  # fmt: skip
    assert [c["ref"] for c in steward.get(f"{base}/controls/candidates").json()["data"]] == [
        control
    ]
    used = steward.put(f"{base}/controls", json={"control": control, "status": "in_place"})
    assert used.status_code == 200 and used.json()["data"]["candidates"] == 0
    refused = steward.put(
        f"{base}/requirements",
        json={"framework": "hipaa-security", "code": "164.310(d)(2)(iv)", "applicable": False},
    )
    assert refused.status_code == 422
    assert steward.put(
        f"{base}/requirements",
        json={"framework": "hipaa-security", "code": "164.310(d)(2)(iv)", "applicable": False,
              "reason": "No removable media are used."},
    ).status_code == 200  # fmt: skip
    found = steward.get(f"{base}/requirements", params={"framework": "hipaa-security"}).json()[
        "data"
    ]
    assert found["counts"]["in_place"] == 3 and found["counts"]["excluded"] == 1
    assert found["applicable"] == 90 and found["can_edit"]
    gaps = steward.get(
        f"{base}/requirements", params={"framework": "hipaa-security", "state": "in_place"}
    )
    assert {row["code"] for row in gaps.json()["data"]["requirements"]} == {
        "164.312(b)", "164.308(a)(1)(ii)(D)", "164.308(a)(5)(ii)(C)",
    }  # fmt: skip
    listed = steward.get("/api/v1/scopes", params={"framework": "hipaa-security"}).json()["data"]
    assert [(row["ref"], row["controls"]) for row in listed] == [(ref, 1)]
    # A member of the unit reads the scope and changes nothing; a scope they cannot see is not there.
    member = as_role("member")
    assert member.get(f"{base}/controls").json()["data"]["can_edit"] is False
    assert (
        member.put(f"{base}/controls", json={"control": control, "status": "planned"}).status_code
        == 403
    )
    assert member.delete(f"{base}/frameworks/hipaa-security").status_code == 403
    assert steward.delete(f"{base}/frameworks/hipaa-security").json()["data"]["held_to"] == []
