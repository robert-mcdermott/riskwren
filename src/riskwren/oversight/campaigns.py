"""Campaigns: a set of people asked to do one thing by a date (OVS-04).

A campaign asks the owners of controls to attest that each still operates, the owners of
risks to look at them again, the stewards of units to confirm their records are complete,
whoever runs a system to describe how it is protected, or the owners of controls for a named
piece of evidence. It tracks who has answered, reminds those who have not, and shows
coverage by unit.

What is answered is kept as a questionnaire response, against the version the campaign was
launched with. An attestation is the owner's word. It is recorded on the control and shown
apart from the rating, and it is never a test (AST-08).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from riskwren.access import roles
from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    Account,
    Campaign,
    CampaignItem,
    Control,
    Evidence,
    EvidenceLink,
    Implementation,
    OrgUnit,
    Questionnaire,
    RecordOwner,
    Response,
    Risk,
    Scope,
    System,
)
from riskwren.db.models import (
    RoleGrant as RoleGrantRow,
)
from riskwren.db.refs import next_ref
from riskwren.events import audit
from riskwren.oversight import questionnaires
from riskwren.people import notices, units


@dataclass(frozen=True)
class Kind:
    key: str
    label: str
    asks: str  # who is asked, in a few words
    subject: str  # the kind of thing each item is about
    questionnaire: str | None
    by_scope: bool = False  # whether it can be limited to what a compliance scope uses


KINDS: dict[str, Kind] = {
    kind.key: kind
    for kind in (
        Kind(
            "attestation",
            "Control attestation",
            "The owners of controls",
            "control",
            "control-attestation",
            by_scope=True,
        ),
        Kind(
            "self_assessment",
            "Risk self-assessment",
            "The owners of risks",
            "risk",
            "risk-self-assessment",
        ),
        Kind(
            "completeness",
            "Unit completeness check",
            "The stewards of units",
            "org_unit",
            "unit-completeness",
        ),
        Kind(
            "profile",
            "System security profile",
            "The owners of systems",
            "system",
            "system-security-profile",
        ),
        Kind(
            "evidence", "Evidence request", "The owners of controls", "control", None, by_scope=True
        ),
    )
}
PATHS = {"control": "controls", "risk": "risks", "system": "systems"}


# --- Who may --------------------------------------------------------------------------------


def can_run(principal: Principal, org_unit_id: int | None) -> bool:
    """Assessors and managers run campaigns, each for the units they cover."""
    return principal.assesses_unit(org_unit_id)


def can_see(principal: Principal, campaign: Campaign) -> bool:
    return principal.reads_all or can_run(principal, campaign.org_unit_id)


def find(session: Session, principal: Principal, ref: str) -> Campaign:
    row = session.scalars(select(Campaign).where(Campaign.ref == ref.strip().upper())).first()
    if row is None or not can_see(principal, row):
        raise NotFound(f"There is no campaign {ref}.")
    return row


def _answerers(session: Session, item: CampaignItem) -> set[int]:
    """Everyone who may answer an item: whoever was asked, and any other owner of its subject."""
    people = {item.account_id} if item.account_id else set()
    if item.subject_type != "org_unit":
        people |= set(notices.owners(session, item.subject_type, item.subject_id))
    return people


def find_item(
    session: Session, principal: Principal, item_id: int
) -> tuple[CampaignItem, Campaign]:
    item = session.get(CampaignItem, item_id)
    campaign = session.get(Campaign, item.campaign_id) if item else None
    if item is None or campaign is None:
        raise NotFound("There is no such request.")
    mine = principal.account_id in _answerers(session, item)
    if item.subject_type == "org_unit" and principal.covers(roles.STEWARD, item.subject_id):
        mine = True
    if not (mine or can_see(principal, campaign)):
        raise NotFound("There is no such request.")
    return item, campaign


def may_answer(session: Session, principal: Principal, item: CampaignItem) -> bool:
    if principal.account_id in _answerers(session, item):
        return True
    return item.subject_type == "org_unit" and principal.covers(roles.STEWARD, item.subject_id)


# --- Who is asked ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Asked:
    subject_type: str
    subject_id: int
    ref: str | None
    name: str
    org_unit_id: int | None
    account_id: int | None


def _first_owner(session: Session, record_type: str, record_id: int) -> int | None:
    """The owner to ask: an owner before a delegate, the longest named first."""
    rows = session.execute(
        select(RecordOwner.account_id, RecordOwner.kind)
        .join(Account, Account.id == RecordOwner.account_id)
        .where(
            RecordOwner.record_type == record_type,
            RecordOwner.record_id == record_id,
            Account.status != "disabled",
        )
        .order_by(RecordOwner.id)
    ).all()
    owners = [account for account, kind in rows if kind == "owner"]
    return (owners or [account for account, _ in rows] or [None])[0]


def audience(
    session: Session, kind: Kind, org_unit_id: int | None, scope: Scope | None
) -> list[Asked]:
    """Everything the campaign is about, each with whoever is asked. Something with nobody
    to ask is still listed, so that the gap shows."""
    within = units.with_descendants(session, [org_unit_id]) if org_unit_id else None
    found: list[Asked] = []
    if kind.subject == "control":
        query = select(Control).where(Control.status == "active").order_by(Control.id)
        if scope is not None:
            used = select(Implementation.control_id).where(
                Implementation.scope_id == scope.id,
                Implementation.inheritance != "inherited",
                Implementation.status != "not_applicable",
            )
            query = query.where(Control.id.in_(used))
        rows: list[Any] = list(session.scalars(query))
    elif kind.subject == "risk":
        rows = list(session.scalars(select(Risk).where(Risk.status == "open").order_by(Risk.id)))
    elif kind.subject == "system":
        rows = list(
            session.scalars(select(System).where(System.status == "active").order_by(System.id))
        )
    else:
        stewards: dict[int, int] = {}
        for account, unit in session.execute(
            select(RoleGrantRow.account_id, RoleGrantRow.org_unit_id)
            .join(Account, Account.id == RoleGrantRow.account_id)
            .where(RoleGrantRow.role == roles.STEWARD, Account.status != "disabled")
            .order_by(RoleGrantRow.id)
        ):
            if unit is not None:
                stewards.setdefault(unit, account)
        for unit_row in session.scalars(
            select(OrgUnit).where(OrgUnit.status == "active").order_by(OrgUnit.id)
        ):
            if (within is None or unit_row.id in within) and unit_row.id in stewards:
                found.append(
                    Asked(
                        "org_unit",
                        unit_row.id,
                        unit_row.code,
                        unit_row.name,
                        unit_row.id,
                        stewards[unit_row.id],
                    )
                )
        return found
    for row in rows:
        if within is not None and scope is None and row.org_unit_id not in within:
            continue
        found.append(
            Asked(
                kind.subject,
                row.id,
                row.ref,
                row.name,
                row.org_unit_id,
                _first_owner(session, kind.subject, row.id),
            )
        )
    return found


# --- Launching ------------------------------------------------------------------------------


def _check(
    session: Session, principal: Principal, values: Mapping[str, Any]
) -> tuple[Kind, int | None, Scope | None, date]:
    errors: dict[str, str] = {}
    kind = KINDS.get(str(values.get("kind") or ""))
    if kind is None:
        errors["kind"] = f"Choose one of: {', '.join(KINDS)}."
    if not str(values.get("name") or "").strip():
        errors["name"] = "Give the campaign a name."
    unit_id = int(values["org_unit_id"]) if values.get("org_unit_id") else None
    if unit_id is not None and session.get(OrgUnit, unit_id) is None:
        errors["org_unit_id"] = "There is no such unit."
    scope = None
    if values.get("scope"):
        scope = session.scalars(
            select(Scope).where(Scope.ref == str(values["scope"]).strip().upper())
        ).first()
        if scope is None or (kind is not None and not kind.by_scope):
            errors["scope"] = "Choose a scope, for a campaign about controls."
        elif unit_id is None:
            unit_id = scope.org_unit_id  # a campaign over a scope is run for the scope's unit
    due: date | None = None
    try:
        due = date.fromisoformat(str(values.get("due_on") or ""))
    except ValueError:
        errors["due_on"] = "Give the date it is due."
    if due is not None and due <= utc_now().date():
        errors["due_on"] = "Give a date after today."
    if kind is not None and kind.key == "evidence" and not str(values.get("wanted") or "").strip():
        errors["wanted"] = "Say what evidence is wanted."
    if errors:
        raise Invalid("The campaign was not started.", errors)
    assert kind is not None and due is not None
    if not can_run(principal, unit_id):
        raise PermissionDenied(
            "Campaigns are run by assessors and managers, for the units they cover."
        )
    return kind, unit_id, scope, due


def preview(session: Session, principal: Principal, values: Mapping[str, Any]) -> dict[str, Any]:
    """Who a campaign would ask, without starting it."""
    kind, unit_id, scope, _due = _check(session, principal, {"name": "preview", **values})
    asked = audience(session, kind, unit_id, scope)
    return {
        "items": len(asked),
        "people": len({each.account_id for each in asked if each.account_id}),
        "nobody_to_ask": sum(1 for each in asked if each.account_id is None),
        "units": len({each.org_unit_id for each in asked if each.org_unit_id}),
    }


def launch(session: Session, principal: Principal, values: Mapping[str, Any]) -> Campaign:
    kind, unit_id, scope, due = _check(session, principal, values)
    asked = audience(session, kind, unit_id, scope)
    if not asked:
        raise Invalid("The campaign was not started.", {"kind": "There is nobody to ask."})
    row = questionnaires.find(session, kind.questionnaire) if kind.questionnaire else None
    if row is not None and row.status != "active":
        raise Conflict(f"{row.title} is no longer used, so nothing can be asked with it.")
    names = dict(
        session.execute(
            select(Account.id, Account.display_name).where(
                Account.id.in_({each.account_id for each in asked if each.account_id} or {0})
            )
        ).all()
    )
    with audit.operation(session, "campaign.launch"):
        campaign = Campaign(
            ref=next_ref(session, "CMP"),
            name=str(values["name"]).strip(),
            summary=str(values.get("summary") or "").strip() or None,
            kind=kind.key,
            questionnaire_id=row.id if row else None,
            version_number=row.current_version if row else None,
            org_unit_id=unit_id,
            scope_id=scope.id if scope else None,
            wanted=str(values.get("wanted") or "").strip() or None,
            due_on=due,
            created_by=principal.account_id,
            created_by_name=principal.name,
            created_at=utc_now(),
        )
        session.add(campaign)
        session.flush()
        for each in asked:
            session.add(
                CampaignItem(
                    campaign_id=campaign.id,
                    subject_type=each.subject_type,
                    subject_id=each.subject_id,
                    subject_ref=each.ref,
                    subject_name=each.name,
                    org_unit_id=each.org_unit_id,
                    account_id=each.account_id,
                    account_name=names.get(each.account_id) if each.account_id else None,
                )
            )
        session.flush()
    _tell_pending(session, campaign, principal, first=True)
    return campaign


def _tell_pending(
    session: Session, campaign: Campaign, by: Principal | None, *, first: bool = False
) -> int:
    """One notice to each person with something still to answer, saying how many."""
    counts: dict[int, int] = {}
    for account in session.scalars(
        select(CampaignItem.account_id).where(
            CampaignItem.campaign_id == campaign.id,
            CampaignItem.status == "pending",
            CampaignItem.account_id.is_not(None),
        )
    ):
        counts[account] = counts.get(account, 0) + 1
    told = 0
    for account, count in counts.items():
        things = "1 thing" if count == 1 else f"{count} things"
        start = "You have been asked for" if first else "Still waiting on you:"
        text = f"{start} {things} in {campaign.name}, by {campaign.due_on.isoformat()}"
        told += notices.tell(
            session, account, "campaign", text, "/?campaign=" + campaign.ref, by=by
        )
    return told


# --- Answering ------------------------------------------------------------------------------


def _done(item: CampaignItem, principal: Principal, outcome: str | None) -> None:
    item.status, item.outcome = "done", outcome
    item.completed_at, item.completed_by_name = utc_now(), principal.name


def answer(
    session: Session,
    principal: Principal,
    item: CampaignItem,
    campaign: Campaign,
    answers: Mapping[str, Any],
    *,
    complete: bool = True,
) -> CampaignItem:
    """Keep someone's answers to what they were asked. Finished answers mark the item done
    and have their effect: an attestation is recorded on the control, and anything that needs
    someone else to act is told to them."""
    if not may_answer(session, principal, item):
        raise PermissionDenied("This was asked of someone else.")
    if campaign.status != "open":
        raise Conflict("This campaign has ended.")
    if item.status != "pending":
        raise Conflict("This has already been answered.")
    if campaign.questionnaire_id is None:
        raise Conflict(
            "This asks for evidence, not for answers. Attach the evidence to the control."
        )
    row = session.get(Questionnaire, campaign.questionnaire_id)
    assert row is not None
    version = questionnaires.version_of(session, row, campaign.version_number)
    earlier = session.get(Response, item.response_id) if item.response_id else None
    if earlier is not None and earlier.account_id != principal.account_id:
        earlier = None  # another owner began it; this person's answers are their own
    response = questionnaires.answer(
        session,
        principal,
        row,
        answers,
        complete=complete,
        response=earlier,
        version=version,
        subject=(item.subject_type, item.subject_id),
    )
    with audit.operation(session, "campaign.answer"):
        item.response_id = response.id
        if complete:
            _done(item, principal, _effect(session, principal, item, campaign, response.answers))
        session.flush()
    return item


def _effect(
    session: Session,
    principal: Principal,
    item: CampaignItem,
    campaign: Campaign,
    said: Mapping[str, Any],
) -> str | None:
    """What finished answers change or set in motion. Returns the outcome in a word."""
    unit = item.org_unit_id
    stewards = notices.holders(session, [roles.STEWARD], unit) if unit else []
    watchers = notices.holders(session, [roles.ASSESSOR, roles.MANAGER], unit) if unit else []
    href = f"/campaigns/{campaign.ref}?item={item.id}"
    what = f"{item.subject_ref or ''} {item.subject_name}".strip()
    if campaign.kind == "attestation":
        control = session.get(Control, item.subject_id)
        operates = str(said.get("operates"))
        if control is not None:
            control.attested_operates = operates
            control.attested_at, control.attested_by_name = utc_now(), principal.name
        if operates != "yes":
            word = "only partly operates" if operates == "partly" else "does not operate"
            notices.tell_all(
                session,
                [*watchers, *stewards],
                "attestation",
                f"{principal.name} says {what} {word} as described",
                href,
                by=principal,
            )
        if said.get("owner_right") is False:
            notices.tell_all(
                session,
                stewards,
                "attestation",
                f"{principal.name} says someone else should answer for {what}",
                href,
                by=principal,
            )
        return operates
    if campaign.kind == "self_assessment":
        if said.get("relevant") is False:
            outcome = "no_longer_stands"
            text = f"{principal.name} says {what} no longer stands"
        elif said.get("rating_right") is False:
            outcome = "rating_not_right"
            text = f"{principal.name} says the rating of {what} is no longer right"
        else:
            return "stands"
        notices.tell_all(session, [*stewards, *watchers], "campaign", text, href, by=principal)
        return outcome
    if campaign.kind == "completeness":
        gaps = (
            said.get("complete") in ("mostly", "no")
            or said.get("new_this_year") is True
            or said.get("retired") is True
            or said.get("owners_right") is False
            or said.get("unrecorded") is True
        )
        if gaps:
            notices.tell_all(
                session,
                watchers,
                "campaign",
                f"{principal.name} says the records of {item.subject_name} need attention",
                href,
                by=principal,
            )
        return "gaps" if gaps else "complete"
    return None


def refresh(session: Session, campaign: Campaign) -> int:
    """Close the evidence requests that have been met: evidence attached to the control since
    it was asked for. Returns how many."""
    if campaign.kind != "evidence" or campaign.status != "open":
        return 0
    met = 0
    for item in session.scalars(
        select(CampaignItem).where(
            CampaignItem.campaign_id == campaign.id, CampaignItem.status == "pending"
        )
    ):
        found = session.scalars(
            select(Evidence)
            .join(EvidenceLink, EvidenceLink.evidence_id == Evidence.id)
            .where(
                EvidenceLink.subject_type == "control",
                EvidenceLink.subject_id == item.subject_id,
                Evidence.status == "active",
                Evidence.created_at > campaign.created_at,
            )
            .order_by(Evidence.id)
        ).first()
        if found is not None:
            item.status, item.evidence_id, item.outcome = "done", found.id, "attached"
            item.completed_at = found.created_at
            met += 1
    session.flush()
    return met


def refresh_all(session: Session) -> int:
    """The scheduler's turn: evidence requests that have been met are closed."""
    return sum(
        refresh(session, campaign)
        for campaign in session.scalars(
            select(Campaign).where(Campaign.kind == "evidence", Campaign.status == "open")
        )
    )


