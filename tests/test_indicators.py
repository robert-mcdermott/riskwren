"""Indicators: thresholds, readings over time, a trend, and what a breach sets in motion."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren import reminders
from riskwren.core.clock import frozen_at
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import Indicator, IndicatorReading, Notice
from riskwren.inventory import history, records
from riskwren.reporting import service as reporting
from riskwren.risk import indicators
from riskwren.risk.indicators import INDICATOR
from riskwren.risk.register import RISK
from tests.people import People
from tests.test_risks import judge, raise_risk, who

Clients = Callable[[str | None], TestClient]
NOON = datetime(2026, 3, 2, 12, tzinfo=UTC)


def at(day: str) -> datetime:
    return datetime.fromisoformat(day).replace(hour=12, tzinfo=UTC)


def add(session, by, unit: int, **more):  # type: ignore[no-untyped-def]
    values = {
        "name": "Days to remove a leaver's access", "org_unit_id": unit, "measure": "days",
        "direction": "up", "warn_at": 2, "breach_at": 5, "frequency": "monthly", **more,
    }  # fmt: skip
    return records.create(session, by, INDICATOR, values)


def told(db: Database, account_id: int) -> list[str]:
    with db.read() as session:
        rows = session.scalars(
            select(Notice).where(Notice.account_id == account_id).order_by(Notice.id)
        )
        return [row.text for row in rows]


def test_an_indicator_has_levels_that_make_sense(db: Database, people: People) -> None:
    steward, member = who(db, people, "steward"), who(db, people, "member")
    hale = people.units["HALE"]
    with db.write(steward.actor) as session, frozen_at(NOON):
        for values, fields in [
            ({"breach_at": None}, {"breach_at"}),
            ({"breach_at": "many"}, {"breach_at"}),
            ({"warn_at": 5, "breach_at": 5}, {"warn_at"}),  # the warning comes first
            ({"direction": "down", "warn_at": 80, "breach_at": 90}, {"warn_at"}),
            ({"direction": "sideways", "frequency": "hourly"}, {"direction", "frequency"}),
        ]:
            with pytest.raises(Invalid) as caught:
                add(session, steward, hale, **values)
            assert set(caught.value.errors) == fields, values
        with pytest.raises(PermissionDenied):
            add(session, member, hale)  # added by a steward or a manager, like any record
        made = add(session, steward, hale)
        assert (made.ref, made.state, made.last_value) == ("IND-0001", "no_reading", None)
        assert indicators.next_due(made) == date(2026, 4, 2)  # a period after it was set up
        low = add(session, steward, hale, name="Staff trained", measure="%", direction="down",
                  warn_at=95, breach_at=90)  # fmt: skip
        # Whichever way is worse, the levels are read that way.
        assert [indicators.state_for(made, v) for v in (0, 1.9, 2, 4.9, 5, 9)] == [
            "ok", "ok", "warn", "warn", "breach", "breach",
        ]  # fmt: skip
        assert [indicators.state_for(low, v) for v in (100, 95.1, 95, 90.1, 90, 0)] == [
            "ok", "ok", "warn", "warn", "breach", "breach",
        ]  # fmt: skip
        assert indicators.state_for(made, None) == "no_reading"


def test_a_breach_tells_the_owner_and_shows_on_each_risk_it_warns_of(
    db: Database, people: People
) -> None:
    """The acceptance test."""
    steward, manager, member = (who(db, people, r) for r in ("steward", "manager", "member"))
    hale = people.units["HALE"]
    owner = [{"account_id": people.accounts["member"], "kind": "owner"}]
    with db.write(steward.actor) as session, frozen_at(NOON):
        first = raise_risk(session, steward, hale, "Access not removed")
        judge(session, steward, first, "inherent", 4, mission=4)
        judge(session, steward, first, "residual", 2, mission=3)
        second = raise_risk(session, steward, hale, "Not yet assessed")
        made = add(session, steward, hale)
        records.set_owners(session, steward, INDICATOR, made, owner)
        indicators.set_risks(session, steward, made, [first.ref, second.ref])
        with pytest.raises(Exception, match="no risk"):
            indicators.set_risks(session, steward, made, ["RSK-9999"])
    with db.write(member.actor) as session:
        made = records.load(session, member, INDICATOR, "IND-0001")
        for day, value in (("2026-03-31", 1), ("2026-04-30", 1.5), ("2026-05-29", 3)):
            with frozen_at(at(day)):
                indicators.record_reading(session, member, made, value=value)
        assert (made.state, made.last_value, made.last_read_on) == ("warn", 3, date(2026, 5, 29))
        with frozen_at(at("2026-06-30")):
            for bad, field in (("lots", "value"), (None, "value")):
                with pytest.raises(Invalid) as caught:
                    indicators.record_reading(session, member, made, value=bad)
                assert field in caught.value.errors
            with pytest.raises(Invalid):
                indicators.record_reading(session, member, made, value=1, read_on="2026-07-15")
            with pytest.raises(PermissionDenied):  # readings are for those who keep it
                indicators.record_reading(session, who(db, people, "auditor"), made, value=1)
    assert told(db, people.accounts["steward"]) == []  # a warning is not yet a breach

    with db.write(member.actor) as session, frozen_at(at("2026-06-30")):
        made = records.load(session, member, INDICATOR, "IND-0001")
        indicators.record_reading(session, member, made, value=7, note="Three agency contracts.")
        assert made.state == "breach"
        seen = records.detail(session, member, INDICATOR, made)
        assert seen["trend"] == "worse" and [r["value"] for r in seen["readings"]] == [1, 1.5, 3, 7]
        assert [r["state"] for r in seen["readings"]] == ["ok", "ok", "warn", "breach"]
        assert [r["ref"] for r in seen["risks"]] == ["RSK-0001", "RSK-0002"]
    # Those who answer for the risks are told; whoever recorded it is not told what they did.
    said = "IND-0001 Days to remove a leaver's access is at 7 days, past its limit of 5"
    assert told(db, people.accounts["steward"]) == [said]
    assert said not in told(db, people.accounts["member"])
    with db.write(steward.actor) as session, frozen_at(at("2026-06-30")):
        first = records.load(session, steward, RISK, "RSK-0001")
        # It shows on the risk: its rating is in doubt, and says why.
        assert first.residual_in_doubt and said in (first.residual_doubt_reason or "")
        shown = indicators.of_risk(session, steward, first)
        assert [(i["ref"], i["state"], i["trend"], i["values"]) for i in shown] == [
            ("IND-0001", "breach", "worse", [1, 1.5, 3, 7])
        ]
        other = records.load(session, steward, RISK, "RSK-0002")
        assert not other.residual_in_doubt  # nothing has been judged there yet to put in doubt
        board = reporting.dashboard(session, manager)["indicators"]
        assert {row["key"]: row["count"] for row in board}["breach"] == 1
    with db.write(member.actor) as session, frozen_at(at("2026-07-31")):
        made = records.load(session, member, INDICATOR, "IND-0001")
        indicators.record_reading(session, member, made, value=8)
    assert told(db, people.accounts["steward"]) == [said]  # still past it: said once
    with db.write(member.actor) as session, frozen_at(at("2026-08-31")):
        made = records.load(session, member, INDICATOR, "IND-0001")
        indicators.record_reading(session, member, made, value=1)
        assert made.state == "ok"
        indicators.record_reading(session, member, made, value=6, read_on="2026-08-31")
        assert made.state == "breach"  # the same day again corrects it, and it has crossed again
        count = session.scalars(
            select(IndicatorReading).where(IndicatorReading.indicator_id == made.id)
        ).all()
        assert len(count) == 6
        said_in_history = str(history.for_record(session, INDICATOR, made))
        assert "Recorded a reading of 7" in said_in_history
        assert "Corrected a reading to 6" in said_in_history
    assert len(told(db, people.accounts["steward"])) == 2


def test_a_reading_that_is_due_is_asked_for(db: Database, people: People) -> None:
    steward, member = who(db, people, "steward"), who(db, people, "member")
    owner = [{"account_id": people.accounts["member"], "kind": "owner"}]
    with db.write(steward.actor) as session, frozen_at(NOON):
        made = add(session, steward, people.units["HALE"], frequency="weekly")
        records.set_owners(session, steward, INDICATOR, made, owner)
    with frozen_at(at("2026-03-05")), db.read() as session:
        assert indicators.due(session, member) == []
        assert all(i["kind"] != "reading" for i in reporting.home(session, member)["items"])
    with frozen_at(at("2026-03-09")):
        with db.read() as session:
            mine = [i for i in reporting.home(session, member)["items"] if i["kind"] == "reading"]
            assert [(i["title"], i["due_on"]) for i in mine] == [
                ("Record a reading of Days to remove a leaver's access", date(2026, 3, 9))
            ]
        with db.bookkeeping() as session:
            assert reminders.send(session)["reminders"] == 1
    assert told(db, people.accounts["member"])[-1].startswith("Due today: a reading of IND-0001")
    with db.write(member.actor) as session, frozen_at(at("2026-03-09")):
        made = records.load(session, member, INDICATOR, "IND-0001")
        indicators.record_reading(session, member, made, value=1)
        assert indicators.due(session, member) == []
    with db.write(steward.actor) as session, frozen_at(at("2026-03-10")):
        made = records.load(session, steward, INDICATOR, "IND-0001")
        records.update(
            session, steward, INDICATOR, made, {"status": "retired"}, version=made.version
        )
        assert indicators.next_due(made) is None
        with pytest.raises(Invalid):
            indicators.record_reading(session, steward, made, value=1)


def test_new_levels_are_applied_to_the_reading_on_record(db: Database, people: People) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session, frozen_at(NOON):
        made = add(session, steward, people.units["HALE"])
        indicators.record_reading(session, steward, made, value=3)
        assert made.state == "warn"
        records.update(session, steward, INDICATOR, made, {"breach_at": 3}, version=made.version)
        assert session.get(Indicator, made.id).state == "breach"


def test_indicators_through_the_api(as_role: Clients, people: People) -> None:
    steward, member = as_role("steward"), as_role("member")
    risk = steward.post(
        "/api/v1/risks",
        json={"name": "Access not removed", "category": "data_quality",
              "org_unit_id": people.units["HALE"]},
    ).json()["data"]  # fmt: skip
    made = steward.post(
        "/api/v1/indicators",
        json={"name": "Days to remove a leaver's access", "org_unit_id": people.units["HALE"],
              "measure": "days", "warn_at": 2, "breach_at": 5},
    )  # fmt: skip
    assert made.status_code == 201 and made.json()["data"]["ref"] == "IND-0001"
    refused = member.post(
        "/api/v1/indicators",
        json={"name": "x", "breach_at": 1, "org_unit_id": people.units["HALE"]},
    )
    assert refused.status_code == 403
    assert (
        steward.put("/api/v1/indicators/IND-0001/risks", json={"risks": [risk["ref"]]}).status_code
        == 200
    )
    assert member.post("/api/v1/indicators/IND-0001/readings", json={"value": 1}).status_code == 403
    done = steward.post("/api/v1/indicators/IND-0001/readings", json={"value": 6, "note": "June"})
    assert done.json()["data"]["state"] == "breach" and done.json()["data"]["trend"] == "steady"
    listed = member.get("/api/v1/indicators", params={"state": "breach"}).json()
    assert [row["ref"] for row in listed["data"]] == ["IND-0001"] and listed["data"][0][
        "risks"
    ] == 1
    assert member.get("/api/v1/indicators", params={"state": "ok"}).json()["data"] == []
    on_risk = member.get(f"/api/v1/risks/{risk['ref']}/indicators").json()["data"]
    assert on_risk[0]["ref"] == "IND-0001" and on_risk[0]["last_value"] == 6
    assert member.get("/api/v1/indicators", params={"risk": risk["ref"]}).json()["data"]
    exported = steward.get("/api/v1/exports/indicators", params={"format": "csv"})
    assert exported.status_code == 200 and "IND-0001" in exported.text and "breach" in exported.text
    assert "reading" in str(steward.get("/api/v1/indicators/IND-0001/history").json()).lower()
