"""The organization's aims and its committees: strategic objectives that risks threaten, and
committee sessions with an agenda drawn from the register, the decision taken on each item,
and the minutes (RSK-16, OVS-09)."""

from __future__ import annotations

from datetime import date, datetime

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
from riskwren.db.models.inventory import RecordMixin, one_of
from riskwren.db.types import UtcDateTime

OBJECTIVE_STATUSES = ("active", "achieved", "retired")
SESSION_STATUSES = ("planned", "held", "cancelled")
# What a committee did with an item on its agenda.
OUTCOMES = ("noted", "approved", "declined", "deferred")


class Objective(RecordMixin, Base):
    """What the organization means to achieve, for which its risks matter."""

    __tablename__ = "objective"
    __subject__ = "objective"

    status: Mapped[str] = mapped_column(String(16), default="active")
    period: Mapped[str | None] = mapped_column(String(120))  # "Strategic plan 2026 to 2030"
    measure: Mapped[str | None] = mapped_column(Text)  # how it is known to be met

    __table_args__ = (
        CheckConstraint(one_of("status", OBJECTIVE_STATUSES), name="status"),
        Index("ix_objective_org_unit_id", "org_unit_id"),
    )


class RiskObjective(Base):
    """A risk names an objective it threatens."""

    __tablename__ = "risk_objective"
    __audit_parent__ = ("risk", "risk_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risk.id"))
    objective_id: Mapped[int] = mapped_column(ForeignKey("objective.id"))

    __table_args__ = (
        UniqueConstraint("risk_id", "objective_id"),
        Index("ix_risk_objective_objective_id", "objective_id"),
    )


class CommitteeSession(RecordMixin, Base):
    """A meeting of a risk or compliance committee."""

    __tablename__ = "committee_session"
    __subject__ = "committee_session"

    committee: Mapped[str] = mapped_column(String(120))  # "Risk committee"
    held_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="planned")
    attendees: Mapped[str | None] = mapped_column(Text)
    minutes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(one_of("status", SESSION_STATUSES), name="status"),
        Index("ix_committee_session_held_on", "held_on"),
    )


class CommitteeItem(Base):
    """One item on a session's agenda: a record from the register, or a topic of its own,
    and the decision taken on it."""

    __tablename__ = "committee_item"
    __audit_parent__ = ("committee_session", "session_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("committee_session.id"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    subject_type: Mapped[str | None] = mapped_column(String(24))
    subject_id: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    note: Mapped[str | None] = mapped_column(Text)  # what the committee is asked
    outcome: Mapped[str | None] = mapped_column(String(16))
    decision: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    decided_by_name: Mapped[str | None] = mapped_column(String(200))
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint(f"outcome IS NULL OR {one_of('outcome', OUTCOMES)}", name="outcome"),
        Index("ix_committee_item_session_id", "session_id"),
        Index("ix_committee_item_subject", "subject_type", "subject_id"),
    )