# --- Running one ----------------------------------------------------------------------------


def _require_run(principal: Principal, campaign: Campaign) -> None:
    if not can_run(principal, campaign.org_unit_id):
        raise PermissionDenied(
            "Campaigns are run by assessors and managers, for the units they cover."
        )


def remind(session: Session, principal: Principal, campaign: Campaign) -> int:
    _require_run(principal, campaign)
    if campaign.status != "open":
        raise Conflict("This campaign has ended.")
    return _tell_pending(session, campaign, principal)


def excuse(
    session: Session, principal: Principal, item: CampaignItem, campaign: Campaign, note: str
) -> CampaignItem:
    """Take something out of a campaign: the control was retired, or the person has left."""
    _require_run(principal, campaign)
    if item.status != "pending":
        raise Conflict("This has already been answered.")
    if not note.strip():
        raise Invalid("It was not excused.", {"note": "Say why it need not be answered."})
    with audit.operation(session, "campaign.excuse"):
        item.status, item.note = "excused", note.strip()
        item.completed_at, item.completed_by_name = utc_now(), principal.name
        session.flush()
    return item


def end(
    session: Session, principal: Principal, campaign: Campaign, *, cancel: bool = False
) -> None:
    """Close a campaign, keeping what was answered; or cancel one started in error."""
    _require_run(principal, campaign)
    if campaign.status != "open":
        raise Conflict("This campaign has already ended.")
    with audit.operation(session, "campaign.end"):
        campaign.status = "cancelled" if cancel else "closed"
        campaign.closed_at, campaign.closed_by_name = utc_now(), principal.name
        session.flush()


