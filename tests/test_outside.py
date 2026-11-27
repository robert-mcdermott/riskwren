"""Outside auditors: one reported engagement or one scope, read-only, until a date, through a
link, with every view recorded."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.core.clock import frozen_at, utc_now
from riskwren.db.engine import Database
from riskwren.db.models import Event, OutsideAccess
from tests.people import People
from tests.test_engagements import as_person, planned
from tests.test_risks import who
from tests.test_scopes import add_scope

Clients = Callable[[str | None], TestClient]
HEADER = "X-RiskWren-Access"


def reported(as_role: Clients, people: People, db: Database) -> str:
    ref, ids = planned(as_role, people, db)
    chief, member = as_person(as_role, "Chief Auditor"), as_role("auditor")
    path = f"/api/v1/engagements/{ref}"
    chief.post(
        f"{path}/start", json={"lead": ids["Chief Auditor"], "members": [ids["Auditor Person"]]}
    )
    member.post(f"{path}/workpapers", json={"title": "Backups are taken"})
    chief.post(f"{path}/advance", json={})
    paper = member.get(path).json()["data"]["workpapers"][0]["id"]
    member.put(f"/api/v1/workpapers/{paper}", json={"done": "Read the job history."})
    chief.post(f"/api/v1/workpapers/{paper}/sign-off")
    chief.post(f"{path}/advance", json={})
    chief.post(f"{path}/advance", json={"summary": "All well.", "opinion": "effective"})
    return ref


def test_an_outsider_reads_one_reported_engagement_and_every_look_is_recorded(
    as_role: Clients, people: People, db: Database
) -> None:
    ref = reported(as_role, people, db)
    auditor = as_role("auditor")
    wanted = {"name": "Dana Reyes", "organization": "Halvard & Co.", "kind": "engagement",
              "ref": ref, "days": 30}  # fmt: skip
    assert as_role("manager").post("/api/v1/audit/outside", json=wanted).status_code == 403
    assert auditor.post("/api/v1/audit/outside", json={**wanted, "days": 0}).status_code == 422
    given = auditor.post("/api/v1/audit/outside", json=wanted)
    assert given.status_code == 201, given.text
    token = given.json()["meta"]["link"]["url"].split("#", 1)[1]
    with db.read() as session:
        kept = session.scalars(select(OutsideAccess)).one()
        assert token not in (kept.token_hash, str(kept.__dict__))

    nobody = as_role(None)
    assert nobody.get("/api/v1/outside").status_code == 404
    assert nobody.get("/api/v1/outside", headers={HEADER: "not-a-token"}).status_code == 404
    for _ in range(2):
        seen = nobody.get("/api/v1/outside", headers={HEADER: token})
        assert seen.status_code == 200, seen.text
    data = seen.json()["data"]
    assert data["engagement"]["ref"] == ref and data["engagement"]["workpapers"]
    assert data["about"]["organization"] == "Halvard & Co." and "can" not in data["engagement"]
    # Nothing else is reachable with it.
    assert nobody.get("/api/v1/risks", headers={HEADER: token}).status_code == 401
    with db.read() as session:
        looks = session.scalars(select(Event).where(Event.action == "outside.viewed")).all()
        assert len(looks) == 2 and looks[0].actor_kind == "outside"
        assert "Dana Reyes" in looks[0].actor_label and looks[0].subject_type == "engagement"
    listed = auditor.get("/api/v1/audit/outside").json()["data"]["grants"][0]
    assert listed["views"] == 2 and listed["state"] == "open"

    with frozen_at(utc_now() + timedelta(days=31)):
        assert as_role(None).get("/api/v1/outside", headers={HEADER: token}).status_code == 410
    auditor.post(f"/api/v1/audit/outside/{listed['id']}/revoke")
    assert nobody.get("/api/v1/outside", headers={HEADER: token}).status_code == 410


def test_a_scope_is_opened_and_work_in_progress_is_not(
    as_role: Clients, people: People, db: Database
) -> None:
    ref, ids = planned(as_role, people, db)
    auditor = as_role("auditor")
    early = auditor.post("/api/v1/audit/outside", json={
        "name": "x", "organization": "y", "kind": "engagement", "ref": ref, "days": 5})  # fmt: skip
    assert early.status_code == 409  # not reported
    manager = who(db, people, "manager")
    with db.write(manager.actor) as session:
        scope = add_scope(session, manager, people.units["IMM"], "Research enclave").ref
    given = auditor.post("/api/v1/audit/outside", json={
        "name": "Sam Ortiz", "organization": "The sponsor", "kind": "scope", "ref": scope,
        "days": 10}).json()  # fmt: skip
    token = given["meta"]["link"]["url"].split("#", 1)[1]
    seen = as_role(None).get("/api/v1/outside", headers={HEADER: token}).json()["data"]
    assert seen["scope"]["ref"] == scope and seen["frameworks"] == [] and "engagement" not in seen
    assert ids  # the team is not involved in opening a scope
