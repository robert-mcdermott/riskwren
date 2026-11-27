"""Tiering: how much is at stake with a third party, by the program's own rules (TPR-02).

A tiering asks a few questions about what a third party holds, how it reaches the
organization, and what relies on it. Where the inventory already knows the answer (the most
sensitive information it holds or handles, the most critical work that relies on it, the
systems its services reach) the answer is suggested from it, and the person confirms it.

The program's tiers are read in order. The first tier with a rule that holds for the answers
is the one the rules give, and every rule of that tier that holds is a reason shown for it.
Like every rating here, the tier recorded is a judgment by a named person (ADR-0011): one
who records a different tier from the rules' says why, and both are kept.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core import conditions
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    Information,
    Process,
    RecordLink,
    Service,
    System,
    ThirdParty,
    TierAssessment,
)
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.registry import THIRD_PARTY
from riskwren.oversight import questionnaires
from riskwren.program import rules, vocab

NOTHING_HOLDS = "None of the rules of a higher tier holds."
LONGEST_RATIONALE = 2000
# What the inventory's kinds of information say about whether it is regulated.
REGULATED_KINDS = {
    "patient_records": "health",
    "participant_data": "participant",
    "controlled_data": "controlled",
}


# --- The program's tiers ------------------------------------------------------------------


def table(session: Session) -> dict[str, Any]:
    return rules.get(session, "tiering")


def tiers(session: Session) -> list[dict[str, Any]]:
    return list(table(session).get("tiers") or [])


def labels(session: Session) -> dict[str, str]:
    return {tier["key"]: tier["label"] for tier in tiers(session)}


def order(session: Session) -> list[str]:
    """The tiers' keys, the one with most at stake first."""
    return [tier["key"] for tier in tiers(session)]


def problems(value: Any) -> list[str]:
    """What is wrong with a tiering table, before it is saved or loaded from a pack."""
    if not isinstance(value, Mapping) or not isinstance(value.get("tiers"), list):
        return ["The tiering needs a list of tiers."]
    found: list[str] = []
    listed = value["tiers"]
    if len(listed) < 2:
        found.append("Have at least two tiers.")
    keys: set[str] = set()
    for index, tier in enumerate(listed):
        where = f"Tier {index + 1}"
        if not isinstance(tier, Mapping):
            found.append(f"{where}: must be an object.")
            continue
        key = tier.get("key")
        if not isinstance(key, str) or not vocab.KEY.fullmatch(key) or key in keys:
            found.append(f"{where}: needs a key of its own.")
        else:
            keys.add(key)
        if not str(tier.get("label") or "").strip():
            found.append(f"{where}: needs a name.")
        months = tier.get("review_months")
        if months is not None and (not isinstance(months, int) or not 1 <= months <= 120):
            found.append(f"{where}: reviewed every 1 to 120 months, or only when called for.")
        given = tier.get("rules")
        if not isinstance(given, list):
            found.append(f"{where}: needs a list of rules, which may be empty for the last.")
            continue
        if index == len(listed) - 1 and given:
            found.append("The last tier has no rules: it is what holds when nothing else does.")
        if index < len(listed) - 1 and not given:
            found.append(f"{where}: needs at least one rule.")
        for rule in given:
            if not isinstance(rule, Mapping) or not str(rule.get("reason") or "").strip():
                found.append(f"{where}: each rule says why, in words.")
            elif not isinstance(rule.get("when"), Mapping) or not rule["when"]:
                found.append(f"{where}: each rule has a condition.")
    return found


def evaluate(listed: list[dict[str, Any]], answers: Mapping[str, Any],
             facts: Mapping[str, Any]) -> tuple[str, list[str]]:  # fmt: skip
    """The tier the rules give, and every rule of it that holds, in its own words."""
    context = {"answers": dict(answers), "facts": dict(facts)}
    for tier in listed[:-1]:
        held = [
            str(rule["reason"])
            for rule in tier.get("rules") or []
            if rule.get("when") and conditions.evaluate(rule["when"], context)
        ]
        if held:
            return tier["key"], held
    return listed[-1]["key"], [NOTHING_HOLDS]


# --- What the inventory says ----------------------------------------------------------------


def _services(session: Session, third_party: ThirdParty) -> list[Service]:
    return list(
        session.scalars(
            select(Service).where(
                Service.third_party_id == third_party.id, Service.status == "active"
            )
        )
    )


def _linked(session: Session, model: Any, where: Any) -> list[Any]:
    ids = select(RecordLink).where(where)
    rows = session.scalars(ids).all()
    wanted = set()
    for row in rows:
        wanted.add(row.from_id if row.from_type == model.__subject__ else row.to_id)
    if not wanted:
        return []
    return list(
        session.scalars(
            select(model).where(model.id.in_(wanted), model.status == "active").order_by(model.ref)
        )
    )


