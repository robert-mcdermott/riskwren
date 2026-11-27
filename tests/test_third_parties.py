"""Third parties as a program: what each provides and touches, and its tier by the program's
rules, with the reasons shown and the person's judgment kept."""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.core import conditions
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import Information, System, ThirdParty, TierAssessment
from riskwren.inventory import completeness, history, links, records
from riskwren.inventory.registry import INFORMATION, PROCESS, SYSTEM, THIRD_PARTY
from riskwren.program import rules, settings, vocab
from riskwren.reporting import graph
from riskwren.thirdparty import tiering
from riskwren.thirdparty.services import SERVICE
from tests.people import People
from tests.test_risks import who

Clients = Callable[[str | None], TestClient]
PLAIN = {"information": "none", "access": ["no_access"], "dependency": "little"}


def thing(session: Any, principal: Any, record_type: Any, **values: Any) -> Any:
    base = {"kind": {"process": "research", "system": "application", "third_party":
                     "service_provider", "information": "participant_data",
                     "service": "software_service"}[record_type.key],
            "org_unit_id": values.pop("unit")}  # fmt: skip
    return records.create(session, principal, record_type, {**base, **values})


def supplier_with_a_service(db: Database, people: People) -> dict[str, str]:
    """A survey host: its service handles restricted participant data and reaches a system
    that a critical process relies on."""
    steward = who(db, people, "steward")
    imm = people.units["IMM"]
    with db.write(steward.actor) as session:
        host = thing(session, steward, THIRD_PARTY, name="Tallyfield Surveys", unit=imm,
                     criticality="moderate")  # fmt: skip
        service = thing(session, steward, SERVICE, name="Hosted participant surveys", unit=imm,
                        third_party=host.ref, data_class="confidential")  # fmt: skip
        data = thing(session, steward, INFORMATION, name="Cohort survey responses", unit=imm,
                     data_class="restricted")  # fmt: skip
        portal = thing(session, steward, SYSTEM, name="Survey portal", unit=imm,
                       criticality="high")  # fmt: skip
        follow_up = thing(session, steward, PROCESS, name="Cohort follow-up", unit=imm,
                          criticality="critical")  # fmt: skip
        links.add(session, steward, SERVICE, service, "handles", INFORMATION, data)
        links.add(session, steward, SERVICE, service, "reaches", SYSTEM, portal)
        links.add(session, steward, PROCESS, follow_up, "relies_on", SERVICE, service)
        return {"host": host.ref, "service": service.ref, "data": data.ref,
                "portal": portal.ref, "process": follow_up.ref}  # fmt: skip


# --- Services -----------------------------------------------------------------------------


def test_a_service_belongs_to_a_third_party_and_touches_systems_and_information(
    db: Database, people: People
) -> None:
    refs = supplier_with_a_service(db, people)
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        with pytest.raises(Invalid) as caught:
            thing(session, steward, SERVICE, name="Nobody's", unit=people.units["IMM"])
        assert "third_party" in caught.value.errors
        with pytest.raises(Invalid) as caught:
            thing(session, steward, SERVICE, name="Ghost", unit=people.units["IMM"],
                  third_party="TP-0999")  # fmt: skip
        assert "third_party" in caught.value.errors
        service = records.load(session, steward, SERVICE, refs["service"])
        assert service.ref.startswith("SVC-")
        shown = records.detail(session, steward, SERVICE, service)
        assert shown["third_party"]["ref"] == refs["host"]
        host = records.load(session, steward, THIRD_PARTY, refs["host"])
        detail = records.detail(session, steward, THIRD_PARTY, host)
        assert [row["ref"] for row in detail["services"]] == [refs["service"]]
        listed, total = records.search(session, steward, SERVICE, {"third_party": refs["host"]})
        assert total == 1 and listed[0].ref == refs["service"]
        # Both sides of every link, and the provider, in the picture of connections.
        found = links.of(session, steward, SERVICE, service)
        said = {(row["relation"], row["record"]["ref"]) for row in found["outgoing"]}
        assert said == {("handles", refs["data"]), ("reaches", refs["portal"])}
        groups = {g["key"]: g for g in graph.around(session, steward, SERVICE, service)["groups"]}
        assert [r["ref"] for r in groups["provided_by"]["records"]] == [refs["host"]]
        groups = {g["key"]: g for g in graph.around(session, steward, THIRD_PARTY, host)["groups"]}
        assert [r["ref"] for r in groups["provides"]["records"]] == [refs["service"]]
        # A service, like every thing, is expected to have an owner, a class, and links.
        assert {rule.key for rule in completeness.expected(SERVICE)} >= {"owner", "data_class"}


