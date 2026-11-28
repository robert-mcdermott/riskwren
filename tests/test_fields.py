"""Fields of the organization's own (PLT-18): set by those who run the program, given on a
record like any other fact, checked by their kind, and kept in the record's history."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.people import People

Clients = Callable[[str | None], TestClient]
FIELDS = [
    {"key": "cost_center", "label": "Cost center", "kind": "text", "required": True,
     "help": "As finance knows it."},
    {"key": "users", "label": "People who use it", "kind": "number"},
    {"key": "renewal", "label": "Contract renewal", "kind": "date"},
    {"key": "tier", "label": "Support tier", "kind": "choice", "choices": ["Gold", "Silver"]},
]  # fmt: skip


def _locations(response) -> set[str]:  # type: ignore[no-untyped-def]
    return {".".join(map(str, e["location"])) for e in response.json()["errors"]}


def test_fields_are_the_programs_and_values_are_the_records(
    as_role: Clients, people: People
) -> None:
    manager, steward, member = as_role("manager"), as_role("steward"), as_role("member")
    assert member.put("/api/v1/program/fields/system", json={"fields": FIELDS}).status_code == 403
    bad = manager.put("/api/v1/program/fields/system", json={"fields": [
        {"key": "Bad Key", "label": "x", "kind": "text"}]})  # fmt: skip
    assert bad.status_code == 422
    assert (
        manager.put("/api/v1/program/fields/incident", json={"fields": FIELDS}).status_code == 422
    )
    saved = manager.put("/api/v1/program/fields/system", json={"fields": FIELDS})
    assert saved.status_code == 200, saved.text
    shown = member.get("/api/v1/program/fields").json()["data"]
    assert [f["key"] for f in shown["fields"]["system"]] == [f["key"] for f in FIELDS]
    assert shown["can_change"] is False

    unit = people.units["HALE"]
    missing = steward.post("/api/v1/systems", json={
        "name": "Freezer monitor", "kind": "application", "org_unit_id": unit})  # fmt: skip
    assert missing.status_code == 422 and "custom.cost_center" in _locations(missing)
    wrong = steward.post("/api/v1/systems", json={
        "name": "Freezer monitor", "kind": "application", "org_unit_id": unit,
        "custom": {"cost_center": "CC-12", "users": "many", "renewal": "soon",
                   "tier": "Bronze", "colour": "red"}})  # fmt: skip
    assert wrong.status_code == 422
    assert {"custom.users", "custom.renewal", "custom.tier", "custom"} <= _locations(wrong)
    made = steward.post("/api/v1/systems", json={
        "name": "Freezer monitor", "kind": "application", "org_unit_id": unit,
        "custom": {"cost_center": " CC-12 ", "users": "40", "renewal": "2027-03-01",
                   "tier": "Gold"}})  # fmt: skip
    assert made.status_code == 201, made.text
    ref = made.json()["data"]["ref"]
    record = steward.get(f"/api/v1/systems/{ref}").json()["data"]
    values = {item["key"]: item["value"] for item in record["custom"]}
    assert values == {"cost_center": "CC-12", "users": 40, "renewal": "2027-03-01", "tier": "Gold"}

    changed = steward.patch(f"/api/v1/systems/{ref}", json={
        "version": record["version"], "custom": {"tier": "Silver", "renewal": None}})  # fmt: skip
    assert changed.status_code == 200, changed.text
    after = {
        i["key"]: i["value"] for i in steward.get(f"/api/v1/systems/{ref}").json()["data"]["custom"]
    }
    assert (
        after["tier"] == "Silver" and after["renewal"] is None and after["cost_center"] == "CC-12"
    )
    history = steward.get(f"/api/v1/systems/{ref}/history").json()["data"]
    assert any("custom_value" in str(event) or "Silver" in str(event) for event in history)

    # A field taken away keeps its values, unshown; brought back, they return.
    manager.put("/api/v1/program/fields/system", json={"fields": FIELDS[1:]})
    gone = steward.get(f"/api/v1/systems/{ref}").json()["data"]["custom"]
    assert "cost_center" not in {item["key"] for item in gone}
    manager.put("/api/v1/program/fields/system", json={"fields": FIELDS})
    back = steward.get(f"/api/v1/systems/{ref}").json()["data"]["custom"]
    assert {i["key"]: i["value"] for i in back}["cost_center"] == "CC-12"


def test_risks_and_controls_carry_fields_too(as_role: Clients, people: People) -> None:
    manager = as_role("manager")
    one = [{"key": "board_item", "label": "Board item", "kind": "choice", "choices": ["Yes", "No"]}]
    for kind in ("risk", "control"):
        assert (
            manager.put(f"/api/v1/program/fields/{kind}", json={"fields": one}).status_code == 200
        )
    risk = manager.post("/api/v1/risks", json={
        "name": "Freezers fail", "cause": "Age", "event": "A freezer fails",
        "consequence": "Specimens lost", "category": "operations",
        "org_unit_id": people.units["IMM"], "custom": {"board_item": "Yes"}})  # fmt: skip
    assert risk.status_code == 201, risk.text
    shown = manager.get(f"/api/v1/risks/{risk.json()['data']['ref']}").json()["data"]
    assert shown["custom"] == [{**one[0], "value": "Yes"}]
    control = manager.post("/api/v1/controls", json={
        "name": "Freezer alarms", "statement": "Alarms page the on-call technician.",
        "kind": "detective", "org_unit_id": people.units["IMM"],
        "custom": {"board_item": "No"}})  # fmt: skip
    assert control.status_code == 201, control.text
    seen = manager.get(f"/api/v1/controls/{control.json()['data']['ref']}").json()["data"]
    assert {item["key"]: item["value"] for item in seen["custom"]} == {"board_item": "No"}
