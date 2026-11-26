"""How one record connects to the others (INV-11).

A record's neighbors, grouped by what joins them: what it relies on and what relies on it,
the risks that bear on it, the controls that reduce them, the scopes it sits in, and the
evidence, issues, exceptions, and assessments about it. Each neighbor is one the person may
see; the rest are counted. The picture and the list beside it are drawn from this one answer,
so they cannot disagree.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.db.models import (
    Assessment,
    ControlTest,
    EvidenceLink,
    ExceptionRequest,
    Implementation,
    IssueSubject,
    RecordLink,
    RiskControl,
    RiskSubject,
    ScopeMember,
)
from riskwren.inventory import access, links, records
from riskwren.inventory.registry import TYPES, RecordType

Edge = tuple[str, str, str, int]  # a group's key and label, and the neighbor's type and id


def _edges(session: Session, key: str, record_id: int) -> list[Edge]:
    """Everything joined to a record, whatever it is, before anyone asks who may see it."""
    found: list[Edge] = []
    kinds = links.kinds(session)
    for row in session.scalars(
        select(RecordLink)
        .where(
            or_(
                (RecordLink.from_type == key) & (RecordLink.from_id == record_id),
                (RecordLink.to_type == key) & (RecordLink.to_id == record_id),
            )
        )
        .order_by(RecordLink.id)
    ):
        forward = row.from_type == key and row.from_id == record_id
        kind = kinds.get(row.relation, {})
        label = str(kind.get("label" if forward else "reverse", row.relation))
        other = (row.to_type, row.to_id) if forward else (row.from_type, row.from_id)
        found.append((f"{row.relation}:{'out' if forward else 'in'}", label, *other))

    def add(group: str, label: str, other_type: str, ids: Any) -> None:
        found.extend((group, label, other_type, int(each)) for each in ids)

    if key == "risk":
        for subject_type, subject_id in session.execute(
            select(RiskSubject.subject_type, RiskSubject.subject_id)
            .where(RiskSubject.risk_id == record_id)
            .order_by(RiskSubject.id)
        ):
            found.append(("bears_on", "Bears on", subject_type, subject_id))
        add("reduced_by", "Reduced by", "control", session.scalars(
            select(RiskControl.control_id).where(RiskControl.risk_id == record_id)
        ))  # fmt: skip
    else:
        add("risks", "Risks to it", "risk", session.scalars(
            select(RiskSubject.risk_id).where(
                RiskSubject.subject_type == key, RiskSubject.subject_id == record_id
            )
        ))  # fmt: skip
    if key == "control":
        add("reduces", "Reduces", "risk", session.scalars(
            select(RiskControl.risk_id).where(RiskControl.control_id == record_id)
        ))  # fmt: skip
        add("used_in", "Used in", "scope", session.scalars(
            select(Implementation.scope_id).where(Implementation.control_id == record_id)
        ))  # fmt: skip
        add("tested_in", "Tested in", "assessment", session.scalars(
            select(ControlTest.assessment_id).where(ControlTest.control_id == record_id)
        ))  # fmt: skip
    if key == "scope":
        for subject_type, subject_id in session.execute(
            select(ScopeMember.subject_type, ScopeMember.subject_id)
            .where(ScopeMember.scope_id == record_id)
            .order_by(ScopeMember.id)
        ):
            found.append(("covers", "Covers", subject_type, subject_id))
        add("uses", "Uses", "control", session.scalars(
            select(Implementation.control_id).where(Implementation.scope_id == record_id)
        ))  # fmt: skip
        add("assessments", "Assessed by", "assessment", session.scalars(
            select(Assessment.id).where(Assessment.scope_id == record_id)
        ))  # fmt: skip
        add("exceptions", "Exceptions", "exception", session.scalars(
            select(ExceptionRequest.id).where(ExceptionRequest.scope_id == record_id)
        ))  # fmt: skip
    else:
        add("within", "Within the scope", "scope", session.scalars(
            select(ScopeMember.scope_id).where(
                ScopeMember.subject_type == key, ScopeMember.subject_id == record_id
            )
        ))  # fmt: skip
    if key == "control":
        add("exceptions", "Exceptions", "exception", session.scalars(
            select(ExceptionRequest.id).where(
                ExceptionRequest.subject_type == "control",
                ExceptionRequest.subject_id == record_id,
            )
        ))  # fmt: skip
    if key == "evidence":
        for subject_type, subject_id in session.execute(
            select(EvidenceLink.subject_type, EvidenceLink.subject_id)
            .where(EvidenceLink.evidence_id == record_id)
            .order_by(EvidenceLink.id)
        ):
            found.append(("supports", "Supports", subject_type, subject_id))
    else:
        add("evidence", "Evidence", "evidence", session.scalars(
            select(EvidenceLink.evidence_id).where(
                EvidenceLink.subject_type == key, EvidenceLink.subject_id == record_id
            )
        ))  # fmt: skip
    if key == "issue":
        for subject_type, subject_id in session.execute(
            select(IssueSubject.subject_type, IssueSubject.subject_id)
            .where(IssueSubject.issue_id == record_id)
            .order_by(IssueSubject.id)
        ):
            found.append(("about", "About", subject_type, subject_id))
    else:
        add("issues", "Issues", "issue", session.scalars(
            select(IssueSubject.issue_id).where(
                IssueSubject.subject_type == key, IssueSubject.subject_id == record_id
            )
        ))  # fmt: skip
    if key == "assessment":
        row = session.get(Assessment, record_id)
        if row is not None:
            found.append(("assesses", "Assesses", "scope", row.scope_id))
        add("tests", "Tests", "control", session.scalars(
            select(ControlTest.control_id).where(ControlTest.assessment_id == record_id)
        ))  # fmt: skip
    if key == "exception":
        row = session.get(ExceptionRequest, record_id)
        if row is not None:
            if row.subject_type == "control":
                found.append(("excepts", "An exception to", "control", row.subject_id))
            if row.scope_id is not None:
                found.append(("in_scope", "Within the scope", "scope", row.scope_id))
    return found


def around(
    session: Session, principal: Principal, record_type: RecordType, record: Any
) -> dict[str, Any]:
    """A record and its neighbors, in groups, cut to what the person may see."""
    groups: dict[str, dict[str, Any]] = {}
    seen: set[tuple[str, str, int]] = set()
    hidden = 0
    setting = access.visibility(session)
    for group, label, other_key, other_id in _edges(session, record_type.key, record.id):
        if (group, other_key, other_id) in seen:
            continue
        seen.add((group, other_key, other_id))
        other_type = TYPES.get(other_key)
        other = session.get(other_type.model, other_id) if other_type is not None else None
        if other is None or other_type is None:
            continue  # a unit, a requirement, or something since removed: not a record
        if not access.can_see(session, principal, other_type, other, setting=setting):
            hidden += 1
            continue
        entry = groups.setdefault(group, {"key": group, "label": label, "records": []})
        entry["records"].append(records.chip(other_type, other))
    found = list(groups.values())
    return {
        "center": records.chip(record_type, record),
        "groups": found,
        "count": sum(len(group["records"]) for group in found),
        "hidden": hidden,
    }
