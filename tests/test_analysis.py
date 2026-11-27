"""Risk analyses: walking what is in a scope against a list of threats, and raising or
refreshing risks as it goes."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.compliance import scopes
from riskwren.core.clock import frozen_at
from riskwren.core.errors import Conflict, Invalid, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import Notice, Risk, RiskAnalysisItem, RiskSubject
from riskwren.inventory import history, records
from riskwren.inventory.registry import SYSTEM
from riskwren.risk import analysis, register
from riskwren.risk.analysis import ANALYSIS
from riskwren.risk.register import RISK
from tests.people import People
from tests.test_risks import judge, raise_risk, who
from tests.test_scopes import add_scope

Clients = Callable[[str | None], TestClient]
NOON = datetime(2026, 3, 2, 12, tzinfo=UTC)
THREATS = ["ransomware", "research_data_loss"]


def stock(session, steward, hale: int):  # type: ignore[no-untyped-def]
    """Two systems in the lab, and one risk already on the register about the first."""
    monitor = records.create(
        session, steward, SYSTEM, {"name": "Freezer monitor", "kind": "device", "org_unit_id": hale}
    )
    sequencer = records.create(
        session, steward, SYSTEM, {"name": "Sequencer", "kind": "instrument", "org_unit_id": hale}
    )
    records.create(
        session, steward, SYSTEM,
        {"name": "Old reader", "kind": "instrument", "org_unit_id": hale, "status": "retired"},
    )  # fmt: skip
    known = raise_risk(session, steward, hale, "Ransomware: Hale Lab", category="availability",
                       library_key="ransomware")  # fmt: skip
    register.set_subjects(session, steward, known, [monitor.ref])
    judge(session, steward, known, "residual", 2, mission=3)
    return monitor, sequencer, known


def items_of(session, found) -> dict[tuple[str, str], RiskAnalysisItem]:  # type: ignore[no-untyped-def]
    rows = session.scalars(select(RiskAnalysisItem).where(RiskAnalysisItem.analysis_id == found.id))
    return {(row.subject_name, row.threat_key): row for row in rows}


def test_an_analysis_walks_each_thing_against_each_threat(db: Database, people: People) -> None:
    steward, member, assessor = (
        who(db, people, role) for role in ("steward", "member", "assessor")
    )
    hale, cancer = people.units["HALE"], people.units["CANCER"]
    with db.write(steward.actor) as session, frozen_at(NOON):
        monitor, sequencer, known = stock(session, steward, hale)
        ask = {"name": "Lab systems, spring", "org_unit_id": hale, "threats": THREATS}
        for values, field in [
            ({**ask, "threats": []}, "threats"),
            ({**ask, "threats": ["meteor_strike"]}, "threats"),
            ({**ask, "categories": ["nowhere"], "threats": []}, "categories"),
            ({**ask, "org_unit_id": cancer}, "org_unit_id"),  # nothing there to look at
            ({**ask, "scope": "SCP-0099"}, "scope"),
        ]:
            with pytest.raises(Invalid) as caught:
                analysis.start(session, steward, values)
            assert set(caught.value.errors) == {field}, values
        with pytest.raises(PermissionDenied):
            analysis.start(session, member, ask)
        # Only what is in use is looked at: the retired reader is left out.
        assert analysis.preview(session, steward, ask) == {"assets": 2, "threats": 2, "items": 4}
        whole = analysis.preview(
            session, steward, {**ask, "threats": [], "categories": ["technology"]}
        )
        assert whole["threats"] > 5
        found = analysis.start(session, assessor, ask)  # an assessor may lead one
        assert (found.ref, found.status) == ("RAN-0001", "open")
        shown = records.detail(session, steward, ANALYSIS, found)
        assert shown["counts"] == {"items": 4, "pending": 4, "considered": 0, "not_applicable": 0,
                                   "covered": 0, "raised": 0}  # fmt: skip
        assert [each["name"] for each in shown["assets"]] == ["Freezer monitor", "Sequencer"]

        # The risk already on the register about this thing, from this threat, is offered.
        page = analysis.asset(session, steward, found, monitor.ref)
        offered = {each["threat"]["key"]: each["suggested"] for each in page["items"]}
        assert [(each["ref"], each["concerns_this"]) for each in offered["ransomware"]] == [
            (known.ref, True)
        ]
        assert offered["research_data_loss"] == [] and page["next"] == sequencer.ref
        items = items_of(session, found)

        # Covered, and worth another look: the risk's rating is put in doubt and its owner told.
        with pytest.raises(Invalid):
            analysis.consider(session, steward, found, items[("Freezer monitor", "ransomware")],
                              {"outcome": "covered"})  # fmt: skip
        with pytest.raises(PermissionDenied):
            analysis.consider(session, member, found, items[("Freezer monitor", "ransomware")],
                              {"outcome": "not_applicable"})  # fmt: skip
        analysis.consider(
            session, assessor, found, items[("Freezer monitor", "ransomware")],
            {"outcome": "covered", "risk": known.ref, "look_again": True,
             "note": "The monitor is now on the main network."},
        )  # fmt: skip
        assert known.residual_in_doubt and "RAN-0001" in (known.residual_doubt_reason or "")
        told = session.scalars(
            select(Notice.text).where(Notice.account_id == steward.account_id)
        ).all()
        assert told[-1] == f"RAN-0001 asks for another look at {known.ref} Ransomware: Hale Lab."

        # Raised: a risk started from the library, about this thing, in its unit.
        analysis.consider(
            session,
            assessor,  # whoever leads the analysis may raise what it finds
            found,
            items[("Sequencer", "research_data_loss")],
            {"outcome": "raised", "note": "Runs are kept only on the instrument."},
        )
        item = items[("Sequencer", "research_data_loss")]
        raised = session.get(Risk, item.risk_id)
        assert raised is not None and raised.library_key == "research_data_loss"
        assert raised.name.endswith(": Sequencer") and raised.org_unit_id == hale and raised.cause
        # The thing's owner answers for the risk, and is told.
        owners = records.owners_of(session, RISK, [raised.id])[raised.id]
        assert [each["account_id"] for each in owners] == [steward.account_id]
        assert (
            session.scalars(select(Notice.text).where(Notice.account_id == steward.account_id))
            .all()[-1]
            .startswith(f"RAN-0001 raised {raised.ref}")
        )
        assert session.scalars(
            select(RiskSubject.subject_id).where(RiskSubject.risk_id == raised.id)
        ).all() == [sequencer.id]
        # A risk it now covers says it concerns the thing.
        analysis.consider(
            session,
            steward,
            found,
            items[("Sequencer", "ransomware")],
            {"outcome": "covered", "risk": known.ref},
        )
        about = register.subjects_of(session, steward, known)["records"]
        assert sorted(each["ref"] for each in about) == sorted([monitor.ref, sequencer.ref])

        # It cannot be closed while a question has no answer, nor without saying what it found.
        with pytest.raises(Invalid) as caught:
            analysis.close(session, steward, found, "Done")
        assert "1 question has no answer" in caught.value.errors["conclusion"]
        assert analysis.rest_do_not_apply(session, steward, found, monitor.ref, "No data held") == 1
        with pytest.raises(Invalid):
            analysis.close(session, steward, found, " ")
        analysis.close(session, steward, found, "One new risk; the monitor needs another look.")
        shown = records.detail(session, steward, ANALYSIS, found)
        assert shown["counts"] == {"items": 4, "pending": 0, "considered": 4, "not_applicable": 1,
                                   "covered": 2, "raised": 1}  # fmt: skip
        assert (shown["status"], shown["closed_by"], shown["can_work"], shown["can_reopen"]) == (
            "closed", "Steward Person", False, True,
        )  # fmt: skip
        with pytest.raises(Conflict):
            analysis.consider(session, steward, found, item, {"outcome": "not_applicable"})
        titles = [entry["title"] for entry in history.for_record(session, ANALYSIS, found)]
        assert titles[0] == "Closed the analysis"
        assert "A risk was raised: Loss of research data against Sequencer" in titles
        analysis.reopen(session, steward, found)
        analysis.consider(session, steward, found, item, {"outcome": "pending"})
        assert (item.outcome, item.risk_id, item.considered_at) == ("pending", None, None)
        assert session.get(Risk, raised.id) is not None  # a risk once raised stays on the register


def test_an_analysis_over_a_scope_takes_what_its_boundary_names(
    db: Database, people: People, as_role: Clients
) -> None:
    steward, manager = who(db, people, "steward"), who(db, people, "manager")
    hale, cancer = people.units["HALE"], people.units["CANCER"]
    with db.write(manager.actor) as session, frozen_at(NOON):
        monitor, _sequencer, _ = stock(session, steward, hale)
        vault = records.create(
            session, manager, SYSTEM, {"name": "Key store", "kind": "infrastructure",
                                       "org_unit_id": cancer, "restricted": True},
        )  # fmt: skip
        scope = add_scope(session, manager, people.units["IMM"], "Cold chain")
        scopes.set_members(session, manager, scope, [monitor.ref, vault.ref], [])
        scope_ref = scope.ref
    client = as_role("steward")
    ask = {"name": "Cold chain threats", "scope": scope_ref, "categories": ["availability"]}
    # The steward cannot see the restricted store, so her analysis does not look at it.
    sized = client.post("/api/v1/risk-analyses/preview", json=ask)
    assert sized.status_code == 200, sized.text
    assert sized.json()["data"]["assets"] == 1 and sized.json()["data"]["threats"] >= 2
    # A scope the member cannot see does not exist for them; a unit they can see is not
    # theirs to analyse.
    assert as_role("member").post("/api/v1/risk-analyses", json=ask).status_code == 422
    theirs = {"name": "Mine", "org_unit_id": hale, "threats": THREATS}
    assert as_role("member").post("/api/v1/risk-analyses", json=theirs).status_code == 403
    made = client.post("/api/v1/risk-analyses", json=ask)
    assert made.status_code == 201, made.text
    found = made.json()["data"]
    assert found["scope"]["ref"] == scope_ref and found["can_work"]
    assert [each["ref"] for each in found["assets"]] == [monitor.ref]
    page = client.get(f"/api/v1/risk-analyses/{found['ref']}/assets/{monitor.ref}").json()["data"]
    first = page["items"][0]
    answered = client.post(
        f"/api/v1/risk-analyses/{found['ref']}/items/{first['id']}",
        json={"outcome": "not_applicable", "note": "Battery backed"},
    )
    assert answered.status_code == 200, answered.text
    assert answered.json()["data"]["counts"]["considered"] == 1
    rest = client.post(
        f"/api/v1/risk-analyses/{found['ref']}/assets/{monitor.ref}/rest", json={"note": None}
    )
    assert rest.json()["meta"]["answered"] == len(page["items"]) - 1
    refused = client.post(f"/api/v1/risk-analyses/{found['ref']}/close", json={})
    assert refused.status_code == 422
    closed = client.post(
        f"/api/v1/risk-analyses/{found['ref']}/close", json={"conclusion": "Nothing new."}
    )
    assert closed.json()["data"]["status"] == "closed"
    # Anyone who may see it reads the report; only those who work it may change it.
    listed = as_role("auditor").get("/api/v1/risk-analyses", params={"status": "closed"})
    assert [each["ref"] for each in listed.json()["data"]] == [found["ref"]]
    assert listed.json()["data"][0]["considered"] == len(page["items"])
    assert (
        as_role("auditor").post(f"/api/v1/risk-analyses/{found['ref']}/reopen").status_code == 403
    )
    assert client.get(f"/api/v1/risk-analyses/{found['ref']}/assets/SYS-9999").status_code == 404
    assert RISK is not None
