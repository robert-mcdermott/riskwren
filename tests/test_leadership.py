"""The leadership report: given once, and reopened exactly as it was, with a fingerprint
that shows it is the report that was given."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.access.principal import Grant
from riskwren.compliance import issues
from riskwren.core.clock import frozen_at, utc_now
from riskwren.db.engine import Database
from riskwren.db.models import Event, LeadershipReport
from riskwren.insight import leadership
from riskwren.people import accounts
from tests.people import ME, People, sign_in
from tests.test_portfolio import more_record
from tests.test_risks import judge, raise_risk, who

Clients = Callable[[str | None], TestClient]


def test_a_report_reopens_as_it_was_issued_and_its_fingerprint_verifies(
    as_role: Clients, people: People, db: Database
) -> None:
    more_record(db, people)
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        flood = raise_risk(session, steward, people.units["IMM"], "Flood in the basement store")
        judge(session, steward, flood, "inherent", 4, safety=4)
        judge(session, steward, flood, "residual", 3, safety=3)
        flood_ref = flood.ref
    manager = as_role("manager")
    issued = manager.post("/api/v1/leadership-reports", json={"summary": "A quiet quarter."})
    assert issued.status_code == 201, issued.text
    report = issued.json()["data"]
    ref = report["ref"]
    assert report["check"]["verified"] is True
    body = report["body"]
    assert body["summary"] == "A quiet quarter." and body["report"]["ref"] == ref
    assert [row["ref"] for row in body["top_risks"]]
    assert {row["key"] for row in body["figures"]} >= {"risks_open", "issues_overdue"}
    assert body["previous"] is None and body["third_parties"][0]["label"] == "Quillon Cloud"

    # The register moves on: a new risk at the top, an issue raised.
    with db.write(steward.actor) as session:
        worse = raise_risk(session, steward, people.units["IMM"], "Ransomware on the lab network")
        judge(session, steward, worse, "inherent", 5, safety=5)
        judge(session, steward, worse, "residual", 5, safety=5)
        worse_ref = worse.ref
        issues.create(session, steward, {"name": "Shared admin password", "severity": "high",
                                         "org_unit_id": people.units["IMM"]})  # fmt: skip
    with frozen_at(utc_now() + timedelta(days=40)):
        for role in ("manager", "auditor"):
            again = as_role(role).get(f"/api/v1/leadership-reports/{ref}")
            assert again.status_code == 200, again.text
            assert again.json()["data"]["body"] == body, role
            assert again.json()["data"]["check"]["verified"] is True
        manager = as_role("manager")  # signed in afresh: forty days is longer than a session
        listed = manager.get("/api/v1/leadership-reports").json()["data"]
        assert [row["ref"] for row in listed["reports"]] == [ref]
        # The next report starts the day after this one ended, and has moved on.
        upcoming = manager.get("/api/v1/leadership-reports/next").json()["data"]["body"]
        assert upcoming["from"] == (utc_now().date() - timedelta(days=39)).isoformat()
        assert upcoming["previous"]["ref"] == ref and upcoming["against"]["kind"] == "report"
        figures = {row["key"]: row for row in upcoming["figures"]}
        assert figures["risks_open"]["before"] == 3 and figures["risks_open"]["value"] == 4
        assert figures["risks_open"]["change"] == 1
        top = {row["ref"]: row for row in upcoming["top_risks"]}
        assert top[worse_ref]["movement"] == "added" and top[flood_ref]["movement"] == "same"
        second = manager.post("/api/v1/leadership-reports", json={"title": "Spring"}).json()
        assert second["data"]["body"]["previous"]["ref"] == ref
        assert second["data"]["title"] == "Spring"
    with db.read() as session:
        assert len(session.scalars(select(LeadershipReport)).all()) == 2


def test_a_changed_report_no_longer_verifies(
    as_role: Clients, people: People, db: Database
) -> None:
    more_record(db, people)
    ref = as_role("manager").post("/api/v1/leadership-reports", json={}).json()["data"]["ref"]
    with db.write(ME.actor) as session:
        report = session.scalars(select(LeadershipReport).where(LeadershipReport.ref == ref)).one()
        body = dict(report.body)
        body["summary"] = "Nothing to worry about."
        report.body = body
    with db.read() as session:
        report = leadership.find(session, who(db, people, "auditor"), ref)
        check = leadership.verify(session, report)
        assert check["verified"] is False and check["recorded"] == report.fingerprint
    # Making the fingerprint fit is itself in the history, and no longer what was issued.
    with db.write(ME.actor) as session:
        report = session.scalars(select(LeadershipReport).where(LeadershipReport.ref == ref)).one()
        report.fingerprint = leadership.fingerprint(report.body)
    with db.read() as session:
        report = leadership.find(session, who(db, people, "auditor"), ref)
        check = leadership.verify(session, report)
        assert check["computed"] == report.fingerprint != check["recorded"]
        assert check["verified"] is False


def test_who_may_read_and_issue_reports(as_role: Clients, people: People, db: Database) -> None:
    more_record(db, people)
    with db.write(ME.actor) as session:
        accounts.create(
            session, ME, email="head@northmere.example", display_name="Head Person",
            password="a long enough passphrase",
            grants=[Grant("leader", org_unit_id=people.units["NMI"], accept_limit="critical")],
        )  # fmt: skip
    ref = as_role("manager").post("/api/v1/leadership-reports", json={}).json()["data"]["ref"]
    head = sign_in(as_role(None), "head@northmere.example")
    assert head.get("/api/v1/session").json()["data"]["permissions"]["leadership"] is True
    assert head.get(f"/api/v1/leadership-reports/{ref}").status_code == 200
    assert head.post("/api/v1/leadership-reports", json={}).status_code == 403
    assert as_role("auditor").get("/api/v1/leadership-reports").status_code == 200
    assert as_role("auditor").post("/api/v1/leadership-reports", json={}).status_code == 403
    # By default, anyone whose role covers the whole organization reads them too: as a
    # security leader who assesses everywhere does.
    assessor = as_role("assessor")
    assert assessor.get("/api/v1/session").json()["data"]["permissions"]["leadership"] is True
    assert assessor.get(f"/api/v1/leadership-reports/{ref}").status_code == 200
    assert assessor.post("/api/v1/leadership-reports", json={}).status_code == 403
    for role in ("leader", "steward", "member"):
        client = as_role(role)
        assert client.get("/api/v1/leadership-reports").status_code == 403, role
        assert client.get(f"/api/v1/leadership-reports/{ref}").status_code == 403, role


def test_who_else_reads_the_reports_is_the_programs_choice(
    as_role: Clients, people: People, db: Database
) -> None:
    manager = as_role("manager")
    ref = manager.post("/api/v1/leadership-reports", json={}).json()["data"]["ref"]
    shown = manager.get("/api/v1/admin/leadership-readers").json()["data"]
    assert shown["reach"] == "organization" and shown["people"] == []
    assert set(shown["choices"]) == {"executives", "organization", "leaders"}

    def reads(role: str) -> bool:
        return as_role(role).get(f"/api/v1/leadership-reports/{ref}").status_code == 200

    def choose(reach: str, named: list[int] | None = None) -> None:
        saved = manager.put("/api/v1/admin/leadership-readers",
                            json={"reach": reach, "people": named or []})  # fmt: skip
        assert saved.status_code == 200, saved.text

    # For a large organization: its executives alone, with those who read everything.
    choose("executives")
    assert [reads(role) for role in ("auditor", "assessor", "leader")] == [True, False, False]
    # For a smaller one: every leader and every manager, of any unit.
    choose("leaders")
    assert [reads(role) for role in ("assessor", "leader", "steward", "member")] == [
        True, True, False, False,
    ]  # fmt: skip
    # Anyone may be named, whatever the reach; and it applies from their next request.
    choose("executives", [people.accounts["member"]])
    assert [reads(role) for role in ("member", "leader")] == [True, False]
    listed = manager.get("/api/v1/admin/leadership-readers").json()["data"]["people"]
    assert [person["account_id"] for person in listed] == [people.accounts["member"]]

    wrong = manager.put("/api/v1/admin/leadership-readers", json={"reach": "everyone"})
    assert wrong.status_code == 422 and "reach" in wrong.text
    nobody = manager.put("/api/v1/admin/leadership-readers",
                         json={"reach": "leaders", "people": [999999]})  # fmt: skip
    assert nobody.status_code == 422 and "people" in nobody.text
    assert as_role("assessor").put("/api/v1/admin/leadership-readers",
                                   json={"reach": "leaders"}).status_code == 403  # fmt: skip
    # Each change is in the history.
    with db.read() as session:
        ops = [event.context.get("op") for event in session.scalars(select(Event))]
    assert ops.count("leadership_readers.edit") == 3


def test_a_reader_does_not_see_the_names_of_records_they_may_not_see(
    as_role: Clients, people: People, db: Database
) -> None:
    more_record(db, people)
    with db.write(ME.actor) as session:
        sealed = raise_risk(session, ME, people.units["HALE"], "Sealed matter", restricted=True)
        judge(session, ME, sealed, "inherent", 5, safety=5)
        judge(session, ME, sealed, "residual", 5, safety=5)
        sealed_ref = sealed.ref
    issued = as_role("manager").post("/api/v1/leadership-reports", json={}).json()["data"]
    assert sealed_ref in [row["ref"] for row in issued["body"]["top_risks"]]
    assert issued["withheld"] == 0

    # The assessor reads the reports, but never sees what is restricted.
    seen = as_role("assessor").get(f"/api/v1/leadership-reports/{issued['ref']}").json()["data"]
    assert seen["withheld"] >= 1 and seen["check"]["verified"] is True
    top = seen["body"]["top_risks"]
    assert sealed_ref not in [row["ref"] for row in top]
    hidden = [row for row in top if row.get("withheld")]
    assert hidden and all(row["name"] is None and row["owners"] == [] for row in hidden)
    assert all(row["rating"] for row in hidden)  # where it stands, but not what it is
    assert all(row["name"] for row in top if not row.get("withheld"))
    assert "Sealed matter" not in str(seen)


def test_a_report_covers_days_that_have_happened(as_role: Clients, people: People) -> None:
    manager = as_role("manager")
    today = utc_now().date()
    ahead = manager.get("/api/v1/leadership-reports/next",
                        params={"to": (today + timedelta(days=1)).isoformat()})  # fmt: skip
    assert ahead.status_code == 422 and "to" in ahead.text
    backwards = manager.post("/api/v1/leadership-reports", json={
        "from": today.isoformat(), "to": (today - timedelta(days=3)).isoformat()})  # fmt: skip
    assert backwards.status_code == 422
    first = manager.get("/api/v1/leadership-reports/next").json()["data"]
    assert first["body"]["from"] == (today - timedelta(days=leadership.DEFAULT_DAYS)).isoformat()
    assert first["body"]["against"] is None and first["title"].startswith("Leadership report")
