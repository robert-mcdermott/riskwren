"""Measures: each figure says what it counts, equals the length of the list it opens for the
person who sees it, and has a trend from a daily snapshot."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren import jobs
from riskwren.compliance import issues
from riskwren.core.clock import frozen_at, utc_now
from riskwren.db.engine import Database
from riskwren.db.models import MeasureSnapshot
from riskwren.insight import measures
from riskwren.inventory import records
from riskwren.inventory.registry import THIRD_PARTY
from tests.people import People
from tests.test_risks import judge, raise_risk, who

Clients = Callable[[str | None], TestClient]


def some_record(db: Database, people: People) -> None:
    """A little of everything a measure counts: risks, one above appetite; issues, one
    overdue; a third party with no tier."""
    steward = who(db, people, "steward")
    imm, hale = people.units["IMM"], people.units["HALE"]
    with db.write(steward.actor) as session:
        high = raise_risk(session, steward, imm, "Freezer failure")
        judge(session, steward, high, "inherent", 5, safety=5)
        raise_risk(session, steward, hale, "Sequencer outage")
        issues.create(session, steward, {"name": "Backups not tested", "severity": "critical",
                                          "org_unit_id": imm})  # fmt: skip
        records.create(
            session,
            steward,
            THIRD_PARTY,
            {"name": "Coldline Service", "kind": "service_provider", "org_unit_id": imm},
        )
    with frozen_at(utc_now() + timedelta(days=60)), db.write(steward.actor) as session:
        issues.create(session, steward, {"name": "Leavers' access", "severity": "moderate",
                                          "org_unit_id": hale})  # fmt: skip


def test_each_figure_is_the_length_of_the_list_it_opens(
    as_role: Clients, people: People, db: Database
) -> None:
    some_record(db, people)
    with frozen_at(utc_now() + timedelta(days=120)):
        for role in ("manager", "auditor"):
            client = as_role(role)
            shown = client.get("/api/v1/measures").json()["data"]
            assert {m["key"] for m in shown["measures"]} == set(measures.BY_KEY)
            for measure in shown["measures"]:
                assert measure["counts"] and measure["group_label"]
                if measure["path"] == "coverage":
                    listed = len(client.get("/api/v1/coverage").json()["data"]["stops"])
                else:
                    params = {
                        k: ("true" if v is True else v) for k, v in measure["filters"].items()
                    }
                    got = client.get(f"/api/v1/{measure['path']}", params={**params, "limit": 1})
                    assert got.status_code == 200, (measure["key"], got.text)
                    listed = got.json()["meta"]["total"]
                assert measure["value"] == listed, (role, measure["key"])
            figures = {m["key"]: m["value"] for m in shown["measures"]}
            assert figures["risks_open"] == 2 and figures["issues_open"] == 2
            assert figures["issues_critical"] == 1 and figures["issues_overdue"] == 1
            assert figures["third_parties_untiered"] == 1
        assert as_role("member").get("/api/v1/measures").status_code == 403


def test_a_snapshot_taken_twice_in_a_day_keeps_one(db: Database, people: People) -> None:
    some_record(db, people)
    today = utc_now().date()
    with db.write(who(db, people, "manager").actor) as session:
        assert measures.snapshot(session) == len(measures.CATALOG)
        assert measures.snapshot(session) == len(measures.CATALOG)
        rows = session.scalars(select(MeasureSnapshot).where(MeasureSnapshot.day == today)).all()
        assert len(rows) == len(measures.CATALOG)
        assert {row.measure: row.value for row in rows}["risks_open"] == 2
        measures.snapshot(session, today - timedelta(days=7))
        trend = measures.trends(session)["risks_open"]
        assert [point["day"] for point in trend] == [today - timedelta(days=7), today]
        shown = measures.overview(session, who(db, people, "manager"))
        opened = next(m for m in shown["measures"] if m["key"] == "risks_open")
        assert opened["change"] == 0 and len(opened["trend"]) == 2
    assert "measures" in jobs.JOBS
