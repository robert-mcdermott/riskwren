"""Insight (RPT): what is kept to read the record back, beyond the record itself."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from riskwren.db.base import Base
from riskwren.db.types import JsonType, UtcDateTime


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


class LeadershipReport(Base):
    """A leadership report as it was issued (RPT-08): what it said, frozen, and the
    fingerprint of what it said. Never edited. The history records its issue with the
    fingerprint, so the report can be shown to be the one that was given."""

    __tablename__ = "leadership_report"
    # The history holds the fingerprint of what the report said; the report holds the rest.
    __audit_skip__ = frozenset({"body"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref: Mapped[str] = mapped_column(String(24), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    summary: Mapped[str | None] = mapped_column(Text)
    body: Mapped[dict[str, Any]] = mapped_column(JsonType)
    fingerprint: Mapped[str] = mapped_column(String(64))
    previous_id: Mapped[int | None] = mapped_column(Integer)
    issued_by: Mapped[int | None] = mapped_column(Integer)
    issued_by_name: Mapped[str] = mapped_column(String(200))
    issued_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (Index("ix_leadership_report_issued_at", "issued_at"),)
