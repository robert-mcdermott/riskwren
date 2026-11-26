"""Bookkeeping tables: the history, the head of its hash chain, and reference counters."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from riskwren.db.base import Base
from riskwren.db.types import JsonType, UtcDateTime


class Event(Base):
    """One entry in the append-only history (ADR-0006).

    ``id`` is the event's place in the chain: it is assigned from ``chain_head`` under a lock,
    never by the database, so the order of ids is the order of the chain with no gaps.
    """

    __tablename__ = "event"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    at: Mapped[datetime] = mapped_column(UtcDateTime)
    actor_kind: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[int | None] = mapped_column(Integer)
    actor_label: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(80))
    subject_type: Mapped[str] = mapped_column(String(40))
    subject_id: Mapped[int | None] = mapped_column(Integer)
    subject_ref: Mapped[str | None] = mapped_column(String(24))
    parent_type: Mapped[str | None] = mapped_column(String(40))
    parent_id: Mapped[int | None] = mapped_column(Integer)
    changes: Mapped[dict[str, Any]] = mapped_column(JsonType)
    context: Mapped[dict[str, Any]] = mapped_column(JsonType)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))

    __table_args__ = (
        Index("ix_event_subject", "subject_type", "subject_id", "id"),
        Index("ix_event_parent", "parent_type", "parent_id", "id"),
        Index("ix_event_actor", "actor_id", "id"),
        Index("ix_event_at", "at"),
    )


class ChainHead(Base):
    """The single row that says where the history's chain ends. Locked to append."""

    __tablename__ = "chain_head"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    seq: Mapped[int] = mapped_column(Integer)
    hash: Mapped[str] = mapped_column(String(64))

    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)


class Counter(Base):
    """The last number given out for each reference prefix (``UC`` → ``UC-0142``)."""

    __tablename__ = "counter"
    __audit__ = False

    prefix: Mapped[str] = mapped_column(String(8), primary_key=True)
    value: Mapped[int] = mapped_column(Integer)
