"""The program's tables of rules: how often things come due, who may accept what, how a
third party is tiered, and which agreements shared information needs.

Like the vocabularies, each starts from the default program pack and is kept as a setting
once an organization changes it.
"""

from __future__ import annotations

import copy
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from riskwren.program import settings, vocab

NAMES = ("cadences", "authority", "tiering", "sharing")


def get(session: Session, name: str) -> dict[str, Any]:
    """The table in force. A rule a later release adds is taken from the default program
    until the organization sets it, so a table saved before it was known still has it."""
    if name not in NAMES:
        raise KeyError(name)
    defaults = copy.deepcopy(vocab.default_pack()[name])
    stored = settings.get(session, f"rules.{name}", None)
    return {**defaults, **stored} if stored is not None else defaults


def put(session: Session, name: str, value: dict[str, Any]) -> bool:
    if name not in NAMES:
        raise KeyError(name)
    return settings.put(session, f"rules.{name}", value)


def add_months(start: date, months: int) -> date:
    """The same day so many months on, or the last day of that month if it is shorter."""
    index = start.month - 1 + months
    year, month = start.year + index // 12, index % 12 + 1
    for day in (start.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    raise AssertionError("every month has a 28th")
