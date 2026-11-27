"""Reminders and escalation: what is nearly due or late, and who is told (OVS-03).

One pass looks at everything with a date on it: actions, risk reviews, issues, evidence,
acceptances, exceptions, the next test of each control, and the review of each document.
Whoever a thing is waiting on is
reminded shortly before its date and again when it passes. If it stays late, the steward of
its unit is told, and later the unit's leader. Each of those is said once for a given date;
moving the date starts again.

A reminder is a notice, so it is read in the app and, where email is set up, sent as each
person has chosen. Nothing here changes a record.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access import roles
from riskwren.controls import service as controls
from riskwren.core.clock import utc_now
from riskwren.db.models import (
    Acceptance,
    Action,
    Campaign,
    CampaignItem,
    Control,
    Evidence,
    ExceptionRequest,
    Indicator,
    Issue,
    PolicyDocument,
    Reminder,
    Risk,
    Scope,
    TreatmentPlan,
)
from riskwren.people import notices
from riskwren.program import rules

DEFAULTS = {"soon_days": 14, "steward_after_days": 7, "leader_after_days": 21}
STAGES = ("soon", "overdue", "steward", "leader")


@dataclass(frozen=True)
class Due:
    """One thing with a date: what it is, who it waits on, and where to go."""

    kind: str
    id: int
    due_on: date
    what: str  # "ACT-0012 Rebuild the call list", as it reads after "Due in 3 days: "
    href: str
    waiting_on: tuple[int, ...]
    unit_id: int | None
    escalates: bool = True
    late: str = "Overdue"  # how being past the date is said


def schedule(session: Session) -> dict[str, int]:
    """When reminders are sent, from the program's cadences."""
    found = rules.get(session, "cadences").get("reminders") or {}
    return {key: int(found.get(key, default)) for key, default in DEFAULTS.items()}


def _action_unit(session: Session, action: Action) -> int | None:
    if action.source_type == "treatment_plan":
        plan = session.get(TreatmentPlan, action.source_id)
        risk = session.get(Risk, plan.risk_id) if plan else None
        return risk.org_unit_id if risk else None
    if action.source_type == "issue":
        issue = session.get(Issue, action.source_id)
        return issue.org_unit_id if issue else None
    return None


def _action_href(session: Session, action: Action) -> str:
    if action.source_type == "issue":
        issue = session.get(Issue, action.source_id)
        if issue is not None:
            return f"/issues/{issue.ref}"
    plan = session.get(TreatmentPlan, action.source_id)
    risk = session.get(Risk, plan.risk_id) if plan else None
    return f"/risks/{risk.ref}?tab=treatment" if risk else "/actions?mine=1"


