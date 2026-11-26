from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from riskwren import __version__
from riskwren.cli import build_parser, main
from riskwren.db import migrate
from riskwren.db.engine import Database
from tests.conftest import TESTER, Instance
from tests.models import Widget


def run(*args: str, config: Path | None = None) -> int:
    return main([*(["--config", str(config)] if config else []), *args])


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stopped:
        main(["--version"])
    assert stopped.value.code == 0
    assert capsys.readouterr().out.strip() == f"RiskWren {__version__}"


def test_no_command_shows_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "commands:" in capsys.readouterr().out


@pytest.mark.sqlite_only
def test_init_sets_up_everything(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = tmp_path / "riskwren.toml"
    assert run("init", config=config) == 0
    out = capsys.readouterr().out
    assert f"Wrote {config}" in out and "now at migration" in out and "riskwren serve" in out
    assert config.is_file() and (tmp_path / "var" / "riskwren.db").is_file()
    assert (tmp_path / "var" / ".riskwren-home").is_file()


@pytest.mark.sqlite_only
def test_init_again_changes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = tmp_path / "riskwren.toml"
    run("init", config=config)
    config.write_text(config.read_text() + "\n# mine\n")
    capsys.readouterr()
    assert run("init", config=config) == 0
    out = capsys.readouterr().out
    assert "Using the configuration" in out and "already at migration" in out
    assert config.read_text().endswith("# mine\n")


def test_init_on_the_configured_database(config_file: Path) -> None:
    """On PostgreSQL too: the address comes from the environment, as in production."""
    assert run("init", config=config_file) == 0
    assert run("db", "current", config=config_file) == 0


def test_a_missing_configuration_is_an_error_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run("verify", config=tmp_path / "absent.toml") == 1
    assert "riskwren init" in capsys.readouterr().err


def test_db_current_and_upgrade(instance: Instance, capsys: pytest.CaptureFixture[str]) -> None:
    assert run("db", "current", config=instance.path) == 0
    migrate.downgrade(instance.db.engine, "base")
    assert run("db", "current", config=instance.path) == 1
    assert "empty" in capsys.readouterr().out
    assert run("verify", config=instance.path) == 1
    assert "riskwren init" in capsys.readouterr().err
    assert run("db", "upgrade", config=instance.path) == 0
    assert "Upgraded" in capsys.readouterr().out
    assert run("db", "upgrade", config=instance.path) == 0
    assert "Already at" in capsys.readouterr().out


def test_verify_reports_a_whole_and_a_broken_history(
    instance: Instance, test_tables: None, capsys: pytest.CaptureFixture[str]
) -> None:
    db: Database = instance.db
    for name in ("a", "b"):
        with db.write(TESTER) as session:
            session.add(Widget(name=name))
    assert run("verify", config=instance.path) == 0
    assert "2 events" in capsys.readouterr().out
    with db.engine.begin() as conn:
        if db.dialect == "sqlite":
            conn.execute(text("DROP TRIGGER event_no_update"))
        else:
            conn.execute(text("ALTER TABLE event DISABLE TRIGGER USER"))
        conn.execute(text("UPDATE event SET actor_label = 'x' WHERE id = 1"))
    assert run("verify", config=instance.path) == 1
    assert "broken at event 1" in capsys.readouterr().err


def test_doctor_on_a_healthy_installation(
    instance: Instance, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run("doctor", config=instance.path) == 0
    out = capsys.readouterr().out
    for name in (
        "Python",
        "Configuration",
        "Data home",
        "Database",
        "Schema",
        "History guard",
        "History",
    ):
        assert name in out
    assert "Everything checks out." in out


def test_doctor_notices_a_missing_guard(
    instance: Instance, capsys: pytest.CaptureFixture[str]
) -> None:
    with instance.db.engine.begin() as conn:
        if instance.db.dialect == "sqlite":
            conn.execute(text("DROP TRIGGER event_no_delete"))
        else:
            conn.execute(text("DROP TRIGGER event_no_truncate ON event"))
    assert run("doctor", config=instance.path) == 1
    assert "no longer refuses changes" in capsys.readouterr().out


def test_doctor_before_init(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = tmp_path / "riskwren.toml"
    config.write_text("")
    assert run("doctor", config=config) == 1
    assert "riskwren init" in capsys.readouterr().out


def test_every_command_has_help_text() -> None:
    def walk(parser):  # type: ignore[no-untyped-def]
        for action in parser._actions:
            if hasattr(action, "choices") and isinstance(action.choices, dict):
                for choice in action._choices_actions:
                    assert choice.help, f"{choice.dest} has no help"
                for sub in action.choices.values():
                    assert sub.description, f"{sub.prog} has no description"
                    walk(sub)

    walk(build_parser())


def test_init_creates_the_first_administrator(
    config_file: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    from riskwren.config import load_config
    from riskwren.people import accounts

    monkeypatch.setattr("sys.stdin", io.StringIO("a long enough passphrase\n"))
    args = (
        "init",
        "--admin-email",
        "Dana@Northmere.example",
        "--admin-name",
        "Dana Okafor",
        "--password-stdin",
    )
    assert run(*args, config=config_file) == 0
    assert "Administrator: dana@northmere.example" in capsys.readouterr().out
    db = Database(load_config(config_file).database_url)
    try:
        with db.read() as session:
            dana = accounts.authenticate(
                session, "dana@northmere.example", "a long enough passphrase"
            )
            assert dana is not None and accounts.active_admins(session) == 1
    finally:
        db.dispose()
    assert run("init", config=config_file) == 0  # and again: nothing more to do
    assert "Administrator" not in capsys.readouterr().out


def test_init_without_an_administrator_says_how_to_make_one(
    config_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run("init", config=config_file) == 0
    assert "users add" in capsys.readouterr().out
    assert run("serve", config=config_file) == 1
    assert "there is no administrator yet" in capsys.readouterr().err


def test_a_weak_first_password_is_explained(
    config_file: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("short\n"))
    assert (
        run(
            "init",
            "--admin-email",
            "dana@northmere.example",
            "--password-stdin",
            config=config_file,
        )
        == 1
    )
    assert "at least 12 characters" in capsys.readouterr().err


def test_users_from_the_command_line(
    instance: Instance, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    from riskwren.people import accounts, units
    from tests.people import ME

    with instance.db.write(ME.actor) as session:
        root = units.create(
            session, ME, name="Northmere Institute", kind="organization", code="NMI"
        )
        units.create(session, ME, name="Hale Lab", kind="lab", code="HALE", parent_id=root.id)

    def users(*args: str, stdin: str = "") -> tuple[int, str, str]:
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
        code = run("users", *args, config=instance.path)
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    assert users("list")[1].startswith("No accounts yet")
    secret = "a long enough passphrase\n"
    code, out, _ = users(
        "add",
        "dana@northmere.example",
        "--name",
        "Dana Okafor",
        "--role",
        "admin",
        "--password-stdin",
        stdin=secret,
    )
    assert code == 0 and "Added dana@northmere.example (active): admin" in out
    code, out, _ = users(
        "add",
        "lee@northmere.example",
        "--name",
        "Lee Park",
        "--invite",
        "--role",
        "steward=unit:HALE",
        "--role",
        "leader=unit:NMI,limit:high",
        "--unit",
        "HALE",
    )
    assert code == 0 and "(invited): steward=HALE, leader=NMI (accepts up to high)" in out
    assert (
        users("add", "dana@northmere.example", "--name", "Again", "--invite")[2].count(
            "already an account"
        )
        == 1
    )
    assert (
        "no unit with the code NOPE"
        in users(
            "add", "x@northmere.example", "--name", "X", "--invite", "--role", "steward=unit:NOPE"
        )[2]
    )
    assert (
        "not a role"
        in users("add", "x@northmere.example", "--name", "X", "--invite", "--role", "wizard")[2]
    )

    listing = users("list")[1]
    assert (
        "dana@northmere.example  active" in listing
        and "[steward=HALE, leader=NMI (accepts up to high)]" in listing
    )
    assert (
        users("roles", "lee@northmere.example")[1].strip()
        == "lee@northmere.example: steward=HALE, leader=NMI (accepts up to high)"
    )
    assert (
        users("roles", "lee@northmere.example", "--set", "auditor")[1].strip()
        == "lee@northmere.example: auditor"
    )
    assert (
        users("roles", "lee@northmere.example", "--set")[1].strip()
        == "lee@northmere.example: member"
    )
    code, _, err = users("roles", "dana@northmere.example", "--set")
    assert code == 1 and "last active administrator" in err

    assert (
        users(
            "reset-password",
            "lee@northmere.example",
            "--password-stdin",
            stdin="another long passphrase\n",
        )[0]
        == 0
    )
    assert (
        users("disable", "lee@northmere.example")[1].strip()
        == "lee@northmere.example is now disabled."
    )
    with instance.db.read() as session:
        assert (
            accounts.authenticate(session, "lee@northmere.example", "another long passphrase")
            is None
        )
    assert users("enable", "lee@northmere.example")[0] == 0
    with instance.db.read() as session:
        assert (
            accounts.authenticate(session, "lee@northmere.example", "another long passphrase")
            is not None
        )
    assert users("disable", "dana@northmere.example")[2].count("last active administrator") == 1
    code, _, err = users("disable", "ghost@northmere.example")
    assert code == 1 and "no account for ghost@northmere.example" in err
    assert run("verify", config=instance.path) == 0
