"""Import and export: a record's name in other systems; every list out as CSV or JSON, as
filtered and as its reader may see it; records in from a spreadsheet with its columns
matched, a dry run, and every problem by row; and a list that goes out of one installation
and into an empty one unchanged."""

from __future__ import annotations

import csv
import io
import json
import uuid
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url

from riskwren.api.app import create_app
from riskwren.compliance import frameworks, packs, scopes
from riskwren.config import example_config_text, load_config
from riskwren.controls.service import CONTROL
from riskwren.core.errors import Invalid
from riskwren.db import migrate
from riskwren.db.engine import Database
from riskwren.db.models import Event
from riskwren.events.actor import Actor
from riskwren.home import DataHome
from riskwren.inventory import history, records
from riskwren.inventory.registry import PROCESS, SYSTEM
from riskwren.program import packs as program_packs
from riskwren.program import vocab
from riskwren.risk import register
from tests.conftest import POSTGRES, POSTGRES_URL, TESTER
from tests.people import People, email_of, seed, sign_in
from tests.test_risks import who
from tests.test_scopes import add_scope
from tests.test_treatment import add_control

Clients = Callable[[str | None], TestClient]
ELSEWHERE = [{"system": "asset_tag", "value": "NM-004417"}, {"system": "ticket", "value": "CHG-88"}]


def add_system(session, by, unit: int, name: str = "Freezer monitoring", **more):  # type: ignore[no-untyped-def]
    values = {"name": name, "kind": "application", "org_unit_id": unit, **more}
    return records.create(session, by, SYSTEM, values)


def sheet(response) -> list[dict[str, str]]:  # type: ignore[no-untyped-def]
    assert response.status_code == 200, response.text
    return list(csv.DictReader(io.StringIO(response.text)))


def send(client: TestClient, path: str, content: str, **params):  # type: ignore[no-untyped-def]
    if isinstance(params.get("mapping"), dict):
        params["mapping"] = json.dumps(params["mapping"])
    answer = client.post(f"/api/v1/imports/{path}", content=content, params=params)
    return answer


@pytest.fixture
def elsewhere(tmp_path: Path) -> Iterator[TestClient]:
    """A second installation with the same units and people and nothing else, signed in to
    as its manager."""
    path = tmp_path / "elsewhere" / "riskwren.toml"
    path.parent.mkdir()
    path.write_text(example_config_text(), encoding="utf-8")
    with ExitStack() as stack:
        env = {}
        if POSTGRES:
            name = f"t_{uuid.uuid4().hex[:24]}"
            admin = create_engine(POSTGRES_URL, isolation_level="AUTOCOMMIT")
            stack.callback(admin.dispose)
            with admin.connect() as conn:
                conn.execute(text(f'CREATE DATABASE "{name}"'))

            def drop() -> None:
                with admin.connect() as conn:
                    conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))

            stack.callback(drop)
            url = make_url(POSTGRES_URL).set(database=name)
            env["RISKWREN_DATABASE_URL"] = url.render_as_string(hide_password=False)
        config = load_config(path, env=env)
        DataHome(config.data.home).create()
        db = Database(config.database_url)
        stack.callback(db.dispose)
        migrate.upgrade(db.engine)
        with db.write(Actor.command("Setup")) as session:
            program_packs.install(session, frameworks=False)
        seed(db)
        client = stack.enter_context(TestClient(create_app(config), base_url="http://localhost"))
        yield sign_in(client, email_of("manager"))


# --- External references --------------------------------------------------------------------


