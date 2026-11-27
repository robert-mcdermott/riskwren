"""Scheduled work: the jobs RiskWren runs by itself, and the scheduler that runs them.

The scheduler lives in the server process. Before a process runs a job it claims the job's
row in the database, so several server processes, or the server and ``riskwren jobs run``
from a scheduled task, never run the same job at once. What is due is worked out from the
clock everything else uses, and from what is in the database, so a restart loses nothing.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from riskwren import mail, reminders
from riskwren.config import Config
from riskwren.core.clock import utc_now
from riskwren.core.errors import NotFound
from riskwren.db.engine import Database
from riskwren.db.models import Job, JobRun, SignInRequest
from riskwren.events.actor import Actor

log = logging.getLogger("riskwren.jobs")

LEASE = timedelta(minutes=15)  # a job claimed by a process that died is taken up after this
KEEP_RUNS = timedelta(days=90)
EVERY_SECONDS = 20  # how often the server looks for work that is due
SCHEDULER = Actor.system("Scheduler")


@dataclass(frozen=True)
class JobSpec:
    key: str
    label: str
    describes: str
    every: timedelta
    run: Callable[[Database, Config], dict[str, int]]


def _mail(db: Database, config: Config) -> dict[str, int]:
    return mail.run_once(db, config)


def _calendar(db: Database, _config: Config) -> dict[str, int]:
    """What the passing of a date changes: a plan past its date or an acceptance that has
    ended leaves its risk needing a decision again."""
    from riskwren.treatment import service as treatment

    return {"risks_brought_up_to_date": treatment.catch_up(db)}


def _reminders(db: Database, _config: Config) -> dict[str, int]:
    # Reminders are notices, which are not history, so no actor writes them.
    with db.bookkeeping() as session:
        counts = reminders.send(session)
    # An evidence request is met when the evidence is attached; nobody has to say so.
    from riskwren.oversight import campaigns

    with db.write(SCHEDULER, action="job.reminders") as session:
        counts["evidence_requests_met"] = campaigns.refresh_all(session)
    return counts


def _tidy(db: Database, _config: Config) -> dict[str, int]:
    now = utc_now()
    with db.bookkeeping() as session:
        runs = session.execute(delete(JobRun).where(JobRun.finished_at < now - KEEP_RUNS))
        begun = session.execute(
            delete(SignInRequest).where(SignInRequest.created_at < now - timedelta(hours=1))
        )
        return {
            "old_runs_removed": runs.rowcount or 0,  # type: ignore[attr-defined]
            "unfinished_sign_ins_removed": begun.rowcount or 0,  # type: ignore[attr-defined]
        }


JOBS: dict[str, JobSpec] = {
    spec.key: spec
    for spec in (
        JobSpec("calendar", "The calendar",
                "Brings risks up to date when a plan passes its date or an acceptance ends",
                timedelta(hours=1), _calendar),
        JobSpec("reminders", "Reminders",
                "Reminds people of what is nearly due, and tells stewards and leaders what "
                "stays late",
                timedelta(hours=1), _reminders),
        JobSpec("mail", "Email",
                "Queues notices and daily summaries and sends what is waiting, where email is "
                "set up",
                timedelta(minutes=1), _mail),
        JobSpec("tidy", "Housekeeping",
                "Removes run records older than ninety days and sign-ins that were never finished",
                timedelta(days=1), _tidy),
    )
}  # fmt: skip


def ensure(db: Database) -> None:
    """Give every job a row. A new job is due at once."""
    with db.bookkeeping() as session:
        known = set(session.scalars(select(Job.key)))
        for key in JOBS:
            if key not in known:
                session.add(Job(key=key, enabled=True, next_run_at=utc_now()))


def _claim(db: Database, key: str, *, force: bool) -> bool:
    now = utc_now()
    with db.bookkeeping() as session:
        row = session.scalars(
            select(Job).where(Job.key == key).with_for_update(skip_locked=True)
        ).first()
        if row is None or (row.claimed_until is not None and row.claimed_until > now):
            return False
        if not force and (not row.enabled or row.next_run_at > now):
            return False
        row.claimed_until = now + LEASE
        row.last_started_at = now
        return True


def _words(counts: dict[str, int]) -> str:
    done = [f"{value} {name.replace('_', ' ')}" for name, value in counts.items() if value]
    return ", ".join(done) or "Nothing to do"


def run_job(
    db: Database, config: Config, key: str, *, force: bool = False
) -> dict[str, Any] | None:
    """Run one job if it is due and nobody else has it. ``force`` runs it now whether or
    not it is due. Returns what happened, or None if it was not this process's to run."""
    spec = JOBS.get(key)
    if spec is None:
        raise NotFound(f"There is no job {key}.")
    if force:
        ensure(db)  # asked for by name, perhaps before the scheduler has ever run
    if not _claim(db, key, force=force):
        return None
    started = utc_now()
    counts: dict[str, int] = {}
    error: str | None = None
    try:
        counts = spec.run(db, config)
    except Exception as exc:  # one bad run must not stop the scheduler
        log.exception("the %s job failed", key)
        error = f"{type(exc).__name__}: {exc}"[:600]
    finished = utc_now()
    status = "failed" if error else "ok"
    with db.bookkeeping() as session:
        row = session.get(Job, key)
        assert row is not None
        row.claimed_until = None
        row.last_finished_at = finished
        row.last_status = status
        row.last_summary = (error or _words(counts))[:300]
        row.next_run_at = started + spec.every
        if error or any(counts.values()):
            session.add(JobRun(job_key=key, started_at=started, finished_at=finished,
                               status=status, counts=counts, error=error))  # fmt: skip
    return {"key": key, "status": status, "counts": counts, "error": error,
            "summary": error or _words(counts)}  # fmt: skip


