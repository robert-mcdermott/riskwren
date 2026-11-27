"""Third parties as a program (TPR): how much is at stake with each, and what is known.

A third party and its services are records of the inventory (``inventory.py``). What this
module holds is what is learned about them: each tiering, a judgment by a named person; the
people there who can be asked; due diligence reviews; and the links through which someone
without an account answers.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from riskwren.db.base import Base
from riskwren.db.models.inventory import RecordMixin, one_of
from riskwren.db.types import JsonType, UtcDateTime

REVIEW_STATUSES = ("draft", "sent", "answered", "concluded", "cancelled")


class TierAssessment(Base):
    """A tiering: the answers given, what the inventory said, the tier the program's rules
    gave and why, and the tier the person recorded. Never edited: tiering again supersedes
    it, and it stays."""

    __tablename__ = "tier_assessment"
    __audit_parent__ = ("third_party", "third_party_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    third_party_id: Mapped[int] = mapped_column(ForeignKey("third_party.id"))
    answers: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    # What the inventory said at the time: the most sensitive information, the most
    # critical work that relies on it, and the systems its services reach.
    facts: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    questionnaire_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("questionnaire_version.id")
    )
    suggested: Mapped[str] = mapped_column(String(24))
    reasons: Mapped[list[str]] = mapped_column(JsonType, default=list)
    tier: Mapped[str] = mapped_column(String(24))
    rationale: Mapped[str | None] = mapped_column(Text)  # needed when tier differs
    assessed_by: Mapped[int | None] = mapped_column(Integer)
    assessed_by_name: Mapped[str] = mapped_column(String(200))
    assessed_at: Mapped[datetime] = mapped_column(UtcDateTime)
    superseded_by: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (Index("ix_tier_assessment_third_party_id", "third_party_id"),)


class ThirdPartyContact(Base):
    """A person at a third party who can be asked: not an account, and never signed in."""

    __tablename__ = "third_party_contact"
    __audit_parent__ = ("third_party", "third_party_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    third_party_id: Mapped[int] = mapped_column(ForeignKey("third_party.id"))
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint("status IN ('active', 'left')", name="status"),
        Index("ix_third_party_contact_third_party_id", "third_party_id"),
    )


class ThirdPartyReview(RecordMixin, Base):
    """Due diligence: a questionnaire sent to a third party's contact, answered, reviewed,
    and concluded (TPR-03)."""

    __tablename__ = "third_party_review"
    __subject__ = "third_party_review"

    third_party_id: Mapped[int] = mapped_column(ForeignKey("third_party.id"))
    tier: Mapped[str | None] = mapped_column(String(24))  # as it was when the review began
    questionnaire_id: Mapped[int] = mapped_column(ForeignKey("questionnaire.id"))
    version_number: Mapped[int | None] = mapped_column(Integer)  # set when first sent
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("third_party_contact.id"))
    due_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    sent_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    answered_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    conclusion: Mapped[str | None] = mapped_column(String(16))
    conclusion_note: Mapped[str | None] = mapped_column(Text)
    concluded_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    concluded_by: Mapped[int | None] = mapped_column(Integer)
    concluded_by_name: Mapped[str | None] = mapped_column(String(200))
    cancelled_note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(one_of("status", REVIEW_STATUSES), name="status"),
        CheckConstraint(
            "conclusion IS NULL OR conclusion IN ('approved', 'conditions', 'declined')",
            name="conclusion",
        ),
        Index("ix_third_party_review_org_unit_id", "org_unit_id"),
        Index("ix_third_party_review_third_party_id", "third_party_id"),
    )


class RespondentLink(Base):
    """A link given to someone without an account: the digest of its token, what it reaches,
    for whom, and until when. The token itself is never kept."""

    __tablename__ = "respondent_link"
    __audit_parent__ = ("@subject_type", "subject_id")
    __audit_skip__ = frozenset({"token_hash", "last_used_at", "used_count"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    purpose: Mapped[str] = mapped_column(String(24))
    subject_type: Mapped[str] = mapped_column(String(24))
    subject_id: Mapped[int] = mapped_column(Integer)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("third_party_contact.id"))
    created_by: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime)
    last_used_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    __table_args__ = (Index("ix_respondent_link_subject", "subject_type", "subject_id"),)


class AssuranceReview(Base):
    """A careful reading of a report or certificate about a third party: what it is, what it
    covers and does not, what it found, and whether it can be relied on. Never edited:
    reviewing again supersedes it, and it stays (TPR-04)."""

    __tablename__ = "assurance_review"
    __audit_parent__ = ("third_party", "third_party_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id"))
    third_party_id: Mapped[int] = mapped_column(ForeignKey("third_party.id"))
    kind: Mapped[str] = mapped_column(String(24))
    issuer: Mapped[str | None] = mapped_column(String(200))  # the auditor or certifying body
    opinion: Mapped[str] = mapped_column(String(16), default="none")
    services: Mapped[list[int]] = mapped_column(JsonType, default=list)  # those it covers
    carve_outs: Mapped[str | None] = mapped_column(Text)  # parts left to others it uses
    exceptions: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    reliance: Mapped[str] = mapped_column(String(16))
    note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[int | None] = mapped_column(Integer)
    reviewed_by_name: Mapped[str] = mapped_column(String(200))
    reviewed_at: Mapped[datetime] = mapped_column(UtcDateTime)
    superseded_by: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint("reliance IN ('relies', 'partly', 'cannot')", name="reliance"),
        CheckConstraint(
            "opinion IN ('unqualified', 'qualified', 'adverse', 'none')", name="opinion"
        ),
        Index("ix_assurance_review_evidence_id", "evidence_id"),
        Index("ix_assurance_review_third_party_id", "third_party_id"),
    )


class AssuranceResponsibility(Base):
    """What a report leaves to the organization to do itself (in a SOC report, a
    complementary user entity control), and the control here that does it."""

    __tablename__ = "assurance_responsibility"
    __audit_parent__ = ("third_party", "third_party_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("assurance_review.id"))
    third_party_id: Mapped[int] = mapped_column(ForeignKey("third_party.id"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text)
    control_id: Mapped[int | None] = mapped_column(ForeignKey("control.id"))
    status: Mapped[str] = mapped_column(String(16))

    __table_args__ = (
        CheckConstraint("status IN ('in_place', 'not_in_place', 'not_applicable')", name="status"),
        Index("ix_assurance_responsibility_review_id", "review_id"),
        Index("ix_assurance_responsibility_control_id", "control_id"),
    )


class Offboarding(Base):
    """Ending a relationship: the steps to record, each with who and when, until the third
    party is retired (TPR-09)."""

    __tablename__ = "offboarding"
    __audit_parent__ = ("third_party", "third_party_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    third_party_id: Mapped[int] = mapped_column(ForeignKey("third_party.id"))
    reason: Mapped[str] = mapped_column(Text)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    status: Mapped[str] = mapped_column(String(16), default="open")
    started_by_name: Mapped[str] = mapped_column(String(200))
    started_at: Mapped[datetime] = mapped_column(UtcDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint("status IN ('open', 'done', 'cancelled')", name="status"),
        Index("ix_offboarding_third_party_id", "third_party_id"),
    )
