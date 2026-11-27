"""Responses, treatment plans, actions, and acceptance (see spec/engine.md).

Every risk above appetite needs a response. A plan brings it down through actions with
owners and dates; an acceptance is a statement by a named person, with the authority for
that rating, that what remains will be lived with until a date. Nobody accepts a risk they
own.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from riskwren.access import roles
from riskwren.access.principal import Principal
from riskwren.core import scoring
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import Acceptance, Account, Action, Risk, TreatmentPlan
from riskwren.db.models.risk import RESPONSES
from riskwren.db.refs import next_ref, parse_ref
from riskwren.events import audit
from riskwren.events.actor import Actor
from riskwren.inventory import access, records
from riskwren.people import units
from riskwren.program import rules
from riskwren.risk import categories
from riskwren.risk import method as methods
from riskwren.risk import register as risks
from riskwren.risk.register import RISK

PLAN = "treatment_plan"
OPEN = ("open", "in_progress")


@dataclass(frozen=True)
class Source:
    """Something other than a treatment plan that actions can belong to (an issue, and later
    an incident or an audit finding). It says who manages its actions, what follows when one
    changes, how it is shown beside an action, and who may see it."""

    key: str
    manage: Callable[[Session, Principal, int], bool]
    settle: Callable[[Session, int], None]
    describe: Callable[[Session, Principal, int], dict[str, Any] | None]
    visible: Callable[[Session, Principal], Any]
    in_units: Callable[[list[int]], Any]


SOURCES: dict[str, Source] = {}


def register_source(source: Source) -> Source:
    SOURCES[source.key] = source
    return source


def _day(value: Any, field: str, errors: records.Errors) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        errors.add(field, "Give a date, as year-month-day.")
        return None


def _person(session: Session, value: Any, field: str, errors: records.Errors) -> Account | None:
    account = session.get(Account, int(value)) if str(value).isdigit() else None
    if account is None or account.status == "disabled":
        errors.add(field, "Choose a person whose account is not disabled.")
        return None
    return account


# --- The response -------------------------------------------------------------------------


def respond(
    session: Session, principal: Principal, risk: Risk, response: str | None, rationale: str | None
) -> Risk:
    """Record what is to be done about a risk: reduce, accept, transfer, or avoid, and why."""
    if not access.can_edit(session, principal, RISK, risk):
        raise PermissionDenied("You cannot edit this risk.")
    errors = records.Errors()
    if response not in RESPONSES:
        errors.add("response", f"Choose one of: {', '.join(RESPONSES)}.")
    reason = records.text(rationale)
    if not reason:
        errors.add("rationale", "Say why this is the right response.")
    if errors:
        raise Invalid("The response was not recorded.", errors)
    with audit.operation(session, "risk.respond"):
        risk.response, risk.response_rationale = response, reason
        records.touch(session, risk)
    return risk


# --- Plans and actions --------------------------------------------------------------------


def find_plan(session: Session, ref: str) -> TreatmentPlan:
    parsed = parse_ref(ref)
    plan = (
        session.scalars(
            select(TreatmentPlan).where(TreatmentPlan.ref == ref.strip().upper())
        ).first()
        if parsed and parsed[0] == "PLN"
        else None
    )
    if plan is None:
        raise NotFound(f"There is no treatment plan {ref}.")
    return plan


def find_action(session: Session, ref: str) -> Action:
    parsed = parse_ref(ref)
    action = (
        session.scalars(select(Action).where(Action.ref == ref.strip().upper())).first()
        if parsed and parsed[0] == "ACT"
        else None
    )
    if action is None:
        raise NotFound(f"There is no action {ref}.")
    return action


def risk_of(session: Session, plan: TreatmentPlan) -> Risk:
    risk = session.get(Risk, plan.risk_id)
    assert risk is not None
    return risk


def create_plan(
    session: Session,
    principal: Principal,
    risk: Risk,
    *,
    objective: str | None,
    owner_id: Any,
    due_on: Any,
    target_rating: str | None = None,
) -> TreatmentPlan:
    """Open a plan to bring a risk down. Its actions are added to it afterwards."""
    if not access.can_edit(session, principal, RISK, risk):
        raise PermissionDenied("You cannot edit this risk.")
    if risk.status == "closed":
        raise Conflict("This risk is closed.")
    errors = records.Errors()
    goal = records.text(objective)
    if not goal:
        errors.add("objective", "Say what the plan will achieve.")
    owner = _person(session, owner_id, "owner_id", errors)
    due = _day(due_on, "due_on", errors)
    if target_rating and target_rating not in scoring.rating_keys(methods.current(session)):
        errors.add("target_rating", "Choose one of the ratings.")
    if errors:
        raise Invalid("The plan was not saved.", errors)
    assert goal is not None and owner is not None and due is not None
    with audit.operation(session, "plan.create"):
        plan = TreatmentPlan(
            ref=next_ref(session, "PLN"),
            risk_id=risk.id,
            objective=goal,
            target_rating=target_rating or risk.target_rating,
            owner_id=owner.id,
            due_on=due,
            status="active",
            created_by=principal.account_id,
            created_at=utc_now(),
        )
        session.add(plan)
        session.flush()
        if risk.response is None:
            risk.response = "reduce"
            risk.response_rationale = f"Being reduced through {plan.ref}."
        risks.refresh(session, risk)
    return plan


def can_manage(session: Session, principal: Principal, plan: TreatmentPlan) -> bool:
    return plan.owner_id == principal.account_id or access.can_edit(
        session, principal, RISK, risk_of(session, plan)
    )


def cancel_plan(
    session: Session, principal: Principal, plan: TreatmentPlan, reason: str | None
) -> TreatmentPlan:
    if not can_manage(session, principal, plan):
        raise PermissionDenied("You cannot change this plan.")
    if plan.status != "active":
        raise Conflict("This plan is already closed.")
    note = records.text(reason)
    if not note:
        raise Invalid("The plan was not cancelled.", {"reason": "Say why it is being cancelled."})
    with audit.operation(session, "plan.cancel"):
        plan.status, plan.closed_note, plan.closed_at = "cancelled", note, utc_now()
        for action in session.scalars(
            select(Action).where(
                Action.source_type == PLAN, Action.source_id == plan.id, Action.status.in_(OPEN)
            )
        ):
            action.status = "cancelled"
        session.flush()
        risks.refresh(session, risk_of(session, plan))
    return plan


def add_action(
    session: Session,
    principal: Principal,
    plan: TreatmentPlan,
    *,
    title: str | None,
    owner_id: Any,
    due_on: Any,
    detail: str | None = None,
) -> Action:
    if not can_manage(session, principal, plan):
        raise PermissionDenied("You cannot change this plan.")
    if plan.status != "active":
        raise Conflict("This plan is closed.")
    return new_action(
        session, principal, PLAN, plan.id, title=title, owner_id=owner_id, due_on=due_on,
        detail=detail,
    )  # fmt: skip


def new_action(
    session: Session,
    principal: Principal,
    source_type: str,
    source_id: int,
    *,
    title: str | None,
    owner_id: Any,
    due_on: Any,
    detail: str | None = None,
) -> Action:
    """Write an action for a plan or another source. Whether the person may is the caller's
    to have checked."""
    errors = records.Errors()
    name = records.text(title)
    if not name or len(name) > 200:
        errors.add("title", "Say what is to be done, in up to 200 characters.")
    owner = _person(session, owner_id, "owner_id", errors)
    due = _day(due_on, "due_on", errors)
    if errors:
        raise Invalid("The action was not added.", errors)
    assert name is not None and owner is not None and due is not None
    with audit.operation(session, "action.create"):
        action = Action(
            ref=next_ref(session, "ACT"),
            title=name,
            detail=records.text(detail),
            owner_id=owner.id,
            due_on=due,
            original_due_on=due,
            extensions=[],
            status="open",
            source_type=source_type,
            source_id=source_id,
            created_by=principal.account_id,
            created_at=utc_now(),
        )
        session.add(action)
        session.flush()
    return action


def _plan_of(session: Session, action: Action) -> TreatmentPlan | None:
    return session.get(TreatmentPlan, action.source_id) if action.source_type == PLAN else None


def can_act(session: Session, principal: Principal, action: Action) -> bool:
    """Its owner may progress an action; those who manage what it came from may change it."""
    return action.owner_id == principal.account_id or _manages(session, principal, action)


def _manages(session: Session, principal: Principal, action: Action) -> bool:
    plan = _plan_of(session, action)
    if plan is not None:
        return can_manage(session, principal, plan)
    source = SOURCES.get(action.source_type)
    return source is not None and source.manage(session, principal, action.source_id)


def update_action(
    session: Session, principal: Principal, action: Action, changes: Mapping[str, Any]
) -> Action:
    """Progress, finish, reassign, or reschedule an action. Moving its date needs a reason,
    and the original date and every move stay on the record."""
    if not can_act(session, principal, action):
        raise PermissionDenied("This action is not yours to change.")
    plan = _plan_of(session, action)
    manages = _manages(session, principal, action)
    if action.status in ("done", "cancelled") and changes.get("status") not in OPEN:
        raise Conflict("This action is closed. Reopen it to change it.")
    errors = records.Errors()
    if not manages and {"title", "detail", "owner_id"} & set(changes):
        raise PermissionDenied(
            "Only those who manage what it belongs to can rewrite or reassign an action."
        )
    if "title" in changes:
        name = records.text(changes["title"])
        if not name or len(name) > 200:
            errors.add("title", "Say what is to be done, in up to 200 characters.")
        else:
            action.title = name
    if "detail" in changes:
        action.detail = records.text(changes["detail"])
    if "owner_id" in changes:
        owner = _person(session, changes["owner_id"], "owner_id", errors)
        if owner is not None:
            action.owner_id = owner.id
    if changes.get("due_on") is not None:
        due = _day(changes["due_on"], "due_on", errors)
        reason = records.text(changes.get("reason"))
        if due is not None and due != action.due_on:
            if not reason:
                errors.add("reason", "Say why the date is moving.")
            else:
                action.extensions = [
                    *action.extensions,
                    {
                        "from": action.due_on.isoformat(),
                        "to": due.isoformat(),
                        "reason": reason,
                        "by": principal.name,
                        "on": utc_now().date().isoformat(),
                    },
                ]
                action.due_on = due
    status = changes.get("status")
    if status is not None:
        if status not in ("open", "in_progress", "done", "cancelled"):
            errors.add("status", "Use open, in_progress, done, or cancelled.")
        elif status == "cancelled" and not manages:
            raise PermissionDenied("Only those who manage what it belongs to can cancel an action.")
        else:
            action.status = status
            if status == "done":
                action.completed_at = utc_now()
                action.completion_note = records.text(changes.get("completion_note"))
            elif status in OPEN:
                action.completed_at, action.completion_note = None, None
    if errors:
        session.expire(action)
        raise Invalid("The action was not saved.", errors)
    with audit.operation(session, "action.update"):
        session.flush()
        if plan is not None:
            _settle(session, plan)
        elif action.source_type in SOURCES:
            SOURCES[action.source_type].settle(session, action.source_id)
    return action


def _settle(session: Session, plan: TreatmentPlan) -> None:
    """When the last open action of a plan closes, the plan is complete. That does not lower
    the rating: the risk's owner is asked for a new assessment."""
    statuses = session.scalars(
        select(Action.status).where(Action.source_type == PLAN, Action.source_id == plan.id)
    ).all()
    risk = risk_of(session, plan)
    finished = bool(statuses) and "done" in statuses and not set(statuses) & set(OPEN)
    if plan.status == "active" and finished:
        plan.status, plan.closed_at = "complete", utc_now()
        risk.residual_in_doubt = True
        risk.residual_doubt_reason = (
            f"Its treatment plan {plan.ref} is complete. Assess the residual risk again."
        )
    elif plan.status == "complete" and not finished:
        plan.status, plan.closed_at = "active", None  # an action was reopened
    session.flush()
    risks.refresh(session, risk)


