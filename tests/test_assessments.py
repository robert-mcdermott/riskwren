"""Assessments and tests: independence, review before a result counts, one result moving
the control, every requirement it answers in every scope that relies on it, and every risk
it reduces; and readiness in five states."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.compliance import assessments, evidence, packs, scopes
from riskwren.compliance.assessments import ASSESSMENT
from riskwren.compliance.scopes import SCOPE
from riskwren.controls import service as controls
from riskwren.controls.service import CONTROL
from riskwren.core.clock import frozen_at
from riskwren.core.errors import Conflict, Invalid, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import ControlRating, ControlTest, TestResult
from riskwren.inventory import records
from riskwren.reporting import service as reporting
from riskwren.risk import register
from tests.conftest import TESTER
from tests.people import People
from tests.test_evidence import add_evidence
from tests.test_risks import judge, raise_risk, who
from tests.test_scopes import add_scope, state_of
from tests.test_treatment import add_control

Clients = Callable[[str | None], TestClient]
FOUND = "Sampled ten restores from the last quarter; all completed and were checked."


@pytest.fixture
def loaded(db: Database, people: People) -> None:
    with db.write(TESTER) as session:
        packs.install(session)


def world(session, people: People, manager):  # type: ignore[no-untyped-def]
    """A provider scope that does backups and identity, and an enclave that inherits both."""
    hale, cancer = people.units["HALE"], people.units["CANCER"]
    backups = add_control(session, manager, cancer, "Backups", library_key="backups_tested")
    factor = add_control(session, manager, cancer, "Second factor", library_key="second_factor")
    # Whoever adds a control owns it; these belong to someone who takes no part in testing them.
    owner = [{"account_id": people.accounts["leader"], "kind": "owner"}]
    for control in (backups, factor):
        records.set_owners(session, manager, CONTROL, control, owner)
    central = add_scope(session, manager, cancer, "Central computing", offers_controls=True)
    scopes.hold_to(session, manager, central, "nist-csf", None)
    for control in (backups, factor):
        scopes.implement(session, manager, central, control, status="in_place")
    enclave = add_scope(session, manager, hale, "The enclave")
    scopes.hold_to(session, manager, enclave, "nist-csf", None)
    for item in scopes.implementations(session, manager, central)["controls"]:
        scopes.inherit(session, manager, enclave, item["id"], inheritance="inherited")
    return central, enclave, backups, factor


def start(session, by, scope, **more):  # type: ignore[no-untyped-def]
    return assessments.create(
        session, by, {"name": "Annual assessment", "scope": scope.ref, **more}
    )


def the_test(session, assessment, control) -> ControlTest:  # type: ignore[no-untyped-def]
    return session.scalars(
        select(ControlTest).where(
            ControlTest.assessment_id == assessment.id, ControlTest.control_id == control.id
        )
    ).one()


def test_an_assessment_plans_a_test_for_each_control_the_scope_does_itself(
    db: Database, loaded: None, people: People
) -> None:
    manager, assessor, steward = (who(db, people, r) for r in ("manager", "assessor", "steward"))
    with db.write(manager.actor) as session:
        central, enclave, backups, factor = world(session, people, manager)
        other = add_control(session, manager, people.units["CANCER"], "Unmapped local control")
        scopes.implement(session, manager, central, other, status="in_place")
    with db.write(assessor.actor) as session:
        central = records.load(session, assessor, SCOPE, central.ref)
        made = start(session, assessor, central, period_start="2026-10-01", period_end="2026-12-15")
        assert (made.ref, made.status, made.lead_id) == ("ASM-0001", "planned", assessor.account_id)
        planned = assessments.tests_of(session, assessor, made)
        assert [t["control"]["name"] for t in planned] == [
            "Backups",
            "Second factor",
            "Unmapped local control",
        ]
        assert {t["state"] for t in planned} == {"todo"} and planned[0]["method"] == "examine"
        assert planned[0]["procedure"].startswith("Confirm that this is done as described:")
        # Against a framework: only the controls that answer a requirement of it that applies.
        narrow = start(session, assessor, central, framework="nist-csf")
        assert len(assessments.tests_of(session, assessor, narrow)) == 2
        chosen = start(session, assessor, central, controls=[factor.ref])
        assert [t["control"]["ref"] for t in assessments.tests_of(session, assessor, chosen)] == [
            factor.ref
        ]
        # What a scope inherits is tested where it is provided, not here.
        enclave = records.load(session, assessor, SCOPE, enclave.ref)
        assert assessments.tests_of(session, assessor, start(session, assessor, enclave)) == []
        with pytest.raises(Invalid) as bad:
            start(session, assessor, enclave, controls=[backups.ref])
        assert "does itself" in bad.value.errors["controls"]
        with pytest.raises(Invalid):
            start(session, assessor, central, framework="hipaa-security")
        with pytest.raises(Invalid):
            start(session, assessor, central, period_start="2026-12-01", period_end="2026-11-01")
        test = the_test(session, made, other)
        assessments.update_test(
            session,
            assessor,
            test,
            {
                "method": "interview",
                "procedure": "Ask the owner how it is done.",
                "assigned_to": assessor.account_id,
            },
        )
        with pytest.raises(Invalid):
            assessments.update_test(session, assessor, test, {"method": "guess"})
        assessments.remove_test(session, assessor, test)
        assessments.add_test(
            session, assessor, made, records.load(session, assessor, CONTROL, other.ref)
        )
        with pytest.raises(Conflict):
            assessments.add_test(
                session, assessor, made, records.load(session, assessor, CONTROL, other.ref)
            )
    # Assessing is the second line's: a steward does not start one.
    with db.write(steward.actor) as session, pytest.raises(PermissionDenied):
        start(session, steward, records.load(session, manager, SCOPE, enclave.ref))


def test_one_result_moves_the_control_every_scope_that_relies_on_it_and_every_risk(
    db: Database, loaded: None, people: People
) -> None:
    manager, assessor = who(db, people, "manager"), who(db, people, "assessor")
    with db.write(manager.actor) as session:
        central, enclave, backups, _ = world(session, people, manager)
        risk = raise_risk(session, manager, people.units["HALE"], "Loss of the enclave's data")
        judge(session, manager, risk, "inherent", 4, mission=4)
        controls.link(session, manager, risk, backups, reduces="impact", reliance="primary")
        assert register.suggestion(session, risk)["impact"] == 4  # nothing is known of it yet
        item = add_evidence(session, manager, people.units["CANCER"], "Restore log")
        made = start(session, manager, central)
        test = the_test(session, made, backups)

        # Before: in place in both scopes, by the provider's word alone.
        for scope in (central, enclave):
            assert (
                state_of(scopes.statement(session, manager, scope, "nist-csf"), "PR.DS-11")
                == "in_place"
            )

        result = assessments.record(
            session, manager, test, design="effective", operation="effective", note=FOUND,
            sample="Ten of forty-one restores.", evidence_refs=[item.ref],
        )  # fmt: skip
        assert made.status == "in_progress"
        # Recorded, and not yet counted: nothing has moved.
        assert assessments.view_of_test(session, manager, test)["state"] == "awaiting"
        assert backups.design == "not_assessed"
        assert (
            state_of(scopes.statement(session, manager, enclave, "nist-csf"), "PR.DS-11")
            == "in_place"
        )
        with pytest.raises(PermissionDenied) as own:
            assessments.review(session, manager, result, confirm=True, note=None)
        assert "their own result" in str(own.value)

    with db.write(assessor.actor) as session:
        result = session.get(TestResult, result.id)
        assessments.review(session, assessor, result, confirm=True, note=None)
        backups = records.load(session, assessor, CONTROL, backups.ref)
        # 1. The control: its rating is the test's, on the basis of a test, in the tester's name.
        rating = session.scalars(
            select(ControlRating).where(ControlRating.control_id == backups.id)
        ).one()
        assert (rating.design, rating.operation, rating.basis) == ("effective", "effective", "test")
        assert rating.rated_by_name == manager.name and rating.note.startswith(
            "Tested in ASM-0001:"
        )
        assert controls.state_of(session, backups) == "effective"
        # 2. Every requirement it answers, in the scope that does it and the scope that inherits it.
        for ref in (central.ref, enclave.ref):
            scope = records.load(session, assessor, SCOPE, ref)
            found = scopes.statement(session, assessor, scope, "nist-csf")
            assert (
                state_of(found, "PR.DS-11") == "verified"
                and state_of(found, "RC.RP-03") == "verified"
            )
            assert found["counts"]["verified"] == 2
            answering = next(r for r in found["requirements"] if r["code"] == "PR.DS-11")[
                "controls"
            ][0]
            assert answering["readiness"] == "verified" and "Tested effective" in answering["why"]
            # The other control is in place and untested, so its requirement is not verified.
            assert state_of(found, "PR.AA-03") == "in_place"
        # 3. Every risk it reduces: the suggestion now takes a level off the impact.
        risk = session.get(type(risk), risk.id)
        assert register.suggestion(session, risk)["impact"] == 3
        # A judgment does not overrule a test that still holds.
        with pytest.raises(Conflict):
            controls.rate(
                session,
                assessor,
                backups,
                design="partly",
                operation="partly",
                note="I think otherwise.",
            )


def test_a_failed_test_shows_as_failing_wherever_the_control_is_relied_on(
    db: Database, loaded: None, people: People
) -> None:
    manager, assessor = who(db, people, "manager"), who(db, people, "assessor")
    with db.write(manager.actor) as session:
        central, enclave, backups, factor = world(session, people, manager)
        risk = raise_risk(session, manager, people.units["HALE"], "Loss of the enclave's data")
        judge(session, manager, risk, "inherent", 4, mission=5)
        controls.link(session, manager, risk, backups, reduces="impact", reliance="primary")
        controls.rate(
            session,
            manager,
            backups,
            design="effective",
            operation="effective",
            note="Looks fine to me.",
        )
        judge(session, manager, risk, "residual", 4, mission=4)
        made = start(session, manager, central)
        first = assessments.record(
            session, manager, the_test(session, made, backups), design="effective",
            operation="ineffective", note="No restore of research storage has been tried in two years.",
        )  # fmt: skip
    with db.write(assessor.actor) as session:
        first = session.get(TestResult, first.id)
        with pytest.raises(Invalid):
            assessments.review(session, assessor, first, confirm=False, note=" ")
        assessments.review(
            session, assessor, first, confirm=False, note="Which storage? Say what was sampled."
        )
        test = session.get(ControlTest, first.test_id)
        assert assessments.view_of_test(session, assessor, test)["state"] == "returned"
        with pytest.raises(Conflict):
            assessments.review(session, assessor, first, confirm=True, note=None)
        # The assessor records it again; the manager, who did not, confirms it.
        second = assessments.record(
            session, assessor, test, design="effective", operation="ineffective",
            note="Research storage, all three arrays: no full restore since 2024.", sample="Restore logs.",
        )  # fmt: skip
        assert session.get(TestResult, first.id).superseded_by == second.id
        assert assessments.view_of_test(session, assessor, test)["results"] == 2
    with db.write(manager.actor) as session:
        assessments.review(
            session, manager, session.get(TestResult, second.id), confirm=True, note="Agreed."
        )
        for ref in (central.ref, enclave.ref):
            found = scopes.statement(
                session, manager, records.load(session, manager, SCOPE, ref), "nist-csf"
            )
            assert state_of(found, "PR.DS-11") == "failing" and found["counts"]["failing"] == 2
            why = next(r for r in found["requirements"] if r["code"] == "PR.DS-11")["controls"][0][
                "why"
            ]
            assert "found ineffective" in why
        # The risk that leaned on it is told its rating is in doubt, naming the control.
        risk = session.get(type(risk), risk.id)
        assert risk.residual_in_doubt and "Backups" in risk.residual_doubt_reason
        made = records.load(session, manager, ASSESSMENT, made.ref)
        with pytest.raises(Conflict) as unfinished:
            assessments.complete(session, manager, made)
        assert "1 of its 2 tests" in str(unfinished.value)
        assessments.remove_test(session, manager, the_test(session, made, factor))
        assert assessments.complete(session, manager, made).status == "complete"
        card = records.cards(session, ASSESSMENT, [made])[0]
        assert (card["tests"], card["counted"], card["failing"], card["awaiting"]) == (1, 1, 1, 0)
        with pytest.raises(Conflict):
            assessments.record(
                session,
                manager,
                the_test(session, made, backups),
                design="effective",
                operation="effective",
                note="Later.",
            )


def test_nobody_tests_or_reviews_a_control_they_own(
    db: Database, loaded: None, people: People
) -> None:
    manager, assessor = who(db, people, "manager"), who(db, people, "assessor")
    with db.write(manager.actor) as session:
        central, _, backups, factor = world(session, people, manager)
        # The assessor is named as the owner of one of the controls.
        records.set_owners(
            session,
            manager,
            CONTROL,
            backups,
            [{"account_id": assessor.account_id, "kind": "owner"}],
        )
        made = start(session, manager, central)
        result = assessments.record(
            session,
            manager,
            the_test(session, made, backups),
            design="effective",
            operation="effective",
            note=FOUND,
        )
    with db.write(assessor.actor) as session:
        made = records.load(session, assessor, ASSESSMENT, made.ref)
        mine = the_test(session, made, backups)
        view = assessments.view_of_test(session, assessor, mine)
        assert view["can"] == {"plan": True, "record": False, "review": False, "owns": True}
        with pytest.raises(PermissionDenied) as refused:
            assessments.record(
                session, assessor, mine, design="effective", operation="effective", note=FOUND
            )
        assert "a control they own" in str(refused.value)
        with pytest.raises(PermissionDenied):
            assessments.review(
                session, assessor, session.get(TestResult, result.id), confirm=True, note=None
            )
        # A control they do not own is theirs to test.
        assessments.record(
            session,
            assessor,
            the_test(session, made, factor),
            design="effective",
            operation="partly",
            note="One exception found.",
        )
        with pytest.raises(Invalid) as bad:
            assessments.record(
                session,
                assessor,
                the_test(session, made, factor),
                design="fine",
                operation="effective",
                note="",
                evidence_refs=["EV-9999"],
            )
        assert set(bad.value.errors) == {"design", "note", "evidence"}
    with db.write(who(db, people, "steward").actor) as session:
        steward = who(db, people, "steward")
        with pytest.raises(PermissionDenied):
            assessments.record(
                session,
                steward,
                session.get(ControlTest, mine.id),
                design="effective",
                operation="effective",
                note=FOUND,
            )


def test_verified_needs_a_test_that_still_holds_and_evidence_that_still_counts(
    db: Database, loaded: None, people: People
) -> None:
    manager, assessor = who(db, people, "manager"), who(db, people, "assessor")
    with frozen_at(datetime(2026, 1, 15, 12, tzinfo=UTC)):
        with db.write(manager.actor) as session:
            central, _, backups, factor = world(session, people, manager)
            made = start(session, manager, central)
            first = assessments.record(
                session,
                manager,
                the_test(session, made, backups),
                design="effective",
                operation="effective",
                note=FOUND,
            )
            second = assessments.record(
                session,
                manager,
                the_test(session, made, factor),
                design="effective",
                operation="effective",
                note=FOUND,
            )
            item = add_evidence(
                session,
                manager,
                people.units["CANCER"],
                "Restore log",
                collected_on="2026-01-10",
                valid_until="2026-06-30",
            )
            evidence.set_subjects(session, manager, item, [backups.ref])
        with db.write(assessor.actor) as session:
            for result in (first, second):
                assessments.review(
                    session, assessor, session.get(TestResult, result.id), confirm=True, note=None
                )
            found = scopes.statement(
                session, assessor, records.load(session, assessor, SCOPE, central.ref), "nist-csf"
            )
            # Tested effective with current evidence: verified. Tested effective with none: in place.
            assert (
                state_of(found, "PR.DS-11") == "verified"
                and state_of(found, "PR.AA-03") == "in_place"
            )
            why = next(r for r in found["requirements"] if r["code"] == "PR.AA-03")["controls"][0][
                "why"
            ]
            assert "no evidence for it still counts" in why
    with frozen_at(datetime(2026, 8, 1, 12, tzinfo=UTC)), db.read() as session:
        # The evidence has gone stale: the test still holds, and the requirement is no longer verified.
        found = scopes.statement(
            session, assessor, records.load(session, assessor, SCOPE, central.ref), "nist-csf"
        )
        assert state_of(found, "PR.DS-11") == "in_place"
    with frozen_at(datetime(2027, 3, 1, 12, tzinfo=UTC)), db.write(assessor.actor) as session:
        # The test has gone out of date: it says nothing now, and a judgment is allowed again.
        backups = records.load(session, assessor, CONTROL, backups.ref)
        assert controls.current_test(session, backups) is None
        found = scopes.statement(
            session, assessor, records.load(session, assessor, SCOPE, central.ref), "nist-csf"
        )
        why = next(r for r in found["requirements"] if r["code"] == "PR.DS-11")["controls"][0][
            "why"
        ]
        assert "no test result that still holds" in why
        controls.rate(
            session, assessor, backups, design="effective", operation="partly", note="Rated again."
        )


def test_tests_and_reviews_appear_on_the_home_of_whoever_they_wait_on(
    db: Database, loaded: None, people: People
) -> None:
    manager, assessor = who(db, people, "manager"), who(db, people, "assessor")
    with db.write(manager.actor) as session:
        central, _, backups, _ = world(session, people, manager)
        made = start(session, manager, central, lead_id=manager.account_id, period_end="2031-01-31")
        assessments.update_test(
            session, manager, the_test(session, made, backups), {"assigned_to": assessor.account_id}
        )
    with db.read() as session:
        mine = [i for i in reporting.home(session, assessor)["items"] if i["kind"] == "test"]
        assert [(i["title"], i["href"]) for i in mine] == [
            ("Test Backups", "/assessments/ASM-0001")
        ]
    with db.write(assessor.actor) as session:
        made = records.load(session, assessor, ASSESSMENT, made.ref)
        assessments.record(
            session,
            assessor,
            the_test(session, made, backups),
            design="effective",
            operation="effective",
            note=FOUND,
        )
    with db.read() as session:
        assert not [i for i in reporting.home(session, assessor)["items"] if i["kind"] == "test"]
        waiting = [i for i in reporting.home(session, manager)["items"] if i["kind"] == "confirm"]
        assert [i["title"] for i in waiting] == ["Review the result for Backups"]


def test_the_api_runs_an_assessment_from_plan_to_counted_result(
    as_role: Clients, db: Database, loaded: None, people: People
) -> None:
    manager, assessor = as_role("manager"), as_role("assessor")
    with db.write(who(db, people, "manager").actor) as session:
        central, _, backups, _ = world(session, people, who(db, people, "manager"))
    made = assessor.post(
        "/api/v1/assessments",
        json={
            "name": "Central computing 2026",
            "scope": central.ref,
            "framework": "nist-csf",
            "period_end": "2026-12-15",
        },
    )
    assert made.status_code == 201
    data = made.json()["data"]
    assert (data["ref"], data["status"], data["tests"], data["can_run"]) == (
        "ASM-0001",
        "planned",
        2,
        True,
    )
    assert data["scope"]["ref"] == central.ref and data["framework"]["key"] == "nist-csf"
    test = next(t for t in data["tests_list"] if t["control"]["ref"] == backups.ref)
    assert test["can"]["record"] and not test["can"]["review"]
    recorded = assessor.post(
        f"/api/v1/tests/{test['id']}/results",
        json={"design": "effective", "operation": "partly", "note": "Two of ten restores failed."},
    )
    assert recorded.status_code == 201 and recorded.json()["data"]["state"] == "awaiting"
    result = recorded.json()["data"]["result"]["id"]
    assert (
        assessor.post(f"/api/v1/results/{result}/review", json={"confirm": True}).status_code == 403
    )
    counted = manager.post(
        f"/api/v1/results/{result}/review", json={"confirm": True, "note": "Agreed."}
    )
    assert (
        counted.json()["data"]["state"] == "counted"
        and counted.json()["data"]["result"]["outcome"] == "partly"
    )
    assert manager.get(f"/api/v1/controls/{backups.ref}").json()["data"]["state"] == "partly"
    found = manager.get(
        f"/api/v1/scopes/{central.ref}/requirements",
        params={"framework": "nist-csf", "state": "failing"},
    ).json()["data"]
    assert {row["code"] for row in found["requirements"]} == {"PR.DS-11", "RC.RP-03"}
    listed = manager.get("/api/v1/assessments", params={"scope": central.ref}).json()["data"]
    assert [(a["ref"], a["status"], a["counted"], a["failing"]) for a in listed] == [
        ("ASM-0001", "in_progress", 1, 1)
    ]
    assert manager.post("/api/v1/assessments/ASM-0001/completion").status_code == 409
    told = [
        entry["title"]
        for entry in manager.get("/api/v1/assessments/ASM-0001/history").json()["data"]
    ]
    assert "Confirmed the result for Backups" in told and "Planned a test of Second factor" in told
    assert "Recorded a result for Backups: design effective, operation partly effective" in told
    # A steward and a member read an assessment of their unit and record nothing.
    steward = as_role("steward")
    assert (
        steward.post("/api/v1/assessments", json={"name": "x", "scope": central.ref}).status_code
        == 403
    )
    assert (
        steward.post(
            f"/api/v1/tests/{test['id']}/results",
            json={"design": "effective", "operation": "effective", "note": "x"},
        ).status_code
        == 403
    )
    assert as_role("auditor").get("/api/v1/assessments/ASM-0001").json()["data"]["can_run"] is False
    assert (
        manager.post("/api/v1/assessments/ASM-0001/cancellation").json()["data"]["status"]
        == "cancelled"
    )
