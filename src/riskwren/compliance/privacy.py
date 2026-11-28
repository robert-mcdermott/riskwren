"""Privacy impact assessments (INC-07).

A process or a system that handles a class of data the program names (restricted, to begin
with) needs a privacy impact assessment: the built-in questionnaire, answered by whoever
answers for it, through a campaign. Its answers are kept with the record; those who assess
for its unit are told when it is answered, with any concerns, and one of them reviews it.
It is done again after the number of months the program sets.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, NotFound, PermissionDenied
from riskwren.db.models import Campaign, CampaignItem, Process, Response, System
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.registry import PROCESS, SYSTEM, RecordType
from riskwren.people import notices
from riskwren.program import rules

KIND = "privacy_impact"
QUESTIONNAIRE = "privacy-impact"
TYPES: dict[str, RecordType] = {"process": PROCESS, "system": SYSTEM}
MODELS: dict[str, Any] = {"process": Process, "system": System}
STATES = {
    "never": "Never assessed",
    "asked": "Asked, not yet answered",
    "to_review": "Answered, to review",
    "current": "Reviewed",
    "due": "Due again",
}


def rule(session: Session) -> dict[str, Any]:
    return rules.get(session, "privacy")


def required(session: Session, record: Any) -> bool:
    return record.data_class in (rule(session).get("impact_assessment_classes") or [])


def _items(session: Session, kind: str, record_id: int) -> list[CampaignItem]:
    return list(
        session.scalars(
            select(CampaignItem)
            .join(Campaign, Campaign.id == CampaignItem.campaign_id)
            .where(
                Campaign.kind == KIND,
                CampaignItem.subject_type == kind,
                CampaignItem.subject_id == record_id,
            )
            .order_by(CampaignItem.id.desc())
        )
    )


def concerns(answers: Mapping[str, Any]) -> list[str]:
    """What in the answers wants a closer look."""
    found = []
    if answers.get("least") is False:
        found.append("It collects more than its purpose needs.")
    if answers.get("shared") is True and answers.get("agreement") == "none":
        found.append("It is shared outside the organization with nothing covering it.")
    if answers.get("access") is False:
        found.append("More people can see it than need to.")
    if answers.get("deidentified") == "no":
        found.append("It is not de-identified, though it could be.")
    return found


def status(session: Session, kind: str, record: Any) -> dict[str, Any]:
    """Whether the record needs an assessment, and where its assessment stands."""
    needed = required(session, record)
    items = _items(session, kind, record.id)
    answered = next((item for item in items if item.status == "done"), None)
    pending = next((item for item in items if item.status == "pending"), None)
    months = int(rule(session).get("impact_assessment_months") or 36)
    due_on: date | None = None
    if answered is not None and answered.completed_at is not None:
        due_on = answered.completed_at.date() + timedelta(days=round(months * 30.44))
    if answered is None:
        state = "asked" if pending is not None else "never"
    elif answered.outcome in ("answered", "concerns"):
        state = "to_review"
    elif due_on is not None and due_on < utc_now().date():
        state = "asked" if pending is not None else "due"
    else:
        state = "current"
    response = (
        session.get(Response, answered.response_id) if answered and answered.response_id else None
    )
    return {
        "required": needed,
        "classes": rule(session).get("impact_assessment_classes") or [],
        "months": months,
        "state": state if (needed or answered is not None) else None,
        "state_label": STATES.get(state) if (needed or answered is not None) else None,
        "last": {
            "item_id": answered.id,
            "answered_at": answered.completed_at,
            "answered_by": answered.completed_by_name,
            "outcome": answered.outcome,
            "note": answered.note,
            "concerns": concerns(response.answers) if response else [],
        }
        if answered is not None
        else None,
        "pending_item": pending.id if pending is not None else None,
        "due_on": due_on,
    }


def needing(session: Session, org_unit_ids: frozenset[int] | None = None) -> list[tuple[str, Any]]:
    """The processes and systems in use that need an assessment and have no current one: what
    a campaign asks about."""
    classes = rule(session).get("impact_assessment_classes") or []
    out: list[tuple[str, Any]] = []
    for kind, model in MODELS.items():
        rows = session.scalars(
            select(model)
            .where(model.status == "active", model.data_class.in_(classes or [""]))
            .order_by(model.id)
        )
        for row in rows:
            if org_unit_ids is not None and row.org_unit_id not in org_unit_ids:
                continue
            if status(session, kind, row)["state"] in ("current", "to_review", "asked"):
                continue
            out.append((kind, row))
    return out


def overview(session: Session, principal: Principal) -> dict[str, Any]:
    """Every process and system that needs an assessment, with where each stands."""
    classes = rule(session).get("impact_assessment_classes") or []
    rows = []
    counts = dict.fromkeys(STATES, 0)
    for kind, model in MODELS.items():
        for row in session.scalars(
            select(model)
            .where(model.status == "active", model.data_class.in_(classes or [""]))
            .order_by(model.name)
        ):
            if not access.can_see(session, principal, TYPES[kind], row):
                continue
            found = status(session, kind, row)
            counts[found["state"]] += 1
            rows.append({**records.chip(TYPES[kind], row), "org_unit_id": row.org_unit_id,
                         "data_class": row.data_class, **found})  # fmt: skip
    order = list(STATES)
    rows.sort(key=lambda row: (order.index(row["state"]), row["name"]))
    return {
        "rows": rows,
        "counts": counts,
        "classes": classes,
        "months": int(rule(session).get("impact_assessment_months") or 36),
        "can_start": principal.assesses,
    }


def review(session: Session, principal: Principal, item_id: int, note: Any) -> CampaignItem:
    """Say an answered assessment has been read, and what was made of it."""
    item = session.get(CampaignItem, item_id)
    campaign = session.get(Campaign, item.campaign_id) if item else None
    if item is None or campaign is None or campaign.kind != KIND:
        raise NotFound("There is no such privacy impact assessment.")
    if not principal.assesses_unit(item.org_unit_id):
        raise PermissionDenied("An assessment is reviewed by those who assess for its unit.")
    if item.status != "done":
        raise Conflict("It has not been answered yet.")
    if item.outcome == "reviewed":
        raise Conflict("It has already been reviewed.")
    with audit.operation(session, "privacy_impact.review"):
        item.outcome = "reviewed"
        said = records.text(note)
        item.note = f"Reviewed by {principal.name}" + (f": {said}" if said else ".")
        session.flush()
    return item


def answered(
    session: Session, principal: Principal, item: CampaignItem, campaign: Campaign,
    answers: Mapping[str, Any],
) -> str:  # fmt: skip
    """When an assessment is answered: those who assess for its unit are told, concerns
    first. Returns the outcome in a word."""
    found = concerns(answers)
    what = f"{item.subject_ref or ''} {item.subject_name}".strip()
    reviewers = (
        notices.holders(session, ("assessor", "manager"), item.org_unit_id)
        if (item.org_unit_id)
        else []
    )
    text = (
        f"A privacy impact assessment with concerns, to review: {what}"
        if found
        else f"A privacy impact assessment to review: {what}"
    )
    href = f"/{TYPES[item.subject_type].path}/{item.subject_ref}?tab=privacy"
    notices.tell_all(session, reviewers, "privacy_impact", text, href, by=principal)
    return "concerns" if found else "answered"


def detail(session: Session, principal: Principal, record: Any, kind: str) -> dict[str, Any]:
    found = status(session, kind, record)
    item = found["last"]
    found["can_review"] = bool(
        item
        and item["outcome"] in ("answered", "concerns")
        and principal.assesses_unit(record.org_unit_id)
    )
    return {"privacy_impact": found}


PROCESS.extra["detail"] = lambda session, principal, record: detail(
    session, principal, record, "process"
)
SYSTEM.extra["detail"] = lambda session, principal, record: detail(
    session, principal, record, "system"
)
