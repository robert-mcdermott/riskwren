"""Scheduled work: each job run once by whichever process claims it, and reminders that go
to the owner, then the steward, then the leader, each once."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren import jobs, reminders
from riskwren.controls import service as controls
from riskwren.core.clock import frozen_at
from riskwren.db.engine import Database
from riskwren.db.models import Job, JobRun, Notice, Reminder
from riskwren.inventory import records
from riskwren.inventory.registry import find
from riskwren.risk.register import RISK
from riskwren.treatment import service as treatment
from tests.conftest import Instance
from tests.people import People
from tests.test_risks import who
from tests.test_treatment import above_appetite, add_control, rated

Clients = Callable[[str | None], TestClient]
START = datetime(2026, 3, 2, 9, 0, tzinfo=UTC)


def at(day: str) -> datetime:
    return datetime.fromisoformat(day).replace(hour=9, tzinfo=UTC)


def notices_of(db: Database, account_id: int) -> list[tuple[str, str]]:
    with db.read() as session:
        rows = session.scalars(
            select(Notice).where(Notice.account_id == account_id).order_by(Notice.id)
        )
        return [(row.kind, row.text) for row in rows]


def remind(db: Database) -> dict[str, int]:
    with db.bookkeeping() as session:
        return reminders.send(session)


# --- Jobs ---------------------------------------------------------------------------------


def test_jobs_run_when_due_and_not_before(instance: Instance, people: People) -> None:
    db, config = instance.db, instance.config
    with frozen_at(START):
        ran = {result["key"] for result in jobs.run_due(db, config)}
        assert ran == set(jobs.JOBS) == {"calendar", "reminders", "mail", "measures", "tidy"}
        assert jobs.run_due(db, config) == []  # nothing is due again yet
    with frozen_at(START + timedelta(minutes=2)):
        assert [result["key"] for result in jobs.run_due(db, config)] == ["mail"]
    with frozen_at(START + timedelta(hours=1, minutes=1)):
        ran = {result["key"] for result in jobs.run_due(db, config)}
        assert ran == {"calendar", "reminders", "mail"}  # not the daily one


def test_two_processes_run_a_job_once_between_them(instance: Instance, people: People) -> None:
    """Each server process, and `riskwren jobs run`, has its own connection to the one
    database. Whichever claims a job has it; the other finds it taken."""
    first, config = instance.db, instance.config
    second = Database(config.database_url)
    try:
        with frozen_at(START):
            jobs.ensure(first)
            results = [jobs.run_job(db, config, "reminders") for db in (first, second)]
            assert [result is not None for result in results] == [True, False]
            with first.read() as session:
                row = session.get(Job, "reminders")
                assert row is not None and row.claimed_until is None
                assert row.next_run_at == START + timedelta(hours=1)
    finally:
        second.dispose()


def test_a_claimed_job_is_not_run_again_until_the_claim_runs_out(
    instance: Instance, people: People
) -> None:
    db, config = instance.db, instance.config
    with frozen_at(START):
        jobs.ensure(db)
        assert jobs._claim(db, "calendar", force=False)  # another process has it
        assert jobs.run_job(db, config, "calendar") is None
        assert jobs.run_job(db, config, "calendar", force=True) is None
    with frozen_at(START + jobs.LEASE + timedelta(seconds=1)):
        result = jobs.run_job(db, config, "calendar")  # that process died; the job is taken up
        assert result is not None and result["status"] == "ok"


def test_a_failing_job_is_recorded_and_tried_again(
    instance: Instance, people: People, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, config = instance.db, instance.config

    def broken(_db: Database, _config: object) -> dict[str, int]:
        raise RuntimeError("the disk is full")

    spec = jobs.JOBS["tidy"]
    monkeypatch.setitem(
        jobs.JOBS, "tidy", jobs.JobSpec(spec.key, spec.label, spec.describes, spec.every, broken)
    )
    with frozen_at(START):
        jobs.ensure(db)
        result = jobs.run_job(db, config, "tidy")
        assert result is not None and result["status"] == "failed"
        with db.read() as session:
            row = session.get(Job, "tidy")
            assert row is not None and row.last_status == "failed" and row.claimed_until is None
            assert "the disk is full" in (row.last_summary or "")
            [run] = session.scalars(select(JobRun)).all()
            assert run.status == "failed"
    monkeypatch.setitem(jobs.JOBS, "tidy", spec)
    with frozen_at(START + timedelta(days=1, seconds=1)):
        result = jobs.run_job(db, config, "tidy")
        assert result is not None and result["status"] == "ok"


def test_a_paused_job_is_skipped_unless_asked_for(instance: Instance, people: People) -> None:
    db, config = instance.db, instance.config
    jobs.set_enabled(db, "reminders", False)
    assert "reminders" not in {result["key"] for result in jobs.run_due(db, config)}
    assert jobs.run_job(db, config, "reminders", force=True) is not None


def test_an_administrator_sees_and_runs_jobs(as_role: Clients, people: People) -> None:
    admin = as_role("admin")
    shown = admin.get("/api/v1/jobs").json()["data"]
    assert [job["key"] for job in shown["jobs"]] == list(jobs.JOBS)
    assert all(job["enabled"] for job in shown["jobs"])
    assert shown["reminders"] == {"soon_days": 14, "steward_after_days": 7, "leader_after_days": 21}
    done = admin.post("/api/v1/jobs/reminders/run").json()["data"]
    assert (done["status"], done["summary"]) == ("ok", "Nothing to do")
    paused = admin.put("/api/v1/jobs/reminders", json={"enabled": False}).json()["data"]
    assert paused["enabled"] is False and paused["last_status"] == "ok"
    assert admin.post("/api/v1/jobs/nothing/run").status_code == 404
    assert as_role("manager").get("/api/v1/jobs").status_code == 403


def test_the_calendar_job_does_what_reading_the_register_used_to(
    instance: Instance, people: People
) -> None:
    db, config = instance.db, instance.config
    steward, me = who(db, people, "steward"), people.accounts["steward"]
    with db.write(steward.actor) as session, frozen_at(START):
        risk = above_appetite(session, people, steward)
        treatment.create_plan(
            session, steward, risk, objective="Fix it", owner_id=me, due_on="2026-04-01"
        )
        assert risk.standing == "treated"
    with frozen_at(at("2026-04-02")):
        results = {result["key"]: result for result in jobs.run_due(db, config)}
        assert results["calendar"]["counts"] == {"risks_brought_up_to_date": 1}
        with db.read() as session:
            assert find(session, RISK, "RSK-0001").standing == "needs_decision"
            kept = {run.job_key for run in session.scalars(select(JobRun))}
            assert "calendar" in kept and "tidy" not in kept  # a run that did nothing is not kept


# --- Reminders ----------------------------------------------------------------------------


def test_an_action_reminds_its_owner_then_the_steward_then_the_leader(
    db: Database, people: People
) -> None:
    steward = who(db, people, "steward")
    owner, above, top = (people.accounts[role] for role in ("member", "steward", "leader"))
    with db.write(steward.actor) as session, frozen_at(START):
        risk = above_appetite(session, people, steward)
        plan = treatment.create_plan(
            session, steward, risk, objective="Fix it", owner_id=above, due_on="2026-12-01"
        )
        treatment.add_action(
            session, steward, plan, title="Buy two freezers", owner_id=owner, due_on="2026-05-01"
        )
    with db.bookkeeping() as session:  # what assigning it said is not what this test is about
        for row in session.scalars(select(Notice)):
            session.delete(row)

    with frozen_at(at("2026-04-10")):  # three weeks ahead: too early
        assert remind(db) == {"reminders": 0, "overdue": 0, "escalated": 0}
    with frozen_at(at("2026-04-28")):
        assert remind(db)["reminders"] == 1
        assert remind(db)["reminders"] == 0  # said once
    assert notices_of(db, owner) == [("reminder", "Due in 3 days: ACT-0001 Buy two freezers")]
    with frozen_at(at("2026-05-02")):
        assert remind(db)["overdue"] == 1
    with frozen_at(at("2026-05-05")):
        assert remind(db) == {"reminders": 0, "overdue": 0, "escalated": 0}  # nothing new to say
    with frozen_at(at("2026-05-08")):
        assert remind(db)["escalated"] == 1
    with frozen_at(at("2026-05-22")):
        assert remind(db)["escalated"] == 1
        assert remind(db)["escalated"] == 0
    assert [kind for kind, _ in notices_of(db, owner)] == ["reminder", "overdue"]
    assert notices_of(db, above) == [
        ("escalated", "Overdue by 7 days, and now with you: ACT-0001 Buy two freezers")
    ]
    assert notices_of(db, top) == [
        ("escalated", "Overdue by 21 days, and now with you: ACT-0001 Buy two freezers")
    ]
    with db.read() as session:
        stages = sorted(row.stage for row in session.scalars(select(Reminder)))
        assert stages == ["leader", "overdue", "soon", "steward"]


def test_moving_the_date_starts_the_reminders_again(db: Database, people: People) -> None:
    steward = who(db, people, "steward")
    owner, above = people.accounts["member"], people.accounts["steward"]
    with db.write(steward.actor) as session, frozen_at(START):
        risk = above_appetite(session, people, steward)
        plan = treatment.create_plan(
            session, steward, risk, objective="Fix it", owner_id=above, due_on="2026-12-01"
        )
        action = treatment.add_action(
            session, steward, plan, title="Buy two freezers", owner_id=owner, due_on="2026-05-01"
        )
        ref = action.ref
    with frozen_at(at("2026-05-02")):
        assert remind(db)["overdue"] == 1
        with db.write(steward.actor) as session:
            treatment.update_action(
                session, steward, treatment.find_action(session, ref),
                {"due_on": "2026-06-01", "reason": "The supplier is late."},
            )  # fmt: skip
        assert remind(db) == {"reminders": 0, "overdue": 0, "escalated": 0}
    with frozen_at(at("2026-06-02")):
        assert remind(db)["overdue"] == 1  # late again, against the new date


def test_something_found_long_overdue_is_said_once_at_the_stage_it_has_reached(
    db: Database, people: People
) -> None:
    """The first run after an upgrade finds things that have been late for months. Each is
    told to the leader, once, and not also to everyone below in the same hour."""
    steward = who(db, people, "steward")
    owner, above, top = (people.accounts[role] for role in ("member", "steward", "leader"))
    with db.write(steward.actor) as session, frozen_at(START):
        risk = above_appetite(session, people, steward)
        plan = treatment.create_plan(
            session, steward, risk, objective="Fix it", owner_id=above, due_on="2026-12-01"
        )
        treatment.add_action(
            session, steward, plan, title="Buy two freezers", owner_id=owner, due_on="2026-05-01"
        )
    with db.bookkeeping() as session:
        for row in session.scalars(select(Notice)):
            session.delete(row)
    with frozen_at(at("2026-08-01")):
        assert remind(db) == {"reminders": 0, "overdue": 0, "escalated": 1}
        assert remind(db) == {"reminders": 0, "overdue": 0, "escalated": 0}
    assert notices_of(db, owner) == [] and notices_of(db, above) == []
    assert [kind for kind, _ in notices_of(db, top)] == ["escalated"]


def test_a_risk_review_and_a_control_test_are_reminded_of(db: Database, people: People) -> None:
    steward, assessor = who(db, people, "steward"), who(db, people, "assessor")
    owner = people.accounts["steward"]
    with db.write(steward.actor) as session, frozen_at(START):
        risk = above_appetite(session, people, steward)  # high: reviewed every six months
        assert risk.next_review_on == date(2026, 9, 2)
        usual = add_control(session, steward, people.units["HALE"], "Freezers alarmed")
        key = add_control(session, steward, people.units["HALE"], "Collection split", is_key=True)
    with db.write(assessor.actor) as session, frozen_at(START):
        for control in (usual, key):
            rated(session, assessor, session.merge(control), "effective", "effective")
        assert controls.next_test_on(session, session.merge(usual)) == date(2027, 3, 2)
        assert controls.next_test_on(session, session.merge(key)) == date(2026, 9, 2)  # sooner
    with db.bookkeeping() as session:
        for row in session.scalars(select(Notice)):
            session.delete(row)
    with frozen_at(at("2026-08-25")):
        assert remind(db)["reminders"] == 2
    told = notices_of(db, owner)
    assert ("reminder", "Due in 8 days: review of RSK-0001 Freezer failure") in told
    assert ("reminder", "Due in 8 days: test of CTL-0002 Collection split") in told
    with frozen_at(at("2026-09-03")):
        assert remind(db)["overdue"] == 3  # the owner twice, and the assessor for the test
    assert ("overdue", "Test overdue by 1 day: test of CTL-0002 Collection split") in notices_of(
        db, people.accounts["assessor"]
    )
    with db.read() as session:
        shown = records.detail(
            session, steward, controls.CONTROL, find(session, controls.CONTROL, "CTL-0002")
        )
        assert shown["next_test_on"] == date(2026, 9, 2) and shown["test_due"] is True
