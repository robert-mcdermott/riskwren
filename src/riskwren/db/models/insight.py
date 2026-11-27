"""Insight (RPT): what is kept to read the record back, beyond the record itself."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from riskwren.db.base import Base
from riskwren.db.types import UtcDateTime


class MeasureSnapshot(Base):
    """The organization's figure for one measure on one day (RPT-06). Bookkeeping, not
    history: outside the hash chain, and replaced if taken again the same day."""

    __tablename__ = "measure_snapshot"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(Date)
    measure: Mapped[str] = mapped_column(String(40))
    value: Mapped[int] = mapped_column(Integer)
    taken_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (
        UniqueConstraint("day", "measure"),
        Index("ix_measure_snapshot_measure", "measure", "day"),
    )
