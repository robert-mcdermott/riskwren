"""Incidents (INC-01 to INC-03): what happened, nearly happened, or worries someone.

Anyone signed in reports one in a short form; where the organization opens it, anyone may
report a concern through a link without a name, and follow it up with a code. Each report is
triaged: given a category, a severity, the records it concerns, and someone to handle it.
"""

from __future__ import annotations

from datetime import date, datetime

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
from riskwren.db.types import UtcDateTime

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