def gather(session: Session, third_party: ThirdParty) -> dict[str, Any]:
    """What the inventory knows that bears on the tier: every record as itself, before
    anyone asks who may see it."""
    services = _services(session, third_party)
    service_ids = [row.id for row in services] or [0]
    providers = or_(
        and_(RecordLink.to_type == "third_party", RecordLink.to_id == third_party.id),
        and_(RecordLink.to_type == "service", RecordLink.to_id.in_(service_ids)),
    )
    information = _linked(session, Information, or_(
        and_(RecordLink.from_type == "information", RecordLink.relation == "shared_with",
             RecordLink.to_type == "third_party", RecordLink.to_id == third_party.id),
        and_(RecordLink.from_type == "service", RecordLink.from_id.in_(service_ids),
             RecordLink.relation == "handles", RecordLink.to_type == "information"),
    ))  # fmt: skip
    # The systems it supplies are reached by it and rely on it; those it reaches alone do not
    # make it something the work depends on.
    supplied = _linked(session, System, and_(
        RecordLink.from_type == "system", RecordLink.relation == "supplied_by", providers,
    ))  # fmt: skip
    reached = _linked(session, System, and_(
        RecordLink.from_type == "service", RecordLink.from_id.in_(service_ids),
        RecordLink.relation == "reaches", RecordLink.to_type == "system",
    ))  # fmt: skip
    systems = sorted({row.id: row for row in [*supplied, *reached]}.values(), key=lambda r: r.ref)
    processes = _linked(session, Process, and_(
        RecordLink.from_type == "process", RecordLink.relation.in_(("performed_by", "relies_on")),
        providers,
    ))  # fmt: skip
    return {
        "third_party": third_party, "services": services, "information": information,
        "systems": systems, "supplied": supplied, "processes": processes,
    }  # fmt: skip


def _highest(session: Session, name: str, rows: list[Any], column: str) -> tuple[str | None, list]:
    """The highest value of an ordered vocabulary among the records, and those that have it."""
    best, rank, holders = None, -1, []
    for row in rows:
        value = getattr(row, column)
        place = vocab.rank(session, name, value)
        if place > rank:
            best, rank, holders = value, place, [row]
        elif place == rank and place >= 0:
            holders.append(row)
    return best, holders


def facts(session: Session, third_party: ThirdParty) -> dict[str, Any]:
    """What the inventory says, as plain data the rules can read and a tiering keeps."""
    found = gather(session, third_party)
    data_class, data_from = _highest(
        session, "data_classes", [third_party, *found["services"], *found["information"]],
        "data_class",
    )  # fmt: skip
    criticality, critical_from = _highest(
        session, "criticalities", [third_party, *found["processes"], *found["supplied"]],
        "criticality",
    )  # fmt: skip
    return {
        "data_class": data_class,
        "data_class_from": [row.ref for row in data_from],
        "information_kinds": sorted({row.kind for row in found["information"]}),
        "information": [row.ref for row in found["information"]],
        "criticality": criticality,
        "criticality_from": [row.ref for row in critical_from],
        "systems": [row.ref for row in found["systems"]],
        "services": [row.ref for row in found["services"]],
    }


def suggest(known: Mapping[str, Any]) -> dict[str, Any]:
    """The answers the inventory suggests. A question it cannot answer is left for the person."""
    out: dict[str, Any] = {}
    if known.get("data_class"):
        out["information"] = known["data_class"]
    kinds = known.get("information_kinds", [])
    regulated = sorted({REGULATED_KINDS[kind] for kind in kinds if kind in REGULATED_KINDS})
    if regulated and out.get("information") in ("internal", "confidential", "restricted"):
        out["regulated"] = regulated
    if known.get("systems"):
        out["access"] = ["integration"]
    dependency = {"critical": "stops", "high": "slows", "moderate": "slows", "low": "little"}
    if known.get("criticality") in dependency:
        out["dependency"] = dependency[known["criticality"]]
    return out


# --- Tiering --------------------------------------------------------------------------------


def current(session: Session, third_party: ThirdParty) -> TierAssessment | None:
    return session.scalars(
        select(TierAssessment)
        .where(
            TierAssessment.third_party_id == third_party.id,
            TierAssessment.superseded_by.is_(None),
        )
        .order_by(TierAssessment.id.desc())
    ).first()


def _questionnaire(session: Session) -> Any:
    key = table(session).get("questionnaire")
    try:
        row = questionnaires.find(session, str(key))
    except NotFound as missing:
        raise Conflict(
            "The questionnaire tiering asks is missing. Load the program again."
        ) from missing
    return row


def may_tier(session: Session, principal: Principal, third_party: ThirdParty) -> bool:
    """Those who keep the third party, and assessors whose scope covers its unit: tiering is
    an assessment, and often the security team's."""
    if third_party.status != "active":
        return False
    return principal.assesses_unit(third_party.org_unit_id) or access.can_edit(
        session, principal, THIRD_PARTY, third_party
    )


