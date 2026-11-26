"""Crosswalks: one control mapped to many requirements, from either end; the starter
controls' suggested mappings; and coverage that counts only what its reader may see."""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from riskwren.compliance import crosswalk, frameworks, packs
from riskwren.controls.service import CONTROL
from riskwren.core.errors import Invalid, NotFound, PermissionDenied
from riskwren.db import migrate
from riskwren.db.engine import Database
from riskwren.db.models import ControlLibraryEntry, ControlRequirement, Event
from riskwren.inventory import records
from riskwren.program import packs as program_packs
from tests.conftest import TESTER, Instance
from tests.people import People
from tests.test_risks import who
from tests.test_treatment import add_control

Clients = Callable[[str | None], TestClient]


@pytest.fixture
def loaded(db: Database, people: People) -> None:
    with db.write(TESTER) as session:
        packs.install(session)


def test_every_suggested_mapping_names_a_requirement_that_exists_and_can_be_cited() -> None:
    library = program_packs.builtin("starter-controls.json")["controls"]
    known = {
        key: {item["code"] for item, _ in packs.walk(packs.builtin(key)["requirements"])
              if not item.get("group")}
        for key in packs.BUILTIN
    }  # fmt: skip
    mapped = [control for control in library if control.get("requirements")]
    assert len(mapped) >= 25
    for control in mapped:
        for framework, codes in control["requirements"].items():
            assert framework in known, control["key"]
            assert codes and len(codes) == len(set(codes)), control["key"]
            assert set(codes) <= known[framework], (control["key"], set(codes) - known[framework])
    # The controls a security program rests on are mapped in all four.
    security = next(c for c in library if c["key"] == "logging_monitoring")
    assert set(security["requirements"]) == set(packs.BUILTIN)


def test_a_control_adopted_from_the_library_arrives_mapped(
    db: Database, loaded: None, people: People
) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        own = add_control(session, steward, people.units["HALE"], "Our own")
        assert crosswalk.of_control(session, steward, own)["total"] == 0
        adopted = add_control(
            session, steward, people.units["HALE"], "Second factor", library_key="second_factor"
        )
        held = crosswalk.of_control(session, steward, adopted)
        assert held["total"] == 6 and held["suggested"] == 0 and held["can_edit"]
        assert [group["key"] for group in held["frameworks"]] == [
            "hipaa-security", "nist-csf", "nist-800-171", "nist-800-53",
        ]  # fmt: skip
        csf = held["frameworks"][1]["requirements"]
        assert [(r["code"], r["coverage"], r["source"]) for r in csf] == [
            ("PR.AA-03", "partial", "pack")
        ]
        # The mappings are part of the control's own history.
        told = session.scalars(
            select(Event).where(Event.subject_type == "control_requirement")
        ).all()
        assert len(told) == 6 and {e.parent_type for e in told} == {"control"}
        assert {e.parent_id for e in told} == {adopted.id}


def test_suggestions_wait_for_a_framework_and_are_added_when_asked(
    db: Database, people: People
) -> None:
    steward, member = who(db, people, "steward"), who(db, people, "member")
    with db.write(steward.actor) as session:
        adopted = add_control(
            session, steward, people.units["HALE"], "Patching", library_key="patching"
        )
        assert crosswalk.of_control(session, steward, adopted)["total"] == 0  # none loaded yet
    with db.write(TESTER) as session:
        packs.load(session, packs.builtin("nist-csf"))
    with db.write(steward.actor) as session:
        adopted = records.load(session, steward, CONTROL, adopted.ref)
        assert crosswalk.of_control(session, steward, adopted)["suggested"] == 2
        with pytest.raises(PermissionDenied):
            crosswalk.apply_suggestions(session, member, adopted)
        assert crosswalk.apply_suggestions(session, steward, adopted) == 2
        assert crosswalk.apply_suggestions(session, steward, adopted) == 0
        held = crosswalk.of_control(session, steward, adopted)
        assert [r["code"] for r in held["frameworks"][0]["requirements"]] == [
            "ID.RA-01",
            "PR.PS-02",
        ]


