"""Policy documents: what they are, how a version is approved and published, how a document
is reviewed, and that what was published stays what it was."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from riskwren import reminders
from riskwren.core.clock import frozen_at
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import Notice, PolicyDocument, PolicyVersion
from riskwren.inventory import history, records
from riskwren.people import accounts
from riskwren.policy import compare, documents
from riskwren.policy.documents import DOCUMENT
from riskwren.reporting import service as reporting
from tests.people import ME, People
from tests.test_risks import who

Clients = Callable[[str | None], TestClient]
NOON = datetime(2026, 3, 2, 12, tzinfo=UTC)

POLICY = """# Information security policy

## Purpose

Northmere protects the information it holds.

## Who it applies to

Everyone who works here, and everyone who uses our systems.

## Rules

- Accounts are personal.
- Restricted data is kept only in approved systems.
"""


def at(day: str) -> datetime:
    return datetime.fromisoformat(day).replace(hour=12, tzinfo=UTC)


def told(db: Database, account_id: int) -> list[str]:
    with db.read() as session:
        rows = session.scalars(
            select(Notice).where(Notice.account_id == account_id).order_by(Notice.id)
        )
        return [row.text for row in rows]


def publish(session, by, approver, document, approvers=None):  # type: ignore[no-untyped-def]
    """Send the draft, approve it as everyone named, and publish it."""
    documents.submit(session, by, document, approvers or [approver.account_id])
    documents.decide(session, approver, document, "approved", None)
    return documents.publish(session, by, document)


# --- What a document is ---------------------------------------------------------------------


def test_documents_are_arranged_by_what_they_implement(db: Database, people: People) -> None:
    steward, leader, member = (who(db, people, role) for role in ("steward", "leader", "member"))
    imm, hale, cancer = people.units["IMM"], people.units["HALE"], people.units["CANCER"]
    with db.write(steward.actor) as session, frozen_at(NOON):
        with pytest.raises(PermissionDenied):
            documents.create(
                session, member, {"name": "Mine", "kind": "policy", "org_unit_id": hale}
            )
        with pytest.raises(PermissionDenied):  # a leader adds for their own units only
            documents.create(
                session, leader, {"name": "Theirs", "kind": "policy", "org_unit_id": cancer}
            )
        policy = documents.create(
            session, leader,
            {"name": "Information security policy", "kind": "policy", "org_unit_id": imm,
             "body": POLICY},
        )  # fmt: skip
        assert (policy.ref, policy.kind, policy.status) == ("POL-0001", "policy", "active")
        standard = documents.create(
            session, steward,
            {"name": "Password standard", "kind": "standard", "org_unit_id": hale,
             "parent": policy.ref},
        )  # fmt: skip
        procedure = documents.create(
            session, steward,
            {"name": "Resetting a password", "kind": "procedure", "org_unit_id": hale,
             "parent": standard.ref},
        )  # fmt: skip
        for values, field in [
            ({"name": "x", "kind": "rule", "org_unit_id": hale}, "kind"),
            ({"name": "x", "kind": "policy", "org_unit_id": hale, "parent": procedure.ref},
             "parent"),  # a policy does not implement a procedure
            ({"name": "x", "kind": "standard", "org_unit_id": hale, "parent": "POL-0999"},
             "parent"),
            ({"name": "x", "kind": "policy", "org_unit_id": hale, "review_months": 0},
             "review_months"),
        ]:  # fmt: skip
            with pytest.raises(Invalid) as caught:
                documents.create(session, steward, values)
            assert set(caught.value.errors) == {field}, values
        # A policy may sit under a broader policy, but never under itself or what is beneath it.
        sub = documents.create(
            session, leader,
            {"name": "Access control policy", "kind": "policy", "org_unit_id": imm,
             "parent": policy.ref},
        )  # fmt: skip
        with pytest.raises(Invalid):
            records.update(session, leader, DOCUMENT, policy, {"parent": sub.ref},
                           version=policy.version)  # fmt: skip
        with pytest.raises(Invalid):  # a standard cannot become a guideline over a procedure
            records.update(session, steward, DOCUMENT, standard, {"kind": "guideline"},
                           version=standard.version)  # fmt: skip
        shown = records.detail(session, member, DOCUMENT, policy)
        assert [each["ref"] for each in shown["children"]] == [sub.ref, standard.ref]
        assert shown["published"] is None and shown["working"] is None  # not the member's
        assert shown["working_status"] == "draft" and not shown["can"]["edit"]
        mine = records.detail(session, leader, DOCUMENT, policy)
        assert mine["working"]["body"].startswith("# Information security policy")
        assert mine["can"]["edit"] and not mine["can"]["draft"]  # a draft is already open
        # What a document is missing: nothing is published, and nothing shows what it governs;
        # what it implements, the procedure says.
        cards = {
            card["ref"]: card for card in records.cards(session, DOCUMENT, [standard, procedure])
        }
        assert [each["key"] for each in cards[procedure.ref]["missing"]] == ["published", "governs"]


# --- Approval and publishing ------------------------------------------------------------------


def test_a_draft_is_published_only_once_everyone_named_has_approved_it(
    db: Database, people: People
) -> None:
    steward, leader, manager, member = (
        who(db, people, role) for role in ("steward", "leader", "manager", "member")
    )
    imm = people.units["IMM"]
    with db.write(steward.actor) as session, frozen_at(NOON):
        policy = documents.create(
            session, steward, {"name": "Information security policy", "kind": "policy",
                               "org_unit_id": imm},
        )  # fmt: skip
        with pytest.raises(Invalid) as caught:  # nothing to approve yet
            documents.submit(session, steward, policy, [leader.account_id])
        assert set(caught.value.errors) == {"content"}
        documents.save_draft(session, steward, policy, {"body": POLICY})
        for approvers, said in [
            ([], "at least one"),
            ([steward.account_id], "may not approve"),  # its author
            ([9999], "not disabled"),
        ]:
            with pytest.raises(Invalid) as caught:
                documents.submit(session, steward, policy, approvers)
            assert said in caught.value.errors["approvers"], approvers
        with pytest.raises(PermissionDenied):
            documents.submit(session, member, policy, [leader.account_id])
        documents.submit(session, steward, policy, [leader.account_id, manager.account_id])
        with pytest.raises(Conflict):  # what is under review is not changed
            documents.save_draft(session, steward, policy, {"body": "Something else"})
        with pytest.raises(Conflict):
            documents.publish(session, steward, policy)
        with pytest.raises(PermissionDenied):  # only those named decide
            documents.decide(session, member, policy, "approved", None)
        with pytest.raises(Invalid):  # a return says why
            documents.decide(session, leader, policy, "returned", " ")
        documents.decide(session, leader, policy, "returned", "Say who approves exceptions.")
        version = documents.open_version(session, policy)
        assert version is not None and version.status == "draft"
        # The other approval is no longer needed, and the author is told why it came back.
        assert documents.awaiting(session, manager) == []
        shown = records.detail(session, steward, DOCUMENT, policy)["working"]
        assert shown["returned"] == {
            "by": "Leader Person", "note": "Say who approves exceptions.", "at": NOON,
        }  # fmt: skip
        documents.save_draft(
            session, steward, policy,
            {"body": POLICY + "- Exceptions are approved by the security officer.\n"},
        )  # fmt: skip
        documents.submit(session, steward, policy, [leader.account_id, manager.account_id])
        documents.decide(session, leader, policy, "approved", "Good.")
        with pytest.raises(Conflict):
            documents.decide(session, leader, policy, "approved", None)
        assert documents.open_version(session, policy).status == "in_review"  # type: ignore[union-attr]
        documents.decide(session, manager, policy, "approved", None)
        assert documents.open_version(session, policy).status == "approved"  # type: ignore[union-attr]
        first = documents.publish(session, steward, policy)
        assert (first.number, first.status, first.published_by_name) == (
            1,
            "published",
            "Steward Person",
        )
        assert policy.published_version_id == first.id and policy.last_reviewed_on == NOON.date()
        assert policy.next_review_on == date(2027, 3, 2)  # the program's twelve months
        assert documents.open_version(session, policy) is None
        # The member reads the version in force.
        shown = records.detail(session, member, DOCUMENT, policy)
        assert shown["published"]["number"] == 1 and shown["published"]["approved_by"] == [
            "Leader Person", "Manager Person",
        ]  # fmt: skip
        assert "security officer" in shown["published"]["body"]

    # A second version: a change note is needed, and the first is superseded.
    with db.write(steward.actor) as session, frozen_at(at("2026-09-01")):
        policy = session.get(PolicyDocument, policy.id)
        documents.start_draft(session, steward, policy)
        with pytest.raises(Conflict):
            documents.start_draft(session, steward, policy)
        documents.save_draft(
            session, steward, policy,
            {"body": POLICY.replace("are personal.", "are personal and never shared.")},
        )  # fmt: skip
        with pytest.raises(Invalid) as caught:
            documents.submit(session, steward, policy, [leader.account_id])
        assert set(caught.value.errors) == {"change_note"}
        documents.save_draft(
            session, steward, policy, {"change_note": "Sharing accounts, said plainly."}
        )
        second = publish(session, steward, leader, policy)
        first = session.get(PolicyVersion, first.id)
        assert (second.number, first.status) == (2, "superseded")
        assert policy.next_review_on == date(2027, 9, 1)
        found = documents.compare(session, member, policy, first.id, second.id)
        assert found["counts"] == {"added": 0, "removed": 1, "changed": 1}
        changed = next(row for row in found["rows"] if row["op"] == "changed")
        assert [piece["text"] for piece in changed["after"] if piece["mark"]] == [
            " and never shared"
        ]
        entries = history.for_record(session, DOCUMENT, policy)
        titles = [entry["title"] for entry in entries]
        # Every version still matches the fingerprint taken when it was published, including
        # the one it replaced.
        assert documents.check_fingerprints(session) == {"checked": 2, "problems": []}
        assert titles[:4] == [
            "Published version 2", "The version it replaces is superseded",
            "Every approval is in: it can be published", "Leader Person approved it",
        ]  # fmt: skip
        assert "Leader Person returned it: Say who approves exceptions." in titles
    assert any("is published" in line for line in told(db, people.accounts["steward"])) is False
    assert told(db, people.accounts["leader"])[0].startswith("Steward Person asks you to approve")


def test_what_was_published_is_never_changed(
    db: Database, people: People, as_role: Clients
) -> None:
    steward, leader = who(db, people, "steward"), who(db, people, "leader")
    with db.write(steward.actor) as session, frozen_at(NOON):
        policy = documents.create(
            session, steward,
            {"name": "Acceptable use policy", "kind": "policy", "org_unit_id": people.units["IMM"],
             "body": POLICY},
        )  # fmt: skip
        version = publish(session, steward, leader, policy)
        ref, version_id = policy.ref, version.id
        assert documents.check_fingerprints(session) == {"checked": 1, "problems": []}
    client = as_role("steward")
    # No route changes a published version: the draft routes act on a draft only.
    auditor = {"approvers": [people.accounts["auditor"]]}
    for method, path, body in [
        ("patch", f"/api/v1/documents/{ref}/draft", {"body": "Rewritten"}),
        ("post", f"/api/v1/documents/{ref}/draft/submit", auditor),
        ("post", f"/api/v1/documents/{ref}/draft/publish", None),
        ("delete", f"/api/v1/documents/{ref}/draft", None),
    ]:  # fmt: skip
        answer = getattr(client, method)(path, **({"json": body} if body is not None else {}))
        assert answer.status_code == 404, (method, path, answer.text)
    shown = client.get(f"/api/v1/documents/{ref}/versions/{version_id}").json()["data"]
    assert shown["body"].startswith("# Information security policy")
    # Changed behind the app's back, it no longer matches what the history says was published.
    with db.engine.begin() as conn:
        conn.execute(
            text("UPDATE policy_version SET body = :body WHERE id = :id"),
            {"body": "Rewritten in the database", "id": version_id},
        )
    with db.read() as session:
        found = documents.check_fingerprints(session)
    assert found["problems"] == [f"{ref} version 1 is not what was published."]


def test_a_draft_is_for_those_working_on_it(db: Database, people: People, as_role: Clients) -> None:
    steward, leader = who(db, people, "steward"), who(db, people, "leader")
    with db.write(steward.actor) as session, frozen_at(NOON):
        policy = documents.create(
            session, steward,
            {"name": "Clean desk guideline", "kind": "guideline",
             "org_unit_id": people.units["HALE"], "body": "Lock your screen."},
        )  # fmt: skip
        version = documents.open_version(session, policy)
        ref, draft = policy.ref, version.id  # type: ignore[union-attr]
        documents.submit(session, steward, policy, [people.accounts["auditor"]])
    for role, seen in [("member", 404), ("assessor", 404), ("auditor", 200), ("leader", 200),
                       ("steward", 200), ("manager", 200)]:  # fmt: skip
        answer = as_role(role).get(f"/api/v1/documents/{ref}/versions/{draft}")
        assert answer.status_code == seen, role
    # The auditor was asked, and may approve; the steward who sent it may not.
    assert (
        as_role("steward")
        .post(f"/api/v1/documents/{ref}/draft/decision", json={"decision": "approved"})
        .status_code
        == 403
    )
    approved = as_role("auditor").post(
        f"/api/v1/documents/{ref}/draft/decision", json={"decision": "approved"}
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["working"]["status"] == "approved"
    listed = as_role("member").get("/api/v1/documents", params={"state": "approved"}).json()
    assert [row["ref"] for row in listed["data"]] == [ref]
    assert listed["data"][0]["working"] == "approved" and listed["data"][0]["number"] is None
    assert leader is not None


# --- Held as a file, or elsewhere ---------------------------------------------------------------


def test_a_version_can_be_a_file_or_a_link(db: Database, people: People, as_role: Clients) -> None:
    client = as_role("steward")
    made = client.post(
        "/api/v1/documents",
        json={"name": "Backup procedure", "kind": "procedure", "org_unit_id": people.units["HALE"],
              "form": "link", "url": "https://wiki.northmere.example/backup"},
    )  # fmt: skip
    assert made.status_code == 201, made.text
    ref = made.json()["data"]["ref"]
    assert made.json()["data"]["working"]["url"] == "https://wiki.northmere.example/backup"
    refused = client.patch(f"/api/v1/documents/{ref}/draft", json={"url": "wiki/backup"})
    assert refused.status_code == 422
    pdf = b"%PDF-1.4\n1 0 obj << >> endobj\ntrailer << >>\n%%EOF\n"
    sent = client.post(f"/api/v1/documents/{ref}/draft/file", params={"name": "Backup v1.pdf"},
                       content=pdf)  # fmt: skip
    assert sent.status_code == 200, sent.text
    working = sent.json()["data"]["working"]
    assert working["form"] == "file" and working["file"]["name"] == "Backup v1.pdf"
    assert working["url"] is None
    client.post(
        f"/api/v1/documents/{ref}/draft/submit", json={"approvers": [people.accounts["leader"]]}
    )
    as_role("leader").post(f"/api/v1/documents/{ref}/draft/decision", json={"decision": "approved"})
    published = client.post(f"/api/v1/documents/{ref}/draft/publish").json()["data"]["published"]
    got = as_role("member").get(f"/api/v1/documents/{ref}/versions/{published['id']}/file")
    assert got.status_code == 200 and got.content == pdf
    assert got.headers["content-disposition"].startswith('attachment; filename="Backup v1.pdf"')
    # Two files are compared by their fingerprints alone.
    client.post(f"/api/v1/documents/{ref}/draft")
    draft = client.get(f"/api/v1/documents/{ref}").json()["data"]["working"]
    pair = {"from": published["id"], "to": draft["id"]}
    same = client.get(f"/api/v1/documents/{ref}/compare", params=pair).json()["data"]
    assert same["same"] is True and same["rows"] == []


# --- Review ---------------------------------------------------------------------------------------


def test_a_document_is_reviewed_on_the_programs_cadence(db: Database, people: People) -> None:
    steward, leader = who(db, people, "steward"), who(db, people, "leader")
    hale = people.units["HALE"]
    with db.write(steward.actor) as session, frozen_at(at("2025-01-10")):
        procedure = documents.create(
            session, steward,
            {"name": "Freezer alarm procedure", "kind": "procedure", "org_unit_id": hale,
             "body": "Answer the alarm.", "review_months": 6},
        )  # fmt: skip
        publish(session, steward, leader, procedure)
        assert procedure.next_review_on == date(2025, 7, 10)
    with db.write(steward.actor) as session, frozen_at(at("2025-07-12")):
        procedure = session.get(PolicyDocument, procedure.id)
        assert documents.review_state(procedure) == "overdue"
        items = reporting.home(session, steward)["items"]
        assert ("document_review", "Review Freezer alarm procedure", True) in [
            (item["kind"], item["title"], item["overdue"]) for item in items
        ]
        sent = reminders.send(session)
        assert sent["overdue"] >= 1
        with pytest.raises(Invalid):
            documents.review(session, steward, procedure, "")
        documents.review(session, steward, procedure, "Checked against the new alarm panel.")
        assert procedure.next_review_on == date(2026, 1, 12)
        titles = [entry["title"] for entry in history.for_record(session, DOCUMENT, procedure)]
        assert titles[0] == "Reviewed it and kept it as it is: Checked against the new alarm panel."
        # Retired, it is no longer reviewed; a document that others implement is not retired.
        documents.retire(session, steward, procedure, "The freezers were replaced.")
        assert procedure.next_review_on is None
        documents.reinstate(session, steward, procedure)
        assert procedure.next_review_on == date(2026, 1, 12)
    assert any(line.startswith("Review overdue") for line in told(db, people.accounts["steward"]))


def test_the_programs_cadence_moves_the_documents_that_follow_it(
    db: Database, people: People
) -> None:
    from riskwren.program import rules
    from riskwren.risk import program

    steward, leader, manager = (who(db, people, role) for role in ("steward", "leader", "manager"))
    hale = people.units["HALE"]
    with db.write(steward.actor) as session, frozen_at(NOON):
        follows = documents.create(
            session,
            steward,
            {"name": "Follows", "kind": "policy", "org_unit_id": hale, "body": "A"},
        )
        own = documents.create(
            session, steward,
            {"name": "Own", "kind": "policy", "org_unit_id": hale, "body": "B", "review_months": 6},
        )  # fmt: skip
        publish(session, steward, leader, follows)
        publish(session, steward, leader, own)
        cadences = {**rules.get(session, "cadences"), "document_review_months": 24}
        found = program.change(session, manager, {"cadences": cadences})
        assert found["counts"]["documents"] == 1
        assert (follows.next_review_on, own.next_review_on) == (date(2028, 3, 2), date(2026, 9, 2))


def test_home_says_what_is_waiting_on_whom(db: Database, people: People) -> None:
    steward, leader = who(db, people, "steward"), who(db, people, "leader")
    with db.write(steward.actor) as session, frozen_at(NOON):
        policy = documents.create(
            session, steward,
            {"name": "Remote work policy", "kind": "policy", "org_unit_id": people.units["IMM"],
             "body": "Work from where it is safe."},
        )  # fmt: skip
        documents.submit(session, steward, policy, [leader.account_id])

        def kinds(person) -> list[str]:  # type: ignore[no-untyped-def]
            return [item["kind"] for item in reporting.home(session, person)["items"]
                    if item.get("ref") == policy.ref]  # fmt: skip

        assert kinds(leader) == ["approve"] and kinds(steward) == []
        documents.decide(session, leader, policy, "returned", "Say what safe means.")
        assert kinds(leader) == [] and kinds(steward) == ["rework"]
        documents.submit(session, steward, policy, [leader.account_id])
        documents.decide(session, leader, policy, "approved", None)
        assert kinds(steward) == ["publish"]
        documents.publish(session, steward, policy)
        assert kinds(steward) == []
        with pytest.raises(NotFound):
            documents.withdraw(session, steward, policy)


# --- Comparing --------------------------------------------------------------------------------


def test_two_texts_are_compared_line_by_line_and_word_by_word() -> None:
    before = "# Title\n\nOne.\nTwo is here.\nThree.\n\n" + "\n".join(
        f"Line {n}." for n in range(20)
    )
    after = "# Title\n\nOne.\nTwo was here.\nFour.\n" + "\n".join(f"Line {n}." for n in range(20))
    found = compare.compare(before, after)
    assert found["counts"] == {"added": 1, "removed": 1, "changed": 1}
    ops = [row["op"] for row in found["rows"]]
    assert ops == ["same", "same", "changed", "removed", "added", "same", "same", "folded"]
    assert found["rows"][-1] == {"op": "folded", "count": 18}
    two = found["rows"][2]
    assert [p["text"] for p in two["before"] if p["mark"]] == ["is"]
    assert [p["text"] for p in two["after"] if p["mark"]] == ["was"]
    assert compare.compare("A\n\nB", "A\nB\n")["same"] is True  # blank lines carry nothing
    added = compare.compare("A", "A\nB\nC")
    assert [row["op"] for row in added["rows"]] == ["same", "added", "added"]
    # A step put in the middle of a numbered list is one line added, the rest renumbered.
    steps = compare.compare(
        "1. Contain it.\n2. Recover from backups.\n3. Learn from it.",
        "1. Contain it.\n2. Decide who must be told.\n3. Recover from backups.\n4. Learn from it.",
    )
    assert [row["op"] for row in steps["rows"]] == ["same", "added", "changed", "changed"]
    assert ME is not None and accounts is not None
