"""Alembic environment.

RiskWren drives Alembic from ``riskwren.db.migrate``. A live connection is handed in through
``config.attributes`` so that a migration runs in the caller's transaction.
"""

from __future__ import annotations

from alembic import context

import riskwren.db.models  # noqa: F401  (registers every model on the metadata)
from riskwren.db.base import Base
from riskwren.db.engine import make_engine

config = context.config
metadata = Base.metadata


def _configure(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=metadata,
        render_as_batch=connection.dialect.name == "sqlite",  # SQLite needs batch ALTERs
        compare_type=True,
        user_module_prefix="riskwren.db.types.",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=metadata,
        literal_binds=True,
        render_as_batch=True,
        user_module_prefix="riskwren.db.types.",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _configure(connection)
        return
    engine = make_engine(config.get_main_option("sqlalchemy.url") or "")
    try:
        with engine.begin() as conn:
            _configure(conn)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
