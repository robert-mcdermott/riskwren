"""Indicators: a measure with thresholds, read over time, that warns of risks (RSK-13)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from riskwren.db.base import Base
from riskwren.db.models.inventory import RECORD_STATUSES, RecordMixin, one_of
from riskwren.db.types import UtcDateTime

INDICATOR_DIRECTIONS = ("up", "down")  # which way is worse
INDICATOR_FREQUENCIES = ("weekly", "monthly", "quarterly", "annually")
INDICATOR_STATES = ("no_reading", "ok", "warn", "breach")


class Indicator(RecordMixin, Base):
    """A number someone reads on a schedule, with the levels at which it should worry
    people. RiskWren never collects it: a person reads it somewhere and records it here."""

    __tablename__ = "indicator"
    __subject__ = "indicator"

    measure: Mapped[str | None] = mapped_column(String(40))  # what it is counted in: %, days
    source: Mapped[str | None] = mapped_column(Text)  # where the number is read from
    direction: Mapped[str] = mapped_column(String(8), default="up")
    warn_at: Mapped[float | None] = mapped_column(Float)
    breach_at: Mapped[float] = mapped_column(Float)
    frequency: Mapped[str] = mapped_column(String(16), default="monthly")
    status: Mapped[str] = mapped_column(String(24), default="active")
    # Kept from the newest reading, so that lists need not read every reading.
    last_value: Mapped[float | None] = mapped_column(Float)
    last_read_on: Mapped[date | None] = mapped_column(Date)
    state: Mapped[str] = mapped_column(String(16), default="no_reading")

    __table_args__ = (
        CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),
        CheckConstraint(one_of("direction", INDICATOR_DIRECTIONS), name="direction"),
        CheckConstraint(one_of("frequency", INDICATOR_FREQUENCIES), name="frequency"),
        CheckConstraint(one_of("state", INDICATOR_STATES), name="state"),
    )


class IndicatorReading(Base):
    """What an indicator stood at on a day, and who read it."""

    __tablename__ = "indicator_reading"
    __audit_parent__ = ("indicator", "indicator_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    indicator_id: Mapped[int] = mapped_column(ForeignKey("indicator.id", ondelete="CASCADE"))
    read_on: Mapped[date] = mapped_column(Date)
    value: Mapped[float] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(Text)
    entered_by: Mapped[int | None] = mapped_column(Integer)
    entered_by_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (UniqueConstraint("indicator_id", "read_on"),)


class IndicatorRisk(Base):
    """That an indicator warns of a risk."""

    __tablename__ = "indicator_risk"
    __audit_parent__ = ("indicator", "indicator_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    indicator_id: Mapped[int] = mapped_column(ForeignKey("indicator.id", ondelete="CASCADE"))
    risk_id: Mapped[int] = mapped_column(ForeignKey("risk.id"))

    __table_args__ = (
        UniqueConstraint("indicator_id", "risk_id"),
        Index("ix_indicator_risk_risk_id", "risk_id"),
    )
