"""Third parties as a program (TPR): how much is at stake with each, and what is known.

A third party and its services are records of the inventory (``inventory.py``). What this
module holds is what is learned about them: each tiering, a judgment by a named person.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from riskwren.db.base import Base
from riskwren.db.types import JsonType, UtcDateTime


class TierAssessment(Base):
    """A tiering: the answers given, what the inventory said, the tier the program's rules
    gave and why, and the tier the person recorded. Never edited: tiering again supersedes
    it, and it stays."""

    __tablename__ = "tier_assessment"
    __audit_parent__ = ("third_party", "third_party_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    third_party_id: Mapped[int] = mapped_column(ForeignKey("third_party.id"))
    answers: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    # What the inventory said at the time: the most sensitive information, the most
    # critical work that relies on it, and the systems its services reach.
    facts: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    questionnaire_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("questionnaire_version.id")
    )
    suggested: Mapped[str] = mapped_column(String(24))
    reasons: Mapped[list[str]] = mapped_column(JsonType, default=list)
    tier: Mapped[str] = mapped_column(String(24))
    rationale: Mapped[str | None] = mapped_column(Text)  # needed when tier differs
    assessed_by: Mapped[int | None] = mapped_column(Integer)
    assessed_by_name: Mapped[str] = mapped_column(String(200))
    assessed_at: Mapped[datetime] = mapped_column(UtcDateTime)
    superseded_by: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (Index("ix_tier_assessment_third_party_id", "third_party_id"),)