def test_a_kind_of_link_a_release_adds_reaches_an_installation_that_edited_its_kinds(
    db: Database, people: People
) -> None:
    with db.write(who(db, people, "manager").actor) as session:
        # Saved as an earlier release had them, with one renamed.
        old = [copy.deepcopy(item) for item in vocab.DEFAULTS["link_kinds"]
               if item["key"] not in ("reaches", "handles")]  # fmt: skip
        for item in old:
            item["between"] = [p for p in item["between"] if "service" not in p]
            if item["key"] == "relies_on":
                item["label"] = "Leans on"
        settings.put(session, "vocab.link_kinds", old)
        kinds = {item["key"]: item for item in vocab.get(session, "link_kinds")}
        assert kinds["relies_on"]["label"] == "Leans on"  # its own name stays
        assert ["process", "service"] in kinds["relies_on"]["between"]
        assert {"reaches", "handles"} <= set(kinds)
        assert links.kinds_between(session, "service", "system") == ["reaches"]


def test_services_through_the_api(as_role: Clients, people: People) -> None:
    steward, member = as_role("steward"), as_role("member")
    imm = people.units["IMM"]
    host = steward.post(
        "/api/v1/third-parties",
        json={"name": "Folio Bench", "kind": "service_provider", "org_unit_id": imm},
    ).json()["data"]
    made = steward.post("/api/v1/services", json={
        "name": "Electronic lab notebook", "kind": "software_service",
        "third_party": host["ref"], "data_class": "confidential"})  # fmt: skip
    assert made.status_code == 201, made.text
    service = made.json()["data"]
    assert service["org_unit_id"] == imm  # the third party's unit, unless another is said
    assert service["third_party"]["ref"] == host["ref"]
    refused = member.post(
        "/api/v1/services",
        json={"name": "Mine", "kind": "software_service", "third_party": host["ref"]},
    )
    assert refused.status_code == 403
    listed = member.get("/api/v1/services", params={"third_party": host["ref"]}).json()
    assert [row["ref"] for row in listed["data"]] == [service["ref"]]
    shown = member.get(f"/api/v1/third-parties/{host['ref']}").json()["data"]
    assert [row["ref"] for row in shown["services"]] == [service["ref"]]
    assert shown["tiering"] is None and shown["can_tier"] is False


# --- Tiering ------------------------------------------------------------------------------


def test_the_tier_recorded_is_the_rules_with_their_reasons_unless_the_person_says_why(
    db: Database, people: People
) -> None:
    refs = supplier_with_a_service(db, people)
    steward, member = who(db, people, "steward"), who(db, people, "member")
    with db.write(steward.actor) as session:
        host = records.load(session, steward, THIRD_PARTY, refs["host"])
        view = tiering.view(session, steward, host)
        # What the inventory says: restricted information through its service, critical
        # work relying on it, and a system it reaches.
        facts = view["facts"]
        assert facts["data_class"] == "restricted" and facts["data_class_from"] == [refs["data"]]
        assert facts["criticality"] == "critical" and facts["criticality_from"] == [refs["process"]]
        assert facts["systems"] == [refs["portal"]]
        assert facts["information_kinds"] == ["participant_data"]
        suggested = view["suggested_answers"]
        assert suggested == {"information": "restricted", "regulated": ["participant"],
                             "access": ["integration"], "dependency": "stops"}  # fmt: skip
        # The rules give Tier 1, with exactly the reasons of that tier that hold.
        listed = tiering.tiers(session)
        want_tier, want_reasons = None, []
        context = {"answers": suggested, "facts": facts}
        for tier in listed[:-1]:
            held = [r["reason"] for r in tier["rules"] if conditions.evaluate(r["when"], context)]
            if held:
                want_tier, want_reasons = tier["key"], held
                break
        assert want_tier == "tier_1" and len(want_reasons) == 3
        with pytest.raises(PermissionDenied):
            tiering.record(session, member, host, suggested, None, None)
        assert tiering.may_tier(session, who(db, people, "assessor"), host)  # an assessment
        made = tiering.record(session, steward, host, suggested, None, None)
        assert (made.tier, made.suggested, made.reasons) == ("tier_1", "tier_1", want_reasons)
        assert host.tier == "tier_1"
        # A different tier needs a reason; given one, both are kept.
        with pytest.raises(Invalid) as caught:
            tiering.record(session, steward, host, suggested, "tier_2", " ")
        assert "rationale" in caught.value.errors
        again = tiering.record(
            session,
            steward,
            host,
            suggested,
            "tier_2",
            "The surveys hold no names; the study codes them first.",
        )
        assert (again.tier, again.suggested) == ("tier_2", "tier_1")
        assert host.tier == "tier_2"
        rows = session.scalars(
            select(TierAssessment).where(TierAssessment.third_party_id == host.id)
            .order_by(TierAssessment.id)
        ).all()  # fmt: skip
        assert [row.superseded_by for row in rows] == [again.id, None]
        # Answers that hold nothing give the last tier, with that said.
        quiet = thing(session, steward, THIRD_PARTY, name="Brightway Cleaning",
                      unit=people.units["IMM"], criticality="low")  # fmt: skip
        plain = tiering.record(session, steward, quiet, PLAIN, None, None)
        assert (plain.tier, plain.reasons) == ("tier_4", [tiering.NOTHING_HOLDS])
        # Lists show, sort, and cut by tier; the history tells each tiering.
        cards = records.cards(session, THIRD_PARTY, [host, quiet])
        assert [card["tier"] for card in cards] == ["tier_2", "tier_4"]
        ordered, _ = records.search(session, steward, THIRD_PARTY, {}, sort="tier")
        assert [row.ref for row in ordered][:2] == [host.ref, quiet.ref]
        _, untiered = records.search(session, steward, THIRD_PARTY, {"tier": "none"})
        assert untiered == 0
        titles = [entry["title"] for entry in history.for_record(session, THIRD_PARTY, host)]
        assert titles[0].startswith("Tiered it: Tier 2, where the rules give Tier 1.")
        assert "Tiered it: Tier 1, as the rules give" in titles


