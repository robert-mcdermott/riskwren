"""What wave 5 adds to a third party's record: its tier, its services, and its tiering.

A third party is registered with the rest of the inventory (``inventory.registry``). This
gives it the hooks every record type may have, so that lists show and sort by its tier, a
list can be cut to one tier or to those not yet tiered, and its history tells each tiering.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from sqlalchemy import case
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.db.models import ThirdParty
from riskwren.inventory.completeness import Expected
from riskwren.inventory.registry import THIRD_PARTY
from riskwren.thirdparty import contacts, coverage, lifecycle, reviews, services, tiering

UNTIERED = "none"


def _cards(session: Session, rows: list[ThirdParty]) -> list[dict[str, Any]]:
    return [{"tier": row.tier, "next_review_on": row.next_review_on} for row in rows]


def _detail(session: Session, principal: Principal, third_party: ThirdParty) -> dict[str, Any]:
    latest = tiering.current(session, third_party)
    names = tiering.labels(session)
    return {
        "services": services.of(session, principal, third_party),
        "tiering": None
        if latest is None
        else {
            "tier": latest.tier,
            "tier_label": names.get(latest.tier, latest.tier),
            "suggested": latest.suggested,
            "suggested_label": names.get(latest.suggested, latest.suggested),
            "reasons": latest.reasons,
            "rationale": latest.rationale,
            "by": latest.assessed_by_name,
            "at": latest.assessed_at,
        },
        "can_tier": tiering.may_tier(session, principal, third_party),
        # Its contacts' addresses are for those who keep it, assessors, and those who read
        # everything; anyone else sees none.
        "contacts": [reviews.contact_view(row) for row in contacts.of(session, third_party)]
        if contacts.may_read(session, principal, third_party)
        else None,
        "reviews": reviews.of(session, principal, third_party),
        "agreements": coverage.agreements_with(session, principal, third_party),
        "next_review_on": third_party.next_review_on,
        "review_called": third_party.review_called,
        "offboarding": lifecycle.offboarding_view(
            lifecycle.current_offboarding(session, third_party)
        ),
    }


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    tier = filters.get("tier")
    if tier == UNTIERED:
        found.append(ThirdParty.tier.is_(None))
    elif tier:
        found.append(ThirdParty.tier == str(tier))
    review = filters.get("review")
    if review in ("due", "soon"):
        today = utc_now().date()
        horizon = today if review == "due" else today + timedelta(days=lifecycle.SOON)
        found += [ThirdParty.status == "active", ThirdParty.next_review_on <= horizon]
    return found


def _tier_order(session: Session, model: Any) -> Any:
    # Tier 1 first when sorted ascending: the most at stake leads.
    return case({key: rank for rank, key in enumerate(tiering.order(session))}, value=model.tier)


def _history_title(event: Any, lookups: Any) -> str | None:
    context = event.context or {}
    op = context.get("op")
    mine = event.subject_type == "third_party"
    if op == "third_party.call_review" and mine:
        return f"Called for a review: {context.get('why')}"
    if event.subject_type == "offboarding":
        if op == "third_party.offboard":
            return f"Started offboarding: {context.get('reason')}"
        if op == "third_party.offboard_step":
            return f"Recorded: {context.get('step')}. {context.get('note')}"
        if op == "third_party.offboard_cancel":
            return "Stopped offboarding" + (f": {context['note']}" if context.get("note") else "")
    if event.subject_type == "third_party_contact" and op == "third_party.contact":
        verb = "Added a contact" if event.action == "created" else "Changed a contact"
        return f"{verb}: {context.get('who')}"
    if op == "third_party.tier" and event.subject_type == "tier_assessment":
        tier, suggested = context.get("tier"), context.get("suggested")
        if tier == suggested:
            return f"Tiered it: {tier}, as the rules give"
        why = context.get("rationale")
        return f"Tiered it: {tier}, where the rules give {suggested}" + (f". {why}" if why else "")
    return None


THIRD_PARTY.extra.update(
    {
        "cards": _cards,
        "detail": _detail,
        "conditions": _conditions,
        "sort_columns": {"tier": _tier_order},
        "history_title": _history_title,
        # A call for a review changes only what the history keeps quiet; it is told by title.
        "history_keeps_titled": True,
        "history_labels": {"tier": "Tier"},
        "history_quiet": ("tier", "next_review_on", "review_called"),
        "expected": [
            Expected(
                "tier",
                "a tier",
                lambda model: model.tier.is_(None),
                "How much is at stake with it, and so how closely it is reviewed, is unknown.",
            )
        ],
    }
)
