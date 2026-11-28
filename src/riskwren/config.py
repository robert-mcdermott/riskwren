"""The deployment's settings, read from ``riskwren.toml``.

The file holds only what describes how the server runs. The risk and compliance program and
the product's appearance live in the database and are edited in the app (ADR-0010), except
that a [branding] section may fix the appearance exactly.
"""

from __future__ import annotations

import os
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, replace
from importlib import resources
from pathlib import Path
from typing import Any, get_type_hints

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from riskwren.core.errors import ConfigError

CONFIG_NAME = "riskwren.toml"
ENV_CONFIG = "RISKWREN_CONFIG"
ENV_PREFIX = "RISKWREN_"

_SECRET_KEY = re.compile(r"(^|_)(password|secret|token|api_key|key)$")
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    workers: int = 1
    base_url: str = ""
    # Fractions are allowed: 0.5 hours idle and 0.5 days in all meet ASVS level 2.
    session_idle_hours: float = 12
    session_max_days: float = 7
    scheduler: bool = True  # run scheduled work inside this server


@dataclass(frozen=True)
class DatabaseConfig:
    url: str = ""


@dataclass(frozen=True)
class DataConfig:
    home: Path = Path("var")


@dataclass(frozen=True)
class SsoConfig:
    """Single sign-on through an OpenID Connect provider, beside local accounts. Off until an
    issuer and a client are named."""

    issuer: str = ""
    client_id: str = ""
    client_secret_env: str = "RISKWREN_SSO_CLIENT_SECRET"  # noqa: S105 (a variable's name)
    scopes: str = "openid profile email"
    roles_claim: str = "roles"
    label: str = "Sign in with your organization account"
    trust_email: bool = False
    create_accounts: bool = True
    local_sign_in: bool = True

    @property
    def enabled(self) -> bool:
        return bool(self.issuer and self.client_id)


@dataclass(frozen=True)
class MailConfig:
    """Email over SMTP. Optional: off until a host and a from address are given, and until
    then notices are read in the app."""

    host: str = ""
    port: int = 587
    security: str = "starttls"
    username: str = ""
    password_env: str = "RISKWREN_MAIL_PASSWORD"  # noqa: S105 (a variable's name)
    from_address: str = ""
    from_name: str = ""
    digest_hour: int = 7

    @property
    def enabled(self) -> bool:
        return bool(self.host and self.from_address)


