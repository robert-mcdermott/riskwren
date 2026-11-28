"""Learning and losses (INC-06): what an incident teaches the register.

Those who handle an incident say which risks it realized, which controls failed and which
held, why it happened, and what was learned; they record what it cost, and raise the issues
that put right what it showed, each an issue in the one register with the incident as its
source. A high or critical incident is not closed until what was learned is said.

The register learns back: a risk shows the incidents and near misses that realized it and
what they cost, against its estimate where it has one; a control shows the incidents in
which it failed or held. What a person sees of these follows the incidents' own rule, so a
restricted case never shows beside a risk or a control to someone not named on it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.compliance import issues
from riskwren.compliance.issues import ISSUE
from riskwren.controls.service import CONTROL
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import Incident, IncidentLoss, IncidentSubject, Issue
from riskwren.db.models.incidents import LOSS_KINDS
from riskwren.events import audit
from riskwren.incidents import reports
from riskwren.incidents.reports import INCIDENT
from riskwren.inventory import access, records
from riskwren.inventory.registry import find_any
from riskwren.program import vocab
from riskwren.risk.register import RISK

ROLES = {"realized": RISK, "failed": CONTROL, "held": CONTROL}
LOSS_LABELS = {
    "response": "Responding to it", "recovery": "Recovering from it",
    "lost_revenue": "Revenue or funding lost", "notification": "Notifying people",
    "legal": "Legal costs", "fines": "Fines and penalties", "other": "Other",
}  # fmt: skip
LONGEST = 20_000


def _require(session: Session, principal: Principal, incident: Incident) -> None:
    if not reports.can_edit(session, principal, incident):
        raise PermissionDenied("What an incident teaches is said by those who handle or triage it.")
    if incident.status == "closed":
        raise Conflict("This incident is closed. Reopen it to add to what it taught.")


# --- What it realized, and what failed or held --------------------------------------------


def links_of(session: Session, principal: Principal, incident: Incident) -> dict[str, Any]:
    out: dict[str, list[dict[str, Any]]] = {role: [] for role in ROLES}
    hidden = 0
    for row in session.scalars(
        select(IncidentSubject)
        .where(IncidentSubject.incident_id == incident.id, IncidentSubject.role.in_(ROLES))
        .order_by(IncidentSubject.id)
    ):
        record_type = ROLES[row.role]
        record = session.get(record_type.model, row.subject_id)
        if record is None:
            continue
        if not access.can_see(session, principal, record_type, record):
            hidden += 1
            continue
        out[row.role].append(records.chip(record_type, record))
    return {**out, "hidden": hidden}


def set_links(
    session: Session, principal: Principal, incident: Incident, given: Mapping[str, Any]
) -> None:
    """Say every risk it realized and every control that failed or held, by reference."""
    _require(session, principal, incident)
    errors = records.Errors()
    wanted: set[tuple[str, str, int]] = set()
    for role, record_type in ROLES.items():
        for ref in dict.fromkeys(str(each).strip().upper() for each in given.get(role) or []):
            try:
                found_type, record = find_any(session, ref)
            except NotFound:
                errors.add(role, f"There is no record {ref}.")
                continue
            if found_type.key != record_type.key or not access.can_see(
                session, principal, found_type, record
            ):
                errors.add(role, f"{ref} is not a {record_type.label} you can see.")
                continue
            wanted.add((role, record_type.key, record.id))
    failed = {item[2] for item in wanted if item[0] == "failed"}
    if failed & {item[2] for item in wanted if item[0] == "held"}:
        errors.add("held", "A control cannot both fail and hold in the same incident.")
    if errors:
        raise Invalid("Nothing was changed.", errors)
    have = {
        (row.role, row.subject_type, row.subject_id): row
        for row in session.scalars(
            select(IncidentSubject).where(
                IncidentSubject.incident_id == incident.id, IncidentSubject.role.in_(ROLES)
            )
        )
    }
    with audit.operation(session, "incident.learning"):
        for key, row in have.items():
            record_type = ROLES[key[0]]
            record = session.get(record_type.model, key[2])
            seen = record is not None and access.can_see(session, principal, record_type, record)
            if key not in wanted and seen:
                session.delete(row)
        for role, kind, identifier in sorted(wanted - set(have)):
            session.add(IncidentSubject(incident_id=incident.id, subject_type=kind,
                                        subject_id=identifier, role=role))  # fmt: skip
        records.touch(session, incident)
        incident.updated_at = utc_now()
        session.flush()


def learn(
    session: Session, principal: Principal, incident: Incident, values: Mapping[str, Any]
) -> None:
    """Say what was learned and why it happened."""
    _require(session, principal, incident)
    errors = records.Errors()
    lessons = records.text(values.get("lessons"))
    if lessons is not None and len(lessons) > LONGEST:
        errors.add("lessons", f"Keep it to {LONGEST} characters.")
    cause = records.choice(session, "root_causes", values.get("root_cause"), "root_cause", errors)
    if errors:
        raise Invalid("Nothing was changed.", errors)
    with audit.operation(session, "incident.learning"):
        incident.lessons, incident.root_cause = lessons, cause
        records.touch(session, incident)


def may_close(incident: Incident) -> str | None:
    """Why it cannot be closed yet, if it cannot."""
    return reports.close_blocked(incident)


# --- What it cost -------------------------------------------------------------------------


def add_loss(
    session: Session, principal: Principal, incident: Incident, values: Mapping[str, Any]
) -> IncidentLoss:
    _require(session, principal, incident)
    errors = records.Errors()
    kind = values.get("kind")
    if kind not in LOSS_KINDS:
        errors.add("kind", "Choose what kind of cost it was.")
    try:
        amount = int(values.get("amount"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        amount = None
        errors.add("amount", "Give the amount in whole units, such as 4800.")
    if amount is not None and not -(10**12) < amount < 10**12:
        errors.add("amount", "That is too large to be right.")
    currency = (records.text(values.get("currency")) or "USD").upper()
    if len(currency) != 3 or not currency.isalpha():
        errors.add("currency", "Give a three-letter currency code, such as USD.")
    if errors or amount is None:
        raise Invalid("The cost was not recorded.", errors)
    row = IncidentLoss(
        incident_id=incident.id, kind=kind, amount=amount, currency=currency,
        note=records.text(values.get("note")), recorded_by=principal.account_id,
        recorded_by_name=principal.name, recorded_at=utc_now(),
    )  # fmt: skip
    with audit.operation(session, "incident.loss"):
        session.add(row)
        records.touch(session, incident)
        incident.updated_at = utc_now()
        session.flush()
    return row


def _losses(session: Session, incident_ids: Iterable[int]) -> dict[int, list[IncidentLoss]]:
    ids = list(incident_ids)
    found: dict[int, list[IncidentLoss]] = {each: [] for each in ids}
    for row in session.scalars(
        select(IncidentLoss)
        .where(IncidentLoss.incident_id.in_(ids or [0]))
        .order_by(IncidentLoss.id)
    ):
        found[row.incident_id].append(row)
    return found


def totals(rows: Iterable[IncidentLoss]) -> dict[str, int]:
    """Each currency's total: amounts in different currencies are not added together."""
    out: dict[str, int] = {}
    for row in rows:
        out[row.currency] = out.get(row.currency, 0) + row.amount
    return out


