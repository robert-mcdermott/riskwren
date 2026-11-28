"""The API's contract with the systems that use it (wave 9, slice 4).

``docs/api-contract.json`` records every route, its parameters, and the fields its body takes,
and which of them are needed. A change may add to it: a new route, a new optional parameter or
field. A change that would break a client is caught here: a route taken away, a parameter or
field taken away, or one that was optional made needed. Such a change is made on purpose, by
editing the contract by hand and saying so under **Breaking** in the changelog.

    UPDATE_DOCS=1 uv run pytest tests/test_contract.py    records what was added
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

CONTRACT = Path(__file__).resolve().parent.parent / "docs" / "api-contract.json"


def _schema(document: dict[str, Any], ref_or_schema: dict[str, Any]) -> dict[str, Any]:
    ref = ref_or_schema.get("$ref")
    if ref:
        return document["components"]["schemas"][ref.rsplit("/", 1)[-1]]
    return ref_or_schema


def contract(document: dict[str, Any]) -> dict[str, Any]:
    """What a client relies on: each operation's parameters and body fields, each needed or not."""
    found: dict[str, Any] = {}
    for path, methods in document["paths"].items():
        for method, operation in methods.items():
            entry: dict[str, Any] = {"parameters": {}, "body": {}}
            for parameter in operation.get("parameters", []):
                entry["parameters"][f"{parameter['in']}:{parameter['name']}"] = bool(
                    parameter.get("required")
                )
            body = operation.get("requestBody", {}).get("content", {}).get("application/json")
            if body:
                schema = _schema(document, body["schema"])
                needed = set(schema.get("required", []))
                entry["body"] = {name: name in needed for name in schema.get("properties", {})}
            found[f"{method.upper()} {path}"] = entry
    return dict(sorted(found.items()))


def breaks(recorded: dict[str, Any], now: dict[str, Any]) -> list[str]:
    found = []
    for operation, before in recorded.items():
        after = now.get(operation)
        if after is None:
            found.append(f"{operation} is gone")
            continue
        for part in ("parameters", "body"):
            for name, needed in before[part].items():
                if name not in after[part]:
                    found.append(f"{operation}: {name} is gone")
                elif after[part][name] and not needed:
                    found.append(f"{operation}: {name} is now needed")
            for name, needed in after[part].items():
                if needed and name not in before[part]:
                    found.append(f"{operation}: a new {name} is needed")
    return found


def test_no_change_breaks_a_client(full_client: TestClient) -> None:
    now = contract(full_client.get("/api/openapi.json").json())
    recorded = json.loads(CONTRACT.read_text(encoding="utf-8")) if CONTRACT.exists() else {}
    problems = breaks(recorded, now)
    assert problems == [], (
        "These would break a client. If they are meant, edit docs/api-contract.json by hand "
        "and say so under Breaking in the changelog:\n  " + "\n  ".join(problems)
    )
    if os.environ.get("UPDATE_DOCS") or not CONTRACT.exists():
        CONTRACT.write_text(json.dumps(now, indent=1) + "\n", encoding="utf-8")
    else:
        added = sorted(set(now) - set(recorded))
        assert not added, f"Record the new routes: UPDATE_DOCS=1 uv run pytest {__file__}: {added}"


def test_the_check_catches_what_breaks() -> None:
    before = {"GET /x": {"parameters": {"query:q": False}, "body": {}},
              "POST /y": {"parameters": {}, "body": {"name": True, "note": False}}}  # fmt: skip
    after = {"POST /y": {"parameters": {}, "body": {"name": True, "note": True, "due": True}},
             "GET /z": {"parameters": {}, "body": {}}}  # fmt: skip
    assert breaks(before, after) == [
        "GET /x is gone", "POST /y: note is now needed",
        "POST /y: a new due is needed"]  # fmt: skip
    assert breaks(after, {**after, "GET /w": {"parameters": {}, "body": {}}}) == []
