from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from riskwren.core.errors import Invalid
from riskwren.db.engine import Database
from riskwren.db.models import Account, Event, OrgUnit
from riskwren.people import accounts, imports, units
from tests.people import ME, People

UNITS = """code,name,kind,parent_code
IMG,Imaging Core,core,NMI
OKA,Okafor Lab,lab,POP
POP,Population Sciences,division,NMI
"""


def count(db: Database, model: type) -> int:
    with db.read() as session:
        return session.execute(select(func.count()).select_from(model)).scalar_one()


def test_a_dry_run_reports_and_changes_nothing(db: Database, people: People) -> None:
    before = (count(db, OrgUnit), count(db, Event))
    with db.write(ME.actor) as session:
        report = imports.import_units(session, ME, UNITS, dry_run=True)
        session.rollback()
    assert (report.rows, report.created, report.updated, report.problems) == (3, 3, 0, [])
    assert not report.applied
    assert (count(db, OrgUnit), count(db, Event)) == before


def test_units_are_created_parents_first_whatever_the_order(db: Database, people: People) -> None:
    with db.write(ME.actor) as session:
        report = imports.import_units(session, ME, UNITS, dry_run=False)
    assert report.applied and report.created == 3
    with db.read() as session:
        lab = units.by_code(session, "OKA")
        assert lab is not None
        assert [unit.code for unit in units.ancestors(session, lab.id)] == ["POP", "NMI"]
        last = session.scalars(select(Event).order_by(Event.id.desc())).first()
        assert last is not None and last.context == {"op": "units.import"}


def test_importing_again_changes_only_what_differs(db: Database, people: People) -> None:
    with db.write(ME.actor) as session:
        imports.import_units(session, ME, UNITS, dry_run=False)
    changed = UNITS.replace("Imaging Core", "Imaging and Microscopy Core").replace(
        "OKA,Okafor Lab,lab,POP", "OKA,Okafor Lab,lab,IMM"
    )
    with db.write(ME.actor) as session:
        report = imports.import_units(session, ME, changed, dry_run=False)
    assert (report.created, report.updated, report.unchanged) == (0, 2, 1)
    with db.read() as session:
        lab = units.by_code(session, "OKA")
        assert lab is not None and lab.parent_id == people.units["IMM"]


def test_every_problem_is_listed_with_its_row(db: Database, people: People) -> None:
    text = """code,name,kind,parent_code
A,Alpha,lab,NOWHERE
A,Alpha again,lab,NMI
,Nameless,,NMI
B,Second root,organization,
C,Loop one,lab,D
D,Loop two,lab,C
"""
    with db.write(ME.actor) as session:
        report = imports.import_units(session, ME, text, dry_run=False)
        session.rollback()
    found = {(p["row"], p["message"]) for p in report.problems}
    assert (2, "The parent NOWHERE is not in the file or already in RiskWren.") in found
    assert (3, "The code A is also on row 2.") in found
    assert (4, "A unit needs a code.") in found and (4, "A unit needs a kind.") in found
    assert any(row == 5 and "no parent" in message for row, message in found)
    assert not report.applied
    with db.read() as session:
        assert units.by_code(session, "A") is None


def test_units_that_refer_to_each_other_are_refused(db: Database, people: People) -> None:
    text = "code,name,kind,parent_code\nC,Loop one,lab,D\nD,Loop two,lab,C\n"
    with db.write(ME.actor) as session:
        report = imports.import_units(session, ME, text, dry_run=True)
        session.rollback()
    assert [p["row"] for p in report.problems] == [2, 3]
    assert all("loop" in p["message"] for p in report.problems)


def test_a_file_without_the_needed_columns_is_refused(db: Database, people: People) -> None:
    with db.write(ME.actor) as session, pytest.raises(Invalid) as caught:
        imports.import_units(session, ME, "name,type\nAlpha,lab\n", dry_run=True)
    assert "code, kind" in caught.value.errors["file"]


PEOPLE = """Email,Name,Title,Unit_Codes,Roles
Priya.Nair@northmere.example,Priya Nair,Lab Manager,HALE,steward=unit:HALE
wei.chen@northmere.example,Wei Chen,Division Director,NMI,"leader=unit:IMM,limit:high; auditor"
member@northmere.example,Member Person,,,
"""


def test_people_are_added_as_invited_with_units_and_roles(db: Database, people: People) -> None:
    with db.write(ME.actor) as session:
        report = imports.import_people(session, ME, "﻿" + PEOPLE, dry_run=False)
    assert (report.created, report.updated, report.unchanged, report.problems) == (2, 0, 1, [])
    with db.read() as session:
        priya = accounts.by_email(session, "priya.nair@northmere.example")
        assert priya is not None and (priya.status, priya.title) == ("invited", "Lab Manager")
        principal = accounts.principal_for(session, priya)
        assert principal.coverage == {"steward": {people.units["HALE"]}}
        wei = accounts.by_email(session, "wei.chen@northmere.example")
        assert wei is not None
        assert {(g.role, g.accept_limit) for g in accounts.grants_of(session, wei.id)} == {
            ("leader", "high"), ("auditor", None),
        }  # fmt: skip


def test_people_problems_stop_the_whole_import(db: Database, people: People) -> None:
    text = """email,name,unit_codes,roles
not-an-address,Somebody,,
ok@northmere.example,Fine Person,,
dup@northmere.example,One,,
dup@northmere.example,Two,NOPE,wizard
blank@northmere.example,,,steward
"""
    before = count(db, Account)
    with db.write(ME.actor) as session:
        report = imports.import_people(session, ME, text, dry_run=False)
        session.rollback()
    messages = {(p["row"], p["message"]) for p in report.problems}
    assert (2, "not-an-address is not an email address.") in messages
    assert (5, "dup@northmere.example is also on row 4.") in messages
    assert (5, "There is no unit with the code NOPE.") in messages
    assert any(row == 5 and "wizard" in message for row, message in messages)
    assert (6, "A person needs a name.") in messages
    assert any(row == 6 and "Name the unit" in message for row, message in messages)
    assert count(db, Account) == before


def test_importing_through_the_api(
    as_role: Callable[[str | None], TestClient], people: People
) -> None:
    admin = as_role("admin")
    dry = admin.post("/api/v1/imports/units", content=UNITS).json()["data"]
    assert dry["dry_run"] and not dry["applied"] and dry["created"] == 3
    assert len(admin.get("/api/v1/units").json()["data"]["units"]) == 4
    done = admin.post("/api/v1/imports/units", params={"dry_run": "false"}, content=UNITS).json()[
        "data"
    ]
    assert done["applied"]
    assert len(admin.get("/api/v1/units").json()["data"]["units"]) == 7
    bad = admin.post(
        "/api/v1/imports/people", params={"dry_run": "false"}, content="email,name\nnope,X\n"
    )
    assert (
        bad.status_code == 200
        and bad.json()["data"]["problems"]
        and not bad.json()["data"]["applied"]
    )
    assert admin.post("/api/v1/imports/people", content=b"\xff\xfe\x00").status_code == 422
    assert admin.post("/api/v1/imports/people", content="name\nX\n").status_code == 422
