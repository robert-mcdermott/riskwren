"""Agreements: what the organization has promised others, what each covers, the requirements
it imposes on the scopes that hold what it covers, and the warnings before it ends."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren import reminders
from riskwren.compliance import agreements, frameworks, packs, scopes
from riskwren.compliance.agreements import AGREEMENT
from riskwren.compliance.scopes import SCOPE
from riskwren.core.clock import frozen_at
from riskwren.core.errors import Conflict, Invalid, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import Notice, ScopeRequirement
from riskwren.inventory import find, history, records
from riskwren.inventory.registry import INFORMATION, SYSTEM
from riskwren.reporting import graph
from riskwren.reporting import service as reporting
from tests.conftest import TESTER
from tests.people import People
from tests.test_risks import who

Clients = Callable[[str | None], TestClient]
NOON = datetime(2026, 3, 2, 12, tzinfo=UTC)
TERMS = """\
DUA-1 The data are used only for the approved study.
DUA-2 The data are encrypted wherever they are stored.
DUA-3 Any loss of the data is reported within seventy-two hours.
"""


@pytest.fixture
def loaded(db: Database, people: People) -> None:
    with db.write(TESTER) as session:
        packs.install(session)


def held(session, scope) -> list[tuple[str, str | None]]:  # type: ignore[no-untyped-def]
    return [
        (row["key"], row["agreement"] and row["agreement"]["ref"])
        for row in scopes.held_to(session, scope)
    ]


def test_an_agreement_has_parties_dates_and_a_notice_date(db: Database, people: People) -> None:
    steward, member = who(db, people, "steward"), who(db, people, "member")
    imm = people.units["IMM"]
    with db.write(steward.actor) as session, frozen_at(NOON):
        base = {"name": "Cohort data", "kind": "data_use", "parties": "Open Cohort Trust",
                "org_unit_id": imm}  # fmt: skip
        for wrong, field in [
            ({"kind": "promise"}, "kind"),
            ({"parties": " "}, "parties"),
            ({"starts_on": "2026-05-01", "ends_on": "2026-04-01"}, "ends_on"),
            ({"notice_days": 30}, "notice_days"),  # notice is counted back from an end
            ({"ends_on": "2027-01-01", "notice_days": 9999}, "notice_days"),
            ({"framework": "no-such-thing"}, "framework"),
        ]:
            with pytest.raises(Invalid) as caught:
                records.create(session, steward, AGREEMENT, {**base, **wrong})
            assert field in caught.value.errors, (wrong, caught.value.errors)
        with pytest.raises(PermissionDenied):
            records.create(session, member, AGREEMENT, base)
        made = records.create(
            session, steward, AGREEMENT,
            {**base, "reference": "OCT-DUA-0417", "starts_on": "2025-03-01",
             "ends_on": "2026-06-30", "notice_days": 90, "renews": True},
        )  # fmt: skip
        assert made.ref == "AGR-0001"
        assert agreements.notice_on(made) == date(2026, 4, 1)
        assert agreements.state_of(made) == "notice"  # within 30 days of its notice date
        assert agreements.state_of(made, date(2026, 1, 5)) == "in_force"
        assert agreements.state_of(made, date(2026, 5, 15)) == "ending"
        assert agreements.state_of(made, date(2026, 7, 1)) == "ended"
        assert agreements.state_of(made, date(2025, 1, 1)) == "upcoming"
        card = records.cards(session, AGREEMENT, [made])[0]
        assert (card["state"], card["notice_on"], card["covers"]) == ("notice", date(2026, 4, 1), 0)
        # It is expected to say what it covers.
        assert [each["key"] for each in card["missing"]] == ["covers"]
        found = find.everywhere(session, steward, "cohort")
        assert any(group["type"] == "agreement" for group in found["groups"])


def test_what_an_agreement_imposes_is_held_by_every_scope_that_holds_what_it_covers(
    db: Database, loaded: None, people: People, as_role: Clients
) -> None:
    manager, steward = who(db, people, "manager"), who(db, people, "steward")
    hale, imm = people.units["HALE"], people.units["IMM"]
    with db.write(manager.actor) as session, frozen_at(NOON):
        terms = frameworks.create(
            session,
            manager,
            {"title": "Data use agreement: Open Cohort Trust", "kind": "agreement"},
        )
        frameworks.paste(session, manager, terms, TERMS, dry_run=False)
        store = records.create(
            session,
            steward,
            SYSTEM,
            {"name": "Enclave storage", "kind": "platform", "org_unit_id": hale},
        )
        cohort = records.create(
            session,
            steward,
            INFORMATION,
            {"name": "Cohort data", "kind": "participant_data", "org_unit_id": hale},
        )
        enclave = records.create(
            session, steward, SCOPE, {"name": "The enclave", "org_unit_id": hale}
        )
        clinic = records.create(session, steward, SCOPE, {"name": "The clinic", "org_unit_id": imm})
        elsewhere = records.create(
            session, steward, SCOPE, {"name": "Elsewhere", "org_unit_id": imm}
        )
        scopes.set_members(session, steward, enclave, [store.ref, cohort.ref], [])
        scopes.hold_to(session, steward, enclave, "nist-800-171", None)
        agreement = records.create(
            session, steward, AGREEMENT,
            {"name": "Cohort data use", "kind": "data_use", "parties": "Open Cohort Trust",
             "org_unit_id": hale, "ends_on": "2027-02-28", "framework": terms.key},
        )  # fmt: skip
        # Covering the information puts its terms in the scope that holds it, and says why.
        agreements.set_coverage(session, steward, agreement, [cohort.ref])
        assert held(session, enclave) == [
            (terms.key, agreement.ref), ("nist-800-171", None),
        ]  # fmt: skip
        assert held(session, clinic) == [] and held(session, elsewhere) == []
        # A scope it covers directly holds them too; so does a scope that comes to hold
        # what it covers.
        agreements.set_coverage(session, steward, agreement, [cohort.ref, clinic.ref])
        assert held(session, clinic) == [(terms.key, agreement.ref)]
        scopes.set_members(session, steward, elsewhere, [store.ref], [])
        assert held(session, elsewhere) == []  # it covers the information, not the system
        scopes.set_members(session, steward, elsewhere, [cohort.ref], [])
        assert held(session, elsewhere) == [(terms.key, agreement.ref)]
        # The requirements are there to answer, like any others.
        statement = scopes.statement(session, steward, enclave, terms.key)
        assert [row["code"] for row in statement["requirements"]] == ["DUA-1", "DUA-2", "DUA-3"]
        # A scope's keepers cannot drop what an agreement imposes; they can hold it themselves.
        with pytest.raises(Conflict) as kept:
            scopes.release_from(session, steward, clinic, terms.key)
        assert agreement.ref in str(kept.value)
        scopes.hold_to(session, steward, clinic, terms.key, None)
        scopes.decide(
            session, steward, enclave, framework=terms.key, code="DUA-3", applicable=False,
            reason="Reported through the trust's own portal.",
        )  # fmt: skip
        # Covering less, or closing it, takes the terms away, with what was decided about them;
        # a scope that holds them by its own decision keeps them.
        agreements.set_coverage(session, steward, agreement, [clinic.ref])
        assert held(session, enclave) == [("nist-800-171", None)]
        assert held(session, elsewhere) == []
        assert (
            session.scalars(
                select(ScopeRequirement).where(ScopeRequirement.scope_id == enclave.id)
            ).all()
            == []
        )
        with pytest.raises(Invalid):
            agreements.close(session, steward, agreement, " ")
        agreements.close(session, steward, agreement, "Replaced by the 2027 agreement.")
        assert held(session, clinic) == [(terms.key, None)]  # held by its own decision
        assert agreements.state_of(agreement) == "closed"
        with pytest.raises(Conflict):
            agreements.set_coverage(session, steward, agreement, [cohort.ref])
        agreements.reopen(session, steward, agreement)
        agreements.set_coverage(session, steward, agreement, [cohort.ref])
        assert held(session, enclave) == [(terms.key, agreement.ref), ("nist-800-171", None)]
        # The history of each says so.
        told = [entry["title"] for entry in history.for_record(session, SCOPE, enclave)]
        assert f"Held to {terms.title}, because {agreement.ref} covers what it holds" in told
        assert (
            f"No longer held to {terms.title}: {agreement.ref} no longer covers what it holds"
            in told
        )
        said = [entry["title"] for entry in history.for_record(session, AGREEMENT, agreement)]
        assert f"Now covers {cohort.ref} Cohort data" in said
        assert "Closed it: Replaced by the 2027 agreement." in said
        # In the connections picture, both ways.
        around = graph.around(session, steward, AGREEMENT, agreement)
        assert [g["key"] for g in around["groups"]] == ["agreement_covers"]
        back = graph.around(session, steward, INFORMATION, cohort)
        assert "covered_by" in [g["key"] for g in back["groups"]]
        ref, cohort_ref = agreement.ref, cohort.ref
    # Through the API.
    client = as_role("steward")
    shown = client.get(f"/api/v1/agreements/{ref}").json()["data"]
    assert [each["ref"] for each in shown["covered"]["records"]] == [cohort_ref]
    assert shown["terms"]["requirements"] == 3
    assert [(each["name"], each["because"]) for each in shown["scopes"]] == [
        ("Elsewhere", True), ("The enclave", True),
    ]  # fmt: skip
    changed = client.put(f"/api/v1/agreements/{ref}/covers", json={"covers": ["RSK-0001"]})
    assert changed.status_code == 422
    listed = client.get("/api/v1/agreements", params={"covers": cohort_ref}).json()["data"]
    assert [row["ref"] for row in listed] == [ref]
    assert as_role("member").patch(
        f"/api/v1/agreements/{ref}", json={"version": shown["version"], "name": "x"}
    ).status_code in (403, 404)


def test_its_owners_are_warned_before_its_notice_date_and_before_it_ends(
    db: Database, people: People
) -> None:
    steward, leader = who(db, people, "steward"), who(db, people, "leader")
    imm = people.units["IMM"]
    with db.write(steward.actor) as session, frozen_at(NOON):
        made = records.create(
            session, steward, AGREEMENT,
            {"name": "Freezer service", "kind": "contract", "parties": "Coldline Services",
             "org_unit_id": imm, "ends_on": "2026-06-30", "notice_days": 60},
        )  # fmt: skip
        ref = made.ref
        # The notice date is 1 May: thirty days ahead, its owner is told, and it is on Home.
        sent = reminders.send(session, today=date(2026, 3, 30))
        assert sent["reminders"] == 0
    with db.write(steward.actor) as session, frozen_at(datetime(2026, 4, 2, 12, tzinfo=UTC)):
        sent = reminders.send(session, today=date(2026, 4, 2))
        assert sent["reminders"] == 1
        home = [
            (item["kind"], item["title"])
            for item in reporting.home(session, steward)["items"]
            if item.get("ref") == ref
        ]
        assert home == [("agreement_notice", "Give notice, or let it carry on: Freezer service")]
    with db.write(steward.actor) as session, frozen_at(datetime(2026, 5, 4, 12, tzinfo=UTC)):
        # Sixty days before it ends, it is said again; once it has ended and is still open, it
        # goes to the unit's steward and then its leader, as anything else left late does.
        sent = reminders.send(session, today=date(2026, 5, 4))
        assert sent["reminders"] == 1
        told = session.scalars(
            select(Notice.text).where(Notice.account_id == steward.account_id).order_by(Notice.id)
        ).all()
        assert told[-1].startswith("Due in ") and f"the end of {ref} Freezer service" in told[-1]
    with db.write(steward.actor) as session, frozen_at(datetime(2026, 7, 30, 12, tzinfo=UTC)):
        sent = reminders.send(session, today=date(2026, 7, 30))
        assert sent["escalated"] >= 1
        told = session.scalars(
            select(Notice.text).where(Notice.account_id == leader.account_id)
        ).all()
        assert any("Ended, and still open" in text and ref in text for text in told)
        assert [
            item["title"]
            for item in reporting.home(session, steward)["items"]
            if item.get("ref") == ref
        ] == ["Close or renew Freezer service"]
