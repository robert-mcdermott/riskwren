"""What a request that only reads may look up once and use again.

A page that counts across the register asks for the same settings, units, and categories many
times over. Inside a session opened with ``Database.read`` nothing can change them, so the
first answer is kept for the rest of that session. A session that writes always asks the
database, so it sees its own changes.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable

from sqlalchemy.orm import Session

READING = "reading"


def remembered[T](session: Session, key: Hashable, load: Callable[[], T]) -> T:
    """``load()`` once per reading session; every time in a session that writes."""
    if not session.info.get(READING):
        return load()
    kept = session.info.setdefault("remembered", {})
    if key not in kept:
        kept[key] = load()
    return kept[key]  # type: ignore[no-any-return]