def test_a_record_carries_what_it_is_called_elsewhere(db: Database, people: People) -> None:
    steward, member = who(db, people, "steward"), who(db, people, "member")
    hale = people.units["HALE"]
    with db.write(steward.actor) as session:
        system = add_system(session, steward, hale, external_refs=[*ELSEWHERE, ELSEWHERE[0]])
        found = records.detail(session, steward, SYSTEM, system)["external_refs"]
        assert [(r["system"], r["label"], r["value"], r["url"]) for r in found] == [
            ("asset_tag", "Asset tag", "NM-004417", None), ("ticket", "Ticket", "CHG-88", None),
        ]  # fmt: skip
        # It is found by that name, by anyone who may see it.
        assert [r.ref for r in records.search(session, member, SYSTEM, {"q": "nm-0044"})[0]] == [
            system.ref
        ]
        assert records.search(session, member, SYSTEM, {"q": "CHG-89"})[1] == 0
        with pytest.raises(Invalid) as bad:
            records.update(
                session,
                steward,
                SYSTEM,
                system,
                {
                    "external_refs": [
                        {"system": "abacus", "value": "1"},
                        {"system": "ticket", "value": " "},
                    ]
                },
                version=system.version,
            )
        assert "abacus" in bad.value.errors["external_refs"]
        # A system with a pattern gives a link, with the identifier made safe for an address.
        systems = vocab.get(session, "external_systems")
        systems[2] = {**systems[2], "url": "https://desk.northmere.example/t/{id}"}
        vocab.put(session, "external_systems", systems)
        records.update(
            session,
            steward,
            SYSTEM,
            system,
            {"external_refs": [{"system": "ticket", "value": "CHG 90/a"}]},
            version=system.version,
        )
        found = records.detail(session, steward, SYSTEM, system)["external_refs"]
        assert [(r["value"], r["url"]) for r in found] == [
            ("CHG 90/a", "https://desk.northmere.example/t/CHG%2090%2Fa")
        ]
        told = [entry["title"] for entry in history.for_record(session, SYSTEM, system)]
        assert "Now also known as CHG 90/a (ticket)" in told
        assert "No longer known as NM-004417 (asset tag)" in told


# --- Out ------------------------------------------------------------------------------------


def test_a_list_goes_out_as_filtered_and_as_its_reader_may_see_it(
    as_role: Clients, db: Database, people: People
) -> None:
    manager, member = who(db, people, "manager"), as_role("member")
    hale, cancer = people.units["HALE"], people.units["CANCER"]
    with db.write(manager.actor) as session:
        add_system(
            session,
            manager,
            hale,
            "=SUM(A1) is its name",
            criticality="high",
            tags=["cold", "alarm"],
            external_refs=ELSEWHERE,
            summary='Says "hello",\nand more',
        )
        add_system(session, manager, hale, "Sealed", restricted=True)
        add_system(session, manager, cancer, "In another division", criticality="high")
    chief = as_role("manager")
    answer = chief.get("/api/v1/exports/systems")
    assert answer.headers["content-type"].startswith("text/csv")
    assert answer.headers["content-disposition"] == 'attachment; filename="riskwren-systems.csv"'
    assert answer.headers["x-content-type-options"] == "nosniff"
    rows = sheet(answer)
    assert [row["ref"] for row in rows] == ["SYS-0001", "SYS-0002", "SYS-0003"]
    first = rows[0]
    # A name a spreadsheet would run as a formula is written so that it will not.
    assert (
        first["name"] == "'=SUM(A1) is its name" and first["summary"] == 'Says "hello",\nand more'
    )
    assert (first["unit"], first["owners"], first["criticality"]) == (
        "HALE",
        email_of("manager"),
        "high",
    )
    assert (first["tags"], first["restricted"]) == ("cold; alarm", "no")
    assert first["external_refs"] == "asset_tag:NM-004417; ticket:CHG-88"
    # As filtered.
    assert [
        r["ref"]
        for r in sheet(
            chief.get("/api/v1/exports/systems", params={"criticality": "high", "unit": hale})
        )
    ] == ["SYS-0001"]
    assert [
        r["ref"] for r in sheet(chief.get("/api/v1/exports/systems", params={"q": "chg-88"}))
    ] == ["SYS-0001"]
    # As its reader may see it: a member does not get what is restricted.
    assert [r["ref"] for r in sheet(member.get("/api/v1/exports/systems"))] == [
        "SYS-0001",
        "SYS-0003",
    ]
    # The same list as JSON, with its values as values.
    document = chief.get(
        "/api/v1/exports/systems", params={"format": "json", "criticality": "high"}
    ).json()
    assert document["list"] == "systems" and document["columns"][:3] == ["ref", "name", "summary"]
    assert (
        document["rows"][0]["tags"] == ["cold", "alarm"]
        and document["rows"][0]["restricted"] is False
    )
    assert chief.get("/api/v1/exports/systems", params={"format": "pdf"}).status_code == 422
    assert chief.get("/api/v1/exports/abacus").status_code == 404
    assert as_role(None).get("/api/v1/exports/systems").status_code == 401
    # Each export is in the history: who took what, how much, and as filtered how.
    with db.read() as session:
        taken = session.scalars(
            select(Event).where(Event.action == "exported").order_by(Event.id)
        ).all()
        assert len(taken) == 5
        assert taken[1].actor_label == manager.name
        assert {key: pair[1] for key, pair in taken[1].changes.items()} == {
            "list": "systems", "format": "csv", "rows": 1,
            "filters": {"criticality": "high", "unit": str(hale)},
        }  # fmt: skip


