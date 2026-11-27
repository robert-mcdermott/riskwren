"""Internal audit's universe and plan: everything worth auditing, ranked from the register with
its working shown, and a period's plan approved by a named person and tracked against."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from fastapi.testclient import TestClient

from riskwren.compliance import issues
from riskwren.core.clock import utc_now
from riskwren.db.engine import Database
from riskwren.inventory import records
from riskwren.inventory.registry import PROCESS
from riskwren.risk import register
from tests.people import People
from tests.test_risks import judge, raise_risk, who
from tests.test_third_parties import thing

Clients = Callable[[str | None], TestClient]


def some_work(db: Database, people: People) -> dict[str, str]:
    """A critical process with a risk rated high and above appetite, and an open issue."""
    steward = who(db, people, "steward")
    imm = people.units["IMM"]
    with db.write(steward.actor) as session:
        sequencing = thing(session, steward, PROCESS, name="Sequencing service", unit=imm,
                           criticality="critical")  # fmt: skip
        quiet = thing(session, steward, PROCESS, name="Seminar booking", unit=imm,
                      criticality="low")  # fmt: skip
        risk = raise_risk(session, steward, imm, "Sequencer data lost")
        judge(session, steward, risk, "inherent", 5, safety=5)
        judge(session, steward, risk, "residual", 4, safety=4)
        register.set_subjects(session, steward, risk, [sequencing.ref])
        issues.create(session, steward, {"name": "Runs not backed up", "severity": "high",
                                         "org_unit_id": imm, "subjects": [risk.ref]})  # fmt: skip
        return {"busy": sequencing.ref, "quiet": quiet.ref, "risk": risk.ref}


def entity(data: dict, ref: str) -> dict:  # type: ignore[type-arg]
    return next(row for row in data["entities"] if row["ref"] == ref)


def test_the_universe_ranks_from_the_register_and_says_how(
    as_role: Clients, people: People, db: Database
) -> None:
    refs = some_work(db, people)
    auditor = as_role("auditor")
    shown = auditor.get("/api/v1/audit/universe").json()["data"]
    busy, quiet = entity(shown, refs["busy"]), entity(shown, refs["quiet"])
    assert busy["score"] > quiet["score"] and busy["score"] == sum(
        p["points"] for p in busy["parts"]
    )
    labels = " ".join(part["label"] for part in busy["parts"])
    assert "worst open risk" in labels and "above appetite" in labels and "open issue" in labels
    assert "Never audited" in labels and busy["open_risks"] == 1 and busy["open_issues"] == 1
    assert shown["entities"].index(busy) < shown["entities"].index(quiet)
    assert {row["kind"] for row in shown["entities"]} >= {"unit", "process"}

    # The register moves, and so does the ranking.
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        risk = records.load(session, steward, register.RISK, refs["risk"])
        judge(session, steward, risk, "residual", 1, safety=1)
    lower = entity(auditor.get("/api/v1/audit/universe").json()["data"], refs["busy"])
    assert lower["score"] < busy["score"]

    # Audit moves a thing with a reason, records an audit from before, or leaves one out.
    path = f"/api/v1/audit/universe/process/{refs['quiet']}"
    assert auditor.put(path, json={"adjustment": 20}).status_code == 422
    moved = auditor.put(path, json={"adjustment": 20, "adjustment_reason": "Fraud tip-off.",
                                    "last_audited_on": (utc_now().date() - timedelta(days=800)
                                                        ).isoformat()}).json()["data"]  # fmt: skip
    assert {"label": "Moved by audit: Fraud tip-off.", "points": 20} in moved["parts"]
    assert any(p["label"] == "Last audited more than two years ago" for p in moved["parts"])
    out = auditor.put(path, json={"left_out": True, "left_out_reason": "Run by the city."})
    assert out.status_code == 200
    again = auditor.get("/api/v1/audit/universe").json()["data"]
    assert refs["quiet"] not in {row["ref"] for row in again["entities"]}
    assert again["left_out"] == 1
    history = as_role("manager").get("/api/v1/history", params={"kind": "audit_entity"})
    assert history.status_code == 200 and history.json()["data"]["entries"]

    # Only auditors change it; those who read everything read it; others do not.
    assert as_role("manager").put(path, json={"adjustment": 0}).status_code == 403
    assert as_role("manager").get("/api/v1/audit/universe").status_code == 200
    for role in ("steward", "leader", "member", "assessor"):
        assert as_role(role).get("/api/v1/audit/universe").status_code == 403, role


def test_a_plan_is_approved_by_a_named_person_and_tracked_against(
    as_role: Clients, people: People, db: Database
) -> None:
    refs = some_work(db, people)
    auditor = as_role("auditor")
    today = utc_now().date()
    made = auditor.post("/api/v1/audit/plans", json={
        "name": "Internal audit plan", "starts_on": today.isoformat(),
        "ends_on": (today + timedelta(days=364)).isoformat()})  # fmt: skip
    assert made.status_code == 201, made.text
    plan = made.json()["data"]["ref"]
    assert plan.startswith("APL-")
    path = f"/api/v1/audit/plans/{plan}/engagements"
    unsaid = auditor.post(path, json={"name": "Sequencing", "kind": "process", "key": refs["busy"],
                                      "reason": ""})  # fmt: skip
    assert unsaid.status_code == 422 and "reason" in unsaid.text
    wanted = {
        "name": "Sequencing data management",
        "kind": "process",
        "key": refs["busy"],
        "reason": "Highest ranked; never audited.",
        "planned_start": today.isoformat(),
    }
    added = auditor.post(path, json=wanted)
    assert added.status_code == 201, added.text
    shown = added.json()["data"]
    first = shown["engagements"][0]
    assert first["ref"].startswith("AUD-") and first["status"] == "planned"
    assert first["entity"]["ref"] == refs["busy"]
    universe = auditor.get("/api/v1/audit/universe").json()["data"]
    assert entity(universe, refs["busy"])["planned"] == [first["ref"]]

    # The auditor who drafted it cannot approve it; the president's role could, and so can
    # another auditor, recording the committee's approval.
    assert auditor.post(f"/api/v1/audit/plans/{plan}/approve", json={}).status_code == 403
    assert shown["can"]["approve"] is False
    with db.write(who(db, people, "admin").actor) as session:
        from riskwren.access.principal import Grant
        from riskwren.people import accounts
        from tests.people import ME

        chief_auditor = {
            "email": "chief@northmere.example",
            "display_name": "Chief Auditor",
            "password": "a long enough passphrase",
            "grants": [Grant("auditor")],
        }
        accounts.create(session, ME, **chief_auditor)
    from tests.people import sign_in

    chief = sign_in(as_role(None), "chief@northmere.example")
    note = {"note": "Approved by the audit committee on 3 December."}
    approved = chief.post(f"/api/v1/audit/plans/{plan}/approve", json=note)
    assert approved.status_code == 200, approved.text
    body = approved.json()["data"]
    assert body["status"] == "approved" and body["approved_by"] == "Chief Auditor"
    asked = {
        "name": "Seminar booking",
        "kind": "process",
        "key": refs["quiet"],
        "reason": "Asked for by the board.",
    }
    late = auditor.post(path, json=asked)
    rows = {row["name"]: row for row in late.json()["data"]["engagements"]}
    assert rows["Seminar booking"]["added_after_approval"] is True
    assert rows["Sequencing data management"]["added_after_approval"] is False
    engagement = rows["Seminar booking"]["ref"]
    assert (
        auditor.post(f"/api/v1/engagements/{engagement}/drop", json={"reason": " "}).status_code
        == 422
    )
    dropped = auditor.post(f"/api/v1/engagements/{engagement}/drop", json={"reason": "Outsourced."})
    assert dropped.json()["data"]["status"] == "dropped"
    counts = auditor.get(f"/api/v1/audit/plans/{plan}").json()["data"]["counts"]
    assert counts["planned"] == 1 and counts["dropped"] == 1
    assert auditor.post(f"/api/v1/audit/plans/{plan}/close").status_code == 200
    closed = auditor.post(path, json={"name": "x", "kind": "process", "key": refs["quiet"],
                                      "reason": "y"})  # fmt: skip
    assert closed.status_code == 409
    period = {
        "name": "x",
        "starts_on": today.isoformat(),
        "ends_on": (today + timedelta(days=30)).isoformat(),
    }
    assert as_role("manager").post("/api/v1/audit/plans", json=period).status_code == 403
    # An empty plan is not approved, even by someone who may approve it.
    bare = auditor.post("/api/v1/audit/plans", json=period).json()["data"]["ref"]
    assert chief.post(f"/api/v1/audit/plans/{bare}/approve", json={}).status_code == 422
