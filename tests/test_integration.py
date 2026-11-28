"""Other systems (INT-02, INT-03): tokens that act as a role, shown once and kept as a digest;
and webhooks told of named events, signed, carrying references and never contents."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import timedelta

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.core.clock import clock_set_to, utc_now
from riskwren.db.models import ApiToken, Event, WebhookDelivery
from riskwren.integration import tokens, webhooks
from tests.conftest import Instance
from tests.people import People

Clients = Callable[[str | None], TestClient]


def _bearer(client: TestClient, raw: str) -> TestClient:
    """The same app, with no cookie and the token in the header."""
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token", None)
    client.headers["Authorization"] = f"Bearer {raw}"
    return client


def test_a_token_acts_as_its_role_and_only_that(
    as_role: Clients, people: People, instance: Instance
) -> None:
    admin = as_role("admin")
    assert as_role("manager").post("/api/v1/admin/tokens", json={
        "name": "x", "role": "auditor", "days": 30}).status_code == 403  # fmt: skip
    wrong = admin.post("/api/v1/admin/tokens", json={"name": "", "role": "admin", "days": 999})
    assert wrong.status_code == 422
    made = admin.post("/api/v1/admin/tokens", json={
        "name": "Ticketing", "role": "auditor", "read_only": True, "days": 30})  # fmt: skip
    assert made.status_code == 201, made.text
    raw = made.json()["meta"]["token"]
    assert raw.startswith("rwt_") and made.json()["data"]["prefix"] == raw[:10]
    with instance.db.read() as session:
        row = session.scalars(select(ApiToken)).one()
        assert row.digest == tokens.digest(raw) and raw not in json.dumps(
            tokens.view(row), default=str
        )
    listed = admin.get("/api/v1/admin/tokens").json()["data"]
    assert [item["state"] for item in listed] == ["active"]

    reader = _bearer(as_role(None), raw)
    assert reader.get("/api/v1/risks").status_code == 200  # an auditor reads everything
    assert reader.get("/api/v1/admin/tokens").status_code == 403  # and administers nothing
    refused = reader.post("/api/v1/risks", json={"name": "x"})
    assert refused.status_code == 403 and "only read" in refused.json()["detail"]
    assert _bearer(as_role(None), "rwt_not-a-token").get("/api/v1/risks").status_code == 401

    # A manager's token, limited to a unit, that may write: it acts, and the history says so.
    writer = admin.post("/api/v1/admin/tokens", json={
        "name": "Inventory sync", "role": "steward", "org_unit_id": people.units["HALE"],
        "read_only": False, "days": 1}).json()  # fmt: skip
    sync = _bearer(as_role(None), writer["meta"]["token"])
    hale, cancer = people.units["HALE"], people.units["CANCER"]
    made_system = sync.post("/api/v1/systems", json={
        "name": "Synced system", "kind": "application", "org_unit_id": hale})  # fmt: skip
    assert made_system.status_code == 201, made_system.text
    elsewhere = sync.post("/api/v1/systems", json={
        "name": "Not mine", "kind": "application", "org_unit_id": cancer})  # fmt: skip
    assert elsewhere.status_code == 403
    with instance.db.read() as session:
        event = session.scalars(
            select(Event).where(Event.subject_ref == made_system.json()["data"]["ref"])
        ).first()
        assert event is not None and event.actor_kind == "token"
        assert event.actor_label == "API token Inventory sync" and event.actor_id is None

    # Withdrawn, or past its date, it is no longer in force.
    token_id = writer["data"]["id"]
    assert admin.post(f"/api/v1/admin/tokens/{token_id}/revoke").status_code == 200
    assert sync.get("/api/v1/systems").status_code == 401
    later = utc_now() + timedelta(days=31)
    with clock_set_to(lambda: later):
        assert _bearer(as_role(None), raw).get("/api/v1/risks").status_code == 401


def test_webhooks_carry_references_signed(
    as_role: Clients, people: People, instance: Instance
) -> None:
    admin = as_role("admin")
    bad = admin.post("/api/v1/admin/webhooks", json={
        "name": "x", "url": "http://plain.example.org", "events": ["nothing.*"]})  # fmt: skip
    assert bad.status_code == 422
    made = admin.post("/api/v1/admin/webhooks", json={
        "name": "Ticketing", "url": "https://tickets.example.org/hook",
        "events": ["issue.*"]})  # fmt: skip
    assert made.status_code == 201, made.text
    secret = made.json()["meta"]["secret"]
    with instance.db.bookkeeping() as session:
        assert webhooks.queue(session) == 0  # the first time starts from now

    manager = as_role("manager")
    issue = manager.post("/api/v1/issues", json={
        "name": "Backups not tested", "severity": "high", "summary": "Never restored.",
        "org_unit_id": people.units["HALE"], "source_kind": "observation"})  # fmt: skip
    assert issue.status_code == 201, issue.text
    manager.post("/api/v1/risks", json={
        "name": "Not told", "cause": "c", "event": "e", "consequence": "q",
        "category": "operations", "org_unit_id": people.units["HALE"]})  # fmt: skip
    with instance.db.bookkeeping() as session:
        assert webhooks.queue(session, base_url="https://grc.example.org") == 1
        delivery = session.scalars(select(WebhookDelivery)).one()
        assert delivery.payload["record"] == {
            "type": "issue", "ref": issue.json()["data"]["ref"],
            "url": f"https://grc.example.org/issues/{issue.json()['data']['ref']}"}  # fmt: skip
        assert "Backups" not in json.dumps(delivery.payload)  # references, never contents

    received: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        received.append(request)
        return httpx.Response(500 if len(received) == 1 else 204)

    transport = httpx.MockTransport(answer)
    assert webhooks.send_due(instance.db, transport=transport) == {
        "webhooks_sent": 0, "webhooks_failed": 0}  # fmt: skip
    first = received[0]
    assert webhooks.verify(secret, first.headers[webhooks.SIGNATURE], first.content)
    assert not webhooks.verify("whsec_wrong", first.headers[webhooks.SIGNATURE], first.content)
    assert first.headers["X-RiskWren-Event"] == "issue.create"
    later = utc_now() + timedelta(minutes=2)
    with clock_set_to(lambda: later):
        assert webhooks.send_due(instance.db, transport=transport)["webhooks_sent"] == 1
    with instance.db.read() as session:
        sent = session.scalars(select(WebhookDelivery)).one()
        assert (sent.status, sent.attempts, sent.response_code) == ("sent", 2, 204)
    listed = admin.get("/api/v1/admin/webhooks").json()["data"]
    assert listed[0]["deliveries"][0]["status"] == "sent"
    assert as_role("manager").get("/api/v1/admin/webhooks").status_code == 403


def test_a_webhook_can_speak_as_a_ticket_or_a_chat_message(
    as_role: Clients, people: People, instance: Instance
) -> None:
    admin = as_role("admin")
    wrong = admin.post("/api/v1/admin/webhooks", json={
        "name": "x", "url": "https://chat.example.org/in", "events": ["issue.*"],
        "format": "email"})  # fmt: skip
    assert wrong.status_code == 422
    chat = admin.post("/api/v1/admin/webhooks", json={
        "name": "Team chat", "url": "https://chat.example.org/in", "events": ["issue.*"],
        "format": "chat"}).json()["data"]  # fmt: skip
    assert chat["format"] == "chat"
    ticket = admin.post("/api/v1/admin/webhooks", json={
        "name": "Service desk", "url": "https://desk.example.org/in",
        "events": ["issue.*"]}).json()["data"]  # fmt: skip
    assert ticket["format"] == "plain"
    changed = admin.patch(f"/api/v1/admin/webhooks/{ticket['id']}", json={"format": "ticket"})
    assert changed.status_code == 200 and changed.json()["data"]["format"] == "ticket"
    with instance.db.bookkeeping() as session:
        webhooks.queue(session)
    made = as_role("manager").post("/api/v1/issues", json={
        "name": "Backups not tested", "severity": "high", "summary": "Never restored.",
        "org_unit_id": people.units["HALE"], "source_kind": "observation"})  # fmt: skip
    made = made.json()["data"]
    with instance.db.bookkeeping() as session:
        assert webhooks.queue(session, base_url="https://grc.example.org") == 2
    bodies: dict[str, dict] = {}

    def answer(request: httpx.Request) -> httpx.Response:
        bodies[request.url.host] = json.loads(request.content)
        return httpx.Response(204)

    sent = webhooks.send_due(instance.db, transport=httpx.MockTransport(answer))
    assert sent["webhooks_sent"] == 2
    where = f"https://grc.example.org/issues/{made['ref']}"
    assert bodies["chat.example.org"] == {"text": f"RiskWren: issue.create: {made['ref']} {where}"}
    desk = bodies["desk.example.org"]
    assert desk["title"] == f"RiskWren: issue.create: {made['ref']}" and desk["link"] == where
    assert "Backups" not in json.dumps(bodies)  # still references, never contents