def _assessment_view(session: Session, row: TierAssessment, names: dict[str, str],
                     document: Any) -> dict[str, Any]:  # fmt: skip
    return {
        "id": row.id,
        "tier": row.tier,
        "tier_label": names.get(row.tier, row.tier),
        "suggested": row.suggested,
        "suggested_label": names.get(row.suggested, row.suggested),
        "reasons": row.reasons,
        "rationale": row.rationale,
        "by": row.assessed_by_name,
        "at": row.assessed_at,
        "current": row.superseded_by is None,
        "answers": row.answers,
        "as_asked": questionnaires.as_asked(document, row.answers) if document else [],
    }


def _chips(session: Session, principal: Principal, refs: list[str]) -> dict[str, Any]:
    from riskwren.inventory.registry import find_any

    shown, hidden = [], 0
    for ref in refs:
        try:
            record_type, record = find_any(session, ref)
        except NotFound:
            continue
        if access.can_see(session, principal, record_type, record):
            shown.append({**records.chip(record_type, record),
                          "data_class": getattr(record, "data_class", None)})  # fmt: skip
        else:
            hidden += 1
    return {"records": shown, "hidden": hidden}


def view(session: Session, principal: Principal, third_party: ThirdParty) -> dict[str, Any]:
    """Everything a tiering needs: the questions, what the inventory suggests and from what,
    the tiers and their rules, and the tierings so far."""
    from riskwren.db.models import QuestionnaireVersion

    row = _questionnaire(session)
    version = questionnaires.version_of(session, row)
    known = facts(session, third_party)
    names = labels(session)
    earlier = session.scalars(
        select(TierAssessment)
        .where(TierAssessment.third_party_id == third_party.id)
        .order_by(TierAssessment.id.desc())
    ).all()
    documents: dict[int, Any] = {}
    for each in earlier:
        if each.questionnaire_version_id and each.questionnaire_version_id not in documents:
            asked = session.get(QuestionnaireVersion, each.questionnaire_version_id)
            documents[each.questionnaire_version_id] = asked.document if asked else None
    return {
        "questionnaire": {"key": row.key, "title": row.title, "version": version.number},
        "document": version.document,
        "facts": known,
        "from": {
            "data_class": _chips(session, principal, known["data_class_from"]),
            "information": _chips(session, principal, known["information"]),
            "criticality": _chips(session, principal, known["criticality_from"]),
            "systems": _chips(session, principal, known["systems"]),
        },
        "suggested_answers": suggest(known),
        "tiers": tiers(session),
        "tierings": [
            _assessment_view(
                session, each, names, documents.get(each.questionnaire_version_id or 0)
            )
            for each in earlier
        ],
        "can": {"tier": may_tier(session, principal, third_party)},
    }


def record(
    session: Session, principal: Principal, third_party: ThirdParty, answers: Mapping[str, Any],
    tier: str | None, rationale: str | None,
) -> TierAssessment:  # fmt: skip
    """Record a tiering: the answers, the tier the rules give and why, and the tier the person
    says, with their reason where it differs."""
    if third_party.status != "active":
        raise Conflict("A retired third party is not tiered.")
    if not may_tier(session, principal, third_party):
        raise PermissionDenied("A third party is tiered by those who keep it, or by an assessor.")
    row = _questionnaire(session)
    version = questionnaires.version_of(session, row)
    cleaned, errors = questionnaires.clean(version.document, answers, complete=True)
    if errors:
        raise Invalid("Some answers need another look.", errors)
    listed = tiers(session)
    names = {each["key"]: each["label"] for each in listed}
    known = facts(session, third_party)
    suggested, reasons = evaluate(listed, cleaned, known)
    chosen = tier or suggested
    said = records.text(rationale)
    if chosen not in names:
        raise Invalid("The tiering was not recorded.", {"tier": "Choose one of the tiers."})
    if chosen != suggested and not said:
        raise Invalid(
            "The tiering was not recorded.",
            {"rationale": f"The rules give {names[suggested]}. Say why it should be "
                          f"{names[chosen]}."},
        )  # fmt: skip
    if said and len(said) > LONGEST_RATIONALE:
        raise Invalid("The tiering was not recorded.",
                      {"rationale": f"Keep this to {LONGEST_RATIONALE} characters."})  # fmt: skip
    before = current(session, third_party)
    with audit.operation(
        session, "third_party.tier", tier=names[chosen], suggested=names[suggested],
        rationale=said if chosen != suggested else None,
    ):  # fmt: skip
        made = TierAssessment(
            third_party_id=third_party.id, answers=cleaned, facts=known,
            questionnaire_version_id=version.id, suggested=suggested, reasons=reasons,
            tier=chosen, rationale=said, assessed_by=principal.account_id,
            assessed_by_name=principal.name, assessed_at=utc_now(),
        )  # fmt: skip
        session.add(made)
        session.flush()
        if before is not None:
            before.superseded_by = made.id
        third_party.tier = chosen
        records.touch(session, third_party)
        session.flush()
    return made
