"""As of: a record and the register as they stood at the end of a day, rebuilt from the
history alone."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.core.clock import frozen_at, utc_now
from riskwren.db.engine import Database
from riskwren.db.models import Event, Risk
from riskwren.insight import as_of
from riskwren.inventory import records
from riskwren.risk import register
from riskwren.risk.register import RISK
from tests.people import People
from tests.test_risks import judge, raise_risk, who

Clients = Callable[[str | None], TestClient]


def history(db: Database, people: People) -> dict[str, str]:
    """Three risks over sixty days: one judged and judged again, renamed, and given an owner;
    one closed; one raised late."""
    steward = who(db, people, "steward")
    imm = people.units["IMM"]
    start = utc_now() - timedelta(days=60)
    with frozen_at(start), db.write(steward.actor) as session:
        moved = raise_risk(session, steward, imm, "Freezer failure")
        judge(session, steward, moved, "inherent", 4, safety=4)
        judge(session, steward, moved, "residual", 2, safety=2)
        gone = raise_risk(session, steward, imm, "Paper records lost")
        judge(session, steward, gone, "residual", 3, safety=3)
        refs = {"moved": moved.ref, "gone": gone.ref}
    with frozen_at(start + timedelta(days=30)), db.write(steward.actor) as session:
        moved = records.load(session, steward, RISK, refs["moved"])
        judge(session, steward, moved, "residual", 5, safety=5)
        register.update(session, steward, moved, {"name": "Freezer failure in the cold room"},
                        version=moved.version)  # fmt: skip
        owner = {"account_id": people.accounts["leader"], "kind": "owner"}
        records.set_owners(session, steward, RISK, moved, [owner])
        gone = records.load(session, steward, RISK, refs["gone"])
        why = "The records were scanned and destroyed."
        closing = {"status": "closed", "closed_reason": why}
        register.update(session, steward, gone, closing, version=gone.version)
    with frozen_at(start + timedelta(days=45)), db.write(steward.actor) as session:
        refs["late"] = raise_risk(session, steward, imm, "Sequencer outage").ref
    return refs


def test_a_record_and_the_register_as_they_stood(
    as_role: Clients, people: People, db: Database
) -> None:
    refs = history(db, people)
    today = utc_now().date()
    early, later = today - timedelta(days=50), today - timedelta(days=20)
    manager = as_role("manager")

    then = manager.get(f"/api/v1/as-of/{refs['moved']}", params={"on": early.isoformat()})
    assert then.status_code == 200, then.text
    data = then.json()["data"]
    fields = {row["field"]: row for row in data["fields"]}
    assert data["existed"] is True and data["changes_since"] > 0
    assert fields["name"]["then"] == "Freezer failure"
    assert fields["name"]["now"] == "Freezer failure in the cold room"
    assert fields["name"]["changed"] and fields["residual_rating"]["changed"]
    assert fields["residual_rating"]["then"] != fields["residual_rating"]["now"]
    assert not fields["org_unit_id"]["changed"]
    assert data["owners_then"] != data["owners_now"]
    assert "Leader Person" in [owner["name"] for owner in data["owners_now"]]
    assert "Leader Person" not in [owner["name"] for owner in data["owners_then"]]

    before = manager.get(f"/api/v1/as-of/{refs['late']}", params={"on": early.isoformat()})
    assert before.json()["data"]["existed"] is False

    for on, open_refs in ((early, {refs["moved"], refs["gone"]}), (later, {refs["moved"]})):
        listed = manager.get("/api/v1/as-of", params={"type": "risk", "on": on.isoformat()})
        assert listed.status_code == 200, listed.text
        assert {row["ref"] for row in listed.json()["data"]["rows"]} == open_refs, on
    everything = manager.get("/api/v1/as-of", params={"on": later.isoformat(), "live": "false"})
    rows = {row["ref"]: row for row in everything.json()["data"]["rows"]}
    assert set(rows) == {refs["moved"], refs["gone"]}
    assert rows[refs["gone"]]["then"]["status"] == "Closed"
    assert manager.get("/api/v1/as-of", params={"on": (today + timedelta(days=1)).isoformat()}
                       ).status_code == 422  # fmt: skip
    # Only what the person may see: the member's unit is the Hale Lab, not Immunology.
    member = as_role("member")
    assert member.get(f"/api/v1/as-of/{refs['moved']}").status_code == 404
    assert (
        member.get("/api/v1/as-of", params={"on": later.isoformat()}).json()["data"]["rows"] == []
    )


def test_rebuilding_backwards_agrees_with_the_history_forwards(
    db: Database, people: People
) -> None:
    """Undoing every later change from now must give, at the end of each day something
    happened, what folding every change up to then forwards from the creation gives."""
    history(db, people)
    with db.read() as session:
        for risk in session.scalars(select(Risk)).all():
            events = session.scalars(
                select(Event)
                .where(Event.subject_type == "risk", Event.subject_id == risk.id)
                .order_by(Event.id)
            ).all()
            assert events[0].action == "created"
            for on in sorted({event.at.date() for event in events}):
                forwards: dict[str, object] = {}
                for event in events:
                    if event.at >= as_of.cutoff(on):
                        break
                    for field, (_, after) in (event.changes or {}).items():
                        forwards[field] = after
                backwards = as_of.state(session, RISK, risk, on)
                assert backwards is not None
                for field, value in forwards.items():
                    assert backwards[field] == value, (risk.ref, on, field)
            assert as_of.state(session, RISK, risk, events[0].at.date() - timedelta(days=1)) is None
