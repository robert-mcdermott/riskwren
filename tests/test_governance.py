"""Strategic objectives that risks threaten, and committee sessions: an agenda drawn from the
register, the decision taken on each item, and the minutes."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.core.clock import frozen_at
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import Notice
from riskwren.inventory import history, records
from riskwren.oversight import sessions
from riskwren.oversight.sessions import SESSION
from riskwren.reporting import graph
from riskwren.reporting import service as reporting
from riskwren.risk import objectives
from riskwren.risk.objectives import OBJECTIVE
from riskwren.risk.register import RISK
from tests.people import People
from tests.test_risks import raise_risk, who

Clients = Callable[[str | None], TestClient]
NOON = datetime(2026, 3, 2, 12, tzinfo=UTC)


def test_an_objectives_risks_are_exactly_those_that_name_it(
    db: Database, people: People, as_role: Clients
) -> None:
    leader, steward, member = (who(db, people, role) for role in ("leader", "steward", "member"))
    imm, hale = people.units["IMM"], people.units["HALE"]
    with db.write(leader.actor) as session, frozen_at(NOON):
        with pytest.raises(PermissionDenied):
            records.create(session, member, OBJECTIVE, {"name": "x", "org_unit_id": imm})
        grow = records.create(
            session, leader, OBJECTIVE,
            {"name": "Grow the cohort to 40,000 participants", "org_unit_id": imm,
             "period": "Strategic plan 2026 to 2030",
             "measure": "Enrolled participants, counted each June."},
        )  # fmt: skip
        trust = records.create(
            session, leader, OBJECTIVE,
            {"name": "Keep participants' trust", "org_unit_id": imm},
        )  # fmt: skip
        # A leader keeps it, unit and all, as the form sends it.
        records.update(
            session, leader, OBJECTIVE, trust, {"org_unit_id": imm, "period": "2026 to 2030"},
            version=trust.version,
        )  # fmt: skip
        old = records.create(session, leader, OBJECTIVE, {"name": "Old aim", "org_unit_id": imm})
        records.update(session, leader, OBJECTIVE, old, {"status": "retired"}, version=old.version)
        freezer = raise_risk(session, steward, hale, "Freezer failure")
        breach = raise_risk(session, steward, hale, "Participant data disclosed")
        unrelated = raise_risk(session, steward, hale, "Grant spending disallowed")
        objectives.set_objectives(session, steward, freezer, [grow.ref])
        objectives.set_objectives(session, steward, breach, [grow.ref, trust.ref])
        with pytest.raises(Invalid) as retired:
            objectives.set_objectives(session, steward, unrelated, [old.ref])
        assert "retired" in retired.value.errors["objectives"]
        with pytest.raises(PermissionDenied):
            objectives.set_objectives(session, member, unrelated, [grow.ref])
        # Exactly those that name it, from either side.
        shown = records.detail(session, steward, OBJECTIVE, grow)
        assert [row["ref"] for row in shown["threatened_by"]["risks"]] == [freezer.ref, breach.ref]
        assert [row["ref"] for row in objectives.risks_of(session, steward, trust)["risks"]] == [
            breach.ref
        ]
        named = records.detail(session, steward, RISK, breach)["objectives"]
        assert [each["ref"] for each in named] == [grow.ref, trust.ref]
        listed, _ = records.search(session, steward, RISK, {"objective": grow.ref})
        assert sorted(row.ref for row in listed) == sorted([freezer.ref, breach.ref])
        # Naming fewer takes the risk away from the objective, and the history says both.
        objectives.set_objectives(session, steward, breach, [trust.ref])
        assert [row["ref"] for row in objectives.risks_of(session, steward, grow)["risks"]] == [
            freezer.ref
        ]
        told = [entry["title"] for entry in history.for_record(session, RISK, breach)]
        assert f"Now threatens {grow.ref} {grow.name}" in told
        assert f"No longer threatens {grow.ref} {grow.name}" in told
        # In the connections picture, both ways; and the list hides retired ones unasked.
        around = graph.around(session, steward, OBJECTIVE, grow)
        assert [chip["ref"] for g in around["groups"] for chip in g["records"]] == [freezer.ref]
        assert {row.ref for row in records.search(session, steward, OBJECTIVE, {})[0]} == {
            grow.ref,
            trust.ref,
        }
        grow_ref, freezer_ref = grow.ref, freezer.ref
    client = as_role("steward")
    risk = client.get(f"/api/v1/risks/{freezer_ref}").json()["data"]
    changed = client.put(f"/api/v1/risks/{freezer_ref}/objectives", json={"objectives": []})
    assert changed.status_code == 200 and changed.json()["data"]["objectives"] == []
    assert risk["objectives"][0]["ref"] == grow_ref
    shown = client.get(f"/api/v1/objectives/{grow_ref}").json()["data"]
    assert shown["threatened_by"]["risks"] == []


def test_a_decision_taken_in_a_session_shows_on_the_record_it_was_about(
    db: Database, people: People, as_role: Clients
) -> None:
    manager, steward = who(db, people, "manager"), who(db, people, "steward")
    imm, hale = people.units["IMM"], people.units["HALE"]
    with db.write(manager.actor) as session, frozen_at(NOON):
        with pytest.raises(PermissionDenied):
            records.create(
                session, steward, SESSION,
                {"name": "x", "committee": "Risk committee", "held_on": "2026-03-10",
                 "org_unit_id": imm},
            )  # fmt: skip
        with pytest.raises(Invalid) as bad:
            records.create(session, manager, SESSION, {"name": "x", "org_unit_id": imm})
        assert set(bad.value.errors) == {"committee", "held_on"}
        meeting = records.create(
            session, manager, SESSION,
            {"name": "Risk committee, March 2026", "committee": "Risk committee",
             "held_on": "2026-03-10", "org_unit_id": imm},
        )  # fmt: skip
        assert (meeting.ref, meeting.status) == ("SES-0001", "planned")
        risk = raise_risk(session, steward, hale, "Freezer failure")
        first = sessions.add_item(
            session, manager, meeting, {"record": risk.ref, "note": "Accept it, or fund a fix?"}
        )
        topic = sessions.add_item(session, manager, meeting, {"title": "The year's audit plan"})
        assert first.title == f"{risk.ref} Freezer failure" and topic.position == 2
        with pytest.raises(Invalid):
            sessions.add_item(session, manager, meeting, {"record": "RSK-9999"})
        with pytest.raises(Invalid):
            sessions.add_item(session, manager, meeting, {})
        with pytest.raises(PermissionDenied):
            sessions.add_item(session, steward, meeting, {"title": "A topic"})
        sessions.move_item(session, manager, meeting, topic.id, up=True)
        shown = records.detail(session, manager, SESSION, meeting)["items_list"]
        assert [row["title"] for row in shown] == ["The year's audit plan", first.title]
        assert shown[1]["subject"]["ref"] == risk.ref
        # On Home for its keeper, as it comes up.
        assert [
            item["kind"] for item in reporting.home(session, manager)["items"]
            if item.get("ref") == meeting.ref
        ] == ["session"]  # fmt: skip
        # The decision: what was decided is needed, unless it was only noted.
        with pytest.raises(Invalid) as unsaid:
            sessions.decide(session, manager, meeting, first.id, "approved", " ")
        assert set(unsaid.value.errors) == {"decision"}
        with pytest.raises(Invalid):
            sessions.decide(session, manager, meeting, first.id, "shelved", "x")
        sessions.decide(
            session, manager, meeting, first.id, "approved",
            "Fund the second freezer this quarter; accept the risk until it is in.",
        )  # fmt: skip
        sessions.decide(session, manager, meeting, topic.id, "noted", None)
        # It shows on the risk, and the risk's owner is told.
        decisions = records.detail(session, steward, RISK, risk)["decisions"]
        assert [(row["session"]["ref"], row["outcome"]) for row in decisions] == [
            (meeting.ref, "approved")
        ]
        assert decisions[0]["decision"].startswith("Fund the second freezer")
        told = session.scalars(
            select(Notice.text).where(Notice.account_id == steward.account_id)
        ).all()
        assert any(
            text.startswith(f"{risk.ref} Risk committee, 2026-03-10: Approved") for text in told
        )
        # What was decided stays: the item cannot be taken off, nor the session cancelled.
        with pytest.raises(Conflict):
            sessions.remove_item(session, manager, meeting, first.id)
        with pytest.raises(Conflict):
            sessions.cancel(session, manager, meeting, "Not needed")
        with pytest.raises(NotFound):
            sessions.decide(session, manager, meeting, 99999, "noted", None)
        sessions.mark_held(session, manager, meeting)
        records.update(
            session, manager, SESSION, meeting,
            {"minutes": "# Minutes\n\nPresent: the committee.", "attendees": "Five members"},
            version=meeting.version,
        )  # fmt: skip
        titles = [entry["title"] for entry in history.for_record(session, SESSION, meeting)]
        assert f"Decided on {first.title}: Approved" in titles
        assert "Recorded that it was held" in titles
        assert f"Added {first.title} to the agenda" in titles
        # In the connections picture, both ways; and found by what was on its agenda.
        around = graph.around(session, manager, RISK, risk)
        assert "discussed_in" in [group["key"] for group in around["groups"]]
        found, _ = records.search(session, manager, SESSION, {"about": risk.ref})
        assert [row.ref for row in found] == [meeting.ref]
        ref, risk_ref = meeting.ref, risk.ref
    client = as_role("manager")
    added = client.post(f"/api/v1/sessions/{ref}/items", json={"title": "Any other business"})
    assert added.status_code == 201, added.text
    item = added.json()["data"]["items_list"][-1]["id"]
    decided = client.post(
        f"/api/v1/sessions/{ref}/items/{item}/decision",
        json={"outcome": "deferred", "decision": "To the June session."},
    )
    assert decided.status_code == 200, decided.text
    assert as_role("steward").get(f"/api/v1/risks/{risk_ref}").json()["data"]["decisions"]
