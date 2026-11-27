"""Breach assessment (INC-05) and privacy impact assessments (INC-07)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta

from fastapi.testclient import TestClient

from riskwren.core.clock import frozen_at, utc_now
from riskwren.db.engine import Database
from riskwren.inventory import records
from riskwren.inventory.registry import PROCESS, SYSTEM
from tests.people import People
from tests.test_incidents import _report
from tests.test_risks import who

Clients = Callable[[str | None], TestClient]


def _fields(response: object) -> set[str]:
    return {error["location"][0] for error in response.json()["errors"]}  # type: ignore[attr-defined]


def _handled(as_role: Clients, people: People) -> str:
    ref = _report(as_role("member"), name="Discharge letters emailed to the wrong patients")["ref"]
    as_role("assessor").post(f"/api/v1/incidents/{ref}/triage", json={
        "category": "privacy", "severity": "high",
        "handler_id": people.accounts["steward"]})  # fmt: skip
    return ref


def test_an_assessment_starts_the_clock_and_each_notification_is_recorded(
    as_role: Clients, people: People
) -> None:
    ref = _handled(as_role, people)
    steward = as_role("steward")
    empty = steward.get(f"/api/v1/incidents/{ref}/breach").json()["data"]
    assert empty["assessment"] is None and empty["can_assess"] is True
    assert {regime["key"] for regime in empty["choices"]["regimes"]} >= {"hipaa", "state", "dfars"}
    # Its reporter does not see the handling; its unit's leader reads it and does not assess.
    assert as_role("member").get(f"/api/v1/incidents/{ref}/breach").status_code == 404
    assert as_role("leader").get(f"/api/v1/incidents/{ref}/breach").status_code == 200
    found_on = utc_now().date() - timedelta(days=10)
    body = {
        "discovered_at": f"{found_on.isoformat()}T09:00:00Z",
        "information": ["health"], "people": 640, "most_in_one_state": 600,
        "factors": {name: {"level": "high"} for name in ("nature", "recipient", "acquired",
                                                         "mitigated")},
        "conclusion": "notify",
        "rationale": "Names, diagnoses, and discharge dates went to 640 other patients.",
        "regimes": [{"key": "hipaa"}, {"key": "state", "name": "Washington", "days": 30}],
    }  # fmt: skip
    assert as_role("leader").post(f"/api/v1/incidents/{ref}/breach", json=body).status_code == 403
    done = steward.post(f"/api/v1/incidents/{ref}/breach", json=body)
    assert done.status_code == 200, done.text
    data = done.json()["data"]
    assert data["suggestion"]["key"] == "presumed"
    due = {(duty["regime"], duty["duty"]): duty for duty in data["obligations"]}
    assert set(due) == {("hipaa", "individuals"), ("hipaa", "secretary"), ("hipaa", "media"),
                        ("state:Washington", "residents")}  # fmt: skip

    def day(duty: dict) -> date:
        return datetime.fromisoformat(duty["due_at"]).date()

    assert day(due[("hipaa", "individuals")]) == found_on + timedelta(days=60)
    assert day(due[("hipaa", "secretary")]) == found_on + timedelta(days=60)
    assert day(due[("state:Washington", "residents")]) == found_on + timedelta(days=30)
    assert not any(duty["overdue"] or duty["done"] for duty in due.values())
    # Whoever handles it finds each notification waiting, soonest first.
    owed = steward.get("/api/v1/home").json()["data"]["items"]
    assert sum(1 for item in owed if item["kind"] == "incident_notify") == 4

    letter = {"regime": "hipaa", "duty": "individuals", "count": 640,
              "recipient": "640 patients, by first-class mail", "method": "First-class mail",
              "sent_on": utc_now().date().isoformat()}  # fmt: skip
    sent = steward.post(f"/api/v1/incidents/{ref}/notifications", json=letter)
    assert sent.status_code == 201, sent.text
    after = {(d["regime"], d["duty"]): d for d in sent.json()["data"]["obligations"]}
    assert after[("hipaa", "individuals")]["done"] is True
    wrong = steward.post(f"/api/v1/incidents/{ref}/notifications", json={
        "regime": "ftc_safeguards", "duty": "ftc", "recipient": "FTC",
        "sent_on": utc_now().date().isoformat()})  # fmt: skip
    assert wrong.status_code == 422 and "regime" in _fields(wrong)

    # Fewer than 500: the Secretary is told within 60 days after the end of the year, and
    # the media not at all. The earlier assessment is kept, superseded.
    fewer = {**body, "people": 120, "most_in_one_state": 120}
    again = steward.post(f"/api/v1/incidents/{ref}/breach", json=fewer).json()["data"]
    due = {(duty["regime"], duty["duty"]): duty for duty in again["obligations"]}
    assert ("hipaa", "media") not in due
    assert day(due[("hipaa", "secretary")]) == date(found_on.year, 12, 31) + timedelta(days=60)
    assert len(again["earlier"]) == 1
    events = as_role("manager").get(f"/api/v1/incidents/{ref}/history").json()["data"]
    titles = " ".join(str(event.get("title")) for event in events)
    assert "Assessed whether it must be notified: it must be notified" in titles
    assert "Recorded a notification to 640 patients" in titles


def test_what_an_assessment_must_say(as_role: Clients, people: People) -> None:
    ref = _handled(as_role, people)
    steward = as_role("steward")
    tomorrow = (utc_now() + timedelta(days=1)).isoformat()
    bad = steward.post(f"/api/v1/incidents/{ref}/breach", json={
        "discovered_at": tomorrow, "information": ["gossip"], "people": 5,
        "most_in_one_state": 9, "exception": "luck", "conclusion": "notify",
        "regimes": [{"key": "state", "name": "Ohio"}]})  # fmt: skip
    assert bad.status_code == 422
    assert _fields(bad) >= {"discovered_at", "information", "most_in_one_state", "exception",
                            "rationale", "regimes"}  # fmt: skip
    # Secured information is not a breach of unsecured information: nothing is due.
    secured = steward.post(f"/api/v1/incidents/{ref}/breach", json={
        "discovered_at": utc_now().date().isoformat(), "information": ["health"], "people": 3000,
        "secured": True, "conclusion": "no_notification",
        "rationale": "The laptop's disk was encrypted, and the key was not with it.",
        "regimes": [{"key": "hipaa"}]})  # fmt: skip
    data = secured.json()["data"]
    assert data["suggestion"]["key"] == "secured" and data["obligations"] == []
    # Undecided, the clock still runs: what would be due if it is a breach is shown.
    undecided = steward.post(f"/api/v1/incidents/{ref}/breach", json={
        "discovered_at": (utc_now() - timedelta(hours=2)).isoformat(),
        "information": ["controlled"], "regimes": [{"key": "dfars"}]})  # fmt: skip
    duty = undecided.json()["data"]["obligations"][0]
    assert duty["if_breach"] is True and duty["within"] == "72 hours"
    hours = datetime.fromisoformat(duty["due_at"]) - (utc_now() - timedelta(hours=2))
    assert timedelta(hours=71) < hours <= timedelta(hours=72)


# --- Privacy impact assessments -----------------------------------------------------------

ANSWERS = {
    "information": ["contact", "health"], "whose": ["patients"], "how_many": 4000,
    "purpose": "Booking and reminding patients of their infusion appointments.",
    "basis": "care", "least": True, "shared": True,
    "shared_with": "The reminder service sends the texts.", "agreement": "none",
    "access": True, "retention": "Seven years, then deleted.", "deidentified": "no",
    "harms": "Someone could learn that a person is being treated.",
    "reduced": "Only the clinic's schedulers can see the list.",
}  # fmt: skip


def test_a_privacy_impact_assessment_is_asked_for_answered_and_reviewed(
    as_role: Clients, people: People, db: Database
) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        booking = records.create(session, steward, SYSTEM, {
            "name": "Infusion booking", "kind": "application", "criticality": "high",
            "data_class": "restricted", "org_unit_id": people.units["HALE"]})  # fmt: skip
        records.create(session, steward, PROCESS, {
            "name": "Ordering supplies", "kind": "administrative", "criticality": "low",
            "data_class": "internal", "org_unit_id": people.units["HALE"]})  # fmt: skip
        booking_ref = booking.ref
    seen = as_role("member").get("/api/v1/privacy").json()["data"]
    assert [row["ref"] for row in seen["rows"]] == [booking_ref]
    assert seen["rows"][0]["state"] == "never" and seen["classes"] == ["restricted"]

    manager = as_role("manager")
    started = manager.post("/api/v1/campaigns", json={
        "kind": "privacy_impact", "name": "Privacy impact assessments, 2027",
        "due_on": (utc_now().date() + timedelta(days=30)).isoformat()})  # fmt: skip
    assert started.status_code == 201, started.text
    campaign = manager.get(f"/api/v1/campaigns/{started.json()['data']['ref']}").json()["data"]
    assert [item["subject"]["ref"] for item in campaign["items"]] == [booking_ref]
    item_id = campaign["items"][0]["id"]
    answered = as_role("steward").post(f"/api/v1/campaign-items/{item_id}/answer",
                                       json={"answers": ANSWERS})  # fmt: skip
    assert answered.status_code == 200, answered.text
    assert answered.json()["data"]["outcome"] == "concerns"
    told = as_role("assessor").get("/api/v1/notices").json()["data"]
    assert any("with concerns" in notice["text"] for notice in told)

    record = as_role("assessor").get(f"/api/v1/systems/{booking_ref}").json()["data"]
    impact = record["privacy_impact"]
    assert impact["state"] == "to_review" and impact["can_review"] is True
    assert any("nothing covering it" in each for each in impact["last"]["concerns"])
    assert as_role("member").post(f"/api/v1/privacy/reviews/{item_id}", json={}).status_code == 403
    note = "A business associate agreement is being drawn up with the reminder service."
    reviewed = as_role("assessor").post(f"/api/v1/privacy/reviews/{item_id}", json={"note": note})
    assert reviewed.status_code == 200 and reviewed.json()["data"]["outcome"] == "reviewed"
    impact = as_role("member").get(f"/api/v1/systems/{booking_ref}").json()["data"]
    assert impact["privacy_impact"]["state"] == "current"
    # A campaign does not ask again about one that is current; after the months the program
    # sets, it is due again.
    preview = manager.post("/api/v1/campaigns/preview", json={
        "kind": "privacy_impact", "name": "Again",
        "due_on": (utc_now().date() + timedelta(days=30)).isoformat()}).json()["data"]  # fmt: skip
    assert booking_ref not in str(preview)
    later = datetime.combine(utc_now().date() + timedelta(days=37 * 31), time(12), tzinfo=UTC)
    with frozen_at(later):
        again = as_role("member").get(f"/api/v1/systems/{booking_ref}").json()["data"]
        assert again["privacy_impact"]["state"] == "due"


def test_the_privacy_and_breach_frameworks_load(as_role: Clients, people: People) -> None:
    manager = as_role("manager")
    for key, code in (("hipaa-breach", "164.404(b)"), ("nist-privacy", "ID.IM-P1")):
        loaded = manager.post("/api/v1/framework-packs", json={"key": key})
        assert loaded.status_code in (200, 201), loaded.text
        found = manager.get(f"/api/v1/frameworks/{key}/requirement", params={"code": code})
        assert found.status_code == 200, (key, found.text)