# --- Acceptance ---------------------------------------------------------------------------


def in_force(session: Session, risk: Risk, today: date) -> Acceptance | None:
    return session.scalars(
        select(Acceptance)
        .where(
            Acceptance.risk_id == risk.id,
            Acceptance.withdrawn_at.is_(None),
            Acceptance.expires_on >= today,
        )
        .order_by(Acceptance.id.desc())
    ).first()


def authority(session: Session, principal: Principal, risk: Risk) -> dict[str, Any]:
    """Whether this person may accept this risk, the reason if not, and the latest date an
    acceptance could run to."""
    method = methods.current(session)
    today = utc_now().date()
    appetite = categories.Tree(session).appetite(risk.category_id)
    rating = risk.residual_rating
    labels = {r["key"]: r["label"] for r in method["ratings"]}
    out: dict[str, Any] = {"allowed": False, "reason": None, "latest": None, "appetite": appetite}
    if risk.status == "closed" or not scoring.exceeds(method, rating, appetite):
        out["reason"] = "This risk is not above appetite, so there is nothing to accept."
        return out
    assert rating is not None
    rule = rules.get(session, "authority")["acceptance"].get(rating) or {
        "max_months": 12,
        "needs_limit": True,
    }
    out["latest"] = rules.add_months(today, int(rule["max_months"]))
    out["max_months"] = int(rule["max_months"])
    if principal.account_id is None:
        out["reason"] = "A risk is accepted by a named person."
        return out
    kinds = access.owner_kinds(session, RISK, risk.id, principal.account_id)
    if "owner" in kinds:
        out["reason"] = "Nobody accepts a risk they own. It goes to a leader above."
        return out
    covering = [
        grant
        for grant in principal.grants
        if grant.role == roles.LEADER
        and grant.org_unit_id is not None
        and risk.org_unit_id in units.with_descendants(session, [grant.org_unit_id])
    ]
    if not covering:
        out["reason"] = "Only a leader of the risk's unit, or of a unit above it, can accept it."
        return out
    if rule.get("needs_limit"):
        reach = max(scoring.position(method, grant.accept_limit) for grant in covering)
        if reach < scoring.position(method, rating):
            out["reason"] = (
                f"Accepting a {labels.get(rating, rating)} risk needs a leader whose limit "
                f"reaches {labels.get(rating, rating)}."
            )
            return out
    out["allowed"] = True
    return out


