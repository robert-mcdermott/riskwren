"""Other systems: tokens that act as a role (INT-02), and webhooks that tell an address of
named events, signed (INT-03)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from riskwren.db.base import Base
from riskwren.db.types import JsonType, UtcDateTime


class ApiToken(Base):
    """A token another system sends as ``Authorization: Bearer``. It acts as a role, never as
    a person; only a digest of it is kept, and it is shown once, when it is made."""

    __tablename__ = "api_token"
    __audit_redact__ = ("digest",)
    __audit_skip__ = frozenset({"last_used_at"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    prefix: Mapped[str] = mapped_column(String(16))  # the first characters, to tell it apart
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    role: Mapped[str] = mapped_column(String(24))
    org_unit_id: Mapped[int | None] = mapped_column(ForeignKey("org_unit.id"))
    read_only: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime)
    created_by: Mapped[int | None] = mapped_column(Integer)
    created_by_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    revoked_by_name: Mapped[str | None] = mapped_column(String(200))
    # Bookkeeping, not history: when it was last used, written without an event.
    last_used_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class Webhook(Base):
    """An address told of named events, each message signed with the hook's secret."""

    __tablename__ = "webhook"
    __audit_redact__ = ("secret",)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    url: Mapped[str] = mapped_column(String(500))
    events: Mapped[list[str]] = mapped_column(JsonType, default=list)
    secret: Mapped[str] = mapped_column(String(80))
    # How a message is shaped: plain (RiskWren's own), ticket (a title, a description, and a
    # link, for a ticketing system), or chat (a line of text, for a chat channel).
    format: Mapped[str] = mapped_column(String(16), default="plain", server_default="plain")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)


class WebhookDelivery(Base):
    """One message to one webhook: what it carries, and how sending it went. Kept for a
    time, outside the history."""

    __tablename__ = "webhook_delivery"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    webhook_id: Mapped[int] = mapped_column(ForeignKey("webhook.id", ondelete="CASCADE"))
    event: Mapped[str] = mapped_column(String(60))
    event_seq: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType)
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued, sent, failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(UtcDateTime)
    response_code: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    sent_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    __table_args__ = (Index("ix_webhook_delivery_due", "status", "next_attempt_at"),)


class WebhookCursor(Base):
    """How far through the history webhooks have been queued: bookkeeping, outside it."""

    __tablename__ = "webhook_cursor"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(Integer)


class ReportedResult(Base):
    """What another system says of a control: a check it ran, or a piece of evidence. Shown
    on the control at once, as its source's; it counts only once a person confirms it, which
    raises an issue for a failure or files the evidence, and it never replaces a person's."""

    __tablename__ = "reported_result"
    __audit_parent__ = ("control", "control_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    control_id: Mapped[int] = mapped_column(ForeignKey("control.id", ondelete="CASCADE"))
    scope_id: Mapped[int | None] = mapped_column(ForeignKey("scope.id"))
    kind: Mapped[str] = mapped_column(String(16))  # result, evidence
    outcome: Mapped[str | None] = mapped_column(String(16))  # passed, partial, failed
    title: Mapped[str] = mapped_column(String(300))
    detail: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(500))
    observed_at: Mapped[datetime] = mapped_column(UtcDateTime)
    source: Mapped[str] = mapped_column(String(120))  # the token's name
    reported_at: Mapped[datetime] = mapped_column(UtcDateTime)
    status: Mapped[str] = mapped_column(String(16), default="reported")
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    decided_by_name: Mapped[str | None] = mapped_column(String(200))
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    decision_note: Mapped[str | None] = mapped_column(Text)
    issue_id: Mapped[int | None] = mapped_column(Integer)
    evidence_id: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (Index("ix_reported_result_control", "control_id", "status"),)
