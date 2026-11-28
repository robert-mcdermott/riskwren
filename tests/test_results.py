"""Results pushed in (INT-04): another system reports a check or a piece of evidence onto a
control; it counts only once a person who does not own the control confirms it."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.people import People

Clients = Callable[[str | None], TestClient]


def _token(as_role: Clients, role: str, **more: object) -> TestClient:
    made = as_role("admin").post("/api/v1/admin/tokens", json={
        "name": f"Scanner as {role}", "role": role, "days": 30, **more})  # fmt: skip
    assert made.status_code == 201, made.text
    client = as_role(None)
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token", None)
    client.headers["Authorization"] = f"Bearer {made.json()['meta']['token']}"
    return client


def _control(as_role: Clients, people: People) -> str:
    made = as_role("manager").post("/api/v1/controls", json={
        "name": "Patching of servers", "statement": "Servers are patched within 30 days.",
        "kind": "preventive", "org_unit_id": people.units["HALE"]})  # fmt: skip
    assert made.status_code == 201, made.text
    return made.json()["data"]["ref"]


def test_a_failed_check_counts_once_a_person_confirms_it(as_role: Clients, people: People) -> None:
    ref = _control(as_role, people)
    scanner = _token(as_role, "steward", org_unit_id=people.units["HALE"], read_only=False)
    failed = {"kind": "result", "outcome": "failed", "title": "12 servers missing patches",
              "detail": "Hosts listed in the scan.",
              "url": "https://scanner.example.org/r/9"}  # fmt: skip
    # A person records results in an assessment; a reading token changes nothing; an auditor's
    # token does not report.
    assert (
        as_role("manager").post(f"/api/v1/controls/{ref}/reported", json=failed).status_code == 403
    )
    assert _token(as_role, "steward", org_unit_id=people.units["HALE"]).post(
        f"/api/v1/controls/{ref}/reported", json=failed).status_code == 403  # fmt: skip
    assert _token(as_role, "auditor", read_only=False).post(
        f"/api/v1/controls/{ref}/reported", json=failed).status_code == 403  # fmt: skip
    wrong = scanner.post(f"/api/v1/controls/{ref}/reported", json={
        "kind": "result", "outcome": "maybe", "title": "", "observed_at": "tomorrow"})  # fmt: skip
    assert wrong.status_code == 422
    made = scanner.post(f"/api/v1/controls/{ref}/reported", json=failed)
    assert made.status_code == 201, made.text
    report = made.json()["data"]
    assert report["status"] == "reported" and report["source"] == "Scanner as steward"

    shown = as_role("member").get(f"/api/v1/controls/{ref}/reported").json()["data"]
    assert [row["id"] for row in shown] == [report["id"]]
    waiting = as_role("assessor").get("/api/v1/reported").json()["data"]
    assert report["id"] in {row["id"] for row in waiting}
    # Neither a token nor the control's owner confirms it.
    assert scanner.post(f"/api/v1/reported/{report['id']}/confirm", json={}).status_code == 403
    confirmed = as_role("assessor").post(f"/api/v1/reported/{report['id']}/confirm", json={})
    assert confirmed.status_code == 200, confirmed.text
    issue = confirmed.json()["data"]["issue"]
    assert confirmed.json()["data"]["status"] == "confirmed" and issue["ref"].startswith("ISS-")
    raised = as_role("manager").get(f"/api/v1/issues/{issue['ref']}").json()["data"]
    assert raised["source_kind"] == "security_test" and raised["severity"] == "high"
    # As a failed test's issue is: the control's owners put it right, not the confirmer.
    assert {owner["account_id"] for owner in raised["owners"]} == {people.accounts["manager"]}
    again = as_role("assessor").post(f"/api/v1/reported/{report['id']}/confirm", json={})
    assert again.status_code == 409


def test_evidence_is_filed_and_a_report_can_be_set_aside(as_role: Clients, people: People) -> None:
    ref = _control(as_role, people)
    monitor = _token(as_role, "assessor", read_only=False)
    sent = monitor.post(f"/api/v1/controls/{ref}/reported", json={
        "kind": "evidence", "title": "Patch compliance report, November",
        "url": "https://monitor.example.org/patching/2026-11"}).json()["data"]  # fmt: skip
    filed = as_role("assessor").post(f"/api/v1/reported/{sent['id']}/confirm", json={})
    assert filed.status_code == 200, filed.text
    item = filed.json()["data"]["evidence"]
    assert item["ref"].startswith("EV-")
    linked = as_role("manager").get(f"/api/v1/evidence/{item['ref']}").json()["data"]
    assert linked["url"] == "https://monitor.example.org/patching/2026-11"

    noisy = monitor.post(f"/api/v1/controls/{ref}/reported", json={
        "kind": "result", "outcome": "partial",
        "title": "One host unreachable"}).json()["data"]  # fmt: skip
    assistant = as_role("assessor")
    assert assistant.post(f"/api/v1/reported/{noisy['id']}/set-aside", json={}).status_code == 422
    aside = assistant.post(f"/api/v1/reported/{noisy['id']}/set-aside",
                           json={"note": "The host was retired last week."})  # fmt: skip
    assert aside.status_code == 200 and aside.json()["data"]["status"] == "set_aside"
    assert aside.json()["data"]["issue"] is None


def test_standing_is_yes_or_no_with_reasons(as_role: Clients, people: People) -> None:
    from datetime import date, timedelta

    steward = as_role("steward")
    host = steward.post("/api/v1/third-parties", json={
        "name": "Halden Research Partners", "kind": "contractor",
        "org_unit_id": people.units["HALE"], "criticality": "moderate"}).json()["data"]  # fmt: skip
    purchasing = _token(as_role, "auditor")
    said = purchasing.get(f"/api/v1/standing/third-party/{host['ref']}")
    assert said.status_code == 200, said.text
    body = said.json()["data"]
    assert body["in_good_standing"] is False  # nothing yet says how closely to look at it
    assert [reason["code"] for reason in body["reasons"]] == ["not_tiered"]
    assert set(body) == {"kind", "ref", "name", "in_good_standing", "reasons", "as_of"}
    assert purchasing.get("/api/v1/standing/third-party/TP-9999").status_code == 404
    assert purchasing.get(f"/api/v1/standing/supplier/{host['ref']}").status_code == 404

    scope = steward.post("/api/v1/scopes", json={
        "name": "Clinic systems", "org_unit_id": people.units["HALE"]}).json()["data"]  # fmt: skip
    assert purchasing.get(f"/api/v1/standing/scope/{scope['ref']}").json()["data"][
        "in_good_standing"]  # fmt: skip
    control = _control(as_role, people)
    asked = steward.post("/api/v1/exceptions", json={
        "control": control, "justification": "Being replaced.",
        "expires_on": (date.today() + timedelta(days=60)).isoformat()})  # fmt: skip
    assert asked.status_code == 201, asked.text
    ref = asked.json()["data"]["ref"]
    pending = steward.get(f"/api/v1/standing/exception/{ref}").json()["data"]
    assert not pending["in_good_standing"]
    assert [reason["code"] for reason in pending["reasons"]] == ["requested"]
    assert as_role("member").get(f"/api/v1/standing/exception/{ref}").status_code == 404
    as_role("leader").post(f"/api/v1/exceptions/{ref}/decision", json={"approve": True})
    assert steward.get(f"/api/v1/standing/exception/{ref}").json()["data"]["in_good_standing"]


def test_a_supplier_is_in_good_standing_only_once_reviewed_and_approved(
    as_role: Clients, people: People, db: Any
) -> None:
    from riskwren.core.clock import utc_now
    from riskwren.db.models import ThirdParty
    from riskwren.thirdparty import lifecycle, reviews
    from tests.test_risks import who

    steward = as_role("steward")
    made = steward.post("/api/v1/third-parties", json={
        "name": "Coldline Service", "kind": "service_provider",
        "org_unit_id": people.units["HALE"], "criticality": "high"}).json()["data"]  # fmt: skip
    ref = made["ref"]
    tiered = steward.post(f"/api/v1/third-parties/{ref}/tiering", json={"answers": {
        "information": "confidential", "access": ["on_site"], "dependency": "slows"}})  # fmt: skip
    assert tiered.status_code in (200, 201), tiered.text
    asker = _token(as_role, "auditor")

    def codes() -> list[str]:
        found = asker.get(f"/api/v1/standing/third-party/{ref}").json()["data"]
        return [reason["code"] for reason in found["reasons"]]

    assert codes() == ["never_reviewed"]  # its tier asks for a review, and none is done
    keeper = who(db, people, "steward")
    with db.write(keeper.actor) as session:
        row = session.scalars(select(ThirdParty).where(ThirdParty.ref == ref)).one()
        review = reviews.start(session, keeper, row, {})
        review.status, review.conclusion, review.concluded_at = "concluded", "declined", utc_now()
        lifecycle.after_review(session, review)
    assert codes() == ["not_approved"]
    with db.write(keeper.actor) as session:
        row = session.scalars(select(ThirdParty).where(ThirdParty.ref == ref)).one()
        later = reviews.start(session, keeper, row, {})
        later.status, later.conclusion, later.concluded_at = "concluded", "approved", utc_now()
        lifecycle.after_review(session, later)
    assert codes() == []
    with db.write(keeper.actor) as session:
        row = session.scalars(select(ThirdParty).where(ThirdParty.ref == ref)).one()
        lifecycle.start(session, keeper, row, "Moving to another service.")
    assert codes() == ["offboarding"]
