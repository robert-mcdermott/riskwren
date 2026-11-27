"""Framework updates: a new version loaded beside the old, what changed, moving a scope
across, and the crosswalks a publisher's mapping suggests."""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.compliance import crosswalk, exceptions, frameworks, packs, scopes, versions
from riskwren.compliance.agreements import AGREEMENT
from riskwren.compliance.scopes import SCOPE
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import ControlRequirement, ExceptionRequest, Framework
from riskwren.inventory import history, records
from tests.conftest import TESTER
from tests.people import People
from tests.test_risks import who
from tests.test_treatment import add_control

Clients = Callable[[str | None], TestClient]
TERMS = """\
T-1 Data are used only for the approved study.
T-2 Data are encrypted wherever they are stored.
T-3 Copies are not made on removable media.
T-4 A loss is reported within five days.
"""


def own_pack(key: str, follows: str | None, lines: list[tuple[str, str]]) -> dict:  # type: ignore[type-arg]
    head = {
        "key": key, "kind": "framework", "framework_kind": "agreement",
        "title": f"Sponsor terms {key[-4:]}", "version": key[-4:], "publisher": "A sponsor",
        "license": "The sponsor's terms, held by the institute", "text_policy": "verbatim",
    }  # fmt: skip
    if follows:
        head["follows"] = follows
    return {"pack": head, "requirements": [{"code": code, "text": text} for code, text in lines]}


def snapshot(session, principal, scope, key: str) -> str:  # type: ignore[no-untyped-def]
    found = scopes.statement(session, principal, scope, key)
    return json.dumps(found, sort_keys=True, default=str)


def cited(pack: dict) -> dict[str, str]:  # type: ignore[type-arg]
    return {
        item["code"]: " ".join(str(item.get("text") or "").split())
        for item, _ in packs.walk(pack["requirements"])
        if not item.get("group")
    }


def test_a_new_version_loaded_beside_the_old_changes_nothing_until_a_scope_is_moved(
    db: Database, people: People
) -> None:
    manager, steward = who(db, people, "manager"), who(db, people, "steward")
    hale = people.units["HALE"]
    first = [("T-1", "Data are used only for the approved study."),
             ("T-2", "Data are encrypted wherever they are stored."),
             ("T-3", "Copies are not made on removable media.")]  # fmt: skip
    second = [("T-1", "Data are used only for the approved study."),
              ("T-2", "Data are encrypted wherever they are stored, and when they are moved."),
              ("T-4", "A loss is reported within three days.")]  # fmt: skip
    with db.write(manager.actor) as session:
        old = packs.load(session, own_pack("terms-2025", None, first))
        scope = records.create(
            session, steward, SCOPE, {"name": "The enclave", "org_unit_id": hale}
        )
        scopes.hold_to(session, steward, scope, old.key, None)
        scopes.decide(session, steward, scope, framework=old.key, code="T-3", applicable=False,
                      reason="No removable media exist here.")  # fmt: skip
        control = add_control(session, steward, hale, "Disks encrypted")
        crosswalk.map_(session, steward, control, framework=old.key, code="T-2", coverage="full")
        exception = exceptions.request(
            session, steward,
            {"requirement": {"framework": old.key, "code": "T-1"}, "scope": scope.ref,
             "justification": "A second study is waiting for its approval.",
             "expires_on": "2026-12-31"},
        )  # fmt: skip
        before = snapshot(session, steward, scope, old.key)
        mapped_before = session.scalars(select(ControlRequirement)).all()
        # Loading the new version touches nothing that uses the old one.
        new = packs.load(session, own_pack("terms-2026", old.key, second))
        assert new.follows == old.key
        assert snapshot(session, steward, scope, old.key) == before
        assert session.scalars(select(ControlRequirement)).all() == mapped_before
        assert [row["key"] for row in scopes.held_to(session, scope)] == [old.key]
        # What changed is exactly what differs between the two.
        found = versions.changes(session, old, new)
        assert [row["code"] for row in found["added"]] == ["T-4"]
        assert [row["code"] for row in found["changed"]] == ["T-2"]
        assert [row["code"] for row in found["withdrawn"]] == ["T-3"]
        assert found["counts"] == {"added": 1, "changed": 1, "withdrawn": 1, "same": 1}
        one = versions.compare_one(session, old, new, "T-2")
        assert one["counts"]["changed"] == 1
        affected = versions.affects(session, steward, old, new)
        assert [row["ref"] for row in affected["scopes"]] == [scope.ref]
        assert affected["scopes"][0]["can_move"]
        assert [(row["ref"], row["codes"]) for row in affected["controls"]] == [
            (control.ref, ["T-2"])
        ]
        assert affected["crosswalks"] == {"carried": 1, "left": 0}
        assert [(row["ref"], row["carries"]) for row in affected["exceptions"]] == [
            (exception.ref, True)
        ]
        # Moving carries what has the same code, and leaves what was withdrawn.
        with pytest.raises(Invalid):
            versions.move(session, steward, scope, new.key, old.key)  # not a later version
        with pytest.raises(PermissionDenied):
            versions.move(session, who(db, people, "member"), scope, old.key, new.key)
        moved = versions.move(session, steward, scope, old.key, new.key)
        assert (moved["decisions"], moved["decisions_left"]) == (0, 1)  # T-3 was withdrawn
        assert (moved["exceptions"], moved["crosswalks"]) == (1, 1)
        assert [row["key"] for row in scopes.held_to(session, scope)] == [new.key]
        statement = scopes.statement(session, steward, scope, new.key)
        assert [row["code"] for row in statement["requirements"]] == ["T-1", "T-2", "T-4"]
        carried = session.scalars(
            select(ControlRequirement).where(ControlRequirement.source == "carried")
        ).one()
        assert carried.coverage == "full" and carried.control_id == control.id
        assert (
            exceptions.subject_of(session, steward, session.get(ExceptionRequest, exception.id))[
                "framework"
            ]["key"]
            == new.key
        )
        # The old version is still there, and still mapped, for anything that has not moved.
        assert session.get(Framework, old.id).status == "active"
        assert versions.versions(session, new)["earlier"]["key"] == old.key
        told = [entry["title"] for entry in history.for_record(session, SCOPE, scope)]
        assert f"Moved from {old.title} to {new.title}" in told
        assert f"Left its decision on T-3 behind: {new.title} has no such requirement" in told
        with pytest.raises(Conflict):
            versions.move(session, steward, scope, old.key, new.key)  # it holds it no longer


