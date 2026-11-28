"""Engines and sessions for SQLite and PostgreSQL."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from riskwren.core.errors import StoreError
from riskwren.db import guard
from riskwren.events.actor import Actor
from riskwren.events.audit import AuditedSession

guard.install()  # a token's stand-in account number is never stored


def _sqlite_pragmas(dbapi_connection: Any, _record: Any) -> None:
    # Python's sqlite3 driver starts transactions itself, but not before schema changes, so a
    # failed migration would keep half its work. Turn that off and let SQLAlchemy say BEGIN
    # (see _sqlite_begin): every transaction then commits or rolls back whole.
    dbapi_connection.isolation_level = None
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")  # readers never block the writer
        cursor.execute("PRAGMA synchronous=NORMAL")  # safe with WAL, much faster than FULL
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
    finally:
        cursor.close()


def _sqlite_begin(conn: Any) -> None:
    # A transaction that will write takes the write lock at once. Otherwise two requests could
    # each read, then both try to write, and the second would fail instead of waiting.
    writing = conn.get_execution_options().get("riskwren_write", False)
    conn.exec_driver_sql("BEGIN IMMEDIATE" if writing else "BEGIN")


def set_sqlite_pragma(conn: Any, pragma: str) -> None:
    """Run a PRAGMA outside any transaction (some, like foreign_keys, are ignored inside one)."""
    conn.connection.dbapi_connection.execute(f"PRAGMA {pragma}")


def make_engine(url: str, *, echo: bool = False) -> Engine:
    """Create an engine for a ``sqlite:///`` or ``postgresql+psycopg://`` address."""
    parsed = make_url(url)
    backend = parsed.get_backend_name()
    if backend == "sqlite":
        database = parsed.database or ""
        if database and database != ":memory:":
            parent = Path(database).parent
            if not parent.is_dir():
                raise StoreError(
                    f"The database directory {parent} does not exist. Run `riskwren init`."
                )
        # A failed statement's values (a report's words, an answer) never reach the log.
        engine = create_engine(url, echo=echo, hide_parameters=True)
        event.listen(engine, "connect", _sqlite_pragmas)
        event.listen(engine, "begin", _sqlite_begin)
        return engine
    if backend == "postgresql":
        try:
            return create_engine(url, echo=echo, pool_pre_ping=True, hide_parameters=True)
        except ModuleNotFoundError as exc:
            raise StoreError(
                "PostgreSQL needs the optional driver: run `uv sync --extra postgres`."
            ) from exc
    raise StoreError(f"Unsupported database {parsed.render_as_string(hide_password=True)}")


class Database:
    """An engine and the two kinds of session the application uses.

    ``read()`` gives a session for looking things up. ``write(actor)`` gives one that commits
    when its block ends and records an event for every change, attributed to ``actor``.
    """

    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.engine = make_engine(url, echo=echo)
        self._read = sessionmaker(self.engine, class_=AuditedSession, expire_on_commit=False)
        self._write = sessionmaker(
            self.engine.execution_options(riskwren_write=True),
            class_=AuditedSession,
            expire_on_commit=False,
        )

    @property
    def dialect(self) -> str:
        return self.engine.dialect.name

    @contextmanager
    def read(self) -> Iterator[Session]:
        session = self._read()
        session.info["reading"] = True  # see riskwren.db.remember
        try:
            yield session
        finally:
            session.close()  # ends the transaction; what was loaded stays readable

    @contextmanager
    def write(
        self, actor: Actor, *, action: str | None = None, context: dict[str, Any] | None = None
    ) -> Iterator[Session]:
        session = self._write()
        session.info["actor"] = actor
        if action:
            session.info["action"] = action
        if context:
            session.info["context"] = dict(context)
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    @contextmanager
    def bookkeeping(self) -> Iterator[Session]:
        """A committing session with no actor, for rows that are not history: sign-in
        sessions and failed sign-ins. Changing an audited row in one is refused."""
        session = self._write()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()