def _questionnaire(session: Session, campaign: Campaign) -> Questionnaire | None:
    if campaign.questionnaire_id is None:
        return None
    return session.get(Questionnaire, campaign.questionnaire_id)


# --- Showing --------------------------------------------------------------------------------


def _counts(session: Session, campaign_ids: list[int]) -> dict[int, dict[str, int]]:
    found: dict[int, dict[str, int]] = {
        each: {"pending": 0, "done": 0, "excused": 0} for each in campaign_ids
    }
    for campaign_id, status, count in session.execute(
        select(CampaignItem.campaign_id, CampaignItem.status, func.count())
        .where(CampaignItem.campaign_id.in_(campaign_ids or [0]))
        .group_by(CampaignItem.campaign_id, CampaignItem.status)
    ):
        found[campaign_id][status] = count
    return found


def summary(session: Session, campaign: Campaign, counts: dict[str, int]) -> dict[str, Any]:
    kind = KINDS[campaign.kind]
    unit = session.get(OrgUnit, campaign.org_unit_id) if campaign.org_unit_id else None
    scope = session.get(Scope, campaign.scope_id) if campaign.scope_id else None
    asked = counts["pending"] + counts["done"]
    today = utc_now().date()
    return {
        "ref": campaign.ref,
        "name": campaign.name,
        "summary": campaign.summary,
        "kind": campaign.kind,
        "kind_label": kind.label,
        "asks": kind.asks,
        "status": campaign.status,
        "due_on": campaign.due_on,
        "overdue": campaign.status == "open" and campaign.due_on < today and counts["pending"] > 0,
        "unit": {"id": unit.id, "name": unit.name} if unit else None,
        "scope": {"ref": scope.ref, "name": scope.name} if scope else None,
        "wanted": campaign.wanted,
        "started_by": campaign.created_by_name,
        "started_at": campaign.created_at,
        "closed_at": campaign.closed_at,
        "closed_by": campaign.closed_by_name,
        "counts": {**counts, "asked": asked},
        "answered": round(100 * counts["done"] / asked) if asked else 100,
    }


