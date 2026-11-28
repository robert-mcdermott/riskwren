"""Learning and losses (INC-06): an incident joined to the risks it realized and the controls
that failed or held, what was learned, what it cost, and the issues that put it right."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from riskwren.db.engine import Database
from tests.people import People
from tests.test_incidents import _report
from tests.test_risks import raise_risk, who
from tests.test_treatment import add_control

Clients = Callable[[str | None], TestClient]


def _fields(response: object) -> set[str]:
    return {error["location"][0] for error in response.json()["errors"]}  # type: ignore[attr-defined]


def _setup(as_role: Clients, people: People, db: Database) -> tuple[str, str, str, str]:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        risk = raise_risk(session, steward, people.units["IMM"], "Ransomware on the lab network")
        mfa = add_control(session, steward, people.units["IMM"], "Multi-factor sign-in")
        backup = add_control(session, steward, people.units["IMM"], "Offline backups")
        refs = risk.ref, mfa.ref, backup.ref
    ref = _report(as_role("member"), name="Files encrypted on the shared drive")["ref"]
    as_role("assessor").post(f"/api/v1/incidents/{ref}/triage", json={
        "category": "security", "severity": "high",
        "handler_id": people.accounts["steward"]})  # fmt: skip
    return (ref, *refs)


def test_an_incident_teaches_the_register(as_role: Clients, people: People, db: Database) -> None:
    ref, risk, mfa, backup = _setup(as_role, people, db)
    steward = as_role("steward")
    wrong = steward.put(f"/api/v1/incidents/{ref}/learning",
                        json={"realized": [mfa], "failed": [backup], "held": [backup]})  # fmt: skip
    assert wrong.status_code == 422 and _fields(wrong) >= {"realized", "held"}
    cause = steward.put(f"/api/v1/incidents/{ref}/learning", json={"root_cause": "bad luck"})
    assert cause.status_code == 422 and "root_cause" in _fields(cause)
    # A high incident is not closed until what was learned is said.
    refused = steward.post(f"/api/v1/incidents/{ref}/close", json={"note": "Restored."})
    assert refused.status_code == 409 and "learned" in refused.text
    done = steward.put(f"/api/v1/incidents/{ref}/learning", json={
        "realized": [risk], "failed": [mfa], "held": [backup],
        "lessons": "The account had no second factor. The backups were apart, and saved us.",
        "root_cause": "design"})  # fmt: skip
    assert done.status_code == 200, done.text
    data = done.json()["data"]
    assert [chip["ref"] for chip in data["links"]["realized"]] == [risk]
    assert [chip["ref"] for chip in data["links"]["failed"]] == [mfa]
    assert [chip["ref"] for chip in data["links"]["held"]] == [backup]
    # Triage again leaves what was learned alone.
    as_role("assessor").post(f"/api/v1/incidents/{ref}/triage", json={
        "category": "security", "severity": "high", "subjects": [],
        "handler_id": people.accounts["steward"]})  # fmt: skip
    again = steward.get(f"/api/v1/incidents/{ref}").json()["data"]
    assert [chip["ref"] for chip in again["links"]["failed"]] == [mfa]

    # What it cost, in each currency.
    for amount, kind in ((4800, "response"), (12500, "recovery"), (-300, "response")):
        added = steward.post(f"/api/v1/incidents/{ref}/losses",
                             json={"kind": kind, "amount": amount})  # fmt: skip
        assert added.status_code == 201, added.text
    assert added.json()["data"]["loss_totals"] == {"USD": 17000}
    bad = steward.post(f"/api/v1/incidents/{ref}/losses", json={"kind": "tears", "amount": 1})
    assert bad.status_code == 422

    # An issue to put right what it showed, with the incident as its source.
    raised = steward.post(f"/api/v1/incidents/{ref}/issues", json={
        "name": "Lab network accounts have no second factor", "severity": "high",
        "subjects": [mfa]})  # fmt: skip
    assert raised.status_code == 201, raised.text
    issue = raised.json()["data"]["issues"][0]
    shown = steward.get(f"/api/v1/issues/{issue['ref']}").json()["data"]
    assert shown["source"]["incident"]["ref"] == ref and shown["source_kind"] == "incident"

    # The register learns back: the risk shows what realized it and what that cost; the
    # controls show where they failed and held.
    seen = as_role("manager").get(f"/api/v1/risks/{risk}").json()["data"]["incidents"]
    assert [item["ref"] for item in seen["items"]] == [ref]
    assert seen["loss_totals"] == {"USD": 17000} and seen["last_year"] == 1
    failed = as_role("manager").get(f"/api/v1/controls/{mfa}").json()["data"]["incidents"]
    assert [item["role"] for item in failed["items"]] == ["failed"]
    summary = as_role("manager").get("/api/v1/incidents/summary").json()["data"]
    assert summary["total"] == 1 and summary["loss_totals"] == {"USD": 17000}
    assert summary["realized"][0]["ref"] == risk and summary["failed"][0]["ref"] == mfa

    closed = steward.post(f"/api/v1/incidents/{ref}/close", json={"note": "Restored."})
    assert closed.status_code == 200, closed.text
    events = steward.get(f"/api/v1/incidents/{ref}/history").json()["data"]
    titles = " ".join(str(event.get("title")) for event in events)
    assert "Realized the risk" in titles and "failed" in titles and "Recorded a cost" in titles


def test_a_restricted_case_never_shows_beside_a_risk(
    as_role: Clients, people: People, db: Database
) -> None:
    ref, risk, mfa, _ = _setup(as_role, people, db)
    steward = as_role("steward")
    steward.put(f"/api/v1/incidents/{ref}/learning", json={
        "realized": [risk], "failed": [mfa], "lessons": "x"})  # fmt: skip
    steward.post(f"/api/v1/incidents/{ref}/losses", json={"kind": "legal", "amount": 9000})
    steward.put(f"/api/v1/incidents/{ref}/case", json={"restricted": True})
    raised = steward.post(f"/api/v1/incidents/{ref}/issues", json={
        "name": "Lab network accounts have no second factor", "severity": "high"})  # fmt: skip
    issue_ref = raised.json()["data"]["issues"][0]["ref"]
    for role in ("manager", "leader", "assessor"):
        client = as_role(role)
        seen = client.get(f"/api/v1/risks/{risk}").json()["data"]["incidents"]
        assert seen["items"] == [] and seen["loss_totals"] == {}, role
        assert client.get("/api/v1/incidents/summary").json()["data"]["total"] == 0, role
    # Its issue is restricted too, and names the case only to those who may know of it.
    assert as_role("assessor").get(f"/api/v1/issues/{issue_ref}").status_code == 404
    shown = as_role("manager").get(f"/api/v1/issues/{issue_ref}").json()["data"]
    assert shown["restricted"] is True and shown["source"] is None
    assert steward.get(f"/api/v1/risks/{risk}").json()["data"]["incidents"]["items"]
