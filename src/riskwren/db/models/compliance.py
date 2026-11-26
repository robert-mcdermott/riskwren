"""What the organization is held to: frameworks, their requirements, and baselines."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
from riskwren.db.types import UtcDateTime

FRAMEWORK_KINDS = ("standard", "regulation", "agreement", "internal")
# What text a framework may carry (see spec/content-packs.md). ``own`` is the organization's
# own framework, entered here: its text is the organization's to hold and never ships.
TEXT_POLICIES = ("verbatim", "attributed", "identifiers", "summary", "own")
ORIGINS = ("pack", "local")
FRAMEWORK_STATUSES = ("active", "retired")
REQUIREMENT_STATUSES = ("active", "withdrawn")


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
    # False for a heading that only groups others: a family, a function, a section.
    is_citable: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(16), default="active")

    __table_args__ = (
        UniqueConstraint("framework_id", "code", name="uq_requirement_framework_code"),
        CheckConstraint(one_of("status", REQUIREMENT_STATUSES), name="status"),
        Index("ix_requirement_parent", "framework_id", "parent_id", "position"),
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