def search(session: Session, principal: Principal, *, status: str | None = None) -> list[dict]:
    query = select(Campaign).order_by(Campaign.id.desc())
    if status in ("open", "closed", "cancelled"):
        query = query.where(Campaign.status == status)
    rows = [row for row in session.scalars(query) if can_see(principal, row)]
    counts = _counts(session, [row.id for row in rows])
    return [summary(session, row, counts[row.id]) for row in rows]


def item_view(session: Session, principal: Principal, item: CampaignItem) -> dict[str, Any]:
    path = PATHS.get(item.subject_type)
    return {
        "id": item.id,
        "subject": {
            "type": item.subject_type,
            "ref": item.subject_ref,
            "name": item.subject_name,
            "href": f"/{path}/{item.subject_ref}" if path and item.subject_ref else None,
        },
        "org_unit_id": item.org_unit_id,
        "asked": item.account_name,
        "asked_id": item.account_id,
        "status": item.status,
        "outcome": item.outcome,
        "note": item.note,
        "completed_at": item.completed_at,
        "completed_by": item.completed_by_name,
        "response_id": item.response_id,
        "can_answer": item.status == "pending" and may_answer(session, principal, item),
    }


def view(session: Session, principal: Principal, campaign: Campaign) -> dict[str, Any]:
    """A campaign in full: how far it has got, coverage by unit, and every item."""
    items = session.scalars(
        select(CampaignItem)
        .where(CampaignItem.campaign_id == campaign.id)
        .order_by(CampaignItem.status.desc(), CampaignItem.subject_name)
    ).all()
    names = dict(session.execute(select(OrgUnit.id, OrgUnit.name)).all())
    by_unit: dict[int | None, dict[str, int]] = {}
    for item in items:
        tally = by_unit.setdefault(item.org_unit_id, {"pending": 0, "done": 0, "excused": 0})
        tally[item.status] += 1
    coverage = [
        {
            "unit": {"id": unit_id, "name": names.get(unit_id, "No unit")},
            **tally,
            "asked": tally["pending"] + tally["done"],
            "answered": round(100 * tally["done"] / (tally["pending"] + tally["done"]))
            if tally["pending"] + tally["done"]
            else 100,
        }
        for unit_id, tally in by_unit.items()
    ]
    coverage.sort(key=lambda row: (row["answered"], row["unit"]["name"]))
    outcomes: dict[str, int] = {}
    for item in items:
        if item.status == "done" and item.outcome:
            outcomes[item.outcome] = outcomes.get(item.outcome, 0) + 1
    row = (
        session.get(Questionnaire, campaign.questionnaire_id) if campaign.questionnaire_id else None
    )
    return {
        **summary(session, campaign, _counts(session, [campaign.id])[campaign.id]),
        "questionnaire": {"key": row.key, "title": row.title, "version": campaign.version_number}
        if row
        else None,
        "coverage": coverage,
        "outcomes": outcomes,
        "nobody_to_ask": sum(1 for i in items if i.account_id is None and i.status == "pending"),
        "items": [item_view(session, principal, item) for item in items],
        "can": {"run": can_run(principal, campaign.org_unit_id) and campaign.status == "open"},
    }


