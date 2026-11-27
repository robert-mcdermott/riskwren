"""Scenarios, estimates in ranges with their simulation, and the bow-tie."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from riskwren.controls import service as controls
from riskwren.db.engine import Database
from riskwren.inventory.registry import PROCESS
from riskwren.risk import bowtie, simulation
from tests.people import People
from tests.test_risks import judge, raise_risk, who
from tests.test_third_parties import thing
from tests.test_treatment import add_control

Clients = Callable[[str | None], TestClient]
GOOD = {
    "frequency_low": 0.1, "frequency_likely": 0.3, "frequency_high": 1,
    "loss_low": 50_000, "loss_likely": 400_000, "loss_high": 3_000_000,
    "assumptions": "Two incidents at peer institutes in five years; recovery costs from them.",
}  # fmt: skip


def two_risks(db: Database, people: People) -> dict[str, str]:
    steward = who(db, people, "steward")
    imm = people.units["IMM"]
    with db.write(steward.actor) as session:
        story = {
            "cause": "Phishing; unpatched instruments\nShared administrator accounts",
            "event": "Lab systems are encrypted",
            "consequence": "Experiments are lost; grant reporting is late",
        }
        ransom = raise_risk(session, steward, imm, "Ransomware on the lab network", **story)
        judge(session, steward, ransom, "inherent", 4, safety=4)
        freezer = raise_risk(session, steward, imm, "Freezer failure")
        sequencing = thing(session, steward, PROCESS, name="Sequencing runs", unit=imm,
                           criticality="high")  # fmt: skip
        return {"ransom": ransom.ref, "freezer": freezer.ref, "process": sequencing.ref}


def test_a_scenario_touches_risks_and_processes_and_says_what_was_concluded(
    as_role: Clients, people: People, db: Database
) -> None:
    refs = two_risks(db, people)
    steward = as_role("steward")
    made = steward.post("/api/v1/scenarios", json={
        "name": "Ransomware takes the lab down for two weeks", "org_unit_id": people.units["IMM"],
        "summary": "Lab systems are encrypted on a Friday night.",
        "assumptions": "Backups are intact; instruments take a week to reinstall."})  # fmt: skip
    assert made.status_code == 201, made.text
    ref = made.json()["data"]["ref"]
    assert ref.startswith("SCN-") and made.json()["data"]["status"] == "draft"
    touched = steward.put(f"/api/v1/scenarios/{ref}/subjects",
                          json={"subjects": [refs["ransom"], refs["process"]]})  # fmt: skip
    assert touched.status_code == 200, touched.text
    touches = touched.json()["data"]["touches"]
    assert [r["ref"] for r in touches["risks"]] == [refs["ransom"]]
    assert [p["ref"] for p in touches["processes"]] == [refs["process"]]
    wrong = steward.put(f"/api/v1/scenarios/{ref}/subjects", json={"subjects": ["CTL-0001"]})
    assert wrong.status_code == 422
    version = touched.json()["data"]["version"]
    unsaid = steward.patch(
        f"/api/v1/scenarios/{ref}", json={"status": "concluded", "version": version}
    )
    assert unsaid.status_code == 422 and "conclusion" in unsaid.text
    done = steward.patch(f"/api/v1/scenarios/{ref}", json={
        "status": "concluded", "version": version,
        "conclusion": "Two weeks is survivable; keep instrument images offline."})  # fmt: skip
    assert done.status_code == 200 and done.json()["data"]["concluded_on"]
    titles = [e["title"] for e in steward.get(f"/api/v1/scenarios/{ref}/history").json()["data"]]
    assert any(title.startswith("Now touches") for title in titles)
    listed = steward.get("/api/v1/scenarios", params={"risk": refs["ransom"]}).json()
    assert [row["ref"] for row in listed["data"]] == [ref] and listed["data"][0]["risks"] == 1
    assert as_role("member").post("/api/v1/scenarios", json={
        "name": "x", "org_unit_id": people.units["IMM"]}).status_code == 403  # fmt: skip


def test_an_estimate_supersedes_the_last_and_a_scenario_adds_its_risks_up(
    as_role: Clients, people: People, db: Database
) -> None:
    refs = two_risks(db, people)
    steward = as_role("steward")
    path = f"/api/v1/risks/{refs['ransom']}/estimate"
    backwards = steward.post(path, json={**GOOD, "frequency_likely": 2})
    assert backwards.status_code == 422 and "frequency_likely" in backwards.text
    unsaid = steward.post(path, json={**GOOD, "assumptions": " "})
    assert unsaid.status_code == 422 and "assumptions" in unsaid.text
    first = steward.post(path, json=GOOD)
    assert first.status_code == 201, first.text
    shown = first.json()["data"]
    found = shown["simulation"]
    assert found["years"] == simulation.YEARS and found["assumptions"]
    assert found["percentiles"]["10"] <= found["percentiles"]["50"] <= found["percentiles"]["90"]
    # The same estimate gives the same figures, every time.
    assert steward.get(path).json()["data"]["simulation"] == found
    second = steward.post(path, json={**GOOD, "loss_likely": 600_000}).json()["data"]
    assert second["estimate"]["loss"]["likely"] == 600_000 and len(second["earlier"]) == 1
    assert second["earlier"][0]["superseded"] is True
    history = steward.get(f"/api/v1/risks/{refs['ransom']}/history").json()["data"]
    assert any(e["title"].startswith("Estimated in ranges") for e in history)
    assert as_role("member").post(path, json=GOOD).status_code in (403, 404)

    steward.post(f"/api/v1/risks/{refs['freezer']}/estimate", json={
        **GOOD, "frequency_low": 0.5, "frequency_likely": 1, "frequency_high": 2,
        "loss_low": 10_000, "loss_likely": 40_000, "loss_high": 90_000})  # fmt: skip
    scenario = steward.post("/api/v1/scenarios", json={
        "name": "A bad winter", "org_unit_id": people.units["IMM"]}).json()["data"]  # fmt: skip
    both = {"subjects": [refs["ransom"], refs["freezer"]]}
    detail = steward.put(f"/api/v1/scenarios/{scenario['ref']}/subjects", json=both).json()["data"]
    together = detail["simulation"]
    assert sorted(together["included"]) == sorted([refs["ransom"], refs["freezer"]])
    assert together["without"] == [] and together["currency"] == "USD"
    assert together["mean"] > second["simulation"]["mean"]


def test_a_simulation_is_reproducible_and_near_what_the_ranges_expect() -> None:
    each = simulation.Inputs(
        "RSK-0001", simulation.Range(0.5, 1, 2), simulation.Range(1_000, 5_000, 20_000)
    )
    first, again = simulation.run([each]), simulation.run([each])
    assert first == again
    expected = simulation.Range(0.5, 1, 2).mean * simulation.Range(1_000, 5_000, 20_000).mean
    assert abs(first["mean"] - expected) / expected < 0.05
    assert first["expected"] == round(expected)
    chances = [point["chance"] for point in first["exceedance"]]
    assert chances == sorted(chances, reverse=True)
    nothing = simulation.run([simulation.Inputs("x", simulation.Range(0, 0, 0),
                                                simulation.Range(1, 2, 3))])  # fmt: skip
    assert nothing["mean"] == 0 and nothing["any_loss"] == 0
    assert simulation.poisson(__import__("random").Random(1), 200) > 100


def test_the_bow_tie_reads_the_risk_and_its_controls(
    as_role: Clients, people: People, db: Database
) -> None:
    refs = two_risks(db, people)
    manager = who(db, people, "manager")
    with db.write(manager.actor) as session:
        from riskwren.inventory import records
        from riskwren.risk.register import RISK

        risk = records.load(session, manager, RISK, refs["ransom"])
        for name, reduces in (("Patching", "likelihood"), ("Offline backups", "impact"),
                              ("Network separation", "both")):  # fmt: skip
            control = add_control(session, manager, people.units["IMM"], name)
            controls.link(session, manager, risk, control, reduces=reduces, reliance="primary")
    shown = as_role("steward").get(f"/api/v1/risks/{refs['ransom']}/bow-tie").json()["data"]
    assert shown["causes"] == ["Phishing", "Unpatched instruments", "Shared administrator accounts"]
    assert shown["event"] == "Lab systems are encrypted"
    assert shown["consequences"] == ["Experiments are lost", "Grant reporting is late"]
    assert [c["name"] for c in shown["preventive"]] == ["Patching", "Network separation"]
    assert [c["name"] for c in shown["mitigating"]] == ["Offline backups", "Network separation"]
    assert bowtie.parts(None) == [] and bowtie.parts("One cause") == ["One cause"]
