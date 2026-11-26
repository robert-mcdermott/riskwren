"""Scheduled work: each job's next turn, the log of its runs, which reminders have gone, and
the email waiting to be sent. None of it is history."""

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
from riskwren.db.types import JsonType, UtcDateTime


class Job(Base):
    """One piece of scheduled work and when it is next due. A process claims the row before
    it runs the job, so that no two run it at once."""

    __tablename__ = "job"
    __audit__ = False

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[datetime] = mapped_column(UtcDateTime)
    claimed_until: Mapped[datetime | None] = mapped_column(UtcDateTime)
    last_started_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    last_finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    last_status: Mapped[str | None] = mapped_column(String(16))
    last_summary: Mapped[str | None] = mapped_column(String(300))


class JobRun(Base):
    """A run that did something, or failed. Runs that found nothing to do are not kept."""

    __tablename__ = "job_run"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_key: Mapped[str] = mapped_column(String(40))
    started_at: Mapped[datetime] = mapped_column(UtcDateTime)
    finished_at: Mapped[datetime] = mapped_column(UtcDateTime)
    status: Mapped[str] = mapped_column(String(16))
    counts: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    error: Mapped[str | None] = mapped_column(String(600))

    __table_args__ = (
        CheckConstraint("status IN ('ok', 'failed')", name="status"),
        Index("ix_job_run_job_key", "job_key", "id"),
    )


class Reminder(Base):
    """That a reminder about something due on a date has been sent at a stage, so that it is
    sent once. Moving the date starts again."""

    __tablename__ = "reminder"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(24))
    subject_id: Mapped[int] = mapped_column(Integer)
    due_on: Mapped[date] = mapped_column(Date)
    stage: Mapped[str] = mapped_column(String(24))
    sent_on: Mapped[date] = mapped_column(Date)

    __table_args__ = (UniqueConstraint("subject_type", "subject_id", "due_on", "stage"),)


class OutboxMessage(Base):
    """An email waiting to be sent, or sent. Kept in the database so that a restart loses
    nothing."""

    __tablename__ = "outbox_message"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"))
    to_address: Mapped[str] = mapped_column(String(254))
    subject: Mapped[str] = mapped_column(String(300))
    body_text: Mapped[str] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16), default="notice")
    digest_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    send_after: Mapped[datetime] = mapped_column(UtcDateTime)
    sent_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    __table_args__ = (
        UniqueConstraint("account_id", "digest_on"),
        CheckConstraint("status IN ('queued', 'sending', 'sent', 'failed')", name="status"),
        Index("ix_outbox_message_status", "status", "send_after"),
    )
