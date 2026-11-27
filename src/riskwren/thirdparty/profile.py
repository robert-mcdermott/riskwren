"""What wave 5 adds to a third party's record: its tier, its services, and its tiering.

A third party is registered with the rest of the inventory (``inventory.registry``). This
gives it the hooks every record type may have, so that lists show and sort by its tier, a
list can be cut to one tier or to those not yet tiered, and its history tells each tiering.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import case
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.db.models import ThirdParty
from riskwren.inventory.completeness import Expected
from riskwren.inventory.registry import THIRD_PARTY
from riskwren.thirdparty import services, tiering

UNTIERED = "none"


def _cards(session: Session, rows: list[ThirdParty]) -> list[dict[str, Any]]:
    return [{"tier": row.tier} for row in rows]


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
    }


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    tier = filters.get("tier")
    if tier == UNTIERED:
        return [ThirdParty.tier.is_(None)]
    if tier:
        return [ThirdParty.tier == str(tier)]
    return []


def _tier_order(session: Session, model: Any) -> Any:
    # Tier 1 first when sorted ascending: the most at stake leads.
    return case({key: rank for rank, key in enumerate(tiering.order(session))}, value=model.tier)


def _history_title(event: Any, lookups: Any) -> str | None:
    context = event.context or {}
    if context.get("op") != "third_party.tier":
        return None
    if event.subject_type == "tier_assessment" and event.action == "created":
        tier, suggested = context.get("tier"), context.get("suggested")
        if tier == suggested:
            return f"Tiered it: {tier}, as the rules give"
        why = context.get("rationale")
        return f"Tiered it: {tier}, where the rules give {suggested}" + (f". {why}" if why else "")
    return "Tiered it"  # the copy onto the third party, already told


THIRD_PARTY.extra.update(
    {
        "cards": _cards,
        "detail": _detail,
        "conditions": _conditions,
        "sort_columns": {"tier": _tier_order},
        "history_title": _history_title,
        "history_labels": {"tier": "Tier"},
        "history_quiet": ("tier",),
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
