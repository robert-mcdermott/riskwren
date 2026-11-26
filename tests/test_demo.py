"""The demo organization: built by the real services, the same every time for a seed, with
something on every screen and a history that verifies."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from riskwren.api.app import create_app
from riskwren.cli import main
from riskwren.core.errors import RiskWrenError
from riskwren.db.engine import Database
from riskwren.db.models import (
    Acceptance,
    Account,
    Action,
    Control,
    Credential,
    Event,
    OrgUnit,
    Process,
    Risk,
    RiskAssessment,
    System,
    ThirdParty,
    TreatmentPlan,
)
from riskwren.demo import build as demo
from riskwren.demo import content
from riskwren.events import chain
from tests.conftest import Instance

TODAY = date(2026, 11, 18)


@pytest.fixture
def built(db: Database) -> demo.Summary:
    return demo.build(db, seed=7, today=TODAY)


def fingerprint(db: Database) -> list[tuple[object, ...]]:
    with db.read() as session:
        rows: list[tuple[object, ...]] = []
        rows += session.execute(
            select(Risk.ref, Risk.name, Risk.standing, Risk.residual_rating, Risk.next_review_on)
        ).all()
        rows += session.execute(select(Control.ref, Control.name, Control.rated_at)).all()
        rows += session.execute(select(Account.email, Account.title)).all()
        rows += session.execute(select(Action.ref, Action.status, Action.due_on)).all()
        rows += session.execute(select(Acceptance.risk_id, Acceptance.expires_on)).all()
        return [tuple(row) for row in rows]


def test_it_has_something_of_everything(db: Database, built: demo.Summary) -> None:
    with db.read() as session:
        count = lambda model: session.execute(select(func.count()).select_from(model)).scalar_one()  # noqa: E731
        group = lambda column: dict(  # noqa: E731
            session.execute(select(column, func.count()).group_by(column)).all()
        )
        assert count(OrgUnit) == 60 and count(Account) >= 200
        assert count(Process) >= 70 and count(System) >= 100 and count(ThirdParty) >= 40
        assert count(Risk) >= 170 and count(Control) >= 90 and count(RiskAssessment) >= 400
        assert count(TreatmentPlan) >= 15 and count(Acceptance) >= 12 and count(Action) >= 60
        standings = group(Risk.standing)
        assert set(standings) == {
            "within", "needs_decision", "treated", "accepted", "not_assessed", "closed"
        }  # fmt: skip
        # Most of the register is in order, as a real one would be.
        assert standings["within"] > standings["needs_decision"] > standings["treated"] > 0
        assert set(group(Risk.residual_rating)) >= {"low", "moderate", "high", "critical"}
        assert {"active", "complete"} <= set(group(TreatmentPlan.status))
        assert {"open", "in_progress", "done"} <= set(group(Action.status))
        assert {"in_service", "unsupported", "sunsetting"} <= set(group(System.lifecycle))
        assert group(System.status).get("retired", 0) >= 1
        # Something due, something overdue, and an acceptance about to expire.
        overdue = select(func.count()).where(
            Action.status.in_(("open", "in_progress")), Action.due_on < TODAY
        )
        assert session.execute(overdue).scalar_one() >= 3
        soon = select(func.count()).where(
            Acceptance.withdrawn_at.is_(None),
            Acceptance.expires_on.between(TODAY, TODAY + timedelta(days=45)),
        )
        assert session.execute(soon).scalar_one() >= 1
        late = select(func.count()).where(Risk.next_review_on < TODAY, Risk.status != "closed")
        assert session.execute(late).scalar_one() >= 3
        assert (
            session.execute(
                select(func.count()).where(Risk.escalated_to_unit_id.is_not(None))
            ).scalar_one()
            >= 3
        )
        assert (
            session.execute(select(func.count()).where(Control.rated_at.is_(None))).scalar_one()
            >= 3
        )
        # Four levels of units.
        parents = dict(session.execute(select(OrgUnit.id, OrgUnit.parent_id)).all())
        depth = lambda unit: 1 if parents[unit] is None else 1 + depth(parents[unit])  # noqa: E731
        assert max(depth(unit) for unit in parents) == 4
        # Two years of history.
        first, last = session.execute(select(func.min(Event.at), func.max(Event.at))).one()
        assert (last - first).days > 700


def test_the_storylines_came_out_as_written(db: Database, built: demo.Summary) -> None:
    with db.read() as session:
        named = lambda name: session.scalars(select(Risk).where(Risk.name == name)).one()  # noqa: E731
        specimens = named("Loss of irreplaceable specimens from freezer failure")
        assert (specimens.inherent_rating, specimens.residual_rating) == ("critical", "high")
        assert (specimens.standing, specimens.target_rating) == ("treated", "moderate")
        ransomware = named("Ransomware reaching research storage")
        newest = session.scalars(
            select(RiskAssessment)
            .where(RiskAssessment.risk_id == ransomware.id, RiskAssessment.kind == "residual")
            .order_by(RiskAssessment.id.desc())
        ).first()
        assert newest is not None and newest.suggested is not None
        assert (newest.rating, newest.suggested["rating"]) == ("high", "moderate")
        workstation = named("Unsupported workstation controlling the cryo-electron microscope")
        acceptance = session.scalars(
            select(Acceptance).where(Acceptance.risk_id == workstation.id)
        ).one()
        assert workstation.standing == "accepted" and acceptance.conditions
        assert acceptance.expires_on == TODAY + timedelta(days=24)
        tracking = named("Outage of the hosted specimen tracking service")
        given = session.scalars(select(Acceptance).where(Acceptance.risk_id == tracking.id)).one()
        assert given.accepted_by_name == "Soren Eriksen" and tracking.standing == "accepted"
        costs = named("Unallowable costs charged to a federal award")
        assert (costs.residual_rating, costs.standing) == ("high", "needs_decision")
        plan = session.scalars(select(TreatmentPlan).where(TreatmentPlan.risk_id == costs.id)).one()
        assert plan.status == "active" and plan.due_on < TODAY
        supplier = named("Sole-source dependence on Brightwater Reagents for sequencing chemistry")
        assert (supplier.response, supplier.standing) == ("reduce", "treated")
        animals = named("Loss of environmental control in the animal facility")
        assert animals.standing == "needs_decision"
        accounts_ = named("Staff accounts taken over through stolen passwords")
        history = session.scalars(
            select(RiskAssessment.rating)
            .where(RiskAssessment.risk_id == accounts_.id, RiskAssessment.kind == "residual")
            .order_by(RiskAssessment.id)
        ).all()
        assert history == ["moderate", "high"]
        closed = named("Loss of refrigerated medication from a failed pharmacy refrigerator")
        assert closed.status == "closed" and closed.closed_reason
        power = named("Emergency power cannot carry the freezer farm and animal facility")
        assert (power.residual_rating, power.standing) == ("critical", "accepted")
        assert power.escalated_to_unit_id is not None
        privacy = named("Identifiable survey responses held on lab laptops")
        assert privacy.escalated_to_unit_id is not None and privacy.escalation_reason
        gone = session.scalars(select(Account).where(Account.status == "disabled")).one()
        assert gone.title == "Principal Investigator"
    assert built.counts["acceptances refused"] == 1


def test_the_history_verifies_and_runs_forward(db: Database, built: demo.Summary) -> None:
    with db.engine.connect() as conn:
        report = chain.verify(conn)
    assert report.ok and report.events > 4000
    with db.read() as session:
        times = [at for (at,) in session.execute(select(Event.at).order_by(Event.id))]
    assert times == sorted(times)


def test_nobody_in_the_demo_has_a_password_and_everyone_is_invented(
    db: Database, built: demo.Summary
) -> None:
    with db.read() as session:
        assert session.execute(select(func.count()).select_from(Credential)).scalar_one() == 0
        emails = [email for (email,) in session.execute(select(Account.email))]
    assert all(email.endswith("@northmere.example") for email in emails)
    assert len(emails) == len(set(emails))
    assert [person["role"] for person in built.sample_accounts] == [
        role for _, role, _ in content.SAMPLE
    ]


def test_the_same_seed_gives_the_same_organization(tmp_path: Path) -> None:
    from riskwren.db import migrate

    prints = []
    for name, seed in (("a", 3), ("b", 3), ("c", 4)):
        db = Database(f"sqlite:///{tmp_path / name}.db")
        migrate.upgrade(db.engine)
        demo.build(db, seed=seed, today=TODAY)
        prints.append(fingerprint(db))
        db.dispose()
    assert prints[0] == prints[1]
    assert prints[0] != prints[2]


def test_it_will_not_build_over_an_organization(db: Database, built: demo.Summary) -> None:
    with pytest.raises(RiskWrenError):
        demo.build(db, seed=7, today=TODAY)


def test_sample_people_sign_in_with_one_click_only_on_a_demo(
    instance: Instance, db: Database, client: TestClient
) -> None:
    assert client.get("/api/v1/meta").json()["data"]["demo"] is None
    email = "mireille.lachance@northmere.example"
    assert client.post("/api/v1/session/demo", json={"email": email}).status_code == 404

    demo.build(db, seed=7, today=TODAY)
    shown = client.get("/api/v1/meta").json()["data"]["demo"]
    assert [person["name"] for person in shown["accounts"]][:2] == [
        "Mireille Lachance", "Chidi Udoka"
    ]  # fmt: skip
    with db.read() as session:
        other = session.scalars(
            select(Account.email).where(
                Account.email.notin_([p["email"] for p in shown["accounts"]])
            )
        ).first()
    assert client.post("/api/v1/session/demo", json={"email": other}).status_code == 404

    done = client.post("/api/v1/session/demo", json={"email": email})
    assert done.status_code == 200 and "manager" in done.json()["data"]["roles"]
    assert client.get("/api/v1/dashboard").status_code == 200
    assert client.get("/api/v1/risks").json()["data"]

    with TestClient(create_app(instance.config), client=("203.0.113.9", 4000)) as elsewhere:
        away = elsewhere.post(
            "/api/v1/session/demo", json={"email": email}, headers={"origin": "http://testserver"}
        )
    assert away.status_code == 404


def test_every_sample_person_has_something_to_look_at(
    instance: Instance, db: Database, built: demo.Summary
) -> None:
    seen = {}
    for person in built.sample_accounts:
        with TestClient(create_app(instance.config)) as client:
            signed = client.post("/api/v1/session/demo", json={"email": person["email"]})
            assert signed.status_code == 200, person["name"]
            assert client.get("/api/v1/systems").json()["data"], person["name"]
            assert client.get("/api/v1/home").status_code == 200
            seen[person["role"]] = client.get("/api/v1/risks").json()["meta"]["total"]
            if person["role"] == "Staff member":
                mine = client.get("/api/v1/actions", params={"mine": "true"}).json()["data"]
                assert any("second aliquot" in action["title"] for action in mine)
    # Those who read everything see everything; a steward sees a unit; a member, their own.
    assert seen["Risk manager"] == seen["Auditor"] == seen["Assessor"] == seen["Administrator"]
    assert seen["Risk manager"] > seen["Division leader"] > seen["Steward"] >= seen["Staff member"]
    assert seen["Staff member"] >= 3


@pytest.mark.sqlite_only
def test_the_command_builds_a_demo_and_refuses_to_overwrite_other_things(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "demo"
    assert main(["demo", str(target), "--seed", "2"]) == 0
    out = capsys.readouterr().out
    assert "which verify" in out and f"--config {target / 'riskwren.toml'} serve" in out
    assert main(["demo", str(target)]) != 0  # already there
    assert main(["demo", str(target), "--force"]) == 0
    other = tmp_path / "other"
    other.mkdir()
    (other / "notes.txt").write_text("keep me")
    assert main(["demo", str(other), "--force"]) != 0
    assert (other / "notes.txt").read_text() == "keep me"
    assert main(["--config", str(target / "riskwren.toml"), "serve", "--host", "0.0.0.0"]) != 0
