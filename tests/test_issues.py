"""Issues, exceptions, and notices: a failed test opens an issue; its date follows from its
severity; it is closed only by someone who does not own it; an exception is decided by
someone who did not ask, and when it ends what it covered is as it was."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from riskwren.compliance import assessments, exceptions, issues, packs, scopes
from riskwren.compliance.exceptions import EXCEPTION
from riskwren.compliance.issues import ISSUE
from riskwren.compliance.scopes import SCOPE
from riskwren.controls.service import CONTROL
from riskwren.core.clock import frozen_at
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import TestResult
from riskwren.inventory import history, records
from riskwren.people import notices
from riskwren.program import rules
from riskwren.reporting import service as reporting
from riskwren.treatment import service as treatment
from tests.conftest import TESTER
from tests.people import People
from tests.test_assessments import start, the_test, world
from tests.test_evidence import add_evidence
from tests.test_risks import who
from tests.test_scopes import state_of
from tests.test_treatment import add_control

Clients = Callable[[str | None], TestClient]
NOW = datetime(2026, 3, 2, 12, tzinfo=UTC)
TODAY = NOW.date()


@pytest.fixture
def loaded(db: Database, people: People) -> None:
    with db.write(TESTER) as session:
        packs.install(session)


def raise_issue(session, by, unit: int, name: str = "Visitors are not signed in", **more):  # type: ignore[no-untyped-def]
    values = {"name": name, "org_unit_id": unit, "severity": "moderate", **more}
    return issues.create(session, by, values)


def told(session, person) -> list[str]:  # type: ignore[no-untyped-def]
    return [notice["text"] for notice in notices.mine(session, person)]


def fail(session, manager, central, control, operation: str = "ineffective"):  # type: ignore[no-untyped-def]
    """An assessment in which the manager finds a control wanting. Not yet confirmed."""
    made = start(session, manager, central)
    return made, assessments.record(
        session, manager, the_test(session, made, control), design="effective",
        operation=operation, note="No restore has been tried in two years.",
        sample="The restore log.",
    )  # fmt: skip


# --- From a test --------------------------------------------------------------------------


def test_a_failed_test_opens_an_issue_filled_in_from_the_result(
    db: Database, loaded: None, people: People
) -> None:
    manager, assessor, leader = (who(db, people, r) for r in ("manager", "assessor", "leader"))
    with frozen_at(NOW):
        with db.write(manager.actor) as session:
            central, enclave, backups, factor = world(session, people, manager)
            made, result = fail(session, manager, central, backups)
            fine = assessments.record(
                session, manager, the_test(session, made, factor), design="effective",
                operation="effective", note="All ten sampled were as described.",
            )  # fmt: skip
            assert records.search(session, manager, ISSUE, {})[1] == 0  # nothing counts yet
        with db.write(assessor.actor) as session:
            for each in (result, fine):
                assessments.review(
                    session, assessor, session.get(TestResult, each.id), confirm=True, note=None
                )
            found, total = records.search(session, assessor, ISSUE, {})
            assert total == 1  # the one that failed, and not the one that passed
            issue = found[0]
            assert (issue.ref, issue.status, issue.source_kind) == ("ISS-0001", "open", "test")
            assert issue.name == "Backups: found ineffective in ASM-0001"
            assert issue.summary.startswith("No restore has been tried in two years.")
            assert "What was looked at: The restore log." in issue.summary
            # Ineffective is high, and high is due in ninety days.
            assert (issue.severity, issue.due_on) == ("high", TODAY + timedelta(days=90))
            assert issue.org_unit_id == people.units["CANCER"]
            view = records.detail(session, assessor, ISSUE, issue)
            # It is about the control, and names every scope that relies on it.
            assert [(s["type"], s["name"]) for s in view["subjects"]["records"]] == [
                ("control", "Backups"), ("scope", "Central computing"), ("scope", "The enclave"),
            ]  # fmt: skip
            assert view["source"]["assessment"]["ref"] == "ASM-0001"
            assert (view["source"]["operation"], view["source"]["tested_by"]) == (
                "ineffective",
                manager.name,
            )
            # It belongs to whoever owns the control, who is told; not to whoever found it.
            assert [o["account_id"] for o in view["owners"]] == [people.accounts["leader"]]
            assert told(session, leader) == [
                "ISS-0001 was opened by a test of Backups, which you own"
            ]
            test = assessments.view_of_test(session, assessor, the_test(session, made, backups))
            assert test["issue"] == {"ref": "ISS-0001", "name": issue.name, "status": "open"}
            assert (
                assessments.view_of_test(session, assessor, the_test(session, made, factor))[
                    "issue"
                ]
                is None
            )
            # It is found from the control, and from either scope.
            for about in (backups.ref, central.ref, enclave.ref):
                assert [
                    i.ref for i in records.search(session, assessor, ISSUE, {"about": about})[0]
                ] == ["ISS-0001"]
        with db.write(manager.actor) as session:
            # Tested again while the issue is open: the one issue stands.
            central = records.load(session, manager, SCOPE, central.ref)
            backups = records.load(session, manager, CONTROL, backups.ref)
            _, again = fail(session, manager, central, backups, operation="partly")
        with db.write(assessor.actor) as session:
            assessments.review(
                session, assessor, session.get(TestResult, again.id), confirm=True, note=None
            )
            assert records.search(session, assessor, ISSUE, {})[1] == 1


# --- The clock ----------------------------------------------------------------------------


def test_the_date_follows_the_severity_and_moving_it_is_counted(
    db: Database, people: People
) -> None:
    steward, member, auditor, manager = (
        who(db, people, r) for r in ("steward", "member", "auditor", "manager")
    )
    hale = people.units["HALE"]
    with frozen_at(NOW), db.write(member.actor) as session:
        # Anyone may say that something is wrong where they work.
        issue = raise_issue(session, member, hale, summary="The door log has gaps.")
        assert (issue.ref, issue.source_kind, issue.due_on) == (
            "ISS-0001",
            "observation",
            TODAY + timedelta(days=180),
        )
        assert issue.original_due_on == issue.due_on
        with pytest.raises(Invalid) as bad:
            raise_issue(session, member, hale, severity="urgent", source_kind="rumour")
        assert set(bad.value.errors) == {"severity", "source_kind"}
        with pytest.raises(PermissionDenied):
            raise_issue(session, member, people.units["CANCER"])
    with db.write(auditor.actor) as session, pytest.raises(PermissionDenied):
        raise_issue(session, auditor, hale)
    with frozen_at(NOW + timedelta(days=10)), db.write(steward.actor) as session:
        issue = records.load(session, steward, ISSUE, "ISS-0001")
        # A change of severity sets the date again, counted from the day it was raised.
        records.update(
            session, steward, ISSUE, issue, {"severity": "critical"}, version=issue.version
        )
        assert issue.due_on == TODAY + timedelta(days=30)
        with pytest.raises(Invalid) as bad:
            issues.reschedule(session, steward, issue, due_on="2026-05-01", reason=" ")
        assert "reason" in bad.value.errors
        issues.reschedule(
            session, steward, issue, due_on="2026-05-01", reason="Waiting on the supplier."
        )
        issues.reschedule(
            session, steward, issue, due_on="2026-06-01", reason="The part was wrong."
        )
        card = records.cards(session, ISSUE, [issue])[0]
        assert (card["due_on"], card["original_due_on"], card["moved"]) == (
            date(2026, 6, 1),
            TODAY + timedelta(days=180),
            2,
        )
        assert [move["reason"] for move in issue.extensions] == [
            "Waiting on the supplier.",
            "The part was wrong.",
        ]
        assert not card["overdue"]
    with frozen_at(NOW + timedelta(days=120)), db.write(manager.actor) as session:
        issue = records.load(session, manager, ISSUE, "ISS-0001")
        assert records.cards(session, ISSUE, [issue])[0]["overdue"]
        assert [i.ref for i in records.search(session, manager, ISSUE, {"overdue": True})[0]] == [
            "ISS-0001"
        ]
        # The clock is the program's to set.
        rules.put(
            session,
            "cadences",
            {
                **rules.get(session, "cadences"),
                "issue_due_days": {"critical": 7, "high": 30, "moderate": 60, "low": 90},
            },
        )
        quick = raise_issue(session, manager, hale, "Second thing", severity="critical")
        assert (quick.due_on - quick.created_at.date()).days == 7


# --- Working on it, and closing it --------------------------------------------------------


def test_an_issue_is_closed_only_by_someone_who_does_not_own_it(
    db: Database, people: People
) -> None:
    steward, member, assessor, manager = (
        who(db, people, r) for r in ("steward", "member", "assessor", "manager")
    )
    hale = people.units["HALE"]
    with db.write(steward.actor) as session:
        control = add_control(session, steward, hale, "Visitors signed in")
        issue = raise_issue(session, steward, hale, subjects=[control.ref], severity="high")
        first = issues.add_action(
            session,
            steward,
            issue,
            title="Put a book at the door",
            owner_id=member.account_id,
            due_on="2031-01-10",
        )
        issues.add_action(
            session,
            steward,
            issue,
            title="Brief reception",
            owner_id=steward.account_id,
            due_on="2031-01-20",
        )
        assert (first.ref, first.source_type, first.source_id) == ("ACT-0001", "issue", issue.id)
        assert told(session, member) == ["ACT-0001 is yours, for ISS-0001: Put a book at the door"]
        assert told(session, steward) == []  # nobody is told of what they did themselves
        item = add_evidence(session, steward, hale, "Photograph of the visitor book")
        with pytest.raises(Conflict) as open_actions:
            issues.propose(session, steward, issue, note="Done.", root_cause="procedure")
        assert "2 of its actions are still open" in str(open_actions.value)
    with db.write(member.actor) as session:
        # Whoever has an action on an issue can see it, and does their part.
        issue = records.load(session, member, ISSUE, "ISS-0001")
        view = records.detail(session, member, ISSUE, issue)
        assert view["progress"] == {"done": 0, "total": 2} and not view["can"]["edit"]
        mine, _ = treatment.search_actions(session, member, {"mine": True})
        assert [(a["ref"], a["source"]["ref"], a["can"]["act"]) for a in mine] == [
            ("ACT-0001", "ISS-0001", True)
        ]
        treatment.update_action(
            session,
            member,
            treatment.find_action(session, "ACT-0001"),
            {"status": "done", "completion_note": "Bought."},
        )
        with pytest.raises(PermissionDenied):
            issues.propose(session, member, issue, note="Done.", root_cause="procedure")
    with db.write(steward.actor) as session:
        issue = records.load(session, steward, ISSUE, "ISS-0001")
        treatment.update_action(
            session, steward, treatment.find_action(session, "ACT-0002"), {"status": "done"}
        )
        assert told(session, steward) == [
            "Every action on ISS-0001 is done. Say what was done, and propose closing it"
        ]
        with pytest.raises(Invalid) as bad:
            issues.propose(
                session,
                steward,
                issue,
                note="",
                root_cause="carelessness",
                evidence_refs=["EV-9999"],
            )
        assert set(bad.value.errors) == {"note", "root_cause", "evidence"}
        issues.propose(
            session,
            steward,
            issue,
            note="A book is at the door and reception use it.",
            root_cause="procedure",
            evidence_refs=[item.ref],
        )
        assert issue.status == "proposed"
        # The owner cannot confirm their own closure, and cannot go on changing the issue.
        with pytest.raises(PermissionDenied) as own:
            issues.validate(session, steward, issue, confirm=True, note=None)
        assert "an issue they own" in str(own.value)
        with pytest.raises(Conflict):
            issues.add_action(
                session,
                steward,
                issue,
                title="One more",
                owner_id=steward.account_id,
                due_on="2031-02-01",
            )
        with pytest.raises(PermissionDenied):
            issues.cancel(session, steward, issue, reason="It was nothing.")
    with db.write(assessor.actor) as session:
        issue = records.load(session, assessor, ISSUE, "ISS-0001")
        assert "ISS-0001 is said to be put right, and waits for someone to confirm it" in told(
            session, assessor
        )
        view = records.detail(session, assessor, ISSUE, issue)
        assert view["can_act"]["validate"] and [e["ref"] for e in view["closure_evidence"]] == [
            item.ref
        ]
        with pytest.raises(Invalid):
            issues.validate(session, assessor, issue, confirm=False, note=None)
        issues.validate(
            session, assessor, issue, confirm=False, note="The book has no entries yet."
        )
        assert (issue.status, issue.return_note) == ("open", "The book has no entries yet.")
    with db.write(steward.actor) as session:
        issue = records.load(session, steward, ISSUE, "ISS-0001")
        assert "ISS-0001 was sent back by Assessor Person: The book has no entries yet." in told(
            session, steward
        )
        issues.propose(
            session,
            steward,
            issue,
            note="A month of entries, checked weekly.",
            root_cause="procedure",
        )
    with db.write(manager.actor) as session:
        issue = records.load(session, manager, ISSUE, "ISS-0001")
        issues.validate(session, manager, issue, confirm=True, note=None)
        assert (issue.status, issue.root_cause, issue.validated_by_name) == (
            "closed",
            "procedure",
            manager.name,
        )
        assert issue.closed_at is not None
        with pytest.raises(Invalid):  # a closed issue is not quietly rewritten
            records.update(
                session, manager, ISSUE, issue, {"name": "Something else"}, version=issue.version
            )
        with pytest.raises(Conflict):
            issues.validate(session, manager, issue, confirm=True, note=None)
        told_titles = [entry["title"] for entry in history.for_record(session, ISSUE, issue)]
        assert "Added an action: Put a book at the door" in told_titles
        issues.reopen(session, manager, issue, reason="It has stopped being used.")
        assert (issue.status, issue.closed_at, issue.validated_by) == ("open", None, None)
        # Whoever proposes closure does not confirm it, whether or not they own the issue.
        issues.propose(session, manager, issue, note="Reception reminded.", root_cause="people")
        with pytest.raises(PermissionDenied) as proposer:
            issues.validate(session, manager, issue, confirm=True, note=None)
        assert "they proposed" in str(proposer.value)
    with db.write(assessor.actor) as session:
        issue = records.load(session, assessor, ISSUE, "ISS-0001")
        issues.validate(session, assessor, issue, confirm=False, note="Not yet.")
        issues.cancel(session, assessor, issue, reason="Recorded twice; see the other.")
        assert issue.status == "cancelled"


def test_an_issue_is_known_only_to_those_with_a_part_in_it(db: Database, people: People) -> None:
    manager, steward, member, assessor, auditor, leader = (
        who(db, people, r)
        for r in ("manager", "steward", "member", "assessor", "auditor", "leader")
    )
    with db.write(manager.actor) as session:
        raise_issue(session, manager, people.units["CANCER"], "In another division")
        raise_issue(session, manager, people.units["HALE"], "In the lab", restricted=True)
        raise_issue(
            session, manager, people.units["HALE"], "Handed to a member", owner_id=member.account_id
        )
    with db.read() as session:
        seen = lambda person: sorted(i.ref for i in records.search(session, person, ISSUE, {})[0])  # noqa: E731
        assert seen(manager) == seen(auditor) == ["ISS-0001", "ISS-0002", "ISS-0003"]
        assert seen(steward) == seen(leader) == ["ISS-0002", "ISS-0003"]  # their unit and below
        assert seen(assessor) == ["ISS-0001", "ISS-0003"]  # not what is restricted
        assert seen(member) == ["ISS-0003"]  # only what is theirs
        with pytest.raises(NotFound):
            records.load(session, member, ISSUE, "ISS-0002")
        assert told(session, member) == ["ISS-0003 is yours to put right: Handed to a member"]
        mine = [i for i in reporting.home(session, member)["items"] if i["kind"] == "issue"]
        assert [(i["title"], i["href"]) for i in mine] == [
            ("Put right: Handed to a member", "/issues/ISS-0003")
        ]


# --- Exceptions ---------------------------------------------------------------------------


def test_an_exception_is_decided_by_someone_else_and_ends_by_itself(
    db: Database, loaded: None, people: People
) -> None:
    manager, assessor, steward, leader, member = (
        who(db, people, r) for r in ("manager", "assessor", "steward", "leader", "member")
    )
    with frozen_at(NOW):
        with db.write(manager.actor) as session:
            central, enclave, backups, _ = world(session, people, manager)
            _, result = fail(session, manager, central, backups)
        with db.write(assessor.actor) as session:
            assessments.review(
                session, assessor, session.get(TestResult, result.id), confirm=True, note=None
            )
        with db.write(member.actor) as session, pytest.raises(PermissionDenied):
            exceptions.request(
                session,
                member,
                {
                    "control": backups.ref,
                    "scope": enclave.ref,
                    "justification": "x",
                    "expires_on": "2026-06-30",
                },
            )
        with db.write(steward.actor) as session:

            def ask(**values):
                return exceptions.request(
                    session,
                    steward,
                    {
                        "scope": enclave.ref,
                        "justification": "The tape library is being replaced.",
                        **values,
                    },
                )

            with pytest.raises(Invalid) as bad:
                ask(control=backups.ref, justification=" ")
            assert set(bad.value.errors) == {"justification", "expires_on"}  # never open-ended
            with pytest.raises(Invalid) as long:
                ask(control=backups.ref, expires_on="2027-06-30")
            assert "at most 12 months" in long.value.errors["expires_on"]
            with pytest.raises(Invalid):
                ask(
                    requirement={"framework": "hipaa-security", "code": "164.308(a)(1)(i)"},
                    expires_on="2026-06-30",
                )
            made = ask(
                control=backups.ref,
                expires_on="2026-06-30",
                compensating="Nightly copies to a second site, checked by hand each week.",
            )
            gap = ask(
                requirement={"framework": "nist-csf", "code": "GV.OC-01"},
                expires_on="2026-04-30",
                starts_on="2026-03-10",
            )
            assert (made.ref, made.status, made.name) == (
                "EXC-0001",
                "requested",
                "Backups in The enclave",
            )
            assert gap.name.startswith("GV.OC-01") and gap.org_unit_id == people.units["HALE"]
            # Asking changes nothing, and whoever asked does not decide.
            found = scopes.statement(
                session, steward, records.load(session, steward, SCOPE, enclave.ref), "nist-csf"
            )
            assert state_of(found, "PR.DS-11") == "failing" and state_of(found, "GV.OC-01") == "gap"
            with pytest.raises(PermissionDenied):
                exceptions.decide(session, steward, made, approve=True, note=None)
        with db.write(manager.actor) as session:
            assert (
                "Steward Person asks for an exception: Backups in The enclave (EXC-0001)"
                in told(session, manager)
            )
        with db.write(leader.actor) as session:
            assert [o["kind"] for o in exceptions.waiting_on(session, leader)] == [
                "decide",
                "decide",
            ]
            made = records.load(session, leader, EXCEPTION, "EXC-0001")
            gap = records.load(session, leader, EXCEPTION, "EXC-0002")
            with pytest.raises(Invalid):
                exceptions.decide(session, leader, gap, approve=False, note=None)
            exceptions.decide(
                session,
                leader,
                made,
                approve=True,
                note="Until the new library is in.",
                expires_on="2026-05-31",
            )
            exceptions.decide(session, leader, gap, approve=True, note=None)
            assert (made.status, made.expires_on, made.decided_by_name) == (
                "approved",
                date(2026, 5, 31),
                leader.name,
            )
            with pytest.raises(Conflict):
                exceptions.decide(session, leader, made, approve=False, note="Changed my mind.")
            assert (
                exceptions.state_of(made) == "in_force" and exceptions.state_of(gap) == "upcoming"
            )
        with db.read() as session:
            assert "EXC-0001 was approved by Leader Person, until 2026-05-31" in told(
                session, steward
            )
            enclave = records.load(session, manager, SCOPE, enclave.ref)
            found = scopes.statement(session, manager, enclave, "nist-csf")
            row = next(r for r in found["requirements"] if r["code"] == "PR.DS-11")
            # In force: excepted, and saying what is underneath.
            assert (row["state"], row["underlying"]) == ("excepted", "failing")
            answering = row["controls"][0]
            assert (
                answering["readiness"] == "excepted" and answering["exception"]["ref"] == "EXC-0001"
            )
            assert answering["why"].startswith("Excepted until 2026-05-31 by EXC-0001. Tested")
            assert found["counts"]["excepted"] == 2 and found["counts"]["failing"] == 0
            # The one that has not started yet covers nothing, and the provider's own scope
            # is not excepted by an exception asked for in the enclave.
            assert state_of(found, "GV.OC-01") == "gap"
            central = records.load(session, manager, SCOPE, central.ref)
            assert (
                state_of(scopes.statement(session, manager, central, "nist-csf"), "PR.DS-11")
                == "failing"
            )
    with frozen_at(NOW + timedelta(days=20)), db.read() as session:
        found = scopes.statement(
            session, manager, records.load(session, manager, SCOPE, enclave.ref), "nist-csf"
        )
        row = next(r for r in found["requirements"] if r["code"] == "GV.OC-01")
        assert (row["state"], row["underlying"], row["exception"]["ref"]) == (
            "excepted",
            "gap",
            "EXC-0002",
        )
        assert [i for i in found["requirements"] if i["state"] == "excepted"] and found["counts"][
            "excepted"
        ] == 3
    with frozen_at(datetime(2026, 5, 20, 9, tzinfo=UTC)), db.write(steward.actor) as session:
        made = records.load(session, steward, EXCEPTION, "EXC-0001")
        assert exceptions.state_of(made) == "expiring"
        assert [o["kind"] for o in exceptions.waiting_on(session, steward)] == ["renew"]
        # Carrying on is asked for again, and decided again.
        again = exceptions.request(
            session,
            steward,
            {
                "renews": "EXC-0001",
                "justification": "Delivery slipped a month.",
                "starts_on": "2026-06-01",
                "expires_on": "2026-06-30",
            },
        )
        assert (again.subject_type, again.subject_id, again.scope_id, again.renews_id) == (
            "control",
            made.subject_id,
            made.scope_id,
            made.id,
        )
        assert exceptions.waiting_on(session, steward) == []
        assert records.detail(session, steward, EXCEPTION, made)["renewed_by"] == {
            "ref": "EXC-0003",
            "status": "requested",
        }
    with frozen_at(datetime(2026, 6, 2, 9, tzinfo=UTC)), db.write(manager.actor) as session:
        # The day after it ends, with the renewal not approved: failing again, by itself.
        made = records.load(session, manager, EXCEPTION, "EXC-0001")
        assert (made.status, exceptions.state_of(made)) == ("approved", "expired")
        enclave = records.load(session, manager, SCOPE, enclave.ref)
        found = scopes.statement(session, manager, enclave, "nist-csf")
        row = next(r for r in found["requirements"] if r["code"] == "PR.DS-11")
        assert (row["state"], row["exception"], row["controls"][0]["exception"]) == (
            "failing",
            None,
            None,
        )
        expired, _ = records.search(session, manager, EXCEPTION, {"state": "expired"})
        assert sorted(e.ref for e in expired) == ["EXC-0001", "EXC-0002"]
        # The manager, who did not ask, approves the renewal; later it is ended early.
        again = records.load(session, manager, EXCEPTION, "EXC-0003")
        exceptions.decide(session, manager, again, approve=True, note=None)
        assert (
            state_of(scopes.statement(session, manager, enclave, "nist-csf"), "PR.DS-11")
            == "excepted"
        )
        with pytest.raises(Invalid):
            exceptions.withdraw(session, manager, again, reason=None)
        exceptions.withdraw(session, manager, again, reason="The library arrived.")
        assert (
            state_of(scopes.statement(session, manager, enclave, "nist-csf"), "PR.DS-11")
            == "failing"
        )


# --- The plan of action, and the API ------------------------------------------------------


def test_a_scope_prints_its_open_issues_as_a_plan_of_action(
    db: Database, loaded: None, people: People
) -> None:
    manager, assessor = who(db, people, "manager"), who(db, people, "assessor")
    with frozen_at(NOW):
        with db.write(manager.actor) as session:
            central, enclave, backups, _ = world(session, people, manager)
            _, result = fail(session, manager, central, backups, operation="partly")
            own = raise_issue(
                session,
                manager,
                people.units["HALE"],
                "No inventory of removable media",
                subjects=[enclave.ref],
                requirements=[{"framework": "nist-csf", "code": "ID.AM-01"}],
                severity="critical",
            )
            issues.add_action(
                session,
                manager,
                own,
                title="Count them",
                owner_id=manager.account_id,
                due_on="2026-03-20",
            )
            raise_issue(session, manager, people.units["HALE"], "Unrelated to any scope")
        with db.write(assessor.actor) as session:
            assessments.review(
                session, assessor, session.get(TestResult, result.id), confirm=True, note=None
            )
            plan = issues.plan_of_action(
                session, assessor, records.load(session, assessor, SCOPE, enclave.ref)
            )
            # Most severe first: its own, then the one it inherits with the control.
            assert [(i["ref"], i["severity"]) for i in plan["issues"]] == [
                ("ISS-0001", "critical"),
                ("ISS-0003", "moderate"),
            ]
            assert plan["counts"] == {"critical": 1, "high": 0, "moderate": 1, "low": 0}
            first = plan["issues"][0]
            assert [a["title"] for a in first["actions"]] == ["Count them"]
            assert first["subjects"]["requirements"][0]["code"] == "ID.AM-01"
            central = records.load(session, assessor, SCOPE, central.ref)
            assert [
                i["ref"] for i in issues.plan_of_action(session, assessor, central)["issues"]
            ] == ["ISS-0003"]


def test_the_api_follows_an_issue_and_an_exception_from_start_to_finish(
    as_role: Clients, db: Database, loaded: None, people: People
) -> None:
    steward, assessor, leader, member = (
        as_role(r) for r in ("steward", "assessor", "leader", "member")
    )
    hale = people.units["HALE"]
    with db.write(who(db, people, "manager").actor) as session:
        _, enclave, backups, _ = world(session, people, who(db, people, "manager"))
    made = steward.post(
        "/api/v1/issues",
        json={
            "name": "Media not counted",
            "org_unit_id": hale,
            "severity": "high",
            "source_kind": "audit",
            "subjects": [enclave.ref],
            "owner_id": people.accounts["member"],
        },
    )
    assert made.status_code == 201
    data = made.json()["data"]
    assert (data["ref"], data["status"], data["source_kind"], data["due_days"]) == (
        "ISS-0001",
        "open",
        "audit",
        90,
    )
    assert [o["account_id"] for o in data["owners"]] == [people.accounts["member"]]
    assert (
        steward.post("/api/v1/issues", json={"name": "x", "org_unit_id": hale}).status_code == 422
    )
    # The member it was handed to is told, sees it, and works on it.
    assert member.get("/api/v1/notices/count").json()["data"] == {"unread": 1}
    listed = member.get("/api/v1/notices").json()
    assert listed["meta"]["unread"] == 1 and listed["data"][0]["href"] == "/issues/ISS-0001"
    assert member.post("/api/v1/notices/read", json={}).json()["data"] == {"marked": 1, "unread": 0}
    action = member.post(
        "/api/v1/issues/ISS-0001/actions",
        json={
            "title": "Count the media",
            "owner_id": people.accounts["member"],
            "due_on": "2031-01-01",
        },
    )
    assert action.status_code == 201 and action.json()["data"]["source"]["ref"] == "ISS-0001"
    assert (
        member.patch(
            f"/api/v1/actions/{action.json()['data']['ref']}", json={"status": "done"}
        ).status_code
        == 200
    )
    moved = member.post(
        "/api/v1/issues/ISS-0001/due-date",
        json={"due_on": "2031-02-01", "reason": "Stocktake is in January."},
    )
    assert moved.json()["data"]["moved"] == 1
    proposed = member.post(
        "/api/v1/issues/ISS-0001/closure",
        json={"note": "Counted and labelled.", "root_cause": "ownership"},
    )
    assert (
        proposed.json()["data"]["status"] == "proposed"
        and not proposed.json()["data"]["can_act"]["validate"]
    )
    # Its owner is refused by the service; a steward is refused by the route.
    assert (
        steward.post("/api/v1/issues/ISS-0001/validation", json={"confirm": True}).status_code
        == 403
    )
    closed = assessor.post("/api/v1/issues/ISS-0001/validation", json={"confirm": True})
    assert (
        closed.json()["data"]["status"] == "closed"
        and closed.json()["data"]["validated"]["by"] == "Assessor Person"
    )
    assert [
        i["ref"] for i in assessor.get("/api/v1/issues", params={"status": "live"}).json()["data"]
    ] == []
    assert [
        i["ref"]
        for i in assessor.get(
            "/api/v1/issues", params={"about": enclave.ref, "severity": "high"}
        ).json()["data"]
    ] == ["ISS-0001"]
    assert (
        assessor.get(f"/api/v1/scopes/{enclave.ref}/plan-of-action").json()["data"]["issues"] == []
    )
    told_titles = [
        e["title"] for e in assessor.get("/api/v1/issues/ISS-0001/history").json()["data"]
    ]
    assert "Added an action: Count the media" in told_titles
    assert (
        assessor.post("/api/v1/issues/ISS-0001/reopening", json={"reason": "Found more."}).json()[
            "data"
        ]["status"]
        == "open"
    )

    asked = steward.post(
        "/api/v1/exceptions",
        json={
            "control": backups.ref,
            "scope": enclave.ref,
            "justification": "Being replaced.",
            "expires_on": (date.today() + timedelta(days=60)).isoformat(),
        },
    )
    assert asked.status_code == 201 and asked.json()["data"]["state"] == "requested"
    assert asked.json()["data"]["can_act"] == {
        "decide": False,
        "asked": True,
        "withdraw": True,
        "renew": False,
    }
    assert (
        steward.post("/api/v1/exceptions/EXC-0001/decision", json={"approve": True}).status_code
        == 403
    )
    assert member.get("/api/v1/exceptions/EXC-0001").status_code == 404
    decided = leader.post(
        "/api/v1/exceptions/EXC-0001/decision", json={"approve": True, "note": "For now."}
    )
    assert (
        decided.json()["data"]["state"] == "in_force"
        and decided.json()["data"]["decided_by"] == "Leader Person"
    )
    assert [
        e["ref"]
        for e in leader.get(
            "/api/v1/exceptions", params={"state": "in_force", "scope": enclave.ref}
        ).json()["data"]
    ] == ["EXC-0001"]
    rows = leader.get(
        f"/api/v1/scopes/{enclave.ref}/requirements",
        params={"framework": "nist-csf", "state": "excepted"},
    ).json()["data"]
    assert rows["requirements"] == []  # in place underneath, so nothing needs excepting
    assert (
        steward.post(
            "/api/v1/exceptions/EXC-0001/withdrawal", json={"reason": "Not needed."}
        ).json()["data"]["state"]
        == "withdrawn"
    )
