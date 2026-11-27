"""Business impact: what each process cannot afford to lose, and whether the systems and
services it relies on can deliver it."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from riskwren.db.engine import Database
from riskwren.inventory import links, records
from riskwren.inventory.registry import PROCESS, SYSTEM
from tests.people import People
from tests.test_risks import who
from tests.test_third_parties import supplier_with_a_service

Clients = Callable[[str | None], TestClient]
HURTS = [{"after": "4h", "level": 2}, {"after": "1d", "level": 4}, {"after": "1w", "level": 5}]
NEEDS = {
    "impacts": HURTS,
    "recovery_hours": 24, "data_loss_hours": 4,
    "minimum": "Two coordinators, the portal, and the participant list.",
}  # fmt: skip


def relies_on_both(db: Database, people: People) -> dict[str, str]:
    """The cohort follow-up relies on the survey service and, directly, on the portal."""
    refs = supplier_with_a_service(db, people)
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        process = records.load(session, steward, PROCESS, refs["process"])
        portal = records.load(session, steward, SYSTEM, refs["portal"])
        links.add(session, steward, PROCESS, process, "relies_on", SYSTEM, portal)
    return refs


def test_a_process_is_checked_against_what_its_dependencies_can_deliver(
    as_role: Clients, people: People, db: Database
) -> None:
    refs = relies_on_both(db, people)
    steward = as_role("steward")
    path = f"/api/v1/processes/{refs['process']}/impact"
    backwards = {**NEEDS, "impacts": [{"after": "4h", "level": 4}, {"after": "1d", "level": 2}]}
    assert steward.post(path, json=backwards).status_code == 422
    first = steward.post(path, json=NEEDS)
    assert first.status_code == 201, first.text
    shown = first.json()["data"]
    assert shown["analysis"]["recovery_hours"] == 24 and shown["shortfalls"] == 2
    assert {d["ref"] for d in shown["dependencies"]} == {refs["portal"], refs["service"]}
    assert all(d["problems"] == ["Nobody has said what it can be restored within."]
               for d in shown["dependencies"])  # fmt: skip

    slow = {"recovery_hours": 48, "data_loss_hours": 1, "basis": "Restored in a test in March."}
    steward.post(f"/api/v1/systems/{refs['portal']}/recovery", json=slow)
    lossy = {"recovery_hours": 8, "data_loss_hours": 24, "basis": "The contract's terms."}
    steward.post(f"/api/v1/services/{refs['service']}/recovery", json=lossy)
    checked = {d["ref"]: d for d in steward.get(path).json()["data"]["dependencies"]}
    assert checked[refs["portal"]]["problems"] == [
        "It is back in 48 hours; the process needs it in 24."
    ]
    assert checked[refs["service"]]["problems"] == [
        "It can lose 24 hours of information; the process can afford 4."
    ]
    fixed = {"recovery_hours": 8, "data_loss_hours": 1, "basis": "Restored in a test in May."}
    again = steward.post(f"/api/v1/systems/{refs['portal']}/recovery", json=fixed).json()["data"]
    assert again["capability"]["recovery_hours"] == 8 and len(again["earlier"]) == 1
    assert [p["ref"] for p in again["needed_by"]] == [refs["process"]]
    assert again["needed_by"][0]["recovery_hours"] == 24
    assert steward.post(f"/api/v1/systems/{refs['portal']}/recovery",
                        json={**fixed, "basis": " "}).status_code == 422  # fmt: skip

    overview = as_role("manager").get("/api/v1/resilience").json()["data"]
    row = next(p for p in overview["processes"] if p["ref"] == refs["process"])
    assert [s["ref"] for s in row["shortfalls"]] == [refs["service"]]
    relaxed = {**NEEDS, "recovery_hours": 72, "data_loss_hours": 24}
    second = steward.post(path, json=relaxed).json()["data"]
    assert second["shortfalls"] == 0 and len(second["earlier"]) == 1
    history = steward.get(f"/api/v1/processes/{refs['process']}/history").json()["data"]
    titles = [entry["title"] for entry in history]
    assert any(t.startswith("Analysed its business impact: back within 72 hours") for t in titles)
    # Those who do not keep the process cannot analyse it.
    assert as_role("member").post(path, json=NEEDS).status_code in (403, 404)
