"""Agreements: what the organization has promised others, with its dates (CMP-12).

An award's terms, a data use agreement, a business associate agreement, a contract. Each has
the parties it is with, when it runs, how much notice ending it takes, what it covers, and
the requirements it imposes, held as a framework of the organization's own.
"""

from __future__ import annotations

from datetime import date

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

AGREEMENT_KINDS = (
    "award", "data_use", "business_associate", "contract", "confidentiality", "memorandum",
    "other",
)  # fmt: skip
AGREEMENT_STATUSES = ("active", "closed")
# What an agreement can cover: the systems and information it is about, and scopes whole.
COVERED = ("system", "information", "scope")


class Agreement(RecordMixin, Base):
    __tablename__ = "agreement"
    __subject__ = "agreement"

    kind: Mapped[str] = mapped_column(String(24))
    parties: Mapped[str] = mapped_column(String(300))  # who it is with
    reference: Mapped[str | None] = mapped_column(String(120))  # their number for it
    url: Mapped[str | None] = mapped_column(String(300))  # where the signed copy is kept
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)  # none: it runs until it is ended
    # Days before it ends by which notice must be given, to end it or to keep it going.
    notice_days: Mapped[int | None] = mapped_column(Integer)
    # Whether it carries on by itself unless notice is given.
    renews: Mapped[bool] = mapped_column(Boolean, default=False)
    # The requirements it imposes: a framework of kind agreement.
    framework_id: Mapped[int | None] = mapped_column(ForeignKey("framework.id"))
    status: Mapped[str] = mapped_column(String(16), default="active")
    closed_on: Mapped[date | None] = mapped_column(Date)
    closed_note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(one_of("kind", AGREEMENT_KINDS), name="kind"),
        CheckConstraint(one_of("status", AGREEMENT_STATUSES), name="status"),
        Index("ix_agreement_org_unit_id", "org_unit_id"),
        Index("ix_agreement_ends_on", "ends_on"),
    )


class AgreementCoverage(Base):
    """A system, a body of information, or a scope that an agreement covers."""

    __tablename__ = "agreement_coverage"
    __audit_parent__ = ("agreement", "agreement_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agreement_id: Mapped[int] = mapped_column(ForeignKey("agreement.id"))
    subject_type: Mapped[str] = mapped_column(String(24))
    subject_id: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("agreement_id", "subject_type", "subject_id"),
        CheckConstraint(one_of("subject_type", COVERED), name="subject_type"),
        Index("ix_agreement_coverage_subject", "subject_type", "subject_id"),
    )
