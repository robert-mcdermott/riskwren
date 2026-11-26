"""The scoring arithmetic: one set of cases for the server and for the browser."""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from riskwren.core import scoring
from riskwren.program import vocab

ROOT = Path(__file__).resolve().parent.parent
CASES = json.loads((ROOT / "tests/fixtures/scoring-cases.json").read_text("utf-8"))["cases"]
METHOD: dict[str, Any] = vocab.default_pack()["scoring_method"]


def run(case: dict[str, Any]) -> Any:
    args = case["args"]
    return {
        "rating": lambda: scoring.rating(METHOD, *args),
        "overall_impact": lambda: scoring.overall_impact(*args),
        "ramp_level": lambda: scoring.ramp_level(*args),
        "position": lambda: scoring.position(METHOD, *args),
        "exceeds": lambda: scoring.exceeds(METHOD, *args),
        "control_state": lambda: scoring.control_state(*args, stale=bool(case.get("stale"))),
        "suggest": lambda: scoring.suggest(METHOD, *args),
    }[case["fn"]]()


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['fn']}-{c.get('name', c['args'])}"[:70])
def test_the_shared_cases(case: dict[str, Any]) -> None:
    expect = case["expect"]
    if isinstance(expect, dict) and expect.get("error"):
        with pytest.raises(ValueError, match="not a level"):
            run(case)
        return
    got = run(case)
    if case["fn"] == "suggest":
        assert {key: got[key] for key in expect} == expect
    else:
        assert got == expect


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node to run the browser's module")
def test_the_browsers_modules_pass_their_tests() -> None:
    files = sorted(str(path) for path in (ROOT / "tests/js").glob("*.test.mjs"))
    # West of Greenwich, where a day read as midnight UTC would be shown as the day before.
    result = subprocess.run(
        ["node", "--test", *files],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "TZ": "America/Los_Angeles"},
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]
    assert "# fail 0" in result.stdout
    passed = int(result.stdout.split("# pass ")[1].split()[0])
    assert passed >= len(CASES) + 1


def test_a_suggestion_shows_its_working() -> None:
    worked = next(c for c in CASES if c.get("name", "").startswith("the worked example"))
    controls = [
        {**control, "ref": f"CTL-000{n}", "name": f"Control {n}"}
        for n, control in enumerate(worked["args"][2], 1)
    ]
    got = scoring.suggest(METHOD, 4, 5, controls)
    assert got["from"] == {"likelihood": 4, "impact": 5, "rating": "critical"}
    assert got["limit"] == 2
    lines = [
        (c["ref"], c["state"], c["strength"], c["weight"], c["counts"]) for c in got["controls"]
    ]
    assert lines == [
        ("CTL-0001", "effective", 1.0, 1.0, 1.0),
        ("CTL-0002", "partly", 0.5, 1.0, 0.5),
        ("CTL-0003", "not_assessed", 0.0, 0.5, 0.0),
        ("CTL-0004", "effective", 1.0, 1.0, 1.0),
        ("CTL-0005", "effective", 1.0, 0.5, 0.5),
    ]  # fmt: skip


def test_the_default_method_is_sound() -> None:
    assert scoring.problems(METHOD) == []
    assert scoring.rating_keys(METHOD) == ["low", "moderate", "high", "critical"]
    # It leans toward impact: a severe consequence is never rated below high.
    assert {scoring.rating(METHOD, likelihood, 5) for likelihood in range(1, 6)} == {
        "high", "critical",
    }  # fmt: skip
    for dimension in METHOD["dimensions"]:
        assert len(dimension["levels"]) == 5 and dimension["question"].endswith("?")


def broken(change: Any) -> list[str]:
    method = copy.deepcopy(METHOD)
    change(method)
    return scoring.problems(method)


def test_a_method_that_cannot_be_used_says_why() -> None:
    assert broken(lambda m: m["ratings"].pop()) != []  # the matrix names a rating that is gone
    assert any("matrix" in p for p in broken(lambda m: m["matrix"].pop()))
    assert any("never fall as likelihood" in p for p in broken(
        lambda m: m["matrix"][2].__setitem__(4, "low")))  # fmt: skip
    assert any("never fall as impact" in p for p in broken(
        lambda m: m["matrix"][4].__setitem__(0, "low")))  # fmt: skip
    assert any("definition for every impact level" in p for p in broken(
        lambda m: m["dimensions"][0]["levels"].pop("3")))  # fmt: skip
    assert any("likelihood level needs a definition" in p for p in broken(
        lambda m: m["likelihood"][0].pop("definition")))  # fmt: skip
    assert any("limit" in p for p in broken(lambda m: m["control_effect"].__setitem__("limit", 9)))
    assert any("three to five ratings" in p for p in broken(
        lambda m: m["ratings"].append({"key": "low", "label": "Again"})))  # fmt: skip
    assert len(scoring.problems({})) >= 5  # everything wrong, reported in one pass
