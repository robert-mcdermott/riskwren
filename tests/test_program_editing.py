"""Changing the program in the app: categories, the scoring method, appetite, cadences, and
vocabularies, with a preview of the risks a change would move."""

from __future__ import annotations

import copy
from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from riskwren.core.clock import frozen_at
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import Event, Risk, ScoringMethod
from riskwren.events import chain
from riskwren.inventory import history, records
from riskwren.program import rules, vocab
from riskwren.risk import categories, program, register
from riskwren.risk import method as methods
from riskwren.risk.register import RISK
from tests.people import ME, People
from tests.test_risks import judge, raise_risk, who

Clients = Callable[[str | None], TestClient]
NOON = datetime(2026, 3, 2, 12, tzinfo=UTC)


def state(db: Database) -> dict[str, tuple]:
    with db.read() as session:
        return {
            risk.ref: (risk.inherent_rating, risk.residual_rating, risk.target_rating,
                       risk.standing, risk.next_review_on, risk.version)
            for risk in session.scalars(select(Risk).order_by(Risk.id))
        }  # fmt: skip


def events(db: Database) -> int:
    with db.read() as session:
        return session.execute(select(func.count()).select_from(Event)).scalar_one()


def stock(db: Database, people: People) -> dict[str, str]:
    """Five risks: three rated at different places on the matrix, one not rated, one closed."""
    steward = who(db, people, "steward")
    hale = people.units["HALE"]
    refs = {}
    with db.write(steward.actor) as session, frozen_at(NOON):
        for name, likelihood, impact in [("Middle", 3, 3), ("Likely", 4, 3), ("Small", 2, 2)]:
            risk = raise_risk(session, steward, hale, name)
            judge(session, steward, risk, "inherent", likelihood, mission=impact)
            judge(session, steward, risk, "residual", likelihood, mission=impact)
            refs[name] = risk.ref
        refs["Unrated"] = raise_risk(session, steward, hale, "Unrated").ref
        gone = raise_risk(session, steward, hale, "Gone")
        judge(session, steward, gone, "residual", 3, mission=3)
        register.update(session, steward, gone, {"status": "closed", "closed_reason": "Sold"},
                        version=gone.version)  # fmt: skip
        refs["Gone"] = gone.ref
    return refs


def harsher(db: Database) -> dict:
    """The method in force with one cell raised: possible and moderate becomes high."""
    with db.read() as session:
        definition = copy.deepcopy(methods.current(session))
    assert definition["matrix"][2][2] == "moderate"
    definition["matrix"][2][2] = "high"
    return definition


def test_publishing_a_changed_matrix_changes_exactly_the_risks_the_preview_listed(
    db: Database, people: People, as_role: Clients
) -> None:
    refs = stock(db, people)
    manager = as_role("manager")
    definition = harsher(db)
    before, logged = state(db), events(db)
    with frozen_at(NOON):
        previewed = manager.post("/api/v1/program/preview", json={"method": definition})
    assert previewed.status_code == 200, previewed.text
    assert previewed.json()["meta"]["preview"] is True
    listed = previewed.json()["data"]
    # Only the risk in the cell that changed is listed, with what would change about it.
    assert [each["ref"] for each in listed["risks"]] == [refs["Middle"]]
    moved = {change["field"]: (change["before"], change["after"])
             for change in listed["risks"][0]["changes"]}  # fmt: skip
    assert moved["inherent_rating"] == moved["residual_rating"] == ("moderate", "high")
    assert moved["next_review_on"] == ("2027-03-02", "2026-09-02")  # high is reviewed sooner
    assert listed["counts"]["rating"] == 1 and listed["changed"] == ["scoring method version 2"]
    # A preview changes nothing: no risk, no version of the method, not one event.
    assert state(db) == before and events(db) == logged
    with db.read() as session:
        assert methods.current_row(session).version == 1

    with frozen_at(NOON):
        published = manager.post("/api/v1/program/publish", json={"method": definition})
    assert published.status_code == 200, published.text
    done = published.json()["data"]
    assert done["risks"] == listed["risks"] and done["counts"] == listed["counts"]
    assert done["program"]["method"]["version"] == 2
    after = state(db)
    changed = {ref for ref in before if before[ref][:5] != after[ref][:5]}
    assert changed == {each["ref"] for each in listed["risks"]}
    assert after[refs["Middle"]][:2] == ("high", "high")
    assert after[refs["Gone"]] == before[refs["Gone"]]  # a closed risk is left as it was
    with db.read() as session:
        risk = session.scalars(select(Risk).where(Risk.ref == refs["Middle"])).one()
        # The judgment keeps the rating it was given and the version it was made under.
        newest = register.latest(session, risk)["residual"]
        assert newest is not None and (newest.rating, newest.method_id) == ("moderate", 1)
        versions = session.scalars(select(ScoringMethod).order_by(ScoringMethod.version))
        assert [row.status for row in versions] == ["superseded", "current"]
        titles = [entry["title"] for entry in history.for_record(session, RISK, risk)]
        assert "Changed when the program was changed" in titles
        assert chain.verify(session.connection()).ok
    # Publishing the same thing again changes nothing, and says so.
    again = manager.post("/api/v1/program/publish", json={"method": definition})
    assert again.json()["data"]["risks"] == [] and again.json()["data"]["changed"] == []
    # A new assessment is rated by the method now in force.
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        fresh = raise_risk(session, steward, people.units["HALE"], "Fresh")
        assert judge(session, steward, fresh, "residual", 3, mission=3).rating == "high"