def test_the_other_lists_go_out_too(as_role: Clients, db: Database, people: People) -> None:
    from riskwren.compliance import issues
    from riskwren.treatment import service as treatment
    from tests.test_risks import judge, raise_risk

    manager = who(db, people, "manager")
    hale = people.units["HALE"]
    with db.write(manager.actor) as session:
        program_packs.install(session)
        risk = raise_risk(session, manager, hale)
        judge(session, manager, risk, "inherent", 4, mission=4)
        plan = treatment.create_plan(
            session,
            manager,
            risk,
            objective="Bring it down",
            owner_id=manager.account_id,
            due_on="2031-01-01",
        )
        treatment.add_action(
            session,
            manager,
            plan,
            title="Buy a spare",
            owner_id=manager.account_id,
            due_on="2030-06-01",
        )
        control = add_control(session, manager, hale, "Backups", library_key="backups_tested")
        scope = add_scope(session, manager, hale, "The enclave")
        scopes.hold_to(session, manager, scope, "nist-csf", None)
        scopes.implement(session, manager, scope, control, status="in_place")
        issue = issues.create(
            session,
            manager,
            {"name": "No spare", "org_unit_id": hale, "severity": "high", "subjects": [scope.ref]},
        )
        issues.add_action(
            session,
            manager,
            issue,
            title="Order it",
            owner_id=manager.account_id,
            due_on="2030-07-01",
        )
    chief = as_role("manager")
    actions = sheet(chief.get("/api/v1/exports/actions"))
    assert [(a["ref"], a["title"], a["for"], a["status"]) for a in actions] == [
        ("ACT-0001", "Buy a spare", risk.ref, "open"),
        ("ACT-0002", "Order it", "ISS-0001", "open"),
    ]
    assert [
        (p["ref"], p["risk"], p["actions"]) for p in sheet(chief.get("/api/v1/exports/plans"))
    ] == [(plan.ref, risk.ref, "1")]
    assert sheet(chief.get("/api/v1/exports/acceptances")) == []
    risks = sheet(chief.get("/api/v1/exports/risks"))
    assert (
        risks[0]["ref"],
        risks[0]["category"],
        risks[0]["inherent_rating"],
        risks[0]["standing"],
    ) == (risk.ref, "data_quality", "high", "not_assessed")
    listed = sheet(chief.get("/api/v1/exports/issues", params={"status": "live"}))
    assert (
        listed[0]["ref"],
        listed[0]["severity"],
        listed[0]["actions"],
        listed[0]["overdue"],
    ) == ("ISS-0001", "high", "1", "no")
    assert [s["frameworks"] for s in sheet(chief.get("/api/v1/exports/scopes"))] == [
        "NIST Cybersecurity Framework"
    ]
    required = sheet(chief.get("/api/v1/exports/requirements", params={"framework": "nist-csf"}))
    assert len(required) > 100 and required[0]["code"] == "GV" and required[1]["parent"] == "GV"
    stated = sheet(
        chief.get(
            "/api/v1/exports/statement",
            params={"scope": scope.ref, "framework": "nist-csf", "state": "in_place"},
        )
    )
    assert {row["code"] for row in stated} == {"PR.DS-11", "RC.RP-03"}
    assert stated[0]["controls"].startswith(f"{control.ref} Backups (in_place)")
    assert (
        chief.get(
            "/api/v1/exports/statement", params={"scope": "SCP-9999", "framework": "nist-csf"}
        ).status_code
        == 404
    )


# --- In -------------------------------------------------------------------------------------

FILE = """Asset name,Looked after by,Department,How critical,Type,Notes,Tag
Freezer monitoring,steward@northmere.example,HALE,High,Application,Alarms for bay 3,asset_tag:NM-1
Sample tracker,steward@northmere.example; delegate:member@northmere.example,Hale Lab,moderate,application,,
"""


