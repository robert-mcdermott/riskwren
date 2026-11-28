"""Starter programs (PLT-18): a program for each kind of organization, chosen at init or loaded
later, written from one script."""

from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest

from riskwren.cli import main
from riskwren.config import load_config
from riskwren.db.engine import Database
from riskwren.program import packs, vocab
from riskwren.risk import categories

ROOT = Path(__file__).resolve().parent.parent


def test_every_starter_is_sound_and_matches_its_script() -> None:
    made = runpy.run_path(str(ROOT / "scripts" / "build-starter-programs.py"))
    assert tuple(made["STARTERS"]) == packs.STARTERS
    for key, build in made["STARTERS"].items():
        shipped = packs.starter(key)
        assert shipped == json.loads(json.dumps(build())), (
            f"{key}.json differs from scripts/build-starter-programs.py; run it"
        )
        assert packs.problems(shipped) == [], key
    with pytest.raises(Exception, match="no starter program"):
        packs.starter("bakery")


@pytest.mark.parametrize("key", ["university", "nonprofit"])
def test_init_starts_from_a_starter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    monkeypatch.delenv("RISKWREN_DATABASE_URL", raising=False)
    path = tmp_path / "riskwren.toml"
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("a long enough password here"))
    first = ["--admin-email", "first@example.org", "--admin-name", "First", "--password-stdin"]
    assert main(["--config", str(path), "init", "--program", key, *first]) == 0
    db = Database(load_config(path).database_url)
    try:
        with db.read() as session:
            found = {row.key: row.status for row in categories.all_(session)}
            kinds = {item["key"] for item in vocab.get(session, "process_kinds")}
    finally:
        db.dispose()
    assert found["clinical"] == "retired" and found["scientific_direction"] == "retired"
    if key == "university":
        assert found["students"] == "active" and "teaching" in kinds
    else:
        assert found["research"] == "retired" and "fundraising" in kinds
    # Loading it again by name changes nothing.
    assert main(["--config", str(path), "program", "import", key]) == 0
    # Running init again never lays a starter over the program in use.
    assert main(["--config", str(path), "init", "--program", "research-institute"]) == 0
    assert main(["--config", str(path), "init", "--program", key]) == 0
    db = Database(load_config(path).database_url)
    try:
        with db.read() as session:
            assert {row.key: row.status for row in categories.all_(session)} == found
    finally:
        db.dispose()


def test_a_framework_of_codes_takes_a_licence_holders_words(
    instance,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],  # type: ignore[no-untyped-def]
) -> None:
    """ISO/IEC 27001 ships as its codes alone; an organization that holds a license loads the
    words into its own installation, where they stay."""
    from riskwren.compliance import frameworks
    from riskwren.compliance import packs as framework_packs

    shipped = framework_packs.builtin("iso-27001")
    assert shipped["pack"]["text_policy"] == "identifiers"
    assert framework_packs.policy_problems(shipped) == []
    flat = json.dumps(shipped["requirements"])
    assert '"text"' not in flat and '"guidance"' not in flat
    config = ["--config", str(instance.path)]
    assert main([*config, "frameworks", "load", "iso-27001"]) == 0
    words = tmp_path / "licensed.csv"
    words.write_text(
        "code,title,text\nA.5.1,Our licensed title,Our licensed text.\n", encoding="utf-8"
    )
    assert main([*config, "frameworks", "text", "iso-27001", str(words)]) == 0
    with instance.db.read() as session:
        framework = frameworks.by_key(session, "iso-27001")
        shown = frameworks.detail(session, framework, "A.5.1")
    assert shown["title"] == "Our licensed title" and shown["text"] == "Our licensed text."
    assert shown["licensed"] is True
    capsys.readouterr()
    wrong = tmp_path / "wrong.csv"
    wrong.write_text("code,title,text\nZ.9,x,y\n", encoding="utf-8")
    assert main([*config, "frameworks", "text", "iso-27001", str(wrong)]) == 1
    assert main([*config, "frameworks", "text", "nist-csf", str(words)]) == 1