def test_a_method_that_would_strand_what_is_on_record_is_refused(
    db: Database, people: People, as_role: Clients
) -> None:
    stock(db, people)
    manager = who(db, people, "manager")
    with db.read() as session:
        now = copy.deepcopy(methods.current(session))
    renamed = copy.deepcopy(now)
    renamed["ratings"][2]["label"] = "Serious"  # a new name for the same rating is fine
    rekeyed = copy.deepcopy(now)
    rekeyed["ratings"][2]["key"] = "serious"
    rekeyed["matrix"] = [["serious" if cell == "high" else cell for cell in row]
                         for row in rekeyed["matrix"]]  # fmt: skip
    shorter = copy.deepcopy(now)
    shorter["likelihood"] = shorter["likelihood"][:3]
    shorter["matrix"] = [row[:3] for row in shorter["matrix"]]
    falling = copy.deepcopy(now)
    falling["matrix"][4][4] = "low"
    with db.write(manager.actor) as session:
        for definition, said in [
            (rekeyed, "cannot be removed"),
            (shorter, "likelihood level 4"),
            (falling, "never fall"),
            ("a matrix", "whole scoring method"),
        ]:
            with pytest.raises(Invalid) as caught:
                program.change(session, manager, {"method": definition})
            assert said in caught.value.errors["method"], definition
        with pytest.raises(Invalid):
            program.change(session, manager, {})
        with pytest.raises(PermissionDenied):
            program.change(session, who(db, people, "steward"), {"method": renamed})
        found = program.change(session, manager, {"method": renamed})
        assert found["risks"] == [] and found["method_version"] == 2
    assert as_role("steward").post("/api/v1/program/preview", json={}).status_code == 403


def test_appetite_and_cadences_are_previewed_the_same_way(
    db: Database, people: People, as_role: Clients
) -> None:
    refs = stock(db, people)
    manager = as_role("manager")
    with db.read() as session:
        tree = categories.Tree(session)
        row = categories.by_key(session, "data_quality")
        in_force = tree.appetite(row.id)
        cadences = rules.get(session, "cadences")
    assert in_force == "moderate" and state(db)[refs["Likely"]][3] == "needs_decision"
    before = state(db)
    with frozen_at(NOON):
        found = manager.post(
            "/api/v1/program/preview", json={"appetites": {"data_quality": "high"}}
        ).json()["data"]
        # With more appetite, the high risk no longer needs a decision.
        assert [(each["ref"], each["changes"]) for each in found["risks"]] == [
            (refs["Likely"], [{"field": "standing", "label": "Standing",
                               "before": "needs_decision", "after": "within"}]),
        ]  # fmt: skip
        assert state(db) == before
        slower = {**cadences, "risk_review_months": {**cadences["risk_review_months"], "low": 36}}
        both = manager.post(
            "/api/v1/program/publish",
            json={"appetites": {"data_quality": "high"}, "cadences": slower},
        ).json()["data"]
    assert both["changed"] == ["appetite for Data and specimen integrity", "cadences"]
    assert {each["ref"] for each in both["risks"]} == {refs["Likely"], refs["Small"]}
    assert both["counts"] == {"risks": 2, "rating": 0, "standing": 1, "review": 1}
    assert state(db)[refs["Small"]][4] == date(2029, 3, 2)
    for cadence, field in [
        ({**cadences, "risk_review_months": {"low": 12}}, "risk_review_months"),
        ({**cadences, "risk_review_months": {**cadences["risk_review_months"], "critical": 48}},
         "risk_review_months"),
        ({**cadences, "control_rating_months": 0}, "control_rating_months"),
        ({**cadences, "issue_due_days": {**cadences["issue_due_days"], "critical": 400}},
         "issue_due_days"),
        ({**cadences, "reminders": {"soon_days": 14, "steward_after_days": 9,
                                    "leader_after_days": 3}}, "reminders"),
        ({**cadences, "coffee_minutes": 5}, "cadences"),
    ]:  # fmt: skip
        refused = manager.post("/api/v1/program/preview", json={"cadences": cadence})
        assert refused.status_code == 422, cadence
        assert [each["location"][0] for each in refused.json()["errors"]] == [field]
    for appetites in ({"nowhere": "high"}, {"data_quality": "enormous"}, {"research": None}):
        refused = manager.post("/api/v1/program/preview", json={"appetites": appetites})
        assert refused.status_code == 422, appetites


