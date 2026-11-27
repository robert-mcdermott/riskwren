"""Frameworks: packs checked whole and held to their text policy, the built-in public
frameworks, browsing a tree, and the organization's own."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from riskwren.cli import main
from riskwren.compliance import frameworks, packs
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import Baseline, Event, Framework, Requirement
from riskwren.events import chain
from tests.conftest import TESTER, Instance
from tests.people import People
from tests.test_risks import who

Clients = Callable[[str | None], TestClient]
ROOT = Path(__file__).resolve().parent.parent

SMALL = {
    "pack": {
        "key": "site-standard",
        "kind": "framework",
        "framework_kind": "internal",
        "title": "Site security standard",
        "version": "3",
        "publisher": "Northmere Institute",
        "license": "Internal",
        "text_policy": "verbatim",
    },
    "requirements": [
        {"code": "1", "title": "Access", "group": True, "children": [
            {"code": "1.1", "text": "Every account belongs to one named person."},
            {"code": "1.2", "text": "Access is removed on the day a person leaves."},
        ]},
        {"code": "2", "title": "Backups", "text": "Backups are restored in full each quarter."},
    ],
    "baselines": [{"key": "core", "title": "Core", "codes": ["1.1", "2"]}],
}  # fmt: skip


def small(**head: object) -> dict[str, object]:
    pack = copy.deepcopy(SMALL)
    pack["pack"].update(head)  # type: ignore[union-attr]
    return pack


@pytest.fixture
def loaded(db: Database, people: People) -> None:
    with db.write(TESTER) as session:
        assert packs.install(session) == 4


# --- Packs --------------------------------------------------------------------------------


def test_every_built_in_pack_is_sound_and_says_where_it_comes_from() -> None:
    sizes = {}
    for key in packs.AVAILABLE:
        pack = packs.builtin(key)
        assert packs.problems(pack) == [], key
        head = pack["pack"]
        assert head["key"] == key and head["text_policy"] == "verbatim"
        assert "Public domain" in head["license"] and head["publisher"]
        assert head["source_url"].startswith("https://") and head["built_from"]
        sizes[key] = sum(not item.get("group") for item, _ in packs.walk(pack["requirements"]))
    # The publishers' own counts: 106 outcomes, 97 requirements, and the active controls.
    assert sizes["nist-csf"] == 106 and sizes["nist-800-171"] == 97
    assert sizes["nist-800-53"] == 1014 and sizes["hipaa-security"] > 80
    assert sizes["nist-800-53-r4"] == 922  # Rev. 4's controls and enhancements not withdrawn
    # What a pack says of other frameworks names only codes that exist on both sides.
    r4 = {item["code"] for item, _ in packs.walk(packs.builtin("nist-800-53-r4")["requirements"])}
    r5 = {item["code"] for item, _ in packs.walk(packs.builtin("nist-800-53")["requirements"])}
    assert all(old in r4 and new in r5 for old, _how, new in packs.builtin("nist-800-53")["moved"])
    derived = packs.builtin("nist-800-171")["mappings"][0]
    assert derived["framework"] == "nist-800-53" and all(code in r5 for _, code in derived["pairs"])


def test_a_pack_may_carry_only_the_text_its_policy_allows() -> None:
    assert packs.problems(small()) == []
    identifiers = small(text_policy="identifiers")
    found = packs.problems(identifiers)
    assert any("1.1: an identifiers pack carries no text" in line for line in found)
    labels = small(text_policy="identifiers")
    labels["requirements"] = [{"code": "A.5", "title": "Policies for information security"}]
    labels["baselines"] = []
    assert packs.problems(labels) == []
    labels["requirements"][0]["title"] = "x" * 81  # type: ignore[index]
    assert any("a label is at most 80" in line for line in packs.problems(labels))
    summary = small(text_policy="summary")
    summary["requirements"][1]["text"] = "y" * 241  # type: ignore[index]
    assert any("a summary is at most 240" in line for line in packs.problems(summary))
    assert any("credited" in line for line in packs.problems(small(text_policy="attributed")))
    assert packs.problems(small(text_policy="attributed", attribution="© Example, CC BY 4.0")) == []
    assert any("text_policy" in line for line in packs.problems(small(text_policy="own")))


def test_every_problem_in_a_pack_is_reported_together() -> None:
    pack = small(publisher="", key="has spaces")
    pack["requirements"].append({"code": "1.1", "text": "A second 1.1."})  # type: ignore[union-attr]
    pack["requirements"].append({"code": "3", "wording": "unknown field"})  # type: ignore[union-attr]
    pack["baselines"][0]["codes"].append("9.9")  # type: ignore[index]
    found = " ".join(packs.problems(pack))
    for expected in ("pack.publisher", "pack.key uses", "1.1: the code is used twice",
                     "3: unknown field 'wording'", "3: a requirement that can be cited",
                     "'9.9' is not a requirement"):  # fmt: skip
        assert expected in found
    assert packs.problems([]) and packs.problems({"pack": {}, "requirements": []})


def test_a_pack_with_anything_wrong_is_refused_whole(db: Database, people: People) -> None:
    bad = small()
    bad["requirements"][0]["children"][1]["code"] = "1.1"  # type: ignore[index]
    with pytest.raises(Invalid), db.write(TESTER) as session:
        packs.load(session, bad)
    with db.read() as session:
        assert session.scalars(select(Framework)).first() is None
        assert session.scalars(select(Requirement)).first() is None


def test_loading_writes_the_tree_its_baselines_and_one_event(db: Database, people: People) -> None:
    with db.read() as session:
        before = session.execute(select(func.count()).select_from(Event)).scalar_one()
    with db.write(TESTER) as session:
        made = packs.load(session, small())
        assert (made.requirement_count, made.citable_count) == (4, 3)
        assert (made.origin, made.kind, made.digest) == ("pack", "internal", packs.digest(SMALL))
    with db.read() as session:
        rows = session.scalars(select(Requirement).order_by(Requirement.id)).all()
        assert [(r.code, r.depth, r.position, r.is_citable) for r in rows] == [
            ("1", 0, 0, False), ("2", 0, 1, True), ("1.1", 1, 0, True), ("1.2", 1, 1, True),
        ]  # fmt: skip
        assert session.scalars(select(Baseline)).one().requirement_count == 2
        events = session.scalars(select(Event).where(Event.id > before)).all()
        # Published content is recorded by its framework, with a digest: not row by row.
        assert [(e.subject_type, e.action) for e in events] == [
            ("framework", "created"), ("framework", "updated"),
        ]  # fmt: skip
        assert events[0].context["op"] == "framework.load"
    with pytest.raises(Conflict), db.write(TESTER) as session:
        packs.load(session, small())
    with db.engine.connect() as conn:
        assert chain.verify(conn).ok


def test_the_built_in_frameworks_load_once(db: Database, loaded: None) -> None:
    with db.write(TESTER) as session:
        assert packs.install(session) == 0
    with db.read() as session:
        rows = {row.key: row for row in frameworks.all_(session)}
        assert set(rows) == set(packs.BUILTIN)
        assert rows["nist-800-53"].citable_count == 1014
        assert rows["hipaa-security"].kind == "regulation"
        counts = {
            b.key: b.requirement_count for b in frameworks.baselines(session, rows["nist-800-53"])
        }
        assert counts == {"low": 149, "moderate": 287, "high": 370, "privacy": 96}


# --- Reading ------------------------------------------------------------------------------


def test_a_tree_is_read_a_level_at_a_time_and_searched_whole(db: Database, loaded: None) -> None:
    with db.read() as session:
        catalog = frameworks.by_key(session, "nist-800-53")
        top, total = frameworks.listing(session, catalog)
        assert total == 20 and top[0]["code"] == "AC" and not top[0]["is_citable"]
        assert top[0]["children"] == 23
        family, _ = frameworks.listing(session, catalog, parent="AC")
        assert [row["code"] for row in family][:3] == ["AC-1", "AC-2", "AC-3"]
        assert family[1]["title"] == "Account Management" and family[1]["children"] == 12
        found, count = frameworks.listing(session, catalog, query="multi-factor")
        assert count == len(found) and "IA-2(1)" in {row["code"] for row in found}
        low, in_low = frameworks.listing(session, catalog, baseline="low", limit=200)
        assert in_low == 149 and len(low) == 149
        both, narrowed = frameworks.listing(session, catalog, baseline="low", query="account")
        assert 0 < narrowed < 149 and all(row["is_citable"] for row in both)
        with pytest.raises(NotFound):
            frameworks.listing(session, catalog, baseline="imaginary")
        with pytest.raises(NotFound):
            frameworks.listing(session, catalog, parent="ZZ-99")


def test_a_requirement_shows_its_text_as_published_and_where_it_sits(
    db: Database, loaded: None
) -> None:
    with db.read() as session:
        catalog = frameworks.by_key(session, "nist-800-53")
        item = frameworks.detail(session, catalog, "AC-2(3)")
        assert [step["code"] for step in item["trail"]] == ["AC", "AC-2"]
        assert item["text"].startswith(
            "Disable accounts within [Assignment: organization-defined time period] when"
        )
        assert "\n(a) Have expired;" in item["text"] and item["guidance"]
        assert [b["key"] for b in item["baselines"]] == ["moderate", "high"]
        first = frameworks.detail(session, catalog, "AC-1")
        assert "[Selection (one or more): organization-level;" in first["text"]
        rule = frameworks.by_key(session, "hipaa-security")
        standard = frameworks.detail(session, rule, "164.308(a)(1)(i)")
        assert standard["title"] == "Security management process" and standard["kind"] == "standard"
        assert [step["code"] for step in standard["trail"]] == [
            "164.308",
            "164.308(a)",
            "164.308(a)(1)",
        ]
        analysis = frameworks.detail(session, rule, "164.308(a)(1)(ii)(A)")
        assert analysis["title"] == "Risk analysis (Required)"
        assert analysis["text"].startswith("Risk analysis (Required). Conduct an accurate")
        outcome = frameworks.detail(session, frameworks.by_key(session, "nist-csf"), "GV.OC-01")
        assert outcome["text"].startswith("The organizational mission is understood")
        assert [step["code"] for step in outcome["trail"]] == ["GV", "GV.OC"]


# --- The organization's own ---------------------------------------------------------------


def test_an_agreement_is_entered_and_kept_as_a_framework_of_its_own(
    db: Database, people: People
) -> None:
    manager = who(db, people, "manager")
    with db.read() as session:
        before = session.execute(select(func.count()).select_from(Event)).scalar_one()
    with db.write(manager.actor) as session:
        made = frameworks.create(
            session, manager,
            {"title": "Data use agreement: Open Cohort Trust", "kind": "agreement",
             "publisher": "Open Cohort Trust", "version": "Signed 2025"},
        )  # fmt: skip
        assert (made.key, made.origin, made.text_policy) == (
            "data-use-agreement-open-cohort-trust", "local", "own",
        )  # fmt: skip
        frameworks.add_requirement(
            session, manager, made, {"code": "4", "title": "Security", "is_citable": False}
        )
        frameworks.add_requirement(
            session, manager, made,
            {"code": "4.1", "text": "Data are held only on managed systems.", "parent": "4"},
        )  # fmt: skip
        row = frameworks.add_requirement(
            session, manager, made, {"code": "4.2", "text": "Access is limited.", "parent": "4"}
        )
        assert (row.depth, row.position) == (1, 1)
        frameworks.add_requirement(session, manager, made, {"code": "5", "text": "Reporting."})
        frameworks.add_requirement(
            session, manager, made, {"code": "4.3", "text": "Copies are logged.", "parent": "4"}
        )
        in_order, _ = frameworks.listing(session, made, query="4.")
        assert [item["code"] for item in in_order] == ["4.1", "4.2", "4.3"]
        everything, _ = frameworks.listing(session, made, query="e")
        assert [item["code"] for item in everything] == ["4", "4.1", "4.2", "4.3", "5"]
        for code in ("5", "4.3"):
            frameworks.remove_requirement(
                session, manager, made, frameworks.find(session, made, code)
            )
        assert (made.requirement_count, made.citable_count) == (3, 2)
        frameworks.update_requirement(
            session, manager, made, row, {"text": "Access is limited to named study staff."}
        )
        with pytest.raises(Invalid) as taken:
            frameworks.add_requirement(session, manager, made, {"code": "4.1", "text": "Again."})
        assert "already a requirement" in taken.value.errors["code"]
    with db.write(manager.actor) as session:
        made = frameworks.by_key(session, "data-use-agreement-open-cohort-trust")
        with pytest.raises(Conflict):
            frameworks.remove_requirement(
                session, manager, made, frameworks.find(session, made, "4")
            )
        frameworks.remove_requirement(session, manager, made, frameworks.find(session, made, "4.1"))
        assert (made.requirement_count, made.citable_count) == (2, 1)
    with db.read() as session:
        events = session.scalars(select(Event).where(Event.id > before).order_by(Event.id)).all()
        told = [e.action for e in events if e.action.startswith("requirement.")]
        assert told == (
            ["requirement.added"] * 5
            + ["requirement.removed"] * 2
            + ["requirement.changed", "requirement.removed"]
        )
        changed = next(e for e in events if e.action == "requirement.changed")
        assert changed.subject_type == "framework" and changed.changes["text"] == [
            "Access is limited.", "Access is limited to named study staff.",
        ]  # fmt: skip
    with db.engine.connect() as conn:
        assert chain.verify(conn).ok


def test_requirements_are_pasted_after_a_dry_run_and_only_if_every_line_can_be(
    db: Database, people: People
) -> None:
    manager = who(db, people, "manager")
    lines = "S-1 Sign in with two factors.\nS-2\tPatch within thirty days,\n   or record why not.\n"
    with db.write(manager.actor) as session:
        made = frameworks.create(session, manager, {"title": "Sponsor security terms"})
        report = frameworks.paste(session, manager, made, lines, dry_run=True)
        assert (report["would_add"], report["applied"], report["problems"]) == (2, False, [])
        assert made.requirement_count == 0
        bad = frameworks.paste(session, manager, made, lines + "S-1 Twice.\nword\n", dry_run=False)
        assert not bad["applied"] and [p["row"] for p in bad["problems"]] == [4, 5]
        assert made.requirement_count == 0
        done = frameworks.paste(session, manager, made, lines, dry_run=False)
        assert done["applied"] and made.citable_count == 2
        second = frameworks.find(session, made, "S-2")
        assert second.text == "Patch within thirty days,\nor record why not."
        again = frameworks.paste(session, manager, made, "S-2 Again.", dry_run=True)
        assert "already a requirement" in again["problems"][0]["message"]


def test_published_frameworks_are_read_not_edited_and_only_the_program_keeps_its_own(
    db: Database, loaded: None, people: People
) -> None:
    manager, steward = who(db, people, "manager"), who(db, people, "steward")
    with db.write(manager.actor) as session:
        csf = frameworks.by_key(session, "nist-csf")
        with pytest.raises(Conflict):
            frameworks.add_requirement(session, manager, csf, {"code": "X", "text": "Mine."})
        with pytest.raises(Conflict):
            frameworks.update(session, manager, csf, {"title": "Ours"})
        frameworks.update(session, manager, csf, {"status": "retired"})
        assert "nist-csf" not in {row.key for row in frameworks.all_(session)}
        assert "nist-csf" in {row.key for row in frameworks.all_(session, retired=True)}
    with db.write(steward.actor) as session:
        with pytest.raises(PermissionDenied):
            frameworks.create(session, steward, {"title": "A steward's own"})
        view = frameworks.view(session, steward, frameworks.by_key(session, "nist-800-171"))
        assert view["can"] == {"edit": False, "retire": False}


# --- Through the API and the command line -------------------------------------------------


def test_the_api_browses_frameworks_and_keeps_the_organizations_own(
    as_role: Clients, db: Database, loaded: None
) -> None:
    member = as_role("member")
    listed = member.get("/api/v1/frameworks").json()["data"]
    assert {row["key"] for row in listed} == set(packs.BUILTIN)
    page = member.get("/api/v1/frameworks/nist-800-53/requirements", params={"parent": "AC-2"})
    assert page.json()["meta"]["total"] == 12
    one = member.get(
        "/api/v1/frameworks/hipaa-security/requirement", params={"code": "164.312(a)(2)(iv)"}
    ).json()["data"]
    assert one["title"] == "Encryption and decryption (Addressable)"
    assert member.get("/api/v1/frameworks/none").status_code == 404
    assert member.post("/api/v1/frameworks", json={"title": "Mine"}).status_code == 403

    manager = as_role("manager")
    made = manager.post(
        "/api/v1/frameworks", json={"title": "Repository terms", "kind": "agreement"}
    )
    assert made.status_code == 201 and made.json()["data"]["can"]["edit"]
    base = "/api/v1/frameworks/repository-terms"
    added = manager.post(
        f"{base}/requirements", json={"code": "A/1", "text": "Keep an access log."}
    )
    assert added.status_code == 201
    tried = manager.post(f"{base}/requirements/paste", json={"text": "A/2 Review it monthly."})
    assert tried.json()["data"] == {
        "dry_run": True, "applied": False, "would_add": 1, "problems": [], "sample": ["A/2"],
    }  # fmt: skip
    assert manager.post(
        f"{base}/requirements/paste",
        params={"dry_run": "false"},
        json={"text": "A/2 Review it monthly."},
    ).json()["data"]["applied"]
    changed = manager.patch(
        f"{base}/requirement", params={"code": "A/1"}, json={"title": "Logging"}
    )
    assert changed.json()["data"]["title"] == "Logging"
    assert manager.delete(f"{base}/requirement", params={"code": "A/2"}).status_code == 200
    assert manager.get(f"{base}/requirements").json()["meta"]["total"] == 1
    assert member.get(base).json()["data"]["can"] == {"edit": False, "retire": False}
    assert member.delete(f"{base}/requirement", params={"code": "A/1"}).status_code == 403
    refused = manager.patch(
        "/api/v1/frameworks/nist-csf/requirement", params={"code": "GV"}, json={"title": "x"}
    )
    assert refused.status_code == 409


def test_the_command_line_lists_shows_and_loads_frameworks(
    instance: Instance, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = lambda *args: main(["--config", str(instance.path), *args])  # noqa: E731
    assert run("frameworks", "list") == 0
    assert "No frameworks are loaded" in capsys.readouterr().out
    assert run("frameworks", "load", "--builtin") == 0
    assert "Loaded 4 built-in frameworks." in capsys.readouterr().out
    assert run("frameworks", "list") == 0
    assert "nist-800-53" in capsys.readouterr().out
    assert run("frameworks", "show", "hipaa-security") == 0
    shown = capsys.readouterr().out
    assert "Department of Health and Human Services" in shown and "Public domain" in shown
    good, bad = tmp_path / "good.json", tmp_path / "bad.json"
    good.write_text(json.dumps(SMALL))
    bad.write_text(json.dumps(small(text_policy="identifiers")))
    assert run("frameworks", "load", str(bad)) != 0
    assert "an identifiers pack carries no text" in capsys.readouterr().out
    assert run("frameworks", "load", str(good), "--dry-run") == 0
    assert run("frameworks", "load", str(good)) == 0
    assert "Loaded Site security standard: 3 requirements." in capsys.readouterr().out
    assert run("frameworks", "load", str(good)) != 0  # already here
    assert run("frameworks", "show", "missing") != 0
    assert run("frameworks", "load") != 0


def test_the_packs_are_exactly_what_the_builder_makes(tmp_path: Path) -> None:
    """The shipped packs are generated, never edited. This rebuilds them from the publishers'
    files where those have been fetched (they are not kept in the repository)."""
    if not (ROOT / ".cache" / "sources").is_dir():
        pytest.skip("the publishers' files have not been fetched on this machine")
    shipped = ROOT / "src" / "riskwren" / "resources" / "packs" / "frameworks"
    before = {path.name: path.read_bytes() for path in shipped.glob("*.json")}
    done = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build-framework-packs.py"), "--offline"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    assert {path.name: path.read_bytes() for path in shipped.glob("*.json")} == before
