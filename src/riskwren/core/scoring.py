"""The arithmetic of a scoring method (see spec/engine.md).

Pure functions over a method document: data in, data out, no database. The same document is
sent to the browser, where ``web/static/js/core/scoring.js`` does the same sums for live
previews; ``tests/fixtures/scoring-cases.json`` holds the cases both must pass.

A method is a document, not a formula. Likelihood and impact are combined by looking up a
cell in a matrix; controls lower a suggestion by whole levels, to a limit. Nothing here is
ever evaluated as code.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from typing import Any

Method = Mapping[str, Any]

AXES = ("likelihood", "impact")
EFFECTIVENESS = ("effective", "partly", "ineffective", "not_assessed")
REDUCES = ("likelihood", "impact", "both")
RELIANCE = ("primary", "supporting")


def problems(method: Method) -> list[str]:
    """Everything wrong with a method document, in one pass. Empty when it can be used."""
    found: list[str] = []
    likelihood = method.get("likelihood") or []
    impact = method.get("impact_levels") or []
    ratings = [r.get("key") for r in method.get("ratings") or []]
    for name, levels in (("likelihood", likelihood), ("impact_levels", impact)):
        numbers = [level.get("level") for level in levels]
        if numbers != list(range(1, len(numbers) + 1)) or not 2 <= len(numbers) <= 7:
            found.append(f"{name} must be levels numbered from 1, between two and seven of them.")
        if any(not level.get("label") for level in levels):
            found.append(f"Every level of {name} needs a label.")
    if any(not level.get("definition") for level in likelihood):
        found.append("Every likelihood level needs a definition.")
    if not 3 <= len(ratings) <= 5 or len(set(ratings)) != len(ratings) or not all(ratings):
        found.append("There must be three to five ratings, each with its own key.")
    dimensions = method.get("dimensions") or []
    if not dimensions:
        found.append("There must be at least one impact dimension.")
    keys = [d.get("key") for d in dimensions]
    if len(set(keys)) != len(keys) or not all(keys):
        found.append("Every impact dimension needs its own key.")
    for dimension in dimensions:
        wanted = {str(level.get("level")) for level in impact}
        given = dimension.get("levels") or {}
        if set(given) != wanted or not all(given.values()):
            found.append(
                f"The {dimension.get('label') or dimension.get('key')} dimension needs a "
                "definition for every impact level."
            )
    matrix = method.get("matrix") or []
    if len(matrix) != len(impact) or any(len(row) != len(likelihood) for row in matrix):
        found.append("The matrix must have a row for each impact level and a cell for each "
                     "likelihood level.")  # fmt: skip
    elif any(cell not in ratings for row in matrix for cell in row):
        found.append("Every cell of the matrix must be one of the ratings.")
    else:
        order = {key: position for position, key in enumerate(ratings)}
        for row in matrix:
            if any(order[a] > order[b] for a, b in itertools.pairwise(row)):
                found.append("A rating must never fall as likelihood rises.")
                break
        for lower, upper in itertools.pairwise(matrix):
            if any(order[a] < order[b] for a, b in zip(upper, lower, strict=True)):
                found.append("A rating must never fall as impact rises.")
                break
    effect = method.get("control_effect") or {}
    if set(effect.get("reliance") or {}) != set(RELIANCE):
        found.append("The control effect needs a weight for primary and for supporting reliance.")
    if set(effect.get("strength") or {}) != set(EFFECTIVENESS):
        found.append("The control effect needs a strength for each state of effectiveness.")
    if not isinstance(effect.get("limit"), int) or not 0 <= effect.get("limit", -1) <= 4:
        found.append("The control effect needs a limit of zero to four levels.")
    return found


def levels(method: Method, axis: str) -> list[int]:
    return [
        level["level"]
        for level in method["likelihood" if axis == "likelihood" else "impact_levels"]
    ]


def rating_keys(method: Method) -> list[str]:
    return [rating["key"] for rating in method["ratings"]]


def position(method: Method, rating: str | None) -> int:
    """Where a rating sits among the method's ratings, from 1. Zero if it is not one of them."""
    keys = rating_keys(method)
    return keys.index(rating) + 1 if rating in keys else 0


