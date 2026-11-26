"""The risk register: categories, the scoring method, risks, and the judgments made of them."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

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
from riskwren.db.models.inventory import RecordMixin, one_of
from riskwren.db.types import JsonType, UtcDateTime

CATEGORY_STATUSES = ("active", "retired")
METHOD_STATUSES = ("current", "superseded")
RISK_STATUSES = ("draft", "open", "closed")
RESPONSES = ("reduce", "accept", "transfer", "avoid")
ASSESSMENT_KINDS = ("inherent", "residual", "target")
STANDINGS = ("not_assessed", "within", "treated", "accepted", "needs_decision", "closed")


class RiskCategory(Base):
    """A kind of risk, in a tree the organization edits. Appetite is set where it is known
    and otherwise comes from the category above."""

    __tablename__ = "risk_category"
    __subject__ = "risk_category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("risk_category.id"))
    key: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    # The key of the highest residual rating the organization is content to live with here.
    appetite: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), default="active")
    position: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (CheckConstraint(one_of("status", CATEGORY_STATUSES), name="status"),)


class ScoringMethod(Base):
    """One published version of how risks are rated. Never changed once published: every
    assessment names the version it was made under."""

    __tablename__ = "scoring_method"
    __subject__ = "scoring_method"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    status: Mapped[str] = mapped_column(String(16), default="current")
    definition: Mapped[dict[str, Any]] = mapped_column(JsonType)
    published_by: Mapped[int | None] = mapped_column(Integer)
    published_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (CheckConstraint(one_of("status", METHOD_STATUSES), name="status"),)


class Risk(RecordMixin, Base):
    """Something that could happen and would matter: a cause, an event, and a consequence."""

    __tablename__ = "risk"
    __subject__ = "risk"

    cause: Mapped[str | None] = mapped_column(Text)
    event: Mapped[str | None] = mapped_column(Text)
    consequence: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int] = mapped_column(ForeignKey("risk_category.id"))
    status: Mapped[str] = mapped_column(String(16), default="open")
    closed_reason: Mapped[str | None] = mapped_column(Text)
    response: Mapped[str | None] = mapped_column(String(16))
    response_rationale: Mapped[str | None] = mapped_column(Text)

    # Copies of the latest assessment of each kind, kept here so lists and the heat map are
    # fast. The assessments are the authority.
    inherent_likelihood: Mapped[int | None] = mapped_column(Integer)
    inherent_impact: Mapped[int | None] = mapped_column(Integer)
    inherent_rating: Mapped[str | None] = mapped_column(String(40))
    residual_likelihood: Mapped[int | None] = mapped_column(Integer)
    residual_impact: Mapped[int | None] = mapped_column(Integer)
    residual_rating: Mapped[str | None] = mapped_column(String(40))
    target_likelihood: Mapped[int | None] = mapped_column(Integer)
    target_impact: Mapped[int | None] = mapped_column(Integer)
    target_rating: Mapped[str | None] = mapped_column(String(40))

    # Whether the risk is in order, worked out by the service and stored so it can be filtered.
    standing: Mapped[str] = mapped_column(String(24), default="not_assessed")
    next_review_on: Mapped[date | None] = mapped_column(Date)
    # Set when what is now known about the controls suggests a worse rating than the one on
    # record, with the reason.
    residual_in_doubt: Mapped[bool] = mapped_column(Boolean, default=False)
    residual_doubt_reason: Mapped[str | None] = mapped_column(Text)

    escalated_to_unit_id: Mapped[int | None] = mapped_column(ForeignKey("org_unit.id"))
    escalation_reason: Mapped[str | None] = mapped_column(Text)
    library_key: Mapped[str | None] = mapped_column(String(80))

    __table_args__ = (
        CheckConstraint(one_of("status", RISK_STATUSES), name="status"),
        CheckConstraint(one_of("standing", STANDINGS), name="standing"),
        CheckConstraint(f"response IS NULL OR {one_of('response', RESPONSES)}", name="response"),
        Index("ix_risk_org_unit_id", "org_unit_id"),
        Index("ix_risk_category_id", "category_id"),
        Index("ix_risk_standing", "standing"),
        Index("ix_risk_escalated_to_unit_id", "escalated_to_unit_id"),
    )


class RiskAssessment(Base):
    """A dated judgment of likelihood and impact by a named person. Never edited: a new
    assessment supersedes the old one, and both stay."""

    __tablename__ = "risk_assessment"
    __audit_parent__ = ("risk", "risk_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risk.id"))
    kind: Mapped[str] = mapped_column(String(16))
    likelihood: Mapped[int] = mapped_column(Integer)
    impact: Mapped[int] = mapped_column(Integer)
    # The level chosen on each impact dimension that was rated.
    impact_levels: Mapped[dict[str, int]] = mapped_column(JsonType, default=dict)
    rating: Mapped[str] = mapped_column(String(40))
    rationale: Mapped[str] = mapped_column(Text)
    # For a residual assessment: what the controls suggested, with its working, exactly as
    # it stood when the judgment was made.
    suggested: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    method_id: Mapped[int] = mapped_column(ForeignKey("scoring_method.id"))
    assessed_by: Mapped[int | None] = mapped_column(Integer)
    assessed_by_name: Mapped[str] = mapped_column(String(200))
    assessed_at: Mapped[datetime] = mapped_column(UtcDateTime)
    superseded_by: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(one_of("kind", ASSESSMENT_KINDS), name="kind"),
        Index("ix_risk_assessment_risk_id", "risk_id"),
    )


class RiskSubject(Base):
    """A process, system, or third party that a risk concerns."""

    __tablename__ = "risk_subject"
    __audit_parent__ = ("risk", "risk_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risk.id"))
    subject_type: Mapped[str] = mapped_column(String(24))
    subject_id: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("risk_id", "subject_type", "subject_id"),
        Index("ix_risk_subject_subject", "subject_type", "subject_id"),
    )


class RiskLibraryEntry(Base):
    """A reusable risk statement, loaded from a pack, from which a risk can be started."""

    __tablename__ = "risk_library"
    __audit__ = False  # content that ships with the product, not the organization's record

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    category_key: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(200))
    cause: Mapped[str] = mapped_column(Text)
    event: Mapped[str] = mapped_column(Text)
    consequence: Mapped[str] = mapped_column(Text)
    suggested_controls: Mapped[list[str]] = mapped_column(JsonType, default=list)
    source_pack: Mapped[str] = mapped_column(String(80))
