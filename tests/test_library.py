"""The library and acknowledgment: who a document applies to, what each person may read, and
who has said they read it."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.core.clock import frozen_at
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import CampaignItem, Notice, PolicyDocument
from riskwren.inventory import records
from riskwren.oversight import campaigns
from riskwren.policy import documents, library
from riskwren.policy.documents import DOCUMENT
from riskwren.reporting import service as reporting
from tests.people import People
from tests.test_documents import publish
from tests.test_risks import who

Clients = Callable[[str | None], TestClient]
NOON = datetime(2026, 3, 2, 12, tzinfo=UTC)
AUP = (
    "# Acceptable use\n\n## You may\n\nUse the systems for your work.\n\n"
    "## You must not\n\nShare your account."
)


def names(rows) -> list[str]:  # type: ignore[no-untyped-def]
    return sorted(row["name"] for row in rows)


def test_a_document_applies_to_everyone_or_to_chosen_units_and_roles(
    db: Database, people: People
) -> None:
    steward, member, auditor = (who(db, people, role) for role in ("steward", "member", "auditor"))
    imm, cancer = people.units["IMM"], people.units["CANCER"]
    with db.write(steward.actor) as session, frozen_at(NOON):
        aup = documents.create(
            session,
            steward,
            {"name": "Acceptable use policy", "kind": "policy", "org_unit_id": imm},
        )
        assert library.audience_of(session, aup) == {"everyone": True, "units": [], "roles": []}
        assert len(library.people(session, aup)) == 7 and library.applies(session, aup, auditor)
        for everyone, unit_ids, chosen, field in [
            (False, [], [], "units"),
            (False, [9999], [], "units"),
            (False, [], ["member"], "roles"),  # everyone is a member; say everyone instead
        ]:
            with pytest.raises(Invalid) as caught:
                library.set_audience(session, steward, aup, everyone, unit_ids, chosen)
            assert set(caught.value.errors) == {field}
        with pytest.raises(PermissionDenied):
            library.set_audience(session, member, aup, True, [], [])
        # Immunology and the units beneath it, and every steward wherever they are.
        library.set_audience(session, steward, aup, False, [imm], ["steward"])
        assert names({"name": person.display_name} for person in library.people(session, aup)) == [
            "Member Person",
            "Steward Person",
        ]  # the member works in the Hale Lab
        assert library.applies(session, aup, member) and library.applies(session, aup, steward)
        assert not library.applies(session, aup, auditor)
        library.set_audience(session, steward, aup, False, [cancer], [])
        assert library.people(session, aup) == []
        library.set_audience(session, steward, aup, True, [imm], [])  # everyone wins
        assert library.audience_of(session, aup)["everyone"] is True


def test_who_has_acknowledged_is_exactly_those_it_applies_to(
    db: Database, people: People, as_role: Clients
) -> None:
    steward, leader, member = (who(db, people, role) for role in ("steward", "leader", "member"))
    auditor = who(db, people, "auditor")
    imm = people.units["IMM"]
    with db.write(steward.actor) as session, frozen_at(NOON):
        aup = documents.create(
            session, steward,
            {"name": "Acceptable use policy", "kind": "policy", "org_unit_id": imm, "body": AUP,
             "acknowledge": True},
        )  # fmt: skip
        library.set_audience(session, steward, aup, False, [imm], ["steward"])
        assert library.required(session, aup) is None  # nothing published, nothing to say
        first = publish(session, steward, leader, aup)
        assert library.required(session, aup).id == first.id  # type: ignore[union-attr]
        found = library.standing(session, aup)
        assert (found["people"], found["acknowledged"], found["outstanding"]) == (2, 0, 2)
        with pytest.raises(Conflict):  # it does not apply to the auditor
            library.acknowledge(session, auditor, aup)
        library.acknowledge(session, member, aup)
        library.acknowledge(session, member, aup)  # said once
        found = library.standing(session, aup)
        assert [(row["name"], row["acknowledged"], row["version"]) for row in found["rows"]] == [
            ("Steward Person", False, None), ("Member Person", True, 1),
        ]  # fmt: skip
        assert {row["unit"]["name"]: (row["people"], row["acknowledged"])
                for row in found["by_unit"]} == {"Hale Lab": (1, 1), "No unit": (1, 0)}  # fmt: skip

        # A new version that does not ask again: what was said still counts.
        documents.start_draft(session, steward, aup)
        documents.save_draft(
            session, steward, aup,
            {"body": AUP + "\n\nA typo fixed.", "change_note": "A typo.", "ask_again": False},
        )  # fmt: skip
        publish(session, steward, leader, aup)
        assert library.required(session, aup).id == first.id  # type: ignore[union-attr]
        assert library.standing(session, aup)["acknowledged"] == 1
        # One that does: everyone is asked again, and told.
        documents.start_draft(session, steward, aup)
        documents.save_draft(
            session, steward, aup,
            {"body": AUP + "\n\nNo personal email.", "change_note": "No personal email."},
        )  # fmt: skip
        third = publish(session, steward, leader, aup)
        assert library.required(session, aup).id == third.id  # type: ignore[union-attr]
        assert library.standing(session, aup)["acknowledged"] == 0
        told = session.scalars(
            select(Notice.text).where(Notice.account_id == member.account_id).order_by(Notice.id)
        ).all()
        assert told[-1] == (
            "Version 3 of Acceptable use policy is published. "
            "Please read it and say you have again."
        )
        ref = aup.ref
    # Through the API: the member reads it in the library and acknowledges it.
    client = as_role("member")
    listed = client.get("/api/v1/library").json()["data"]
    assert [(row["ref"], row["acknowledge"], row["acknowledged"]) for row in listed] == [
        (ref, True, False)
    ]
    reading = client.get(f"/api/v1/library/{ref}").json()["data"]
    assert reading["version"]["number"] == 3 and "No personal email" in reading["version"]["body"]
    done = client.post(f"/api/v1/library/{ref}/acknowledge").json()["data"]
    assert done["acknowledged"] is True and done["acknowledged_version"] == 3
    assert as_role("member").get(f"/api/v1/documents/{ref}/acknowledgments").status_code == 403
    standing = as_role("auditor").get(f"/api/v1/documents/{ref}/acknowledgments").json()["data"]
    assert (standing["people"], standing["acknowledged"]) == (2, 1)


def test_the_library_is_what_applies_to_the_reader(db: Database, people: People) -> None:
    steward, leader, member = (who(db, people, role) for role in ("steward", "leader", "member"))
    imm, cancer = people.units["IMM"], people.units["CANCER"]
    with db.write(steward.actor) as session, frozen_at(NOON):
        made = {}
        for name, kind, unit, body, audience in [
            ("Information security policy", "policy", imm, "Protect what we hold.", None),
            ("Freezer procedure", "procedure", imm, "Answer the **alarm** within ten minutes.",
             [imm]),
            ("Clinic procedure", "procedure", imm, "Wash your hands.", [cancer]),
            ("Unpublished guideline", "guideline", imm, "Not yet.", None),
        ]:  # fmt: skip
            document = documents.create(
                session, steward, {"name": name, "kind": kind, "org_unit_id": unit, "body": body}
            )
            if audience:
                library.set_audience(session, steward, document, False, audience, [])
            if name != "Unpublished guideline":
                publish(session, steward, leader, document)
            made[name] = document
        secret = documents.create(
            session, who(db, people, "manager"),
            {"name": "Key ceremony procedure", "kind": "procedure", "org_unit_id": cancer,
             "body": "Two people, always.", "restricted": True},
        )  # fmt: skip
        session.flush()
        mine = library.library(session, member)
        assert [row["name"] for row in mine] == ["Information security policy", "Freezer procedure"]
        assert [row["name"] for row in library.library(session, member, words="alarm")] == [
            "Freezer procedure"  # found in its text
        ]
        everything = library.library(session, member, everything=True)
        assert [row["name"] for row in everything] == [
            "Information security policy", "Clinic procedure", "Freezer procedure",
        ]  # fmt: skip
        assert secret.ref not in [row["ref"] for row in everything]
        with pytest.raises(NotFound):  # nothing published, nothing to read
            library.reading(session, member, made["Unpublished guideline"])
        shown = library.reading(session, member, made["Freezer procedure"])
        assert shown["parent"] is None and shown["acknowledge"] is False


def test_a_campaign_asks_those_who_have_not_acknowledged(
    db: Database, people: People, as_role: Clients
) -> None:
    steward, leader, member, manager = (
        who(db, people, role) for role in ("steward", "leader", "member", "manager")
    )
    imm = people.units["IMM"]
    with db.write(steward.actor) as session, frozen_at(NOON):
        aup = documents.create(
            session, steward,
            {"name": "Acceptable use policy", "kind": "policy", "org_unit_id": imm, "body": AUP},
        )  # fmt: skip
        publish(session, steward, leader, aup)
        ask = {"kind": "acknowledgment", "name": "Acceptable use, 2026", "due_on": "2026-04-01",
               "document": aup.ref}  # fmt: skip
        with pytest.raises(Invalid) as caught:  # it does not ask anyone to acknowledge it
            campaigns.launch(session, manager, ask)
        assert set(caught.value.errors) == {"document"}
        records.update(session, steward, DOCUMENT, aup, {"acknowledge": True}, version=aup.version)
        library.set_audience(session, steward, aup, False, [imm], ["steward", "leader"])
        library.acknowledge(session, steward, aup)  # before anyone asked
        assert campaigns.preview(session, manager, ask)["people"] == 3
        campaign = campaigns.launch(session, manager, ask)
        items = {
            item.account_name: item
            for item in session.scalars(
                select(CampaignItem).where(CampaignItem.campaign_id == campaign.id)
            )
        }
        assert {name: item.status for name, item in items.items()} == {
            "Steward Person": "done", "Member Person": "pending", "Leader Person": "pending",
        }  # fmt: skip
        assert items["Member Person"].subject_ref == aup.ref
        # On the member's Home once: the campaign, with its date, and no second item for it.
        home = [
            (item["kind"], item["title"], item["href"])
            for item in reporting.home(session, member)["items"]
            if item.get("ref") in (aup.ref, campaign.ref)
        ]
        assert home == [
            ("campaign", f"Read and acknowledge {aup.ref} Acceptable use policy",
             f"/library/{aup.ref}"),
        ]  # fmt: skip
        with pytest.raises(Conflict):  # it is answered by acknowledging, not with answers
            campaigns.answer(session, member, items["Member Person"], campaign, {})
        library.acknowledge(session, member, aup)
        assert items["Member Person"].status == "done"
        shown = campaigns.view(session, manager, campaign)
        assert shown["document"] == {"ref": aup.ref, "name": "Acceptable use policy"}
        assert shown["counts"]["done"] == 2 and shown["counts"]["pending"] == 1
        # Without a campaign, what someone must acknowledge is on their Home all the same.
        campaigns.end(session, manager, campaign)
        assert [
            item["kind"]
            for item in reporting.home(session, leader)["items"]
            if item.get("ref") == aup.ref
        ] == ["acknowledge"]
    asked = as_role("manager").post(
        "/api/v1/campaigns/preview",
        json={"kind": "acknowledgment", "name": "x", "due_on": "2026-12-01", "document": aup.ref},
    )
    assert asked.status_code == 200, asked.text
    assert PolicyDocument is not None
