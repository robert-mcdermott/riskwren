"""Shared fixtures. The whole suite runs on SQLite, and again on PostgreSQL when
``RISKWREN_TEST_DATABASE=postgres`` and ``RISKWREN_TEST_POSTGRES_URL`` are set."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from riskwren.api.app import create_app
from riskwren.config import Config, example_config_text, load_config
from riskwren.db import migrate
from riskwren.db.base import Base
from riskwren.db.engine import Database
from riskwren.events.actor import Actor
from riskwren.home import DataHome
from riskwren.program import packs
from tests import models

POSTGRES = os.environ.get("RISKWREN_TEST_DATABASE", "").lower() == "postgres"
POSTGRES_URL = os.environ.get("RISKWREN_TEST_POSTGRES_URL", "")
KEEP = {"RISKWREN_TEST_DATABASE", "RISKWREN_TEST_POSTGRES_URL"}

TESTER = Actor.command("Tester")


def pytest_configure(config: pytest.Config) -> None:
    if POSTGRES and not POSTGRES_URL:
        raise pytest.UsageError("RISKWREN_TEST_DATABASE=postgres needs RISKWREN_TEST_POSTGRES_URL")


def pytest_report_header(config: pytest.Config) -> str:
    return f"database: {'PostgreSQL' if POSTGRES else 'SQLite'}"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        if POSTGRES and "sqlite_only" in item.keywords:
            item.add_marker(pytest.mark.skip(reason="about the SQLite database file"))
        if not POSTGRES and "postgres" in item.keywords:
            item.add_marker(pytest.mark.skip(reason="needs PostgreSQL (scripts/test-both.sh)"))


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith("RISKWREN_") and name not in KEEP:
            monkeypatch.delenv(name)


@pytest.fixture(autouse=True)
def _cheap_passwords(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hashing is deliberately slow; tests hash hundreds of passwords."""
    from riskwren.auth import passwords

    monkeypatch.setattr(passwords, "SCRYPT_N", 2**8)


@pytest.fixture
def database_url() -> Iterator[str]:
    """Empty for SQLite (a file in the data home), or a fresh PostgreSQL database."""
    if not POSTGRES:
        yield ""
        return
    name = f"t_{uuid.uuid4().hex[:24]}"
    admin = create_engine(POSTGRES_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield make_url(POSTGRES_URL).set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def config_file(tmp_path: Path, database_url: str, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "riskwren.toml"
    path.write_text(example_config_text(), encoding="utf-8")
    if database_url:
        monkeypatch.setenv("RISKWREN_DATABASE_URL", database_url)
    # Tests run scheduled work themselves, when they mean to.
    monkeypatch.setenv("RISKWREN_SERVER_SCHEDULER", "false")
    return path


@dataclass
class Instance:
    path: Path
    config: Config
    home: DataHome
    db: Database


@pytest.fixture
def instance(config_file: Path) -> Iterator[Instance]:
    """An initialized installation: configuration, data home, and a migrated database."""
    config = load_config(config_file)
    home = DataHome(config.data.home)
    home.create()
    db = Database(config.database_url)
    migrate.upgrade(db.engine)
    try:
        yield Instance(config_file, config, home, db)
    finally:
        db.dispose()


@pytest.fixture
def db(instance: Instance) -> Database:
    return instance.db


@pytest.fixture
def test_tables(db: Database) -> None:
    """Create the tables of the test-only models (see ``tests/models.py``)."""
    Base.metadata.create_all(db.engine, tables=models.TEST_TABLES)


@pytest.fixture
def client(instance: Instance) -> Iterator[TestClient]:
    with TestClient(create_app(instance.config), base_url="http://localhost") as test_client:
        yield test_client


@pytest.fixture
def full_client(instance: Instance) -> Iterator[TestClient]:
    """A client of an app with every optional part turned on, for the API's own documents."""
    from dataclasses import replace

    from riskwren.config import AssistantConfig

    on = AssistantConfig(enabled=True, model="m", url="http://127.0.0.1:9/v1")
    app = create_app(replace(instance.config, assistant=on))
    with TestClient(app, base_url="http://localhost") as test_client:
        yield test_client


@pytest.fixture
def people(instance: Instance):  # type: ignore[no-untyped-def]
    """A small organization with one person in each role (see ``tests/people.py``), and the
    default program."""
    from tests.people import seed

    with instance.db.write(Actor.command("Setup")) as session:
        # The default program, as `riskwren init` loads it. The public frameworks are left
        # out here for speed; the tests about them load them.
        packs.install(session, frameworks=False)
    return seed(instance.db)


@pytest.fixture
def as_role(instance: Instance, people) -> Iterator[Callable[[str | None], TestClient]]:  # type: ignore[no-untyped-def]
    """A factory of clients, each signed in as the person with the given role (None: nobody)."""
    from tests.people import email_of, sign_in

    with ExitStack() as stack:
        app = create_app(instance.config)

        def make(role: str | None) -> TestClient:
            client = stack.enter_context(TestClient(app, base_url="http://localhost"))
            return sign_in(client, email_of(role)) if role else client

        yield make
