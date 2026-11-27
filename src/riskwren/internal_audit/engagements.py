"""Engagements and workpapers (AUD-03, AUD-04, AUD-07).

An engagement planned in a period's plan is started by an auditor with a team and a lead. It
moves through planning, fieldwork, and reporting to reported. Its program of work is a list
of steps, each with a workpaper: what was to be done, what was done, what was found, and the
evidence. A workpaper is signed off by a member of the team other than the one who prepared
it, once every review note on it has been cleared. Fieldwork ends when every workpaper is
signed off; the report is issued with a summary and an opinion.

Independence: until the engagement is reported, its work is seen by its team alone. Others
who may read the plan see that it exists and where it stands, and nothing of what was done
or found. The history records every change to a workpaper and to a review note, but keeps
their words out of it, so that reading the history does not undo that.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access import roles
from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    Account,
    AuditPlan,
    Engagement,
    EngagementMember,
    Evidence,
    ReviewNote,
    RoleGrant,
    Workpaper,
)
from riskwren.db.models.audit import OPINIONS
from riskwren.events import audit
from riskwren.internal_audit import plans, universe
from riskwren.inventory import records

NEXT = {"planning": "fieldwork", "fieldwork": "reporting", "reporting": "reported"}
OPINION_LABELS = {
    "effective": "Effective",
    "needs_improvement": "Needs improvement",
    "ineffective": "Ineffective",
}


def team(session: Session, engagement: Engagement) -> list[dict[str, Any]]:
    rows = session.execute(
        select(EngagementMember.account_id, EngagementMember.role, Account.display_name)
        .join(Account, Account.id == EngagementMember.account_id)
        .where(EngagementMember.engagement_id == engagement.id)
        .order_by(EngagementMember.role, Account.display_name)
    ).all()
    return [{"account_id": a, "role": r, "name": n} for a, r, n in rows]


def role_on(session: Session, principal: Principal, engagement: Engagement) -> str | None:
    if principal.account_id is None:
        return None
    return session.scalars(
        select(EngagementMember.role).where(
            EngagementMember.engagement_id == engagement.id,
            EngagementMember.account_id == principal.account_id,
        )
    ).first()


def may_see_work(session: Session, principal: Principal, engagement: Engagement) -> bool:
    if role_on(session, principal, engagement) is not None:
        return True
    return engagement.status == "reported" and universe.may_read(principal)


def _require_team(session: Session, principal: Principal, engagement: Engagement) -> str:
    role = role_on(session, principal, engagement)
    if role is None:
        raise PermissionDenied("Only the engagement's team works on it.")
    return role


def _auditors(session: Session, ids: list[int]) -> dict[int, Account]:
    found = {
        row.id: row
        for row in session.scalars(
            select(Account)
            .join(RoleGrant, RoleGrant.account_id == Account.id)
            .where(Account.id.in_(ids or [0]), RoleGrant.role == roles.AUDITOR)
        )
    }
    return found


def start(
    session: Session, principal: Principal, engagement: Engagement, values: Mapping[str, Any]
) -> None:
    """Begin a planned engagement: its lead, its team, and what it covers."""
    universe.require_work(principal)
    if engagement.status != "planned":
        raise Conflict("Only a planned engagement is started.")
    errors = records.Errors()
    try:
        lead = int(values.get("lead") or 0)
        members = [int(each) for each in values.get("members") or []]
    except (TypeError, ValueError):
        raise Invalid("The team was not understood.", {"members": "Give account ids."}) from None
    found = _auditors(session, [lead, *members])
    if lead not in found:
        errors.add("lead", "The lead must be an auditor.")
    for each in members:
        if each not in found:
            errors.add("members", "Everyone on the team must be an auditor.")
    if errors:
        raise Invalid("The engagement was not started.", errors)
    with audit.operation(session, "engagement.start"):
        session.add(EngagementMember(engagement_id=engagement.id, account_id=lead, role="lead"))
        for each in dict.fromkeys(members):
            if each != lead:
                session.add(
                    EngagementMember(engagement_id=engagement.id, account_id=each, role="member")
                )
        engagement.status = "planning"
        engagement.started_on = utc_now().date()
        engagement.scope_note = records.text(values.get("scope_note"))
        engagement.updated_at = utc_now()
        engagement.version += 1
        session.flush()


def add_step(
    session: Session, principal: Principal, engagement: Engagement, values: Mapping[str, Any]
) -> Workpaper:
    _require_team(session, principal, engagement)
    if engagement.status not in ("planning", "fieldwork"):
        raise Conflict("Steps are added while planning, or during fieldwork.")
    title = records.text(values.get("title"))
    if not title:
        raise Invalid("The step was not added.", {"title": "Say what the step is."})
    count = len(
        session.scalars(select(Workpaper.id).where(Workpaper.engagement_id == engagement.id)).all()
    )
    with audit.operation(session, "workpaper.add"):
        paper = Workpaper(
            engagement_id=engagement.id,
            sequence=count + 1,
            title=title[:200],
            procedure=records.text(values.get("procedure")),
            evidence=[],
        )
        session.add(paper)
        engagement.updated_at = utc_now()
        session.flush()
    return paper


def find_workpaper(
    session: Session, principal: Principal, paper_id: int
) -> tuple[Workpaper, Engagement]:
    paper = session.get(Workpaper, paper_id)
    engagement = session.get(Engagement, paper.engagement_id) if paper else None
    if paper is None or engagement is None or not may_see_work(session, principal, engagement):
        raise NotFound(f"There is no workpaper {paper_id}.")
    return paper, engagement


def record_work(
    session: Session,
    principal: Principal,
    paper: Workpaper,
    engagement: Engagement,
    values: Mapping[str, Any],
) -> None:
    """What was done, what was found, and the evidence. A change after sign-off undoes it."""
    _require_team(session, principal, engagement)
    if engagement.status not in ("fieldwork", "reporting"):
        raise Conflict("Work is recorded during fieldwork.")
    errors = records.Errors()
    done = records.text(values.get("done"))
    if not done:
        errors.add("done", "Say what was done.")
    refs = [str(each).strip().upper() for each in values.get("evidence") or []]
    known = set(session.scalars(select(Evidence.ref).where(Evidence.ref.in_(refs or [""]))))
    for ref in refs:
        if ref not in known:
            errors.add("evidence", f"{ref} is not an item of evidence.")
    if errors:
        raise Invalid("The work was not recorded.", errors)
    with audit.operation(session, "workpaper.work"):
        paper.done, paper.found = done, records.text(values.get("found"))
        paper.evidence = list(dict.fromkeys(refs))
        paper.prepared_by, paper.prepared_by_name = principal.account_id, principal.name
        paper.prepared_at = utc_now()
        paper.signed_off_by = paper.signed_off_by_name = paper.signed_off_at = None
        engagement.updated_at = utc_now()


def _open_notes(session: Session, paper: Workpaper) -> int:
    return len(
        session.scalars(
            select(ReviewNote.id).where(
                ReviewNote.workpaper_id == paper.id, ReviewNote.cleared_at.is_(None)
            )
        ).all()
    )


def add_note(
    session: Session, principal: Principal, paper: Workpaper, engagement: Engagement, text: Any
) -> None:
    _require_team(session, principal, engagement)
    if paper.prepared_by == principal.account_id:
        raise PermissionDenied("A workpaper is reviewed by someone other than its preparer.")
    words = records.text(text)
    if not words:
        raise Invalid("The note was not added.", {"note": "Say what needs looking at."})
    with audit.operation(session, "workpaper.note"):
        session.add(
            ReviewNote(
                engagement_id=engagement.id,
                workpaper_id=paper.id,
                note=words,
                by=principal.account_id,
                by_name=principal.name,
                at=utc_now(),
            )
        )
        paper.signed_off_by = paper.signed_off_by_name = paper.signed_off_at = None
        session.flush()


def find_note(
    session: Session, principal: Principal, note_id: int
) -> tuple[ReviewNote, Engagement]:
    note = session.get(ReviewNote, note_id)
    engagement = session.get(Engagement, note.engagement_id) if note else None
    if note is None or engagement is None or not may_see_work(session, principal, engagement):
        raise NotFound(f"There is no review note {note_id}.")
    return note, engagement


def answer_note(
    session: Session, principal: Principal, note: ReviewNote, engagement: Engagement, text: Any
) -> None:
    _require_team(session, principal, engagement)
    words = records.text(text)
    if not words:
        raise Invalid("The answer was not recorded.", {"answer": "Say what was done about it."})
    with audit.operation(session, "workpaper.answer"):
        note.answer = words


def clear_note(
    session: Session, principal: Principal, note: ReviewNote, engagement: Engagement
) -> None:
    _require_team(session, principal, engagement)
    if note.by != principal.account_id:
        raise PermissionDenied("A review note is cleared by the one who wrote it.")
    if not note.answer:
        raise Conflict("It has not been answered yet.")
    with audit.operation(session, "workpaper.clear"):
        note.cleared_at = utc_now()


def sign_off(
    session: Session, principal: Principal, paper: Workpaper, engagement: Engagement
) -> None:
    _require_team(session, principal, engagement)
    if paper.prepared_at is None:
        raise Conflict("Nothing has been recorded on it yet.")
    if paper.prepared_by == principal.account_id:
        raise PermissionDenied("A workpaper is signed off by someone other than its preparer.")
    if _open_notes(session, paper):
        raise Conflict("Every review note on it must be cleared first.")
    with audit.operation(session, "workpaper.sign_off"):
        paper.signed_off_by, paper.signed_off_by_name = principal.account_id, principal.name
        paper.signed_off_at = utc_now()


def advance(
    session: Session, principal: Principal, engagement: Engagement, values: Mapping[str, Any]
) -> None:
    """Move to the next stage: fieldwork once there is a program of work, reporting once every
    workpaper is signed off, and reported with a summary and an opinion."""
    if _require_team(session, principal, engagement) != "lead":
        raise PermissionDenied("The engagement's lead moves it on.")
    stage = NEXT.get(engagement.status)
    if stage is None:
        raise Conflict("It does not move on from here.")
    papers = session.scalars(
        select(Workpaper).where(Workpaper.engagement_id == engagement.id)
    ).all()
    errors = records.Errors()
    if stage == "fieldwork" and not papers:
        errors.add("steps", "Plan at least one step of the work first.")
    if stage == "reporting" and any(paper.signed_off_at is None for paper in papers):
        errors.add("steps", "Every workpaper must be signed off first.")
    summary = records.text(values.get("summary"))
    opinion = values.get("opinion")
    if stage == "reported":
        if not summary:
            errors.add("summary", "Say what the engagement found, for its report.")
        if opinion not in OPINIONS:
            errors.add("opinion", "Effective, needs improvement, or ineffective.")
    if errors:
        raise Invalid("It did not move on.", errors)
    today = utc_now().date()
    with audit.operation(session, f"engagement.{stage}"):
        engagement.status = stage
        if stage == "fieldwork":
            engagement.fieldwork_on = today
        elif stage == "reporting":
            engagement.reporting_on = today
        else:
            engagement.reported_on = today
            engagement.report_summary, engagement.opinion = summary, str(opinion)
        engagement.updated_at = utc_now()
        engagement.version += 1


def _paper_view(session: Session, principal: Principal, paper: Workpaper) -> dict[str, Any]:
    notes = session.scalars(
        select(ReviewNote).where(ReviewNote.workpaper_id == paper.id).order_by(ReviewNote.id)
    ).all()
    return {
        "id": paper.id,
        "sequence": paper.sequence,
        "title": paper.title,
        "procedure": paper.procedure,
        "done": paper.done,
        "found": paper.found,
        "evidence": paper.evidence,
        "prepared_by": paper.prepared_by_name,
        "prepared_at": paper.prepared_at,
        "signed_off_by": paper.signed_off_by_name,
        "signed_off_at": paper.signed_off_at,
        "notes": [
            {
                "id": n.id,
                "note": n.note,
                "by": n.by_name,
                "at": n.at,
                "answer": n.answer,
                "cleared_at": n.cleared_at,
                "mine": n.by == principal.account_id,
            }
            for n in notes
        ],
        "mine": paper.prepared_by == principal.account_id,
    }


def view(session: Session, principal: Principal, engagement: Engagement) -> dict[str, Any]:
    plan = session.get(AuditPlan, engagement.plan_id) if engagement.plan_id else None
    base = plans.engagement_view(session, engagement, plan=plan)
    role = role_on(session, principal, engagement)
    seen = may_see_work(session, principal, engagement)
    papers = session.scalars(
        select(Workpaper)
        .where(Workpaper.engagement_id == engagement.id)
        .order_by(Workpaper.sequence)
    ).all()
    return {
        **base,
        "plan": {"ref": plan.ref, "name": plan.name} if plan else None,
        "started_on": engagement.started_on,
        "fieldwork_on": engagement.fieldwork_on,
        "reporting_on": engagement.reporting_on,
        "team": team(session, engagement),
        "restricted": not seen,
        "scope_note": engagement.scope_note if seen else None,
        "workpapers": [_paper_view(session, principal, paper) for paper in papers] if seen else [],
        "progress": {
            "steps": len(papers),
            "prepared": sum(1 for p in papers if p.prepared_at),
            "signed_off": sum(1 for p in papers if p.signed_off_at),
        },
        "report": (
            {
                "summary": engagement.report_summary,
                "opinion": engagement.opinion,
                "opinion_label": OPINION_LABELS.get(engagement.opinion or ""),
            }
            if engagement.status == "reported"
            else None
        ),
        "opinions": OPINION_LABELS,
        "role": role,
        "can": {
            "start": engagement.status == "planned" and universe.may_work(principal),
            "work": role is not None
            and engagement.status in ("planning", "fieldwork", "reporting"),
            "advance": role == "lead" and engagement.status in NEXT,
        },
        "next": NEXT.get(engagement.status),
        "waiting": _waiting(engagement, papers),
    }


def _waiting(engagement: Engagement, papers: list[Workpaper]) -> str | None:
    """What stands between the engagement and its next stage, in words."""
    if engagement.status == "planning" and not papers:
        return "Plan at least one step of the work first."
    if engagement.status == "fieldwork":
        left = sum(1 for paper in papers if paper.signed_off_at is None)
        if left:
            return f"{left} workpaper{'s' if left != 1 else ''} still to be signed off."
    return None


def auditors(session: Session, principal: Principal) -> list[dict[str, Any]]:
    universe.require_read(principal)
    rows = session.execute(
        select(Account.id, Account.display_name)
        .join(RoleGrant, RoleGrant.account_id == Account.id)
        .where(RoleGrant.role == roles.AUDITOR, Account.status != "disabled")
        .order_by(Account.display_name)
    ).all()
    return [{"account_id": a, "name": n} for a, n in dict(rows).items()]
