"""``riskwren doctor``: is this installation healthy?"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass

from sqlalchemy import text

from riskwren.config import Config, config_warnings, load_config
from riskwren.core.errors import RiskWrenError
from riskwren.db import migrate
from riskwren.db.engine import Database
from riskwren.events import chain
from riskwren.home import DataHome

OK, WARN, FAIL = "ok", "warn", "fail"
MARKS = {OK: "✓", WARN: "!", FAIL: "✗"}

SQLITE_TRIGGERS = "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'event'"
POSTGRES_TRIGGERS = (
    "SELECT tgname FROM pg_trigger WHERE tgrelid = 'event'::regclass AND NOT tgisinternal"
)
EXPECTED_TRIGGERS = {
    "sqlite": {"event_no_update", "event_no_delete"},
    "postgresql": {"event_no_change", "event_no_truncate"},
}


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def run(config_path: str | None = None) -> list[Check]:
    checks = [_python()]
    try:
        config = load_config(config_path)
    except RiskWrenError as exc:
        return [*checks, Check("Configuration", FAIL, str(exc).splitlines()[0])]
    checks.append(Check("Configuration", OK, str(config.path)))
    checks += [Check("Advice", WARN, warning) for warning in config_warnings(config)]

    home = DataHome(config.data.home)
    if not home.is_initialized():
        return [
            *checks,
            Check("Data home", FAIL, f"{home.root} is not set up; run `riskwren init`"),
        ]
    checks.append(_disk(home))
    checks += _database(config)
    # Single sign-on is optional. Without it, people sign in with local accounts.
    checks.append(_sso(config) if config.sso.enabled else Check("Sign-in", OK, "local accounts"))
    # Email is optional as well. Without it, notices and reminders are read in the app.
    checks.append(_mail(config) if config.mail.enabled else Check("Email", OK, "not set up"))
    checks.append(_jobs(config))
    return checks


def _mail(config: Config) -> Check:
    """Can the mail server be reached and signed in to? Nothing is sent."""
    from riskwren import mail

    try:
        mail.SmtpSender(config.mail).check()
    except RiskWrenError as exc:
        return Check("Email", FAIL, str(exc))
    return Check(
        "Email", OK, f"{config.mail.host}:{config.mail.port} as {config.mail.from_address}"
    )


def _jobs(config: Config) -> Check:
    """Is scheduled work being done, by this server or by something else?"""
    from datetime import timedelta

    from sqlalchemy import select

    from riskwren.core.clock import utc_now
    from riskwren.db.models import Job

    db = Database(config.database_url)
    try:
        with db.read() as session:
            rows = list(session.scalars(select(Job)))
    finally:
        db.dispose()
    failed = [row.key for row in rows if row.last_status == "failed"]
    if failed:
        return Check("Scheduled work", WARN, f"the last run of {', '.join(failed)} failed")
    ran = [row.last_finished_at for row in rows if row.last_finished_at]
    if not config.server.scheduler and (not ran or max(ran) < utc_now() - timedelta(days=2)):
        return Check(
            "Scheduled work",
            WARN,
            "the server's scheduler is off and nothing has run for two days: run "
            "`riskwren jobs run` from a scheduled task, or turn the scheduler on",
        )
    how = "by the server" if config.server.scheduler else "by `riskwren jobs run`"
    return Check("Scheduled work", OK, f"run {how}")


def _sso(config: Config) -> Check:
    """Can the identity provider be read, and is the client secret where it should be?"""
    import os

    from riskwren.auth import oidc

    client = oidc.Client(config.sso)
    try:
        client.metadata()
        client.keys()
    except RiskWrenError as exc:
        return Check("Single sign-on", FAIL, str(exc))
    if not os.environ.get(config.sso.client_secret_env):
        return Check(
            "Single sign-on",
            FAIL,
            f"the client secret is not set: put it in {config.sso.client_secret_env}",
        )
    if not config.server.base_url:
        return Check(
            "Single sign-on",
            WARN,
            "set [server] base_url, so that the redirect address does not depend on how "
            "each request arrives",
        )
    return Check("Single sign-on", OK, f"{config.sso.issuer}, beside local accounts")


def _python() -> Check:
    version = ".".join(str(part) for part in sys.version_info[:3])
    return Check("Python", OK, version)


def _disk(home: DataHome) -> Check:
    free = shutil.disk_usage(home.root).free
    detail = f"{home.root} ({free / 1e9:.1f} GB free)"
    return Check("Data home", WARN if free < 1e9 else OK, detail)


def _database(config: Config) -> list[Check]:
    kind = "SQLite" if config.uses_sqlite else "PostgreSQL"
    db = None
    try:
        db = Database(config.database_url)
        with db.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        if db is not None:
            db.dispose()
        reason = str(getattr(exc, "orig", exc)).strip().splitlines()[0]
        return [Check("Database", FAIL, f"{kind} cannot be reached: {reason}")]
    try:
        checks = [Check("Database", OK, kind)]
        try:
            migrate.require_current(db.engine)
        except RiskWrenError as exc:
            return [*checks, Check("Schema", FAIL, str(exc))]
        checks.append(Check("Schema", OK, f"migration {migrate.current_revision(db.engine)}"))
        with db.engine.connect() as conn:
            query = SQLITE_TRIGGERS if db.dialect == "sqlite" else POSTGRES_TRIGGERS
            present = {row[0] for row in conn.execute(text(query))}
            missing = EXPECTED_TRIGGERS[db.dialect] - present
            if missing:
                checks.append(
                    Check(
                        "History guard",
                        FAIL,
                        "the database no longer refuses changes to the history "
                        f"(missing: {', '.join(sorted(missing))})",
                    )
                )
            else:
                checks.append(Check("History guard", OK, "the database refuses changes to events"))
            report = chain.verify(conn)
        if report.ok:
            checks.append(Check("History", OK, f"{report.events} events verify"))
        else:
            checks.append(
                Check("History", FAIL, f"broken at event {report.broken_at}: {report.reason}")
            )
        return checks
    finally:
        db.dispose()
