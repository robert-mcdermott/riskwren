"""A session that only reads looks a setting, the units, or the categories up once; a session
that writes always asks, so it sees its own changes."""

from __future__ import annotations

from sqlalchemy import event

from riskwren.db.engine import Database
from riskwren.people import units
from riskwren.program import settings
from tests.people import ME, People


def test_reading_asks_once_and_writing_sees_its_own_changes(db: Database, people: People) -> None:
    asked: list[str] = []

    def count(_conn, _cursor, statement, *_args) -> None:  # type: ignore[no-untyped-def]
        asked.append(statement)

    event.listen(db.engine, "before_cursor_execute", count)
    try:
        with db.write(ME.actor) as session:
            settings.put(session, "example.kept", {"a": 1})
            assert settings.get(session, "example.kept") == {"a": 1}
            settings.put(session, "example.kept", {"a": 2})
            assert settings.get(session, "example.kept") == {"a": 2}
        with db.read() as session:
            asked.clear()
            first = settings.get(session, "example.kept")
            first["a"] = 99  # a copy: changing it changes nothing
            assert settings.get(session, "example.kept") == {"a": 2}
            assert settings.get(session, "example.never", "none") == "none"
            assert settings.get(session, "example.never", "none") == "none"
            names = [unit.name for unit in units.all_units(session)]
            assert [unit.name for unit in units.all_units(session)] == names
            looked = [s for s in asked if "FROM setting" in s or "FROM org_unit" in s]
            assert len(looked) == 3  # one for each setting, one for the units
    finally:
        event.remove(db.engine, "before_cursor_execute", count)