def run_due(db: Database, config: Config) -> list[dict[str, Any]]:
    """Run every job that is due. Safe to call from several processes at once."""
    ensure(db)
    results = []
    for key in JOBS:
        result = run_job(db, config, key)
        if result is not None:
            results.append(result)
    return results


def status(session: Session, *, runs: int = 12) -> list[dict[str, Any]]:
    rows = {row.key: row for row in session.scalars(select(Job))}
    recent = session.scalars(select(JobRun).order_by(JobRun.id.desc()).limit(200)).all()
    out = []
    for key, spec in JOBS.items():
        row = rows.get(key)
        out.append(
            {
                "key": key,
                "label": spec.label,
                "describes": spec.describes,
                "every_seconds": int(spec.every.total_seconds()),
                "enabled": row.enabled if row else True,
                "next_run_at": row.next_run_at if row else None,
                "running": bool(row and row.claimed_until and row.claimed_until > utc_now()),
                "last_finished_at": row.last_finished_at if row else None,
                "last_status": row.last_status if row else None,
                "last_summary": row.last_summary if row else None,
                "runs": [
                    {"started_at": run.started_at, "finished_at": run.finished_at,
                     "status": run.status, "summary": run.error or _words(run.counts)}
                    for run in recent if run.job_key == key
                ][:runs],
            }
        )  # fmt: skip
    return out


def set_enabled(db: Database, key: str, enabled: bool) -> None:
    if key not in JOBS:
        raise NotFound(f"There is no job {key}.")
    ensure(db)
    with db.bookkeeping() as session:
        row = session.get(Job, key)
        assert row is not None
        row.enabled = enabled


def start_worker(db: Database, config: Config) -> threading.Event:
    """Run the scheduler beside the server for as long as it is up. Returns an event that
    stops it when set."""
    stop = threading.Event()

    def work() -> None:
        while not stop.wait(EVERY_SECONDS):
            try:
                run_due(db, config)
            except Exception:  # the scheduler must outlive a bad turn
                log.exception("the scheduler failed this time and will try again")

    threading.Thread(target=work, name="riskwren-jobs", daemon=True).start()
    return stop
