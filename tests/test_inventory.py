"""The inventory: records, owners, links, who sees what, and the readable history."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from riskwren.access.principal import Principal
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.engine import Database
from riskwren.inventory import access, history, links, records
from riskwren.inventory.registry import PROCESS, SYSTEM, THIRD_PARTY, find, find_any
from riskwren.people import accounts
from riskwren.program import settings, vocab
from tests.people import ME, ROLES, People

Clients = Callable[[str | None], TestClient]


def who(db: Database, people: People, role: str) -> Principal:
    with db.read() as session:
        return accounts.principal_for(session, accounts.get(session, people.accounts[role]))


@dataclass
class Stock:
    storage: str  # a process in the Hale Lab, added by the steward
    monitor: str  # a system in the Hale Lab
    lims: str  # a system in Cancer Biology
    supplier: str  # a third party at the top of the organization
    sealed: str  # a restricted system in the Hale Lab
    vault: str  # a restricted system in Cancer Biology


@pytest.fixture
def stock(db: Database, people: People) -> Stock:
    steward, manager = who(db, people, "steward"), who(db, people, "manager")
    hale, cancer, top = people.units["HALE"], people.units["CANCER"], people.units["NMI"]
    with db.write(ME.actor) as session:
        storage = records.create(
            session, steward, PROCESS,
            {"name": "Specimen storage", "kind": "research_support", "org_unit_id": hale,
             "criticality": "critical"},
        )  # fmt: skip
        monitor = records.create(
            session, steward, SYSTEM,
            {"name": "Freezer monitoring", "kind": "device", "org_unit_id": hale},
        )  # fmt: skip
        lims = records.create(
            session, manager, SYSTEM,
            {"name": "Sample tracking", "kind": "application", "org_unit_id": cancer,
             "data_class": "restricted", "criticality": "high"},
        )  # fmt: skip
        supplier = records.create(
            session, manager, THIRD_PARTY,
            {"name": "Coldline Service", "kind": "service_provider", "org_unit_id": top},
        )  # fmt: skip
        sealed = records.create(
            session, steward, SYSTEM,
            {"name": "Sequencer workstation", "kind": "instrument", "org_unit_id": hale,
             "restricted": True},
        )  # fmt: skip
        vault = records.create(
            session, manager, SYSTEM,
            {"name": "Key store", "kind": "infrastructure", "org_unit_id": cancer,
             "restricted": True},
        )  # fmt: skip
        return Stock(storage.ref, monitor.ref, lims.ref, supplier.ref, sealed.ref, vault.ref)


# --- Vocabularies -------------------------------------------------------------------------


def test_vocabularies_have_defaults_and_keep_their_order(db: Database) -> None:
    with db.write(ME.actor) as session:
        assert vocab.keys(session, "criticalities") == ["low", "moderate", "high", "critical"]
        assert vocab.keys(session, "data_classes") == [
            "public", "internal", "confidential", "restricted",
        ]  # fmt: skip
        assert vocab.rank(session, "criticalities", "high") == 2
        assert vocab.rank(session, "criticalities", "nope") == -1
        assert vocab.labels(session, "owner_kinds")["delegate"] == "Delegate"
        assert all("examples" in item for item in vocab.get(session, "data_classes"))
        kinds = vocab.get(session, "process_kinds")
        kinds[0]["label"] = "Science"
        kinds[1]["retired"] = True
        vocab.put(session, "process_kinds", kinds)
        assert vocab.labels(session, "process_kinds")["research"] == "Science"
        assert "research_support" not in vocab.keys(session, "process_kinds")
        assert "research_support" in vocab.keys(session, "process_kinds", active_only=False)
        with pytest.raises(Invalid, match="not valid") as caught:
            vocab.put(session, "process_kinds", kinds[1:])
        assert "cannot be removed" in caught.value.errors["items"]
        with pytest.raises(Invalid):
            vocab.put(session, "process_kinds", [{"key": "a", "label": ""}])
        with pytest.raises(Invalid):
            vocab.put(session, "nothing", [])


def test_every_kind_of_link_joins_record_types_that_exist(db: Database) -> None:
    from riskwren.inventory.registry import TYPES

    with db.read() as session:
        for kind in links.kinds(session).values():
            assert kind["label"] and kind["reverse"]
            assert all(end in TYPES for pair in kind["between"] for end in pair)
        assert links.kinds_between(session, "process", "system") == ["relies_on"]
        assert links.kinds_between(session, "system", "process") == []


# --- Adding and changing ------------------------------------------------------------------


def test_adding_a_record_gives_it_a_reference_and_an_owner(
    db: Database, people: People, stock: Stock
) -> None:
    assert (stock.storage, stock.monitor, stock.lims) == ("PRC-0001", "SYS-0001", "SYS-0002")
    assert stock.supplier == "TP-0001"
    steward = who(db, people, "steward")
    with db.read() as session:
        storage = find(session, PROCESS, stock.storage)
        shown = records.detail(session, steward, PROCESS, storage)
        assert shown["criticality"] == "critical" and shown["status"] == "active"
        assert [(o["account_id"], o["kind"]) for o in shown["owners"]] == [
            (people.accounts["steward"], "owner")
        ]
        assert not shown["orphaned"] and shown["can"] == {"edit": True, "assess": True}
        monitor = records.detail(session, steward, SYSTEM, find(session, SYSTEM, stock.monitor))
        # What was not said takes the default: moderately critical, and in service.
        assert (monitor["criticality"], monitor["lifecycle"]) == ("moderate", "in_service")
        assert find_any(session, " sys-0002 ")[0] is SYSTEM
        with pytest.raises(NotFound):
            find(session, PROCESS, "SYS-0001")
        with pytest.raises(NotFound):
            find_any(session, "XYZ-0001")


def test_what_is_entered_is_checked(db: Database, people: People) -> None:
    manager = who(db, people, "manager")
    with db.write(ME.actor) as session, pytest.raises(Invalid) as caught:
        records.create(
            session, manager, SYSTEM,
            {"name": " ", "kind": "robot", "org_unit_id": 9999, "criticality": "extreme",
             "data_class": "secret", "url": "ftp://files", "tags": "one", "hosting": "moon"},
        )  # fmt: skip
    assert set(caught.value.errors) == {
        "name", "kind", "org_unit_id", "criticality", "data_class", "url", "tags", "hosting",
    }  # fmt: skip
    with db.write(ME.actor) as session, pytest.raises(Invalid) as caught:
        records.create(session, manager, PROCESS, {"name": "x" * 201})
    assert set(caught.value.errors) == {"name", "kind", "org_unit_id"}


def test_records_are_added_by_a_units_steward_or_a_manager(db: Database, people: People) -> None:
    hale, cancer = people.units["HALE"], people.units["CANCER"]
    system = {"name": "Plate reader", "kind": "instrument"}
    for role, unit, allowed in [
        ("steward", hale, True),  # a steward of the division above
        ("steward", cancer, False),
        ("manager", cancer, True),
        ("member", hale, False),  # works there, and that is not enough
        ("leader", hale, False),
        ("assessor", hale, False),
        ("admin", hale, False),  # administration is not judgment
        ("auditor", hale, False),
    ]:
        principal = who(db, people, role)
        with db.write(ME.actor) as session:
            if allowed:
                assert records.create(session, principal, SYSTEM, {**system, "org_unit_id": unit})
            else:
                with pytest.raises(PermissionDenied):
                    records.create(session, principal, SYSTEM, {**system, "org_unit_id": unit})


def test_an_edit_against_an_old_version_is_refused(
    db: Database, people: People, stock: Stock
) -> None:
    steward = who(db, people, "steward")
    with db.write(ME.actor) as session:
        record = find(session, SYSTEM, stock.monitor)
        records.update(session, steward, SYSTEM, record, {"summary": "Probes"}, version=1)
        assert record.version == 2
        with pytest.raises(Conflict, match="changed by someone else"):
            records.update(session, steward, SYSTEM, record, {"summary": "Mine"}, version=1)
        # Saying the same thing again changes nothing, and so is not a new version.
        records.update(session, steward, SYSTEM, record, {"summary": "Probes"}, version=2)
        assert record.version == 2
        with pytest.raises(Invalid):
            records.update(
                session, steward, SYSTEM, record, {"name": "", "summary": "Lost"}, version=2
            )
        assert (record.name, record.summary) == ("Freezer monitoring", "Probes")
        records.update(session, steward, SYSTEM, record, {"status": "retired"}, version=2)
        assert record.status == "retired"


def test_who_may_edit(db: Database, people: People, stock: Stock) -> None:
    with db.write(ME.actor) as session:
        monitor, lims = find(session, SYSTEM, stock.monitor), find(session, SYSTEM, stock.lims)
        for role, record, allowed in [
            ("steward", monitor, True),
            ("manager", monitor, True),
            ("steward", lims, False),  # another division
            ("member", monitor, False),
            ("leader", monitor, False),  # a leader reads and accepts; they do not edit
            ("assessor", monitor, False),
            ("auditor", monitor, False),
            ("admin", monitor, False),
        ]:
            principal = who(db, people, role)
            assert access.can_edit(session, principal, SYSTEM, record) is allowed, role
        # Naming the member as a delegate lets them edit; as a contact, it does not.
        steward, member = who(db, people, "steward"), who(db, people, "member")
        named = [{"account_id": people.accounts["steward"], "kind": "owner"}]
        for kind, allowed in (("delegate", True), ("contact", False)):
            records.set_owners(
                session, steward, SYSTEM, monitor,
                [*named, {"account_id": people.accounts["member"], "kind": kind}],
            )  # fmt: skip
            session.flush()
            assert access.can_edit(session, member, SYSTEM, monitor) is allowed
        # A record moves only to a unit its editor looks after.
        with pytest.raises(PermissionDenied, match="only to a unit"):
            records.update(
                session, steward, SYSTEM, monitor,
                {"org_unit_id": people.units["CANCER"]}, version=monitor.version,
            )  # fmt: skip
        assert monitor.org_unit_id == people.units["HALE"]


# --- Who sees what ------------------------------------------------------------------------

# Which of the six records each role may see. The inventory is open to everyone signed in,
# whatever the visibility setting, because a record can only be linked to what its author
# can see. What is restricted is seen only by those who look after its unit.
# storage and monitor are ordinary records in the Hale Lab; lims is ordinary in Cancer
# Biology; supplier is ordinary at the top; sealed is restricted in the Hale Lab; vault is
# restricted in Cancer Biology.
ALL = {"storage", "monitor", "lims", "supplier", "sealed", "vault"}
ORDINARY = {"storage", "monitor", "lims", "supplier"}
SIGHT = {
    "admin": ALL,
    "manager": ALL,
    "auditor": ALL,
    "assessor": ORDINARY,  # everywhere, and never what is restricted
    "leader": ORDINARY | {"sealed"},  # their own division's restricted records too
    "steward": ORDINARY | {"sealed"},
    "member": ORDINARY,
}


@pytest.mark.parametrize("setting", ["open", "unit", "assigned"])
def test_who_sees_what(db: Database, people: People, stock: Stock, setting: str) -> None:
    with db.write(ME.actor) as session:
        settings.put(session, access.VISIBILITY_SETTING, setting)
    names = {getattr(stock, name): name for name in ALL}
    for role in ROLES:
        principal = who(db, people, role)
        with db.read() as session:
            one_by_one, listed = set(), set()
            for record_type in (PROCESS, SYSTEM, THIRD_PARTY):
                model = record_type.model
                for record in session.query(model).all():
                    if access.can_see(session, principal, record_type, record):
                        one_by_one.add(names[record.ref])
                rows, total = records.search(session, principal, record_type, {}, limit=200)
                assert total == len(rows)
                listed |= {names[row.ref] for row in rows}
        assert one_by_one == SIGHT[role], f"{setting}, {role}: single records"
        assert listed == one_by_one, f"{setting}, {role}: the list and single records disagree"


def test_being_named_on_a_record_is_enough_to_see_it(
    db: Database, people: People, stock: Stock
) -> None:
    member, manager = who(db, people, "member"), who(db, people, "manager")
    with db.write(ME.actor) as session:
        settings.put(session, access.VISIBILITY_SETTING, "assigned")
        vault = find(session, SYSTEM, stock.vault)
        with pytest.raises(NotFound):
            records.detail(session, member, SYSTEM, vault)
        records.set_owners(
            session, manager, SYSTEM, vault,
            [{"account_id": people.accounts["manager"], "kind": "owner"},
             {"account_id": people.accounts["member"], "kind": "contact"}],
        )  # fmt: skip
        session.flush()
        shown = records.detail(session, member, SYSTEM, vault)
        assert shown["restricted"] and shown["can"] == {"edit": False, "assess": False}
        rows, _ = records.search(session, member, SYSTEM, {"mine": True})
        assert [row.ref for row in rows] == [stock.vault]
        everything, _ = records.search(session, member, SYSTEM, {})
        assert stock.vault in {row.ref for row in everything}
        assert stock.sealed not in {row.ref for row in everything}


# --- Owners -------------------------------------------------------------------------------


def test_owners(db: Database, people: People, stock: Stock) -> None:
    steward = who(db, people, "steward")
    me, member = people.accounts["steward"], people.accounts["member"]
    with db.write(ME.actor) as session:
        record = find(session, SYSTEM, stock.monitor)
        for owners, message in [
            ([], "needs an owner"),
            ([{"account_id": member, "kind": "contact"}], "needs an owner"),
            ([{"account_id": me, "kind": "captain"}], "not a kind of owner"),
            ([{"account_id": 9999, "kind": "owner"}], "not disabled"),
        ]:
            with pytest.raises(Invalid) as caught:
                records.set_owners(session, steward, SYSTEM, record, owners)
            assert message in caught.value.errors["owners"]
        with pytest.raises(PermissionDenied):
            records.set_owners(
                session, who(db, people, "member"), SYSTEM, record,
                [{"account_id": member, "kind": "owner"}],
            )  # fmt: skip
        records.set_owners(
            session, steward, SYSTEM, record,
            [{"account_id": member, "kind": "owner"}, {"account_id": me, "kind": "delegate"}],
        )  # fmt: skip
        session.flush()
        shown = records.detail(session, steward, SYSTEM, record)
        assert [(o["account_id"], o["kind"]) for o in shown["owners"]] == [
            (member, "owner"), (me, "delegate"),
        ]  # fmt: skip
        # The lists narrow to what a person is named on.
        mine, _ = records.search(session, who(db, people, "member"), SYSTEM, {"mine": True})
        assert [row.ref for row in mine] == [stock.monitor]
        theirs, _ = records.search(session, steward, SYSTEM, {"owner": member})
        assert [row.ref for row in theirs] == [stock.monitor]
    # When the owner's account is disabled, the record has nobody answering for it.
    with db.write(ME.actor) as session:
        accounts.update(session, ME, accounts.get(session, member), {"status": "disabled"})
    with db.read() as session:
        record = find(session, SYSTEM, stock.monitor)
        assert records.detail(session, steward, SYSTEM, record)["orphaned"]
        rows, _ = records.search(session, steward, SYSTEM, {"q": "freezer"})
        assert records.cards(session, SYSTEM, rows)[0]["orphaned"]


# --- Links --------------------------------------------------------------------------------


def test_links_read_both_ways(db: Database, people: People, stock: Stock) -> None:
    steward, manager, member = (who(db, people, role) for role in ("steward", "manager", "member"))
    with db.write(ME.actor) as session:
        storage = find(session, PROCESS, stock.storage)
        monitor, lims = find(session, SYSTEM, stock.monitor), find(session, SYSTEM, stock.lims)
        sealed = find(session, SYSTEM, stock.sealed)
        supplier = find(session, THIRD_PARTY, stock.supplier)
        links.add(session, steward, PROCESS, storage, "relies_on", SYSTEM, monitor, note=" Alarms ")
        links.add(session, steward, PROCESS, storage, "relies_on", SYSTEM, sealed)
        links.add(session, steward, SYSTEM, monitor, "supplied_by", THIRD_PARTY, supplier)
        links.add(session, manager, SYSTEM, lims, "depends_on", SYSTEM, monitor)
        vault = find(session, SYSTEM, stock.vault)
        links.add(session, manager, SYSTEM, vault, "depends_on", SYSTEM, monitor)

        for args, field in [
            ((PROCESS, storage, "supplied_by", SYSTEM, monitor), "relation"),  # not that way
            ((SYSTEM, monitor, "relies_on", PROCESS, storage), "relation"),  # nor backwards
            ((PROCESS, storage, "relies_on", SYSTEM, monitor), "to"),  # already linked
            ((SYSTEM, monitor, "depends_on", SYSTEM, monitor), "to"),  # to itself
        ]:
            with pytest.raises(Invalid) as caught:
                links.add(session, steward, *args)
            assert field in caught.value.errors, args[2]
        with pytest.raises(PermissionDenied):
            links.add(session, member, PROCESS, storage, "relies_on", SYSTEM, lims)

        from_storage = links.of(session, steward, PROCESS, storage)
        assert [(e["label"], e["record"]["ref"], e["note"]) for e in from_storage["outgoing"]] == [
            ("Relies on", stock.monitor, "Alarms"), ("Relies on", stock.sealed, None),
        ]  # fmt: skip
        of_monitor = links.of(session, steward, SYSTEM, monitor)
        assert [(e["label"], e["record"]["ref"]) for e in of_monitor["outgoing"]] == [
            ("Supplied by", stock.supplier)
        ]
        # The system is also depended on by a restricted record in another division, which
        # the steward may not see: it is counted, and not shown.
        assert [(e["label"], e["record"]["ref"]) for e in of_monitor["incoming"]] == [
            ("Supports", stock.storage), ("Is depended on by", stock.lims),
        ]  # fmt: skip
        assert of_monitor["hidden"] == 1
        seen_by_manager = links.of(session, manager, SYSTEM, monitor)
        assert [e["record"]["ref"] for e in seen_by_manager["incoming"]] == [
            stock.storage, stock.lims, stock.vault,
        ]  # fmt: skip
        assert seen_by_manager["hidden"] == 0
        # A member of the lab sees the process and not the restricted system it relies on.
        for_member = links.of(session, member, PROCESS, storage)
        assert [e["record"]["ref"] for e in for_member["outgoing"]] == [stock.monitor]
        assert for_member["hidden"] == 1

        first = from_storage["outgoing"][0]["id"]
        with pytest.raises(NotFound):
            links.remove(session, steward, SYSTEM, sealed, first)  # not one of its links
        with pytest.raises(PermissionDenied):
            links.remove(session, member, PROCESS, storage, first)
        links.remove(session, steward, SYSTEM, monitor, first)  # from the other end
        session.flush()
        assert [e["record"]["ref"] for e in links.of(session, steward, PROCESS, storage)["outgoing"]
                ] == [stock.sealed]  # fmt: skip


# --- History ------------------------------------------------------------------------------


def test_the_history_reads_like_a_story(db: Database, people: People, stock: Stock) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        record = find(session, SYSTEM, stock.monitor)
        records.update(
            session, steward, SYSTEM, record,
            {"criticality": "high", "hosting": "on_premises", "org_unit_id": people.units["IMM"]},
            version=1,
        )  # fmt: skip
        records.update(session, steward, SYSTEM, record, {"lifecycle": "unsupported"}, version=2)
        records.set_owners(
            session, steward, SYSTEM, record,
            [{"account_id": people.accounts["steward"], "kind": "owner"},
             {"account_id": people.accounts["member"], "kind": "delegate"}],
        )  # fmt: skip
        links.add(
            session, steward, SYSTEM, record, "supplied_by",
            THIRD_PARTY, find(session, THIRD_PARTY, stock.supplier),
        )  # fmt: skip
    with db.read() as session:
        story = history.for_record(session, SYSTEM, find(session, SYSTEM, stock.monitor))
    assert [entry["title"] for entry in story] == [
        "Now supplied by TP-0001 Coldline Service",
        "Added Member Person as delegate",
        "Lifecycle changed",
        "Edited",
        "Added Steward Person as owner",
        "Added this system",
    ]
    assert story[0]["actor"] == "Steward Person"
    assert story[2]["lines"] == [
        {"field": "lifecycle", "label": "Lifecycle", "before": "In service", "after": "Unsupported"}
    ]
    edited = {line["label"]: (line["before"], line["after"]) for line in story[3]["lines"]}
    assert edited == {
        "Criticality": ("Moderate", "High"),
        "Hosting": (None, "On premises"),
        "Unit": ("Hale Lab", "Immunology"),
    }


# --- The API ------------------------------------------------------------------------------


def test_the_inventory_through_the_api(as_role: Clients, people: People, stock: Stock) -> None:
    steward, member, manager = as_role("steward"), as_role("member"), as_role("manager")
    hale = people.units["HALE"]

    vocabularies = member.get("/api/v1/vocabularies").json()["data"]
    assert {"criticalities", "data_classes", "system_kinds", "link_kinds"} <= set(vocabularies)

    created = steward.post(
        "/api/v1/systems",
        json={"name": "Imaging archive", "kind": "data_store", "org_unit_id": hale,
              "criticality": "high", "tags": ["Imaging", "imaging", " archive "]},
    )  # fmt: skip
    assert created.status_code == 201
    system = created.json()["data"]
    assert system["ref"] == "SYS-0005" and system["tags"] == ["imaging", "archive"]
    assert member.post("/api/v1/systems", json={"name": "x"}).status_code == 403
    refused = steward.post("/api/v1/systems", json={"name": "No kind", "org_unit_id": hale})
    assert refused.status_code == 422
    assert [e["location"] for e in refused.json()["errors"]] == [["kind"]]

    # Lists filter, sort, and page, and count what the person may see.
    page = steward.get("/api/v1/systems", params={"sort": "-criticality", "limit": 2}).json()
    assert page["meta"]["total"] == 4 and [r["ref"] for r in page["data"]] == [
        "SYS-0005", stock.lims,
    ]  # fmt: skip
    rest = steward.get(
        "/api/v1/systems",
        params={"sort": "-criticality", "limit": 2, "cursor": page["meta"]["next_cursor"]},
    ).json()
    assert [r["ref"] for r in rest["data"]] == [stock.sealed, stock.monitor]
    assert not rest["meta"]["next_cursor"]
    assert manager.get("/api/v1/systems").json()["meta"]["total"] == 5
    found = manager.get("/api/v1/systems", params={"q": "TRACK", "data_class": "restricted"})
    assert [r["ref"] for r in found.json()["data"]] == [stock.lims]
    in_division = manager.get("/api/v1/systems", params={"unit": people.units["IMM"]}).json()
    assert in_division["meta"]["total"] == 3
    assert steward.get("/api/v1/systems", params={"sort": "color"}).status_code == 422

    # A change says which version it was made against.
    path = f"/api/v1/systems/{stock.monitor}"
    assert steward.patch(path, json={"summary": "Probes"}).status_code == 409
    changed = steward.patch(path, json={"summary": "Probes", "version": 1})
    assert changed.status_code == 200 and changed.json()["data"]["version"] == 2
    assert steward.patch(path, json={"summary": "Again", "version": 1}).status_code == 409
    assert member.patch(path, json={"summary": "Mine", "version": 2}).status_code == 403
    # What a person may not see is, to them, not there.
    assert member.get(f"/api/v1/systems/{stock.vault}").status_code == 404
    assert steward.get(f"/api/v1/systems/{stock.vault}").status_code == 404
    assert steward.get(f"/api/v1/systems/{stock.lims}").json()["data"]["can"]["edit"] is False
    assert steward.get("/api/v1/systems/PRC-0001").status_code == 404

    owners = steward.put(
        f"{path}/owners",
        json={"owners": [{"account_id": people.accounts["member"], "kind": "owner"}]},
    )
    assert owners.status_code == 200
    assert [o["name"] for o in owners.json()["data"]["owners"]] == ["Member Person"]
    assert member.patch(path, json={"summary": "Mine", "version": 2}).status_code == 200

    linked = steward.post(
        f"/api/v1/processes/{stock.storage}/links",
        json={"relation": "relies_on", "to": stock.monitor, "note": "Alarms"},
    )
    assert linked.status_code == 201
    link = linked.json()["data"]["outgoing"][0]
    assert (link["label"], link["record"]["name"]) == ("Relies on", "Freezer monitoring")
    shown = member.get(path).json()["data"]
    assert [e["record"]["ref"] for e in shown["links"]["incoming"]] == [stock.storage]
    wrong = steward.post(
        f"/api/v1/processes/{stock.storage}/links", json={"relation": "relies_on", "to": "TP-0001"}
    )
    assert wrong.status_code == 422
    gone = steward.delete(f"/api/v1/processes/{stock.storage}/links/{link['id']}")
    assert gone.status_code == 200 and gone.json()["data"]["outgoing"] == []

    story = steward.get(f"/api/v1/processes/{stock.storage}/history").json()["data"]
    assert [entry["title"] for entry in story] == [
        "No longer relies on SYS-0001 Freezer monitoring",
        "Now relies on SYS-0001 Freezer monitoring",
        "Added Steward Person as owner",
        "Added this process",
    ]
    assert story[0]["operation"] == "unlink"

    # How much everyone sees is the program's to set.
    assert member.get("/api/v1/admin/visibility").status_code == 403
    assert manager.get("/api/v1/admin/visibility").json()["data"]["visibility"] == "unit"
    assert manager.put("/api/v1/admin/visibility", json={"visibility": "all"}).status_code == 422
    assert manager.put("/api/v1/admin/visibility", json={"visibility": "open"}).status_code == 200
    assert manager.get("/api/v1/admin/visibility").json()["data"]["visibility"] == "open"
    # The setting is about risks and controls; what is restricted stays restricted.
    assert member.get(f"/api/v1/systems/{stock.vault}").status_code == 404
