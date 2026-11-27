"""Questionnaires: versioned documents of questions, and the answers given to them. Campaigns:
a set of people asked to do one thing by a date."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
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
from riskwren.db.types import JsonType, UtcDateTime

QUESTIONNAIRE_STATUSES = ("active", "retired")
QUESTIONNAIRE_ORIGINS = ("pack", "local")
RESPONSE_STATUSES = ("draft", "submitted")


class Questionnaire(Base):
    """A set of questions to ask, by name. What it asks is in its versions."""

    __tablename__ = "questionnaire"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(60), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(String(24), default="other")
    status: Mapped[str] = mapped_column(String(16), default="active")
    origin: Mapped[str] = mapped_column(String(16), default="local")
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint("status IN ('active', 'retired')", name="status"),
        CheckConstraint("origin IN ('pack', 'local')", name="origin"),
    )


class QuestionnaireVersion(Base):
    """What a questionnaire asked from one publication to the next. Never changed: an answer
    is always read against the version it was given to."""

    __tablename__ = "questionnaire_version"
    __audit_parent__ = ("questionnaire", "questionnaire_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    questionnaire_id: Mapped[int] = mapped_column(ForeignKey("questionnaire.id"))
    number: Mapped[int] = mapped_column(Integer)
    document: Mapped[dict[str, Any]] = mapped_column(JsonType)
    note: Mapped[str | None] = mapped_column(Text)
    published_by: Mapped[int | None] = mapped_column(Integer)
    published_by_name: Mapped[str] = mapped_column(String(200))
    published_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (UniqueConstraint("questionnaire_id", "number"),)


class Response(Base):
    """One person's answers to one version of a questionnaire, about a record or about
    nothing in particular."""

    __tablename__ = "response"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("questionnaire_version.id"))
    subject_type: Mapped[str | None] = mapped_column(String(24))
    subject_id: Mapped[int | None] = mapped_column(Integer)
    # Who answered: an account, or a contact at a third party answering through a link.
    account_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("third_party_contact.id"))
    account_name: Mapped[str] = mapped_column(String(200))
    answers: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    started_at: Mapped[datetime] = mapped_column(UtcDateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'submitted')", name="status"),
        Index("ix_response_subject", "subject_type", "subject_id"),
        Index("ix_response_account_id", "account_id"),
    )


CAMPAIGN_KINDS = (
    "attestation", "self_assessment", "completeness", "profile", "evidence", "acknowledgment",
)  # fmt: skip


class Campaign(Base):
    """A request to a set of people to do one thing by a date (OVS-04)."""

    __tablename__ = "campaign"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref: Mapped[str] = mapped_column(String(24), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(24))
    # The questionnaire and the version of it that everyone in the campaign is asked.
    questionnaire_id: Mapped[int | None] = mapped_column(ForeignKey("questionnaire.id"))
    version_number: Mapped[int | None] = mapped_column(Integer)
    # Who is asked: about what lies in a unit and beneath it, or what a scope uses.
    org_unit_id: Mapped[int | None] = mapped_column(ForeignKey("org_unit.id"))
    scope_id: Mapped[int | None] = mapped_column(ForeignKey("scope.id"))
    wanted: Mapped[str | None] = mapped_column(Text)  # for evidence: what is asked for
    # For an acknowledgment: the document people are asked to say they have read.
    document_id: Mapped[int | None] = mapped_column(ForeignKey("policy_document.id"))
    due_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_by: Mapped[int | None] = mapped_column(Integer)
    created_by_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    closed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    closed_by_name: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        CheckConstraint("status IN ('open', 'closed', 'cancelled')", name="status"),
        CheckConstraint(
            "kind IN ('attestation', 'self_assessment', 'completeness', 'profile', 'evidence', "
            "'acknowledgment')",
            name="kind",
        ),
    )


class CampaignItem(Base):
    """One thing one person is asked for in a campaign: about a control, a risk, a system, or
    a unit. Its subject's name is kept as it was when asked."""

    __tablename__ = "campaign_item"
    __audit_parent__ = ("campaign", "campaign_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaign.id", ondelete="CASCADE"))
    subject_type: Mapped[str] = mapped_column(String(24))
    subject_id: Mapped[int] = mapped_column(Integer)
    subject_ref: Mapped[str | None] = mapped_column(String(24))
    subject_name: Mapped[str] = mapped_column(String(200))
    org_unit_id: Mapped[int | None] = mapped_column(ForeignKey("org_unit.id"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    account_name: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    response_id: Mapped[int | None] = mapped_column(ForeignKey("response.id"))
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence.id"))
    outcome: Mapped[str | None] = mapped_column(String(40))
    note: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    completed_by_name: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'done', 'excused')", name="status"),
        # One item for each thing asked about, and for each person: an acknowledgment asks
        # everyone about the same document.
        UniqueConstraint("campaign_id", "subject_type", "subject_id", "account_id"),
        Index("ix_campaign_item_account_id", "account_id", "status"),
    )