def item_detail(
    session: Session, principal: Principal, item: CampaignItem, campaign: Campaign
) -> dict[str, Any]:
    """What one person is asked: the campaign, the thing it is about, the questions, and any
    answers they have begun or given."""
    row = (
        session.get(Questionnaire, campaign.questionnaire_id) if campaign.questionnaire_id else None
    )
    document = (
        questionnaires.version_of(session, row, campaign.version_number).document if row else None
    )
    response = session.get(Response, item.response_id) if item.response_id else None
    about: dict[str, Any] = {}
    if item.subject_type == "control":
        control = session.get(Control, item.subject_id)
        about = {"statement": control.statement if control else None}
    elif item.subject_type == "risk":
        risk = session.get(Risk, item.subject_id)
        about = {"statement": risk.summary if risk else None}
    mine = response is not None and response.account_id == principal.account_id
    return {
        **item_view(session, principal, item),
        "campaign": {
            "ref": campaign.ref,
            "name": campaign.name,
            "kind": campaign.kind,
            "kind_label": KINDS[campaign.kind].label,
            "due_on": campaign.due_on,
            "status": campaign.status,
            "wanted": campaign.wanted,
            "started_by": campaign.created_by_name,
            "summary": campaign.summary,
            "can_see": can_see(principal, campaign),
        },
        "about": about,
        "questionnaire": {"title": row.title, "document": document} if row else None,
        "draft": response.answers if response and response.status == "draft" and mine else None,
        "as_asked": questionnaires.as_asked(document, response.answers)
        if response and response.status == "submitted" and document
        else None,
    }


def waiting_on(session: Session, principal: Principal) -> list[tuple[CampaignItem, Campaign]]:
    """What open campaigns still want from this person."""
    if principal.account_id is None:
        return []
    return [
        (item, campaign)
        for item, campaign in session.execute(
            select(CampaignItem, Campaign)
            .join(Campaign, Campaign.id == CampaignItem.campaign_id)
            .where(
                CampaignItem.account_id == principal.account_id,
                CampaignItem.status == "pending",
                Campaign.status == "open",
            )
            .order_by(Campaign.due_on, CampaignItem.id)
            .limit(200)
        ).all()
    ]
