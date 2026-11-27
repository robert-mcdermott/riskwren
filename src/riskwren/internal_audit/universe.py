"""The audit universe (AUD-01): everything worth auditing, ranked from the register.

The universe is not kept by hand. It is every unit beneath the organization, and every
process, system, third party, and scope in use, each ranked by what the register says about
it today: the highest residual rating among the open risks that concern it, how many of
those are above appetite, its open issues, how critical it is, how ready a scope is, and how
long since it was last audited. Each part of the ranking is shown with the points it gave.
An auditor may move a thing up or down with a reason, record an audit from before RiskWren,
or leave a thing out of the universe with a reason; what audit says is kept, and in the
history.

The universe and the plans are read by those who read everything and by those who lead the
whole organization. Only auditors change them.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access import roles
from riskwren.access.principal import Principal
from riskwren.core import scoring
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    AuditEntity,
    Engagement,
    Issue,
    IssueSubject,
    OrgUnit,
    Process,
    Risk,
    RiskSubject,
    Scope,
    System,
    ThirdParty,
)
from riskwren.db.models.audit import AUDITABLE
from riskwren.events import audit
from riskwren.inventory import records
from riskwren.program import vocab
from riskwren.risk import method as methods

LABELS = {
    "unit": "Unit",
    "process": "Process",
    "system": "System",
    "third_party": "Third party",
    "scope": "Scope",
}
MODELS: dict[str, Any] = {
    "process": Process,
    "system": System,
    "third_party": ThirdParty,
    "scope": Scope,
}
ABOVE = ("treated", "accepted", "needs_decision")
LIVE_ISSUES = ("open", "proposed")
SERIOUS = ("critical", "high")
BANDS = (("high", 55, "High"), ("medium", 30, "Medium"), ("low", 0, "Low"))
MOST_ADJUSTMENT = 30
WORK_UNDER_WAY = ("planned", "planning", "fieldwork", "reporting")


def may_read(principal: Principal) -> bool:
    return principal.reads_reports


def may_work(principal: Principal) -> bool:
    """The audit function's own records are changed by auditors alone."""
    return principal.has(roles.AUDITOR)


def require_read(principal: Principal) -> None:
    if not may_read(principal):
        raise PermissionDenied(
            "The audit universe and plans are read by those who read everything and those "
            "who lead the whole organization."
        )


def require_work(principal: Principal) -> None:
    if not may_work(principal):
        raise PermissionDenied("Only auditors change internal audit's own records.")


def band(score: int) -> tuple[str, str]:
    for key, floor, label in BANDS:
        if score >= floor:
            return key, label
    return "low", "Low"


def _since(last: date | None, today: date) -> tuple[int, str]:
    if last is None:
        return 20, "Never audited"
    years = (today - last).days / 365.25
    if years >= 3:
        return 15, "Last audited more than three years ago"
    if years >= 2:
        return 10, "Last audited more than two years ago"
    if years >= 1:
        return 5, "Last audited more than a year ago"
    return 0, "Audited within the year"


