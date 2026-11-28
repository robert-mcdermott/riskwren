"""Running the installation: scheduled work, email, and how each person wants to be told."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from riskwren import jobs, mail, reminders
from riskwren.access.policy import current
from riskwren.api.common import envelope, reading, writing
from riskwren.api.problems import problem
from riskwren.people import accounts

router = APIRouter(prefix="/api/v1", tags=["operations"])


class JobSwitch(BaseModel):
    enabled: bool


class Preferences(BaseModel):
    email_notices: str = Field(max_length=16)


def _size(root: Any) -> int:
    """The bytes the data home holds."""
    from pathlib import Path

    total = 0
    for path in Path(root).rglob("*"):
        try:
            total += path.stat().st_size if path.is_file() else 0
        except OSError:
            continue
    return total


@router.get("/admin/operations", summary="This installation: version, database, backups, health")
def installation(request: Request) -> dict[str, Any]:
    """What an administrator needs to know of the installation itself, and what `riskwren
    doctor --production` would say of it, without reaching anything outside."""
    import shutil

    from riskwren import __version__, backup
    from riskwren.cli import doctor
    from riskwren.db import migrate
    from riskwren.home import DataHome

    config = request.app.state.config
    home = DataHome(config.data.home)
    db = request.app.state.db
    checks = doctor.going_live(config, home)
    return envelope({
        "version": __version__,
        "database": "SQLite" if config.uses_sqlite else "PostgreSQL",
        "migration": migrate.current_revision(db.engine),
        "workers": config.server.workers,
        "scheduler": config.server.scheduler,
        "base_url": config.server.base_url,
        "data_home": {"path": str(home.root), "bytes": _size(home.root),
                      "free_bytes": shutil.disk_usage(home.root).free},
        "last_backup": backup.last(home),
        "checks": [{"name": c.name, "status": c.status, "detail": c.detail} for c in checks],
    })  # fmt: skip


@router.get("/jobs", summary="Scheduled work, and how its recent runs went")
def jobs_status(request: Request) -> dict[str, Any]:
    jobs.ensure(request.app.state.db)
    with reading(request) as session:
        return envelope(
            {
                "jobs": jobs.status(session),
                "scheduler": request.app.state.config.server.scheduler,
                "reminders": reminders.schedule(session),
            }
        )


@router.post("/jobs/{key}/run", summary="Run one job now")
def jobs_run(key: str, request: Request) -> Any:
    """Runs the job at once, whether or not it is due, and says what it did. If another
    process is running it at this moment, nothing is run and the answer says so."""
    if key not in jobs.JOBS:
        return problem(404, f"There is no job {key}.", instance=request.url.path)
    result = jobs.run_job(request.app.state.db, request.app.state.config, key, force=True)
    if result is None:
        return problem(409, "That job is running at the moment.", instance=request.url.path)
    return envelope(result)


@router.put("/jobs/{key}", summary="Pause or resume one job")
def jobs_set(key: str, body: JobSwitch, request: Request) -> Any:
    if key not in jobs.JOBS:
        return problem(404, f"There is no job {key}.", instance=request.url.path)
    jobs.set_enabled(request.app.state.db, key, body.enabled)
    with reading(request) as session:
        return envelope(next(job for job in jobs.status(session) if job["key"] == key))


@router.get("/mail", summary="How email is set up, and how it is doing")
def mail_status(request: Request) -> dict[str, Any]:
    with reading(request) as session:
        return envelope(mail.status(session, request.app.state.config))


@router.post("/mail/test", summary="Send yourself a test message")
def mail_test(request: Request) -> Any:
    """Sends one message to your own address, now, and says whether the mail server took it."""
    principal = current(request)
    with reading(request) as session:
        account = accounts.get(session, principal.account_id or 0)
    try:
        mail.send_test(
            request.app.state.db,
            request.app.state.config,
            account,
            getattr(request.app.state, "mail_sender", None),
        )
    except mail.MailError as exc:
        return problem(502, str(exc), instance=request.url.path)
    return envelope({"sent_to": account.email})


@router.get("/session/preferences", summary="How you want to be told")
def preferences(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        account = accounts.get(session, principal.account_id or 0)
        return envelope(
            {
                "email_notices": account.email_notices,
                "choices": list(mail.PREFERENCES),
                # Whether choosing changes anything yet: email is optional.
                "email": request.app.state.config.mail.enabled,
                "address": account.email,
            }
        )


@router.put("/session/preferences", summary="Say how you want to be told")
def set_preferences(body: Preferences, request: Request) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        account = accounts.get(session, principal.account_id or 0)
        accounts.set_email_notices(session, account, body.email_notices)
        return envelope({"email_notices": account.email_notices})