def due_items(session: Session, today: date, horizon: date) -> Iterator[Due]:
    """Everything with a date on or before the horizon that is still open."""
    for action in session.scalars(
        select(Action).where(Action.status.in_(("open", "in_progress")), Action.due_on <= horizon)
    ):
        yield Due(
            "action", action.id, action.due_on, f"{action.ref} {action.title}",
            _action_href(session, action), (action.owner_id,), _action_unit(session, action),
        )  # fmt: skip
    for risk in session.scalars(
        select(Risk).where(
            Risk.status == "open", Risk.next_review_on.is_not(None), Risk.next_review_on <= horizon
        )
    ):
        assert risk.next_review_on is not None
        yield Due(
            "risk_review", risk.id, risk.next_review_on, f"review of {risk.ref} {risk.name}",
            f"/risks/{risk.ref}", tuple(notices.owners(session, "risk", risk.id)),
            risk.org_unit_id, late="Review overdue",
        )  # fmt: skip
    for issue in session.scalars(
        select(Issue).where(Issue.status == "open", Issue.due_on <= horizon)
    ):
        yield Due(
            "issue", issue.id, issue.due_on, f"{issue.ref} {issue.name}", f"/issues/{issue.ref}",
            tuple(notices.owners(session, "issue", issue.id)), issue.org_unit_id,
        )  # fmt: skip
    for item in session.scalars(
        select(Evidence).where(Evidence.status == "active", Evidence.valid_until <= horizon)
    ):
        yield Due(
            "evidence", item.id, item.valid_until, f"{item.ref} {item.name}",
            f"/evidence/{item.ref}", tuple(notices.owners(session, "evidence", item.id)),
            item.org_unit_id, escalates=False, late="No longer counts",
        )  # fmt: skip
    for acceptance in session.scalars(
        select(Acceptance).where(
            Acceptance.withdrawn_at.is_(None), Acceptance.expires_on <= horizon
        )
    ):
        risk = session.get(Risk, acceptance.risk_id)
        if risk is None or risk.status != "open":
            continue
        people = (*notices.owners(session, "risk", risk.id), acceptance.accepted_by)
        yield Due(
            "acceptance", acceptance.id, acceptance.expires_on,
            f"acceptance of {risk.ref} {risk.name}", f"/risks/{risk.ref}?tab=treatment",
            tuple(dict.fromkeys(people)), risk.org_unit_id, escalates=False,
            late="Acceptance has ended",
        )  # fmt: skip
    for asked in session.scalars(
        select(ExceptionRequest).where(
            ExceptionRequest.status == "approved", ExceptionRequest.expires_on <= horizon
        )
    ):
        scope = session.get(Scope, asked.scope_id) if asked.scope_id else None
        yield Due(
            "exception", asked.id, asked.expires_on, f"exception {asked.ref}",
            f"/exceptions/{asked.ref}", (asked.requested_by,) if asked.requested_by else (),
            scope.org_unit_id if scope else None, escalates=False, late="Exception has ended",
        )  # fmt: skip
    for control in session.scalars(
        select(Control).where(Control.status == "active", Control.rated_at.is_not(None))
    ):
        when = controls.next_test_on(session, control)
        if when is None or when > horizon:
            continue
        yield Due(
            "control_test", control.id, when, f"test of {control.ref} {control.name}",
            f"/controls/{control.ref}", tuple(notices.owners(session, "control", control.id)),
            control.org_unit_id, escalates=False, late="Test overdue",
        )  # fmt: skip


def _campaign_items(session: Session, horizon: date) -> Iterator[Due]:
    """What open campaigns still want, each from the person it was asked of."""
    for item, campaign in session.execute(
        select(CampaignItem, Campaign)
        .join(Campaign, Campaign.id == CampaignItem.campaign_id)
        .where(
            CampaignItem.status == "pending",
            Campaign.status == "open",
            Campaign.due_on <= horizon,
            CampaignItem.account_id.is_not(None),
        )
    ):
        about = f"{item.subject_ref or ''} {item.subject_name}".strip()
        yield Due(
            "campaign_item",
            item.id,
            campaign.due_on,
            f"{campaign.name}: {about}",
            f"/library/{item.subject_ref}"
            if campaign.kind == "acknowledgment"
            else f"/campaign-items/{item.id}",
            (item.account_id,),
            item.org_unit_id,
        )


def _documents(session: Session, horizon: date) -> Iterator[Due]:
    """Documents in force that are due to be looked at again."""
    for document in session.scalars(
        select(PolicyDocument).where(
            PolicyDocument.status == "active",
            PolicyDocument.next_review_on.is_not(None),
            PolicyDocument.next_review_on <= horizon,
        )
    ):
        assert document.next_review_on is not None
        yield Due(
            "document_review",
            document.id,
            document.next_review_on,
            f"review of {document.ref} {document.name}",
            f"/documents/{document.ref}",
            tuple(notices.owners(session, "document", document.id)),
            document.org_unit_id,
            late="Review overdue",
        )