def test_the_inventory_counts_only_what_is_in_use(db: Database, people: People) -> None:
    refs = supplier_with_a_service(db, people)
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        data = session.scalars(select(Information).where(Information.ref == refs["data"])).one()
        portal = session.scalars(select(System).where(System.ref == refs["portal"])).one()
        records.update(session, steward, INFORMATION, data, {"status": "retired"},
                       version=data.version)  # fmt: skip
        records.update(session, steward, SYSTEM, portal, {"status": "retired"},
                       version=portal.version)  # fmt: skip
        host = session.scalars(select(ThirdParty).where(ThirdParty.ref == refs["host"])).one()
        facts = tiering.facts(session, host)
        assert facts["data_class"] == "confidential"  # the service's own, now the highest
        assert facts["systems"] == [] and facts["information"] == []


def test_a_tiering_table_is_checked_before_it_is_used(db: Database, people: People) -> None:
    with db.write(who(db, people, "manager").actor) as session:
        table = rules.get(session, "tiering")
        assert tiering.problems(table) == []
        broken = copy.deepcopy(table)
        broken["tiers"][-1]["rules"] = broken["tiers"][0]["rules"]
        broken["tiers"][0]["rules"][0].pop("when")
        found = tiering.problems(broken)
        assert any("last tier has no rules" in each for each in found)
        assert any("condition" in each for each in found)


def test_the_tiers_travel_with_the_program(db: Database, people: People) -> None:
    from riskwren.program import packs

    manager = who(db, people, "manager")
    with db.write(manager.actor) as session:
        pack = packs.export(session)
        assert pack["tiering"]["tiers"][0]["key"] == "tier_1"
        pack["tiering"]["tiers"][0]["review_months"] = 6
        assert packs.import_(session, manager, pack)["changed"] == ["tiering"]
        assert tiering.tiers(session)[0]["review_months"] == 6
        pack["tiering"]["tiers"] = pack["tiering"]["tiers"][:1]
        with pytest.raises(Invalid):
            packs.import_(session, manager, pack)


def test_tiering_through_the_api(as_role: Clients, people: People) -> None:
    steward, member = as_role("steward"), as_role("member")
    imm = people.units["IMM"]
    host = steward.post("/api/v1/third-parties", json={
        "name": "Halden Research Partners", "kind": "contractor", "org_unit_id": imm,
        "criticality": "moderate"}).json()["data"]  # fmt: skip
    tiers = member.get("/api/v1/tiers").json()["data"]
    assert [tier["key"] for tier in tiers] == ["tier_1", "tier_2", "tier_3", "tier_4"]
    seen = member.get(f"/api/v1/third-parties/{host['ref']}/tiering").json()["data"]
    assert seen["can"]["tier"] is False and seen["tierings"] == []
    assert seen["questionnaire"]["key"] == "third-party-tiering"
    path = f"/api/v1/third-parties/{host['ref']}/tiering"
    refused = member.post(path, json={"answers": PLAIN})
    assert refused.status_code == 403
    missing = steward.post(path, json={"answers": {"information": "internal"}})
    assert missing.status_code == 422
    assert {tuple(e["location"]) for e in missing.json()["errors"]} == {
        ("access",),
        ("dependency",),
    }
    done = steward.post(
        path,
        json={
            "answers": {"information": "confidential", "access": ["on_site"], "dependency": "slows"}
        },
    )
    assert done.status_code == 201, done.text
    latest = done.json()["data"]["tierings"][0]
    assert (latest["tier"], latest["suggested"]) == ("tier_2", "tier_2")
    assert latest["reasons"] == ["It holds, receives, or can see confidential information."]
    assert latest["as_asked"][0]["questions"][0]["said"] == "Confidential"
    listed = member.get("/api/v1/third-parties", params={"tier": "tier_2"}).json()["data"]
    assert [row["ref"] for row in listed] == [host["ref"]]
