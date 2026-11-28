"""Changing the program where it is used, and seeing first what a change would do (RSK-14).

A change to the scoring method, to appetite, or to the cadences can move risks: a rating
is read from the matrix, a standing from appetite, a review date from the cadence. One
function makes the change and reports every risk it moved. A preview is that same function
with its work thrown away afterwards, so what is published is exactly what was previewed.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core import scoring
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.db.models import PolicyDocument, Risk, RiskAssessment
from riskwren.db.models.risk import ASSESSMENT_KINDS
from riskwren.events import audit
from riskwren.program import rules, vocab
from riskwren.risk import categories, register
from riskwren.risk import method as methods

WATCHED = {
    "inherent_rating": "Inherent rating",
    "residual_rating": "Residual rating",
    "target_rating": "Target rating",
    "standing": "Standing",
    "next_review_on": "Next review",
}
METHOD_PARTS = (
    "title", "likelihood", "impact_levels", "dimensions", "ratings", "matrix", "control_effect",
)  # fmt: skip
MONTHS = (1, 120)
DAYS = (1, 1825)


def _snapshot(session: Session) -> dict[int, dict[str, Any]]:
    return {
        risk.id: {name: getattr(risk, name) for name in WATCHED}
        for risk in session.scalars(select(Risk).where(Risk.status != "closed"))
    }


def _whole(value: Any, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def cadence_problems(session: Session, doc: Any, ratings: list[str]) -> dict[str, str]:
    """Everything wrong with a table of cadences, by the part it is wrong in."""
    found: dict[str, str] = {}
    if not isinstance(doc, dict):
        return {"cadences": "Send the whole table of cadences."}
    reviews = doc.get("risk_review_months")
    if (
        not isinstance(reviews, dict)
        or set(reviews) != set(ratings)
        or not all(_whole(value, *MONTHS) for value in reviews.values())
    ):
        found["risk_review_months"] = (
            "Give a number of months, from 1 to 120, for each rating: " + ", ".join(ratings) + "."
        )
    else:
        order = [reviews[key] for key in ratings]  # lowest rating first
        if any(later > earlier for earlier, later in itertools.pairwise(order)):
            found["risk_review_months"] = "A higher rating is never reviewed less often."
    for name, label in (
        ("unrated_risk_review_months", "how soon an unrated risk is due"),
        ("control_rating_months", "how long a control's rating stands"),
        ("key_control_test_months", "how often a key control is tested"),
        ("exception_max_months", "how long an exception may run"),
        ("document_review_months", "how often a document is reviewed"),
        ("plan_exercise_months", "how often a continuity plan is exercised"),
    ):
        if not _whole(doc.get(name), *MONTHS):
            found[name] = f"Give {label} as a number of months, from 1 to 120."
    severities = vocab.keys(session, "issue_severities", active_only=False)
    due = doc.get("issue_due_days")
    if (
        not isinstance(due, dict)
        or set(due) != set(severities)
        or not all(_whole(value, *DAYS) for value in due.values())
    ):
        found["issue_due_days"] = "Give a number of days, from 1 to 1825, for each severity."
    else:
        order = [due[key] for key in severities]  # most severe first
        if any(later < earlier for earlier, later in itertools.pairwise(order)):
            found["issue_due_days"] = "A more severe issue is never given longer."
    reminders = doc.get("reminders")
    if not isinstance(reminders, dict) or not all(
        _whole(reminders.get(key), 0, 365)
        for key in ("soon_days", "steward_after_days", "leader_after_days")
    ):
        found["reminders"] = "Give each reminder as a number of days, from 0 to 365."
    elif reminders["leader_after_days"] < reminders["steward_after_days"]:
        found["reminders"] = "The leader is told after the steward, not before."
    unknown = set(doc) - {
        "risk_review_months", "unrated_risk_review_months", "control_rating_months",
        "key_control_test_months", "exception_max_months", "issue_due_days", "reminders",
        "document_review_months", "plan_exercise_months",
    }  # fmt: skip
    if unknown:
        found["cadences"] = f"{sorted(unknown)[0]!r} is not a cadence."
    return found


def _method_problems(session: Session, definition: Any) -> list[str]:
    """What stops a method being published here, beyond its own shape: what is already on
    record has to keep its meaning."""
    if not isinstance(definition, dict):
        return ["Send the whole scoring method."]
    found = scoring.problems(definition)
    if found:
        return found
    now = methods.current(session)
    gone = [key for key in scoring.rating_keys(now) if key not in scoring.rating_keys(definition)]
    if gone:
        found.append(
            f"The rating {gone[0]!r} cannot be removed or given another key: appetite, "
            "acceptances, and people's limits refer to it. Change its name and meaning."
        )
    elif scoring.rating_keys(now) != scoring.rating_keys(definition):
        found.append("Ratings are added by a program pack, where everything that names them "
                     "can be changed together.")  # fmt: skip
    for axis, column in (
        ("likelihood", RiskAssessment.likelihood),
        ("impact", RiskAssessment.impact),
    ):
        highest = session.execute(
            select(func.max(column)).where(RiskAssessment.superseded_by.is_(None))
        ).scalar_one()
        if highest and highest > len(scoring.levels(definition, axis)):
            found.append(
                f"Risks are rated at {axis} level {highest}, which this method does not have."
            )
    return found


def settle(session: Session) -> None:
    """Read every open risk again under the program in force: its ratings from the matrix,
    then its standing and its next review. Assessments keep the rating they were given."""
    method = methods.current(session)
    for risk in session.scalars(select(Risk).where(Risk.status != "closed").order_by(Risk.id)):
        for kind in ASSESSMENT_KINDS:
            likelihood = getattr(risk, f"{kind}_likelihood")
            impact = getattr(risk, f"{kind}_impact")
            if not (likelihood and impact):
                continue
            rating = scoring.rating(method, likelihood, impact)
            if getattr(risk, f"{kind}_rating") != rating:
                setattr(risk, f"{kind}_rating", rating)
                risk.version += 1
                risk.updated_at = utc_now()
        register.refresh(session, risk)


def _redate_documents(session: Session) -> int:
    """Documents that follow the program's review cadence take their next review from it.
    Returns how many moved."""
    from riskwren.policy import documents

    moved = 0
    for document in session.scalars(
        select(PolicyDocument).where(
            PolicyDocument.status == "active", PolicyDocument.review_months.is_(None)
        )
    ):
        due = documents.next_review(session, document)
        if document.next_review_on != due:
            document.next_review_on = due
            moved += 1
    session.flush()
    return moved


def change(session: Session, principal: Principal, changes: Mapping[str, Any]) -> dict[str, Any]:
    """Change the scoring method, appetites, or cadences, and say which risks moved. Checked
    whole before anything is changed. To preview, call this and roll the session back."""
    if not principal.configures:
        raise PermissionDenied("Only those who run the program can change it.")
    definition, appetites, cadences = (
        changes.get("method"), changes.get("appetites") or {}, changes.get("cadences"),
    )  # fmt: skip
    errors: dict[str, str] = {}
    if isinstance(definition, dict):
        # What the app adds when it shows a method is not part of the method.
        definition = {key: definition[key] for key in METHOD_PARTS if key in definition}
        definition["ratings"] = [
            {key: value for key, value in rating.items() if key != "ramp_level"}
            if isinstance(rating, dict) else rating
            for rating in definition.get("ratings") or []
        ]  # fmt: skip
    if definition is not None:
        found = _method_problems(session, definition)
        if found:
            errors["method"] = " ".join(found)
    ratings = scoring.rating_keys(definition if definition and "method" not in errors
                                  else methods.current(session))  # fmt: skip
    rows = {}
    tree = categories.Tree(session)
    for key, appetite in appetites.items():
        row = next((each for each in tree.rows if each.key == key), None)
        if row is None:
            errors["appetites"] = f"There is no risk category {key!r}."
        elif appetite is not None and appetite not in ratings:
            errors["appetites"] = f"Choose one of the ratings: {', '.join(ratings)}."
        elif appetite is None and row.parent_id is None:
            errors["appetites"] = f"{row.name} is at the top of the tree and needs an appetite."
        else:
            rows[key] = row
    if cadences is not None:
        errors.update(cadence_problems(session, cadences, ratings))
    if errors:
        raise Invalid("The program was not changed.", errors)
    if definition is None and not rows and cadences is None:
        raise Invalid("The program was not changed.", {"changes": "Nothing was changed."})

    before = _snapshot(session)
    said = []
    with audit.operation(session, "program.change"):
        if definition is not None and definition != methods.current(session):
            row = methods.publish(session, principal, definition)
            said.append(f"scoring method version {row.version}")
        for key, category in rows.items():
            if category.appetite != appetites[key]:
                category.appetite = appetites[key]
                said.append(f"appetite for {category.name}")
        if cadences is not None and cadences != rules.get(session, "cadences"):
            rules.put(session, "cadences", dict(cadences))
            audit.record(session, "program.cadences", subject_kind="program",
                         changes={"cadences": dict(cadences)})  # fmt: skip
            said.append("cadences")
        session.flush()
        settle(session)
        redated = _redate_documents(session)
    after = _snapshot(session)

    moved = []
    for risk in session.scalars(select(Risk).where(Risk.id.in_(list(before))).order_by(Risk.ref)):
        was, now = before[risk.id], after.get(risk.id, {})
        differences = [
            {"field": name, "label": label, "before": was[name], "after": now.get(name)}
            for name, label in WATCHED.items()
            if was[name] != now.get(name)
        ]
        if differences:
            moved.append({"ref": risk.ref, "name": risk.name, "org_unit_id": risk.org_unit_id,
                          "changes": differences})  # fmt: skip

    def count(*fields: str) -> int:
        return sum(1 for each in moved if any(c["field"] in fields for c in each["changes"]))

    return {
        "changed": said,
        "risks": moved,
        "counts": {
            "risks": len(moved),
            "rating": count("inherent_rating", "residual_rating", "target_rating"),
            "standing": count("standing"),
            "review": count("next_review_on"),
            "documents": redated,
        },
        "method_version": methods.current_row(session).version,
    }
