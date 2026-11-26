"""Controls of known effectiveness, the suggested residual rating, plans, actions, and
acceptance under the authority table."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from riskwren.access.principal import Grant, Principal
from riskwren.controls import service as controls
from riskwren.controls.service import CONTROL
from riskwren.core.clock import frozen_at
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import Control, Risk
from riskwren.inventory import history, records
from riskwren.inventory.registry import find
from riskwren.people import accounts
from riskwren.risk import register
from riskwren.risk.register import RISK
from riskwren.treatment import service as treatment
from tests.people import ME, People
from tests.test_risks import WHY, judge, raise_risk, who

Clients = Callable[[str | None], TestClient]
SEEN = "Walked the freezer farm with the facilities lead and read the last year's call-out log."


def add_control(session, by: Principal, unit: int, name: str, **more) -> Control:  # type: ignore[no-untyped-def]
    values = {
        "name": name,
        "statement": f"{name}, every month.",
        "kind": "preventive",
        "org_unit_id": unit,
        **more,
    }
    return records.create(session, by, CONTROL, values)


def rated(session, by: Principal, control: Control, design: str, operation: str, **more):  # type: ignore[no-untyped-def]
    return controls.rate(
        session, by, control, design=design, operation=operation, note=SEEN, **more
    )


def setup_risk(session, people: People, steward: Principal) -> tuple[Risk, dict[str, Control]]:  # type: ignore[no-untyped-def]
    """The worked example in the engine document: a critical inherent risk and five controls."""
    hale = people.units["HALE"]
    risk = raise_risk(session, steward, hale)
    judge(session, steward, risk, "inherent", 4, mission=5)
    made = {}
    for name, reduces, reliance, design, operation in [
        ("Maintenance", "likelihood", "primary", "effective", "effective"),
        ("Alarm", "likelihood", "primary", "effective", "partly"),
        ("Signage", "likelihood", "supporting", None, None),
        ("Split", "impact", "primary", "effective", "effective"),
        ("Spare", "impact", "supporting", "effective", "effective"),
    ]:
        control = add_control(session, steward, hale, name)
        if design:
            rated(session, steward, control, design, operation)
        controls.link(session, steward, risk, control, reduces=reduces, reliance=reliance)
        made[name] = control
    return risk, made


# --- Controls -----------------------------------------------------------------------------


def test_the_starter_controls_are_loaded_and_every_library_risk_suggests_some(
    db: Database, people: People
) -> None:
    from riskwren.risk import library

    with db.read() as session:
        entries = controls.library(session)
        keys = {entry["key"] for entry in entries}
        assert len(entries) >= 50 and all(e["statement"].endswith(".") for e in entries)
        for risk in library.search(session):
            assert risk["suggested_controls"], risk["key"]
            assert set(risk["suggested_controls"]) <= keys, risk["key"]
        found = controls.library(session, query="FREEZER")
        assert [entry["key"] for entry in found] == ["freezer_monitoring", "backup_capacity"]
        wanted = controls.library(session, keys=["succession", "nothing"])
        assert [entry["key"] for entry in wanted] == ["succession"]


def test_a_control_is_described_once_and_rated_by_someone(db: Database, people: People) -> None:
    steward, hale = who(db, people, "steward"), people.units["HALE"]
    with db.write(steward.actor) as session:
        control = add_control(session, steward, hale, "Freezers alarmed", frequency="continuous")
        assert (control.ref, control.design, control.operation) == (
            "CTL-0001", "not_assessed", "not_assessed",
        )  # fmt: skip
        shown = records.detail(session, steward, CONTROL, control)
        assert shown["state"] == "not_assessed" and shown["rating"] is None
        with pytest.raises(Invalid) as caught:
            records.create(session, steward, CONTROL, {"name": "x", "org_unit_id": hale})
        assert set(caught.value.errors) == {"statement", "kind"}

        for values, fields in [
            ({"design": "great", "operation": "effective", "note": SEEN}, {"design"}),
            ({"design": "effective", "operation": None, "note": " "}, {"operation", "note"}),
            ({"design": "effective", "operation": "effective", "note": SEEN, "basis": "hunch"},
             {"basis"}),
        ]:  # fmt: skip
            with pytest.raises(Invalid) as caught:
                controls.rate(session, steward, control, **values)
            assert set(caught.value.errors) == fields
        first = rated(session, steward, control, "effective", "partly")
        second = rated(session, steward, control, "effective", "effective")
        assert first.superseded_by == second.id and (first.operation, second.basis) == (
            "partly", "judgment",
        )  # fmt: skip
        shown = records.detail(session, steward, CONTROL, control)
        assert (shown["state"], shown["rating"]["rated_by"]) == ("effective", "Steward Person")
        assert [r["superseded"] for r in controls.ratings(session, control)] == [False, True]
    for role, allowed in [("assessor", True), ("manager", True), ("member", False),
                          ("leader", False), ("auditor", False), ("admin", False)]:  # fmt: skip
        with db.write(ME.actor) as session:
            control = find(session, CONTROL, "CTL-0001")
            if allowed:
                rated(session, who(db, people, role), control, "effective", "effective")
            else:
                with pytest.raises(PermissionDenied):
                    rated(session, who(db, people, role), control, "effective", "effective")


def test_a_rating_goes_stale(db: Database, people: People) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session, frozen_at(datetime(2026, 1, 10, tzinfo=UTC)):
        control = add_control(session, steward, people.units["HALE"], "Backups tested")
        rated(session, steward, control, "effective", "effective")
        assert controls.state_of(session, control) == "effective"
        assert controls.state_of(session, control, today=date(2027, 1, 10)) == "effective"
        assert controls.state_of(session, control, today=date(2027, 1, 11)) == "stale"
        rows, _ = records.search(session, steward, CONTROL, {"state": "effective"})
        assert [row.ref for row in rows] == [control.ref]
        assert records.search(session, steward, CONTROL, {"state": "not_assessed"})[1] == 0


# --- The suggested residual rating ----------------------------------------------------------


def test_the_worked_example_in_the_engine_document(db: Database, people: People) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        risk, made = setup_risk(session, people, steward)
        suggestion = register.suggestion(session, risk)
        assert suggestion is not None
        assert (suggestion["likelihood"], suggestion["impact"], suggestion["rating"]) == (
            3, 4, "high",
        )  # fmt: skip
        assert suggestion["totals"] == {"likelihood": 1.5, "impact": 1.5}
        lines = {line["name"]: (line["state"], line["counts"]) for line in suggestion["controls"]}
        assert lines == {
            "Maintenance": ("effective", 1.0),
            "Alarm": ("partly", 0.5),
            "Signage": ("not_assessed", 0.0),  # unknown counts for nothing
            "Split": ("effective", 1.0),
            "Spare": ("effective", 0.5),
        }
        # The suggestion is kept on the assessment beside the assessor's own judgment.
        agreed = judge(session, steward, risk, "residual", 3, mission=4)
        assert agreed.suggested is not None and agreed.suggested["rating"] == "high"
        departed = judge(session, steward, risk, "residual", 2, mission=4)
        assert (departed.rating, departed.suggested["rating"]) == ("moderate", "high")
        assert not risk.residual_in_doubt  # a judgment that departs is not thereby in doubt
        shown = controls.of_risk(session, steward, risk)
        assert [c["control"]["name"] for c in shown["controls"]] == list(made)
        assert shown["controls"][1]["control"]["state"] == "partly"
        assert shown["suggestion"]["rating"] == "high" and shown["hidden"] == 0


def test_no_number_of_controls_argues_a_risk_away(db: Database, people: People) -> None:
    steward, hale = who(db, people, "steward"), people.units["HALE"]
    with db.write(steward.actor) as session:
        risk = raise_risk(session, steward, hale)
        judge(session, steward, risk, "inherent", 5, safety=5)
        for number in range(6):
            control = add_control(session, steward, hale, f"Control {number}")
            rated(session, steward, control, "effective", "effective")
            controls.link(session, steward, risk, control, reduces="both", reliance="primary")
        suggestion = register.suggestion(session, risk)
        assert suggestion["steps"] == {"likelihood": 2, "impact": 2} and suggestion["limit"] == 2
        assert (suggestion["likelihood"], suggestion["impact"]) == (3, 3)


def test_linking_is_checked(db: Database, people: People) -> None:
    steward, member, manager = (who(db, people, r) for r in ("steward", "member", "manager"))
    hale, cancer = people.units["HALE"], people.units["CANCER"]
    with db.write(ME.actor) as session:
        risk = raise_risk(session, steward, hale)
        control = add_control(session, steward, hale, "Alarm")
        sealed = add_control(session, manager, cancer, "Sealed", restricted=True)
        for values, field in [
            ({"reduces": "everything", "reliance": "primary"}, "reduces"),
            ({"reduces": "impact", "reliance": "entirely"}, "reliance"),
            ({"reduces": "impact", "reliance": "primary", "note": "x" * 301}, "note"),
        ]:
            with pytest.raises(Invalid) as caught:
                controls.link(session, steward, risk, control, **values)
            assert field in caught.value.errors
        with pytest.raises(PermissionDenied):
            controls.link(session, member, risk, control, reduces="impact", reliance="primary")
        with pytest.raises(NotFound):  # a control they may not see is, to them, not there
            controls.link(session, steward, risk, sealed, reduces="impact", reliance="primary")
        controls.link(session, steward, risk, control, reduces="impact", reliance="primary")
        again = controls.link(
            session, steward, risk, control, reduces="both", reliance="supporting", note="Helps"
        )
        assert (again.reduces, again.reliance, again.note) == ("both", "supporting", "Helps")
        assert len(controls.of_risk(session, steward, risk)["controls"]) == 1  # linked once
        about = records.detail(session, steward, CONTROL, control)["reduces"]
        assert [r["ref"] for r in about["risks"]] == [risk.ref]
        rows, _ = records.search(session, steward, CONTROL, {"risk": risk.ref})
        assert [row.ref for row in rows] == [control.ref]
        records.update(session, steward, CONTROL, control, {"status": "retired"}, version=1)
        with pytest.raises(Invalid) as caught:
            controls.link(session, steward, risk, control, reduces="impact", reliance="primary")
        assert "retired" in caught.value.errors["control"]
        controls.unlink(session, steward, risk, control)
        with pytest.raises(NotFound):
            controls.unlink(session, steward, risk, control)


def test_a_control_that_gets_worse_puts_the_rating_in_doubt(db: Database, people: People) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        risk, made = setup_risk(session, people, steward)
        judge(session, steward, risk, "residual", 3, mission=4)  # high, as suggested
        assert not risk.residual_in_doubt
        # A control improving, or one that mattered little getting worse, changes nothing.
        rated(session, steward, made["Alarm"], "effective", "effective")
        rated(session, steward, made["Signage"], "ineffective", "ineffective")
        assert not risk.residual_in_doubt and risk.residual_rating == "high"
        # The maintenance contract lapses and the alarm fails. Likelihood is no longer
        # brought down, but on this matrix the rating does not move, so nothing is flagged.
        rated(session, steward, made["Maintenance"], "effective", "ineffective")
        rated(session, steward, made["Alarm"], "effective", "ineffective")
        assert register.suggestion(session, risk)["rating"] == "high"
        assert not risk.residual_in_doubt
        # Then the collection is found not to be split after all, and impact is not reduced.
        rated(session, steward, made["Split"], "ineffective", "ineffective")
        assert risk.residual_in_doubt and risk.residual_rating == "high"  # flagged, not changed
        for name in ("Maintenance", "Alarm", "Split"):
            assert f"{name} is now ineffective" in risk.residual_doubt_reason
        assert risk.residual_doubt_reason.endswith("The controls now suggest Critical.")
        flagged, _ = records.search(session, steward, RISK, {"in_doubt": True})
        assert [row.ref for row in flagged] == [risk.ref]
        # Putting the control right and assessing again settles it.
        rated(session, steward, made["Split"], "effective", "effective")
        judge(session, steward, risk, "residual", 4, mission=4)
        assert not risk.residual_in_doubt and risk.residual_doubt_reason is None
        # Unlinking a control the rating leaned on raises the doubt again.
        controls.unlink(session, steward, risk, made["Split"])
        assert risk.residual_in_doubt and "Split is no longer linked" in risk.residual_doubt_reason


# --- Treatment ----------------------------------------------------------------------------


def above_appetite(session, people: People, steward: Principal) -> Risk:  # type: ignore[no-untyped-def]
    risk = raise_risk(session, steward, people.units["HALE"])  # appetite: moderate
    judge(session, steward, risk, "inherent", 4, mission=5)
    judge(session, steward, risk, "residual", 3, mission=4)  # high
    assert risk.standing == "needs_decision"
    return risk


def test_a_plan_treats_a_risk_and_finishing_it_asks_for_a_new_assessment(
    db: Database, people: People
) -> None:
    steward, member = who(db, people, "steward"), who(db, people, "member")
    me, them = people.accounts["steward"], people.accounts["member"]
    with db.write(steward.actor) as session, frozen_at(datetime(2026, 3, 1, tzinfo=UTC)):
        risk = above_appetite(session, people, steward)
        for values, fields in [
            ({"objective": " ", "owner_id": me, "due_on": "soon"}, {"objective", "due_on"}),
            ({"objective": "Split the collection", "owner_id": 9999, "due_on": "2026-09-01",
              "target_rating": "tiny"}, {"owner_id", "target_rating"}),
        ]:  # fmt: skip
            with pytest.raises(Invalid) as caught:
                treatment.create_plan(session, steward, risk, **values)
            assert set(caught.value.errors) == fields
        with pytest.raises(PermissionDenied):
            treatment.create_plan(
                session, member, risk, objective="x", owner_id=them, due_on="2026-09-01"
            )
        plan = treatment.create_plan(
            session, steward, risk, objective="Split the collection across two buildings",
            owner_id=me, due_on="2026-09-01", target_rating="moderate",
        )  # fmt: skip
        assert (plan.ref, risk.standing, risk.response) == ("PLN-0001", "treated", "reduce")
        first = treatment.add_action(
            session, steward, plan, title="Buy two freezers", owner_id=them, due_on="2026-05-01"
        )
        second = treatment.add_action(
            session, steward, plan, title="Move half the boxes", owner_id=me, due_on="2026-08-01"
        )
        assert (first.ref, second.ref) == ("ACT-0001", "ACT-0002")
        shown = treatment.plan_view(session, steward, plan)
        assert shown["progress"] == {"done": 0, "total": 2} and not shown["overdue"]

        # Its owner may progress an action; they may not rewrite, reassign, or cancel it.
        treatment.update_action(session, member, first, {"status": "in_progress"})
        for changes in ({"title": "Buy one"}, {"owner_id": me}, {"status": "cancelled"}):
            with pytest.raises(PermissionDenied):
                treatment.update_action(session, member, first, changes)
        with pytest.raises(PermissionDenied):
            treatment.update_action(session, member, second, {"status": "done"})  # not theirs
        # Moving the date needs a reason, and the move stays on the record.
        with pytest.raises(Invalid) as caught:
            treatment.update_action(session, member, first, {"due_on": "2026-06-15"})
        assert "reason" in caught.value.errors
        treatment.update_action(
            session, member, first, {"due_on": "2026-06-15", "reason": "The supplier is late."}
        )
        assert (first.due_on, first.original_due_on) == (date(2026, 6, 15), date(2026, 5, 1))
        assert first.extensions == [
            {"from": "2026-05-01", "to": "2026-06-15", "reason": "The supplier is late.",
             "by": "Member Person", "on": "2026-03-01"}
        ]  # fmt: skip
        treatment.update_action(
            session, member, first, {"status": "done", "completion_note": "Delivered."}
        )
        with pytest.raises(Conflict, match="closed"):
            treatment.update_action(session, member, first, {"completion_note": "Again"})
        assert (plan.status, risk.standing, risk.residual_in_doubt) == ("active", "treated", False)

        # The last action closing completes the plan. The rating does not move: the owner is
        # asked to assess again, and until they do the risk needs a decision.
        treatment.update_action(session, steward, second, {"status": "done"})
        assert plan.status == "complete" and risk.residual_rating == "high"
        assert risk.residual_in_doubt and "PLN-0001 is complete" in risk.residual_doubt_reason
        assert risk.standing == "needs_decision"
        with pytest.raises(Conflict):
            treatment.add_action(
                session, steward, plan, title="x", owner_id=me, due_on="2026-09-01"
            )
        judge(session, steward, risk, "residual", 2, mission=4)
        assert (risk.residual_rating, risk.standing, risk.residual_in_doubt) == (
            "moderate", "within", False,
        )  # fmt: skip
        # Reopening an action reopens the plan.
        treatment.update_action(session, steward, second, {"status": "open"})
        assert plan.status == "active"


def test_an_overdue_plan_no_longer_counts(db: Database, people: People) -> None:
    steward, me = who(db, people, "steward"), people.accounts["steward"]
    with db.write(steward.actor) as session, frozen_at(datetime(2026, 3, 1, tzinfo=UTC)):
        risk = above_appetite(session, people, steward)
        plan = treatment.create_plan(
            session, steward, risk, objective="Fix it", owner_id=me, due_on="2026-04-01"
        )
        action = treatment.add_action(
            session, steward, plan, title="Do it", owner_id=me, due_on="2026-03-20"
        )
        assert risk.standing == "treated"
    with frozen_at(datetime(2026, 4, 2, tzinfo=UTC)):
        assert treatment.catch_up(db) == 1  # the calendar moved on
        assert treatment.catch_up(db) == 0  # and there is nothing more to do
        with db.write(steward.actor) as session:
            risk = find(session, RISK, "RSK-0001")
            assert risk.standing == "needs_decision"
            view = treatment.plan_view(session, steward, treatment.find_plan(session, "PLN-0001"))
            assert view["overdue"] and view["actions"][0]["overdue"]
            late, total = treatment.search_actions(session, steward, {"overdue": True})
            assert [a["ref"] for a in late] == [action.ref] and total == 1
            assert [p["ref"] for p in treatment.search_plans(session, steward, {"overdue": True})]
            with pytest.raises(Invalid) as caught:
                treatment.cancel_plan(session, steward, plan, " ")
            assert "reason" in caught.value.errors
            plan = treatment.find_plan(session, "PLN-0001")
            treatment.cancel_plan(session, steward, plan, "Superseded by the building project.")
            assert plan.status == "cancelled"
            assert treatment.find_action(session, "ACT-0001").status == "cancelled"
            with pytest.raises(Conflict):
                treatment.cancel_plan(session, steward, plan, "Again")


def test_a_response_is_recorded_with_its_reason(db: Database, people: People) -> None:
    steward, member = who(db, people, "steward"), who(db, people, "member")
    with db.write(steward.actor) as session:
        risk = above_appetite(session, people, steward)
        for response, rationale, field in [
            ("ignore", "x", "response"),
            ("avoid", " ", "rationale"),
        ]:
            with pytest.raises(Invalid) as caught:
                treatment.respond(session, steward, risk, response, rationale)
            assert field in caught.value.errors
        with pytest.raises(PermissionDenied):
            treatment.respond(session, member, risk, "avoid", "Stop.")
        treatment.respond(session, steward, risk, "transfer", "Covered by the equipment policy.")
        assert (risk.response, risk.standing) == ("transfer", "needs_decision")


# --- Acceptance ---------------------------------------------------------------------------


def test_who_may_accept(db: Database, people: People) -> None:
    steward = who(db, people, "steward")
    with db.write(ME.actor) as session:
        risk = above_appetite(session, people, steward)  # high, in the Hale Lab
        within = raise_risk(session, steward, people.units["HALE"], "Small")
        judge(session, steward, within, "residual", 1, mission=2)
        # A leader of the division, whose limit reaches high, may. Nobody else may.
        expect = {
            "leader": None,
            "steward": "Nobody accepts a risk they own",  # they raised it, so they own it
            "manager": "Only a leader",
            "admin": "Only a leader",
            "member": "Only a leader",
            "assessor": "Only a leader",
            "auditor": "Only a leader",
        }
        for role, reason in expect.items():
            may = treatment.authority(session, who(db, people, role), risk)
            assert may["allowed"] is (reason is None), role
            assert reason is None or may["reason"].startswith(reason), role
        assert treatment.authority(session, ME, risk)["reason"].endswith("by a named person.")
        nothing = treatment.authority(session, who(db, people, "leader"), within)
        assert not nothing["allowed"] and "nothing to accept" in nothing["reason"]

        # The same person as a leader with no limit, or one that stops at moderate, may not.
        leader = accounts.get(session, people.accounts["leader"])
        for limit in (None, "moderate"):
            accounts.set_grants(
                session, ME, leader,
                [Grant("leader", org_unit_id=people.units["IMM"], accept_limit=limit)],
            )  # fmt: skip
            may = treatment.authority(session, accounts.principal_for(session, leader), risk)
            assert not may["allowed"] and "limit reaches High" in may["reason"]
        # A leader of another division may not, whatever their limit.
        accounts.set_grants(
            session, ME, leader,
            [Grant("leader", org_unit_id=people.units["CANCER"], accept_limit="critical")],
        )  # fmt: skip
        may = treatment.authority(session, accounts.principal_for(session, leader), risk)
        assert not may["allowed"] and may["reason"].startswith("Only a leader")
        # A leader who owns the risk may not accept it, whatever their limit.
        accounts.set_grants(
            session, ME, leader,
            [Grant("leader", org_unit_id=people.units["NMI"], accept_limit="critical")],
        )  # fmt: skip
        records.set_owners(
            session, steward, RISK, risk, [{"account_id": leader.id, "kind": "owner"}]
        )
        session.flush()
        may = treatment.authority(session, accounts.principal_for(session, leader), risk)
        assert not may["allowed"] and may["reason"].startswith("Nobody accepts a risk they own")
        # A moderate risk above appetite needs only a leader of the unit or above.
        low = raise_risk(session, steward, people.units["HALE"], "Dosing", category="medication")
        judge(session, steward, low, "residual", 3, safety=3)
        assert low.standing == "needs_decision"
        accounts.set_grants(session, ME, leader, [Grant("leader", org_unit_id=people.units["IMM"])])
        assert treatment.authority(session, accounts.principal_for(session, leader), low)["allowed"]


def test_accepting_a_risk(db: Database, people: People) -> None:
    steward, leader = who(db, people, "steward"), who(db, people, "leader")
    with db.write(leader.actor) as session, frozen_at(datetime(2026, 3, 1, tzinfo=UTC)):
        risk = above_appetite(session, people, steward)
        with pytest.raises(PermissionDenied, match="Nobody accepts a risk they own"):
            treatment.accept(session, steward, risk, rationale="Fine.", expires_on="2026-12-01")
        for values, field in [
            ({"rationale": " ", "expires_on": "2026-12-01"}, "rationale"),
            ({"rationale": "Fine.", "expires_on": "2026-03-01"}, "expires_on"),  # not the future
            ({"rationale": "Fine.", "expires_on": "2027-03-02"}, "expires_on"),  # over a year
        ]:
            with pytest.raises(Invalid) as caught:
                treatment.accept(session, leader, risk, **values)
            assert field in caught.value.errors
        assert "at most 12 months" in caught.value.errors["expires_on"]
        made = treatment.accept(
            session, leader, risk, rationale="It cannot be patched before the grant ends.",
            expires_on="2026-09-30", conditions="Kept off the general network.",
        )  # fmt: skip
        assert (made.rating_accepted, made.appetite, made.accepted_by_name) == (
            "high", "moderate", "Leader Person",
        )  # fmt: skip
        assert (risk.standing, risk.residual_rating) == ("accepted", "high")
        view = treatment.of_risk(session, leader, risk)
        assert view["acceptances"][0]["state"] == "in_force"
        assert view["acceptances"][0]["expires_in_days"] == 213
        assert [a["risk"]["ref"] for a in treatment.search_acceptances(
            session, leader, {"expiring_within": 220})] == [risk.ref]  # fmt: skip
        assert treatment.search_acceptances(session, leader, {"expiring_within": 200}) == []
        # If the risk gets worse than what was accepted, the acceptance no longer covers it.
        judge(session, steward, risk, "residual", 4, mission=5)
        assert (risk.residual_rating, risk.standing) == ("critical", "needs_decision")
        judge(session, steward, risk, "residual", 3, mission=4)
        assert risk.standing == "accepted"
    # On the day after it expires, the risk goes back to needing a decision.
    with frozen_at(datetime(2026, 9, 30, tzinfo=UTC)):
        assert treatment.catch_up(db) == 0
    with frozen_at(datetime(2026, 10, 1, tzinfo=UTC)):
        assert treatment.catch_up(db) == 1
        with db.write(leader.actor) as session:
            risk = find(session, RISK, "RSK-0001")
            assert risk.standing == "needs_decision"
            view = treatment.of_risk(session, leader, risk)
            assert view["acceptances"][0]["state"] == "expired"
            renewed = treatment.accept(
                session, leader, risk, rationale="Still the case.", expires_on="2027-03-31"
            )
            assert risk.standing == "accepted"
            with pytest.raises(PermissionDenied):
                treatment.withdraw(session, steward, renewed, "No.")
            with pytest.raises(Invalid):
                treatment.withdraw(session, leader, renewed, " ")
            treatment.withdraw(session, leader, renewed, "The instrument has been replaced.")
            assert risk.standing == "needs_decision"
            with pytest.raises(Conflict):
                treatment.withdraw(session, leader, renewed, "Again.")
            states = [a["state"] for a in treatment.of_risk(session, leader, risk)["acceptances"]]
            assert states == ["withdrawn", "expired"]


def test_the_story_of_a_risk_includes_what_was_done_about_it(db: Database, people: People) -> None:
    steward, leader = who(db, people, "steward"), who(db, people, "leader")
    with db.write(steward.actor) as session:
        risk, _ = setup_risk(session, people, steward)
        judge(session, steward, risk, "residual", 3, mission=4)
        treatment.create_plan(
            session, steward, risk, objective="Monitor out of hours",
            owner_id=people.accounts["steward"], due_on="2031-01-01",
        )  # fmt: skip
    with db.write(leader.actor) as session:
        risk = find(session, RISK, "RSK-0001")
        treatment.accept(session, leader, risk, rationale="For now.", expires_on="2027-06-30")
    with db.read() as session:
        risk = find(session, RISK, "RSK-0001")
        titles = [entry["title"] for entry in history.for_record(session, RISK, risk)]
        story = history.for_record(session, CONTROL, find(session, CONTROL, "CTL-0002"))
    assert "Standing changed" in titles and titles[-1] == "Added this risk"
    assert [entry["title"] for entry in story][:1] == [
        "Rated: design Effective, operation Partly effective"
    ]


# --- The API ------------------------------------------------------------------------------


def test_controls_and_treatment_through_the_api(as_role: Clients, people: People) -> None:
    steward, member, leader, assessor = (
        as_role(role) for role in ("steward", "member", "leader", "assessor")
    )
    hale = people.units["HALE"]
    entry = member.get("/api/v1/control-library", params={"q": "alarm"}).json()["data"][0]
    assert entry["key"] == "freezer_monitoring" and entry["reduces"] == "likelihood"

    risk = steward.post(
        "/api/v1/risks",
        json={"name": "Freezer failure", "category": "data_quality", "org_unit_id": hale},
    ).json()["data"]["ref"]
    assess = {"impact_levels": {"mission": 5}, "rationale": WHY}
    steward.post(
        f"/api/v1/risks/{risk}/assessments", json={"kind": "inherent", "likelihood": 4, **assess}
    )
    made = steward.post(
        "/api/v1/controls",
        json={"name": entry["title"], "statement": entry["statement"], "kind": entry["kind"],
              "nature": entry["nature"], "frequency": entry["frequency"], "org_unit_id": hale,
              "library_key": entry["key"]},
    )  # fmt: skip
    assert made.status_code == 201
    control = made.json()["data"]
    assert (control["ref"], control["state"]) == ("CTL-0001", "not_assessed")
    assert member.post("/api/v1/controls", json={"name": "x"}).status_code == 403

    linked = steward.put(
        f"/api/v1/risks/{risk}/controls",
        json={"control": control["ref"], "reduces": "likelihood", "reliance": "primary"},
    )
    assert linked.status_code == 200
    assert linked.json()["data"]["suggestion"]["rating"] == "critical"  # not assessed: nothing
    assert member.put(
        f"/api/v1/risks/{risk}/controls",
        json={"control": control["ref"], "reduces": "impact", "reliance": "primary"},
    ).status_code == 403  # fmt: skip
    rating = {"design": "effective", "operation": "effective", "note": SEEN}
    assert member.post(f"/api/v1/controls/{control['ref']}/ratings", json=rating).status_code == 403
    rated_ = assessor.post(f"/api/v1/controls/{control['ref']}/ratings", json=rating)
    assert rated_.status_code == 201 and rated_.json()["data"]["state"] == "effective"
    now = member.get(f"/api/v1/risks/{risk}/controls").json()["data"]
    assert (now["suggestion"]["likelihood"], now["suggestion"]["rating"]) == (3, "high")
    assert member.get(f"/api/v1/controls/{control['ref']}/ratings").json()["data"][0][
        "rated_by"
    ] == ("Assessor Person")
    page = member.get("/api/v1/controls", params={"state": "effective"}).json()
    assert page["meta"]["total"] == 1 and page["data"][0]["risks"] == 1

    judged = steward.post(
        f"/api/v1/risks/{risk}/assessments", json={"kind": "residual", "likelihood": 3, **assess}
    ).json()["data"]
    assert judged["standing"] == "needs_decision"
    assert judged["assessments"]["residual"]["suggested"]["rating"] == "high"

    # The steward owns the risk and may not accept it; the leader may, within the limit.
    care = member.get(f"/api/v1/risks/{risk}/treatment").json()["data"]
    assert care["plans"] == [] and not care["authority"]["allowed"]
    body = {"rationale": "Until the new building opens.", "expires_on": "2099-01-01"}
    assert steward.post(f"/api/v1/risks/{risk}/acceptances", json=body).status_code == 403
    assert member.post(f"/api/v1/risks/{risk}/acceptances", json=body).status_code == 403
    too_long = leader.post(f"/api/v1/risks/{risk}/acceptances", json=body)
    assert (
        too_long.status_code == 422
        and "at most 12 months" in too_long.json()["errors"][0]["message"]
    )
    latest = leader.get(f"/api/v1/risks/{risk}/treatment").json()["data"]["authority"]["latest"]
    accepted = leader.post(f"/api/v1/risks/{risk}/acceptances", json={**body, "expires_on": latest})
    assert accepted.status_code == 201
    assert accepted.json()["data"]["acceptances"][0]["accepted_by"] == "Leader Person"
    assert member.get(f"/api/v1/risks/{risk}").json()["data"]["standing"] == "accepted"
    listed = leader.get("/api/v1/acceptances", params={"state": "in_force", "mine": True}).json()
    acceptance = listed["data"][0]
    assert acceptance["risk"]["ref"] == risk
    assert steward.post(
        f"/api/v1/acceptances/{acceptance['id']}/withdrawal", json={"reason": "No."}
    ).status_code == 403  # fmt: skip
    assert leader.post(
        f"/api/v1/acceptances/{acceptance['id']}/withdrawal", json={"reason": "Replaced."}
    ).json()["data"]["state"] == "withdrawn"  # fmt: skip
    assert (
        leader.post("/api/v1/acceptances/9999/withdrawal", json={"reason": "x"}).status_code == 404
    )

    plan = steward.post(
        f"/api/v1/risks/{risk}/plans",
        json={"objective": "Monitor the alarm out of hours", "due_on": "2099-06-01",
              "owner_id": people.accounts["steward"], "target_rating": "moderate"},
    )  # fmt: skip
    assert plan.status_code == 201
    ref = plan.json()["data"]["ref"]
    added = steward.post(
        f"/api/v1/plans/{ref}/actions",
        json={"title": "Sign the call-out contract", "owner_id": people.accounts["member"],
              "due_on": "2099-03-01"},
    )  # fmt: skip
    assert added.status_code == 201 and added.json()["data"]["progress"] == {"done": 0, "total": 1}
    assert member.get(f"/api/v1/risks/{risk}").json()["data"]["standing"] == "treated"
    mine = member.get("/api/v1/actions", params={"mine": True, "status": "open"}).json()
    assert mine["meta"]["total"] == 1 and mine["data"][0]["can"] == {"act": True, "manage": False}
    action = mine["data"][0]["ref"]
    assert (
        member.patch(f"/api/v1/actions/{action}", json={"due_on": "2099-04-01"}).status_code == 422
    )
    done = member.patch(
        f"/api/v1/actions/{action}", json={"status": "done", "completion_note": "Signed."}
    )
    assert done.status_code == 200 and done.json()["data"]["status"] == "done"
    finished = member.get(f"/api/v1/plans/{ref}").json()["data"]
    assert finished["status"] == "complete" and finished["risk"]["standing"] == "needs_decision"
    after = member.get(f"/api/v1/risks/{risk}").json()["data"]
    assert after["residual_in_doubt"] and "is complete" in after["residual_doubt_reason"]
    assert (
        steward.post(f"/api/v1/plans/{ref}/cancellation", json={"reason": "x"}).status_code == 409
    )
    assert (
        member.get("/api/v1/plans", params={"status": "complete"}).json()["data"][0]["ref"] == ref
    )
    assert steward.put(
        f"/api/v1/risks/{risk}/response", json={"response": "avoid", "rationale": "Stop the work."}
    ).json()["data"]["response"] == "avoid"  # fmt: skip
    assert (
        steward.delete(f"/api/v1/risks/{risk}/controls/{control['ref']}").json()["data"]["controls"]
        == []
    )
    assert member.get("/api/v1/plans/PLN-9999").status_code == 404
    assert member.patch("/api/v1/actions/ACT-9999", json={"status": "done"}).status_code == 404
