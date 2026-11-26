from __future__ import annotations

from pathlib import Path

import pytest

from riskwren.config import (
    Config,
    config_warnings,
    example_config_text,
    find_config_path,
    load_config,
    parse_config,
)
from riskwren.core.errors import ConfigError

REPO = Path(__file__).resolve().parent.parent


def parse(text: str, tmp_path: Path, env: dict[str, str] | None = None) -> Config:
    path = tmp_path / "riskwren.toml"
    path.write_text(text, encoding="utf-8")
    return load_config(path, env=env or {})


def test_the_example_is_a_valid_configuration(tmp_path: Path) -> None:
    config = parse(example_config_text(), tmp_path)
    assert config.server.host == "127.0.0.1"
    assert config.server.port == 8000
    assert config.uses_sqlite
    assert config.database_url == f"sqlite:///{tmp_path / 'var' / 'riskwren.db'}"


def test_the_example_at_the_repository_root_is_the_packaged_one() -> None:
    assert (REPO / "riskwren.example.toml").read_text(encoding="utf-8") == example_config_text()


def test_an_empty_file_gives_the_defaults(tmp_path: Path) -> None:
    config = parse("", tmp_path)
    assert config.server.workers == 1
    assert config.data.home == tmp_path / "var"


def test_relative_paths_resolve_against_the_file(tmp_path: Path) -> None:
    config = parse('[data]\nhome = "store"\n[database]\nurl = "sqlite:///db/g.db"\n', tmp_path)
    assert config.data.home == tmp_path / "store"
    assert config.database_url == f"sqlite:///{tmp_path / 'db' / 'g.db'}"


def test_every_problem_is_reported_at_once(tmp_path: Path) -> None:
    text = """
    [server]
    port = "eighty"
    workers = 0
    colour = "blue"
    [sever]
    host = "x"
    """
    with pytest.raises(ConfigError) as caught:
        parse(text, tmp_path)
    problems = caught.value.problems
    assert any("[sever]" in p for p in problems)
    assert any("port" in p and "whole number" in p for p in problems)
    assert any("workers" in p for p in problems)
    assert any("colour" in p for p in problems)
    assert len(problems) == 4


@pytest.mark.parametrize("key", ["password", "client_secret", "api_key", "token"])
def test_secrets_are_refused_in_the_file(tmp_path: Path, key: str) -> None:
    with pytest.raises(ConfigError, match="never written in this file"):
        parse(f'[server]\n{key} = "hunter2"\n', tmp_path)


def test_a_database_password_in_the_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="PGPASSWORD"):
        parse('[database]\nurl = "postgresql+psycopg://u:pw@db.example.org/g"\n', tmp_path)


def test_a_database_password_may_come_from_the_environment(tmp_path: Path) -> None:
    url = "postgresql+psycopg://u:pw@db.example.org/g"
    config = parse("", tmp_path, env={"RISKWREN_DATABASE_URL": url})
    assert config.database_url == url
    assert not config.uses_sqlite


@pytest.mark.parametrize(
    "url", ["mysql://db.example.org/g", "postgresql://db.example.org/g", "not a url"]
)
def test_other_databases_are_refused(tmp_path: Path, url: str) -> None:
    with pytest.raises(ConfigError, match=r"\[database\] url"):
        parse(f'[database]\nurl = "{url}"\n', tmp_path)


def test_environment_overrides_the_file(tmp_path: Path) -> None:
    env = {
        "RISKWREN_SERVER_PORT": "9001",
        "RISKWREN_SERVER_HOST": "0.0.0.0",
        "RISKWREN_DATA_HOME": "/srv/g",
    }
    config = parse("[server]\nport = 8000\n", tmp_path, env=env)
    assert (config.server.port, config.server.host) == (9001, "0.0.0.0")
    assert config.data.home == Path("/srv/g")


def test_a_bad_environment_value_names_the_variable(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="RISKWREN_SERVER_PORT"):
        parse("", tmp_path, env={"RISKWREN_SERVER_PORT": "many"})


def test_base_url_must_be_an_origin(tmp_path: Path) -> None:
    assert parse('[server]\nbase_url = "https://g.example.org"\n', tmp_path).server.base_url
    with pytest.raises(ConfigError, match="base_url"):
        parse('[server]\nbase_url = "https://g.example.org/app/"\n', tmp_path)


def test_a_missing_file_says_what_to_do(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="riskwren init"):
        load_config(tmp_path / "nowhere.toml", env={})


def test_invalid_toml_is_explained(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not valid TOML"):
        parse("[server\n", tmp_path)


def test_where_the_configuration_is_looked_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert find_config_path(None, {}) == (tmp_path / "riskwren.toml").resolve()
    elsewhere = str((tmp_path / "etc" / "g.toml").resolve())
    assert find_config_path(None, {"RISKWREN_CONFIG": elsewhere}) == Path(elsewhere)
    assert find_config_path("mine.toml", {"RISKWREN_CONFIG": elsewhere}).name == "mine.toml"


def test_warnings_do_not_stop_anything() -> None:
    config = parse_config({"server": {"workers": 4}}, base_dir=Path("/tmp"))
    assert any("SQLite" in warning for warning in config_warnings(config))