def test_moving_is_refused_where_an_agreement_imposes_the_version(
    db: Database, people: People
) -> None:
    manager, steward = who(db, people, "manager"), who(db, people, "steward")
    hale = people.units["HALE"]
    with db.write(manager.actor) as session:
        old = packs.load(session, own_pack("terms-2025", None, [("T-1", "Use.")]))
        new = packs.load(session, own_pack("terms-2026", old.key, [("T-1", "Use it well.")]))
        scope = records.create(session, steward, SCOPE, {"name": "Enclave", "org_unit_id": hale})
        agreement = records.create(
            session, steward, AGREEMENT,
            {"name": "Sponsor", "kind": "award", "parties": "A sponsor", "org_unit_id": hale,
             "framework": old.key},
        )  # fmt: skip
        from riskwren.compliance import agreements

        agreements.set_coverage(session, steward, agreement, [scope.ref])
        with pytest.raises(Conflict) as refused:
            versions.move(session, steward, scope, old.key, new.key)
        assert "agreement" in str(refused.value)
        # The agreement names the new version instead, and the scope follows it.
        records.update(session, steward, AGREEMENT, agreement, {"framework": new.key},
                       version=agreement.version)  # fmt: skip
        assert [row["key"] for row in scopes.held_to(session, scope)] == [new.key]


def test_a_published_revision_is_compared_with_the_one_before_by_code(
    db: Database, people: People, as_role: Clients
) -> None:
    manager = who(db, people, "manager")
    with db.write(TESTER) as session:
        packs.install(session)
    r4, r5 = packs.builtin("nist-800-53-r4"), packs.builtin("nist-800-53")
    old_codes, new_codes = cited(r4), cited(r5)
    # It ships, and is loaded when someone asks.
    client = as_role("manager")
    shipped = {row["key"]: row for row in client.get("/api/v1/framework-packs").json()["data"]}
    assert shipped["nist-800-53-r4"]["loaded"] is False
    assert shipped["nist-800-53"]["follows"] == "nist-800-53-r4"
    assert (
        as_role("steward")
        .post("/api/v1/framework-packs", json={"key": "nist-800-53-r4"})
        .status_code
        == 403
    )
    loaded = client.post("/api/v1/framework-packs", json={"key": "nist-800-53-r4"})
    assert loaded.status_code == 201, loaded.text
    assert client.post("/api/v1/framework-packs", json={"key": "nist-800-53-r4"}).status_code == 409
    seen = client.get("/api/v1/frameworks/nist-800-53").json()["data"]
    assert seen["versions"]["earlier"]["key"] == "nist-800-53-r4"
    with db.write(manager.actor) as session:
        old = frameworks.by_key(session, "nist-800-53-r4")
        new = frameworks.by_key(session, "nist-800-53")
        found = versions.changes(session, old, new)
        assert {row["code"] for row in found["added"]} == set(new_codes) - set(old_codes)
        assert {row["code"] for row in found["withdrawn"]} == set(old_codes) - set(new_codes)
        assert {row["code"] for row in found["changed"]} == {
            code
            for code in set(old_codes) & set(new_codes)
            if old_codes[code] != new_codes[code] or False
        } | {row["code"] for row in found["changed"] if row["retitled"]}
        # Where the publisher says a withdrawn control went.
        account = next(row for row in found["withdrawn"] if row["code"] == "AC-2(10)")
        assert account["went"] == [{"how": "incorporated_into", "code": "AC-2"}]
    shown = client.get("/api/v1/frameworks/nist-800-53/changes", params={"from": "nist-800-53-r4"})
    assert shown.status_code == 200 and shown.json()["data"]["counts"]["withdrawn"] > 100


