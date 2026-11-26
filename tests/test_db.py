from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import StatementError

from riskwren.core.errors import StoreError
from riskwren.db import migrate
from riskwren.db.base import Base
from riskwren.db.engine import Database, make_engine
from tests import models
from tests.conftest import TESTER, Instance
from tests.models import Widget


def test_unsupported_databases_are_refused() -> None:
    with pytest.raises(StoreError, match="Unsupported"):
        make_engine("mysql://localhost/g")


@pytest.mark.sqlite_only
def test_a_missing_directory_is_explained(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(StoreError, match="riskwren init"):
        make_engine(f"sqlite:///{tmp_path / 'nowhere' / 'g.db'}")


@pytest.mark.sqlite_only
def test_sqlite_is_set_up_for_safety(db: Database) -> None:
    with db.engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_times_are_utc_and_never_naive(db: Database, test_tables: None) -> None:
    seattle = timezone(timedelta(hours=-8))
    moment = datetime(2026, 3, 1, 9, 30, 15, 123456, tzinfo=seattle)
    with db.write(TESTER) as session:
        session.add(Widget(name="clock", seen_at=moment))
    with db.read() as session:
        stored = session.scalars(select(Widget.seen_at)).one()
    assert stored == moment
    assert stored.tzinfo is UTC
    with pytest.raises(StatementError, match="timezone-aware"), db.write(TESTER) as session:
        session.add(Widget(name="naive", seen_at=datetime(2026, 3, 1)))


def test_json_round_trips(db: Database, test_tables: None) -> None:
    details = {"tags": ["a", "b"], "n": 3, "nested": {"ok": True, "none": None}, "text": "café"}
    with db.write(TESTER) as session:
        session.add(Widget(name="json", details=details))
    with db.read() as session:
        assert session.scalars(select(Widget.details)).one() == details


def test_a_failed_write_changes_nothing(db: Database, test_tables: None) -> None:
    with pytest.raises(RuntimeError), db.write(TESTER) as session:
        session.add(Widget(name="doomed"))
        session.flush()
        raise RuntimeError("stop")
    with db.read() as session:
        assert session.scalars(select(Widget)).all() == []
    with db.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM event")).scalar() == 0


def test_migrations_build_exactly_what_the_models_describe(db: Database) -> None:
    from alembic.autogenerate import compare_metadata
    from alembic.runtime.migration import MigrationContext

    def real_tables(obj, name, type_, reflected, compare_to):  # type: ignore[no-untyped-def]
        table = name if type_ == "table" else getattr(getattr(obj, "table", None), "name", "")
        return not str(table).startswith("test_")

    with db.engine.connect() as conn:
        context = MigrationContext.configure(
            conn, opts={"compare_type": True, "include_object": real_tables}
        )
        assert compare_metadata(context, Base.metadata) == []


def test_migrations_go_down_and_up_again(instance: Instance) -> None:
    engine = instance.db.engine
    assert migrate.is_current(engine)
    migrate.downgrade(engine, "base")
    assert migrate.current_revision(engine) is None
    migrate.upgrade(engine)
    assert migrate.is_current(engine)


def test_a_database_that_is_behind_is_refused(instance: Instance) -> None:
    engine = instance.db.engine
    migrate.downgrade(engine, "base")
    with pytest.raises(StoreError, match="riskwren init"):
        migrate.require_current(engine)


def test_the_test_models_are_not_in_any_migration() -> None:
    assert all(table.name.startswith("test_") for table in models.TEST_TABLES)
