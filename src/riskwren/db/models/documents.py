"""Policy documents: policies, standards, procedures, and guidelines, with their versions and
the approvals each version was published on (POL-01, POL-02, POL-03, POL-07)."""

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
from riskwren.db.models.inventory import RECORD_STATUSES, RecordMixin, one_of
from riskwren.db.types import UtcDateTime

# From the broadest to the most particular. A document implements one of an earlier kind.
DOCUMENT_KINDS = ("policy", "standard", "procedure", "guideline")
# Where a version's words are: written here, a link to where they are kept, or a file.
VERSION_FORMS = ("text", "link", "file")
VERSION_STATUSES = ("draft", "in_review", "approved", "published", "superseded", "discarded")
APPROVAL_DECISIONS = ("pending", "approved", "returned", "cancelled")


class PolicyDocument(RecordMixin, Base):
    """A document the organization has, whatever its version. What it says is in its
    versions; one of them, once published, is the one in force."""

    __tablename__ = "policy_document"
    __subject__ = "document"

    kind: Mapped[str] = mapped_column(String(16), default="policy")
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("policy_document.id"))
    status: Mapped[str] = mapped_column(String(24), default="active")
    # Months between reviews; none means the program's cadence.
    review_months: Mapped[int | None] = mapped_column(Integer)
    published_version_id: Mapped[int | None] = mapped_column(Integer)
    last_reviewed_on: Mapped[date | None] = mapped_column(Date)
    next_review_on: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),
        CheckConstraint(one_of("kind", DOCUMENT_KINDS), name="kind"),
        Index("ix_policy_document_org_unit_id", "org_unit_id"),
        Index("ix_policy_document_parent_id", "parent_id"),
    )


class PolicyVersion(Base):
    """One version of a document: a draft, one under review, or one that was published.
    A published version is never changed again. The text is not copied into the history,
    which holds its fingerprint instead, so that what was published can be shown to be what
    is shown."""

    __tablename__ = "policy_version"
    __audit_parent__ = ("document", "document_id")
    __audit_skip__ = frozenset({"body"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("policy_document.id"))
    # Given when it is published: the first published is 1, the next 2, and so on.
    number: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    form: Mapped[str] = mapped_column(String(8), default="text")
    body: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(500))
    file_id: Mapped[int | None] = mapped_column(ForeignKey("stored_file.id"))
    file_name: Mapped[str | None] = mapped_column(String(200))
    fingerprint: Mapped[str | None] = mapped_column(String(64))
    change_note: Mapped[str | None] = mapped_column(Text)
    review_round: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(Integer)
    created_by_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime)
    submitted_by: Mapped[int | None] = mapped_column(Integer)
    submitted_by_name: Mapped[str | None] = mapped_column(String(200))
    submitted_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    published_by_name: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    superseded_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint(one_of("status", VERSION_STATUSES), name="status"),
        CheckConstraint(one_of("form", VERSION_FORMS), name="form"),
        UniqueConstraint("document_id", "number"),
        Index("ix_policy_version_document_id", "document_id"),
    )


class PolicyApproval(Base):
    """That a named person was asked to approve a version, and what they said. Like every
    judgment here it is never edited: sending the version again asks again."""

    __tablename__ = "policy_approval"
    __audit_parent__ = ("document", "document_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("policy_document.id"))
    version_id: Mapped[int] = mapped_column(ForeignKey("policy_version.id"))
    review_round: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    account_name: Mapped[str] = mapped_column(String(200))
    decision: Mapped[str] = mapped_column(String(16), default="pending")
    note: Mapped[str | None] = mapped_column(Text)
    asked_at: Mapped[datetime] = mapped_column(UtcDateTime)
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint(one_of("decision", APPROVAL_DECISIONS), name="decision"),
        UniqueConstraint("version_id", "review_round", "account_id"),
        Index("ix_policy_approval_account_id", "account_id"),
    )