def test_a_control_is_mapped_changed_and_unmapped_by_those_who_keep_it(
    db: Database, loaded: None, people: People
) -> None:
    steward, member = who(db, people, "steward"), who(db, people, "member")
    with db.write(steward.actor) as session:
        control = add_control(session, steward, people.units["HALE"], "Restore test")
        made = crosswalk.map_(
            session, steward, control, framework="nist-800-53", code="CP-9(1)", coverage="full"
        )
        assert (made.coverage, made.source) == ("full", "person")
        again = crosswalk.map_(
            session, steward, control, framework="nist-800-53", code="CP-9(1)",
            coverage="partial", note="Research storage is not yet covered.",
        )  # fmt: skip
        assert again.id == made.id and again.coverage == "partial"  # once, not twice
        crosswalk.map_(
            session, steward, control, framework="hipaa-security",
            code="164.308(a)(7)(ii)(D)", coverage="partial",
        )  # fmt: skip
        with pytest.raises(Invalid) as heading:
            crosswalk.map_(
                session, steward, control, framework="nist-800-53", code="CP", coverage="full"
            )
        assert "heading" in heading.value.errors["code"]
        with pytest.raises(Invalid) as bad:
            crosswalk.map_(
                session, steward, control, framework="nist-csf", code="XX.YY-99", coverage="some"
            )
        assert set(bad.value.errors) == {"code", "coverage"}
        with pytest.raises(PermissionDenied):
            crosswalk.map_(
                session, member, control, framework="nist-csf", code="PR.DS-11", coverage="full"
            )
        assert crosswalk.of_control(session, steward, control)["total"] == 2
        with pytest.raises(NotFound):
            crosswalk.unmap(session, steward, control, 99999)
        crosswalk.unmap(session, steward, control, made.id)
        assert crosswalk.of_control(session, steward, control)["total"] == 1
        csf = frameworks.by_key(session, "nist-csf")
        frameworks.update(session, who(db, people, "manager"), csf, {"status": "retired"})
        with pytest.raises(Invalid) as retired:
            crosswalk.map_(
                session, steward, control, framework="nist-csf", code="PR.DS-11", coverage="full"
            )
        assert "retired" in retired.value.errors["framework"]


def test_a_requirement_shows_its_controls_and_coverage_counts_what_the_reader_may_see(
    db: Database, loaded: None, people: People
) -> None:
    manager, member = who(db, people, "manager"), who(db, people, "member")
    with db.write(manager.actor) as session:
        mine = add_control(session, manager, people.units["HALE"], "Backups restored")
        theirs = add_control(session, manager, people.units["CANCER"], "Their backups")
        secret = add_control(session, manager, people.units["HALE"], "Secret", restricted=True)
        for control in (mine, theirs, secret):
            crosswalk.map_(
                session, manager, control, framework="nist-csf", code="PR.DS-11", coverage="partial"
            )
        crosswalk.map_(
            session, manager, mine, framework="nist-csf", code="RC.RP-03", coverage="full"
        )
    with db.read() as session:
        csf = frameworks.by_key(session, "nist-csf")
        requirement = frameworks.find(session, csf, "PR.DS-11")
        seen = crosswalk.controls_of(session, manager, requirement)
        assert [c["control"]["name"] for c in seen["controls"]] == [
            "Backups restored",
            "Their backups",
            "Secret",
        ]
        assert seen["hidden"] == 0 and seen["controls"][0]["control"]["state"] == "not_assessed"
        # A member of the unit sees its ordinary controls: not the other unit's, not the restricted one.
        partly = crosswalk.controls_of(session, member, requirement)
        assert [c["control"]["name"] for c in partly["controls"]] == ["Backups restored"]
        assert partly["hidden"] == 2
        assert crosswalk.coverage(session, manager, csf) == {
            "citable": 106,
            "mapped": 2,
            "unmapped": 104,
        }
        assert crosswalk.counts(session, manager, [requirement.id]) == {requirement.id: 3}
        assert crosswalk.counts(session, member, [requirement.id]) == {requirement.id: 1}
        with_, total = frameworks.listing(
            session, csf, only=crosswalk.condition(session, manager, mapped=True)
        )
        assert total == 2 and {row["code"] for row in with_} == {"PR.DS-11", "RC.RP-03"}
        _, without = frameworks.listing(
            session, csf, only=crosswalk.condition(session, manager, mapped=False)
        )
        assert without == 104
    # A retired control answers nothing.
    with db.write(manager.actor) as session:
        mine = records.load(session, manager, CONTROL, mine.ref)
        records.update(session, manager, CONTROL, mine, {"status": "retired"}, version=mine.version)
        csf = frameworks.by_key(session, "nist-csf")
        assert crosswalk.coverage(session, manager, csf)["mapped"] == 1
        # For a member of the unit, all that is left is restricted or in another unit.
        assert crosswalk.coverage(session, member, csf)["mapped"] == 0


