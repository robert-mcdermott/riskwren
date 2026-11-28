"""Continuity plans (RES-03) and exercises (RES-04): a plan is a document of its own kind,
says what it restores, prints and downloads for when the systems are down, and is exercised,
with findings that become issues."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from fastapi.testclient import TestClient

from riskwren.core.clock import utc_now
from riskwren.db.engine import Database
from riskwren.inventory import records
from riskwren.inventory.registry import PROCESS
from riskwren.policy import documents
from riskwren.resilience import analyse, plans
from tests.people import People
from tests.test_documents import publish
from tests.test_risks import who

Clients = Callable[[str | None], TestClient]
PLAN = """# When the freezer room loses power

1. Call **facilities** on the emergency line.
2. Move the most valuable boxes to the spare freezer.

- Keep the door shut.
- Log each move.
"""


def _fields(response: object) -> set[str]:
    return {error["location"][0] for error in response.json()["errors"]}  # type: ignore[attr-defined]


def _plan(db: Database, people: People) -> tuple[str, str]:
    steward, leader = who(db, people, "steward"), who(db, people, "leader")
    with db.write(steward.actor) as session:
        process = records.create(session, steward, PROCESS, {
            "name": "Keeping specimens frozen", "kind": "research_support",
            "criticality": "critical", "org_unit_id": people.units["IMM"]})  # fmt: skip
        analyse(session, steward, process, {
            "impacts": [{"after": "4h", "level": 4}, {"after": "1d", "level": 5}],
            "recovery_hours": 4, "data_loss_hours": 0,
            "minimum": "One freezer at minus 80, and someone to move the boxes."})  # fmt: skip
        plan = documents.create(session, steward, {
            "name": "Freezer room continuity plan", "kind": "plan",
            "org_unit_id": people.units["IMM"], "body": PLAN})  # fmt: skip
        publish(session, steward, leader, plan)
        return plan.ref, process.ref


def test_a_plan_says_what_it_restores_and_whom_to_call(
    as_role: Clients, people: People, db: Database
) -> None:
    ref, process = _plan(db, people)
    steward = as_role("steward")
    shown = steward.get(f"/api/v1/continuity/{ref}").json()["data"]
    assert shown["version"]["number"] == 1 and shown["covers"] == []
    assert shown["can"] == {"change": True, "exercise": True}
    # A plan's own kind: an ordinary document is not one.
    with db.write(who(db, people, "steward").actor) as session:
        policy = documents.create(session, who(db, people, "steward"), {
            "name": "A policy", "kind": "policy", "org_unit_id": people.units["IMM"]})  # fmt: skip
        policy_ref = policy.ref
    assert steward.get(f"/api/v1/continuity/{policy_ref}").status_code == 404

    assert as_role("member").put(f"/api/v1/continuity/{ref}/covers",
                                 json={"processes": [process]}).status_code == 403  # fmt: skip
    set_ = steward.put(f"/api/v1/continuity/{ref}/covers", json={"processes": [process]})
    assert set_.status_code == 200, set_.text
    covered = set_.json()["data"]["covers"]
    assert [(c["ref"], c["recovery_hours"], c["data_loss_hours"]) for c in covered] == [
        (process, 4, 0)
    ]
    assert any(c["name"] == "Steward Person" for c in set_.json()["data"]["contacts"])
    # The process's business impact names the plan that restores it.
    impact = steward.get(f"/api/v1/processes/{process}/impact").json()["data"]
    assert [plan["ref"] for plan in impact["plans"]] == [ref]
    overview = as_role("member").get("/api/v1/continuity").json()["data"]
    assert [row["ref"] for row in overview["plans"]] == [ref] and overview["uncovered"] == []

    # The copy for when the systems are down: one file, the plan's words as written.
    offline = steward.get(f"/api/v1/continuity/{ref}/offline")
    assert offline.status_code == 200 and "attachment" in offline.headers["content-disposition"]
    page = offline.text
    assert "<h2>When the freezer room loses power</h2>" in page
    assert "<strong>facilities</strong>" in page and "<ol>" in page and "<ul>" in page
    assert "Keeping specimens frozen" in page and "4 hours" in page and "version 1" in page
    assert "<script" not in page


def test_an_exercise_is_recorded_and_its_findings_are_issues(
    as_role: Clients, people: People, db: Database
) -> None:
    ref, _ = _plan(db, people)
    steward = as_role("steward")
    shown = steward.get(f"/api/v1/continuity/{ref}").json()["data"]
    assert shown["last_exercised"] is None
    wrong = steward.post(f"/api/v1/continuity/{ref}/exercises", json={
        "kind": "drill", "held_on": (utc_now().date() + timedelta(days=2)).isoformat(),
        "scenario": "", "outcome": "", "result": "maybe"})  # fmt: skip
    assert wrong.status_code == 422
    assert _fields(wrong) >= {"kind", "held_on", "scenario", "outcome", "result"}
    held = (utc_now().date() - timedelta(days=3)).isoformat()
    done = as_role("assessor").post(f"/api/v1/continuity/{ref}/exercises", json={
        "kind": "tabletop", "held_on": held, "result": "partly", "achieved_hours": 6,
        "scenario": "Freezer room B loses power at 2 am on a Saturday.",
        "participants": "The repository manager, facilities, the on-call technician.",
        "outcome": "The boxes were moved in six hours: the spare freezer's key was not where "
                   "the plan said."})  # fmt: skip
    assert done.status_code == 201, done.text
    data = done.json()["data"]
    exercise = data["exercises"][0]
    assert exercise["version"] == 1 and exercise["result"] == "partly"
    assert data["last_exercised"] == held and data["exercise_overdue"] is False
    assert as_role("member").post(f"/api/v1/continuity/{ref}/exercises", json={
        "kind": "tabletop", "held_on": held, "scenario": "x", "outcome": "x",
        "result": "met"}).status_code == 403  # fmt: skip

    key = {"name": "The spare freezer's key is not where the plan says", "severity": "moderate"}
    found = steward.post(f"/api/v1/continuity/{ref}/exercises/{exercise['id']}/issues", json=key)
    assert found.status_code == 201, found.text
    finding = found.json()["data"]["exercises"][0]["findings"][0]
    issue = steward.get(f"/api/v1/issues/{finding['ref']}").json()["data"]
    assert issue["source_kind"] == "exercise" and issue["source"]["exercise"]["plan"]["ref"] == ref
    events = steward.get(f"/api/v1/documents/{ref}/history").json()["data"]
    titles = " ".join(str(event.get("title")) for event in events)
    assert "Exercised: Tabletop, partly met" in titles


def test_a_plan_with_no_exercise_waits_on_its_owner(db: Database, people: People) -> None:
    ref, _ = _plan(db, people)
    steward = who(db, people, "steward")
    with db.read() as session:
        document = plans.load(session, steward, ref)
        # A new plan is first exercised within three months.
        assert plans.waiting_on(session, steward) == []
        assert plans.view(session, steward, document)["next_exercise_on"] == (
            document.created_at.date() + timedelta(days=90)
        )
