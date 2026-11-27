"""Readiness: what is known about each control, turned into a state.

Nothing here is typed in. A control's state within a scope follows from where it stands
there, whether a test that still holds found it effective, and whether there is evidence
that still counts.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from riskwren.core.clock import utc_now
from riskwren.db.models import (
    Control,
    ControlRating,
    ControlTest,
    Evidence,
    EvidenceLink,
    TestResult,
)
from riskwren.program import rules


def assurance(session: Session, control_ids: list[int]) -> dict[int, dict[str, Any]]:
    """For each control: the result of a test that still holds, if there is one, and
    whether any evidence for it still counts."""
    today = utc_now().date()
    found: dict[int, dict[str, Any]] = {
        control_id: {"test": None, "tested_on": None, "evidence": False, "attested": None}
        for control_id in control_ids
    }
    if not control_ids:
        return found
    months = int(rules.get(session, "cadences").get("control_rating_months", 12))
    # What each control's owner last said of it, if that still holds. An attestation is the
    # owner's word: it is shown, and it can take a control out of verified, but it never puts
    # one there (AST-08).
    for control in session.scalars(
        select(Control).where(Control.id.in_(control_ids), Control.attested_at.is_not(None))
    ):
        when = control.attested_at.date()
        if rules.add_months(when, months) >= today:
            found[control.id]["attested"] = (control.attested_operates, when)
    for rating in session.scalars(
        select(ControlRating).where(
            ControlRating.control_id.in_(control_ids),
            ControlRating.superseded_by.is_(None),
            ControlRating.basis == "test",
        )
    ):
        tested_on: date = rating.rated_at.date()
        if rules.add_months(tested_on, months) < today:
            continue  # out of date: it no longer says anything
        worst = min(
            (rating.design, rating.operation),
            key=("ineffective", "partly", "effective").index,
        )
        found[rating.control_id].update(test=worst, tested_on=tested_on)
    current = (Evidence.status == "active", Evidence.valid_until >= today)
    on_control = session.execute(
        select(EvidenceLink.subject_id, func.count())
        .join(Evidence, Evidence.id == EvidenceLink.evidence_id)
        .where(
            EvidenceLink.subject_type == "control",
            EvidenceLink.subject_id.in_(control_ids),
            *current,
        )
        .group_by(EvidenceLink.subject_id)
    ).all()
    for control_id, _ in on_control:
        found[control_id]["evidence"] = True
    # Evidence cited by the result that counts is evidence for the control too.
    cited = session.execute(
        select(ControlTest.control_id)
        .join(TestResult, TestResult.test_id == ControlTest.id)
        .join(
            EvidenceLink,
            (EvidenceLink.subject_type == "test_result")
            & (EvidenceLink.subject_id == TestResult.id),
        )
        .join(Evidence, Evidence.id == EvidenceLink.evidence_id)
        .where(
            ControlTest.control_id.in_(control_ids),
            TestResult.review == "confirmed",
            TestResult.superseded_by.is_(None),
            *current,
        )
    ).all()
    for (control_id,) in cited:
        found[control_id]["evidence"] = True
    return found


def of_control(standing: str, known: dict[str, Any]) -> tuple[str, str]:
    """A control's state within a scope, and the reason in a few words."""
    test, when = known["test"], known["tested_on"]
    on = f" on {when.isoformat()}" if when else ""
    if test in ("partly", "ineffective"):
        word = "partly effective" if test == "partly" else "ineffective"
        return "failing", f"Tested{on} and found {word}"
    if standing != "in_place":
        return "planned", "Not yet in place here"
    said, said_on = known.get("attested") or (None, None)
    if test == "effective":
        if said in ("partly", "no") and when is not None and said_on > when:
            # A test found it working, and since then its owner has said otherwise. That is
            # not a failed test, and it is not something to go on calling verified.
            word = "only partly operates" if said == "partly" else "no longer operates"
            return "in_place", (
                f"Tested effective{on}, but its owner said on {said_on.isoformat()} that it {word}"
            )
        if known["evidence"]:
            return "verified", f"Tested effective{on}, with evidence that still counts"
        return "in_place", f"Tested effective{on}, but no evidence for it still counts"
    if said == "yes":
        return "in_place", (
            f"In place, and attested by its owner on {said_on.isoformat()}. "
            "No test result still holds"
        )
    if said in ("partly", "no"):
        word = "only partly operates" if said == "partly" else "does not operate"
        return "in_place", (
            f"Said to be in place, but its owner said on {said_on.isoformat()} that it {word}. "
            "No test result still holds"
        )
    return "in_place", "In place, with no test result that still holds"