@dataclass(frozen=True)
class Config:
    path: Path | None = None
    server: ServerConfig = field(default_factory=ServerConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    data: DataConfig = field(default_factory=DataConfig)
    sso: SsoConfig = field(default_factory=SsoConfig)
    mail: MailConfig = field(default_factory=MailConfig)
    # The [branding] section, checked: a ``riskwren.program.branding.FileBranding``, or None.
    branding: Any = None

    @property
    def database_url(self) -> str:
        """The configured database, or SQLite inside the data home."""
        if self.database.url:
            return self.database.url
        return f"sqlite:///{self.data.home / 'riskwren.db'}"

    @property
    def uses_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


_SECTIONS: dict[str, type] = {
    "server": ServerConfig,
    "database": DatabaseConfig,
    "data": DataConfig,
    "sso": SsoConfig,
    "mail": MailConfig,
}


def example_config_text() -> str:
    """The commented example configuration that ``riskwren init`` writes."""
    return (
        resources.files("riskwren.resources")
        .joinpath("riskwren.example.toml")
        .read_text(encoding="utf-8")
    )


def find_config_path(
    explicit: str | Path | None = None, env: Mapping[str, str] | None = None
) -> Path:
    """Where the configuration is: ``--config``, ``$RISKWREN_CONFIG``, or ``./riskwren.toml``."""
    env = os.environ if env is None else env
    if explicit:
        return Path(explicit).expanduser().resolve()
    if env.get(ENV_CONFIG):
        return Path(env[ENV_CONFIG]).expanduser().resolve()
    return (Path.cwd() / CONFIG_NAME).resolve()


def load_config(path: str | Path | None = None, env: Mapping[str, str] | None = None) -> Config:
    """Read, check, and return the configuration. Every problem is reported together."""
    env = os.environ if env is None else env
    file = find_config_path(path, env)
    if not file.is_file():
        raise ConfigError(f"No configuration file at {file}. Run `riskwren init` to write one.")
    try:
        raw = tomllib.loads(file.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{file} is not valid TOML: {exc}") from exc
    return parse_config(raw, base_dir=file.parent, path=file, env=env)


def parse_config(
    raw: Mapping[str, Any],
    *,
    base_dir: Path,
    path: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Config:
    env = {} if env is None else env
    problems: list[str] = []
    sections: dict[str, Any] = {}

    for name in raw:
        if name not in _SECTIONS and name != "branding":
            problems.append(f"[{name}] is not a section RiskWren knows")

    for name, cls in _SECTIONS.items():
        table = raw.get(name, {})
        if not isinstance(table, Mapping):
            problems.append(f"[{name}] must be a table")
            table = {}
        sections[name] = _build(name, cls, table, env, problems)

    brand = None
    if "branding" in raw:
        from riskwren.program import branding as brand_rules

        brand, found = brand_rules.from_file(raw["branding"], base_dir)
        problems.extend(found)
    config = Config(path=path, branding=brand, **sections)
    config = replace(config, data=replace(config.data, home=_resolve(config.data.home, base_dir)))
    config = replace(
        config,
        database=replace(config.database, url=_resolve_sqlite(config.database.url, base_dir)),
    )
    problems.extend(_validate(config, raw))
    if problems:
        where = f" in {path}" if path else ""
        raise ConfigError(f"Invalid configuration{where}:", problems)
    return config


def _build(
    section: str, cls: type, table: Mapping[str, Any], env: Mapping[str, str], problems: list[str]
) -> Any:
    hints = get_type_hints(cls)
    known = {f.name for f in fields(cls)}
    values: dict[str, Any] = {}
    for key, value in table.items():
        if _SECRET_KEY.search(key):
            problems.append(
                f"[{section}] {key}: keys and secrets are never written in this file; "
                "put the value in an environment variable"
            )
        elif key not in known:
            problems.append(f"[{section}] {key} is not a setting RiskWren knows")
        else:
            try:
                values[key] = _convert(value, hints[key], from_env=False)
            except ValueError as exc:
                problems.append(f"[{section}] {key}: {exc}")
    for key in known:
        variable = f"{ENV_PREFIX}{section.upper()}_{key.upper()}"
        if variable in env:
            try:
                values[key] = _convert(env[variable], hints[key], from_env=True)
            except ValueError as exc:
                problems.append(f"{variable}: {exc}")
    return cls(**values)


def _convert(value: Any, kind: Any, *, from_env: bool) -> Any:
    if kind is bool:
        if isinstance(value, bool):
            return value
        if from_env and str(value).strip().lower() in _TRUE | _FALSE:
            return str(value).strip().lower() in _TRUE
        raise ValueError("must be true or false")
    if kind is int:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if from_env:
            try:
                return int(str(value).strip())
            except ValueError:
                pass
        raise ValueError("must be a whole number")
    if kind is float:
        if isinstance(value, int | float) and not isinstance(value, bool):
            return float(value)
        if from_env:
            try:
                return float(str(value).strip())
            except ValueError:
                pass
        raise ValueError("must be a number")
    if kind is Path:
        if isinstance(value, str) and value.strip():
            return Path(value).expanduser()
        raise ValueError("must be a path")
    if kind is str:
        if isinstance(value, str):
            return value.strip()
        raise ValueError("must be text in quotes")
    raise ValueError(f"unsupported setting type {kind!r}")  # a programming error, not the user's


def _resolve(path: Path, base_dir: Path) -> Path:
    return path if path.is_absolute() else (base_dir / path).resolve()


def _resolve_sqlite(url: str, base_dir: Path) -> str:
    """Make a relative SQLite file path absolute, so the installation moves as a unit."""
    if not url.startswith("sqlite:///") or url.startswith("sqlite:////"):
        return url
    database = url[len("sqlite:///") :]
    if not database or database == ":memory:":
        return url
    return f"sqlite:///{_resolve(Path(database), base_dir)}"


def _validate(config: Config, raw: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    server = config.server
    if not server.host:
        problems.append("[server] host must not be empty")
    if not 1 <= server.port <= 65535:
        problems.append("[server] port must be between 1 and 65535")
    if not 1 <= server.workers <= 64:
        problems.append("[server] workers must be between 1 and 64")
    if server.session_idle_hours < 0.25:
        problems.append("[server] session_idle_hours must be at least 0.25 (fifteen minutes)")
    if server.session_max_days < 0.25:
        problems.append("[server] session_max_days must be at least 0.25 (six hours)")
    if server.base_url and not re.fullmatch(r"https?://[^/\s]+", server.base_url):
        problems.append(
            '[server] base_url must look like "https://riskwren.example.org", with no path'
        )

    url = config.database.url
    if url:
        try:
            parsed = make_url(url)
        except ArgumentError:
            problems.append("[database] url is not a database address RiskWren can read")
        else:
            backend = parsed.get_backend_name()
            if backend not in {"sqlite", "postgresql"}:
                problems.append("[database] url must be for SQLite or PostgreSQL")
            if backend == "postgresql" and parsed.drivername != "postgresql+psycopg":
                problems.append(
                    '[database] url for PostgreSQL must start with "postgresql+psycopg://"'
                )
            file_url = raw.get("database", {}).get("url", "") if isinstance(raw, Mapping) else ""
            if parsed.password and isinstance(file_url, str) and file_url.strip() == url:
                problems.append(
                    "[database] url: the password is never written in this file; put it in the "
                    "PGPASSWORD environment variable, or set RISKWREN_DATABASE_URL instead"
                )
    sso = config.sso
    if bool(sso.issuer) != bool(sso.client_id):
        problems.append("[sso] issuer and client_id go together: set both, or neither")
    if sso.issuer:
        local = re.fullmatch(r"http://(localhost|127\.0\.0\.1)(:\d+)?(/\S*)?", sso.issuer)
        if not (re.fullmatch(r"https://[^\s?#]+", sso.issuer) or local):
            problems.append(
                "[sso] issuer must be an https address, such as "
                '"https://login.microsoftonline.com/<tenant id>/v2.0"'
            )
        if re.search(r"/(common|organizations|consumers)(/|$)", sso.issuer):
            problems.append(
                "[sso] issuer must name one tenant. Use the directory (tenant) ID in place of "
                '"common", "organizations", or "consumers", so that only your own directory '
                "can sign people in"
            )
        if "openid" not in sso.scopes.split():
            problems.append('[sso] scopes must include "openid"')
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", sso.client_secret_env):
            problems.append(
                "[sso] client_secret_env names the environment variable that holds the client "
                "secret, such as RISKWREN_SSO_CLIENT_SECRET"
            )
        if not sso.roles_claim:
            problems.append("[sso] roles_claim must not be empty")
        if not sso.label:
            problems.append("[sso] label must not be empty")
    mail = config.mail
    if bool(mail.host) != bool(mail.from_address):
        problems.append("[mail] host and from_address go together: set both, or neither")
    if mail.host:
        if mail.security not in ("starttls", "tls", "none"):
            problems.append('[mail] security must be "starttls", "tls", or "none"')
        if not 1 <= mail.port <= 65535:
            problems.append("[mail] port must be between 1 and 65535")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", mail.from_address):
            problems.append("[mail] from_address must be an email address")
        if not 0 <= mail.digest_hour <= 23:
            problems.append("[mail] digest_hour must be between 0 and 23")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", mail.password_env):
            problems.append(
                "[mail] password_env names the environment variable that holds the password, "
                "such as RISKWREN_MAIL_PASSWORD"
            )
    return problems


def config_warnings(config: Config) -> list[str]:
    """Advice that does not stop RiskWren from running."""
    warnings: list[str] = []
    if config.server.workers > 1 and config.uses_sqlite:
        warnings.append(
            "Several server processes share one SQLite file. That works for light use; "
            "for many people at once, use PostgreSQL."
        )
    if config.server.base_url.startswith("http://") and "localhost" not in config.server.base_url:
        warnings.append("base_url is not https. Serve RiskWren over TLS in production.")
    if config.mail.enabled and not config.server.base_url:
        warnings.append(
            "[mail] is set up but [server] base_url is empty, so emails cannot link back to "
            "RiskWren. Set base_url to the address people use."
        )
    return warnings
