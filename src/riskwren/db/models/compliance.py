"""What the organization is held to: frameworks, their requirements, and baselines."""

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

FRAMEWORK_KINDS = ("standard", "regulation", "agreement", "internal")
# What text a framework may carry (see spec/content-packs.md). ``own`` is the organization's
# own framework, entered here: its text is the organization's to hold and never ships.
TEXT_POLICIES = ("verbatim", "attributed", "identifiers", "summary", "own")
ORIGINS = ("pack", "local")
FRAMEWORK_STATUSES = ("active", "retired")
COVERAGE = ("full", "partial")
MAPPING_SOURCES = ("pack", "person")
IMPLEMENTATION_STATUSES = ("planned", "partly", "in_place", "not_applicable")
INHERITANCE = ("none", "inherited", "shared")
EVIDENCE_KINDS = ("file", "link", "note", "attestation")
ASSESSMENT_STATUSES = ("planned", "in_progress", "complete", "cancelled")
TEST_METHODS = ("examine", "interview", "test")
TEST_RESULTS = ("effective", "partly", "ineffective")
REVIEWS = ("confirmed", "returned")
REQUIREMENT_STATUSES = ("active", "withdrawn")
SEVERITIES = ("critical", "high", "moderate", "low")
ISSUE_STATUSES = ("open", "proposed", "closed", "cancelled")
EXCEPTION_STATUSES = ("requested", "approved", "refused", "withdrawn")
EXCEPTION_SUBJECTS = ("control", "requirement", "document")


class Framework(Base):
    """A source of requirements: a public standard, a regulation, an agreement's terms, or
    an internal standard."""

    __tablename__ = "framework"
    __subject__ = "framework"
    __audit_skip__ = frozenset({"updated_at"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    version: Mapped[str | None] = mapped_column(String(120))  # of the source document
    kind: Mapped[str] = mapped_column(String(24))
    summary: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(String(200))
    license: Mapped[str | None] = mapped_column(String(200))
    text_policy: Mapped[str] = mapped_column(String(24))
    attribution: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(300))
    built_from: Mapped[str | None] = mapped_column(Text)
    pack_version: Mapped[str | None] = mapped_column(String(40))
    origin: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="active")
    # Kept here so lists are fast, and so the history says how much a load brought in.
    requirement_count: Mapped[int] = mapped_column(Integer, default=0)
    citable_count: Mapped[int] = mapped_column(Integer, default=0)
    digest: Mapped[str | None] = mapped_column(String(64))  # of a pack's requirements
    created_by: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint(one_of("kind", FRAMEWORK_KINDS), name="kind"),
        CheckConstraint(one_of("text_policy", TEXT_POLICIES), name="text_policy"),
        CheckConstraint(one_of("origin", ORIGINS), name="origin"),
        CheckConstraint(one_of("status", FRAMEWORK_STATUSES), name="status"),
    )


class Requirement(Base):
    """One entry in a framework's tree. Its code is stable across versions of the pack, and
    is how crosswalks, tests, and evidence stay attached to it.

    Rows are not audited one by one: a pack's requirements are published content, recorded
    by the framework's own event with a digest. A change to a requirement of one of the
    organization's own frameworks is recorded explicitly by the service that makes it.
    """

    __tablename__ = "requirement"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    framework_id: Mapped[int] = mapped_column(ForeignKey("framework.id", ondelete="CASCADE"))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("requirement.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(120))
    title: Mapped[str | None] = mapped_column(String(300))
    text: Mapped[str | None] = mapped_column(Text)
    guidance: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str | None] = mapped_column(String(40))
    position: Mapped[int] = mapped_column(Integer, default=0)
    depth: Mapped[int] = mapped_column(Integer, default=0)
    # Its place in the document, reading from the top: what a flat list is ordered by.
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    # False for a heading that only groups others: a family, a function, a section.
    is_citable: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(16), default="active")

    __table_args__ = (
        UniqueConstraint("framework_id", "code", name="uq_requirement_framework_code"),
        CheckConstraint(one_of("status", REQUIREMENT_STATUSES), name="status"),
        Index("ix_requirement_parent", "framework_id", "parent_id", "position"),
        Index("ix_requirement_sequence", "framework_id", "sequence"),
    )


