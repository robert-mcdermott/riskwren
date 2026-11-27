"""Dossiers, the security plan, and a scope in OSCAL: a package that proves itself, and plans
in the customary order and the open format."""

from __future__ import annotations

import io
import json
import re
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.cli import main
from riskwren.compliance import issues, packs
from riskwren.db.engine import Database
from riskwren.db.models import Event
from riskwren.insight import dossier, oscal
from riskwren.inventory import records
from riskwren.inventory.registry import THIRD_PARTY
from tests.conftest import TESTER
from tests.people import People
from tests.test_assessments import world
from tests.test_evidence import PDF
from tests.test_risks import judge, raise_risk, who
from tests.test_treatment import add_control

Clients = Callable[[str | None], TestClient]


@pytest.fixture
def scoped(db: Database, people: People) -> dict[str, str]:
    """A provider scope held to the CSF doing backups and a second factor, with a file of
    evidence for the backups, and an open issue about the scope."""
    with db.write(TESTER) as session:
        packs.install(session)
    manager = who(db, people, "manager")
    with db.write(manager.actor) as session:
        central, _, backups, _ = world(session, people, manager)
        issues.create(session, manager, {"name": "Restore never tested", "severity": "high",
                                         "org_unit_id": people.units["CANCER"],
                                         "subjects": [central.ref]})  # fmt: skip
        return {"scope": central.ref, "control": backups.ref}


def evidence_file(client: TestClient, people: People, control: str) -> str:
    made = client.post("/api/v1/evidence", json={"name": "Restore report", "kind": "file",
                       "org_unit_id": people.units["CANCER"]}).json()["data"]  # fmt: skip
    client.post(f"/api/v1/evidence/{made['ref']}/file", params={"name": "restore.pdf"},
                content=PDF)  # fmt: skip
    client.put(f"/api/v1/evidence/{made['ref']}/subjects", json={"subjects": [control]})
    return str(made["ref"])


def rezip(data: bytes, change: Callable[[dict[str, bytes]], None]) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    change(files)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return out.getvalue()


def test_a_dossier_holds_the_record_and_its_manifest_verifies(
    as_role: Clients, people: People, db: Database, scoped: dict[str, str], tmp_path: Path
) -> None:
    manager = as_role("manager")
    item = evidence_file(manager, people, scoped["control"])
    got = manager.get(f"/api/v1/dossiers/{scoped['scope']}")
    assert got.status_code == 200, got.text
    assert got.headers["content-type"] == "application/zip"
    assert got.headers["content-disposition"].startswith(f'attachment; filename="{scoped["scope"]}')
    data = got.content
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
        assert archive.read(f"files/{item}-restore.pdf") == PDF
        ssp = json.loads(archive.read("oscal/ssp-nist-csf.json"))
        plan = archive.read("security-plan.html").decode()
    assert {"record.json", "history.json", "index.html", "security-plan.html", "evidence.json",
            "oscal/poam.json", "scope/statement-nist-csf.json"} <= names  # fmt: skip
    assert {item["path"] for item in manifest["files"]} == names - {"manifest.json"}
    assert manifest["record"]["ref"] == scoped["scope"] and manifest["left_out"] == []
    assert (
        ssp["system-security-plan"]["system-characteristics"]["system-name"] == "Central computing"
    )
    assert "1. System identification" in plan and "Backups" in plan

    checked = manager.post("/api/v1/dossiers/check", content=data).json()["data"]
    assert checked["verified"] is True and checked["problems"] == []
    assert checked["recorded"]["by"] == "Manager Person"
    with db.read() as session:
        taken = session.scalars(select(Event).where(Event.action == "dossier.taken")).one()
        assert taken.changes["fingerprint"][1] == manifest["fingerprint"]
    whole = tmp_path / "dossier.zip"
    whole.write_bytes(data)
    assert main(["check-dossier", str(whole)]) == 0

    def edit_record(files: dict[str, bytes]) -> None:
        files["record.json"] = files["record.json"].replace(b"Central", b"Centrall")

    def add_file(files: dict[str, bytes]) -> None:
        files["extra.txt"] = b"not listed"

    def drop_from_manifest(files: dict[str, bytes]) -> None:
        listed = json.loads(files["manifest.json"])
        listed["files"] = [f for f in listed["files"] if f["path"] != "history.json"]
        files["manifest.json"] = json.dumps(listed).encode()
        del files["history.json"]

    for change, said in ((edit_record, "record.json has been changed."),
                         (add_file, "extra.txt is not in the manifest."),
                         (drop_from_manifest, "The manifest has been changed")):  # fmt: skip
        broken = rezip(data, change)
        found = dossier.verify(broken)
        assert found["verified"] is False
        assert any(problem.startswith(said) for problem in found["problems"]), found["problems"]
        whole.write_bytes(broken)
        assert main(["check-dossier", str(whole)]) == 1
    assert dossier.verify(b"not a zip")["problems"] == ["This is not a ZIP file."]
    # Only what the person may see: the member's unit is the Hale Lab.
    assert as_role("member").get(f"/api/v1/dossiers/{scoped['scope']}").status_code == 404


