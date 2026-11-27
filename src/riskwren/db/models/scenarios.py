"""Scenarios and estimates in ranges (RSK-18, RSK-19).

A scenario is a story told on purpose: what might happen, what is assumed, the risks and
processes it would touch, and what was concluded. An estimate puts numbers to a risk as
ranges, low, likely, and high, of how often it happens in a year and what each time costs.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from riskwren.db.base import Base
from riskwren.db.models.inventory import RecordMixin, one_of
from riskwren.db.types import UtcDateTime

SCENARIO_STATUSES = ("draft", "concluded", "retired")
SCENARIO_SUBJECTS = ("risk", "process")


class Scenario(RecordMixin, Base):
    """What might happen, told as a story, with what was assumed and concluded."""

    __tablename__ = "scenario"
    __subject__ = "scenario"

    status: Mapped[str] = mapped_column(String(16), default="draft")
    assumptions: Mapped[str | None] = mapped_column(Text)
    conclusion: Mapped[str | None] = mapped_column(Text)
    concluded_on: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        CheckConstraint(one_of("status", SCENARIO_STATUSES), name="status"),
        Index("ix_scenario_org_unit_id", "org_unit_id"),
    )


class ScenarioSubject(Base):
    """A risk or a process a scenario would touch."""

    __tablename__ = "scenario_subject"
    __audit_parent__ = ("scenario", "scenario_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenario.id"))
    subject_type: Mapped[str] = mapped_column(String(24))
    subject_id: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(one_of("subject_type", SCENARIO_SUBJECTS), name="subject_type"),
        Index("ix_scenario_subject_scenario_id", "scenario_id"),
        Index("ix_scenario_subject_subject", "subject_type", "subject_id"),
    )


class RiskEstimate(Base):
    """A risk in numbers: how often a year, and what each time costs, each as a low, likely,
    and high value, with what was assumed. Never edited: a new one supersedes it."""

    __tablename__ = "risk_estimate"
    __audit_parent__ = ("risk", "risk_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risk.id"))
    frequency_low: Mapped[float] = mapped_column(Float)
    frequency_likely: Mapped[float] = mapped_column(Float)
    frequency_high: Mapped[float] = mapped_column(Float)
    loss_low: Mapped[int] = mapped_column(Integer)
    loss_likely: Mapped[int] = mapped_column(Integer)
    loss_high: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    assumptions: Mapped[str] = mapped_column(Text)
    estimated_by: Mapped[int | None] = mapped_column(Integer)
    estimated_by_name: Mapped[str] = mapped_column(String(200))
    estimated_at: Mapped[datetime] = mapped_column(UtcDateTime)
    superseded_by: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (Index("ix_risk_estimate_risk_id", "risk_id"),)
