"""Internal audit (AUD): the third line's own records on the shared record.

What audit knows about each auditable thing (its place in the universe), the plan for a
period, and the engagements in it. An auditable thing is not a new kind of record: it is a
unit, a process, a system, a third party, or a scope already kept by the first and second
lines.
"""

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
from riskwren.db.models.inventory import one_of
from riskwren.db.types import JsonType, UtcDateTime

AUDITABLE = ("unit", "process", "system", "third_party", "scope")
PLAN_STATUSES = ("draft", "approved", "closed")
ENGAGEMENT_STATUSES = ("planned", "planning", "fieldwork", "reporting", "reported", "dropped")


class AuditEntity(Base):
    """What audit says about one auditable thing: a change to its ranking with the reason,
    when it was last audited before RiskWren, or that it is left out of the universe."""

    __tablename__ = "audit_entity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(24))
    subject_id: Mapped[int] = mapped_column(Integer)
    adjustment: Mapped[int] = mapped_column(Integer, default=0)
    adjustment_reason: Mapped[str | None] = mapped_column(Text)
    last_audited_on: Mapped[date | None] = mapped_column(Date)
    last_audit_note: Mapped[str | None] = mapped_column(Text)
    left_out: Mapped[bool] = mapped_column(Boolean, default=False)
    left_out_reason: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[int | None] = mapped_column(Integer)
    updated_by_name: Mapped[str] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint(one_of("subject_type", AUDITABLE), name="subject_type"),
        UniqueConstraint("subject_type", "subject_id"),
    )


class AuditPlan(Base):
    """The work internal audit means to do in a period, approved by a named person."""

    __tablename__ = "audit_plan"
    __audit_skip__ = frozenset({"version", "updated_at"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref: Mapped[str] = mapped_column(String(24), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    approved_by: Mapped[int | None] = mapped_column(Integer)
    approved_by_name: Mapped[str | None] = mapped_column(String(200))
    approved_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    approval_note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (CheckConstraint(one_of("status", PLAN_STATUSES), name="status"),)


class Engagement(Base):
    """A piece of audit work on one auditable thing: planned in a period's plan, then carried
    out through planning, fieldwork, and reporting, or dropped with a reason."""

    __tablename__ = "engagement"
    __audit_skip__ = frozenset({"version", "updated_at"})
    __audit_redact__ = frozenset({"scope_note", "report_summary"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref: Mapped[str] = mapped_column(String(24), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("audit_plan.id"))
    subject_type: Mapped[str] = mapped_column(String(24))
    subject_id: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text)
    planned_start: Mapped[date | None] = mapped_column(Date)
    planned_end: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="planned")
    dropped_reason: Mapped[str | None] = mapped_column(Text)
    reported_on: Mapped[date | None] = mapped_column(Date)
    started_on: Mapped[date | None] = mapped_column(Date)
    fieldwork_on: Mapped[date | None] = mapped_column(Date)
    reporting_on: Mapped[date | None] = mapped_column(Date)
    scope_note: Mapped[str | None] = mapped_column(Text)  # what the engagement covers
    report_summary: Mapped[str | None] = mapped_column(Text)
    opinion: Mapped[str | None] = mapped_column(String(24))
    created_by: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (
        CheckConstraint(one_of("status", ENGAGEMENT_STATUSES), name="status"),
        CheckConstraint(one_of("subject_type", AUDITABLE), name="subject_type"),
        Index("ix_engagement_plan_id", "plan_id"),
        Index("ix_engagement_subject", "subject_type", "subject_id"),
    )


ENGAGEMENT_ROLES = ("lead", "member")
OPINIONS = ("effective", "needs_improvement", "ineffective")


class EngagementMember(Base):
    """An auditor on an engagement's team. Until it is reported, only the team sees its work."""

    __tablename__ = "engagement_member"
    __audit_parent__ = ("engagement", "engagement_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagement.id"))
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    role: Mapped[str] = mapped_column(String(16), default="member")

    __table_args__ = (
        CheckConstraint(one_of("role", ENGAGEMENT_ROLES), name="role"),
        UniqueConstraint("engagement_id", "account_id"),
    )


class Workpaper(Base):
    """One step of an engagement's program of work: what was to be done, what was done and
    found, the evidence, and its sign-off by someone other than the one who prepared it."""

    __tablename__ = "workpaper"
    __audit_parent__ = ("engagement", "engagement_id")
    # Until the report is issued, only the team reads what was done and found; the history
    # says that they changed, and keeps the words out (AUD-07).
    __audit_redact__ = frozenset({"procedure", "done", "found"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagement.id"))
    sequence: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    procedure: Mapped[str | None] = mapped_column(Text)  # what is to be done
    done: Mapped[str | None] = mapped_column(Text)  # what was done
    found: Mapped[str | None] = mapped_column(Text)  # what was found
    evidence: Mapped[list[str]] = mapped_column(JsonType, default=list)  # references
    prepared_by: Mapped[int | None] = mapped_column(Integer)
    prepared_by_name: Mapped[str | None] = mapped_column(String(200))
    prepared_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    signed_off_by: Mapped[int | None] = mapped_column(Integer)
    signed_off_by_name: Mapped[str | None] = mapped_column(String(200))
    signed_off_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    __table_args__ = (Index("ix_workpaper_engagement_id", "engagement_id"),)


class ReviewNote(Base):
    """A reviewer's note on a workpaper, open until its preparer answers and it is cleared."""

    __tablename__ = "review_note"
    __audit_parent__ = ("engagement", "engagement_id")
    __audit_redact__ = frozenset({"note", "answer"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagement.id"))
    workpaper_id: Mapped[int] = mapped_column(ForeignKey("workpaper.id"))
    note: Mapped[str] = mapped_column(Text)
    by: Mapped[int | None] = mapped_column(Integer)
    by_name: Mapped[str] = mapped_column(String(200))
    at: Mapped[datetime] = mapped_column(UtcDateTime)
    answer: Mapped[str | None] = mapped_column(Text)
    cleared_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    __table_args__ = (Index("ix_review_note_workpaper_id", "workpaper_id"),)


REQUEST_STATUSES = ("open", "answered", "accepted")


class AuditRequest(Base):
    """Something an engagement needs from the audited: asked of one person by a date, and
    answered with words and evidence, which the team accepts or sends back."""

    __tablename__ = "audit_request"
    __audit_parent__ = ("engagement", "engagement_id")
    # What audit asks for tells what it is looking at: kept out of the history (AUD-07).
    __audit_redact__ = frozenset({"what", "answer", "returned_reason"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagement.id"))
    what: Mapped[str] = mapped_column(Text)
    assignee_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    due_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="open")
    answer: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[list[str]] = mapped_column(JsonType, default=list)
    answered_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    returned_reason: Mapped[str | None] = mapped_column(Text)
    accepted_by_name: Mapped[str | None] = mapped_column(String(200))
    accepted_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    asked_by: Mapped[int | None] = mapped_column(Integer)
    asked_by_name: Mapped[str] = mapped_column(String(200))
    asked_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint(one_of("status", REQUEST_STATUSES), name="status"),
        Index("ix_audit_request_engagement_id", "engagement_id"),
        Index("ix_audit_request_assignee_id", "assignee_id", "status"),
    )