def test_a_spreadsheet_is_matched_checked_and_only_then_loaded(
    as_role: Clients, db: Database, people: People
) -> None:
    steward = as_role("steward")
    found = send(steward, "records/systems/columns", FILE).json()["data"]
    assert (
        found["columns"][:3] == ["Asset name", "Looked after by", "Department"]
        and found["rows"] == 2
    )
    guessed = {field["name"]: field["column"] for field in found["fields"]}
    # What the headings make plain is matched; the rest is for the person to say.
    assert (guessed["unit"], guessed["name"], guessed["owners"]) == ("Department", None, None)
    assert [f["name"] for f in found["fields"] if f["required"]] == ["name", "unit", "kind"]
    assert "Asset name" in found["unused"]
    unmapped = send(steward, "records/systems", FILE)
    assert unmapped.status_code == 422 and "Say which column holds: Name, Kind." in unmapped.text
    mapping = {
        "name": "Asset name",
        "owners": "Looked after by",
        "criticality": "How critical",
        "kind": "Type",
        "summary": "Notes",
        "external_refs": "Tag",
    }
    assert (
        send(steward, "records/systems", FILE, mapping={"name": "No such column"}).status_code
        == 422
    )
    checked = send(steward, "records/systems", FILE, mapping=mapping).json()["data"]
    assert checked == {
        "kind": "systems",
        "dry_run": True,
        "applied": False,
        "rows": 2,
        "created": 2,
        "updated": 0,
        "unchanged": 0,
        "problems": [],
    }
    with db.read() as session:
        assert (
            records.search(session, who(db, people, "manager"), SYSTEM, {})[1] == 0
        )  # a dry run keeps nothing
    loaded = send(steward, "records/systems", FILE, mapping=mapping, dry_run=False).json()["data"]
    assert loaded["applied"] and loaded["created"] == 2
    listed = sheet(steward.get("/api/v1/exports/systems"))
    assert [(r["ref"], r["name"], r["unit"], r["criticality"], r["kind"]) for r in listed] == [
        ("SYS-0001", "Freezer monitoring", "HALE", "high", "application"),
        ("SYS-0002", "Sample tracker", "HALE", "moderate", "application"),
    ]  # fmt: skip
    assert (
        listed[0]["external_refs"] == "asset_tag:NM-1"
        and listed[0]["summary"] == "Alarms for bay 3"
    )
    assert listed[1]["owners"] == f"{email_of('steward')}; delegate:{email_of('member')}"
    with db.read() as session:
        told = history.for_record(
            session, SYSTEM, records.load(session, who(db, people, "manager"), SYSTEM, "SYS-0001")
        )
        assert told[-1]["title"] == "Added this system" and told[-1]["actor"] == "Steward Person"
    # Loading the same file again would add everything twice, so it adds nothing.
    again = send(steward, "records/systems", FILE, mapping=mapping, dry_run=False).json()["data"]
    assert not again["applied"] and [p["row"] for p in again["problems"]] == [2, 3]
    assert "already on record in the unit, as SYS-0001" in again["problems"][0]["message"]


def test_every_problem_is_reported_by_row_and_nothing_is_loaded(
    as_role: Clients, db: Database, people: People
) -> None:
    steward = as_role("steward")
    bad = """name,unit,kind,criticality,owners,restricted,external_refs,ref,status
Good one,HALE,application,high,,no,,,
,HALE,application,,,,,,
No such unit,BASEMENT,application,,,,,,
Wrong choices,HALE,gizmo,vital,nobody@northmere.example,perhaps,abacus:1,PRC-0001,dormant
Good one,HALE,application,,,,,,
Not theirs,CANCER,application,,,,,,
"""
    report = send(steward, "records/systems", bad, dry_run=False).json()["data"]
    assert not report["applied"] and report["rows"] == 6 and report["created"] == 1
    by_row: dict[int, list[str]] = {}
    for problem in report["problems"]:
        by_row.setdefault(problem["row"], []).append(problem["message"])
    assert set(by_row) == {3, 4, 5, 6, 7}
    assert by_row[3] == ["Name: Give it a name."]
    assert by_row[4] == ["Unit: there is no unit 'BASEMENT'."]
    assert by_row[5] == [
        "Owners: nobody has the address 'nobody@northmere.example'.",
        "Restricted: say yes or no.",
        "External references: 'abacus:1' is not a system on record, a colon, and an identifier.",
    ]
    assert "already on record in the unit, from an earlier row" in by_row[6][0]
    assert "steward of the unit, or a manager" in by_row[7][0]
    with db.read() as session:
        assert records.search(session, who(db, people, "manager"), SYSTEM, {})[1] == 0
    # With the owner, restricted, and tag put right, what is left is for the service to say.
    fixed = bad.replace(
        "nobody@northmere.example,perhaps,abacus:1", "member@northmere.example,yes,ticket:1"
    )
    by_row = {}
    for problem in send(steward, "records/systems", fixed).json()["data"]["problems"]:
        by_row.setdefault(problem["row"], []).append(problem["message"])
    assert sorted(by_row[5]) == [
        "Criticality: 'vital' is not one of the choices.",
        "Kind: 'gizmo' is not one of the choices.",
        "Status: Use active or retired.",
    ]
    wrong_ref = "name,unit,kind,ref\nA,HALE,application,PRC-0001\n"
    assert (
        "not a reference for systems"
        in send(steward, "records/systems", wrong_ref).json()["data"]["problems"][0]["message"]
    )
    assert (
        send(steward, "records/systems", "name,unit,kind\n").json()["data"]["problems"][0][
            "message"
        ]
        == "The file has a header and no rows."
    )
    assert send(steward, "records/systems", "name,name,unit\nA,B,HALE\n").status_code == 422
    assert send(steward, "records/issues", "name,unit\nA,HALE\n").status_code == 404
    # A member is not let in to import at all; an assessor neither.
    assert send(as_role("member"), "records/systems", fixed).status_code == 403