class Baseline(Base):
    """A published selection from a framework: the starting point for a scope."""

    __tablename__ = "baseline"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    framework_id: Mapped[int] = mapped_column(ForeignKey("framework.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(200))
    requirement_count: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (UniqueConstraint("framework_id", "key", name="uq_baseline_framework_key"),)


class BaselineRequirement(Base):
    __tablename__ = "baseline_requirement"
    __audit__ = False

    baseline_id: Mapped[int] = mapped_column(
        ForeignKey("baseline.id", ondelete="CASCADE"), primary_key=True
    )
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("requirement.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (Index("ix_baseline_requirement_requirement_id", "requirement_id"),)


class ControlRequirement(Base):
    """A crosswalk: this control helps to satisfy this requirement. One control answers
    many requirements, in any number of frameworks, and is tested once."""

    __tablename__ = "control_requirement"
    __subject__ = "control_requirement"
    __audit_parent__ = ("control", "control_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    control_id: Mapped[int] = mapped_column(ForeignKey("control.id", ondelete="CASCADE"))
    requirement_id: Mapped[int] = mapped_column(ForeignKey("requirement.id", ondelete="CASCADE"))
    # Whether the control answers the requirement by itself, or only in part.
    coverage: Mapped[str] = mapped_column(String(16), default="partial")
    note: Mapped[str | None] = mapped_column(String(300))
    # Suggested by a pack, or said by a person.
    source: Mapped[str] = mapped_column(String(16), default="person")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (
        UniqueConstraint("control_id", "requirement_id", name="uq_control_requirement"),
        CheckConstraint(one_of("coverage", COVERAGE), name="coverage"),
        CheckConstraint(one_of("source", MAPPING_SOURCES), name="source"),
        Index("ix_control_requirement_requirement_id", "requirement_id"),
    )


class Scope(RecordMixin, Base):
    """A named boundary that must meet one or more frameworks: the clinical systems, a data
    enclave, the whole organization."""

    __tablename__ = "scope"
    __subject__ = "scope"

    boundary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="active")
    # A scope that offers its controls lets other scopes inherit them.
    offers_controls: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),
        Index("ix_scope_org_unit_id", "org_unit_id"),
    )


class ScopeMember(Base):
    """Something inside a scope's boundary: a unit, a process, a system, a body of
    information, or a third party."""

    __tablename__ = "scope_member"
    __audit_parent__ = ("scope", "scope_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_id: Mapped[int] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    subject_type: Mapped[str] = mapped_column(String(24))
    subject_id: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("scope_id", "subject_type", "subject_id", name="uq_scope_member"),
        Index("ix_scope_member_subject", "subject_type", "subject_id"),
    )


class ScopeFramework(Base):
    """A framework a scope must meet, and the baseline it starts from, if any."""

    __tablename__ = "scope_framework"
    __audit_parent__ = ("scope", "scope_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_id: Mapped[int] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    framework_id: Mapped[int] = mapped_column(ForeignKey("framework.id"))
    baseline_id: Mapped[int | None] = mapped_column(ForeignKey("baseline.id"))

    __table_args__ = (
        UniqueConstraint("scope_id", "framework_id", name="uq_scope_framework"),
        Index("ix_scope_framework_framework_id", "framework_id"),
    )


class ScopeRequirement(Base):
    """A decision that departs from the starting point: a requirement left out of a scope,
    with the reason, or one brought in from outside its baseline."""

    __tablename__ = "scope_requirement"
    __audit_parent__ = ("scope", "scope_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_id: Mapped[int] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    requirement_id: Mapped[int] = mapped_column(ForeignKey("requirement.id", ondelete="CASCADE"))
    applicable: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    decided_by_name: Mapped[str | None] = mapped_column(String(200))
    decided_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (
        UniqueConstraint("scope_id", "requirement_id", name="uq_scope_requirement"),
        Index("ix_scope_requirement_requirement_id", "requirement_id"),
    )


class Implementation(Base):
    """How one control is done within one scope: where it stands, who answers for it, and,
    where another scope provides it, whose it is."""

    __tablename__ = "implementation"
    __audit_parent__ = ("scope", "scope_id")
    __audit_skip__ = frozenset({"updated_at"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_id: Mapped[int] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    control_id: Mapped[int] = mapped_column(ForeignKey("control.id"))
    status: Mapped[str] = mapped_column(String(24), default="planned")
    responsibility: Mapped[str | None] = mapped_column(String(200))
    statement: Mapped[str | None] = mapped_column(Text)
    inheritance: Mapped[str] = mapped_column(String(16), default="none")
    inherits_from_id: Mapped[int | None] = mapped_column(ForeignKey("implementation.id"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (
        UniqueConstraint("scope_id", "control_id", name="uq_implementation_scope_control"),
        CheckConstraint(one_of("status", IMPLEMENTATION_STATUSES), name="status"),
        CheckConstraint(one_of("inheritance", INHERITANCE), name="inheritance"),
        Index("ix_implementation_control_id", "control_id"),
        Index("ix_implementation_inherits_from_id", "inherits_from_id"),
    )


class StoredFile(Base):
    """A file in the data home, known by the digest of its bytes. The same bytes are stored
    once however many times they are sent."""

    __tablename__ = "stored_file"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    size: Mapped[int] = mapped_column(Integer)
    media_type: Mapped[str] = mapped_column(String(120))
    extension: Mapped[str] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)


class Evidence(RecordMixin, Base):
    """Something that shows a control is done: a file, a link, a note, or an attestation,
    with who collected it, the period it covers, and the date until which it holds."""

    __tablename__ = "evidence"
    __subject__ = "evidence"

    kind: Mapped[str] = mapped_column(String(16))
    file_id: Mapped[int | None] = mapped_column(ForeignKey("stored_file.id"))
    file_name: Mapped[str | None] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(String(300))
    note: Mapped[str | None] = mapped_column(Text)
    data_class: Mapped[str | None] = mapped_column(String(40))
    collected_on: Mapped[date] = mapped_column(Date)
    covers_from: Mapped[date | None] = mapped_column(Date)
    covers_to: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(24), default="active")

    __table_args__ = (
        CheckConstraint(one_of("kind", EVIDENCE_KINDS), name="kind"),
        CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),
        Index("ix_evidence_org_unit_id", "org_unit_id"),
        Index("ix_evidence_valid_until", "valid_until"),
    )


class EvidenceLink(Base):
    """What a piece of evidence supports. One item supports any number of things."""

    __tablename__ = "evidence_link"
    __audit_parent__ = ("evidence", "evidence_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"))
    subject_type: Mapped[str] = mapped_column(String(24))
    subject_id: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("evidence_id", "subject_type", "subject_id", name="uq_evidence_link"),
        Index("ix_evidence_link_subject", "subject_type", "subject_id"),
    )


class Assessment(RecordMixin, Base):
    """A planned look at whether a scope's controls work: over a period, against a framework
    or a chosen set of controls, with a lead."""

    __tablename__ = "assessment"
    __subject__ = "assessment"

    scope_id: Mapped[int] = mapped_column(ForeignKey("scope.id"))
    framework_id: Mapped[int | None] = mapped_column(ForeignKey("framework.id"))
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    approach: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="planned")
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint(one_of("status", ASSESSMENT_STATUSES), name="status"),
        Index("ix_assessment_org_unit_id", "org_unit_id"),
        Index("ix_assessment_scope_id", "scope_id"),
    )


