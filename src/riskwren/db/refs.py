"""Permanent, human-readable references: ``UC-0142``."""

from __future__ import annotations

import re

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from riskwren.db.models.system import Counter

# Every prefix RiskWren gives out. Each is seeded by the migration that introduces its record.
PREFIXES = {
    "PRC": "Process",
    "SYS": "System",
    "TP": "Third party",
    "INF": "Information asset",
    "RSK": "Risk",
    "CTL": "Control",
    "PLN": "Treatment plan",
    "ACT": "Action",
    "SCP": "Scope",
    "ASM": "Assessment",
    "EV": "Evidence",
    "ISS": "Issue",
    "EXC": "Exception",
    "IND": "Indicator",
    "POL": "Policy document",
    "AGR": "Agreement",
    "AUD": "Audit engagement",
    "INC": "Incident",
}
REF_PATTERN = re.compile(r"^([A-Z]{2,4})-(\d{4,})$")


def format_ref(prefix: str, number: int) -> str:
    return f"{prefix}-{number:04d}"


def next_ref(session: Session, prefix: str) -> str:
    """Take the next number for a prefix, inside the caller's transaction.

    The counter row is locked by the update, so two transactions never get the same number.
    A reference that reaches the database is never given out again."""
    if prefix not in PREFIXES:
        raise ValueError(f"Unknown reference prefix {prefix!r}")
    conn = session.connection()
    updated = conn.execute(
        update(Counter).where(Counter.prefix == prefix).values(value=Counter.value + 1)
    )
    if updated.rowcount == 0:
        conn.execute(insert(Counter).values(prefix=prefix, value=1))
        return format_ref(prefix, 1)
    number = conn.execute(select(Counter.value).where(Counter.prefix == prefix)).scalar_one()
    return format_ref(prefix, number)


def parse_ref(text: str) -> tuple[str, int] | None:
    match = REF_PATTERN.match(text.strip().upper())
    if not match or match.group(1) not in PREFIXES:
        return None
    return match.group(1), int(match.group(2))
