"""Resilience (RES): what each process cannot afford to lose, and what its dependencies can
deliver.

A business impact analysis is a judgment by a named person about one process, never edited:
a new one supersedes it. A recovery capability is what a system or a service can actually be
restored within, and how much information it can lose, with what that rests on.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from riskwren.db.base import Base
from riskwren.db.models.inventory import one_of
from riskwren.db.types import JsonType, UtcDateTime

CAPABLE = ("system", "service")


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
