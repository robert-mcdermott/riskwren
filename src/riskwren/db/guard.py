"""Keep a token's stand-in account number out of the database.

A token acts as a role, never as a person, and its principal carries a negative account number
that no account has, so that nothing compares equal to it: no record is ever its own by
creator, owner, or author, in Python or in SQL (where ``None`` would have matched every empty
column). Services that write ``principal.account_id`` into a column that names a person store
``None`` instead, as they always have for a command; the history names the token.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session


def _names_a_person(column: Any) -> bool:
    if any(fk.column.table.name == "account" for fk in column.foreign_keys):
        return True
    return column.name.endswith("_by")


def _clear(session: Session, _context: Any, _instances: Any) -> None:
    for obj in list(session.new) + list(session.dirty):
        state = inspect(obj)
        for column in state.mapper.columns:
            if not _names_a_person(column):
                continue
            key = state.mapper.get_property_by_column(column).key
            value = state.dict.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value < 0:
                setattr(obj, key, None)


def install() -> None:
    if not event.contains(Session, "before_flush", _clear):
        event.listen(Session, "before_flush", _clear)
