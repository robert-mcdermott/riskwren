"""Resilience (RES): what each process cannot afford to lose, and what its dependencies can
deliver.

A business impact analysis is a judgment by a named person about one process, never edited:
a new one supersedes it. A recovery capability is what a system or a service can actually be
restored within, and how much information it can lose, with what that rests on.

A continuity plan is a document of the kind "plan" (versioned, approved, and reviewed as any
document is); what it restores and each exercise of it are kept here (RES-03, RES-04).
"""

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
from riskwren.db.models.inventory import one_of
from riskwren.db.types import JsonType, UtcDateTime

CAPABLE = ("system", "service")
EXERCISE_KINDS = ("tabletop", "walkthrough", "simulation", "full")
EXERCISE_RESULTS = ("met", "partly", "not_met")


class ImpactAnalysis(Base):
    """For one process: how much its loss hurts as time goes on, how soon it must be back,
    how much information it can lose, and the least it needs to run (RES-01)."""

    __tablename__ = "impact_analysis"
    __audit_parent__ = ("process", "process_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("process.id"))
    impacts: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    recovery_hours: Mapped[int] = mapped_column(Integer)  # how soon it must be back
    data_loss_hours: Mapped[int] = mapped_column(Integer)  # how much information may be lost
    minimum: Mapped[str | None] = mapped_column(Text)  # the least it needs to run
    note: Mapped[str | None] = mapped_column(Text)
    analysed_by: Mapped[int | None] = mapped_column(Integer)
    analysed_by_name: Mapped[str] = mapped_column(String(200))
    analysed_at: Mapped[datetime] = mapped_column(UtcDateTime)
    superseded_by: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (Index("ix_impact_analysis_process_id", "process_id"),)


class RecoveryCapability(Base):
    """What a system or service can be restored within, and how much it can lose."""

    __tablename__ = "recovery_capability"
    __audit_parent__ = ("@subject_type", "subject_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(24))
    subject_id: Mapped[int] = mapped_column(Integer)
    recovery_hours: Mapped[int] = mapped_column(Integer)
    data_loss_hours: Mapped[int] = mapped_column(Integer)
    basis: Mapped[str] = mapped_column(Text)  # what it rests on: a tested restore, a contract
    recorded_by: Mapped[int | None] = mapped_column(Integer)
    recorded_by_name: Mapped[str] = mapped_column(String(200))
    recorded_at: Mapped[datetime] = mapped_column(UtcDateTime)
    superseded_by: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(one_of("subject_type", CAPABLE), name="subject_type"),
        Index("ix_recovery_capability_subject", "subject_type", "subject_id"),
    )


class ContinuityCover(Base):
    """A process a continuity plan restores."""

    __tablename__ = "continuity_cover"
    __audit_parent__ = ("document", "document_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("policy_document.id", ondelete="CASCADE"))
    process_id: Mapped[int] = mapped_column(ForeignKey("process.id"))

    __table_args__ = (
        UniqueConstraint("document_id", "process_id", name="uq_continuity_cover"),
        Index("ix_continuity_cover_process_id", "process_id"),
    )


class ContinuityExercise(Base):
    """A test of a continuity plan: what was tried, what happened, and whether its recovery
    objectives were met. Findings are issues, with the exercise as their source. Never
    edited."""

    __tablename__ = "continuity_exercise"
    __audit_parent__ = ("document", "document_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("policy_document.id", ondelete="CASCADE"))
    # The version in force when it was exercised.
    version_id: Mapped[int | None] = mapped_column(ForeignKey("policy_version.id"))
    kind: Mapped[str] = mapped_column(String(16))
    held_on: Mapped[date] = mapped_column(Date)
    scenario: Mapped[str] = mapped_column(Text)
    participants: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(String(16))
    # How long recovery took in the exercise, where it was timed.
    achieved_hours: Mapped[int | None] = mapped_column(Integer)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    recorded_by_name: Mapped[str] = mapped_column(String(200))
    recorded_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint(one_of("kind", EXERCISE_KINDS), name="kind"),
        CheckConstraint(one_of("result", EXERCISE_RESULTS), name="result"),
        Index("ix_continuity_exercise_document_id", "document_id"),
    )
