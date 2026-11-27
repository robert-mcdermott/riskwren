"""Controls and what is known of them, and what is done about a risk: plans, actions, and
acceptances."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
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
from riskwren.db.models.inventory import RECORD_STATUSES, RecordMixin, one_of
from riskwren.db.types import JsonType, UtcDateTime

EFFECTIVENESS = ("effective", "partly", "ineffective", "not_assessed")
BASES = ("judgment", "attestation", "test")
REDUCES = ("likelihood", "impact", "both")
RELIANCE = ("primary", "supporting")
PLAN_STATUSES = ("active", "complete", "cancelled")
ACTION_STATUSES = ("open", "in_progress", "done", "cancelled")


class Control(RecordMixin, Base):
    """Something the organization does to reduce a risk, described once, with an owner."""

    __tablename__ = "control"
    __subject__ = "control"

    statement: Mapped[str] = mapped_column(Text)
    objective: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(40))
    nature: Mapped[str | None] = mapped_column(String(40))
    frequency: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), default="active")
    is_key: Mapped[bool] = mapped_column(Boolean, default=False)
    # Copies of the latest rating, kept here so lists are fast. The ratings are the authority.
    design: Mapped[str] = mapped_column(String(16), default="not_assessed")
    operation: Mapped[str] = mapped_column(String(16), default="not_assessed")
    rated_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    # What its owner last said of it. An attestation is the owner's word, not a test, and is
    # always shown apart from the rating.
    attested_operates: Mapped[str | None] = mapped_column(String(16))
    attested_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    attested_by_name: Mapped[str | None] = mapped_column(String(200))
    library_key: Mapped[str | None] = mapped_column(String(80))

    __table_args__ = (
        CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),
        CheckConstraint(one_of("design", EFFECTIVENESS), name="design"),
        CheckConstraint(one_of("operation", EFFECTIVENESS), name="operation"),
        Index("ix_control_org_unit_id", "org_unit_id"),
    )


class ControlRating(Base):
    """What a named person found, on a date, about whether a control works. Never edited."""

    __tablename__ = "control_rating"
    __audit_parent__ = ("control", "control_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    control_id: Mapped[int] = mapped_column(ForeignKey("control.id"))
    design: Mapped[str] = mapped_column(String(16))
    operation: Mapped[str] = mapped_column(String(16))
    basis: Mapped[str] = mapped_column(String(16), default="judgment")
    note: Mapped[str] = mapped_column(Text)
    rated_by: Mapped[int | None] = mapped_column(Integer)
    rated_by_name: Mapped[str] = mapped_column(String(200))
    rated_at: Mapped[datetime] = mapped_column(UtcDateTime)
    superseded_by: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(one_of("design", EFFECTIVENESS), name="design"),
        CheckConstraint(one_of("operation", EFFECTIVENESS), name="operation"),
        CheckConstraint(one_of("basis", BASES), name="basis"),
        Index("ix_control_rating_control_id", "control_id"),
    )


class RiskControl(Base):
    """A control that bears on a risk: what it reduces, and how much the risk relies on it."""

    __tablename__ = "risk_control"
    __audit_parent__ = ("risk", "risk_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risk.id"))
    control_id: Mapped[int] = mapped_column(ForeignKey("control.id"))
    reduces: Mapped[str] = mapped_column(String(16))
    reliance: Mapped[str] = mapped_column(String(16))
    note: Mapped[str | None] = mapped_column(String(300))

    __table_args__ = (
        UniqueConstraint("risk_id", "control_id"),
        CheckConstraint(one_of("reduces", REDUCES), name="reduces"),
        CheckConstraint(one_of("reliance", RELIANCE), name="reliance"),
        Index("ix_risk_control_control_id", "control_id"),
    )


class ControlLibraryEntry(Base):
    """A common control in plain words, loaded from a pack, from which one can be started."""

    __tablename__ = "control_library"
    __audit__ = False  # content that ships with the product, not the organization's record

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    statement: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(40))
    nature: Mapped[str | None] = mapped_column(String(40))
    frequency: Mapped[str | None] = mapped_column(String(40))
    reduces: Mapped[str] = mapped_column(String(16), default="likelihood")
    # Framework key → the codes of the requirements this control helps to satisfy.
    requirements: Mapped[dict[str, list[str]]] = mapped_column(JsonType, default=dict)
    source_pack: Mapped[str] = mapped_column(String(80))


class TreatmentPlan(Base):
    """The actions that will bring a risk to its target rating, with an owner and a date."""

    __tablename__ = "treatment_plan"
    __subject__ = "treatment_plan"
    __audit_parent__ = ("risk", "risk_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref: Mapped[str] = mapped_column(String(24), unique=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risk.id"))
    objective: Mapped[str] = mapped_column(Text)
    target_rating: Mapped[str | None] = mapped_column(String(40))
    owner_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    due_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="active")
    closed_note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    closed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint(one_of("status", PLAN_STATUSES), name="status"),
        Index("ix_treatment_plan_risk_id", "risk_id"),
        Index("ix_treatment_plan_owner_id", "owner_id"),
    )


class Acceptance(Base):
    """A statement by a named person, with the authority to make it, that a risk above
    appetite will be lived with until a date. Never edited; it may be withdrawn."""

    __tablename__ = "acceptance"
    __audit_parent__ = ("risk", "risk_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risk.id"))
    rating_accepted: Mapped[str] = mapped_column(String(40))
    likelihood: Mapped[int] = mapped_column(Integer)
    impact: Mapped[int] = mapped_column(Integer)
    appetite: Mapped[str | None] = mapped_column(String(40))
    rationale: Mapped[str] = mapped_column(Text)
    conditions: Mapped[str | None] = mapped_column(Text)
    accepted_by: Mapped[int] = mapped_column(ForeignKey("account.id"))
    accepted_by_name: Mapped[str] = mapped_column(String(200))
    accepted_at: Mapped[datetime] = mapped_column(UtcDateTime)
    expires_on: Mapped[date] = mapped_column(Date)
    withdrawn_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    withdrawn_by_name: Mapped[str | None] = mapped_column(String(200))
    withdrawn_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_acceptance_risk_id", "risk_id"),
        Index("ix_acceptance_expires_on", "expires_on"),
    )


class Action(Base):
    """Something a named person must do by a date, whatever it came from."""

    __tablename__ = "action"
    __subject__ = "action"
    __audit_parent__ = ("@source_type", "source_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref: Mapped[str] = mapped_column(String(24), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    due_on: Mapped[date] = mapped_column(Date)
    # Moving the date needs a reason; where it started and how often it moved stay here.
    original_due_on: Mapped[date] = mapped_column(Date)
    extensions: Mapped[list[dict[str, str]]] = mapped_column(JsonType, default=list)
    status: Mapped[str] = mapped_column(String(16), default="open")
    source_type: Mapped[str] = mapped_column(String(24))
    source_id: Mapped[int] = mapped_column(Integer)
    # Who outside does it, where a third party's contact does: the owner follows it up.
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("third_party_contact.id"))
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    completion_note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint(one_of("status", ACTION_STATUSES), name="status"),
        Index("ix_action_owner_id", "owner_id"),
        Index("ix_action_source", "source_type", "source_id"),
        Index("ix_action_due_on", "due_on"),
    )