class ControlTest(Base):
    """One control to be examined in one assessment: the procedure, the method, and who is
    to do it. What was found is a result."""

    __tablename__ = "control_test"
    __audit_parent__ = ("assessment", "assessment_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessment.id", ondelete="CASCADE"))
    implementation_id: Mapped[int] = mapped_column(ForeignKey("implementation.id"))
    control_id: Mapped[int] = mapped_column(ForeignKey("control.id"))
    procedure: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String(16), default="examine")
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("account.id"))

    __table_args__ = (
        UniqueConstraint("assessment_id", "control_id", name="uq_control_test"),
        CheckConstraint(one_of("method", TEST_METHODS), name="method"),
        Index("ix_control_test_control_id", "control_id"),
        Index("ix_control_test_assigned_to", "assigned_to"),
    )


class TestResult(Base):
    """What a test found, by whom, and who reviewed it. Never edited: a correction is a new
    result that supersedes it, and it counts only once a second person has confirmed it."""

    __tablename__ = "test_result"
    __test__ = False  # not a test case, whatever its name suggests to the test runner
    __audit_parent__ = ("assessment", "assessment_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("control_test.id", ondelete="CASCADE"))
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessment.id", ondelete="CASCADE"))
    sample: Mapped[str | None] = mapped_column(Text)
    design: Mapped[str] = mapped_column(String(16))
    operation: Mapped[str] = mapped_column(String(16))
    note: Mapped[str] = mapped_column(Text)
    tested_by: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    tested_by_name: Mapped[str] = mapped_column(String(200))
    tested_at: Mapped[datetime] = mapped_column(UtcDateTime)
    review: Mapped[str | None] = mapped_column(String(16))
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    reviewed_by_name: Mapped[str | None] = mapped_column(String(200))
    reviewed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    superseded_by: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(one_of("design", TEST_RESULTS), name="design"),
        CheckConstraint(one_of("operation", TEST_RESULTS), name="operation"),
        CheckConstraint("review IS NULL OR " + one_of("review", REVIEWS), name="review"),
        Index("ix_test_result_test_id", "test_id"),
    )