def accept(
    session: Session,
    principal: Principal,
    risk: Risk,
    *,
    rationale: str | None,
    expires_on: Any,
    conditions: str | None = None,
) -> Acceptance:
    """Accept what remains of a risk above appetite, until a date. Refused for the risk's
    own owner and for anyone without the authority for its rating."""
    may = authority(session, principal, risk)
    if not may["allowed"]:
        raise PermissionDenied(may["reason"])
    errors = records.Errors()
    reason = records.text(rationale)
    if not reason:
        errors.add("rationale", "Say why this risk is being lived with.")
    until = _day(expires_on, "expires_on", errors)
    today = utc_now().date()
    if until is not None and until <= today:
        errors.add("expires_on", "Choose a date in the future.")
    elif until is not None and until > may["latest"]:
        errors.add(
            "expires_on",
            f"A risk at this rating can be accepted for at most {may['max_months']} months: "
            f"until {may['latest'].isoformat()}.",
        )
    if errors:
        raise Invalid("The acceptance was not recorded.", errors)
    assert reason is not None and until is not None
    assert principal.account_id is not None and risk.residual_rating is not None
    with audit.operation(session, "risk.accept"):
        acceptance = Acceptance(
            risk_id=risk.id,
            rating_accepted=risk.residual_rating,
            likelihood=risk.residual_likelihood,
            impact=risk.residual_impact,
            appetite=may["appetite"],
            rationale=reason,
            conditions=records.text(conditions),
            accepted_by=principal.account_id,
            accepted_by_name=principal.name,
            accepted_at=utc_now(),
            expires_on=until,
        )
        session.add(acceptance)
        session.flush()
        risks.refresh(session, risk)
    return acceptance