def test_categories_are_added_and_put_in_order(
    db: Database, people: People, as_role: Clients
) -> None:
    manager = as_role("manager")
    for body, field in [
        ({"name": "", "appetite": "low"}, "name"),
        ({"name": "Space weather"}, "appetite"),  # the top of the tree needs its own
        ({"name": "Space weather", "appetite": "vast"}, "appetite"),
        ({"name": "Solar storms", "parent": "nowhere"}, "parent"),
        ({"name": "Solar storms", "parent": "data_quality"}, "parent"),  # two deep, no more
        ({"name": "Research", "appetite": "low"}, "name"),  # its key is taken
        ({"name": "Space weather", "key": "Space Weather", "appetite": "low"}, "key"),
    ]:
        refused = manager.post("/api/v1/risk-categories", json=body)
        assert refused.status_code == 422, body
        assert [each["location"][0] for each in refused.json()["errors"]] == [field], body
    assert (
        as_role("steward")
        .post("/api/v1/risk-categories", json={"name": "x", "appetite": "low"})
        .status_code
        == 403
    )
    made = manager.post(
        "/api/v1/risk-categories", json={"name": "Space weather", "appetite": "low"}
    )
    assert made.status_code == 201, made.text
    tops = [each["key"] for each in made.json()["data"]]
    assert tops[-1] == "space_weather"
    under = manager.post(
        "/api/v1/risk-categories", json={"name": "Solar storms", "parent": "space_weather"}
    ).json()["data"]
    assert under[-1]["children"][0]["key"] == "solar_storms"
    assert under[-1]["children"][0]["appetite_in_force"] == "low"
    moved = manager.patch("/api/v1/risk-categories/space_weather", json={"move": "up"})
    assert [each["key"] for each in moved.json()["data"]][-2:] == ["space_weather", tops[-2]]
    # A risk can be raised under it at once, and retiring it keeps the risk.
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        risk = raise_risk(session, steward, people.units["HALE"], "Flare", category="solar_storms")
        ref = risk.ref
    manager.patch("/api/v1/risk-categories/solar_storms", json={"status": "retired"})
    with db.write(steward.actor) as session:
        assert records.load(session, steward, RISK, ref).category_id is not None
        with pytest.raises(Invalid):
            raise_risk(session, steward, people.units["HALE"], "Another", category="solar_storms")


def test_a_vocabulary_is_renamed_extended_and_retired_never_rekeyed(
    db: Database, people: People, as_role: Clients
) -> None:
    manager = as_role("manager")
    listed = {
        each["name"]: each for each in manager.get("/api/v1/admin/vocabularies").json()["data"]
    }
    assert listed["issue_severities"]["labels_only"] and listed["lifecycles"]["kept"] == [
        "in_service"
    ]
    kinds = listed["system_kinds"]["items"]
    kinds[0]["label"] = "Software"
    kinds[1]["retired"] = True
    kinds.insert(1, {"key": "robot", "label": "Laboratory robot", "description": "Moves samples"})
    saved = manager.put("/api/v1/vocabularies/system_kinds", json={"items": kinds})
    assert saved.status_code == 200, saved.text
    now = saved.json()["data"][:3]
    assert [(item["key"], item["label"], item.get("retired", False)) for item in now] == [
        ("application", "Software", False), ("robot", "Laboratory robot", False),
        ("platform", "Platform", True),
    ]  # fmt: skip
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        assert vocab.keys(session, "system_kinds")[:2] == ["application", "robot"]
        hale = people.units["HALE"]
        from riskwren.inventory.registry import SYSTEM

        records.create(
            session, steward, SYSTEM, {"name": "Arm", "kind": "robot", "org_unit_id": hale}
        )
        with pytest.raises(Invalid):  # a retired value is not offered to new records
            records.create(session, steward, SYSTEM,
                           {"name": "Old", "kind": "platform", "org_unit_id": hale})  # fmt: skip
    severities = listed["issue_severities"]["items"]
    for name, items, said in [
        ("system_kinds", kinds[1:], "in use and cannot be removed"),
        ("system_kinds", [*kinds, {"key": "Bad Key", "label": "x"}], "is not a key"),
        ("system_kinds", [{**item, "retired": True} for item in kinds], "at least one"),
        ("issue_severities", [*severities, {"key": "dire", "label": "Dire"}],
         "added by a program pack"),
        ("owner_kinds", [{**item, "retired": True} for item in listed["owner_kinds"]["items"]],
         "cannot be retired"),
        ("lifecycles", [{**item, "retired": item["key"] == "in_service"}
                        for item in listed["lifecycles"]["items"]], "so it stays"),
        ("nonsense", [], "nonsense"),
    ]:  # fmt: skip
        refused = manager.put(f"/api/v1/vocabularies/{name}", json={"items": items})
        assert refused.status_code == 422, (name, refused.text)
        assert said in refused.text, (name, refused.text)
    # What a list holds beyond names stays: a kind of link still says what it joins.
    links = listed["link_kinds"]["items"]
    renamed = [{"key": item["key"], "label": item["label"].upper()} for item in links]
    kept = manager.put("/api/v1/vocabularies/link_kinds", json={"items": renamed}).json()["data"]
    assert (
        kept[0]["label"] == links[0]["label"].upper() and kept[0]["between"] == links[0]["between"]
    )
    assert (
        as_role("steward")
        .put("/api/v1/vocabularies/system_kinds", json={"items": kinds})
        .status_code
        == 403
    )
    assert ME is not None