# --- Putting right what it showed ---------------------------------------------------------


def raise_issue(
    session: Session, principal: Principal, incident: Incident, values: Mapping[str, Any]
) -> Issue:
    """An issue in the one register, with the incident as its source. Raised for an
    incident's unit by those who handle it, whether or not they keep that unit's records."""
    _require(session, principal, incident)
    on_behalf = Principal.for_command(principal.name)
    with audit.operation(session, "incident.issue", incident=incident.ref):
        issue = issues.create(
            session,
            on_behalf,
            {
                "name": values.get("name"),
                "summary": values.get("summary"),
                "severity": values.get("severity"),
                "org_unit_id": incident.org_unit_id,
                "source_kind": "incident",
                "subjects": list(values.get("subjects") or []),
                "owner_id": values.get("owner_id") or principal.account_id,
                # What a restricted case shows stays with those who may know of it.
                "restricted": incident.restricted,
            },
        )
        issue.source_type, issue.source_id = "incident", incident.id
        issue.created_by = principal.account_id
        session.flush()
    return issue


def issues_of(session: Session, principal: Principal, incident: Incident) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Issue)
        .where(Issue.source_type == "incident", Issue.source_id == incident.id)
        .order_by(Issue.ref)
    ).all()
    shown = [row for row in rows if access.can_see(session, principal, ISSUE, row)]
    return [
        {**records.chip(ISSUE, row), "status": row.status, "severity": row.severity,
         "due_on": row.due_on}
        for row in shown
    ]  # fmt: skip


# --- What an incident shows, and what the register shows of incidents --------------------


def detail(session: Session, principal: Principal, incident: Incident) -> dict[str, Any]:
    losses = _losses(session, [incident.id])[incident.id]
    return {
        "links": links_of(session, principal, incident),
        "lessons": incident.lessons,
        "root_cause": incident.root_cause,
        "losses": [
            {
                "id": row.id,
                "kind": row.kind,
                "label": LOSS_LABELS[row.kind],
                "amount": row.amount,
                "currency": row.currency,
                "note": row.note,
                "by": row.recorded_by_name,
                "at": row.recorded_at,
            }
            for row in losses
        ],
        "loss_totals": totals(losses),
        "issues": issues_of(session, principal, incident),
        "close_blocked": may_close(incident),
    }