def withdraw(
    session: Session, principal: Principal, acceptance: Acceptance, reason: str | None
) -> Acceptance:
    """Take an acceptance back. Whoever gave it may, and so may a manager."""
    risk = session.get(Risk, acceptance.risk_id)
    assert risk is not None
    allowed = acceptance.accepted_by == principal.account_id or principal.manages_unit(
        risk.org_unit_id
    )
    if not allowed:
        raise PermissionDenied("Only whoever accepted the risk, or a manager, can withdraw it.")
    if acceptance.withdrawn_at is not None:
        raise Conflict("This acceptance has already been withdrawn.")
    note = records.text(reason)
    if not note:
        raise Invalid("The acceptance was not withdrawn.", {"reason": "Say why."})
    with audit.operation(session, "risk.acceptance_withdrawn"):
        acceptance.withdrawn_at = utc_now()
        acceptance.withdrawn_by_name, acceptance.withdrawn_reason = principal.name, note
        session.flush()
        risks.refresh(session, risk)
    return acceptance


def find_acceptance(session: Session, principal: Principal, acceptance_id: int) -> Acceptance:
    found = session.get(Acceptance, acceptance_id)
    risk = session.get(Risk, found.risk_id) if found is not None else None
    if found is None or risk is None or not access.can_see(session, principal, RISK, risk):
        raise NotFound("There is no such acceptance.")
    return found