def ramp_level(place: int, count: int) -> int:
    """Where the rating at ``place`` of ``count`` sits on the five-step color ramp, so that
    the lowest and highest ratings are always at its ends."""
    if not place:
        return 0
    if count <= 1:
        return 5
    return int(1 + ((place - 1) * 4) / (count - 1) + 0.5)


def overall_impact(impact_levels: Mapping[str, int | None]) -> int | None:
    """The highest level rated on any dimension. Averaging would let four small
    consequences hide one severe one."""
    rated = [level for level in impact_levels.values() if level]
    return max(rated) if rated else None


def rating(method: Method, likelihood: int, impact: int) -> str:
    """The rating for a likelihood and an overall impact, by looking up the matrix."""
    if likelihood not in levels(method, "likelihood") or impact not in levels(method, "impact"):
        raise ValueError("That is not a level of this scoring method.")
    return str(method["matrix"][impact - 1][likelihood - 1])


def exceeds(method: Method, rating_key: str | None, appetite: str | None) -> bool:
    """Whether a rating is above an appetite. With either unknown, nothing is exceeded."""
    if not rating_key or not appetite:
        return False
    return position(method, rating_key) > position(method, appetite)


def control_state(design: str | None, operation: str | None, *, stale: bool = False) -> str:
    """What is known about a control, as one word. Unknown counts for nothing: a control
    nobody has checked, or whose rating has aged out, is not treated as working."""
    if stale:
        return "stale"
    if design in (None, "not_assessed") or operation in (None, "not_assessed"):
        return "not_assessed"
    if "ineffective" in (design, operation):
        return "ineffective"
    if "partly" in (design, operation):
        return "partly"
    return "effective"


def strength(method: Method, state: str) -> float:
    table = method["control_effect"]["strength"]
    return float(table.get("not_assessed" if state == "stale" else state, 0.0))


def suggest(
    method: Method, likelihood: int, impact: int, controls: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """The residual rating the controls suggest, with its working.

    Each control has ``reduces`` (likelihood, impact, or both), ``reliance`` (primary or
    supporting), ``design``, ``operation``, and optionally ``stale``. For each axis, strength
    times reliance weight is added up; its whole part is the number of levels the axis comes
    down, to the method's limit and never below level 1.
    """
    effect = method["control_effect"]
    totals = dict.fromkeys(AXES, 0.0)
    lines = []
    for control in controls:
        state = control_state(
            control.get("design"), control.get("operation"), stale=bool(control.get("stale"))
        )
        power = strength(method, state)
        weight = float(effect["reliance"].get(control.get("reliance"), 0.0))
        reduces = control.get("reduces")
        for axis in AXES:
            if reduces in (axis, "both"):
                totals[axis] += power * weight
        lines.append(
            {
                **{key: control[key] for key in ("ref", "name") if key in control},
                "reduces": reduces,
                "reliance": control.get("reliance"),
                "state": state,
                "strength": power,
                "weight": weight,
                "counts": power * weight,
            }
        )
    start = {"likelihood": likelihood, "impact": impact}
    steps, after = {}, {}
    for axis in AXES:
        down = min(int(effect["limit"]), int(totals[axis] + 1e-9))
        after[axis] = max(1, start[axis] - down)
        steps[axis] = start[axis] - after[axis]
    return {
        "likelihood": after["likelihood"],
        "impact": after["impact"],
        "rating": rating(method, after["likelihood"], after["impact"]),
        "from": {**start, "rating": rating(method, likelihood, impact)},
        "totals": totals,
        "steps": steps,
        "limit": int(effect["limit"]),
        "controls": lines,
    }
