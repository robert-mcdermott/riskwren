"""Reading and changing program settings."""

from __future__ import annotations

import copy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.core.clock import utc_now
from riskwren.db.models import Setting


def get(session: Session, key: str, default: Any = None) -> Any:
    """A setting's value, or the default. The value is a copy: changing it changes nothing."""
    row = session.scalars(select(Setting).where(Setting.key == key)).first()
    return copy.deepcopy(row.value) if row is not None else default


def put(session: Session, key: str, value: Any) -> bool:
    """Set a setting. Returns whether anything changed. Permission is the caller's to check."""
    row = session.scalars(select(Setting).where(Setting.key == key)).first()
    if row is None:
        session.add(Setting(key=key, value=copy.deepcopy(value), updated_at=utc_now()))
        session.flush()
        return True
    if row.value == value:
        return False
    row.value = copy.deepcopy(value)
    row.updated_at = utc_now()
    session.flush()
    return True