# --- What treatment says about a risk's standing ----------------------------------------------


def standing(session: Session, risk: Risk, today: date) -> str | None:
    """For a risk above appetite: accepted while an acceptance that covers its rating is in
    force; being treated while a plan is active and on time; otherwise it needs a decision."""
    method = methods.current(session)
    acceptance = in_force(session, risk, today)
    if acceptance is not None and scoring.position(
        method, acceptance.rating_accepted
    ) >= scoring.position(method, risk.residual_rating):
        return "accepted"
    on_time = session.scalars(
        select(TreatmentPlan.id).where(
            TreatmentPlan.risk_id == risk.id,
            TreatmentPlan.status == "active",
            TreatmentPlan.due_on >= today,
        )
    ).first()
    return "treated" if on_time is not None else None


risks.TREATMENT.append(standing)


def lapsed(session: Session, today: date) -> list[Risk]:
    """Risks whose standing rests on a date that has now passed: an acceptance that has
    expired, or a plan that is overdue."""
    covered = exists(
        select(Acceptance.id).where(
            Acceptance.risk_id == Risk.id,
            Acceptance.withdrawn_at.is_(None),
            Acceptance.expires_on >= today,
        )
    )
    planned = exists(
        select(TreatmentPlan.id).where(
            TreatmentPlan.risk_id == Risk.id,
            TreatmentPlan.status == "active",
            TreatmentPlan.due_on >= today,
        )
    )
    return list(
        session.scalars(
            select(Risk).where(
                or_(
                    and_(Risk.standing == "accepted", ~covered),
                    and_(Risk.standing == "treated", ~planned, ~covered),
                )
            )
        )
    )


def catch_up(db: Any, *, today: date | None = None) -> int:
    """Bring standings up to date with the calendar. Until scheduled jobs arrive, this runs
    when the register is read; it writes only when a date has actually passed."""
    today = today or utc_now().date()
    with db.read() as session:
        waiting = [risk.id for risk in lapsed(session, today)]
    if not waiting:
        return 0
    with db.write(Actor.command("Calendar")) as session, audit.operation(session, "risk.lapse"):
        for risk in session.scalars(select(Risk).where(Risk.id.in_(waiting))):
            risks.refresh(session, risk, today=today)
    return len(waiting)


# --- Showing ------------------------------------------------------------------------------