class Facts:
    """What the register says, gathered once for the whole universe."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.method = methods.current(session)
        self.places = len(self.method["ratings"])
        self.labels = {rating["key"]: rating["label"] for rating in self.method["ratings"]}
        self.risks = {
            row.id: row
            for row in session.execute(
                select(Risk.id, Risk.org_unit_id, Risk.residual_rating, Risk.standing).where(
                    Risk.status == "open"
                )
            )
        }
        self.risk_subjects: dict[tuple[str, int], set[int]] = defaultdict(set)
        for row in session.execute(select(RiskSubject.risk_id, RiskSubject.subject_type,
                                          RiskSubject.subject_id)):  # fmt: skip
            if row.risk_id in self.risks:
                self.risk_subjects[(row.subject_type, row.subject_id)].add(row.risk_id)
        self.issues = {
            row.id: row
            for row in session.execute(
                select(Issue.id, Issue.org_unit_id, Issue.severity).where(
                    Issue.status.in_(LIVE_ISSUES)
                )
            )
        }
        self.issue_subjects: dict[tuple[str, int], set[int]] = defaultdict(set)
        for row in session.execute(select(IssueSubject.issue_id, IssueSubject.subject_type,
                                          IssueSubject.subject_id)):  # fmt: skip
            if row.issue_id in self.issues:
                self.issue_subjects[(row.subject_type, row.subject_id)].add(row.issue_id)
        units = session.execute(select(OrgUnit.id, OrgUnit.parent_id)).all()
        children: dict[int | None, list[int]] = defaultdict(list)
        for unit_id, parent in units:
            children[parent].append(unit_id)
        self.beneath: dict[int, set[int]] = {}
        for unit_id, _ in units:
            found, stack = set(), [unit_id]
            while stack:
                each = stack.pop()
                found.add(each)
                stack.extend(children.get(each, []))
            self.beneath[unit_id] = found
        criticalities = vocab.keys(session, "criticalities")
        self.critical = {key: index for index, key in enumerate(criticalities)}
        self.said = {
            (row.subject_type, row.subject_id): row for row in session.scalars(select(AuditEntity))
        }
        self.reported: dict[tuple[str, int], date] = {}
        self.planned: dict[tuple[str, int], list[str]] = defaultdict(list)
        for row in session.scalars(select(Engagement)):
            key = (row.subject_type, row.subject_id)
            if row.status == "reported" and row.reported_on:
                self.reported[key] = max(row.reported_on, self.reported.get(key, row.reported_on))
            elif row.status in WORK_UNDER_WAY:
                self.planned[key].append(row.ref)

    def risks_of(self, kind: str, row: Any) -> set[int]:
        if kind == "unit":
            within = self.beneath.get(row.id, {row.id})
            return {r.id for r in self.risks.values() if r.org_unit_id in within}
        return set(self.risk_subjects.get((kind, row.id), set()))

    def issues_of(self, kind: str, row: Any) -> set[int]:
        if kind == "unit":
            within = self.beneath.get(row.id, {row.id})
            return {i.id for i in self.issues.values() if i.org_unit_id in within}
        found = set(self.issue_subjects.get((kind, row.id), set()))
        for risk_id in self.risks_of(kind, row):  # issues about its risks bear on it too
            found |= self.issue_subjects.get(("risk", risk_id), set())
        return found


def _readiness(session: Session, scope: Scope) -> tuple[int, int]:
    """How many requirements apply to a scope across its frameworks, and how many are not
    yet verified or in place."""
    from riskwren.compliance import scopes

    everyone = Principal.for_command("Audit universe")
    applicable = short = 0
    for held in scopes.held_to(session, scope):
        found = scopes.statement(session, everyone, scope, held["key"])
        applicable += found["applicable"]
        short += sum(found["counts"][s] for s in ("gap", "planned", "failing"))
    return applicable, short


def rank(facts: Facts, kind: str, row: Any, today: date) -> dict[str, Any]:
    """How the thing ranks, and every part of it with the points it gave."""
    parts: list[dict[str, Any]] = []
    risks = [facts.risks[r] for r in facts.risks_of(kind, row)]
    if risks:
        worst = max(risks, key=lambda r: scoring.position(facts.method, r.residual_rating))
        place = scoring.position(facts.method, worst.residual_rating)
        if place:
            points = round(30 * place / facts.places)
            label = facts.labels.get(worst.residual_rating, worst.residual_rating)
            parts.append({"label": f"Its worst open risk is rated {label}", "points": points})
        above = sum(1 for r in risks if r.standing in ABOVE)
        if above:
            parts.append({"label": f"{above} open risk{'s' if above != 1 else ''} above appetite",
                          "points": min(16, 4 * above)})  # fmt: skip
    issues = [facts.issues[i] for i in facts.issues_of(kind, row)]
    if issues:
        serious = sum(1 for i in issues if i.severity in SERIOUS)
        points = min(16, 2 * len(issues) + 2 * serious)
        words = f"{len(issues)} open issue{'s' if len(issues) != 1 else ''}"
        if serious:
            words += f", {serious} critical or high"
        parts.append({"label": words, "points": points})
    criticality = getattr(row, "criticality", None)
    if criticality in facts.critical and len(facts.critical) > 1:
        position = facts.critical[criticality]
        points = round(15 * position / (len(facts.critical) - 1))
        if points:
            parts.append({"label": f"Its criticality is {criticality}", "points": points})
    if kind == "scope":
        applicable, short = _readiness(facts.session, row)
        if applicable and short:
            parts.append({"label": f"{short} of {applicable} requirements not yet in place",
                          "points": round(20 * short / applicable)})  # fmt: skip
    said = facts.said.get((kind, row.id))
    last = facts.reported.get((kind, row.id))
    if said is not None and said.last_audited_on and (last is None or said.last_audited_on > last):
        last = said.last_audited_on
    points, words = _since(last, today)
    if points:
        parts.append({"label": words, "points": points})
    if said is not None and said.adjustment:
        parts.append({"label": f"Moved by audit: {said.adjustment_reason}",
                      "points": said.adjustment})  # fmt: skip
    score = max(0, sum(part["points"] for part in parts))
    key, label = band(score)
    return {
        "score": score,
        "band": key,
        "band_label": label,
        "parts": parts,
        "last_audited_on": last,
        "open_risks": len(risks),
        "open_issues": len(issues),
        "planned": facts.planned.get((kind, row.id), []),
        "left_out": bool(said and said.left_out),
        "left_out_reason": said.left_out_reason if said else None,
        "adjustment": said.adjustment if said else 0,
        "adjustment_reason": said.adjustment_reason if said else None,
        "last_audit_note": said.last_audit_note if said else None,
    }


def _things(session: Session) -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = [
        ("unit", row)
        for row in session.scalars(
            select(OrgUnit)
            .where(OrgUnit.status == "active", OrgUnit.parent_id.is_not(None))
            .order_by(OrgUnit.name)
        )
    ]
    for kind, model in MODELS.items():
        found += [
            (kind, row)
            for row in session.scalars(
                select(model).where(model.status == "active").order_by(model.ref)
            )
        ]
    return found


def key_of(kind: str, row: Any) -> str:
    return str(row.id) if kind == "unit" else str(row.ref)


def entry(
    facts: Facts, kind: str, row: Any, names: Mapping[int, str], today: date
) -> dict[str, Any]:
    return {
        "kind": kind,
        "kind_label": LABELS[kind],
        "key": key_of(kind, row),
        "ref": None if kind == "unit" else row.ref,
        "name": row.name,
        "unit": names.get(row.id if kind == "unit" else row.org_unit_id),
        **rank(facts, kind, row, today),
    }


def universe(
    session: Session, principal: Principal, *, kind: str | None = None, left_out: bool = False
) -> dict[str, Any]:
    """Every auditable thing, highest ranked first."""
    require_read(principal)
    facts = Facts(session)
    today = utc_now().date()
    names = {row.id: row.name for row in session.execute(select(OrgUnit.id, OrgUnit.name))}
    rows = [
        entry(facts, each_kind, row, names, today)
        for each_kind, row in _things(session)
        if kind in (None, "", each_kind)
    ]
    shown = [row for row in rows if row["left_out"] == left_out]
    shown.sort(key=lambda row: (-row["score"], row["kind"], row["name"]))
    counts = {key: sum(1 for row in rows if row["band"] == key and not row["left_out"])
              for key, _, _ in BANDS}  # fmt: skip
    return {
        "entities": shown,
        "counts": counts,
        "left_out": sum(1 for row in rows if row["left_out"]),
        "kinds": LABELS,
        "bands": {key: label for key, _, label in BANDS},
        "can_work": may_work(principal),
    }


def find(session: Session, kind: str, key: str) -> Any:
    if kind not in AUDITABLE:
        raise NotFound(f"There is nothing to audit of the kind {kind}.")
    if kind == "unit":
        row = session.get(OrgUnit, int(key)) if key.isdigit() else None
    else:
        model = MODELS[kind]
        row = session.scalars(select(model).where(model.ref == key.strip().upper())).first()
    if row is None:
        raise NotFound(f"There is no {LABELS[kind].lower()} {key}.")
    return row


def one(session: Session, principal: Principal, kind: str, key: str) -> dict[str, Any]:
    require_read(principal)
    row = find(session, kind, key)
    names = {row.id: row.name for row in session.execute(select(OrgUnit.id, OrgUnit.name))}
    return entry(Facts(session), kind, row, names, utc_now().date())


def say(
    session: Session, principal: Principal, kind: str, key: str, values: Mapping[str, Any]
) -> dict[str, Any]:
    """Record what audit says about a thing: a move up or down with a reason, an audit from
    before RiskWren, or that it is left out of the universe and why."""
    require_work(principal)
    row = find(session, kind, key)
    errors = records.Errors()
    said = session.scalars(
        select(AuditEntity).where(AuditEntity.subject_type == kind,
                                  AuditEntity.subject_id == row.id)
    ).first()  # fmt: skip
    if said is None:
        said = AuditEntity(subject_type=kind, subject_id=row.id, adjustment=0, left_out=False)
    if "adjustment" in values:
        try:
            moved = int(values.get("adjustment") or 0)
        except (TypeError, ValueError):
            moved = None
            errors.add("adjustment", "Give a whole number of points.")
        reason = records.text(values.get("adjustment_reason"))
        if moved is not None:
            if abs(moved) > MOST_ADJUSTMENT:
                errors.add("adjustment", f"At most {MOST_ADJUSTMENT} points either way.")
            elif moved and not reason:
                errors.add("adjustment_reason", "Say why audit moves it.")
            else:
                said.adjustment, said.adjustment_reason = moved, reason if moved else None
    if "last_audited_on" in values:
        value = values.get("last_audited_on")
        if value in (None, ""):
            said.last_audited_on, said.last_audit_note = None, None
        else:
            try:
                day = value if isinstance(value, date) else date.fromisoformat(str(value))
            except ValueError:
                errors.add("last_audited_on", "Give a date, as year-month-day.")
            else:
                if day > utc_now().date():
                    errors.add("last_audited_on", "That has not happened yet.")
                else:
                    said.last_audited_on = day
                    said.last_audit_note = records.text(values.get("last_audit_note"))
    if "left_out" in values:
        out = bool(values.get("left_out"))
        reason = records.text(values.get("left_out_reason"))
        if out and not reason:
            errors.add("left_out_reason", "Say why it is left out of the universe.")
        else:
            said.left_out, said.left_out_reason = out, reason if out else None
    if errors:
        raise Invalid("What audit says was not recorded.", errors)
    with audit.operation(session, "audit.universe", subject=f"{kind}:{key}"):
        said.updated_by = principal.account_id
        said.updated_by_name = principal.name
        said.updated_at = utc_now()
        session.add(said)
        session.flush()
    return one(session, principal, kind, key)
