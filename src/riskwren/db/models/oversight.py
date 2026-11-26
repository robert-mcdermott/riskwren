"""Questionnaires: versioned documents of questions, and the answers given to them."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
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