def test_risks_and_controls_come_in_as_records_and_never_as_judgments(
    as_role: Clients, db: Database, people: People
) -> None:
    chief = as_role("manager")
    risks = """name,unit,category,cause,event,consequence,owners,residual_rating,standing
Loss of the freezer farm,HALE,Data and specimen integrity,Power fails,Freezers warm,Specimens lost,steward@northmere.example,low,in_order
"""
    report = send(chief, "records/risks", risks, dry_run=False).json()["data"]
    assert not report["problems"], report
    assert report["applied"] and report["created"] == 1
    controls = "name,unit,statement,kind,frequency,design,operation,state\nNightly copy,HALE,Copied every night,Preventive,Daily,effective,effective,effective\n"
    assert send(chief, "records/controls", controls, dry_run=False).json()["data"]["applied"]
    with db.read() as session:
        manager = who(db, people, "manager")
        risk = records.load(session, manager, register.RISK, "RSK-0001")
        # What a file says of a rating is not read: a rating is a judgment made here.
        assert (risk.cause, risk.residual_rating, risk.standing) == (
            "Power fails",
            None,
            "not_assessed",
        )
        assert [
            o["email"] for o in records.detail(session, manager, register.RISK, risk)["owners"]
        ] == [email_of("steward")]
        control = records.load(session, manager, CONTROL, "CTL-0001")
        assert (control.kind, control.frequency, control.design) == (
            "preventive",
            "daily",
            "not_assessed",
        )
    bad = send(
        chief,
        "records/risks",
        risks.replace("Data and specimen integrity", "Weather").replace("Loss of", "Loss  of"),
    ).json()["data"]
    assert bad["problems"] == [{"row": 2, "message": "Category: 'Weather' is not a risk category."}]


def test_an_agreements_requirements_come_in_from_a_spreadsheet(
    as_role: Clients, db: Database, people: People
) -> None:
    chief = as_role("manager")
    with db.write(TESTER) as session:
        packs.install(session)
        made = frameworks.create(
            session,
            who(db, people, "manager"),
            {"title": "Cohort data use agreement", "kind": "agreement"},
        )
        key = made.key
    file = """Clause,Heading,Wording,Under
A,Security,,
A.1,Storage,Data is kept only on approved systems.,A
A.2,Access,Only named users may open it.,A
B.7,Missing parent,Text,Z
"""
    found = send(chief, f"requirements/{key}/columns", file).json()["data"]
    assert {f["name"]: f["column"] for f in found["fields"]} == {
        "code": None,
        "title": None,
        "text": None,
        "parent": None,
    }
    mapping = {"code": "Clause", "title": "Heading", "text": "Wording", "parent": "Under"}
    assert send(chief, f"requirements/{key}", file).status_code == 422
    report = send(chief, f"requirements/{key}", file, mapping=mapping, dry_run=False).json()["data"]
    assert not report["applied"] and report["problems"] == [
        {"row": 5, "message": "Parent: There is no requirement 'Z' to put it under."}
    ]
    good = file.replace("B.7,Missing parent,Text,Z\n", "")
    assert send(chief, f"requirements/{key}", good, mapping=mapping).json()["data"]["created"] == 3
    assert send(chief, f"requirements/{key}", good, mapping=mapping, dry_run=False).json()["data"][
        "applied"
    ]
    out = sheet(chief.get("/api/v1/exports/requirements", params={"framework": key}))
    assert [(r["code"], r["title"], r["parent"]) for r in out] == [
        ("A", "Security", ""),
        ("A.1", "Storage", "A"),
        ("A.2", "Access", "A"),
    ]
    # A published framework is not added to from a file, and a steward does not get this far.
    refused = send(chief, "requirements/nist-csf", "code\nX.1\n", dry_run=False).json()["data"]
    assert not refused["applied"] and len(refused["problems"]) == 1
    assert send(as_role("steward"), f"requirements/{key}", good, mapping=mapping).status_code == 403


