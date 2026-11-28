"""Webhooks (INT-03): addresses an administrator registers are told of named events.

An event's name is the operation that made it, such as ``risk.assess``, ``issue.close``, or
``incident.report``; a webhook subscribes to whole families (``issue.*``) or to names. A
message carries references and never contents: the event, when, and the record's type and
reference. The receiver asks the API, with a token, for what it may see. A restricted record is
never named. Messages are queued from the history by a scheduled job, signed with the hook's
secret (HMAC-SHA256 over the timestamp and the body), and tried again with growing pauses.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid, NotFound, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import Event, Webhook, WebhookCursor, WebhookDelivery
from riskwren.events import audit

# The families of record a webhook may be told about, by the type the history names them by.
FAMILIES = {
    "risk": "Risks", "control": "Controls", "issue": "Issues", "exception": "Exceptions",
    "incident": "Incidents", "document": "Policies and other documents", "evidence": "Evidence",
    "assessment": "Assessments", "third_party": "Third parties",
    "third_party_review": "Due diligence", "system": "Systems", "process": "Processes",
    "scope": "Scopes", "agreement": "Agreements",
}  # fmt: skip
TRIES = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30), timedelta(hours=2),
         timedelta(hours=12))  # fmt: skip
KEEP = timedelta(days=30)
MOST_HOOKS = 20
FORMATS = ("plain", "ticket", "chat")
TIMEOUT = 10.0
SIGNATURE = "X-RiskWren-Signature"


def _require_admin(principal: Principal) -> None:
    if not principal.is_admin:
        raise PermissionDenied("Only an administrator registers webhooks.")


def view(row: Webhook, deliveries: list[WebhookDelivery] | None = None) -> dict[str, Any]:
    return {
        "id": row.id, "name": row.name, "url": row.url, "events": row.events, "active": row.active,
        "format": row.format,
        "created_by": row.created_by_name, "created_at": row.created_at,
        "deliveries": [
            {"id": d.id, "event": d.event, "status": d.status, "attempts": d.attempts,
             "response_code": d.response_code, "error": d.error, "created_at": d.created_at,
             "sent_at": d.sent_at, "record": d.payload.get("record")}
            for d in deliveries or []
        ],
    }  # fmt: skip


def list_(session: Session, principal: Principal) -> list[dict[str, Any]]:
    _require_admin(principal)
    out = []
    for row in session.scalars(select(Webhook).order_by(Webhook.id)):
        recent = session.scalars(
            select(WebhookDelivery)
            .where(WebhookDelivery.webhook_id == row.id)
            .order_by(WebhookDelivery.id.desc())
            .limit(10)
        ).all()
        out.append(view(row, list(recent)))
    return out


def _check(values: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    name = str(values.get("name") or "").strip()
    if not name or len(name) > 80:
        errors["name"] = "Name it for what receives it, in up to 80 characters."
    url = str(values.get("url") or "").strip()
    parts = urlsplit(url)
    if len(url) > 500 or parts.scheme != "https" or not parts.hostname or parts.username:
        errors["url"] = (
            "Give an address that starts with https://, without a name or password in it."
        )
    if values.get("format", "plain") not in FORMATS:
        errors["format"] = f"Use one of: {', '.join(FORMATS)}."
    events = values.get("events")
    if (
        not isinstance(events, list)
        or not events
        or not all(isinstance(e, str) and (e == "*" or e.split(".")[0] in FAMILIES) for e in events)
    ):
        errors["events"] = ("Choose what it is told of: * for everything, a family such as "
                            "issue.*, or an event such as issue.close.")  # fmt: skip
    return errors


def create(session: Session, principal: Principal, values: dict[str, Any]) -> tuple[Webhook, str]:
    """Register a webhook. Returns it with its secret, which is shown this once."""
    _require_admin(principal)
    errors = _check(values)
    if session.scalar(select(Webhook.id).order_by(Webhook.id.desc()).offset(MOST_HOOKS - 1)):
        errors["name"] = f"There can be no more than {MOST_HOOKS} webhooks."
    if errors:
        raise Invalid("The webhook was not registered.", errors)
    secret = "whsec_" + secrets.token_urlsafe(32)
    row = Webhook(name=str(values["name"]).strip(), url=str(values["url"]).strip(),
                  events=sorted(set(values["events"])), secret=secret, active=True,
                  format=values.get("format") or "plain",
                  created_by_name=principal.name, created_at=utc_now())  # fmt: skip
    with audit.operation(session, "webhook.create"):
        session.add(row)
        session.flush()
    return row, secret


def update(session: Session, principal: Principal, hook_id: int, values: dict[str, Any]) -> Webhook:
    _require_admin(principal)
    row = session.get(Webhook, hook_id)
    if row is None:
        raise NotFound("There is no such webhook.")
    merged = {"name": row.name, "url": row.url, "events": row.events, "format": row.format,
              **values}  # fmt: skip
    errors = _check(merged)
    if errors:
        raise Invalid("The webhook was not changed.", errors)
    with audit.operation(session, "webhook.edit"):
        row.name, row.url = str(merged["name"]).strip(), str(merged["url"]).strip()
        row.events = sorted(set(merged["events"]))
        row.format = merged["format"]
        if "active" in values:
            row.active = bool(values["active"])
        session.flush()
    return row


def remove(session: Session, principal: Principal, hook_id: int) -> None:
    _require_admin(principal)
    row = session.get(Webhook, hook_id)
    if row is None:
        raise NotFound("There is no such webhook.")
    with audit.operation(session, "webhook.remove"):
        session.delete(row)
        session.flush()


def wants(events: list[str], name: str) -> bool:
    family = name.split(".")[0]
    return "*" in events or name in events or f"{family}.*" in events


def _restricted(session: Session, event: Event) -> bool:
    """Whether the record is one that only those named on it may know of. A kind of record
    that is not known here is treated as one: nothing is named that cannot be checked."""
    from riskwren.inventory.registry import TYPES

    record_type = TYPES.get(event.subject_type)
    if record_type is None:
        return True
    row = session.get(record_type.model, event.subject_id)
    return bool(row is None or getattr(row, "restricted", False))


def _path(subject_type: str) -> str:
    from riskwren.inventory.registry import TYPES

    found = TYPES.get(subject_type)
    return found.path if found is not None else subject_type.replace("_", "-") + "s"


def queue(session: Session, *, base_url: str = "") -> int:
    """Turn what has happened since the last time into messages for the webhooks that want
    them. The first time, start from now: a new webhook is not told of the past."""
    import riskwren.api.app  # noqa: F401  (every kind of record registers itself on import)

    kept = session.get(WebhookCursor, 1)
    newest = session.scalar(select(Event.id).order_by(Event.id.desc()).limit(1)) or 0
    if kept is None:
        session.add(WebhookCursor(id=1, event_id=newest))
        return 0
    cursor = kept.event_id
    hooks = session.scalars(select(Webhook).where(Webhook.active.is_(True))).all()
    events = session.scalars(
        select(Event).where(Event.id > cursor, Event.subject_ref.is_not(None),
                            Event.parent_type.is_(None)).order_by(Event.id).limit(5000)
    ).all()  # fmt: skip
    queued = 0
    told: set[tuple[int, str, str]] = set()
    now = utc_now()
    for event in events:
        if event.subject_type not in FAMILIES or not hooks:
            continue
        name = (event.context or {}).get("op") or f"{event.subject_type}.{event.action}"
        if not name.startswith(f"{event.subject_type}."):
            name = f"{event.subject_type}.{name.split('.', 1)[-1]}"
        if _restricted(session, event):
            continue
        for hook in hooks:
            key = (hook.id, name, str(event.subject_ref))
            if key in told or not wants(hook.events, name):
                continue
            told.add(key)  # one message for one operation on one record
            payload = {
                "event": name, "at": event.at.isoformat(), "seq": event.id,
                "record": {"type": event.subject_type, "ref": event.subject_ref,
                           **({"url": f"{base_url}/{_path(event.subject_type)}/{event.subject_ref}"}
                              if base_url else {})},
            }  # fmt: skip
            session.add(WebhookDelivery(webhook_id=hook.id, event=name, event_seq=event.id,
                                        payload=payload, status="queued", attempts=0,
                                        next_attempt_at=now, created_at=now))  # fmt: skip
            queued += 1
    kept.event_id = events[-1].id if events else max(cursor, newest)
    return queued


def shape(hook_format: str, payload: dict[str, Any]) -> dict[str, Any]:
    """The message as the receiver reads it: still references only, never contents."""
    record = payload.get("record") or {}
    where = record.get("url") or ""
    said = payload["event"] + (f": {record['ref']}" if record.get("ref") else "")
    if hook_format == "chat":
        return {"text": f"RiskWren: {said}" + (f" {where}" if where else "")}
    if hook_format == "ticket":
        told = f"RiskWren recorded {payload['event']} at {payload['at']}." + (
            f" See {where}" if where else ""
        )
        return {"title": f"RiskWren: {said}", "description": told,
                "link": where or None, "event": payload["event"],
                "record": record or None}  # fmt: skip
    return payload


def sign(secret: str, timestamp: int, body: bytes) -> str:
    mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256)
    return f"t={timestamp},v1={mac.hexdigest()}"


def verify(secret: str, header: str, body: bytes, *, tolerance: int = 300) -> bool:
    """What a receiver does: check the signature and that the message is recent."""
    parts = dict(part.split("=", 1) for part in header.split(",") if "=" in part)
    try:
        timestamp = int(parts["t"])
    except (KeyError, ValueError):
        return False
    if abs(time.time() - timestamp) > tolerance:
        return False
    return hmac.compare_digest(sign(secret, timestamp, body), header)


def send_due(db: Database, *, transport: httpx.BaseTransport | None = None) -> dict[str, int]:
    """Send what is due, one try each, and keep how it went."""
    sent = failed = 0
    now = utc_now()
    with db.bookkeeping() as session:
        due = session.scalars(
            select(WebhookDelivery).where(WebhookDelivery.status == "queued",
                                          WebhookDelivery.next_attempt_at <= now)
            .order_by(WebhookDelivery.id).limit(200).with_for_update(skip_locked=True)
        ).all()  # fmt: skip
        hooks = {row.id: row for row in session.scalars(select(Webhook))}
        with httpx.Client(timeout=TIMEOUT, transport=transport, follow_redirects=False) as client:
            for delivery in due:
                hook = hooks.get(delivery.webhook_id)
                if hook is None or not hook.active:
                    delivery.status = "failed"
                    delivery.error = "The webhook was paused or removed."
                    continue
                body = json.dumps(shape(hook.format, delivery.payload),
                                  separators=(",", ":")).encode()  # fmt: skip
                stamp = int(time.time())
                delivery.attempts += 1
                try:
                    answer = client.post(hook.url, content=body, headers={
                        "Content-Type": "application/json", "User-Agent": "RiskWren-Webhook",
                        SIGNATURE: sign(hook.secret, stamp, body),
                        "X-RiskWren-Event": delivery.event,
                        "X-RiskWren-Delivery": str(delivery.id)})  # fmt: skip
                    delivery.response_code = answer.status_code
                    ok = 200 <= answer.status_code < 300
                    delivery.error = None if ok else f"The address answered {answer.status_code}."
                except httpx.HTTPError as exc:
                    ok = False
                    delivery.error = f"{type(exc).__name__}: {exc}"[:500]
                if ok:
                    delivery.status, delivery.sent_at = "sent", utc_now()
                    sent += 1
                elif delivery.attempts > len(TRIES):
                    delivery.status = "failed"
                    failed += 1
                else:
                    delivery.next_attempt_at = utc_now() + TRIES[delivery.attempts - 1]
        session.execute(delete(WebhookDelivery).where(WebhookDelivery.created_at < now - KEEP))
    return {"webhooks_sent": sent, "webhooks_failed": failed}


def test(session: Session, principal: Principal, hook_id: int) -> WebhookDelivery:
    """Queue a message that says only that this is a test, to check the address."""
    _require_admin(principal)
    row = session.get(Webhook, hook_id)
    if row is None:
        raise NotFound("There is no such webhook.")
    now = utc_now()
    delivery = WebhookDelivery(webhook_id=row.id, event="webhook.test", payload={
        "event": "webhook.test", "at": now.isoformat(), "record": None}, status="queued",
        attempts=0, next_attempt_at=now, created_at=now)  # fmt: skip
    session.add(delivery)
    session.flush()
    return delivery
