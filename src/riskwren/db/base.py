"""The declarative base every model inherits from."""

from __future__ import annotations

from typing import ClassVar

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Fixed names for every constraint, so a migration finds the same names on both databases.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base for all models.

    Every model is audited unless it says otherwise: a change to one of its rows writes an
    event in the same transaction (see ``riskwren.events.audit``).

    ``__audit__``           False for bookkeeping tables whose changes are not history.
    ``__audit_redact__``    Columns whose values never appear in an event, only that they changed.
    ``__audit_skip__``      Columns that are bookkeeping and never appear in an event at all.
    ``__audit_parent__``    ``(subject_type, column)`` naming the record a child row belongs to,
                            so the change also shows in that record's history.
                            ``("@column", column)`` reads the type from the row.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    __audit__: ClassVar[bool] = True
    __audit_redact__: ClassVar[frozenset[str]] = frozenset()
    __audit_parent__: ClassVar[tuple[str, str] | None] = None
    __audit_skip__: ClassVar[frozenset[str]] = frozenset()
