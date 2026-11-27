"""The one condition language (ADR-0007).

The questions a questionnaire shows, and later applicability and tiering rules, all ask the
same kind of question: *given these answers, is this true?* A condition is plain data, never code:

    {"all": [ ... ]}        every one is true (an empty list is true)
    {"any": [ ... ]}        at least one is true (an empty list is false)
    {"not": { ... }}        the one inside is false
    {"field": "answers.data_class", "op": "eq", "value": "restricted"}

A field is a dotted path into the context it is evaluated against. A missing field is
empty: only ``empty``, ``ne``, and ``not_in`` can be true of it.

The web app has a twin of this evaluator (``js/core/conditions.js``). Both must pass the
cases in ``tests/fixtures/conditions-cases.json``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

OPERATORS = (
    "eq", "ne", "in", "not_in", "contains", "contains_any", "contains_all",
    "gt", "gte", "lt", "lte", "answered", "empty",
)  # fmt: skip
_NO_VALUE = {"answered", "empty"}
_LIST_VALUE = {"in", "not_in", "contains_any", "contains_all"}
_NUMBER = {"gt", "gte", "lt", "lte"}
MAX_DEPTH = 12


def lookup(context: Mapping[str, Any], path: str) -> Any:
    """The value at a dotted path, or None if any step is missing."""
    current: Any = context
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list | tuple):
        return list(value)
    return [] if _is_empty(value) else [value]


def _compare(op: str, actual: Any, expected: Any) -> bool:
    if op == "empty":
        return _is_empty(actual)
    if op == "answered":
        return not _is_empty(actual)
    if op == "ne":
        return actual != expected
    if op == "not_in":
        return actual not in _as_list(expected)
    if _is_empty(actual):
        return False
    if op == "eq":
        return bool(actual == expected)
    if op == "in":
        return actual in _as_list(expected)
    if op == "contains":
        return expected in _as_list(actual)
    if op == "contains_any":
        return any(item in _as_list(actual) for item in _as_list(expected))
    if op == "contains_all":
        wanted = _as_list(expected)
        return bool(wanted) and all(item in _as_list(actual) for item in wanted)
    left, right = _number(actual), _number(expected)
    if left is None or right is None:
        return False
    return {"gt": left > right, "gte": left >= right, "lt": left < right, "lte": left <= right}[op]


def evaluate(
    condition: Mapping[str, Any] | None, context: Mapping[str, Any], *, _depth: int = 0
) -> bool:
    """Is the condition true of the context? No condition at all is true."""
    if not condition:
        return True
    if _depth > MAX_DEPTH:
        return False
    if "all" in condition:
        return all(evaluate(part, context, _depth=_depth + 1) for part in condition["all"])
    if "any" in condition:
        return any(evaluate(part, context, _depth=_depth + 1) for part in condition["any"])
    if "not" in condition:
        return not evaluate(condition["not"], context, _depth=_depth + 1)
    return _compare(condition["op"], lookup(context, condition["field"]), condition.get("value"))


def problems(condition: Any, *, where: str = "condition", _depth: int = 0) -> list[str]:
    """What is wrong with a condition's shape. An empty list means it can be evaluated."""
    if condition is None or condition == {}:
        return []
    if not isinstance(condition, Mapping):
        return [f"{where}: must be an object"]
    if _depth > MAX_DEPTH:
        return [f"{where}: nested too deeply"]
    for group in ("all", "any"):
        if group in condition:
            if len(condition) != 1 or not isinstance(condition[group], list):
                return [f"{where}: `{group}` must be a list, alone in its object"]
            found: list[str] = []
            for index, part in enumerate(condition[group]):
                if not part:
                    found.append(f"{where}.{group}[{index}]: is empty")
                found += problems(part, where=f"{where}.{group}[{index}]", _depth=_depth + 1)
            return found
    if "not" in condition:
        if len(condition) != 1 or not condition["not"]:
            return [f"{where}: `not` must hold one condition, alone in its object"]
        return problems(condition["not"], where=f"{where}.not", _depth=_depth + 1)
    found = []
    field, op = condition.get("field"), condition.get("op")
    if not isinstance(field, str) or not field or any(not part for part in field.split(".")):
        found.append(f"{where}: needs a `field` such as answers.data_class")
    if op not in OPERATORS:
        found.append(f"{where}: `op` must be one of {', '.join(OPERATORS)}")
        return found
    extra = set(condition) - {"field", "op", "value"}
    if extra:
        found.append(f"{where}: does not understand {', '.join(sorted(extra))}")
    if op in _NO_VALUE:
        if "value" in condition:
            found.append(f"{where}: `{op}` takes no value")
    elif "value" not in condition:
        found.append(f"{where}: `{op}` needs a value")
    elif op in _LIST_VALUE and not isinstance(condition["value"], list):
        found.append(f"{where}: `{op}` needs a list of values")
    elif op in _NUMBER and _number(condition["value"]) is None:
        found.append(f"{where}: `{op}` needs a number")
    return found


def fields(condition: Mapping[str, Any] | None) -> set[str]:
    """Every field a condition looks at."""
    if not condition:
        return set()
    if "all" in condition or "any" in condition:
        found: set[str] = set()
        for part in condition.get("all", condition.get("any", [])):
            found |= fields(part)
        return found
    if "not" in condition:
        return fields(condition["not"])
    return {condition["field"]}
