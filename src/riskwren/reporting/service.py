"""What each person owes, the heat map, and the risk dashboard.

Every figure here is a count of records the viewer may see, taken with the same conditions
the lists use, so that a figure and the list it opens always agree.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from riskwren.access import roles
from riskwren.access.principal import Principal
from riskwren.controls import service as controls
from riskwren.controls.service import CONTROL
from riskwren.core import scoring
from riskwren.core.clock import utc_now
from riskwren.db.models import (
    Acceptance,
    Account,
    Action,
    Control,
    Handover,
    OrgUnit,
    RecordOwner,
    Risk,
    TreatmentPlan,
)
from riskwren.db.models.risk import ASSESSMENT_KINDS, STANDINGS
from riskwren.inventory import access, records
from riskwren.inventory.registry import TYPES, RecordType
from riskwren.program import vocab
from riskwren.risk import categories
from riskwren.risk import method as methods
from riskwren.risk.register import RISK
from riskwren.treatment import service as treatment

SOON = 30  # days ahead that something due is worth showing
OPEN = {"status": "open"}


def count(
    session: Session, principal: Principal, record_type: RecordType, filters: Mapping[str, Any]
) -> int:
    """How many records of a type the person may see that match, exactly as a list would."""
    model: Any = record_type.model
    conditions = records.conditions_for(session, principal, record_type, filters)
    return session.execute(select(func.count()).select_from(model).where(*conditions)).scalar_one()


def _scope(unit: int | None, category: str | None = None) -> dict[str, Any]:
    scope: dict[str, Any] = {}
    if unit:
        scope["unit"] = unit
    if category:
        scope["category"] = category
    return scope


# --- The heat map -------------------------------------------------------------------------


def heat_map(
    session: Session,
    principal: Principal,
    *,
    kind: str = "residual",
    unit: int | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    """Open risks counted by likelihood and impact. ``cells[impact - 1][likelihood - 1]``."""
    if kind not in ASSESSMENT_KINDS:
        kind = "residual"
    method = methods.current(session)
    scope = {**OPEN, **_scope(unit, category)}
    conditions = records.conditions_for(session, principal, RISK, scope)
    likelihood, impact = getattr(Risk, f"{kind}_likelihood"), getattr(Risk, f"{kind}_impact")
    rows = session.execute(
        select(likelihood, impact, func.count()).where(*conditions).group_by(likelihood, impact)
    ).all()
    wide, tall = len(method["likelihood"]), len(method["impact_levels"])
    cells = [[0] * wide for _ in range(tall)]
    unrated = 0
    for across, up, number in rows:
        if across and up and across <= wide and up <= tall:
            cells[up - 1][across - 1] = number
        else:
            unrated += number
    appetite = None
    if category:
        tree = categories.Tree(session)
        appetite = tree.appetite(categories.by_key(session, category).id)
    by_rating = dict.fromkeys(scoring.rating_keys(method), 0)
    for up, row in enumerate(cells, 1):
        for across, number in enumerate(row, 1):
            by_rating[scoring.rating(method, across, up)] += number
    return {
        "kind": kind,
        "cells": cells,
        "rated": sum(map(sum, cells)),
        "unrated": unrated,
        "by_rating": by_rating,
        "appetite": appetite,
    }


# --- The dashboard ------------------------------------------------------------------------


def dashboard(session: Session, principal: Principal, *, unit: int | None = None) -> dict[str, Any]:
    """Where the register stands, for everything the person may see or for one unit and
    those beneath it. Each figure is paired with the filters of the list that produces it."""
    method = methods.current(session)
    scope = _scope(unit)

    def risks(**filters: Any) -> dict[str, Any]:
        asked = {**OPEN, **scope, **filters}
        return {"count": count(session, principal, RISK, asked), "filters": asked}

    def control_count(**filters: Any) -> dict[str, Any]:
        asked = {"status": "active", **scope, **filters}
        return {"count": count(session, principal, CONTROL, asked), "filters": asked}

    def indicator_count(**filters: Any) -> dict[str, Any]:
        from riskwren.risk.indicators import INDICATOR

        asked = {"status": "active", **scope, **filters}
        return {"count": count(session, principal, INDICATOR, asked), "filters": asked}

    def actions(**filters: Any) -> dict[str, Any]:
        asked = {"status": "open", **scope, **filters}
        return {
            "count": treatment.search_actions(session, principal, asked, limit=1)[1],
            "filters": asked,
        }

    tree = categories.Tree(session)
    by_category = []
    for top in (row for row in tree.rows if row.parent_id is None and row.status == "active"):
        figure = risks(category=top.key)
        if figure["count"]:
            by_category.append(
                {
                    "key": top.key,
                    "name": top.name,
                    "appetite": top.appetite,
                    **figure,
                    "above": risks(category=top.key, above_appetite=True)["count"],
                }
            )
    children = session.scalars(
        select(OrgUnit)
        .where(OrgUnit.parent_id == unit if unit else OrgUnit.parent_id.is_(None))
        .order_by(OrgUnit.name)
    ).all()
    if not unit and len(children) == 1:  # one root: show what is beneath it
        children = session.scalars(
            select(OrgUnit).where(OrgUnit.parent_id == children[0].id).order_by(OrgUnit.name)
        ).all()
    by_unit = []
    for child in children:
        asked = {**OPEN, "unit": child.id}
        number = count(session, principal, RISK, asked)
        if number:
            above = count(session, principal, RISK, {**asked, "above_appetite": True})
            by_unit.append(
                {
                    "unit_id": child.id,
                    "name": child.name,
                    "count": number,
                    "filters": asked,
                    "above": above,
                }
            )
    top, _ = records.search(
        session, principal, RISK, {**OPEN, **scope}, sort="-residual_rating", limit=8
    )
    top = [risk for risk in top if risk.residual_rating]
    return {
        "unit": unit,
        "totals": {
            "open": risks(),
            "above_appetite": risks(above_appetite=True),
            "needs_decision": risks(standing="needs_decision"),
            "review_overdue": risks(overdue=True),
            "in_doubt": risks(in_doubt=True),
            "not_assessed": risks(standing="not_assessed"),
            "actions_open": actions(),
            "actions_overdue": actions(overdue=True),
        },
        "by_standing": [
            {"key": key, **risks(standing=key)} for key in STANDINGS if key != "closed"
        ],
        "by_rating": [
            {"key": rating["key"], "label": rating["label"], **risks(residual_rating=rating["key"])}
            for rating in reversed(method["ratings"])
        ],
        "by_category": by_category,
        "by_unit": by_unit,
        "controls": {
            "total": control_count(),
            "by_state": [
                {"key": state, **control_count(state=state)}
                for state in ("effective", "partly", "ineffective", "not_assessed")
            ],
            "stale": control_count(stale=True),
        },
        # Early warning: where the indicators stand. Each count opens its list.
        "indicators": [
            {"key": state, **indicator_count(state=state)}
            for state in ("breach", "warn", "ok", "no_reading")
        ],
        "top_risks": records.cards(session, RISK, top),
        "heat_map": heat_map(session, principal, unit=unit),
    }


# --- What I owe ---------------------------------------------------------------------------


def _owned(session: Session, record_type: RecordType, account_id: int) -> Any:
    return select(RecordOwner.record_id).where(
        RecordOwner.record_type == record_type.key,
        RecordOwner.account_id == account_id,
        RecordOwner.kind.in_(access.EDITING_KINDS),
    )


def _orphans(
    session: Session, record_type: RecordType, covered: frozenset[int] | None
) -> list[Any]:
    """Records in these units that nobody who can sign in answers for."""
    model: Any = record_type.model
    answered = (
        select(RecordOwner.record_id)
        .join(Account, Account.id == RecordOwner.account_id)
        .where(
            RecordOwner.record_type == record_type.key,
            RecordOwner.kind == records.OWNER,
            Account.status != "disabled",
        )
    )
    conditions = [model.id.not_in(answered)]
    if hasattr(model, "status"):
        conditions.append(model.status.not_in(("retired", "closed")))
    if covered is not None:
        conditions.append(model.org_unit_id.in_(covered))
    return list(session.scalars(select(model).where(*conditions).order_by(model.name).limit(25)))


def home(session: Session, principal: Principal) -> dict[str, Any]:
    """One list of what the person owes, overdue first."""
    today = utc_now().date()
    soon = today + timedelta(days=SOON)
    me = principal.account_id
    items: list[dict[str, Any]] = []

    def add(kind: str, title: str, detail: str, href: str, due: date | None, **more: Any) -> None:
        items.append(
            {
                "kind": kind,
                "title": title,
                "detail": detail,
                "href": href,
                "due_on": due,
                "overdue": bool(due and due < today),
                **more,
            }
        )

    if me is not None:
        mine = session.scalars(
            select(Risk).where(Risk.id.in_(_owned(session, RISK, me)), Risk.status == "open")
        ).all()
        for risk in mine:
            link = f"/risks/{risk.ref}"
            if risk.residual_in_doubt:
                add(
                    "assess",
                    f"Assess {risk.name} again",
                    risk.residual_doubt_reason or "",
                    link,
                    today,
                    ref=risk.ref,
                )
            elif not risk.residual_rating:
                add(
                    "assess",
                    f"Assess {risk.name}",
                    "It has no residual rating yet.",
                    link,
                    risk.next_review_on,
                    ref=risk.ref,
                )
            elif risk.next_review_on and risk.next_review_on <= soon:
                add(
                    "review",
                    f"Review {risk.name}",
                    "Its review is due.",
                    link,
                    risk.next_review_on,
                    ref=risk.ref,
                )
            if risk.standing == "needs_decision":
                add(
                    "decide", f"{risk.name} needs a decision",
                    "It is above appetite, with no plan on time and no acceptance in force.",
                    f"{link}?tab=treatment", None, ref=risk.ref,
                )  # fmt: skip
        for action in session.scalars(
            select(Action)
            .where(Action.owner_id == me, Action.status.in_(treatment.OPEN))
            .order_by(Action.due_on)
        ):
            plan = (
                session.get(TreatmentPlan, action.source_id)
                if action.source_type == treatment.PLAN
                else None
            )
            risk = session.get(Risk, plan.risk_id) if plan is not None else None
            source = treatment.SOURCES.get(action.source_type)
            about = source.describe(session, principal, action.source_id) if source else None
            if risk is not None:
                detail, href = f"{action.ref} · for {risk.name}", f"/risks/{risk.ref}?tab=treatment"
            elif about is not None:
                detail = f"{action.ref} · for {about['ref']} {about['name']}"
                href = f"/issues/{about['ref']}"
            else:
                detail, href = action.ref, "/actions?mine=true"
            add("action", action.title, detail, href, action.due_on, ref=action.ref)
        for control in session.scalars(
            select(Control).where(
                Control.id.in_(_owned(session, CONTROL, me)), Control.status == "active"
            )
        ):
            state = controls.state_of(session, control, today=today)
            if state in ("not_assessed", "stale"):
                why = (
                    "Nobody has rated it yet."
                    if state == "not_assessed"
                    else "Its rating is out of date."
                )
                add(
                    "rate",
                    f"Rate {control.name}",
                    why,
                    f"/controls/{control.ref}",
                    None,
                    ref=control.ref,
                )
        for acceptance, risk in session.execute(
            select(Acceptance, Risk)
            .join(Risk, Risk.id == Acceptance.risk_id)
            .where(
                Acceptance.accepted_by == me,
                Acceptance.withdrawn_at.is_(None),
                Acceptance.expires_on >= today,
                Acceptance.expires_on <= today + timedelta(days=60),
            )
        ):
            add(
                "acceptance", f"Your acceptance of {risk.name} is about to expire",
                "Renew it, or the risk will need a decision again.",
                f"/risks/{risk.ref}?tab=treatment", acceptance.expires_on, ref=risk.ref,
            )  # fmt: skip

    # Evidence of one's own that has stopped counting, or is about to.
    from riskwren.compliance import evidence  # it builds on the controls this module reads

    for held in evidence.due(session, principal):
        stale = held.valid_until < today
        add(
            "evidence", f"Renew {held.name}",
            "It no longer counts. Collect it again." if stale
            else "It stops counting soon. Collect it again.",
            f"/evidence/{held.ref}", held.valid_until, ref=held.ref,
        )  # fmt: skip

    # Indicators of theirs whose next reading is due.
    from riskwren.risk import indicators

    for indicator in indicators.due(session, principal):
        add(
            "reading", f"Record a reading of {indicator.name}",
            f"{indicator.ref} · read {indicator.frequency}",
            f"/indicators/{indicator.ref}", indicators.next_due(indicator), ref=indicator.ref,
        )  # fmt: skip

    # What campaigns have asked of them: an attestation, a look at a risk, a check of a unit.
    from riskwren.oversight import campaigns

    for item, campaign in campaigns.waiting_on(session, principal):
        about = f"{item.subject_ref or ''} {item.subject_name}".strip()
        verb = {
            "attestation": "Attest", "self_assessment": "Look again at",
            "completeness": "Check the records of", "profile": "Describe the security of",
            "evidence": "Provide evidence for", "acknowledgment": "Read and acknowledge",
        }[campaign.kind]  # fmt: skip
        href = (
            f"/library/{item.subject_ref}" if campaign.kind == "acknowledgment"
            else f"/campaign-items/{item.id}"
        )  # fmt: skip
        add("campaign", f"{verb} {about}", f"{campaign.ref} · {campaign.name}", href,
            campaign.due_on, ref=campaign.ref)  # fmt: skip

    # An analysis the person leads that still has questions without an answer.
    from riskwren.risk.analysis import ANALYSIS

    led, _ = records.search(
        session, principal, ANALYSIS, {"mine": True, "status": "open"}, limit=20
    )
    for found, card in zip(led, records.cards(session, ANALYSIS, led), strict=True):
        if card["pending"]:
            left = card["pending"]
            add(
                "analysis", f"Carry on with {found.name}",
                f"{left} of {card['items']} questions have no answer yet."
                if left != 1 else f"1 of {card['items']} questions has no answer yet.",
                f"/risk-analyses/{found.ref}", None, ref=found.ref,
            )  # fmt: skip

    # Documents: drafts waiting for this person's approval, approved ones waiting to be
    # published, ones sent back, and reviews coming due.
    from riskwren.policy import documents as policy_documents

    for document, version in policy_documents.awaiting(session, principal):
        add(
            "approve", f"Approve the new version of {document.name}",
            f"{document.ref} · sent by {version.submitted_by_name}",
            f"/documents/{document.ref}?tab=draft", None, ref=document.ref,
        )  # fmt: skip
    from riskwren.policy import library as policy_library

    asked = policy_library.asked_by_campaign(session, principal)
    for document in policy_library.outstanding(session, principal):
        if document.id in asked:
            continue  # the campaign that asks for it is on the list already
        add(
            "acknowledge", f"Read and acknowledge {document.name}",
            f"{document.ref} · {policy_documents.KIND_LABELS[document.kind].lower()}",
            f"/library/{document.ref}", None, ref=document.ref,
        )  # fmt: skip
    soon = date.fromordinal(today.toordinal() + policy_documents.SOON)
    for document in policy_documents.owned(session, principal):
        working = policy_documents.open_version(session, document)
        if working is not None and working.status == "approved":
            add(
                "publish", f"Publish the new version of {document.name}",
                f"{document.ref} · everyone named has approved it",
                f"/documents/{document.ref}?tab=draft", None, ref=document.ref,
            )  # fmt: skip
        elif working is not None and working.status == "draft" and working.review_round:
            add(
                "rework", f"Rework the draft of {document.name}",
                f"{document.ref} · it was returned with a reason",
                f"/documents/{document.ref}?tab=draft", None, ref=document.ref,
            )  # fmt: skip
        if document.next_review_on is not None and document.next_review_on <= soon:
            add(
                "document_review", f"Review {document.name}",
                f"{document.ref} · keep it as it is, or start a new version",
                f"/documents/{document.ref}", document.next_review_on, ref=document.ref,
            )  # fmt: skip

    # Tests a person has been asked to do, and results that wait for their review.
    from riskwren.compliance import assessments

    for owed in assessments.waiting_on(session, principal):
        assessment, control = owed["assessment"], owed["control"]
        if owed["kind"] == "test":
            add(
                "test", f"Test {control.name}", f"{assessment.ref} · {assessment.name}",
                f"/assessments/{assessment.ref}", assessment.period_end, ref=assessment.ref,
            )  # fmt: skip
        else:
            add(
                "confirm", f"Review the result for {control.name}",
                f"{assessment.ref} · it counts once a second person has confirmed it",
                f"/assessments/{assessment.ref}", None, ref=assessment.ref,
            )  # fmt: skip

    # Issues a person owns, closures that wait for them, and exceptions to decide or renew.
    from riskwren.compliance import exceptions, issues

    severities = vocab.labels(session, "issue_severities")
    for owed in issues.waiting_on(session, principal):
        issue = owed["issue"]
        if owed["kind"] == "issue":
            add(
                "issue", f"Put right: {issue.name}",
                f"{issue.ref} · {severities.get(issue.severity, issue.severity)}",
                f"/issues/{issue.ref}", issue.due_on, ref=issue.ref,
            )  # fmt: skip
        else:
            add(
                "closure", f"Confirm that {issue.ref} is put right",
                f"{issue.name} · {issue.proposed_by_name} says it is",
                f"/issues/{issue.ref}", None, ref=issue.ref,
            )  # fmt: skip
    for owed in exceptions.waiting_on(session, principal):
        item = owed["exception"]
        if owed["kind"] == "decide":
            add(
                "exception", f"Decide an exception: {item.name}",
                f"{item.ref} · asked for by {item.requested_by_name}",
                f"/exceptions/{item.ref}", None, ref=item.ref,
            )  # fmt: skip
        else:
            add(
                "exception", f"An exception of yours is about to end: {item.name}",
                f"{item.ref} · ask again if it is still needed",
                f"/exceptions/{item.ref}", item.expires_on, ref=item.ref,
            )  # fmt: skip

    # A leader is shown what waits on someone with their authority.
    led = principal.units_for(roles.LEADER)
    if led:
        waiting = session.scalars(
            select(Risk)
            .where(
                Risk.org_unit_id.in_(led), Risk.standing == "needs_decision", Risk.status == "open"
            )
            .order_by(Risk.name)
            .limit(25)
        ).all()
        for risk in waiting:
            if any(item.get("ref") == risk.ref and item["kind"] == "decide" for item in items):
                continue
            may = treatment.authority(session, principal, risk)
            add(
                "decide", f"{risk.name} needs a decision",
                "You may accept it." if may["allowed"] else "It is above appetite in your unit.",
                f"/risks/{risk.ref}?tab=treatment", None, ref=risk.ref,
            )  # fmt: skip
    # A steward is shown what nobody answers for.
    kept = principal.units_for(roles.STEWARD, roles.MANAGER)
    if kept is None or kept:
        for record_type in TYPES.values():
            for record in _orphans(session, record_type, kept):
                add(
                    "orphan", f"Name an owner for {record.name}",
                    f"{record.ref} has nobody answering for it.",
                    f"/{record_type.path}/{record.ref}", None, ref=record.ref,
                )  # fmt: skip

    # Whoever is standing in for someone who has left is asked to name who takes it for good.
    standing_in = session.execute(
        select(Handover.from_account_id, func.count())
        .where(Handover.held_by == principal.account_id)
        .group_by(Handover.from_account_id)
    ).all()
    for account_id, number in standing_in:
        gone = session.get(Account, account_id)
        things = "1 thing" if number == 1 else f"{number} things"
        add(
            "handover", f"Name who takes what {gone.display_name if gone else 'someone'} held",
            f"You answer for {things} of theirs until someone is named.",
            f"/handover/{account_id}", None,
        )  # fmt: skip

    items.sort(key=lambda item: (not item["overdue"], item["due_on"] or date.max, item["title"]))
    summary = None
    covered = principal.units_for(*access.TRUSTED)
    if principal.reads_all or covered is None or covered:
        figures = dashboard(session, principal)["totals"]
        summary = {
            name: figures[name]
            for name in ("above_appetite", "needs_decision", "review_overdue", "actions_overdue")
        }
        # And where compliance stands: what a test has found wanting, and what is late.
        failing = {"status": "active", "tested": "failing"}
        late = {"status": "live", "overdue": True}
        summary["controls_failing"] = {
            "count": count(session, principal, CONTROL, failing), "filters": failing,
        }  # fmt: skip
        summary["issues_overdue"] = {
            "count": count(session, principal, issues.ISSUE, late), "filters": {"overdue": True},
        }  # fmt: skip
    return {"items": items, "overdue": sum(item["overdue"] for item in items), "summary": summary}