class Issue(RecordMixin, Base):
    """Something found to be wrong that must be put right, whatever found it. Its date follows
    from its severity, and it closes only when someone other than its owner has confirmed
    that it is fixed."""

    __tablename__ = "issue"
    __subject__ = "issue"

    severity: Mapped[str] = mapped_column(String(16))
    # What found it (a test, a gap, an audit, an incident, a review, someone's own
    # observation), and, where there is one, the row it came from.
    source_kind: Mapped[str] = mapped_column(String(24), default="observation")
    source_type: Mapped[str | None] = mapped_column(String(24))
    source_id: Mapped[int | None] = mapped_column(Integer)
    due_on: Mapped[date] = mapped_column(Date)
    # Moving the date needs a reason; where it started and how often it moved stay here.
    original_due_on: Mapped[date] = mapped_column(Date)
    extensions: Mapped[list[dict[str, str]]] = mapped_column(JsonType, default=list)
    status: Mapped[str] = mapped_column(String(16), default="open")
    root_cause: Mapped[str | None] = mapped_column(String(40))
    closure_note: Mapped[str | None] = mapped_column(Text)
    proposed_by: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    proposed_by_name: Mapped[str | None] = mapped_column(String(200))
    proposed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    # What the person asked to confirm closure said when they sent it back.
    return_note: Mapped[str | None] = mapped_column(Text)
    validated_by: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    validated_by_name: Mapped[str | None] = mapped_column(String(200))
    validated_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    closed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint(one_of("severity", SEVERITIES), name="severity"),
        CheckConstraint(one_of("status", ISSUE_STATUSES), name="status"),
        Index("ix_issue_org_unit_id", "org_unit_id"),
        Index("ix_issue_status_due_on", "status", "due_on"),
        Index("ix_issue_source", "source_type", "source_id"),
    )


class IssueSubject(Base):
    """What an issue is about: a control, a requirement, a scope, or a risk."""

    __tablename__ = "issue_subject"
    __audit_parent__ = ("issue", "issue_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issue.id", ondelete="CASCADE"))
    subject_type: Mapped[str] = mapped_column(String(24))
    subject_id: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("issue_id", "subject_type", "subject_id", name="uq_issue_subject"),
        Index("ix_issue_subject_subject", "subject_type", "subject_id"),
    )


class ExceptionRequest(RecordMixin, Base):
    """A request to depart from a control or a requirement for a time, with what makes up
    for it, and the decision of someone with authority who did not ask."""

    __tablename__ = "exception_request"
    __subject__ = "exception"

    subject_type: Mapped[str] = mapped_column(String(24))
    subject_id: Mapped[int] = mapped_column(Integer)
    # Where it applies. An exception to a requirement is always within a scope; one to a
    # control may be within a scope, or wherever the control is relied on.
    scope_id: Mapped[int | None] = mapped_column(ForeignKey("scope.id"))
    justification: Mapped[str] = mapped_column(Text)
    compensating: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    requested_by_name: Mapped[str] = mapped_column(String(200))
    requested_at: Mapped[datetime] = mapped_column(UtcDateTime)
    starts_on: Mapped[date] = mapped_column(Date)
    expires_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="requested")
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    decided_by_name: Mapped[str | None] = mapped_column(String(200))
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    decision_note: Mapped[str | None] = mapped_column(Text)
    # The exception this one would carry on from, when it is a renewal.
    renews_id: Mapped[int | None] = mapped_column(ForeignKey("exception_request.id"))

    __table_args__ = (
        CheckConstraint(one_of("status", EXCEPTION_STATUSES), name="status"),
        CheckConstraint(one_of("subject_type", EXCEPTION_SUBJECTS), name="subject_type"),
        Index("ix_exception_request_org_unit_id", "org_unit_id"),
        Index("ix_exception_request_subject", "subject_type", "subject_id"),
        Index("ix_exception_request_scope_id", "scope_id"),
    )


class Notice(Base):
    """Something a person should know was assigned to them or changed for them. A pointer,
    not a record: the history holds what happened."""

    __tablename__ = "notice"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(String(400))
    href: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    read_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    # What became of it as email: queued, digest (waiting for a daily summary), or skipped.
    # Empty until the mailer has looked at it, which it does only where email is set up.
    mail_state: Mapped[str | None] = mapped_column(String(16))

    __table_args__ = (
        Index("ix_notice_account_id_read_at", "account_id", "read_at"),
        Index("ix_notice_mail_state", "mail_state"),
    )
