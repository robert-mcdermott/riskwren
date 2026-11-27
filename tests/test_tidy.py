"""Finding anything on record, and keeping it in order: one search, saved views, what
records are missing, likely duplicates, and what a person held when they leave."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.core.clock import frozen_at
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import Account, Action, Notice, RecordOwner
from riskwren.inventory import completeness, duplicates, find, links, records, views
from riskwren.inventory.registry import PROCESS, SYSTEM, TYPES
from riskwren.people import accounts, handover
from riskwren.reporting import service as reporting
from riskwren.risk.register import RISK
from riskwren.treatment import service as treatment
from tests.people import ME, ROLES, People
from tests.test_risks import raise_risk, who

Clients = Callable[[str | None], TestClient]
NOON = datetime(2026, 3, 2, 12, tzinfo=UTC)


def system(session, by, unit: int, name: str, **more):  # type: ignore[no-untyped-def]
    values = {"name": name, "kind": "application", "org_unit_id": unit, **more}
    return records.create(session, by, SYSTEM, values)


def give(session, by, record_type, record, account_id: int) -> None:  # type: ignore[no-untyped-def]
    records.set_owners(
        session, by, record_type, record, [{"account_id": account_id, "kind": "owner"}]
    )


# --- Search -------------------------------------------------------------------------------


def test_a_search_never_returns_a_record_its_searcher_could_not_open(
    db: Database, people: People, as_role: Clients
) -> None:
    manager, steward = who(db, people, "manager"), who(db, people, "steward")
    hale, cancer = people.units["HALE"], people.units["CANCER"]
    with db.write(manager.actor) as session, frozen_at(NOON):
        system(session, steward, hale, "Freezer monitoring", summary="Alarms for the cold room")
        system(session, steward, hale, "Freezer vault", restricted=True)
        system(session, manager, cancer, "Freezer inventory", restricted=True)
        records.create(
            session, steward, PROCESS,
            {"name": "Freezer maintenance", "kind": "research_support", "org_unit_id": hale},
        )  # fmt: skip
        raise_risk(session, steward, hale, "Freezer failure")
        raise_risk(session, manager, cancer, "Freezer room flood")
        raise_risk(session, manager, cancer, "Stolen freezer keys", restricted=True)
        everything = sum(
            records.search(session, ME, each, {"q": "freezer"}, limit=1)[1]
            for each in TYPES.values()
        )
        assert everything == 7
    seen = {}
    for role in ROLES:
        client = as_role(role)
        found = client.get("/api/v1/search", params={"q": "freezer", "limit": 50}).json()["data"]
        refs = [item["ref"] for group in found["groups"] for item in group["items"]]
        assert found["total"] == len(refs)
        # Everything found opens for the person who found it.
        with db.read() as session:
            for group in found["groups"]:
                for item in group["items"]:
                    opened = client.get(f"/api/v1/{group['path']}/{item['ref']}")
                    assert opened.status_code == 200, (role, item)
        seen[role] = len(refs)
    # Those who read everything find everything; a member of one lab finds what is open to
    # them and nothing restricted or kept by another division.
    assert seen["manager"] == seen["auditor"] == seen["admin"] == 7
    assert seen["steward"] < 7 and seen["member"] < seen["steward"]
    member = as_role("member")
    found = member.get("/api/v1/search", params={"q": "freezer", "limit": 50}).json()["data"]
    names = {item["name"] for group in found["groups"] for item in group["items"]}
    assert "Freezer monitoring" in names and "Freezer failure" in names
    assert not names & {"Freezer vault", "Freezer inventory", "Stolen freezer keys"}
    assert member.get("/api/v1/search", params={"q": "stolen keys"}).json()["data"]["total"] == 0


def test_search_ranks_what_was_asked_for_first(db: Database, people: People) -> None:
    steward = who(db, people, "steward")
    hale = people.units["HALE"]
    with db.write(steward.actor) as session, frozen_at(NOON):
        system(session, steward, hale, "Laboratory notebook", summary="Holds the cold room log")
        cold = system(session, steward, hale, "Cold room monitor")
        system(session, steward, hale, "Monitor of the cold room doors")
        found = find.everywhere(session, steward, "cold room")
        assert [item["name"] for item in found["groups"][0]["items"]] == [
            "Cold room monitor", "Monitor of the cold room doors", "Laboratory notebook",
        ]  # fmt: skip
        # Words are found in any order, and all of them must be there.
        assert find.everywhere(session, steward, "monitor cold")["total"] == 2
        assert find.everywhere(session, steward, "cold freezer")["total"] == 0
        # A reference is its own best answer.
        exact = find.everywhere(session, steward, cold.ref.lower())
        assert exact["best"] == {"type": "system", "ref": cold.ref}
        # Too little to go on finds nothing, and one kind can be asked for alone.
        assert find.everywhere(session, steward, "c")["groups"] == []
        assert find.everywhere(session, steward, "cold", only="risk")["total"] == 0


# --- Completeness -------------------------------------------------------------------------


def test_a_record_says_what_it_is_missing_and_the_count_is_the_list(
    db: Database, people: People, as_role: Clients
) -> None:
    steward = who(db, people, "steward")
    hale = people.units["HALE"]
    with db.write(steward.actor) as session, frozen_at(NOON):
        bare = system(session, steward, hale, "Bare")
        whole = system(session, steward, hale, "Whole", hosting="cloud", data_class="internal")
        store = records.create(
            session, steward, PROCESS,
            {"name": "Storage", "kind": "research_support", "org_unit_id": hale,
             "summary": "Keeps specimens", "data_class": "internal"},
        )  # fmt: skip
        links.add(session, steward, PROCESS, store, "relies_on", SYSTEM, whole)
        retired = system(session, steward, hale, "Old", status="retired")
        session.flush()
        cards = {
            card["name"]: [each["key"] for each in card["missing"]]
            for card in records.cards(session, SYSTEM, [bare, whole, retired])
        }
        assert cards == {"Bare": ["data_class", "links", "hosting"], "Whole": [], "Old": []}
        shown = records.detail(session, steward, SYSTEM, bare)
        assert [each["label"] for each in shown["missing"]] == [
            "the class of data it handles", "a link to anything else", "where it is hosted",
        ]  # fmt: skip
        raise_risk(session, steward, hale, "Unrated")
        summary = {each["type"]: each for each in completeness.summary(session, steward)}
        assert summary["system"]["total"] == 2 and summary["system"]["incomplete"] == 1
        assert {each["key"]: each["count"] for each in summary["risk"]["missing"]} == {
            "rating": 1, "controls": 1,
        }  # fmt: skip
        # Each figure is the length of the list its filters give.
        for kind in summary.values():
            for figure in [kind, *kind["missing"]]:
                rows, total = records.search(
                    session, steward, TYPES[kind["type"]], figure["filters"]
                )
                number = figure["incomplete"] if figure is kind else figure["count"]
                assert total == number == len(rows)
        with pytest.raises(Invalid):
            records.search(session, steward, SYSTEM, {"missing": "a soul"})
    listed = as_role("steward").get("/api/v1/systems", params={"missing": "data_class"})
    assert [row["name"] for row in listed.json()["data"]] == ["Bare"]
    tidy = as_role("member").get("/api/v1/tidy").json()["data"]
    assert {each["type"] for each in tidy["completeness"]} == {"system", "process", "risk"}


# --- Duplicates ---------------------------------------------------------------------------


def test_likely_duplicates_are_suggested_and_can_be_dismissed(
    db: Database, people: People, as_role: Clients
) -> None:
    assert duplicates.likeness("Freezer monitoring", "Monitoring of the freezer") == 1.0
    assert duplicates.likeness("Freezer monitoring", "Freezer monitorng") > duplicates.CLOSE
    assert duplicates.likeness("Ransomware: Immunology", "Ransomware: Cancer Biology") < 0.88
    assert duplicates.likeness("Backups", "Badges") < duplicates.CLOSE
    manager, steward, member = (who(db, people, role) for role in ("manager", "steward", "member"))
    hale, cancer = people.units["HALE"], people.units["CANCER"]
    with db.write(manager.actor) as session, frozen_at(NOON):
        one = system(session, steward, hale, "Freezer monitoring")
        two = system(session, steward, hale, "Freezer monitorng")
        system(session, steward, hale, "Sequencer")
        # Two units each keep one on purpose: only the very same name counts across units.
        system(session, manager, cancer, "Freezer monitoring service")
        same = system(session, manager, cancer, "Monitoring, freezer")
        system(session, steward, hale, "Freezer monitoring", status="retired")
        found = duplicates.pairs(session, manager, SYSTEM)
        assert [sorted(each["ref"] for each in pair["records"]) for pair in found] == [
            sorted([one.ref, same.ref]), sorted([one.ref, two.ref]),
        ]  # fmt: skip
        # While a name is being typed, what it might already be is offered.
        offered = duplicates.similar(session, steward, SYSTEM, "Freezer monitor", unit=hale)
        assert sorted(each["ref"] for each in offered) == [one.ref, two.ref]
        assert duplicates.similar(session, steward, SYSTEM, "Fr") == []
        assert duplicates.similar(session, steward, SYSTEM, "Mass spectrometer") == []
        # Someone who can edit one of them says they are different things.
        with pytest.raises(PermissionDenied):
            duplicates.dismiss(session, member, SYSTEM, one, two)
        duplicates.dismiss(session, steward, SYSTEM, one, two)
        duplicates.dismiss(session, steward, SYSTEM, two, one)  # said once
        assert len(duplicates.pairs(session, manager, SYSTEM)) == 1
        assert two.ref not in [
            each["ref"]
            for each in duplicates.similar(session, steward, SYSTEM, one.name, except_id=one.id)
        ]
    steward_client = as_role("steward")
    asked = steward_client.get(
        "/api/v1/similar", params={"type": "system", "name": "freezer monitoring", "unit": hale}
    )
    assert asked.json()["data"][0]["name"] == "Freezer monitoring"
    assert (
        steward_client.get("/api/v1/similar", params={"type": "x", "name": "y"}).status_code == 422
    )
    # A member sees only pairs they can see both halves of.
    tidy = as_role("manager").get("/api/v1/tidy").json()["data"]
    assert [len(each["pairs"]) for each in tidy["duplicates"]] == [1]
    said = as_role("manager").post(
        "/api/v1/tidy/not-duplicates", json={"refs": [one.ref, same.ref]}
    )
    assert said.status_code == 200
    assert as_role("manager").get("/api/v1/tidy").json()["data"]["duplicates"] == []


# --- Saved views --------------------------------------------------------------------------


def test_a_view_keeps_the_question_and_never_the_answer(
    db: Database, people: People, as_role: Clients
) -> None:
    member, steward, admin = as_role("member"), as_role("steward"), as_role("admin")
    made = member.post(
        "/api/v1/views",
        json={
            "name": " My  late risks ",
            "path": "/risks",
            "query": "?overdue=true&cursor=abc&sort=name",
        },
    )
    assert made.status_code == 201, made.text
    view = made.json()["data"]
    assert (view["name"], view["href"]) == ("My late risks", "/risks?overdue=true&sort=name")
    assert view["mine"] and not view["shared"]
    for body, field in [
        ({"name": "My late risks", "path": "/risks", "query": ""}, "name"),  # a second of the name
        ({"name": "", "path": "/risks"}, "name"),
        ({"name": "x", "path": "risks"}, "path"),
        ({"name": "x", "path": "https://elsewhere.example/"}, "path"),
        ({"name": "y", "path": "/risks", "shared": True}, "shared"),  # not a member's to share
    ]:
        refused = member.post("/api/v1/views", json=body)
        assert refused.status_code == 422, body
        assert [each["location"][0] for each in refused.json()["errors"]] == [field], body
    # A steward shares one; everyone has it, and only its maker changes it.
    shared = steward.post(
        "/api/v1/views", json={"name": "Above appetite", "path": "/risks",
                               "query": "above_appetite=true", "shared": True},
    ).json()["data"]  # fmt: skip
    assert shared["shared"]
    listed = member.get("/api/v1/views", params={"path": "/risks"}).json()
    assert [(each["name"], each["mine"], each["can_change"]) for each in listed["data"]] == [
        ("My late risks", True, True), ("Above appetite", False, False),
    ]  # fmt: skip
    assert listed["meta"]["can_share"] is False
    assert member.get("/api/v1/views", params={"path": "/controls"}).json()["data"] == []
    assert steward.get("/api/v1/views").json()["data"][0]["name"] == "Above appetite"
    assert (
        member.patch(f"/api/v1/views/{shared['id']}", json={"name": "Mine now"}).status_code == 403
    )
    assert member.delete(f"/api/v1/views/{shared['id']}").status_code == 403
    assert steward.get("/api/v1/views?path=/risks").json()["data"][0]["by"] == "Steward Person"
    # Another person's private view does not exist, as far as anyone else can tell.
    assert steward.patch(f"/api/v1/views/{view['id']}", json={"name": "x"}).status_code == 404
    renamed = member.patch(
        f"/api/v1/views/{view['id']}", json={"name": "Late", "query": "overdue=true"}
    )
    assert renamed.json()["data"]["href"] == "/risks?overdue=true"
    # An administrator can take a shared view down; its maker can stop sharing it.
    assert (
        steward.patch(f"/api/v1/views/{shared['id']}", json={"shared": False}).json()["data"][
            "shared"
        ]
        is False
    )
    assert (
        member.get("/api/v1/views", params={"path": "/risks"}).json()["data"][0]["name"] == "Late"
    )
    steward.patch(f"/api/v1/views/{shared['id']}", json={"shared": True})
    assert admin.delete(f"/api/v1/views/{shared['id']}").status_code == 200
    assert member.delete(f"/api/v1/views/{view['id']}").status_code == 200
    assert member.get("/api/v1/views").json()["data"] == []
    assert views.clean_query("?b=2&a=1&cursor=x") == "a=1&b=2"


# --- When someone leaves ------------------------------------------------------------------


def unowned(session) -> list[tuple[str, str]]:  # type: ignore[no-untyped-def]
    """Every record with nobody who can sign in answering for it."""
    out = []
    for record_type in TYPES.values():
        rows = session.scalars(select(record_type.model)).all()
        owners = records.owners_of(session, record_type, [row.id for row in rows])
        out += [
            (record_type.key, row.ref) for row in rows if records.orphaned(owners.get(row.id, []))
        ]
    return out


def test_disabling_an_owner_leaves_nothing_without_one(
    db: Database, people: People, as_role: Clients
) -> None:
    manager, steward = who(db, people, "manager"), who(db, people, "steward")
    hale, cancer = people.units["HALE"], people.units["CANCER"]
    member = people.accounts["member"]
    with db.write(manager.actor) as session, frozen_at(NOON):
        alone = system(session, steward, hale, "Hers alone")
        give(session, steward, SYSTEM, alone, member)
        shared = system(session, steward, hale, "Shared")
        records.set_owners(
            session, steward, SYSTEM, shared,
            [{"account_id": member, "kind": "owner"},
             {"account_id": people.accounts["leader"], "kind": "owner"}],
        )  # fmt: skip
        helped = system(session, steward, hale, "Helped with")
        records.set_owners(
            session, steward, SYSTEM, helped,
            [{"account_id": steward.account_id, "kind": "owner"},
             {"account_id": member, "kind": "delegate"}],
        )  # fmt: skip
        far = system(session, manager, cancer, "In another division")
        give(session, manager, SYSTEM, far, member)
        risk = raise_risk(session, steward, hale, "Her risk")
        give(session, steward, RISK, risk, member)
        plan = treatment.create_plan(
            session, steward, risk, objective="Fix it", owner_id=member, due_on="2026-09-01"
        )
        action = treatment.add_action(
            session, steward, plan, title="Buy a spare", owner_id=member, due_on="2026-05-01"
        )
        session.flush()
        assert unowned(session) == []
        before = handover.holdings(session, manager, accounts.get(session, member))
        assert len(before["items"]) == 7
    admin = as_role("admin")
    disabled = admin.patch(f"/api/v1/accounts/{member}", json={"status": "disabled"})
    assert disabled.status_code == 200, disabled.text
    with db.read() as session, frozen_at(NOON):
        # Nothing is without an owner who can sign in. What she alone answered for went to
        # the steward of its unit, or where there is none, to whoever runs the program.
        assert unowned(session) == []
        owner = lambda record: [  # noqa: E731
            row.account_id
            for row in session.scalars(
                select(RecordOwner).where(
                    RecordOwner.record_type == "system", RecordOwner.record_id == record.id,
                    RecordOwner.kind == "owner",
                )
            )
        ]  # fmt: skip
        assert owner(alone) == [steward.account_id]
        assert owner(far) == [manager.account_id]
        assert sorted(owner(shared)) == sorted([member, people.accounts["leader"]])  # left be
        assert session.get(Action, action.id).owner_id == steward.account_id
        told = session.scalars(
            select(Notice.text).where(Notice.account_id == steward.account_id)
        ).all()
        assert told[-1] == (
            "Member Person's account was disabled. You now answer for 4 things they owned, "
            "until someone is named for good."
        )
        home = reporting.home(session, who(db, people, "steward"))
        assert ("handover", "Name who takes what Member Person held") in [
            (item["kind"], item["title"]) for item in home["items"]
        ]
        # What she held is still listed as hers to pass on, with who has it meanwhile.
        held = handover.holdings(session, manager, accounts.get(session, member))
        assert sorted((each["name"], each["kind"], each["held_by"]) for each in held["items"]) == [
            ("Buy a spare", "owner", "Steward Person"),
            ("Helped with", "delegate", None),
            ("Her risk", "owner", "Steward Person"),
            ("Hers alone", "owner", "Steward Person"),
            ("In another division", "owner", "Manager Person"),
            ("Shared", "owner", None),
            ("Treatment plan for Her risk", "owner", "Steward Person"),
        ]
        assert [each["name"] for each in handover.waiting(session, steward)] == ["Member Person"]
    # The steward passes on what is in her units, in one step; the rest is not hers to move.
    steward_client, leader = as_role("steward"), people.accounts["leader"]
    seen = steward_client.get(f"/api/v1/accounts/{member}/holdings").json()["data"]
    assert seen["can_pass_on"] == 6
    refused = steward_client.post(f"/api/v1/accounts/{member}/handover", json={"to": member})
    assert refused.status_code == 422
    done = steward_client.post(f"/api/v1/accounts/{member}/handover", json={"to": leader})
    assert done.status_code == 200, done.text
    assert done.json()["data"]["passed_on"] == 6
    with db.read() as session:
        assert unowned(session) == []
        left = handover.holdings(session, manager, accounts.get(session, member))
        assert [each["name"] for each in left["items"]] == ["In another division"]
        assert session.get(Action, action.id).owner_id == leader
        rows = session.scalars(
            select(RecordOwner).where(RecordOwner.account_id.in_([member, steward.account_id]))
        ).all()
        # The stand-in no longer holds what was passed on, and she holds only what is left.
        assert [
            (row.record_type, row.account_id) for row in rows if row.record_id != helped.id
        ] == []
        assert handover.waiting(session, steward) == []
        assert (
            session.scalars(select(Account.status).where(Account.id == member)).one() == "disabled"
        )
    # A member cannot pass on anything; an administrator passes on the rest, by name.
    assert (
        as_role("auditor")
        .post(f"/api/v1/accounts/{member}/handover", json={"to": leader})
        .status_code
        == 403
    )
    only = admin.post(
        f"/api/v1/accounts/{member}/handover",
        json={"to": leader, "only": [{"type": "system", "id": far.id}]},
    )
    assert only.json()["data"]["passed_on"] == 1 and only.json()["data"]["items"] == []
