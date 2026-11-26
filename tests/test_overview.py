"""The compliance dashboard, the picture of how a record is connected, and every change in
one place: each figure opens the list that makes it, the picture's list is complete, and the
whole history is for those who may read everything."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from riskwren.compliance import assessments, exceptions, packs, scopes
from riskwren.compliance.issues import ISSUE
from riskwren.compliance.scopes import SCOPE
from riskwren.controls import service as controls
from riskwren.controls.service import CONTROL
from riskwren.core.clock import frozen_at
from riskwren.db.engine import Database
from riskwren.db.models import TestResult
from riskwren.inventory import history, links, records
from riskwren.inventory.registry import PROCESS, SYSTEM
from riskwren.reporting import compliance, graph
from riskwren.reporting import service as reporting
from riskwren.risk import register
from tests.conftest import TESTER
from tests.people import People
from tests.test_assessments import start, the_test, world
from tests.test_evidence import add_evidence
from tests.test_exchange import add_system
from tests.test_issues import raise_issue
from tests.test_risks import raise_risk, who

Clients = Callable[[str | None], TestClient]
NOW = datetime(2026, 3, 2, 12, tzinfo=UTC)


@pytest.fixture
def loaded(db: Database, people: People) -> None:
    with db.write(TESTER) as session:
        packs.install(session)


def program(db: Database, people: People) -> dict[str, str]:
    """A provider and an enclave, one control tested and found wanting, issues of several
    ages, evidence of every freshness, and exceptions at three stages."""
    manager, assessor, steward, leader = (
        who(db, people, r) for r in ("manager", "assessor", "steward", "leader")
    )
    hale = people.units["HALE"]
    with frozen_at(NOW - timedelta(days=200)), db.write(manager.actor) as session:
        central, enclave, backups, factor = world(session, people, manager)
        raise_issue(session, manager, hale, "An old one", severity="critical")
        add_evidence(
            session, manager, hale, "Old log", collected_on="2025-08-01", valid_until="2026-01-31"
        )
    with frozen_at(NOW - timedelta(days=40)), db.write(manager.actor) as session:
        raise_issue(session, manager, hale, "A newer one", severity="moderate", source_kind="audit")
        add_evidence(
            session,
            manager,
            hale,
            "Ending log",
            collected_on="2026-01-20",
            valid_until="2026-03-20",
        )
    with frozen_at(NOW):
        with db.write(manager.actor) as session:
            central = records.load(session, manager, SCOPE, central.ref)
            backups = records.load(session, manager, CONTROL, backups.ref)
            factor = records.load(session, manager, CONTROL, factor.ref)
            made = start(session, manager, central)
            bad = assessments.record(
                session,
                manager,
                the_test(session, made, backups),
                design="effective",
                operation="ineffective",
                note="No restore in two years.",
            )
            good = assessments.record(
                session,
                manager,
                the_test(session, made, factor),
                design="effective",
                operation="effective",
                note="All ten as described.",
            )
            add_evidence(session, manager, hale, "Fresh log")
        with db.write(assessor.actor) as session:
            assessments.review(
                session, assessor, session.get(TestResult, bad.id), confirm=True, note=None
            )
        with db.write(steward.actor) as session:
            ask = {"scope": enclave.ref, "justification": "Being replaced."}
            exceptions.request(
                session, steward, {**ask, "control": backups.ref, "expires_on": "2026-03-20"}
            )
            exceptions.request(
                session,
                steward,
                {
                    **ask,
                    "requirement": {"framework": "nist-csf", "code": "GV.OC-01"},
                    "expires_on": "2026-09-30",
                },
            )
        with db.write(leader.actor) as session:
            exceptions.decide(
                session,
                leader,
                records.load(session, leader, exceptions.EXCEPTION, "EXC-0001"),
                approve=True,
                note=None,
            )
    return {
        "central": central.ref,
        "enclave": enclave.ref,
        "backups": backups.ref,
        "factor": factor.ref,
        "good": str(good.id),
    }


# --- The compliance dashboard ---------------------------------------------------------------


def test_each_figure_on_the_compliance_dashboard_opens_the_list_that_makes_it(
    db: Database, loaded: None, people: People
) -> None:
    made = program(db, people)
    manager, member = who(db, people, "manager"), who(db, people, "member")
    with frozen_at(NOW), db.read() as session:
        board = compliance.board(session, manager)
        by_scope = {row["scope"]["name"]: row for row in board["readiness"]}
        # Each scope against its framework: the same counts as its statement of applicability.
        for ref in (made["central"], made["enclave"]):
            scope = records.load(session, manager, SCOPE, ref)
            row = by_scope[scope.name]
            assert row["counts"] == scopes.statement(session, manager, scope, "nist-csf")["counts"]
            assert row["framework"]["key"] == "nist-csf" and row["applicable"] == 106
        central, enclave = by_scope["Central computing"], by_scope["The enclave"]
        assert (central["counts"]["failing"], central["counts"]["in_place"], central["ready"]) == (
            2,
            1,
            1,
        )
        # The enclave inherits the failing control, and an exception covers it there.
        assert (enclave["counts"]["failing"], enclave["counts"]["excepted"]) == (0, 2)
        assert central["issues"] == enclave["issues"] == 1  # the issue the failed test opened
        assert board["requirements"]["failing"] == 2 and board["requirements"]["excepted"] == 2
        t = board["totals"]
        assert {key: figure["count"] for key, figure in t.items()} == {
            "issues_open": 3, "issues_overdue": 1, "closures_waiting": 0, "evidence_stale": 1,
            "exceptions_expiring": 1, "exceptions_requested": 1, "controls_failing": 1,
            "results_waiting": 1,
        }  # fmt: skip
        # Every figure is the count of the list its filters produce.
        for figure, record_type in (
            (t["issues_open"], ISSUE), (t["issues_overdue"], ISSUE),
            (t["evidence_stale"], compliance.EVIDENCE), (t["exceptions_expiring"], compliance.EXCEPTION),
            (t["exceptions_requested"], compliance.EXCEPTION), (t["controls_failing"], CONTROL),
        ):  # fmt: skip
            assert (
                records.search(session, manager, record_type, figure["filters"])[1]
                == figure["count"]
            )
        # Issues by severity and by how long they have been open.
        aging = {row["key"]: row for row in board["issues"]["by_severity"]}
        ages = lambda key: [age["count"] for age in aging[key]["ages"]]  # noqa: E731
        assert board["ages"] == ["0-30", "31-90", "91-180", "181+"]
        assert (ages("critical"), aging["critical"]["overdue"]["count"]) == ([0, 0, 0, 1], 1)
        assert ages("moderate") == [0, 1, 0, 0] and ages("high") == [1, 0, 0, 0]
        old = aging["critical"]["ages"][3]
        assert [i.name for i in records.search(session, manager, ISSUE, old["filters"])[0]] == [
            "An old one"
        ]
        assert {s["key"]: s["count"] for s in board["issues"]["by_source"]} == {
            "test": 1,
            "audit": 1,
            "observation": 1,
        }
        assert [i["name"] for i in board["worst_issues"]] == ["An old one"]
        assert {e["key"]: e["count"] for e in board["evidence"]} == {
            "current": 2,
            "expiring": 1,
            "stale": 1,
        }
        assert {e["key"]: e["count"] for e in board["exceptions"]} == {
            "requested": 1,
            "in_force": 1,
            "expiring": 1,
            "expired": 0,
        }
        tested = {c["key"]: c["count"] for c in board["controls"]["by_test"]}
        assert (
            tested == {"effective": 0, "failing": 1, "none": 1}
            and board["controls"]["total"]["count"] == 2
        )
        assert [
            c.ref for c in records.search(session, manager, CONTROL, {"tested": "failing"})[0]
        ] == [made["backups"]]
        assert [
            (a["ref"], a["tests"], a["counted"], a["awaiting"]) for a in board["assessments"]
        ] == [("ASM-0001", 2, 1, 1)]
        # For one unit and those beneath it; and for someone who sees less, less.
        lab = compliance.board(session, manager, unit=people.units["HALE"])
        assert [row["scope"]["name"] for row in lab["readiness"]] == ["The enclave"]
        assert (
            lab["totals"]["issues_open"]["count"] == 2
            and lab["totals"]["controls_failing"]["count"] == 0
        )
        assert lab["totals"]["issues_open"]["filters"] == {
            "unit": people.units["HALE"],
            "status": "live",
        }
        less = compliance.board(session, member)
        assert less["totals"]["issues_open"]["count"] == 0 and less["worst_issues"] == []
    with frozen_at(NOW + timedelta(days=30)), db.read() as session:
        # A month on, with nothing touched: the exception has ended and the evidence is stale.
        later = compliance.board(session, manager)
        assert {e["key"]: e["count"] for e in later["exceptions"]}["expired"] == 1
        assert {e["key"]: e["count"] for e in later["evidence"]} == {
            "current": 1,
            "expiring": 0,
            "stale": 2,
        }
        assert {row["scope"]["name"]: row["counts"]["failing"] for row in later["readiness"]}[
            "The enclave"
        ] == 2


# --- The graph --------------------------------------------------------------------------------


def test_the_picture_of_a_record_lists_everything_joined_to_it(
    db: Database, loaded: None, people: People
) -> None:
    made = program(db, people)
    manager, member = who(db, people, "manager"), who(db, people, "member")
    hale = people.units["HALE"]
    with frozen_at(NOW), db.write(manager.actor) as session:
        backups = records.load(session, manager, CONTROL, made["backups"])
        enclave = records.load(session, manager, SCOPE, made["enclave"])
        system = add_system(session, manager, hale, "Tape library")
        sealed = add_system(session, manager, hale, "Sealed", restricted=True)
        process = records.create(
            session,
            manager,
            PROCESS,
            {"name": "Specimen storage", "kind": "research_support", "org_unit_id": hale},
        )
        for each in (system, sealed):
            links.add(session, manager, PROCESS, process, "relies_on", SYSTEM, each)
        risk = raise_risk(session, manager, hale, "Loss of the archive")
        register.set_subjects(session, manager, risk, [system.ref])
        controls.link(session, manager, risk, backups, reduces="impact", reliance="primary")
        scopes.set_members(session, manager, enclave, [system.ref], [hale])
        item = add_evidence(session, manager, hale, "Restore log")
        from riskwren.compliance import evidence

        evidence.set_subjects(session, manager, item, [backups.ref, enclave.ref])

        def groups(record_type, record, by=manager):  # type: ignore[no-untyped-def]
            found = graph.around(session, by, record_type, record)
            return {
                g["label"]: sorted(r["name"] for r in g["records"]) for g in found["groups"]
            }, found

        seen, found = groups(CONTROL, backups)
        assert seen == {
            "Reduces": ["Loss of the archive"],
            "Used in": ["Central computing", "The enclave"],
            "Tested in": ["Annual assessment"],
            "Exceptions": ["Backups in The enclave"],
            "Evidence": ["Restore log"],
            "Issues": ["Backups: found ineffective in ASM-0001"],
        }
        assert (found["center"]["ref"], found["count"], found["hidden"]) == (backups.ref, 7, 0)
        seen, _ = groups(SYSTEM, system)
        assert seen == {
            "Supports": ["Specimen storage"],
            "Risks to it": ["Loss of the archive"],
            "Within the scope": ["The enclave"],
        }
        seen, _ = groups(SCOPE, enclave)
        assert seen["Covers"] == ["Tape library"] and seen["Uses"] == ["Backups", "Second factor"]
        assert seen["Evidence"] == ["Restore log"] and len(seen["Exceptions"]) == 2
        assert seen["Issues"] == ["Backups: found ineffective in ASM-0001"]
        seen, _ = groups(reporting.RISK, risk)
        assert seen == {"Bears on": ["Tape library"], "Reduced by": ["Backups"]}
        issue = records.load(session, manager, ISSUE, "ISS-0003")
        assert groups(ISSUE, issue)[0] == {"About": ["Backups", "Central computing", "The enclave"]}
        # What a person may not see is counted, and not shown.
        seen, found = groups(PROCESS, process, by=member)
        assert seen == {"Relies on": ["Tape library"]} and found["hidden"] == 1
        seen, found = groups(PROCESS, process)
        assert seen == {"Relies on": ["Sealed", "Tape library"]} and found["hidden"] == 0


def test_the_api_draws_from_the_same_answers(
    as_role: Clients, db: Database, loaded: None, people: People
) -> None:
    made = program(db, people)
    chief, member, auditor = as_role("manager"), as_role("member"), as_role("auditor")
    board = chief.get("/api/v1/compliance").json()["data"]
    assert len(board["readiness"]) == 2 and board["totals"]["controls_failing"]["count"] == 1
    figure = board["totals"]["controls_failing"]
    assert [
        c["ref"] for c in chief.get("/api/v1/controls", params=figure["filters"]).json()["data"]
    ] == [made["backups"]]
    old = chief.get("/api/v1/issues", params={"status": "live", "age": "181+"}).json()["data"]
    # (These are asked on the real day, months after the program above was dated.)
    assert (
        len(old) == 3
        and not chief.get("/api/v1/issues", params={"status": "live", "age": "0-30"}).json()["data"]
    )
    assert [
        e["ref"]
        for e in chief.get("/api/v1/exceptions", params={"state": "expiring"}).json()["data"]
    ] in ([], ["EXC-0001"])
    around = chief.get(f"/api/v1/graph/{made['backups']}").json()["data"]
    assert around["center"]["ref"] == made["backups"] and {
        g["label"] for g in around["groups"]
    } >= {"Used in", "Issues"}
    assert member.get(f"/api/v1/graph/{made['backups']}").status_code == 404  # not theirs to see
    assert chief.get("/api/v1/graph/SYS-9999").status_code == 404

    # Every change in one place, for those who read everything.
    assert member.get("/api/v1/history").status_code == 403
    assert as_role("steward").get("/api/v1/history").status_code == 403
    page = auditor.get("/api/v1/history").json()["data"]
    assert len(page["entries"]) == 100 and page["next"] is not None
    newest = page["entries"][0]
    assert newest["id"] > page["entries"][-1]["id"] and {
        "at",
        "actor",
        "title",
        "record",
        "kind",
    } <= set(newest)
    older = auditor.get("/api/v1/history", params={"before": page["next"]}).json()["data"]
    assert older["entries"][0]["id"] < page["entries"][-1]["id"]
    # By record: what happened to the control, and to the things that hang from it.
    about = auditor.get("/api/v1/history", params={"about": made["backups"]}).json()["data"][
        "entries"
    ]
    titles = [entry["title"] for entry in about]
    assert "Added this control" in titles and any(title.startswith("Rated: ") for title in titles)
    assert all(entry["record"]["ref"] == made["backups"] for entry in about)
    # By person, by kind, and by date.
    leader = people.accounts["leader"]
    theirs = auditor.get("/api/v1/history", params={"actor": leader}).json()["data"]["entries"]
    assert theirs and all(entry["actor"] == "Leader Person" for entry in theirs)
    assert [entry["record"]["ref"] for entry in theirs] == ["EXC-0001"]
    raised = auditor.get("/api/v1/history", params={"kind": "issue"}).json()["data"]["entries"]
    assert {entry["kind"] for entry in raised} == {"issue"} and len(
        {e["record"]["ref"] for e in raised}
    ) == 3
    assert (
        auditor.get("/api/v1/history", params={"until": "2000-01-01"}).json()["data"]["entries"]
        == []
    )
    assert auditor.get("/api/v1/history", params={"since": "not a date"}).status_code == 422
    # What is not a change to a record is told too: here, an export.
    chief.get("/api/v1/exports/issues")
    other = auditor.get("/api/v1/history", params={"kind": "other"}).json()["data"]["entries"]
    assert other[0]["title"] == "Exported issues as CSV: 3 rows" and other[0]["record"] is None
    assert other[0]["actor"] == "Manager Person"


def test_the_whole_history_tells_what_a_records_own_history_tells(
    db: Database, loaded: None, people: People
) -> None:
    program(db, people)
    manager = who(db, people, "manager")
    with db.read() as session:
        issue = records.load(session, manager, ISSUE, "ISS-0003")
        own = history.for_record(session, ISSUE, issue)
        everywhere = history.everywhere(session, about=(ISSUE, issue))["entries"]
        assert [(e["id"], e["title"]) for e in everywhere] == [(e["id"], e["title"]) for e in own]
