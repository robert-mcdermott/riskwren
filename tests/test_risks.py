"""The risk register: ratings that explain themselves, appetite, standing, and who sees what."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from riskwren.access.principal import Principal
from riskwren.core.clock import frozen_at
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import Risk, RiskAssessment, RiskLibraryEntry, ScoringMethod
from riskwren.inventory import access, history, records
from riskwren.inventory.registry import SYSTEM, find
from riskwren.people import accounts
from riskwren.program import packs, rules, settings
from riskwren.risk import categories, library, register
from riskwren.risk import method as methods
from riskwren.risk.register import RISK
from tests.conftest import Instance
from tests.people import ME, ROLES, People

Clients = Callable[[str | None], TestClient]
WHY = "Two failures in the last five years, and the alarm is not monitored out of hours."


def who(db: Database, people: People, role: str) -> Principal:
    with db.read() as session:
        return accounts.principal_for(session, accounts.get(session, people.accounts[role]))


def raise_risk(session, by: Principal, unit: int, name: str = "Freezer failure", **more):  # type: ignore[no-untyped-def]
    values = {"name": name, "category": "data_quality", "org_unit_id": unit, **more}
    return register.create(session, by, values)


def judge(session, by: Principal, risk: Risk, kind: str, likelihood: int, **levels: int):  # type: ignore[no-untyped-def]
    return register.assess(
        session, by, risk, kind=kind, likelihood=likelihood, impact_levels=levels, rationale=WHY
    )


# --- The program a new installation is given ----------------------------------------------


def test_a_new_installation_has_a_program(db: Database, people: People) -> None:
    with db.write(ME.actor) as session:
        row = methods.current_row(session)
        assert (row.version, row.status) == (1, "current")
        tree = categories.Tree(session)
        tops = [node["key"] for node in tree.view()]
        assert tops == [
            "strategic", "research", "clinical", "regulatory", "technology", "operations",
            "people", "financial", "third_party",
        ]  # fmt: skip
        # A category takes its appetite from above unless it has one of its own.
        specimens = categories.by_key(session, "data_quality")
        assert specimens.appetite is None and tree.appetite(specimens.id) == "moderate"
        assert tree.label(specimens.id) == (
            "Research and scientific integrity · Data and specimen integrity"
        )
        assert tree.appetite(categories.by_key(session, "medication").id) == "low"
        known = {row.key for row in tree.rows}
        entries = session.scalars(select(RiskLibraryEntry)).all()
        assert len(entries) >= 50 and {entry.category_key for entry in entries} <= known
        assert all(e.cause and e.event and e.consequence for e in entries)
        # Loading again adds nothing and changes nothing.
        assert set(packs.install(session).values()) == {0}
        assert rules.get(session, "cadences")["risk_review_months"]["critical"] == 3
        assert rules.add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
        assert rules.add_months(date(2026, 11, 30), 3) == date(2027, 2, 28)
        assert rules.add_months(date(2026, 6, 15), 24) == date(2028, 6, 15)


def test_the_library_can_be_searched(db: Database, people: People) -> None:
    with db.read() as session:
        found = library.search(session, query="FREEZER")
        assert [entry["key"] for entry in found] == ["specimen_loss"]
        assert found[0]["category_label"].endswith("Data and specimen integrity")
        research = library.search(session, category="research")
        assert {entry["category"] for entry in research} == {
            "integrity", "human_subjects", "animals", "data_quality", "research_security",
        }  # fmt: skip
        with pytest.raises(NotFound):
            library.by_key(session, "nothing")


# --- Raising a risk -----------------------------------------------------------------------


def test_raising_a_risk(db: Database, people: People) -> None:
    steward, hale = who(db, people, "steward"), people.units["HALE"]
    with db.write(steward.actor) as session:
        entry = library.by_key(session, "specimen_loss")
        risk = register.create(
            session, steward,
            {"name": entry.title, "cause": entry.cause, "event": entry.event,
             "consequence": entry.consequence, "category": entry.category_key,
             "org_unit_id": hale, "library_key": entry.key},
        )  # fmt: skip
        assert (risk.ref, risk.status, risk.standing) == ("RSK-0001", "open", "not_assessed")
        shown = records.detail(session, steward, RISK, risk)
        assert shown["category"] == "data_quality" and shown["appetite"] == "moderate"
        assert shown["ratings"]["residual"] == {"likelihood": None, "impact": None, "rating": None}
        assert [o["kind"] for o in shown["owners"]] == ["owner"]
        assert shown["library_key"] == "specimen_loss" and shown["event"].startswith("stored")
        # Until it is assessed, it is due for a first look within three months.
        assert shown["next_review_on"] == rules.add_months(risk.created_at.date(), 3)
        for values, field in [
            ({"name": "No category", "org_unit_id": hale}, "category"),
            ({"name": "Bad", "org_unit_id": hale, "category": "nonsense"}, "category"),
            ({"category": "ransomware", "org_unit_id": hale}, "name"),
        ]:
            with pytest.raises(Invalid) as caught:
                register.create(session, steward, values)
            assert field in caught.value.errors
    member = who(db, people, "member")
    with db.write(ME.actor) as session, pytest.raises(PermissionDenied):
        raise_risk(session, member, hale)
    with db.write(ME.actor) as session, pytest.raises(PermissionDenied):
        raise_risk(session, steward, people.units["CANCER"])  # not theirs to add to


# --- Assessing ----------------------------------------------------------------------------


def test_a_rating_explains_itself(db: Database, people: People) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        risk = raise_risk(session, steward, people.units["HALE"])
        made = judge(session, steward, risk, "inherent", 4, mission=5, financial=3, trust=4)
        assert (made.likelihood, made.impact, made.rating) == (4, 5, "critical")
        assert (risk.inherent_likelihood, risk.inherent_impact, risk.inherent_rating) == (
            4, 5, "critical",
        )  # fmt: skip
        shown = register.view_assessment(session, made)
        assert shown["likelihood_label"] == "Likely"
        assert shown["likelihood_definition"] == "Expected about once a year"
        assert (shown["impact_label"], shown["rating_label"], shown["ramp_level"]) == (
            "Severe", "Critical", 5,
        )  # fmt: skip
        # Each dimension rated shows its level and what that level means; the overall impact
        # is the highest of them, not the average.
        assert [(d["label"], d["level"], d["level_label"]) for d in shown["dimensions"]] == [
            ("Mission", 5, "Severe"), ("Financial", 3, "Moderate"), ("Trust", 4, "Major"),
        ]  # fmt: skip
        assert shown["dimensions"][0]["definition"].startswith("Irreplaceable material")
        assert (shown["assessed_by"], shown["rationale"], shown["method_version"]) == (
            "Steward Person", WHY, 1,
        )  # fmt: skip
        assert shown["suggested"] is None and not shown["superseded"]


def test_what_is_judged_is_checked(db: Database, people: People) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        risk = raise_risk(session, steward, people.units["HALE"])
        for values, fields in [
            ({"kind": "final", "likelihood": 3, "impact_levels": {"mission": 2}, "rationale": WHY},
             {"kind"}),
            ({"kind": "inherent", "likelihood": 9, "impact_levels": {}, "rationale": " "},
             {"likelihood", "impact_levels", "rationale"}),
            ({"kind": "inherent", "likelihood": 2, "impact_levels": {"mood": 3, "safety": 8},
              "rationale": WHY}, {"impact_levels"}),
            ({"kind": "inherent", "likelihood": "3", "impact_levels": {"safety": None},
              "rationale": WHY}, {"likelihood", "impact_levels"}),
        ]:  # fmt: skip
            with pytest.raises(Invalid) as caught:
                register.assess(session, steward, risk, **values)
            assert set(caught.value.errors) == fields
        assert session.execute(select(func.count()).select_from(RiskAssessment)).scalar_one() == 0


def test_an_assessment_is_superseded_and_never_changed(db: Database, people: People) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        risk = raise_risk(session, steward, people.units["HALE"])
        first = judge(session, steward, risk, "inherent", 4, mission=5)
        second = judge(session, steward, risk, "inherent", 3, mission=4)
        target = judge(session, steward, risk, "target", 2, mission=3)
        assert first.superseded_by == second.id and second.superseded_by is None
        assert target.superseded_by is None  # a different kind supersedes nothing
        assert (first.likelihood, first.impact, first.rating) == (4, 5, "critical")  # as it was
        assert risk.inherent_rating == "high" and risk.target_rating == "moderate"
        newest = register.latest(session, risk)
        assert (newest["inherent"], newest["residual"], newest["target"]) == (second, None, target)
        story = register.assessments(session, risk)
        assert [(a["kind"], a["rating"], a["superseded"]) for a in story] == [
            ("target", "moderate", False), ("inherent", "high", False),
            ("inherent", "critical", True),
        ]  # fmt: skip
    # A new version of the method changes no assessment already made.
    with db.write(ME.actor) as session:
        definition = copy.deepcopy(methods.current(session))
        definition["likelihood"][3]["definition"] = "Expected most years"
        definition["matrix"][4] = ["critical"] * 5
        published = methods.publish(session, ME, definition)
        assert published.version == 2
        assert session.scalars(select(ScoringMethod.status).order_by(ScoringMethod.id)).all() == [
            "superseded", "current",
        ]  # fmt: skip
        risk = find(session, RISK, "RSK-0001")
        old = register.assessments(session, risk)[-1]
        assert (old["method_version"], old["likelihood_definition"], old["rating"]) == (
            1, "Expected about once a year", "critical",
        )  # fmt: skip
        again = judge(session, ME, risk, "inherent", 1, mission=5)
        assert again.rating == "critical"  # under the new matrix
        assert register.view_assessment(session, again)["method_version"] == 2
        broken = copy.deepcopy(definition)
        broken["matrix"].pop()
        with pytest.raises(Invalid, match="cannot be used"):
            methods.publish(session, ME, broken)
        with pytest.raises(PermissionDenied):
            methods.publish(session, who(db, people, "steward"), definition)


def test_who_may_assess(db: Database, people: People) -> None:
    with db.write(ME.actor) as session:
        risk = raise_risk(session, who(db, people, "steward"), people.units["HALE"])
        for role, allowed in [
            ("steward", True),  # looks after the unit
            ("manager", True),
            ("assessor", True),  # an assessor for the whole organization
            ("member", False),
            ("leader", False),  # a leader accepts; they do not assess
            ("auditor", False),
            ("admin", False),
        ]:
            principal = who(db, people, role)
            if allowed:
                assert judge(session, principal, risk, "inherent", 3, safety=3), role
            else:
                with pytest.raises(PermissionDenied):
                    judge(session, principal, risk, "inherent", 3, safety=3)


# --- Appetite, standing, and dates --------------------------------------------------------


def test_standing_follows_rating_and_appetite(db: Database, people: People) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session, frozen_at(datetime(2026, 3, 10, tzinfo=UTC)):
        risk = raise_risk(session, steward, people.units["HALE"])  # appetite: moderate
        judge(session, steward, risk, "inherent", 4, mission=5)
        assert risk.standing == "not_assessed"  # the inherent rating alone says nothing of it
        judge(session, steward, risk, "residual", 3, mission=3)
        assert (risk.residual_rating, risk.standing) == ("moderate", "within")
        assert risk.next_review_on == date(2027, 3, 10)  # moderate: every twelve months
        judge(session, steward, risk, "residual", 3, mission=4)
        assert (risk.residual_rating, risk.standing) == ("high", "needs_decision")
        assert risk.next_review_on == date(2026, 9, 10)  # high: every six
    with db.write(ME.actor) as session:
        risk = find(session, RISK, "RSK-0001")
        other = raise_risk(
            session, ME, people.units["HALE"], "Phishing", category="confidentiality"
        )
        judge(session, ME, other, "residual", 3, trust=4)
        assert other.standing == "needs_decision"  # technology's appetite is moderate too
        # Raising one category's appetite changes the standing of its risks and no others.
        research = categories.by_key(session, "research")
        categories.update(session, ME, research, {"appetite": "high"})
        assert register.refresh_category(session, research.id) == 1
        assert (risk.standing, other.standing) == ("within", "needs_decision")
        assert (risk.residual_rating, risk.next_review_on) == ("high", date(2026, 9, 10))
        # A category may hold its own appetite, tighter than the one above it.
        specimens = categories.by_key(session, "data_quality")
        categories.update(session, ME, specimens, {"appetite": "low"})
        register.refresh_category(session, specimens.id)
        assert risk.standing == "needs_decision"
        for changes, field in [
            ({"appetite": "enormous"}, "appetite"),
            ({"name": ""}, "name"),
            ({"status": "gone"}, "status"),
        ]:
            with pytest.raises(Invalid) as caught:
                categories.update(session, ME, specimens, changes)
            assert field in caught.value.errors
        with pytest.raises(Invalid, match="not saved") as caught:
            categories.update(session, ME, research, {"appetite": None})
        assert "top of the tree" in caught.value.errors["appetite"]
        with pytest.raises(PermissionDenied):
            categories.update(session, who(db, people, "steward"), specimens, {"name": "Mine"})


def test_a_review_falls_overdue_and_a_closed_risk_does_not(db: Database, people: People) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session, frozen_at(datetime(2026, 1, 15, tzinfo=UTC)):
        risk = raise_risk(session, steward, people.units["HALE"])
        judge(session, steward, risk, "residual", 4, mission=5)  # critical: every three months
        assert risk.next_review_on == date(2026, 4, 15)
        assert not register.flags(risk, date(2026, 4, 15))["review_overdue"]
        assert register.flags(risk, date(2026, 4, 16))["review_overdue"]
    with db.write(steward.actor) as session, frozen_at(datetime(2026, 6, 1, tzinfo=UTC)):
        risk = find(session, RISK, "RSK-0001")
        overdue, _ = records.search(session, steward, RISK, {"overdue": True})
        assert [row.ref for row in overdue] == ["RSK-0001"]
        with pytest.raises(Invalid) as caught:
            register.update(session, steward, risk, {"status": "closed"}, version=risk.version)
        assert "closed_reason" in caught.value.errors
        register.update(
            session, steward, risk,
            {"status": "closed", "closed_reason": "The collection moved to another site."},
            version=risk.version,
        )  # fmt: skip
        assert (risk.standing, risk.next_review_on) == ("closed", None)
        assert not register.flags(risk)["review_overdue"]
        assert records.search(session, steward, RISK, {"overdue": True})[1] == 0
        with pytest.raises(Conflict, match="closed"):
            judge(session, steward, risk, "residual", 2, mission=2)
        register.update(session, steward, risk, {"status": "open"}, version=risk.version)
        assert (risk.standing, risk.closed_reason) == ("needs_decision", None)
        assert risk.next_review_on == date(2026, 4, 15)  # from the judgment still on record


# --- Who sees what ------------------------------------------------------------------------

# Three risks: one ordinary in the Hale Lab, one ordinary in Cancer Biology, and one
# restricted in the Hale Lab. Unlike the inventory, the register follows the setting.
EVERY = {"hale", "cancer", "sealed"}
SIGHT = {
    "open": {
        "admin": EVERY, "manager": EVERY, "auditor": EVERY,
        "assessor": {"hale", "cancer"},  # never what is restricted
        "leader": EVERY, "steward": EVERY,  # their division's restricted risk, and the rest
        "member": {"hale", "cancer"},
    },
    "unit": {
        "admin": EVERY, "manager": EVERY, "auditor": EVERY,
        "assessor": {"hale", "cancer"},
        "leader": {"hale", "sealed"}, "steward": {"hale", "sealed"},
        "member": {"hale"},  # works in the Hale Lab
    },
    "assigned": {
        "admin": EVERY, "manager": EVERY, "auditor": EVERY,
        "assessor": {"hale", "cancer"},
        "leader": {"hale", "sealed"}, "steward": {"hale", "sealed"},
        "member": set(),
    },
}  # fmt: skip


@pytest.mark.parametrize("setting", ["open", "unit", "assigned"])
def test_who_sees_which_risks(db: Database, people: People, setting: str) -> None:
    with db.write(ME.actor) as session:
        settings.put(session, access.VISIBILITY_SETTING, setting)
        names = {
            raise_risk(session, ME, people.units["HALE"], "Hale").ref: "hale",
            raise_risk(session, ME, people.units["CANCER"], "Cancer").ref: "cancer",
            raise_risk(session, ME, people.units["HALE"], "Sealed", restricted=True).ref: "sealed",
        }
    for role in ROLES:
        principal = who(db, people, role)
        with db.read() as session:
            one_by_one = {
                names[risk.ref]
                for risk in session.scalars(select(Risk))
                if access.can_see(session, principal, RISK, risk)
            }
            rows, total = records.search(session, principal, RISK, {}, sort="name")
            assert total == len(rows)
        assert one_by_one == SIGHT[setting][role], f"{setting}, {role}: single risks"
        assert {names[row.ref] for row in rows} == one_by_one, f"{setting}, {role}: the list"


# --- What a risk concerns, and where it sits ----------------------------------------------


def test_a_risk_concerns_things(db: Database, people: People) -> None:
    steward, manager, member = (who(db, people, r) for r in ("steward", "manager", "member"))
    hale, cancer = people.units["HALE"], people.units["CANCER"]
    with db.write(ME.actor) as session:
        monitor = records.create(
            session, steward, SYSTEM, {"name": "Monitor", "kind": "device", "org_unit_id": hale}
        )
        vault = records.create(
            session, manager, SYSTEM,
            {"name": "Vault", "kind": "data_store", "org_unit_id": cancer, "restricted": True},
        )  # fmt: skip
        risk = raise_risk(session, steward, hale)
        other = raise_risk(session, steward, hale, "Another")
        register.set_subjects(session, manager, risk, [monitor.ref, vault.ref, monitor.ref])
        assert [s["ref"] for s in register.subjects_of(session, manager, risk)["records"]] == [
            monitor.ref, vault.ref,
        ]  # fmt: skip
        # The steward cannot see the restricted system: it is counted, and it is not theirs
        # to remove by leaving it out.
        seen = register.subjects_of(session, steward, risk)
        assert [s["ref"] for s in seen["records"]] == [monitor.ref] and seen["hidden"] == 1
        register.set_subjects(session, steward, risk, [])
        assert register.subjects_of(session, manager, risk)["records"][0]["ref"] == vault.ref
        register.set_subjects(session, steward, risk, [monitor.ref])
        for refs, message in [
            ([vault.ref], "There is no record"),  # what they cannot see is not there
            (["SYS-9999"], "There is no"),
            ([other.ref], "concerns processes, systems, and third parties"),
        ]:
            with pytest.raises(Invalid) as caught:
                register.set_subjects(session, steward, risk, refs)
            assert message in caught.value.errors["subjects"]
        with pytest.raises(PermissionDenied):
            register.set_subjects(session, member, risk, [monitor.ref])
        # And each thing can be asked for its risks.
        about, _ = records.search(session, steward, RISK, {"subject": monitor.ref})
        assert [row.ref for row in about] == [risk.ref]
        with pytest.raises(NotFound):
            records.search(session, steward, RISK, {"subject": vault.ref})


def test_roll_up_and_escalation(db: Database, people: People) -> None:
    steward, leader, member = (who(db, people, r) for r in ("steward", "leader", "member"))
    hale, immuno, cancer, top = (people.units[c] for c in ("HALE", "IMM", "CANCER", "NMI"))
    with db.write(ME.actor) as session:
        lab = raise_risk(session, steward, hale, "In the lab")
        division = raise_risk(session, steward, immuno, "In the division")
        elsewhere = raise_risk(session, ME, cancer, "Elsewhere")
        # A leader sees their unit's risks and those beneath it, and no others.
        mine, _ = records.search(session, leader, RISK, {}, sort="name")
        assert [row.ref for row in mine] == [division.ref, lab.ref]
        under, _ = records.search(session, ME, RISK, {"unit": immuno}, sort="name")
        assert [row.ref for row in under] == [division.ref, lab.ref]
        at_division, _ = records.search(session, ME, RISK, {"at": immuno})
        assert [row.ref for row in at_division] == [division.ref]

        for unit, reason, field in [
            (cancer, "It is serious.", "unit_id"),  # not above the lab
            (hale, "It is serious.", "unit_id"),  # nor the lab itself
            (immuno, " ", "reason"),
        ]:
            with pytest.raises(Invalid) as caught:
                register.escalate(session, steward, lab, unit, reason)
            assert field in caught.value.errors
        with pytest.raises(PermissionDenied):
            register.escalate(session, member, lab, immuno, "Please look.")
        register.escalate(session, leader, lab, immuno, "It needs the division's budget.")
        assert lab.escalated_to_unit_id == immuno
        at_division, _ = records.search(session, ME, RISK, {"at": immuno}, sort="name")
        assert [row.ref for row in at_division] == [division.ref, lab.ref]
        shown = records.detail(session, leader, RISK, lab)
        assert shown["escalation_reason"] == "It needs the division's budget."
        assert shown["can_escalate"] and not shown["can"]["edit"]
        register.escalate(session, steward, lab, top, "And now the institute's.")
        assert records.search(session, ME, RISK, {"at": immuno})[1] == 1
        register.escalate(session, steward, lab, None, None)
        assert (lab.escalated_to_unit_id, lab.escalation_reason) == (None, None)
        assert elsewhere.ref not in {r.ref for r in mine}


def test_the_register_sorts_by_what_is_at_stake(db: Database, people: People) -> None:
    hale = people.units["HALE"]
    with db.write(ME.actor) as session:
        made = {}
        for name, likelihood, impact in [("b", 3, 3), ("a", 5, 5), ("c", 1, 1), ("d", 4, 4)]:
            made[name] = raise_risk(session, ME, hale, name)
            judge(session, ME, made[name], "residual", likelihood, safety=impact)
        unrated = raise_risk(session, ME, hale, "e")
        # Ratings sort by their order (critical first), not by their spelling; what has no
        # rating comes last either way.
        rows, _ = records.search(session, ME, RISK, {}, sort="-residual_rating")
        assert [row.name for row in rows] == ["a", "d", "b", "c", "e"]
        rows, _ = records.search(session, ME, RISK, {}, sort="residual_rating")
        assert [row.name for row in rows] == ["c", "b", "d", "a", "e"]
        for filters, names in [
            ({"residual_rating": "high"}, ["d"]),
            ({"standing": "needs_decision"}, ["a", "d"]),
            ({"above_appetite": True}, ["a", "d"]),
            ({"standing": "not_assessed"}, ["e"]),
            ({"category": "research"}, ["a", "b", "c", "d", "e"]),
            ({"category": "technology"}, []),
            ({"residual_likelihood": 4, "residual_impact": 4}, ["d"]),
            ({"q": "RSK-0003"}, ["c"]),
        ]:
            rows, total = records.search(session, ME, RISK, filters, sort="name")
            assert [row.name for row in rows] == names and total == len(names), filters
        assert unrated.standing == "not_assessed"


# --- History ------------------------------------------------------------------------------


def test_a_risks_history_reads_like_a_story(db: Database, people: People) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        monitor = records.create(
            session, steward, SYSTEM,
            {"name": "Monitor", "kind": "device", "org_unit_id": people.units["HALE"]},
        )  # fmt: skip
        risk = raise_risk(session, steward, people.units["HALE"])
        judge(session, steward, risk, "inherent", 4, mission=5)
        judge(session, steward, risk, "residual", 3, mission=4)
        register.set_subjects(session, steward, risk, [monitor.ref])
        register.escalate(session, steward, risk, people.units["IMM"], "It needs funding.")
    with db.read() as session:
        story = history.for_record(session, RISK, find(session, RISK, "RSK-0001"))
    titles = [entry["title"] for entry in story]
    assert titles[0] == "Edited" and titles[1] == "Now concerns SYS-0001 Monitor"
    assert "Assessed the residual risk as High" in titles
    assert "Assessed the inherent risk as Critical" in titles
    assert titles[-1] == "Added this risk"
    escalated = {line["label"]: line["after"] for line in story[0]["lines"]}
    assert escalated == {"Escalated to": "Immunology", "Why it was escalated": "It needs funding."}
    standing = [line for entry in story for line in entry["lines"] if line["label"] == "Standing"]
    assert (standing[0]["before"], standing[0]["after"]) == ("Not assessed", "Needs decision")


# --- Moving a program ---------------------------------------------------------------------


def test_a_program_exports_and_imports(db: Database, people: People) -> None:
    with db.write(ME.actor) as session:
        pack = packs.export(session)
        assert packs.problems(pack) == []
        assert packs.import_(session, ME, pack) == {"dry_run": False, "changed": []}
        changed = copy.deepcopy(pack)
        changed["categories"][0]["appetite"] = "moderate"
        changed["categories"].append({"key": "mission", "name": "Mission", "appetite": "low"})
        changed["cadences"]["risk_review_months"]["high"] = 4
        changed["scoring_method"]["ratings"][0]["label"] = "Minor"
        changed["vocabularies"]["criticalities"][0]["label"] = "Slight"
        preview = packs.import_(session, ME, changed, dry_run=True)
        assert preview["dry_run"] and preview["changed"] == [
            "vocabulary criticalities", "scoring method", "category strategic",
            "category mission (new)", "cadences",
        ]  # fmt: skip
        assert packs.export(session) == pack  # a dry run changes nothing
        assert packs.import_(session, ME, changed)["changed"] == preview["changed"]
        after = packs.export(session)
        assert after["categories"][-1]["key"] == "mission"
        assert after["cadences"]["risk_review_months"]["high"] == 4
        assert methods.current_row(session).version == 2
        # A pack is loaded whole or not at all, and says everything that is wrong with it.
        broken = copy.deepcopy(pack)
        broken["scoring_method"]["matrix"][0][0] = "enormous"
        broken["categories"][1]["appetite"] = "enormous"
        broken["categories"].append(copy.deepcopy(broken["categories"][0]))
        broken["vocabularies"]["colors"] = []
        broken["cadences"]["risk_review_months"].pop("low")
        with pytest.raises(Invalid) as caught:
            packs.import_(session, ME, broken)
        message = caught.value.errors["pack"]
        for part in ("matrix", "appetite of research", "appears twice", "colors", "cadence"):
            assert part in message, part
        assert packs.export(session) == after
        with pytest.raises(Invalid, match="not loaded"):
            packs.import_(session, ME, {"pack": {"kind": "framework"}})
        with pytest.raises(PermissionDenied):
            packs.import_(session, who(db, people, "steward"), pack)


def test_a_program_moves_from_the_command_line(
    instance: Instance, people: People, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from riskwren.cli import main

    def run(*args: str) -> int:
        return main(["--config", str(instance.path), *args])

    out = tmp_path / "program.json"
    assert run("program", "export", "--output", str(out)) == 0
    pack = json.loads(out.read_text("utf-8"))
    assert pack["pack"]["kind"] == "program" and len(pack["categories"]) == 9
    capsys.readouterr()
    assert run("program", "import", str(out)) == 0
    assert "Nothing to change" in capsys.readouterr().out
    pack["categories"][0]["name"] = "Strategy"
    out.write_text(json.dumps(pack), encoding="utf-8")
    assert run("program", "import", str(out), "--dry-run") == 0
    assert "Would change:\n  category strategic" in capsys.readouterr().out
    assert run("program", "import", str(out)) == 0
    assert "Changed:\n  category strategic" in capsys.readouterr().out
    pack["scoring_method"]["matrix"] = []
    out.write_text(json.dumps(pack), encoding="utf-8")
    assert run("program", "import", str(out)) == 1
    assert "matrix" in capsys.readouterr().err
    assert run("program", "import", str(tmp_path / "missing.json")) == 1
    capsys.readouterr()
    assert run("program", "export") == 0
    assert json.loads(capsys.readouterr().out)["categories"][0]["name"] == "Strategy"


# --- The API ------------------------------------------------------------------------------


def test_the_register_through_the_api(as_role: Clients, people: People) -> None:
    steward, member, manager, leader = (
        as_role(role) for role in ("steward", "member", "manager", "leader")
    )
    hale = people.units["HALE"]

    program = member.get("/api/v1/program").json()["data"]
    assert program["method"]["version"] == 1 and len(program["method"]["matrix"]) == 5
    assert [r["ramp_level"] for r in program["method"]["ratings"]] == [1, 2, 4, 5]
    assert program["categories"][1]["children"][3]["appetite_in_force"] == "moderate"
    entry = member.get("/api/v1/risk-library", params={"q": "ransom"}).json()["data"][0]
    assert entry["key"] == "ransomware"

    made = steward.post(
        "/api/v1/risks",
        json={"name": entry["title"], "cause": entry["cause"], "event": entry["event"],
              "consequence": entry["consequence"], "category": entry["category"],
              "org_unit_id": hale, "library_key": entry["key"]},
    )  # fmt: skip
    assert made.status_code == 201
    risk = made.json()["data"]
    path = f"/api/v1/risks/{risk['ref']}"
    assert risk["standing"] == "not_assessed" and risk["category_label"].endswith("systems")
    assert member.post("/api/v1/risks", json={"name": "x"}).status_code == 403

    refused = steward.post(
        f"{path}/assessments",
        json={"kind": "inherent", "likelihood": 4, "impact_levels": {}, "rationale": ""},
    )
    assert refused.status_code == 422
    assert {e["location"][0] for e in refused.json()["errors"]} == {"impact_levels", "rationale"}
    judged = steward.post(
        f"{path}/assessments",
        json={"kind": "inherent", "likelihood": 4,
              "impact_levels": {"mission": 4, "trust": 5, "financial": None}, "rationale": WHY},
    )  # fmt: skip
    assert judged.status_code == 201
    assert judged.json()["data"]["ratings"]["inherent"] == {
        "likelihood": 4, "impact": 5, "rating": "critical",
    }  # fmt: skip
    again = steward.post(
        f"{path}/assessments",
        json={"kind": "residual", "likelihood": 2, "impact_levels": {"trust": 4}, "rationale": WHY},
    ).json()["data"]
    assert (again["ratings"]["residual"]["rating"], again["standing"]) == ("moderate", "within")
    assert again["assessments"]["residual"]["assessed_by"] == "Steward Person"
    assert again["assessments"]["inherent"]["dimensions"][1]["label"] == "Trust"
    listed = member.get(f"{path}/assessments").json()
    assert [a["kind"] for a in listed["data"]] == ["residual", "inherent"]
    assert listed["meta"]["suggestion"]["rating"] == "critical"  # no controls yet: no reduction
    # A member of the lab may read the risk and may not judge it. Nothing changes a judgment.
    assert member.post(f"{path}/assessments", json={
        "kind": "target", "likelihood": 1, "impact_levels": {"trust": 1}, "rationale": WHY,
    }).status_code == 403  # fmt: skip
    for method in ("PATCH", "PUT", "DELETE"):
        assert steward.request(method, f"{path}/assessments").status_code == 405
        assert steward.request(method, f"{path}/assessments/1").status_code in (404, 405)

    page = member.get("/api/v1/risks", params={"category": "technology"}).json()
    assert page["meta"]["total"] == 1 and page["data"][0]["ratings"]["residual"]["likelihood"] == 2
    assert member.get("/api/v1/risks", params={"standing": "needs_decision"}).json()["data"] == []
    assert steward.patch(path, json={"summary": "Mine"}).status_code == 409
    version = again["version"]
    closed = steward.patch(path, json={"status": "closed", "version": version})
    assert closed.status_code == 422
    shut = steward.patch(
        path, json={"status": "closed", "closed_reason": "Retired.", "version": version}
    ).json()["data"]
    assert (shut["status"], shut["standing"], shut["next_review_on"]) == ("closed", "closed", None)

    escalated = leader.put(
        f"{path}/escalation", json={"unit_id": people.units["IMM"], "reason": "Needs funding."}
    )
    assert escalated.status_code == 200
    assert escalated.json()["data"]["escalated_to_unit_id"] == people.units["IMM"]
    assert member.put(f"{path}/escalation", json={"unit_id": None}).status_code == 403
    assert steward.put(f"{path}/subjects", json={"subjects": ["SYS-0404"]}).status_code == 422
    story = steward.get(f"{path}/history").json()["data"]
    assert story[-1]["title"] == "Added this risk"

    # Appetite is the program's to set, and changing it says how many risks it moved.
    assert steward.patch("/api/v1/risk-categories/technology", json={"appetite": "low"}
                         ).status_code == 403  # fmt: skip
    moved = manager.patch("/api/v1/risk-categories/technology", json={"appetite": "low"}).json()
    assert moved["meta"]["risks_whose_standing_changed"] == 0  # the one risk there is closed
    assert moved["data"][4]["appetite"] == "low"
    assert manager.patch("/api/v1/risk-categories/nothing", json={}).status_code == 404
