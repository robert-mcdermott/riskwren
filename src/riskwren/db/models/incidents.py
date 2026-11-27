"""Incidents (INC-01 to INC-05): what happened, nearly happened, or worries someone.

Anyone signed in reports one in a short form; where the organization opens it, anyone may
report a concern through a link without a name, and follow it up with a code. Each report is
triaged: given a category, a severity, the records it concerns, and someone to handle it.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from riskwren.db.base import Base
from riskwren.db.models.compliance import SEVERITIES
from riskwren.db.models.inventory import RecordMixin, one_of
from riskwren.db.types import JsonType, UtcDateTime

INCIDENT_KINDS = ("incident", "near_miss", "concern")
INCIDENT_STATUSES = ("reported", "handling", "closed")
INCIDENT_SUBJECTS = (
    "system", "service", "information", "third_party", "process", "risk", "control", "scope",
)  # fmt: skip


class Incident(RecordMixin, Base):
    """Something that happened, nearly happened, or worries someone. Its reporter is the
    account that added it, or nobody, when it was reported without a name."""

    __tablename__ = "incident"
    __subject__ = "incident"
    # The digest of an anonymous reporter's code is kept out of the history: it is how they
    # come back, and nothing else needs it.
    __audit_redact__ = frozenset({"follow_up_hash"})

    kind: Mapped[str] = mapped_column(String(16), default="incident")
    status: Mapped[str] = mapped_column(String(16), default="reported")
    occurred_on: Mapped[date | None] = mapped_column(Date)
    location: Mapped[str | None] = mapped_column(String(200))
    anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    follow_up_hash: Mapped[str | None] = mapped_column(String(64))
    # Set at triage.
    category: Mapped[str | None] = mapped_column(String(40))
    severity: Mapped[str | None] = mapped_column(String(16))
    triaged_by: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    triaged_by_name: Mapped[str | None] = mapped_column(String(200))
    triaged_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    closure_note: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint(one_of("kind", INCIDENT_KINDS), name="kind"),
        CheckConstraint(one_of("status", INCIDENT_STATUSES), name="status"),
        CheckConstraint(one_of("severity", SEVERITIES), name="severity"),
        Index("ix_incident_org_unit_id", "org_unit_id"),
        Index("ix_incident_status", "status"),
        Index("ix_incident_follow_up_hash", "follow_up_hash", unique=True),
    )


class IncidentSubject(Base):
    """A record an incident concerns: a system, a service, information, a third party, a
    process, a risk, a control, or a scope."""

    __tablename__ = "incident_subject"
    __audit_parent__ = ("incident", "incident_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incident.id", ondelete="CASCADE"))
    subject_type: Mapped[str] = mapped_column(String(24))
    subject_id: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(one_of("subject_type", INCIDENT_SUBJECTS), name="subject_type"),
        UniqueConstraint("incident_id", "subject_type", "subject_id", name="uq_incident_subject"),
        Index("ix_incident_subject_subject", "subject_type", "subject_id"),
    )


class IncidentMessage(Base):
    """A note on an incident: shared with the person who reported it, or kept among those
    handling it."""

    __tablename__ = "incident_message"
    __audit_parent__ = ("incident", "incident_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incident.id", ondelete="CASCADE"))
    from_reporter: Mapped[bool] = mapped_column(Boolean, default=False)
    shared: Mapped[bool] = mapped_column(Boolean, default=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    author_name: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (Index("ix_incident_message_incident_id", "incident_id"),)


class IncidentMember(Base):
    """Someone named on a restricted case. A restricted case is known to those named on it
    (its members and its handlers), and to whoever reported it, and to nobody else."""

    __tablename__ = "incident_member"
    __audit_parent__ = ("incident", "incident_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incident.id", ondelete="CASCADE"))
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))

    __table_args__ = (
        UniqueConstraint("incident_id", "account_id", name="uq_incident_member"),
        Index("ix_incident_member_account_id", "account_id"),
    )


BREACH_CONCLUSIONS = ("undecided", "notify", "no_notification")


class BreachAssessment(Base):
    """Whether an incident involving protected information must be notified (INC-05): what
    was involved and when it was discovered, the factors weighed, any exception, and the
    conclusion, with the rules that apply. Never edited: a new one supersedes the last."""

    __tablename__ = "breach_assessment"
    __audit_parent__ = ("incident", "incident_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incident.id", ondelete="CASCADE"))
    discovered_at: Mapped[datetime] = mapped_column(UtcDateTime)
    # Keys of the protected_information vocabulary.
    information: Mapped[list[str]] = mapped_column(JsonType, default=list)
    people: Mapped[int | None] = mapped_column(Integer)
    most_in_one_state: Mapped[int | None] = mapped_column(Integer)
    # Rendered unusable, unreadable, or indecipherable to anyone not allowed to see it.
    secured: Mapped[bool] = mapped_column(Boolean, default=False)
    exception: Mapped[str | None] = mapped_column(String(40))
    # {factor: {"level": low | moderate | high, "note": str}}
    factors: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    conclusion: Mapped[str] = mapped_column(String(24), default="undecided")
    rationale: Mapped[str | None] = mapped_column(Text)
    # [{"key": ..., "name": ..., "days": ...}]: the rules that apply, with any of the
    # organization's own (a state's law, a contract) named and timed.
    regimes: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    assessed_by: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    assessed_by_name: Mapped[str] = mapped_column(String(200))
    assessed_at: Mapped[datetime] = mapped_column(UtcDateTime)
    superseded_by: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(one_of("conclusion", BREACH_CONCLUSIONS), name="conclusion"),
        Index("ix_breach_assessment_incident_id", "incident_id"),
    )


class BreachNotification(Base):
    """A notification made about an incident: to whom, under which rule, when, and how.
    Never edited."""

    __tablename__ = "breach_notification"
    __audit_parent__ = ("incident", "incident_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incident.id", ondelete="CASCADE"))
    # The rule it was made under, as the assessment names it: "hipaa", or "state:Washington".
    regime: Mapped[str] = mapped_column(String(120))
    duty: Mapped[str] = mapped_column(String(40))
    recipient: Mapped[str] = mapped_column(String(200))
    count: Mapped[int | None] = mapped_column(Integer)
    sent_on: Mapped[date] = mapped_column(Date)
    method: Mapped[str | None] = mapped_column(String(200))
    reference: Mapped[str | None] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    recorded_by_name: Mapped[str] = mapped_column(String(200))
    recorded_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (Index("ix_breach_notification_incident_id", "incident_id"),)
