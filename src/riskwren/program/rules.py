"""The program's tables of rules: how often things come due, and who may accept what.

Like the vocabularies, each starts from the default program pack and is kept as a setting
once an organization changes it.
"""

from __future__ import annotations

import copy
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from riskwren.program import settings, vocab

NAMES = ("cadences", "authority")


def get(session: Session, name: str) -> dict[str, Any]:
    if name not in NAMES:
        raise KeyError(name)
    stored = settings.get(session, f"rules.{name}", None)
    return stored if stored is not None else copy.deepcopy(vocab.default_pack()[name])


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
