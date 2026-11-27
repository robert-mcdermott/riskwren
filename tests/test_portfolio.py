"""The portfolio: the register and compliance by unit, category, framework, and third party,
and issues by cause, source, and age. Every figure opens exactly the records it counts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient

from riskwren.compliance import issues
from riskwren.core.clock import frozen_at, utc_now
from riskwren.db.engine import Database
from riskwren.insight import portfolio
from riskwren.inventory import records
from riskwren.inventory.registry import THIRD_PARTY
from riskwren.thirdparty import tiering
from tests.people import People
from tests.test_measures import some_record
from tests.test_risks import who

Clients = Callable[[str | None], TestClient]
TIER_1 = {"information": "restricted", "access": ["integration"], "dependency": "stops"}


def more_record(db: Database, people: People) -> None:
    """On top of some_record: a closed issue with its root cause, and a tier 1 supplier."""
    some_record(db, people)
    steward, assessor = who(db, people, "steward"), who(db, people, "assessor")
    with db.write(steward.actor) as session:
        fixed = issues.create(session, steward, {"name": "Door left open", "severity": "low",
                                                 "org_unit_id": people.units["IMM"]})  # fmt: skip
        issues.propose(session, steward, fixed, note="Closer fitted.", root_cause="procedure")
        ref = fixed.ref
        party = records.create(
            session,
            steward,
            THIRD_PARTY,
            {
                "name": "Quillon Cloud",
                "kind": "service_provider",
                "org_unit_id": people.units["IMM"],
            },
        )
        tiering.record(session, steward, party, TIER_1, None, None)
    with db.write(assessor.actor) as session:
        issue = records.load(session, assessor, issues.ISSUE, ref)
        issues.validate(session, assessor, issue, confirm=True, note="Seen fitted.")


def figures(data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for row in data.get("rows", []):
        out += [(f"{row['label']}/{key}", fig) for key, fig in row["figures"].items()]
    for name in ("root_causes", "sources", "ages"):
        out += [(f"{name}/{row['key']}", row) for row in data.get(name, [])]
    for row in data.get("months", []):
        out += [
            (f"{row['month']}/raised", row["raised"]),
            (f"{row['month']}/closed", row["closed"]),
        ]
    return out


def test_every_figure_opens_exactly_the_records_it_counts(
    as_role: Clients, people: People, db: Database
) -> None:
    more_record(db, people)
    with frozen_at(utc_now() + timedelta(days=90)):
        for role in ("manager", "member", "steward"):
            client = as_role(role)
            counted = 0
            for view in portfolio.VIEWS:
                for period in portfolio.PERIODS:
                    got = client.get("/api/v1/portfolio", params={"by": view, "period": period})
                    assert got.status_code == 200, got.text
                    for name, figure in figures(got.json()["data"]):
                        if figure["path"] == "coverage":
                            continue  # counted by the coverage tests
                        params = {k: ("true" if v is True else v)
                                  for k, v in figure["filters"].items()}  # fmt: skip
                        listed = client.get(f"/api/v1/{figure['path']}",
                                            params={**params, "limit": 1})  # fmt: skip
                        assert listed.status_code == 200, (name, listed.text)
                        assert listed.json()["meta"]["total"] == figure["count"], (role, view, name)
                        counted += figure["count"]
            if role == "manager":
                assert counted > 0


def test_the_views_say_what_happened_in_the_period(db: Database, people: People) -> None:
    more_record(db, people)
    manager = who(db, people, "manager")
    with db.read() as session:
        units = portfolio.view(session, manager, "unit", "quarter")
        imm = next(row for row in units["rows"] if row["label"] == "Immunology")
        assert imm["figures"]["closed"]["count"] == 1 and imm["figures"]["raised"]["count"] == 2
        causes = portfolio.view(session, manager, "causes", "quarter")
        assert {r["key"]: r["count"] for r in causes["root_causes"]}["procedure"] == 1
        assert len(causes["months"]) == 12
        parties = portfolio.view(session, manager, "third_party", "year")
        assert [row["label"] for row in parties["rows"]] == ["Quillon Cloud"]
        categories = portfolio.view(session, manager, "category", "half")
        assert sum(row["figures"]["risks"]["count"] for row in categories["rows"]) == 2
    start, end = portfolio.span("quarter")
    assert portfolio.parse_range(portfolio.as_range(start, end)) == (start, end)
    assert portfolio.parse_range("nonsense") is None
