"""Program settings: what the program team and administrators configure in the app."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from riskwren.db.base import Base
from riskwren.db.types import JsonType, UtcDateTime


class Setting(Base):
    """One named program setting, as a JSON value (ADR-0010).

    The value is replaced whole, never changed in place, so that the history sees the change.
    """

    __tablename__ = "setting"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    value: Mapped[Any] = mapped_column(JsonType)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime)
