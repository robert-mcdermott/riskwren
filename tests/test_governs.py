"""Policies in the web of records: the controls a document directs, the requirements it
answers, and exceptions to a document."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from riskwren.compliance import exceptions, frameworks, packs
from riskwren.controls.service import CONTROL
from riskwren.core.clock import frozen_at
from riskwren.core.errors import Invalid, NotFound, PermissionDenied
from riskwren.db.engine import Database
from riskwren.inventory import completeness, find, records
from riskwren.policy import documents, governs
from riskwren.policy.documents import DOCUMENT
from riskwren.reporting import graph
from tests.conftest import TESTER
from tests.people import People
from tests.test_documents import publish
from tests.test_risks import who
from tests.test_treatment import add_control

Clients = Callable[[str | None], TestClient]
NOON = datetime(2026, 3, 2, 12, tzinfo=UTC)
LATER = datetime(2026, 7, 1, 12, tzinfo=UTC)


@pytest.fixture
def loaded(db: Database, people: People) -> None:
    with db.write(TESTER) as session:
        packs.install(session)


def groups(found: dict) -> dict[str, list[str]]:  # type: ignore[type-arg]
    return {group["key"]: [chip["ref"] for chip in group["records"]] for group in found["groups"]}


def test_a_requirement_shows_the_published_documents_that_answer_it(
    db: Database, loaded: None, people: People, as_role: Clients
) -> None:
    steward, leader, member = (who(db, people, role) for role in ("steward", "leader", "member"))
    imm = people.units["IMM"]
    with db.write(steward.actor) as session, frozen_at(NOON):
        policy = documents.create(
            session, steward,
            {"name": "Backup standard", "kind": "standard", "org_unit_id": imm,
             "body": "Every system is backed up each night, and a restore is tested each month."},
        )  # fmt: skip
        backups = add_control(session, steward, people.units["HALE"], "Nightly backups")
        restores = add_control(session, steward, imm, "Monthly restore test")
        retired = add_control(session, steward, imm, "Tape rotation")
        records.update(session, steward, CONTROL, retired, {"status": "retired"},
                       version=retired.version)  # fmt: skip

        # What it governs is said by those who keep the document.
        with pytest.raises(PermissionDenied):
            governs.direct(session, member, policy, backups.ref)
        made = governs.direct(session, steward, policy, backups.ref)
        again = governs.direct(session, steward, policy, backups.ref, "Research storage too.")
        assert again.id == made.id and again.note == "Research storage too."  # once, not twice
        governs.direct(session, steward, policy, restores.ref)
        with pytest.raises(Invalid) as bad:
            governs.direct(session, steward, policy, retired.ref)
        assert "retired" in bad.value.errors["control"]
        with pytest.raises(Invalid) as missing:
            governs.direct(session, steward, policy, "CTL-9999")
        assert set(missing.value.errors) == {"control"}
        answered = governs.answer(
            session, steward, policy, framework="nist-800-53", code="CP-9", note="In full."
        )
        with pytest.raises(Invalid) as heading:
            governs.answer(session, steward, policy, framework="nist-800-53", code="CP")
        assert "heading" in heading.value.errors["code"]

        # Each side shows the other: the document its controls and requirements, the control
        # the documents that direct it.
        shown = governs.of_document(session, steward, policy)
        assert [row["control"]["ref"] for row in shown["controls"]] == [backups.ref, restores.ref]
        assert [(group["key"], [r["code"] for r in group["requirements"]])
                for group in shown["frameworks"]] == [("nist-800-53", ["CP-9"])]  # fmt: skip
        assert shown["can_edit"] and not governs.of_document(session, member, policy)["can_edit"]
        directing = records.detail(session, member, CONTROL, backups)["directed_by"]
        assert [(row["ref"], row["number"]) for row in directing["documents"]] == [
            (policy.ref, None)
        ]  # not yet in force, and said so
        detail = records.detail(session, steward, DOCUMENT, policy)
        assert detail["governs"] == {"controls": 2, "requirements": 1}

        # A requirement shows only what is in force: nothing until it is published.
        requirement = frameworks.find(session, frameworks.by_key(session, "nist-800-53"), "CP-9")
        assert governs.of_requirement(session, member, requirement)["documents"] == []
        publish(session, steward, leader, policy)
        found = governs.of_requirement(session, member, requirement)["documents"]
        assert [(row["ref"], row["number"], row["note"]) for row in found] == [
            (policy.ref, 1, "In full.")
        ]

        # In the picture of connections, from both ends.
        around = groups(graph.around(session, steward, DOCUMENT, policy))
        assert around["directs"] == [backups.ref, restores.ref]
        assert groups(graph.around(session, steward, CONTROL, backups))["directed_by"] == [
            policy.ref
        ]
        # Taken off again, with the history saying so.
        governs.undirect(session, steward, policy, made.id)
        governs.unanswer(session, steward, policy, answered.id)
        assert governs.of_requirement(session, member, requirement)["documents"] == []
        with pytest.raises(NotFound):
            governs.undirect(session, steward, policy, made.id)
        ref = policy.ref
    titles = [
        entry["title"]
        for entry in as_role("steward").get(f"/api/v1/documents/{ref}/history").json()["data"]
    ]
    for said in (
        f"Directs {backups.ref} Nightly backups",
        "Answers CP-9 of NIST SP 800-53 Rev. 5",
        f"No longer directs {backups.ref} Nightly backups",
        "No longer answers CP-9 of NIST SP 800-53 Rev. 5",
    ):
        assert said in titles, (said, titles)

    # Through the API: from the document's side, and seen from the requirement's.
    client = as_role("steward")
    added = client.put(f"/api/v1/documents/{ref}/requirements",
                       json={"framework": "nist-800-53", "code": "CP-10"})  # fmt: skip
    assert added.status_code == 200, added.text
    assert added.json()["data"]["requirements"] == 1
    link = added.json()["data"]["frameworks"][0]["requirements"][0]["id"]
    seen = (
        as_role("member")
        .get("/api/v1/frameworks/nist-800-53/requirement", params={"code": "CP-10"})
        .json()["data"]
    )
    assert [row["ref"] for row in seen["documents"]] == [ref]
    refused = as_role("member").put(
        f"/api/v1/documents/{ref}/controls", json={"control": restores.ref}
    )
    assert refused.status_code == 403
    gone = client.delete(f"/api/v1/documents/{ref}/requirements/{link}")
    assert gone.json()["data"]["requirements"] == 0


def test_a_document_says_what_it_is_missing_and_is_found_by_search(
    db: Database, loaded: None, people: People
) -> None:
    steward, leader = who(db, people, "steward"), who(db, people, "leader")
    imm = people.units["IMM"]
    with db.write(steward.actor) as session, frozen_at(NOON):
        made = {
            kind: documents.create(
                session,
                steward,
                {
                    "name": f"Password {kind}",
                    "kind": kind,
                    "org_unit_id": imm,
                    "body": "Long ones.",
                },
            )
            for kind in ("policy", "guideline")
        }
        for document in made.values():
            publish(session, steward, leader, document)
        lacking, _ = records.search(session, steward, DOCUMENT, {"missing": "governs"})
        # A guideline is advice, and is not expected to govern anything.
        assert [row.name for row in lacking] == ["Password policy"]
        assert "governs" in [rule.key for rule in completeness.expected(DOCUMENT)]
        control = add_control(session, steward, imm, "Passwords are long")
        governs.direct(session, steward, made["policy"], control.ref)
        assert records.search(session, steward, DOCUMENT, {"missing": "governs"})[1] == 0
        hits = find.everywhere(session, steward, "password")
        found = next(group for group in hits["groups"] if group["type"] == "document")
        assert {item["ref"] for item in found["items"]} == {
            made["policy"].ref, made["guideline"].ref
        }  # fmt: skip
        rows, _ = records.search(session, steward, DOCUMENT, {})
        cards = records.cards(session, DOCUMENT, rows)
        assert {row["name"]: (row["controls"], row["requirements"]) for row in cards} == {
            "Password guideline": (0, 0), "Password policy": (1, 0),
        }  # fmt: skip


def test_an_exception_to_a_document_is_decided_by_its_keepers_and_ends_by_its_dates(
    db: Database, loaded: None, people: People, as_role: Clients
) -> None:
    manager, steward, leader, member = (
        who(db, people, role) for role in ("manager", "steward", "leader", "member")
    )
    cancer = people.units["CANCER"]
    with db.write(manager.actor) as session, frozen_at(NOON):
        standard = documents.create(
            session, manager,
            {"name": "Encryption standard", "kind": "standard", "org_unit_id": cancer,
             "body": "Laptops are encrypted."},
        )  # fmt: skip
        ask = {
            "document": standard.ref,
            "justification": "The microscope PC cannot be encrypted.",
            "compensating": "It never leaves the locked room.",
            "expires_on": "2026-05-31",
        }
        with pytest.raises(Invalid) as early:  # nothing in force to depart from
            exceptions.request(session, steward, ask)
        assert set(early.value.errors) == {"document"}
        publish(session, manager, who(db, people, "admin"), standard)
        with pytest.raises(PermissionDenied):  # a member asks their steward
            exceptions.request(session, member, ask)
        # The Immunology steward asks; the Immunology leader has no say over Cancer Biology's
        # standard, and whoever asked does not decide.
        made = exceptions.request(session, steward, ask)
        assert (made.subject_type, made.org_unit_id, made.name) == (
            "document",
            cancer,
            "Encryption standard",
        )
        assert exceptions.state_of(made) == "requested"
        with pytest.raises(PermissionDenied):
            exceptions.decide(session, leader, made, approve=True, note=None)
        exceptions.decide(session, manager, made, approve=True, note="Until the new PC comes.")
        assert exceptions.state_of(made) == "in_force"
        shown = records.detail(session, manager, DOCUMENT, standard)
        assert [(row["ref"], row["state"]) for row in shown["exceptions"]] == [
            (made.ref, "in_force")
        ]
        assert exceptions.subject_of(session, steward, made)["ref"] == standard.ref
        assert groups(graph.around(session, manager, DOCUMENT, standard))["exceptions"] == [
            made.ref
        ]
        listed, _ = records.search(
            session, manager, exceptions.EXCEPTION, {"document": standard.ref}
        )
        assert [row.ref for row in listed] == [made.ref]
        ref = made.ref
    # It ends by its dates, with nobody doing anything.
    with db.write(manager.actor) as session, frozen_at(LATER):
        item = records.load(session, manager, exceptions.EXCEPTION, ref)
        assert exceptions.state_of(item) == "expired"
        assert records.detail(session, manager, DOCUMENT, standard)["exceptions"][0]["state"] == (
            "expired"
        )
        # Carrying on is a new request, about the same document.
        renewed = exceptions.request(
            session, steward, {"renews": ref, "justification": "The PC is late.",
                               "expires_on": "2026-09-30"},
        )  # fmt: skip
        assert (renewed.subject_type, renewed.subject_id) == ("document", standard.id)
    # Through the API, as the form sends it.
    client = as_role("steward")
    sent = client.post(
        "/api/v1/exceptions",
        json={"document": standard.ref, "justification": "Another one.",
              "expires_on": "2026-12-31"},
    )  # fmt: skip
    assert sent.status_code == 201, sent.text
    assert sent.json()["data"]["subject"]["ref"] == standard.ref