# --- Out of one installation and into another ----------------------------------------------


def test_an_exported_list_reimports_unchanged_into_an_empty_installation(
    as_role: Clients, db: Database, people: People, elsewhere: TestClient
) -> None:
    manager, steward = who(db, people, "manager"), who(db, people, "steward")
    hale, cancer = people.units["HALE"], people.units["CANCER"]
    delegate = [
        {"account_id": steward.account_id, "kind": "owner"},
        {"account_id": people.accounts["member"], "kind": "delegate"},
    ]
    with db.write(manager.actor) as session:
        first = add_system(
            session,
            steward,
            hale,
            "Freezer monitoring",
            criticality="high",
            data_class="confidential",
            tags=["cold", "alarm"],
            external_refs=ELSEWHERE,
            summary='Alarms, "pages", and\na second line',
            hosting="on_premises",
        )
        records.set_owners(session, steward, SYSTEM, first, delegate)
        add_system(
            session, manager, cancer, "=cmd|' /C calc'!A0", restricted=True, status="retired"
        )
        add_system(session, manager, hale, "-2 freezer", kind="instrument")
        records.create(
            session,
            manager,
            PROCESS,
            {
                "name": "Specimen storage",
                "kind": "research_support",
                "org_unit_id": hale,
                "purpose": "Keep what cannot be collected again",
            },
        )
        add_control(
            session,
            steward,
            hale,
            "Nightly copy",
            objective="Nothing is lost for more than a day",
            nature="automated",
            frequency="daily",
            tags=["backup"],
        )
        register.create(
            session,
            steward,
            {
                "name": "Loss of the freezer farm",
                "category": "data_quality",
                "org_unit_id": hale,
                "cause": "Power fails",
                "event": "Freezers warm",
                "consequence": "Specimens are lost",
                "external_refs": [{"system": "other", "value": "ERM-12"}],
            },
        )
    here = as_role("manager")
    # A gap in the references, which a faithful copy keeps.
    assert (
        here.post(
            "/api/v1/systems", json={"name": "Scratch", "kind": "application", "org_unit_id": hale}
        ).json()["data"]["ref"]
        == "SYS-0004"
    )
    for path in ("systems", "processes", "controls", "risks"):
        before = here.get(f"/api/v1/exports/{path}").text
        if path == "systems":
            before = "".join(
                line
                for line in before.splitlines(keepends=True)
                if not line.startswith("SYS-0002,")
            )
            assert before.count("SYS-") == 3
        assert sheet(elsewhere.get(f"/api/v1/exports/{path}")) == []  # empty to begin with
        report = send(elsewhere, f"records/{path}", before, dry_run=False).json()["data"]
        assert report["applied"] and not report["problems"], report
        after = elsewhere.get(f"/api/v1/exports/{path}").text
        assert after == before, path
    # The references came across, and the next one given there does not reuse any of them.
    made = elsewhere.post(
        "/api/v1/systems", json={"name": "New there", "kind": "application", "org_unit_id": hale}
    )
    assert made.json()["data"]["ref"] == "SYS-0005"
    there = elsewhere.get("/api/v1/systems/SYS-0001").json()["data"]
    assert there["summary"] == 'Alarms, "pages", and\na second line' and there["tags"] == [
        "cold",
        "alarm",
    ]
    assert [(o["email"], o["kind"]) for o in there["owners"]] == [
        (email_of("steward"), "owner"),
        (email_of("member"), "delegate"),
    ]
    assert elsewhere.get("/api/v1/systems/SYS-0003").json()["data"]["name"] == "-2 freezer"
