"""Engagements and workpapers: stages, a team, a program of work signed off by someone other
than its preparer, and work in progress seen by the team alone until the report is issued."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.access.principal import Grant
from riskwren.core.clock import utc_now
from riskwren.db.engine import Database
from riskwren.db.models import Event
from riskwren.people import accounts
from tests.people import ME, People, sign_in
from tests.test_internal_audit import some_work
from tests.test_risks import who

Clients = Callable[[str | None], TestClient]
PASSWORD = "a long enough passphrase"


def auditor_named(db: Database, name: str) -> int:
    email = f"{name.split()[0].lower()}@northmere.example"
    with db.write(ME.actor) as session:
        made = accounts.create(session, ME, email=email, display_name=name, password=PASSWORD,
                               grants=[Grant("auditor")])  # fmt: skip
        return made.id


def as_person(as_role: Clients, name: str) -> TestClient:
    return sign_in(as_role(None), f"{name.split()[0].lower()}@northmere.example")


def planned(as_role: Clients, people: People, db: Database) -> tuple[str, dict[str, int]]:
    """An approved plan with one engagement on the busiest process."""
    refs = some_work(db, people)
    ids = {name: auditor_named(db, name) for name in ("Chief Auditor", "Outside Auditor")}
    ids["Auditor Person"] = people.accounts["auditor"]
    auditor = as_role("auditor")
    today = utc_now().date()
    plan = auditor.post("/api/v1/audit/plans", json={
        "name": "Plan", "starts_on": today.isoformat(),
        "ends_on": (today + timedelta(days=300)).isoformat()}).json()["data"]["ref"]  # fmt: skip
    shown = auditor.post(f"/api/v1/audit/plans/{plan}/engagements", json={
        "name": "Sequencing data", "kind": "process", "key": refs["busy"],
        "reason": "Ranked highest."}).json()["data"]  # fmt: skip
    as_person(as_role, "Chief Auditor").post(f"/api/v1/audit/plans/{plan}/approve", json={})
    return shown["engagements"][0]["ref"], ids


def test_an_engagement_moves_through_its_stages_with_its_work_signed_off(
    as_role: Clients, people: People, db: Database
) -> None:
    ref, ids = planned(as_role, people, db)
    chief, member = as_person(as_role, "Chief Auditor"), as_role("auditor")
    path = f"/api/v1/engagements/{ref}"
    wrong = chief.post(f"{path}/start", json={"lead": people.accounts["manager"]})
    assert wrong.status_code == 422
    started = chief.post(f"{path}/start", json={
        "lead": ids["Chief Auditor"], "members": [ids["Auditor Person"]],
        "scope_note": "Backups of sequencing runs, and who can delete them."})  # fmt: skip
    assert started.status_code == 200, started.text
    assert started.json()["data"]["status"] == "planning"
    assert {m["name"] for m in started.json()["data"]["team"]} == {
        "Chief Auditor",
        "Auditor Person",
    }

    # The work is the team's alone until the report is issued.
    for outsider in (as_role("manager"), as_person(as_role, "Outside Auditor")):
        seen = outsider.get(path).json()["data"]
        assert (
            seen["restricted"] is True and seen["workpapers"] == [] and seen["scope_note"] is None
        )

    for title in ("Backups are taken", "Deletion is limited"):
        assert member.post(f"{path}/workpapers", json={"title": title}).status_code == 201
    assert member.post(f"{path}/advance", json={}).status_code == 403  # only the lead
    assert chief.post(f"{path}/advance", json={}).json()["data"]["status"] == "fieldwork"
    papers = member.get(path).json()["data"]["workpapers"]
    first, second = papers[0]["id"], papers[1]["id"]

    bad = member.put(f"/api/v1/workpapers/{first}", json={"done": "x", "evidence": ["EV-9999"]})
    assert bad.status_code == 422
    secret = "Sampled twelve nightly backups; two were empty."
    done = member.put(f"/api/v1/workpapers/{first}", json={"done": secret,
                      "found": "Two empty backups went unnoticed."})  # fmt: skip
    assert done.status_code == 200
    assert member.post(f"/api/v1/workpapers/{first}/sign-off").status_code == 403  # its preparer
    noted = chief.post(f"/api/v1/workpapers/{first}/notes", json={"note": "Which twelve nights?"})
    assert noted.status_code == 201
    assert chief.post(f"/api/v1/workpapers/{first}/sign-off").status_code == 409  # a note is open
    note = noted.json()["data"]["workpapers"][0]["notes"][0]["id"]
    assert chief.post(f"/api/v1/review-notes/{note}/clear").status_code == 409  # not answered
    member.post(f"/api/v1/review-notes/{note}/answer", json={"answer": "The first of each month."})
    assert member.post(f"/api/v1/review-notes/{note}/clear").status_code == 403  # not theirs
    assert chief.post(f"/api/v1/review-notes/{note}/clear").status_code == 200
    assert chief.post(f"/api/v1/workpapers/{first}/sign-off").status_code == 200

    early = chief.post(f"{path}/advance", json={})
    assert early.status_code == 422  # the second is not signed off
    chief.put(f"/api/v1/workpapers/{second}", json={"done": "Read the storage permissions."})
    assert member.post(f"/api/v1/workpapers/{second}/sign-off").status_code == 200
    assert chief.post(f"{path}/advance", json={}).json()["data"]["status"] == "reporting"
    unsaid = chief.post(f"{path}/advance", json={"opinion": "effective"})
    assert unsaid.status_code == 422 and "summary" in unsaid.text
    report = {"summary": "Backups are taken but not checked.", "opinion": "needs_improvement"}
    reported = chief.post(f"{path}/advance", json=report)
    data = reported.json()["data"]
    assert data["status"] == "reported" and data["report"]["opinion_label"] == "Needs improvement"

    # Reported, the work is open to those who read the plan, and the universe knows.
    after = as_role("manager").get(path).json()["data"]
    assert after["restricted"] is False and len(after["workpapers"]) == 2
    universe = as_role("auditor").get("/api/v1/audit/universe").json()["data"]
    busy = next(row for row in universe["entities"] if row["ref"] == data["entity"]["ref"])
    assert busy["last_audited_on"] == utc_now().date().isoformat() and busy["planned"] == []
    # The history says the workpaper changed, and keeps its words out.
    with db.read() as session:
        events = session.scalars(select(Event).where(Event.subject_type == "workpaper")).all()
        assert events and all(secret not in str(event.changes) for event in events)


def test_only_auditors_start_and_work_and_only_the_team(
    as_role: Clients, people: People, db: Database
) -> None:
    ref, ids = planned(as_role, people, db)
    path = f"/api/v1/engagements/{ref}"
    assert as_role("manager").post(f"{path}/start", json={"lead": 1}).status_code == 403
    chief = as_person(as_role, "Chief Auditor")
    chief.post(f"{path}/start", json={"lead": ids["Chief Auditor"]})
    outsider = as_person(as_role, "Outside Auditor")
    assert outsider.post(f"{path}/workpapers", json={"title": "x"}).status_code == 403
    assert who(db, people, "auditor").has("auditor")
