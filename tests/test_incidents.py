"""Incidents: reported by anyone in one form, seen by those who need to, and triaged."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.access.principal import Grant
from riskwren.db.engine import Database
from riskwren.db.models import Event, Incident
from riskwren.incidents import anonymous
from riskwren.inventory import records
from riskwren.inventory.registry import SYSTEM
from riskwren.people import accounts
from tests.people import ME, People, sign_in
from tests.test_risks import who

Clients = Callable[[str | None], TestClient]


def _report(client: TestClient, **more: object) -> dict:
    body = {"kind": "incident", "name": "Laptop left on the train",
            "summary": "My work laptop was left on the 8:05 train. It has the lab's data on it.",
            "occurred_on": "2026-11-20", "location": "The 8:05 train", **more}  # fmt: skip
    sent = client.post("/api/v1/incidents", json=body)
    assert sent.status_code == 201, sent.text
    return sent.json()["data"]


def _fields(response: object) -> set[str]:
    return {error["location"][0] for error in response.json()["errors"]}  # type: ignore[attr-defined]


def _outsider(as_role: Clients, people: People, db: Database) -> TestClient:
    """A steward of Cancer Biology, who works there: nothing to do with the Hale Lab."""
    with db.write(ME.actor) as session:
        account = accounts.create(
            session, ME, email="outsider@northmere.example", display_name="Outside Person",
            password="a long enough passphrase",
            grants=[Grant("steward", org_unit_id=people.units["CANCER"])],
        )  # fmt: skip
        accounts.set_memberships(session, ME, account, [people.units["CANCER"]])
    return sign_in(as_role(None), "outsider@northmere.example")


def test_a_report_is_seen_by_those_who_need_to_and_nobody_else(
    as_role: Clients, people: People, db: Database
) -> None:
    member = as_role("member")
    report = _report(member)
    ref = report["ref"]
    assert ref.startswith("INC-") and report["status"] == "reported"
    # It is put in the reporter's own unit, and has no handler until it is triaged.
    assert report["org_unit_id"] == people.units["HALE"] and report["owners"] == []
    assert report["is_reporter"] is True and report["everything"] is False
    for role in ("member", "manager", "assessor", "leader", "steward", "auditor", "admin"):
        assert as_role(role).get(f"/api/v1/incidents/{ref}").status_code == 200, role
        listed = as_role(role).get("/api/v1/incidents").json()["data"]
        assert [row["ref"] for row in listed] == [ref], role
    outsider = _outsider(as_role, people, db)
    assert outsider.get(f"/api/v1/incidents/{ref}").status_code == 404
    assert outsider.get("/api/v1/incidents").json()["data"] == []
    assert outsider.get(f"/api/v1/incidents/{ref}/history").status_code == 404
    # Those who triage for the unit are told.
    told = as_role("assessor").get("/api/v1/notices").json()["data"]
    assert any(ref in notice["text"] for notice in told)
    owed = as_role("assessor").get("/api/v1/home").json()["data"]["items"]
    assert any(item["kind"] == "incident_triage" and item["ref"] == ref for item in owed)
    # A steward of its unit sees it, but is not asked to name who answers for it.
    owed = as_role("steward").get("/api/v1/home").json()["data"]["items"]
    assert not any(item.get("ref") == ref for item in owed)


def test_triage_gives_it_a_category_a_severity_its_records_and_a_handler(
    as_role: Clients, people: People, db: Database
) -> None:
    ref = _report(as_role("member"))["ref"]
    with db.write(ME.actor) as session:
        laptop = records.create(session, ME, SYSTEM, {"name": "Lab laptops", "kind": "device",
                                                      "org_unit_id": people.units["HALE"],
                                                      "criticality": "moderate"})  # fmt: skip
        laptop_ref = laptop.ref
    assessor = as_role("assessor")
    steward_id = people.accounts["steward"]
    wrong = assessor.post(f"/api/v1/incidents/{ref}/triage", json={
        "category": "weather", "severity": "dire", "subjects": ["SYS-9999"]})  # fmt: skip
    assert wrong.status_code == 422
    assert _fields(wrong) >= {"category", "severity", "subjects", "handler_id"}
    for role in ("leader", "steward", "member"):
        refused = as_role(role).post(f"/api/v1/incidents/{ref}/triage", json={
            "category": "security", "severity": "high", "handler_id": steward_id})  # fmt: skip
        assert refused.status_code == 403, role
    done = assessor.post(f"/api/v1/incidents/{ref}/triage", json={
        "category": "security", "severity": "high", "subjects": [laptop_ref],
        "handler_id": steward_id})  # fmt: skip
    assert done.status_code == 200, done.text
    incident = done.json()["data"]
    assert incident["status"] == "handling" and incident["category"] == "security"
    assert incident["severity"] == "high"
    assert [chip["ref"] for chip in incident["subjects"]["records"]] == [laptop_ref]
    assert [(o["account_id"], o["kind"]) for o in incident["owners"]] == [(steward_id, "owner")]
    assert incident["triaged"]["by"] == "Assessor Person"
    # The handler and the reporter are told; the handler finds it waiting on them.
    steward = as_role("steward")
    assert any(ref in n["text"] for n in steward.get("/api/v1/notices").json()["data"])
    owed = steward.get("/api/v1/home").json()["data"]["items"]
    assert any(item["kind"] == "incident_handle" and item["ref"] == ref for item in owed)
    told = as_role("member").get("/api/v1/notices").json()["data"]
    assert any("being handled" in n["text"] for n in told)
    # Triage again names another handler in place of the first.
    again = assessor.post(f"/api/v1/incidents/{ref}/triage", json={
        "category": "privacy", "severity": "critical", "subjects": [],
        "handler_id": people.accounts["manager"]})  # fmt: skip
    data = again.json()["data"]
    assert [o["account_id"] for o in data["owners"]] == [people.accounts["manager"]]
    assert data["subjects"]["records"] == [] and data["category"] == "privacy"
    # It is all in the history.
    events = as_role("manager").get(f"/api/v1/incidents/{ref}/history").json()["data"]
    titles = " ".join(str(event.get("title")) for event in events)
    assert "Now concerns" in titles and "No longer concerns" in titles


def test_the_reporter_sees_what_they_reported_and_what_is_said_to_them(
    as_role: Clients, people: People
) -> None:
    member = as_role("member")
    ref = _report(member)["ref"]
    assessor = as_role("assessor")
    assessor.post(f"/api/v1/incidents/{ref}/triage", json={
        "category": "security", "severity": "high",
        "handler_id": people.accounts["steward"]})  # fmt: skip
    steward = as_role("steward")
    note = steward.post(
        f"/api/v1/incidents/{ref}/messages",
        json={"body": "Asked IT to wipe it remotely.", "shared": False},
    )
    assert note.status_code == 201, note.text
    steward.post(f"/api/v1/incidents/{ref}/messages",
                 json={"body": "Thank you. Was it locked?", "shared": True})  # fmt: skip
    mine = member.get(f"/api/v1/incidents/{ref}").json()["data"]
    assert [m["body"] for m in mine["messages"]] == ["Thank you. Was it locked?"]
    assert "subjects" not in mine and "reporter" not in mine and mine["severity"] is None
    assert member.get(f"/api/v1/incidents/{ref}/history").status_code == 404
    # Nor the views that show every field of a record, or what it is joined to.
    for view in (f"/api/v1/as-of/{ref}", f"/api/v1/graph/{ref}"):
        assert member.get(view).status_code == 404, view
        assert steward.get(view).status_code == 200, view
    # The reporter answers; whatever they send is shared, and the handler is told.
    member.post(f"/api/v1/incidents/{ref}/messages", json={"body": "Yes, with a PIN.",
                                                            "shared": False})  # fmt: skip
    handled = steward.get(f"/api/v1/incidents/{ref}").json()["data"]
    said = [(m["body"], m["from_reporter"], m["shared"]) for m in handled["messages"]]
    assert said[-1] == ("Yes, with a PIN.", True, True) and len(said) == 3
    assert handled["reporter"]["name"] == "Member Person"
    assert any("reporter wrote" in n["text"] for n in steward.get("/api/v1/notices").json()["data"])
    # The reporter cannot change it, or triage it.
    assert member.post(f"/api/v1/incidents/{ref}/close", json={"note": "x"}).status_code == 403
    version = mine["version"]
    assert (
        member.patch(
            f"/api/v1/incidents/{ref}", json={"version": version, "name": "Changed"}
        ).status_code
        == 403
    )


def test_closing_and_reopening(as_role: Clients, people: People) -> None:
    member = as_role("member")
    ref = _report(member, kind="near_miss")["ref"]
    as_role("assessor").post(f"/api/v1/incidents/{ref}/triage", json={
        "category": "security", "severity": "low",
        "handler_id": people.accounts["steward"]})  # fmt: skip
    steward = as_role("steward")
    assert steward.post(f"/api/v1/incidents/{ref}/close", json={}).status_code == 422
    closed = steward.post(f"/api/v1/incidents/{ref}/close",
                          json={"note": "Found in lost property, untouched."})  # fmt: skip
    assert closed.status_code == 200 and closed.json()["data"]["status"] == "closed"
    assert any("is closed" in n["text"] for n in member.get("/api/v1/notices").json()["data"])
    refused = steward.post(f"/api/v1/incidents/{ref}/messages", json={"body": "One more thing"})
    assert refused.status_code == 409
    assert steward.post(f"/api/v1/incidents/{ref}/reopen").status_code == 403
    reopened = as_role("assessor").post(f"/api/v1/incidents/{ref}/reopen")
    assert reopened.json()["data"]["status"] == "handling"


def test_a_report_needs_to_say_what_happened(as_role: Clients) -> None:
    member = as_role("member")
    empty = member.post("/api/v1/incidents", json={"occurred_on": "2999-01-01"})
    assert empty.status_code == 422
    assert _fields(empty) >= {"name", "summary", "occurred_on"}
    odd = member.post("/api/v1/incidents", json={"name": "x", "summary": "y", "kind": "rumor"})
    assert odd.status_code == 422 and "kind" in _fields(odd)


# --- Reporting without a name -------------------------------------------------------------


def test_reporting_without_a_name_is_closed_until_an_administrator_opens_it(
    as_role: Clients, people: People, db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    nobody = as_role(None)
    concern = {
        "name": "Someone is taking samples home",
        "summary": "A colleague takes specimen tubes home in a cooler on Fridays.",
    }
    assert nobody.get("/api/v1/meta").json()["data"]["report_without_name"] is False
    assert nobody.post("/api/v1/anonymous-reports", json=concern).status_code == 404
    assert as_role("manager").put("/api/v1/admin/anonymous-reporting",
                                  json={"open": True}).status_code == 403  # fmt: skip
    opened = as_role("admin").put("/api/v1/admin/anonymous-reporting", json={"open": True})
    assert opened.status_code == 200 and opened.json()["data"]["open"] is True
    assert nobody.get("/api/v1/anonymous-reports").json()["data"]["open"] is True

    sent = nobody.post("/api/v1/anonymous-reports", json=concern)
    assert sent.status_code == 201, sent.text
    ref, code = sent.json()["data"]["ref"], sent.json()["data"]["code"]
    assert len(code) == 23 and code.count("-") == 3
    with db.read() as session:
        incident = session.scalars(select(Incident).where(Incident.ref == ref)).one()
        assert incident.anonymous and incident.created_by is None and incident.kind == "concern"
        assert incident.org_unit_id == people.units["NMI"]
        assert incident.follow_up_hash == anonymous.digest(code)
        events = session.scalars(select(Event).where(Event.subject_type == "incident")).all()
        assert {event.actor_label for event in events} == {"Reported without a name"}
        assert code not in str([event.changes for event in events])
        assert incident.follow_up_hash not in str([event.changes for event in events])

    # Typed however it comes: small letters, no dashes, an O for a zero.
    typed = code.replace("-", "").lower().replace("0", "o")
    seen = nobody.post("/api/v1/anonymous-reports/follow-up", json={"code": typed})
    assert seen.status_code == 200 and seen.json()["data"]["status"] == "reported"
    wrong = nobody.post("/api/v1/anonymous-reports/follow-up", json={"code": "ABCDE-12345"})
    assert wrong.status_code == 404

    manager = as_role("manager")
    shown = manager.get(f"/api/v1/incidents/{ref}").json()["data"]
    assert shown["reporter"] is None and shown["anonymous"] is True
    manager.post(f"/api/v1/incidents/{ref}/triage", json={
        "category": "conduct", "severity": "moderate", "org_unit_id": people.units["HALE"],
        "handler_id": people.accounts["manager"]})  # fmt: skip
    manager.post(f"/api/v1/incidents/{ref}/messages",
                 json={"body": "Thank you. Which day did you last see it?"})  # fmt: skip
    added = nobody.post("/api/v1/anonymous-reports/messages",
                        json={"code": code, "body": "Last Friday, about five."})  # fmt: skip
    assert added.status_code == 200, added.text
    said = added.json()["data"]["messages"]
    assert [(m["by"], m["body"]) for m in said] == [
        ("Those handling it", "Thank you. Which day did you last see it?"),
        ("You", "Last Friday, about five."),
    ]
    assert "owners" not in added.json()["data"] and "severity" not in added.json()["data"]

    # Someone signed in who reports without a name is not named either.
    member = as_role("member")
    from riskwren.auth.sessions import CSRF_HEADER

    member.headers.pop(CSRF_HEADER)
    theirs = member.post("/api/v1/anonymous-reports", json=concern)
    assert theirs.status_code == 201, theirs.text
    with db.read() as session:
        row = session.scalars(
            select(Incident).where(Incident.ref == theirs.json()["data"]["ref"])
        ).one()
        assert row.created_by is None
    # Only so many an hour, from everyone together.
    monkeypatch.setattr(anonymous, "MOST_AN_HOUR", 3)
    assert nobody.post("/api/v1/anonymous-reports", json=concern).status_code == 201
    assert nobody.post("/api/v1/anonymous-reports", json=concern).status_code == 409
    # Closing it again closes the page.
    as_role("admin").put("/api/v1/admin/anonymous-reporting", json={"open": False})
    assert nobody.post("/api/v1/anonymous-reports", json=concern).status_code == 404


def test_who_sees_a_report_follows_the_rule(db: Database, people: People) -> None:
    """The record type's rule and its condition for lists agree."""
    from riskwren.incidents import reports

    with db.write(ME.actor) as session:
        member = who(db, people, "member")
        made = reports.create(session, member, {"name": "Door propped open", "summary": "x"})
        made_id = made.id
    for role in ("member", "manager", "assessor", "leader", "steward", "auditor", "admin"):
        principal = who(db, people, role)
        with db.read() as session:
            incident = session.get(Incident, made_id)
            assert reports.can_see(session, principal, incident), role
            rows, _ = records.search(session, principal, reports.INCIDENT, {})
            assert [row.id for row in rows] == [made_id], role