def _readings(session: Session, horizon: date) -> Iterator[Due]:
    """Indicators whose next reading is due. A reading nobody takes is an indicator that
    warns of nothing."""
    from riskwren.risk import indicators

    for indicator in session.scalars(select(Indicator).where(Indicator.status == "active")):
        when = indicators.next_due(indicator)
        # A weekly reading is always nearly due, so nobody is told two weeks ahead of one:
        # only as it falls due.
        if when is None or when > min(horizon, utc_now().date() + timedelta(days=2)):
            continue
        yield Due(
            "indicator_reading",
            indicator.id,
            when,
            f"a reading of {indicator.ref} {indicator.name}",
            f"/indicators/{indicator.ref}",
            tuple(notices.owners(session, "indicator", indicator.id)),
            indicator.org_unit_id,
            escalates=False,
            late="Reading overdue",
        )


def _when(days: int) -> str:
    if days == 0:
        return "today"
    return "tomorrow" if days == 1 else f"in {days} days"


def _late(days: int) -> str:
    return "1 day" if days == 1 else f"{days} days"


def stage_of(due: Due, today: date, plan: dict[str, int]) -> str | None:
    """How far along the reminders for this are: the furthest stage it has reached."""
    late = (today - due.due_on).days
    if late < 1:
        return "soon" if (due.due_on - today).days <= plan["soon_days"] else None
    if due.escalates and late >= plan["leader_after_days"]:
        return "leader"
    if due.escalates and late >= plan["steward_after_days"]:
        return "steward"
    return "overdue"


def send(session: Session, *, today: date | None = None) -> dict[str, int]:
    """Send every reminder that is due and has not been sent. Safe to run at any time: what
    has been said for a date is not said again."""
    today = today or utc_now().date()
    plan = schedule(session)
    horizon = date.fromordinal(today.toordinal() + plan["soon_days"])
    already = {
        (row.subject_type, row.subject_id, row.due_on, row.stage)
        for row in session.scalars(select(Reminder))
    }
    counts = {"reminders": 0, "overdue": 0, "escalated": 0}

    def tell(people: Iterable[int | None], kind: str, text: str, href: str) -> int:
        return notices.tell_all(session, people, kind, text, href)

    everything = [
        *due_items(session, today, horizon),
        *_campaign_items(session, horizon),
        *_readings(session, horizon),
        *_documents(session, horizon),
    ]
    for due in everything:
        stage = stage_of(due, today, plan)
        if stage is None or (due.kind, due.id, due.due_on, stage) in already:
            continue
        # Whatever this stage follows is taken as said: something found already three weeks
        # late is told to the leader once, and not also to everyone below in the same hour.
        for earlier in STAGES[: STAGES.index(stage) + 1]:
            key = (due.kind, due.id, due.due_on, earlier)
            if key not in already:
                already.add(key)
                session.add(
                    Reminder(
                        subject_type=due.kind,
                        subject_id=due.id,
                        due_on=due.due_on,
                        stage=earlier,
                        sent_on=today,
                    )
                )
        late = (today - due.due_on).days
        what = due.what[:300]
        if stage == "soon":
            counts["reminders"] += tell(
                due.waiting_on, "reminder", f"Due {_when(-late)}: {what}", due.href
            )
        elif stage == "overdue":
            text = f"{due.late} by {_late(late)}: {what}"
            people: list[int | None] = list(due.waiting_on)
            if due.kind == "control_test" and due.unit_id is not None:
                # A test is the assessors' to do; the owner cannot test their own control.
                people += notices.holders(session, [roles.ASSESSOR], due.unit_id)
            counts["overdue"] += tell(people, "overdue", text, due.href)
        elif due.unit_id is not None:
            role = roles.STEWARD if stage == "steward" else roles.LEADER
            above = [
                each for each in notices.holders(session, [role], due.unit_id)
                if each not in due.waiting_on
            ]  # fmt: skip
            text = f"{due.late} by {_late(late)}, and now with you: {what}"
            counts["escalated"] += tell(above, "escalated", text, due.href)
    session.flush()
    return counts


def view(session: Session) -> dict[str, Any]:
    """The schedule, for showing beside the rest of the program."""
    return schedule(session)
