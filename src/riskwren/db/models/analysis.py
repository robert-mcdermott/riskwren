"""Structured risk assessment: an exercise that walks what is in a scope against a list of
threats, and raises or refreshes risks as it goes (RSK-15).

It is called a risk analysis here, because "assessment" already names two other things: a
judgment of one risk, and the testing of controls.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from riskwren.db.base import Base
from riskwren.db.models.inventory import RecordMixin, one_of
from riskwren.db.types import UtcDateTime

ANALYSIS_STATUSES = ("open", "closed")
ANALYSIS_OUTCOMES = ("pending", "not_applicable", "covered", "raised")


class RiskAnalysis(RecordMixin, Base):
    """One exercise: what was looked at, against what, and what came of it."""

    __tablename__ = "risk_analysis"
    __subject__ = "risk_analysis"

    status: Mapped[str] = mapped_column(String(16), default="open")
    # What it is over: a scope's boundary, or everything a unit and those beneath it hold.
    scope_id: Mapped[int | None] = mapped_column(ForeignKey("scope.id"))
    conclusion: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    closed_by_name: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        CheckConstraint(one_of("status", ANALYSIS_STATUSES), name="status"),
        Index("ix_risk_analysis_org_unit_id", "org_unit_id"),
    )


class RiskAnalysisItem(Base):
    """One thing considered against one threat, and what was decided. The names are kept as
    they were, so the report still reads if the thing is later renamed or retired."""

    __tablename__ = "risk_analysis_item"
    __audit_parent__ = ("risk_analysis", "analysis_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("risk_analysis.id", ondelete="CASCADE"))
    subject_type: Mapped[str] = mapped_column(String(24))
    subject_id: Mapped[int] = mapped_column(Integer)
    subject_ref: Mapped[str] = mapped_column(String(24))
    subject_name: Mapped[str] = mapped_column(String(200))
    threat_key: Mapped[str] = mapped_column(String(80))
    threat_title: Mapped[str] = mapped_column(String(200))
    outcome: Mapped[str] = mapped_column(String(16), default="pending")
    risk_id: Mapped[int | None] = mapped_column(ForeignKey("risk.id"))
    note: Mapped[str | None] = mapped_column(Text)
    considered_by_name: Mapped[str | None] = mapped_column(String(200))
    considered_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint(one_of("outcome", ANALYSIS_OUTCOMES), name="outcome"),
        UniqueConstraint("analysis_id", "subject_type", "subject_id", "threat_key"),
        Index("ix_risk_analysis_item_risk_id", "risk_id"),
    )