def test_a_new_version_of_a_framework_of_ones_own_is_a_copy_beside_it(
    db: Database, people: People
) -> None:
    manager, steward = who(db, people, "manager"), who(db, people, "steward")
    with db.write(manager.actor) as session:
        old = frameworks.create(session, manager, {"title": "Cohort terms", "kind": "agreement"})
        frameworks.paste(session, manager, old, TERMS, dry_run=False)
        with pytest.raises(PermissionDenied):
            versions.start_version(session, steward, old, {"title": "Cohort terms 2027"})
        with pytest.raises(Invalid):
            versions.start_version(session, manager, old, {"title": " "})
        new = versions.start_version(
            session, manager, old, {"title": "Cohort terms 2027", "version": "Renewed 2027"}
        )
        assert (new.follows, new.citable_count, new.kind) == (old.key, 4, "agreement")
        frameworks.update_requirement(
            session, manager, new, frameworks.find(session, new, "T-4"),
            {"text": "A loss is reported within seventy-two hours."},
        )  # fmt: skip
        assert frameworks.find(session, old, "T-4").text == "A loss is reported within five days."
        found = versions.changes(session, old, new)
        assert [row["code"] for row in found["changed"]] == ["T-4"]
        packs.install(session)
        nist = frameworks.by_key(session, "nist-csf")
        with pytest.raises(Conflict):
            versions.start_version(session, manager, nist, {"title": "My CSF"})


def test_a_publishers_mapping_suggests_crosswalks_that_a_person_confirms_or_sets_aside(
    db: Database, people: People, as_role: Clients
) -> None:
    steward, member = who(db, people, "steward"), who(db, people, "member")
    hale = people.units["HALE"]
    with db.write(TESTER) as session:
        packs.install(session)
    with db.write(steward.actor) as session:
        accounts = add_control(session, steward, hale, "Accounts are approved and reviewed")
        flows = add_control(session, steward, hale, "Network flows are restricted")
        crosswalk.map_(session, steward, accounts, framework="nist-800-171", code="03.01.01",
                       coverage="full")  # fmt: skip
        crosswalk.map_(session, steward, flows, framework="nist-800-53", code="AC-4",
                       coverage="partial")  # fmt: skip
        sp53 = frameworks.by_key(session, "nist-800-53")
        sp171 = frameworks.by_key(session, "nist-800-171")
        # SP 800-171's 03.01.01 is derived from AC-2 and three of its enhancements.
        found = crosswalk.publisher_suggestions(session, steward, sp53)
        mine = next(row for row in found["controls"] if row["control"]["ref"] == accounts.ref)
        assert [each["code"] for each in mine["suggestions"]] == [
            "AC-2", "AC-2(13)", "AC-2(3)", "AC-2(5)"
        ]  # fmt: skip
        assert mine["suggestions"][0]["because"] == [
            {"framework": sp171.title, "key": "nist-800-171", "code": "03.01.01"}
        ]
        # And the other way: AC-4 is where 03.01.03 comes from.
        back = crosswalk.publisher_suggestions(session, steward, sp171)
        assert [(row["control"]["ref"], [s["code"] for s in row["suggestions"]])
                for row in back["controls"]] == [(flows.ref, ["03.01.03"])]  # fmt: skip
        with pytest.raises(PermissionDenied):
            crosswalk.confirm_suggestion(session, member, sp53, accounts, "AC-2")
        made = crosswalk.confirm_suggestion(session, steward, sp53, accounts, "AC-2")
        assert (made.coverage, made.source) == ("partial", "person")
        assert "03.01.01" in (made.note or "")
        crosswalk.set_aside(session, steward, sp53, accounts, "AC-2(13)")
        with pytest.raises(NotFound):
            crosswalk.confirm_suggestion(session, steward, sp53, accounts, "AC-2(13)")
        left = crosswalk.publisher_suggestions(session, steward, sp53)
        mine = next(row for row in left["controls"] if row["control"]["ref"] == accounts.ref)
        assert [each["code"] for each in mine["suggestions"]] == ["AC-2(3)", "AC-2(5)"]
        ref = accounts.ref
    client = as_role("steward")
    shown = client.get("/api/v1/frameworks/nist-800-53/suggestions").json()["data"]
    assert shown["total"] >= 2 and shown["sources"] == [sp171.title]
    confirmed = client.post(
        "/api/v1/frameworks/nist-800-53/suggestions/confirm",
        json={"control": ref, "code": "AC-2(3)"},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert client.get("/api/v1/frameworks/nist-800-53").json()["data"]["suggested"] >= 1
