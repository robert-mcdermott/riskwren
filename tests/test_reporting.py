"""What each person owes, the heat map, and the dashboard: every figure opens its own list."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from riskwren.controls import service as controls
from riskwren.core.clock import frozen_at
from riskwren.db.engine import Database
from riskwren.inventory import records
from riskwren.inventory.registry import SYSTEM
from riskwren.people import accounts
from riskwren.reporting import service as reporting
from riskwren.treatment import service as treatment
from tests.people import ME, ROLES, People
from tests.test_risks import judge, raise_risk, who
from tests.test_treatment import add_control, rated

Clients = Callable[[str | None], TestClient]
THEN = datetime(2026, 3, 1, tzinfo=UTC)
NOW = datetime(2026, 11, 20, tzinfo=UTC)


@pytest.fixture
def world(db: Database, people: People) -> People:
    """A register with something in every state: rated and not, within appetite and above
    it, treated, accepted, overdue, in doubt, restricted, closed, and in two divisions."""
    steward, manager, leader = (who(db, people, role) for role in ("steward", "manager", "leader"))
    hale, immuno, cancer = people.units["HALE"], people.units["IMM"], people.units["CANCER"]
    me = people.accounts["steward"]
    with db.write(ME.actor) as session, frozen_at(THEN):
        specimens = raise_risk(session, steward, hale, "Specimens")
        judge(session, steward, specimens, "inherent", 4, mission=5)
        alarm = add_control(session, steward, hale, "Alarm")
        rated(session, steward, alarm, "effective", "effective")
        controls.link(session, steward, specimens, alarm, reduces="likelihood", reliance="primary")
        judge(session, steward, specimens, "residual", 3, mission=4)  # high: above appetite
        plan = treatment.create_plan(
            session, steward, specimens, objective="Split", owner_id=me, due_on="2027-06-01"
        )
        treatment.add_action(session, steward, plan, title="Buy", owner_id=me, due_on="2026-06-01")
        treatment.add_action(
            session, steward, plan, title="Move", owner_id=people.accounts["member"],
            due_on="2027-03-01",
        )  # fmt: skip

        instrument = raise_risk(session, manager, immuno, "Instrument", category="integrity_change")
        judge(session, manager, instrument, "inherent", 4, trust=4)
        judge(session, manager, instrument, "residual", 4, trust=4)  # high
        treatment.accept(session, leader, instrument, rationale="For now.", expires_on="2026-12-15")

        phishing = raise_risk(session, manager, cancer, "Phishing", category="confidentiality")
        judge(session, manager, phishing, "inherent", 5, trust=3)
        judge(session, manager, phishing, "residual", 2, trust=2)  # low: within appetite

        dosing = raise_risk(session, manager, cancer, "Dosing", category="medication")
        judge(session, manager, dosing, "residual", 3, safety=4)  # high, and nothing done

        raise_risk(session, steward, hale, "Unrated")
        sealed = raise_risk(session, steward, hale, "Sealed", restricted=True)
        judge(session, steward, sealed, "residual", 5, safety=5)  # critical
        gone = raise_risk(session, steward, hale, "Gone")
        from riskwren.risk import register

        register.update(
            session, steward, gone, {"status": "closed", "closed_reason": "Moved."}, version=1
        )
        add_control(session, steward, hale, "Unrated control")
        partly = add_control(session, manager, cancer, "Training")
        rated(session, manager, partly, "partly", "effective")
        records.create(
            session, manager, SYSTEM, {"name": "Orphan", "kind": "device", "org_unit_id": hale}
        )
    with db.write(ME.actor) as session, frozen_at(NOW):
        # The alarm is later found not to work: the specimen risk falls into doubt.
        rated(session, steward, session.get(type(alarm), alarm.id), "effective", "ineffective")
    return people


def test_every_figure_opens_a_list_of_that_length(as_role: Clients, world: People) -> None:
    lists = {"risks": "/api/v1/risks", "controls": "/api/v1/controls", "actions": "/api/v1/actions"}

    def total(client: TestClient, kind: str, filters: dict[str, object]) -> int:
        params = {key: str(value).lower() if isinstance(value, bool) else value
                  for key, value in filters.items()}  # fmt: skip
        answer = client.get(lists[kind], params={**params, "limit": 1})
        assert answer.status_code == 200, answer.text
        return int(answer.json()["meta"]["total"])

    with frozen_at(NOW):
        seen = {}
        for role in ROLES:
            client = as_role(role)
            for unit in (None, world.units["IMM"]):
                params = {"unit": unit} if unit else {}
                board = client.get("/api/v1/dashboard", params=params).json()["data"]
                checked = 0
                for name, figure in board["totals"].items():
                    kind = "actions" if name.startswith("actions") else "risks"
                    assert total(client, kind, figure["filters"]) == figure["count"], (role, name)
                    checked += 1
                for group in ("by_standing", "by_rating", "by_category", "by_unit"):
                    for figure in board[group]:
                        assert total(client, "risks", figure["filters"]) == figure["count"], (
                            role, group, figure,
                        )  # fmt: skip
                        checked += 1
                for figure in [board["controls"]["total"], board["controls"]["stale"],
                               *board["controls"]["by_state"]]:  # fmt: skip
                    assert total(client, "controls", figure["filters"]) == figure["count"], role
                    checked += 1
                assert checked >= 20
                # The parts add up to the whole.
                open_risks = board["totals"]["open"]["count"]
                assert sum(f["count"] for f in board["by_standing"]) == open_risks
                assert sum(f["count"] for f in board["by_category"]) == open_risks
                assert len(board["top_risks"]) <= 8
                for kind in ("inherent", "residual", "target"):
                    heat = client.get("/api/v1/heat-map", params={"kind": kind, **params}).json()[
                        "data"
                    ]
                    assert heat["rated"] + heat["unrated"] == open_risks, (role, kind)
                    assert sum(heat["by_rating"].values()) == heat["rated"]
                    for impact, row in enumerate(heat["cells"], 1):
                        for likelihood, number in enumerate(row, 1):
                            cell = {"status": "open", f"{kind}_likelihood": likelihood,
                                    f"{kind}_impact": impact, **params}  # fmt: skip
                            assert total(client, "risks", cell) == number, (role, kind, cell)
                if unit is None:
                    seen[role] = open_risks
    # Six open risks in all; one is restricted, and four are in the steward's division.
    assert seen == {
        "admin": 6, "manager": 6, "auditor": 6,
        "assessor": 5,  # never what is restricted
        "leader": 4, "steward": 4,  # their division, restricted included
        "member": 2,  # the ordinary risks of the lab they work in
    }  # fmt: skip


def test_the_dashboard_says_where_the_register_stands(db: Database, world: People) -> None:
    manager = who(db, world, "manager")
    with db.read() as session, frozen_at(NOW):
        board = reporting.dashboard(session, manager)
        totals = {name: figure["count"] for name, figure in board["totals"].items()}
        assert totals == {
            "open": 6,
            "above_appetite": 4,  # specimens, instrument, dosing, and the sealed risk
            "needs_decision": 2,  # dosing and sealed: nothing has been done about either
            "review_overdue": 5,  # everything last looked at in March, but the one low risk
            "in_doubt": 1,
            "not_assessed": 1,
            "actions_open": 2,
            "actions_overdue": 1,
        }
        standing = {figure["key"]: figure["count"] for figure in board["by_standing"]}
        assert standing == {
            "not_assessed": 1, "within": 1, "treated": 1, "accepted": 1, "needs_decision": 2,
        }  # fmt: skip
        assert [(f["label"], f["count"]) for f in board["by_rating"]] == [
            ("Critical", 1), ("High", 3), ("Moderate", 0), ("Low", 1),
        ]  # fmt: skip
        research = next(c for c in board["by_category"] if c["key"] == "research")
        assert (research["count"], research["above"], research["appetite"]) == (3, 2, "moderate")
        assert [(u["name"], u["count"], u["above"]) for u in board["by_unit"]] == [
            ("Cancer Biology", 2, 1), ("Immunology", 4, 3),
        ]  # fmt: skip
        states = {f["key"]: f["count"] for f in board["controls"]["by_state"]}
        assert states == {"effective": 0, "partly": 1, "ineffective": 1, "not_assessed": 1}
        assert board["controls"]["total"]["count"] == 3 and board["controls"]["stale"]["count"] == 0
        assert board["top_risks"][0]["name"] == "Sealed"
        # Narrowed to one division, it counts that division and what is beneath it.
        division = reporting.dashboard(session, manager, unit=world.units["IMM"])
        assert division["totals"]["open"]["count"] == 4
        assert [u["name"] for u in division["by_unit"]] == ["Hale Lab"]
    with db.read() as session, frozen_at(datetime(2028, 1, 1, tzinfo=UTC)):
        later = reporting.dashboard(session, who(db, world, "manager"))
        assert later["controls"]["stale"]["count"] == 2  # every rating has aged out


def test_the_heat_map(db: Database, world: People) -> None:
    manager = who(db, world, "manager")
    with db.read() as session, frozen_at(NOW):
        heat = reporting.heat_map(session, manager)
        assert (heat["kind"], heat["rated"], heat["unrated"]) == ("residual", 5, 1)
        assert heat["cells"][3][2] == 2  # likelihood 3, impact 4: specimens and dosing
        assert heat["cells"][4][4] == 1 and heat["cells"][1][1] == 1
        assert heat["by_rating"] == {"low": 1, "moderate": 0, "high": 3, "critical": 1}
        assert heat["appetite"] is None
        inherent = reporting.heat_map(session, manager, kind="inherent")
        assert (inherent["rated"], inherent["unrated"]) == (3, 3)
        research = reporting.heat_map(session, manager, category="research")
        assert (research["rated"], research["appetite"]) == (2, "moderate")
        assert reporting.heat_map(session, manager, kind="nonsense")["kind"] == "residual"
        assert reporting.heat_map(session, manager, unit=world.units["CANCER"])["rated"] == 2


def test_home_lists_what_each_person_owes(db: Database, world: People) -> None:
    def owes(role: str) -> list[tuple[str, str, bool]]:
        with db.read() as session:
            person = accounts.principal_for(session, accounts.get(session, world.accounts[role]))
            listing = reporting.home(session, person)
            return [(item["kind"], item["title"], item["overdue"]) for item in listing["items"]]

    with frozen_at(NOW):
        steward = owes("steward")
        # Overdue first, soonest first: the action that is late is among them.
        late = [item for item in steward if item[2]]
        assert steward[: len(late)] == late and ("action", "Buy", True) in late
        assert ("assess", "Assess Specimens again", False) in steward  # the alarm failed
        assert ("assess", "Assess Unrated", True) in steward  # never assessed, and now late
        assert ("review", "Review Sealed", True) in steward
        assert ("decide", "Sealed needs a decision", False) in steward
        assert ("rate", "Rate Unrated control", False) in steward
        # What nobody answers for is shown to whoever keeps the unit.
        assert ("orphan", "Name an owner for Orphan", False) not in steward  # its maker owns it
        assert owes("member") == [("action", "Move", False)]
        leader = owes("leader")
        assert ("decide", "Sealed needs a decision", False) in leader
        assert ("acceptance", "Your acceptance of Instrument is about to expire", False) in leader
        assert not any(kind == "action" for kind, _, _ in leader)
        assert owes("auditor") == [] and owes("admin") == []
    # When an owner leaves, their records fall to the steward to reassign.
    with db.write(ME.actor) as session:
        accounts.update(
            session, ME, accounts.get(session, world.accounts["manager"]), {"status": "disabled"}
        )
    with frozen_at(NOW):
        steward = owes("steward")
        # Nothing is left without an owner: the steward stands in, and is asked to name
        # who takes each thing for good.
        assert not any(kind == "orphan" for kind, _, _ in steward)
        assert ("handover", "Name who takes what Manager Person held", False) in steward


def test_reports_through_the_api(as_role: Clients, world: People) -> None:
    with frozen_at(NOW):
        steward, member = as_role("steward"), as_role("member")
        mine = steward.get("/api/v1/home").json()["data"]
        assert mine["overdue"] >= 2 and mine["items"][0]["overdue"]
        assert any(item["href"].endswith("?tab=treatment") for item in mine["items"])
        assert mine["summary"]["needs_decision"]["count"] == 1  # in their division
        theirs = member.get("/api/v1/home").json()["data"]
        assert theirs["summary"] is None and len(theirs["items"]) == 1
        heat = member.get("/api/v1/heat-map", params={"category": "research"}).json()["data"]
        assert heat["rated"] == 1 and heat["appetite"] == "moderate"
        assert steward.get("/api/v1/heat-map", params={"category": "nonsense"}).status_code == 404
        # Reading the register brings standings up to date with the calendar.
        assert steward.get("/api/v1/risks/RSK-0002").json()["data"]["standing"] == "accepted"
    with frozen_at(datetime(2026, 12, 16, tzinfo=UTC)):
        board = as_role("manager").get("/api/v1/dashboard").json()["data"]
        standing = {f["key"]: f["count"] for f in board["by_standing"]}
        assert standing["accepted"] == 0 and standing["needs_decision"] == 3