def _names(session: Session, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return dict(
        session.execute(select(Account.id, Account.display_name).where(Account.id.in_(ids))).all()
    )


def _contact_of(session: Session, action: Action) -> dict[str, Any] | None:
    """Who at a third party does it, where someone outside does."""
    if action.contact_id is None:
        return None
    from riskwren.db.models import ThirdParty, ThirdPartyContact

    contact = session.get(ThirdPartyContact, action.contact_id)
    party = session.get(ThirdParty, contact.third_party_id) if contact else None
    if contact is None:
        return None
    return {"name": contact.name, "third_party": party.name if party else None}


def action_view(
    session: Session, principal: Principal, action: Action, names: dict[int, str] | None = None
) -> dict[str, Any]:
    names = names or _names(session, {action.owner_id})
    today = utc_now().date()
    plan = _plan_of(session, action)
    risk = risk_of(session, plan) if plan is not None else None
    seen = risk is not None and access.can_see(session, principal, RISK, risk)
    source = SOURCES.get(action.source_type)
    return {
        "ref": action.ref,
        "title": action.title,
        "detail": action.detail,
        "owner": {"account_id": action.owner_id, "name": names.get(action.owner_id, "")},
        "contact": _contact_of(session, action),
        "due_on": action.due_on,
        "original_due_on": action.original_due_on,
        "extensions": action.extensions,
        "status": action.status,
        "overdue": action.status in OPEN and action.due_on < today,
        "completed_at": action.completed_at,
        "completion_note": action.completion_note,
        "plan": plan.ref if plan is not None else None,
        "risk": records.chip(RISK, risk) if seen and risk is not None else None,
        # What it belongs to when that is not a plan: an issue, for one.
        "source": source.describe(session, principal, action.source_id) if source else None,
        "can": {
            "act": can_act(session, principal, action),
            "manage": _manages(session, principal, action),
        },
    }


def plan_view(session: Session, principal: Principal, plan: TreatmentPlan) -> dict[str, Any]:
    actions = session.scalars(
        select(Action)
        .where(Action.source_type == PLAN, Action.source_id == plan.id)
        .order_by(Action.due_on, Action.id)
    ).all()
    names = _names(session, {plan.owner_id, *(a.owner_id for a in actions)})
    risk = risk_of(session, plan)
    counts: dict[str, int] = defaultdict(int)
    for action in actions:
        counts[action.status] += 1
    live = [a for a in actions if a.status != "cancelled"]
    today = utc_now().date()
    return {
        "ref": plan.ref,
        "objective": plan.objective,
        "target_rating": plan.target_rating,
        "owner": {"account_id": plan.owner_id, "name": names.get(plan.owner_id, "")},
        "due_on": plan.due_on,
        "status": plan.status,
        "overdue": plan.status == "active" and plan.due_on < today,
        "closed_note": plan.closed_note,
        "closed_at": plan.closed_at,
        "created_at": plan.created_at,
        "progress": {"done": counts["done"], "total": len(live)},
        "actions": [action_view(session, principal, action, names) for action in actions],
        "risk": {
            **records.chip(RISK, risk),
            "residual_rating": risk.residual_rating,
            "standing": risk.standing,
            "org_unit_id": risk.org_unit_id,
        },
        "can": {"manage": can_manage(session, principal, plan)},
    }


def acceptance_view(
    session: Session, acceptance: Acceptance, risk: Risk | None = None
) -> dict[str, Any]:
    today = utc_now().date()
    state = (
        "withdrawn"
        if acceptance.withdrawn_at is not None
        else "expired"
        if acceptance.expires_on < today
        else "in_force"
    )
    out: dict[str, Any] = {
        "id": acceptance.id,
        "rating_accepted": acceptance.rating_accepted,
        "likelihood": acceptance.likelihood,
        "impact": acceptance.impact,
        "appetite": acceptance.appetite,
        "rationale": acceptance.rationale,
        "conditions": acceptance.conditions,
        "accepted_by": acceptance.accepted_by_name,
        "accepted_by_id": acceptance.accepted_by,
        "accepted_at": acceptance.accepted_at,
        "expires_on": acceptance.expires_on,
        "state": state,
        "expires_in_days": (acceptance.expires_on - today).days if state == "in_force" else None,
        "withdrawn_at": acceptance.withdrawn_at,
        "withdrawn_by": acceptance.withdrawn_by_name,
        "withdrawn_reason": acceptance.withdrawn_reason,
    }
    if risk is not None:
        out["risk"] = {
            **records.chip(RISK, risk),
            "residual_rating": risk.residual_rating,
            "standing": risk.standing,
            "org_unit_id": risk.org_unit_id,
        }
    return out


def of_risk(session: Session, principal: Principal, risk: Risk) -> dict[str, Any]:
    """Everything being done about one risk."""
    plans = session.scalars(
        select(TreatmentPlan)
        .where(TreatmentPlan.risk_id == risk.id)
        .order_by(TreatmentPlan.id.desc())
    ).all()
    acceptances = session.scalars(
        select(Acceptance).where(Acceptance.risk_id == risk.id).order_by(Acceptance.id.desc())
    ).all()
    return {
        "response": risk.response,
        "response_rationale": risk.response_rationale,
        "plans": [plan_view(session, principal, plan) for plan in plans],
        "acceptances": [acceptance_view(session, acceptance) for acceptance in acceptances],
        "authority": authority(session, principal, risk),
    }


def _visible_risk(session: Session, principal: Principal) -> Any:
    seen = access.visible(session, principal, RISK)
    return seen if seen is not None else (Risk.id == Risk.id)


def search_actions(
    session: Session,
    principal: Principal,
    filters: Mapping[str, Any],
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Actions the person owns, or that belong to a risk they may see."""
    today = utc_now().date()
    statement = (
        select(Action)
        .outerjoin(
            TreatmentPlan, and_(Action.source_type == PLAN, Action.source_id == TreatmentPlan.id)
        )
        .outerjoin(Risk, Risk.id == TreatmentPlan.risk_id)
    )
    seen = [and_(Action.source_type == PLAN, _visible_risk(session, principal))]
    for source in SOURCES.values():
        seen.append(and_(Action.source_type == source.key, source.visible(session, principal)))
    conditions: list[Any] = [or_(Action.owner_id == principal.account_id, *seen)]
    owner = principal.account_id if filters.get("mine") else filters.get("owner")
    if owner:
        conditions.append(Action.owner_id == int(owner))
    status = filters.get("status")
    if status == "open":
        conditions.append(Action.status.in_(OPEN))
    elif status:
        conditions.append(Action.status == status)
    if filters.get("overdue"):
        conditions += [Action.status.in_(OPEN), Action.due_on < today]
    if filters.get("unit"):
        within = list(units.with_descendants(session, [int(filters["unit"])]))
        conditions.append(
            or_(
                Risk.org_unit_id.in_(within),
                *(
                    and_(Action.source_type == source.key, source.in_units(within))
                    for source in SOURCES.values()
                ),
            )
        )
    words = records.text(filters.get("q"))
    if words:
        like = f"%{words.lower()}%"
        conditions.append(
            or_(func.lower(Action.title).like(like), func.lower(Action.ref).like(like))
        )
    total = session.execute(
        select(func.count()).select_from(statement.where(*conditions).subquery())
    ).scalar_one()
    rows = session.scalars(
        statement.where(*conditions).order_by(Action.due_on, Action.id).limit(limit).offset(offset)
    ).all()
    names = _names(session, {row.owner_id for row in rows})
    return [action_view(session, principal, row, names) for row in rows], total


def search_plans(
    session: Session, principal: Principal, filters: Mapping[str, Any]
) -> list[dict[str, Any]]:
    today = utc_now().date()
    conditions: list[Any] = [_visible_risk(session, principal)]
    status = filters.get("status")
    if status:
        conditions.append(TreatmentPlan.status == status)
    if filters.get("overdue"):
        conditions += [TreatmentPlan.status == "active", TreatmentPlan.due_on < today]
    if filters.get("mine"):
        conditions.append(TreatmentPlan.owner_id == principal.account_id)
    if filters.get("unit"):
        conditions.append(
            Risk.org_unit_id.in_(units.with_descendants(session, [int(filters["unit"])]))
        )
    rows = session.scalars(
        select(TreatmentPlan)
        .join(Risk, Risk.id == TreatmentPlan.risk_id)
        .where(*conditions)
        .order_by(TreatmentPlan.due_on, TreatmentPlan.id)
        .limit(200)
    ).all()
    return [plan_view(session, principal, plan) for plan in rows]


def search_acceptances(
    session: Session, principal: Principal, filters: Mapping[str, Any]
) -> list[dict[str, Any]]:
    today = utc_now().date()
    conditions: list[Any] = [_visible_risk(session, principal)]
    state = filters.get("state")
    if state == "in_force":
        conditions += [Acceptance.withdrawn_at.is_(None), Acceptance.expires_on >= today]
    elif state == "expired":
        conditions += [Acceptance.withdrawn_at.is_(None), Acceptance.expires_on < today]
    elif state == "withdrawn":
        conditions.append(Acceptance.withdrawn_at.is_not(None))
    if filters.get("expiring_within"):
        soon = rules.add_months(today, 0).toordinal() + int(filters["expiring_within"])
        conditions += [
            Acceptance.withdrawn_at.is_(None),
            Acceptance.expires_on >= today,
            Acceptance.expires_on <= date.fromordinal(soon),
        ]
    if filters.get("mine"):
        conditions.append(Acceptance.accepted_by == principal.account_id)
    if filters.get("unit"):
        conditions.append(
            Risk.org_unit_id.in_(units.with_descendants(session, [int(filters["unit"])]))
        )
    rows = session.execute(
        select(Acceptance, Risk)
        .join(Risk, Risk.id == Acceptance.risk_id)
        .where(*conditions)
        .order_by(Acceptance.expires_on, Acceptance.id)
        .limit(200)
    ).all()
    return [acceptance_view(session, acceptance, risk) for acceptance, risk in rows]