def test_the_api_maps_from_either_end(
    as_role: Clients, db: Database, loaded: None, people: People
) -> None:
    steward = as_role("steward")
    made = steward.post(
        "/api/v1/controls",
        json={"name": "Access reviewed", "statement": "Twice a year.", "kind": "detective",
              "org_unit_id": people.units["HALE"], "library_key": "access_reviewed"},
    )  # fmt: skip
    ref = made.json()["data"]["ref"]
    held = steward.get(f"/api/v1/controls/{ref}/requirements").json()["data"]
    assert held["total"] == 6 and held["can_edit"]
    mapped = steward.put(
        f"/api/v1/controls/{ref}/requirements",
        json={"framework": "nist-800-53", "code": "AC-6", "coverage": "partial", "note": "Reviews only."},
    )  # fmt: skip
    assert mapped.status_code == 200 and mapped.json()["data"]["total"] == 7
    one = steward.get("/api/v1/frameworks/nist-800-53/requirement", params={"code": "AC-6"}).json()[
        "data"
    ]
    assert [c["control"]["ref"] for c in one["controls"]] == [ref] and one["hidden"] == 0
    assert one["controls"][0]["note"] == "Reviews only."
    family = steward.get(
        "/api/v1/frameworks/nist-800-53/requirements", params={"parent": "AC"}
    ).json()["data"]
    assert {row["code"]: row["controls"] for row in family}["AC-2"] == 1
    gaps = steward.get("/api/v1/frameworks/nist-csf/requirements", params={"mapped": "false"})
    assert gaps.json()["meta"]["total"] == 105
    assert steward.get("/api/v1/frameworks/nist-csf/coverage").json()["data"] == {
        "citable": 106, "mapped": 1, "unmapped": 105,
    }  # fmt: skip
    mapping = next(
        r["id"]
        for g in mapped.json()["data"]["frameworks"]
        for r in g["requirements"]
        if r["code"] == "AC-6"
    )
    assert (
        steward.delete(f"/api/v1/controls/{ref}/requirements/{mapping}").json()["data"]["total"]
        == 6
    )
    # A member of the unit reads the control's requirements and cannot change them.
    member = as_role("member")
    assert member.get(f"/api/v1/controls/{ref}/requirements").json()["data"]["can_edit"] is False
    refused = member.put(
        f"/api/v1/controls/{ref}/requirements", json={"framework": "nist-csf", "code": "PR.AA-05"}
    )
    assert refused.status_code == 403
    assert member.post(f"/api/v1/controls/{ref}/requirements/suggested").status_code == 403
    # An auditor reads everything and changes nothing.
    assert as_role("auditor").delete(f"/api/v1/controls/{ref}/requirements/1").status_code == 403


def test_upgrading_keeps_the_library_and_makes_room_for_its_mappings(instance: Instance) -> None:
    db = instance.db
    migrate.downgrade(db.engine, "0007")
    with db.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO control_library (key, title, statement, kind, reduces, source_pack) "
                "VALUES ('kept', 'Kept', 'A row from before.', 'preventive', 'likelihood', 'old')"
            )
        )
    migrate.upgrade(db.engine)
    with db.read() as session:
        row = session.scalars(select(ControlLibraryEntry)).one()
        assert (row.key, row.requirements) == ("kept", {})
        assert session.scalars(select(ControlRequirement)).first() is None
    with db.write(TESTER) as session:
        program_packs.install(session, frameworks=False)
        entry = session.scalars(
            select(ControlLibraryEntry).where(ControlLibraryEntry.key == "patching")
        ).one()
        assert json.dumps(entry.requirements["nist-800-53"]) == '["SI-2", "RA-5"]'
