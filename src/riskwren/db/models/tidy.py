"""Keeping the record in order: saved views, pairs that are not duplicates, and what was
handed on when someone left (INV-10, INV-12, OVS-08)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from riskwren.db.base import Base
from riskwren.db.types import UtcDateTime


class SavedView(Base):
    """A list as someone filtered and sorted it, kept under a name. It holds the filters
    and never the results, so whoever opens it sees only what they may see."""

    __tablename__ = "saved_view"
    __audit__ = False  # a convenience of one person's, not part of the record

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"))
    owner_name: Mapped[str] = mapped_column(String(200))
    path: Mapped[str] = mapped_column(String(80))  # the list: /risks
    name: Mapped[str] = mapped_column(String(80))
    query: Mapped[str] = mapped_column(String(1000))  # its filters, as the address has them
    shared: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (
        UniqueConstraint("account_id", "path", "name"),
        Index("ix_saved_view_path", "path"),
    )


class NotDuplicate(Base):
    """Two records that look alike and that someone has said are different things."""

    __tablename__ = "not_duplicate"
    __audit_parent__ = ("@record_type", "low_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_type: Mapped[str] = mapped_column(String(24))
    low_id: Mapped[int] = mapped_column(Integer)
    high_id: Mapped[int] = mapped_column(Integer)
    said_by_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (UniqueConstraint("record_type", "low_id", "high_id"),)


class Handover(Base):
    """Something a person answered for when their account was disabled, and who has it
    now. It is kept until someone is named for good, so that what a person left behind can
    be seen and passed on in one step."""

    __tablename__ = "handover"
    __audit__ = False  # the change of owner is recorded on the thing itself

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    subject_type: Mapped[str] = mapped_column(String(24))  # a record type, action, campaign_item
    subject_id: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(24), default="owner")
    held_by: Mapped[int] = mapped_column(ForeignKey("account.id"))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (
        UniqueConstraint("from_account_id", "subject_type", "subject_id", "kind"),
        Index("ix_handover_held_by", "held_by"),
    )
