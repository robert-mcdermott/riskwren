"""The condition language: its meaning, its twin in the browser, and what it refuses."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from riskwren.core import conditions

ROOT = Path(__file__).resolve().parent.parent
CASES = json.loads(
    (ROOT / "tests" / "fixtures" / "conditions-cases.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_the_shared_cases(case: dict) -> None:
    assert conditions.evaluate(case["condition"], case["context"]) is case["expect"]
    assert conditions.problems(case["condition"]) == []


def test_there_are_enough_cases_to_mean_something() -> None:
    used = {part["op"] for case in CASES for part in _leaves(case["condition"])}
    assert used == set(conditions.OPERATORS), "every operator needs a shared case"
    assert len(CASES) >= 60


def _leaves(condition: dict | None) -> list[dict]:
    if not condition:
        return []
    if "all" in condition or "any" in condition:
        return [
            leaf
            for part in condition.get("all", condition.get("any", []))
            for leaf in _leaves(part)
        ]
    if "not" in condition:
        return _leaves(condition["not"])
    return [condition]


@pytest.mark.skipif(
    shutil.which("node") is None, reason="needs Node to run the browser's evaluator"
)
def test_the_browser_agrees_on_every_case() -> None:
    """The browser's evaluator against the same cases. Only this file: every JavaScript
    test is run together, with the time zone the date tests need, by ``tests/test_scoring.py``."""
    result = subprocess.run(
        ["node", "--test", "tests/js/conditions.test.mjs"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )  # fmt: skip
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


@pytest.mark.parametrize(
    ("condition", "complaint"),
    [
        ("answers.x == 1", "must be an object"),
        ({"field": "answers.x", "op": "matches", "value": ".*"}, "`op` must be one of"),
        ({"field": "", "op": "eq", "value": 1}, "needs a `field`"),
        ({"field": "answers..x", "op": "eq", "value": 1}, "needs a `field`"),
        ({"op": "eq", "value": 1}, "needs a `field`"),
        ({"field": "answers.x", "op": "eq"}, "needs a value"),
        ({"field": "answers.x", "op": "in", "value": "a"}, "needs a list"),
        ({"field": "answers.x", "op": "gt", "value": "3"}, "needs a number"),
        ({"field": "answers.x", "op": "gt", "value": True}, "needs a number"),
        ({"field": "answers.x", "op": "answered", "value": True}, "takes no value"),
        (
            {"field": "answers.x", "op": "eq", "value": 1, "exec": "rm -rf"},
            "does not understand exec",
        ),
        ({"all": {"field": "a", "op": "answered"}}, "must be a list"),
        ({"all": [], "any": []}, "alone in its object"),
        ({"all": [{}]}, "is empty"),
        ({"not": {}}, "must hold one condition"),
        (
            {"any": [{"all": [{"field": "a", "op": "between", "value": [1, 2]}]}]},
            "condition.any[0].all[0]",
        ),
    ],
)
def test_malformed_conditions_are_explained(condition: object, complaint: str) -> None:
    found = conditions.problems(condition)
    assert found and any(complaint in problem for problem in found), found


def test_conditions_cannot_nest_without_end() -> None:
    deep: dict = {"field": "tier", "op": "eq", "value": 3}
    for _ in range(conditions.MAX_DEPTH + 2):
        deep = {"not": deep}
    assert any("too deeply" in problem for problem in conditions.problems(deep))
    assert conditions.evaluate(deep, {"tier": 3}) in (True, False)  # and never recurses forever


def test_the_fields_a_condition_looks_at() -> None:
    condition = {
        "all": [
            {"field": "answers.a", "op": "answered"},
            {
                "any": [
                    {"field": "tier", "op": "gte", "value": 3},
                    {"not": {"field": "answers.b", "op": "empty"}},
                ]
            },
        ]
    }
    assert conditions.fields(condition) == {"answers.a", "tier", "answers.b"}
    assert conditions.fields(None) == set()