def test_a_scope_in_oscal_and_as_a_security_plan(as_role: Clients, scoped: dict[str, str]) -> None:
    manager = as_role("manager")
    first = manager.get(f"/api/v1/scopes/{scoped['scope']}/oscal/ssp").json()
    again = manager.get(f"/api/v1/scopes/{scoped['scope']}/oscal/ssp?framework=nist-csf").json()
    plan = first["system-security-plan"]
    assert plan["metadata"]["oscal-version"] == oscal.VERSION
    for key in ("uuid", "import-profile", "system-characteristics", "system-implementation",
                "control-implementation", "back-matter"):  # fmt: skip
        assert key in plan, key
    assert plan["import-profile"]["href"] == "#" + plan["back-matter"]["resources"][0]["uuid"]
    requirements = plan["control-implementation"]["implemented-requirements"]
    assert requirements and all(
        re.match(r"^[a-z_][\w.\-]*$", r["control-id"]) for r in requirements
    )
    assert [r["uuid"] for r in requirements] == [
        r["uuid"] for r in again["system-security-plan"]["control-implementation"][
            "implemented-requirements"]
    ]  # fmt: skip
    states = {c["implementation-status"]["state"] for r in requirements for c in r["by-components"]}
    assert states <= set(oscal.STATUS.values()) and "implemented" in states
    poam = manager.get(f"/api/v1/scopes/{scoped['scope']}/oscal/poam").json()
    items = poam["plan-of-action-and-milestones"]["poam-items"]
    assert [item["title"].split(" ", 1)[1] for item in items] == ["Restore never tested"]
    assert manager.get(f"/api/v1/scopes/{scoped['scope']}/oscal/other").status_code == 404
    page = manager.get(f"/api/v1/scopes/{scoped['scope']}/security-plan")
    assert page.headers["content-disposition"].endswith('-security-plan.html"')
    assert page.headers["content-security-policy"] == "default-src 'none'; sandbox"
    text = page.text
    order = [text.index(heading) for heading in (
        "1. System identification", "2. System description", "3. What the system includes",
        "4. What it is held to", "5. Control implementation", "Plan of action and milestones",
    )]  # fmt: skip
    assert order == sorted(order) and "Restore never tested" in text
    assert oscal.control_id("AC-2(1)") == "ac-2.1" and oscal.control_id("03.01.01") == "_03.01.01"


def test_a_risk_and_a_third_party_have_dossiers_too(
    as_role: Clients, people: People, db: Database
) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        risk = raise_risk(session, steward, people.units["IMM"], "Freezer failure")
        judge(session, steward, risk, "inherent", 4, safety=4)
        party = records.create(session, steward, THIRD_PARTY, {
            "name": "Coldline Service", "kind": "service_provider",
            "org_unit_id": people.units["IMM"]})  # fmt: skip
        refs = (risk.ref, party.ref)
    manager = as_role("manager")
    for ref, expected in zip(refs, ("risk/treatment.json", "third-party/reviews.json"),
                             strict=True):  # fmt: skip
        data = manager.get(f"/api/v1/dossiers/{ref}").content
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert expected in archive.namelist()
        assert dossier.verify(data)["verified"] is True
    boss = who(db, people, "manager")
    with db.write(boss.actor) as session:
        control = add_control(session, boss, people.units["IMM"], "Backups").ref
    assert manager.get(f"/api/v1/dossiers/{control}").status_code == 422
