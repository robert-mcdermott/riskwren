"""A reference others can check (INT-05): is this supplier, scope, or exception in good
standing? Another process (purchasing, a data-access request, a deployment pipeline) asks with
a token and gets yes or no, with the reasons by kind and nothing of the record's contents. A
record the asker may not see is not found, as everywhere else.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import NotFound
from riskwren.inventory import records

KINDS = ("third-party", "scope", "exception")


def _third_party(session: Session, principal: Principal, row: Any) -> list[dict[str, str]]:
    """In good standing means: active and not on its way out, tiered, reviewed as its tier
    asks and approved, the review in date, and nothing shared with it that an agreement
    should cover and does not. Coverage is judged whatever the asker may see, and only the
    kind of gap is said."""
    from riskwren.thirdparty import coverage, lifecycle

    reasons = []
    today = utc_now().date()
    if row.status != "active":
        reasons.append({"code": "not_active", "text": "The relationship is not active."})
    ending = lifecycle.current_offboarding(session, row)
    if ending is not None and ending.status == "open":
        reasons.append({"code": "offboarding", "text": "The relationship is being ended."})
    if not row.tier:
        reasons.append({"code": "not_tiered",
                        "text": "It has not been tiered, so nothing says how closely it is "
                                "to be reviewed."})  # fmt: skip
    last = lifecycle.last_concluded(session, row)
    if row.tier and lifecycle.months_for(session, row.tier) and last is None:
        said = "Its tier calls for a review, and none has been concluded."
        reasons.append({"code": "never_reviewed", "text": said})
    if last is not None and last.conclusion == "declined":
        reasons.append({"code": "not_approved",
                        "text": "Its last review concluded that it is not approved."})  # fmt: skip
    if row.next_review_on is not None and row.next_review_on < today:
        due = row.next_review_on.isoformat()
        reasons.append({"code": "review_overdue", "text": f"Its review was due on {due}."})
    if any(found["sharing"].third_party.id == row.id for found in coverage.stops(session)):
        reasons.append({"code": "no_agreement",
                        "text": "Information is shared with it that no agreement of the kind "
                                "the program requires covers."})  # fmt: skip
    return reasons


def _scope(session: Session, principal: Principal, row: Any) -> list[dict[str, str]]:
    from riskwren.compliance import scopes
    from riskwren.db.models import Issue
    from riskwren.inventory.registry import TYPES

    reasons = []
    if row.status != "active":
        reasons.append({"code": "not_active", "text": "The scope is not active."})
    failing = 0
    for held in scopes.held_to(session, row):
        found = scopes.statement(session, principal, row, held["key"], brief=True)
        failing += found["counts"].get("failing", 0)
    if failing:
        said = f"{failing} requirement(s) have a control that failed a test."
        reasons.append({"code": "failing", "text": said})
    from riskwren.compliance import issues
    from riskwren.db.models import IssueSubject

    today = utc_now().date()
    late = session.scalars(
        select(Issue.id)
        .join(IssueSubject, IssueSubject.issue_id == Issue.id)
        .where(
            IssueSubject.subject_type == TYPES["scope"].key, IssueSubject.subject_id == row.id,
            Issue.status.in_(issues.LIVE), Issue.due_on < today,
            Issue.severity.in_(("critical", "high")),
        )
    ).all()  # fmt: skip
    late = len(set(late))
    if late:
        said = f"{late} critical or high issue(s) about it are past their date."
        reasons.append({"code": "issues_overdue", "text": said})
    return reasons


def _exception(session: Session, principal: Principal, row: Any) -> list[dict[str, str]]:
    from riskwren.compliance import exceptions

    state = exceptions.state_of(row)
    if exceptions.is_in_force(row):
        return []
    return [{"code": state, "text": f"The exception is {state.replace('_', ' ')}, not in force."}]


def check(session: Session, principal: Principal, kind: str, ref: str) -> dict[str, Any]:
    """Yes or no, with the reasons, for a record the asker may see."""
    if kind not in KINDS:
        raise NotFound(f"Standing is checked for: {', '.join(KINDS)}.")
    if kind == "third-party":
        from riskwren.inventory.registry import THIRD_PARTY as record_type

        judge = _third_party
    elif kind == "scope":
        from riskwren.compliance.scopes import SCOPE as record_type

        judge = _scope
    else:
        from riskwren.compliance.exceptions import EXCEPTION as record_type

        judge = _exception
    row = records.load(session, principal, record_type, ref)  # NotFound if not seen
    reasons = judge(session, principal, row)
    return {"kind": kind, "ref": row.ref, "name": row.name, "in_good_standing": not reasons,
            "reasons": reasons, "as_of": utc_now()}  # fmt: skip
