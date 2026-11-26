"""Models that exist only for tests of the machinery every real model relies on.

Their tables are named ``test_…`` and are created by the fixtures that need them, never by a
migration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from riskwren.db.base import Base
from riskwren.db.types import JsonType, UtcDateTime


class Widget(Base):
    __tablename__ = "test_widget"
    __subject__ = "widget"
    __audit_redact__ = frozenset({"secret"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref: Mapped[str | None] = mapped_column(String(24))
    name: Mapped[str] = mapped_column(String(100))
    size: Mapped[int | None] = mapped_column(Integer)
    secret: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    seen_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class Part(Base):
    __tablename__ = "test_part"
    __subject__ = "part"
    __audit_parent__ = ("widget", "widget_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    widget_id: Mapped[int] = mapped_column(ForeignKey("test_widget.id"))
    label: Mapped[str] = mapped_column(String(100))


class Scratch(Base):
    __tablename__ = "test_scratch"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    note: Mapped[str] = mapped_column(String(100))


TEST_TABLES = [Widget.__table__, Part.__table__, Scratch.__table__]