def beside(
    session: Session, principal: Principal, kind: str, record_id: int, roles: tuple[str, ...]
) -> dict[str, Any]:
    """The incidents that bear on a risk or a control, as far as the person may see them."""
    seen = reports.visible(session, principal)
    statement = (
        select(Incident, IncidentSubject.role)
        .join(IncidentSubject, IncidentSubject.incident_id == Incident.id)
        .where(
            IncidentSubject.subject_type == kind,
            IncidentSubject.subject_id == record_id,
            IncidentSubject.role.in_(roles),
        )
        .order_by(Incident.created_at.desc())
    )
    if seen is not None:
        statement = statement.where(seen)
    rows = session.execute(statement).all()
    losses = _losses(session, [incident.id for incident, _ in rows])
    year_ago = utc_now() - timedelta(days=365)
    items = [
        {"ref": incident.ref, "name": incident.name, "kind": incident.kind, "role": role,
         "status": incident.status, "reported_at": incident.created_at,
         "loss_totals": totals(losses[incident.id])}
        for incident, role in rows
    ]  # fmt: skip
    every = [row for incident in {incident.id for incident, _ in rows} for row in losses[incident]]
    return {
        "items": items,
        "loss_totals": totals(every),
        "last_year": sum(1 for incident, _ in rows if incident.created_at >= year_ago),
    }


def summary(session: Session, principal: Principal, days: int = 365) -> dict[str, Any]:
    """The incidents a person may see, reported in the last year: how many of each kind and
    category, what they cost, and the risks and controls that come up most."""
    seen = reports.visible(session, principal)
    since = utc_now() - timedelta(days=days)
    statement = select(Incident).where(Incident.created_at >= since)
    if seen is not None:
        statement = statement.where(seen)
    rows = session.scalars(statement).all()
    ids = [row.id for row in rows]
    by_kind: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for row in rows:
        by_kind[row.kind] = by_kind.get(row.kind, 0) + 1
        if row.category:
            by_category[row.category] = by_category.get(row.category, 0) + 1
    every = [loss for group in _losses(session, ids).values() for loss in group]

    def most(role: str, record_type: Any) -> list[dict[str, Any]]:
        counted = session.execute(
            select(IncidentSubject.subject_id, func.count())
            .where(
                IncidentSubject.incident_id.in_(ids or [0]),
                IncidentSubject.role == role,
                IncidentSubject.subject_type == record_type.key,
            )
            .group_by(IncidentSubject.subject_id)
            .order_by(func.count().desc())
            .limit(10)
        ).all()
        out = []
        for subject_id, number in counted:
            record = session.get(record_type.model, subject_id)
            if record is not None and access.can_see(session, principal, record_type, record):
                out.append({**records.chip(record_type, record), "count": int(number)})
        return out[:5]

    labels = vocab.labels(session, "incident_categories")
    return {
        "days": days,
        "total": len(rows),
        "by_kind": by_kind,
        "by_category": [
            {"key": key, "label": labels.get(key, key), "count": number}
            for key, number in sorted(by_category.items(), key=lambda pair: -pair[1])
        ],
        "loss_totals": totals(every),
        "realized": most("realized", RISK),
        "failed": most("failed", CONTROL),
    }


def install() -> None:
    """Add to an incident, a risk, and a control what each shows of the others."""
    for record_type, roles, key in (
        (RISK, ("realized",), "risk"),
        (CONTROL, ("failed", "held"), "control"),
    ):
        before = record_type.extra.get("detail")

        def detail_(session: Session, principal: Principal, record: Any, before: Any = before,
                    roles: tuple[str, ...] = roles, key: str = key) -> dict[str, Any]:  # fmt: skip
            out = dict(before(session, principal, record)) if before is not None else {}
            out["incidents"] = beside(session, principal, key, record.id, roles)
            return out

        record_type.extra["detail"] = detail_

    previous = INCIDENT.extra["detail"]

    def incident_detail(
        session: Session, principal: Principal, incident: Incident
    ) -> dict[str, Any]:
        out = previous(session, principal, incident)
        if out.get("everything"):
            out.update(detail(session, principal, incident))
        return out

    INCIDENT.extra["detail"] = incident_detail
    INCIDENT.extra["history_labels"] = {
        **INCIDENT.extra.get("history_labels", {}), "lessons": "What was learned",
        "root_cause": "Why it happened",
    }  # fmt: skip
    INCIDENT.extra["history_vocabularies"] = {
        **INCIDENT.extra.get("history_vocabularies", {}), "root_cause": "root_causes",
    }  # fmt: skip
    previous_title = INCIDENT.extra.get("history_title")

    def title(event: Any, lookups: Any) -> str | None:
        if event.subject_type == "incident_loss" and event.action == "created":
            changes = event.changes or {}
            amount = (changes.get("amount") or [None, None])[1]
            currency = (changes.get("currency") or [None, None])[1]
            return f"Recorded a cost of {amount:,} {currency}" if amount is not None else None
        return previous_title(event, lookups) if previous_title is not None else None

    INCIDENT.extra["history_title"] = title


install()
