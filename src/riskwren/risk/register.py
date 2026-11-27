"""The register: raising a risk, judging it, and knowing whether it is in order."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from datetime import date
from typing import Any

from sqlalchemy import case, exists, or_, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core import scoring
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import Event, OrgUnit, Risk, RiskAssessment, RiskSubject
from riskwren.db.models.risk import ASSESSMENT_KINDS, RISK_STATUSES
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.completeness import Expected
from riskwren.inventory.registry import TYPES, Field, RecordType, find_any, register
from riskwren.people import units
from riskwren.program import rules
from riskwren.risk import categories
from riskwren.risk import method as methods

# --- What a risk is, for the code that every record type shares -----------------------------


def _new(risk: Risk) -> None:
    risk.status, risk.standing, risk.residual_in_doubt = "open", "not_assessed", False


def _apply(
    session: Session, risk: Risk, values: Mapping[str, Any], errors: records.Errors, creating: bool
) -> None:
    if "category" in values or creating:
        key = records.text(values.get("category"))
        if key is None:
            errors.add("category", "Say what kind of risk this is.")
        else:
            try:
                found = categories.by_key(session, key)
            except NotFound:
                errors.add("category", f"{key!r} is not a risk category.")
            else:
                if found.status != "active" and found.id != risk.category_id:
                    errors.add("category", "That category has been retired. Choose another.")
                else:
                    risk.category_id = found.id
    if "library_key" in values and creating:
        risk.library_key = records.text(values["library_key"])
    if values.get("status") is not None:
        status = values["status"]
        if status not in RISK_STATUSES:
            errors.add("status", f"Use one of: {', '.join(RISK_STATUSES)}.")
        elif status == "closed" and not records.text(
            values.get("closed_reason", risk.closed_reason)
        ):
            errors.add("closed_reason", "Say why this risk no longer applies.")
        else:
            risk.status = status
    if "closed_reason" in values:
        risk.closed_reason = records.text(values["closed_reason"])
    if risk.status != "closed":
        risk.closed_reason = None


def _rating_order(name: str) -> Callable[[Session, Any], Any]:
    def column(session: Session, model: Any) -> Any:
        ranks = {
            key: rank for rank, key in enumerate(scoring.rating_keys(methods.current(session)))
        }
        return case(ranks, value=getattr(model, name), else_=None)

    return column


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    if filters.get("category"):
        tree = categories.Tree(session)
        top = categories.by_key(session, str(filters["category"]))
        found.append(Risk.category_id.in_(tree.with_descendants(top.id)))
    if filters.get("at"):
        # Risks that sit at exactly this level: its own, and those escalated to it.
        unit = int(filters["at"])
        found.append(or_(Risk.org_unit_id == unit, Risk.escalated_to_unit_id == unit))
    if filters.get("objective"):
        from riskwren.db.models import Objective, RiskObjective

        objective = session.scalars(
            select(Objective).where(Objective.ref == str(filters["objective"]).strip().upper())
        ).first()
        found.append(
            Risk.id.in_(
                select(RiskObjective.risk_id).where(
                    RiskObjective.objective_id == (objective.id if objective else -1)
                )
            )
        )
    if filters.get("subject"):
        record_type, record = find_any(session, str(filters["subject"]))
        if not access.can_see(session, principal, record_type, record):
            raise NotFound(f"There is no record {filters['subject']}.")
        found.append(
            Risk.id.in_(
                select(RiskSubject.risk_id).where(
                    RiskSubject.subject_type == record_type.key,
                    RiskSubject.subject_id == record.id,
                )
            )
        )
    if filters.get("above_appetite"):
        found.append(Risk.standing.in_(("treated", "accepted", "needs_decision")))
    if filters.get("overdue"):
        found.append(Risk.status == "open")
        found.append(Risk.next_review_on < utc_now().date())
    if filters.get("in_doubt"):
        found.append(Risk.residual_in_doubt.is_(True))
    for axis in ("likelihood", "impact"):
        for kind in ASSESSMENT_KINDS:
            value = filters.get(f"{kind}_{axis}")
            if value not in (None, ""):
                found.append(getattr(Risk, f"{kind}_{axis}") == int(value))
    return found


def flags(risk: Risk, today: date | None = None) -> dict[str, Any]:
    today = today or utc_now().date()
    return {
        "review_overdue": bool(
            risk.status == "open" and risk.next_review_on and risk.next_review_on < today
        ),
        "residual_in_doubt": risk.residual_in_doubt,
        "residual_doubt_reason": risk.residual_doubt_reason,
    }


def _ratings(risk: Risk) -> dict[str, Any]:
    return {
        kind: {
            "likelihood": getattr(risk, f"{kind}_likelihood"),
            "impact": getattr(risk, f"{kind}_impact"),
            "rating": getattr(risk, f"{kind}_rating"),
        }
        for kind in ASSESSMENT_KINDS
    }


def _cards(session: Session, rows: list[Risk]) -> list[dict[str, Any]]:
    tree = categories.Tree(session)
    today = utc_now().date()
    out = []
    for risk in rows:
        category = tree.by_id.get(risk.category_id)
        out.append(
            {
                "status": risk.status,
                "standing": risk.standing,
                "category": category.key if category else None,
                "category_label": tree.label(risk.category_id),
                "appetite": tree.appetite(risk.category_id),
                "ratings": _ratings(risk),
                "next_review_on": risk.next_review_on,
                "escalated_to_unit_id": risk.escalated_to_unit_id,
                "response": risk.response,
                **flags(risk, today),
            }
        )
    return out


def _detail(session: Session, principal: Principal, risk: Risk) -> dict[str, Any]:
    return {
        "closed_reason": risk.closed_reason,
        "response_rationale": risk.response_rationale,
        "escalation_reason": risk.escalation_reason,
        "library_key": risk.library_key,
        "subjects": subjects_of(session, principal, risk),
        "assessments": {
            kind: view_assessment(session, row) if row else None
            for kind, row in latest(session, risk).items()
        },
        "can_escalate": can_escalate(session, principal, risk),
        "indicators": _indicators(session, principal, risk),
        "objectives": _objectives(session, principal, risk),
    }


def _objectives(session: Session, principal: Principal, risk: Risk) -> list[dict[str, Any]]:
    from riskwren.risk import objectives

    return objectives.objectives_of(session, principal, risk)


def _indicators(session: Session, principal: Principal, risk: Risk) -> list[dict[str, Any]]:
    """The indicators that warn of the risk. They build on this module, so they are asked
    for when needed."""
    from riskwren.risk import indicators

    return indicators.of_risk(session, principal, risk)


def _history_title(event: Event, lookups: Any) -> str | None:
    changes = event.changes or {}

    def now(field: str) -> Any:
        pair = changes.get(field) or [None, None]
        return pair[1] if pair[1] is not None else pair[0]

    if event.subject_type == "risk_assessment" and event.action == "created":
        ratings = {r["key"]: r["label"] for r in methods.current(lookups.session)["ratings"]}
        rating = ratings.get(now("rating"), now("rating"))
        return f"Assessed the {now('kind')} risk as {rating}"
    if event.subject_type == "risk_assessment":
        return "An earlier assessment was superseded"
    if event.subject_type == "risk" and (event.context or {}).get("op") == "program.change":
        return "Changed when the program was changed"
    if event.subject_type == "risk_objective":
        from riskwren.risk import objectives  # noqa: F401  so that objectives can be named

        name = lookups.name("objective", now("objective_id")) or "an objective"
        return (
            f"Now threatens {name}" if event.action == "created" else f"No longer threatens {name}"
        )
    if event.subject_type == "risk_subject":
        kind = now("subject_type")
        name = lookups.name(kind, now("subject_id")) if kind in TYPES else "a record"
        return f"Now concerns {name}" if event.action == "created" else f"No longer concerns {name}"
    return None


def _history_value(lookups: Any, field: str, value: Any) -> Any:
    """Names for what a risk's events hold as keys: its category and its ratings."""
    if field == "category_id":
        return categories.Tree(lookups.session).label(value) or None
    if field.endswith("_rating"):
        ratings = {r["key"]: r["label"] for r in methods.current(lookups.session)["ratings"]}
        return ratings.get(value, value)
    return None


def _no_controls(model: Any) -> Any:
    from riskwren.db.models import RiskControl

    return ~exists(select(RiskControl.id).where(RiskControl.risk_id == model.id))


RISK = register(
    RecordType(
        "risk",
        Risk,
        "RSK",
        "risks",
        "risk",
        "risks",
        fields=(
            Field("cause", "Cause", "long"),
            Field("event", "Event", "long"),
            Field("consequence", "Consequence", "long"),
        ),
        is_thing=False,
        sorts=(
            "updated_at",
            "name",
            "ref",
            "residual_rating",
            "inherent_rating",
            "target_rating",
            "standing",
            "next_review_on",
            "status",
        ),
        filters=("status", "standing", "residual_rating", "inherent_rating", "response"),
        extra={
            "new": _new,
            "apply": _apply,
            "cards": _cards,
            "detail": _detail,
            "conditions": _conditions,
            "live_statuses": ("open",),
            "live_filters": {"status": "open"},
            "expected": [
                Expected(
                    "rating",
                    "a rating",
                    lambda model: model.standing == "not_assessed",
                    "Nobody has said how likely or how bad it is.",
                ),
                Expected(
                    "controls",
                    "a control that bears on it",
                    _no_controls,
                    "Nothing is recorded as reducing it.",
                ),
            ],
            "sort_columns": {
                name: _rating_order(name)
                for name in ("residual_rating", "inherent_rating", "target_rating")
            },
            "history_title": _history_title,
            "history_value": _history_value,
            "history_loud": ("program.change",),
            "history_quiet": (
                "next_review_on",
                *(
                    f"{kind}_{part}"
                    for kind in ASSESSMENT_KINDS
                    for part in ("likelihood", "impact", "rating")
                ),
            ),
            "history_labels": {
                "category_id": "Category",
                "closed_reason": "Why it was closed",
                "response": "Response",
                "response_rationale": "Why this response",
                "standing": "Standing",
                "next_review_on": "Next review",
                "escalated_to_unit_id": "Escalated to",
                "escalation_reason": "Why it was escalated",
                "residual_in_doubt": "Residual rating in doubt",
                "residual_doubt_reason": "Why it is in doubt",
                **{
                    f"{kind}_{part}": f"{kind.capitalize()} {part}"
                    for kind in ASSESSMENT_KINDS
                    for part in ("likelihood", "impact", "rating")
                },
            },
        },
    )
)


# --- Raising and changing -----------------------------------------------------------------


def create(
    session: Session, principal: Principal, values: Mapping[str, Any], *, checked: bool = False
) -> Risk:
    risk: Risk = records.create(session, principal, RISK, values, checked=checked)
    with audit.operation(session, "risk.create"):
        refresh(session, risk)
    return risk


def update(
    session: Session,
    principal: Principal,
    risk: Risk,
    values: Mapping[str, Any],
    *,
    version: int | None,
) -> Risk:
    records.update(session, principal, RISK, risk, values, version=version)
    with audit.operation(session, "risk.edit"):
        refresh(session, risk)
    return risk


# --- Standing and dates -------------------------------------------------------------------

# Slice 6 adds what treatment says about a risk above appetite: a plan on time, or an
# acceptance in force. Until something is registered here, such a risk needs a decision.
TREATMENT: list[Callable[[Session, Risk, date], str | None]] = []


def standing_of(session: Session, risk: Risk, *, today: date | None = None) -> str:
    """Whether the risk is in order (see spec/engine.md). Rating says how much is at stake;
    this says whether it is within appetite, being treated, accepted, or needs a decision."""
    today = today or utc_now().date()
    if risk.status == "closed":
        return "closed"
    if not risk.residual_rating:
        return "not_assessed"
    appetite = categories.Tree(session).appetite(risk.category_id)
    if not scoring.exceeds(methods.current(session), risk.residual_rating, appetite):
        return "within"
    for ask in TREATMENT:
        answer = ask(session, risk, today)
        if answer:
            return answer
    return "needs_decision"


def next_review(session: Session, risk: Risk) -> date | None:
    """When the risk is next due to be looked at: sooner the more is at stake."""
    if risk.status == "closed":
        return None
    cadences = rules.get(session, "cadences")
    newest = latest(session, risk).get("residual")
    if newest is None:
        months = int(cadences.get("unrated_risk_review_months", 3))
        return rules.add_months(risk.created_at.date(), months)
    # The rating as the method in force reads it, which may not be the one it was given.
    rating = risk.residual_rating or newest.rating
    months = int(cadences["risk_review_months"].get(rating, 12))
    return rules.add_months(newest.assessed_at.date(), months)


def refresh(session: Session, risk: Risk, *, today: date | None = None) -> None:
    """Work out again what follows from the risk's ratings: its standing and its next review."""
    session.flush()
    standing, due = standing_of(session, risk, today=today), next_review(session, risk)
    if risk.standing != standing:
        risk.standing = standing
    if risk.next_review_on != due:
        risk.next_review_on = due
    session.flush()


def refresh_category(session: Session, category_id: int) -> int:
    """After an appetite changes: the standing of every risk beneath that category."""
    ids = categories.Tree(session).with_descendants(category_id)
    changed = 0
    for risk in session.scalars(select(Risk).where(Risk.category_id.in_(ids))):
        before = risk.standing
        refresh(session, risk)
        changed += before != risk.standing
    return changed


# --- Assessments --------------------------------------------------------------------------

# Slice 6 registers how a risk's controls are found, so that a residual assessment can be
# offered a suggestion with its working.
CONTROLS: list[Callable[[Session, Risk], list[dict[str, Any]]]] = []


def latest(session: Session, risk: Risk) -> dict[str, RiskAssessment | None]:
    rows = session.scalars(
        select(RiskAssessment)
        .where(RiskAssessment.risk_id == risk.id, RiskAssessment.superseded_by.is_(None))
        .order_by(RiskAssessment.id)
    ).all()
    found: dict[str, RiskAssessment | None] = dict.fromkeys(ASSESSMENT_KINDS)
    for row in rows:
        found[row.kind] = row
    return found


def suggestion(session: Session, risk: Risk) -> dict[str, Any] | None:
    """What the risk's controls suggest for its residual rating, or None when there is no
    inherent rating to start from."""
    if not (risk.inherent_likelihood and risk.inherent_impact):
        return None
    controls = [control for provider in CONTROLS for control in provider(session, risk)]
    return scoring.suggest(
        methods.current(session), risk.inherent_likelihood, risk.inherent_impact, controls
    )


def assess(
    session: Session,
    principal: Principal,
    risk: Risk,
    *,
    kind: str,
    likelihood: Any,
    impact_levels: Mapping[str, Any] | None,
    rationale: str | None,
) -> RiskAssessment:
    """Record a judgment of the risk. It supersedes the last of its kind and is never edited."""
    if not access.can_assess(session, principal, RISK, risk):
        raise PermissionDenied("You cannot assess this risk.")
    if risk.status == "closed":
        raise Conflict("This risk is closed. Reopen it before assessing it.")
    row = methods.current_row(session)
    method = row.definition
    errors = records.Errors()
    if kind not in ASSESSMENT_KINDS:
        errors.add("kind", f"Use one of: {', '.join(ASSESSMENT_KINDS)}.")
    if not isinstance(likelihood, int) or likelihood not in scoring.levels(method, "likelihood"):
        errors.add("likelihood", "Choose how likely it is.")
    known = {dimension["key"] for dimension in method["dimensions"]}
    allowed = scoring.levels(method, "impact")
    chosen: dict[str, int] = {}
    for key, level in (impact_levels or {}).items():
        if level in (None, "", 0):
            continue
        if key not in known:
            errors.add("impact_levels", f"{key!r} is not one of the impact dimensions.")
        elif not isinstance(level, int) or level not in allowed:
            errors.add("impact_levels", "Choose a level for each dimension that applies.")
        else:
            chosen[key] = level
    impact = scoring.overall_impact(chosen)
    if impact is None:
        errors.add("impact_levels", "Say how bad it would be on at least one dimension.")
    reason = records.text(rationale)
    if not reason:
        errors.add("rationale", "Say why, in a sentence or two. A rating is a judgment.")
    if errors:
        raise Invalid("The assessment was not recorded.", errors)
    assert impact is not None and reason is not None
    with audit.operation(session, "risk.assess", kind=kind):
        new = RiskAssessment(
            risk_id=risk.id,
            kind=kind,
            likelihood=likelihood,
            impact=impact,
            impact_levels=chosen,
            rating=scoring.rating(method, likelihood, impact),
            rationale=reason,
            suggested=suggestion(session, risk) if kind == "residual" else None,
            method_id=row.id,
            assessed_by=principal.account_id,
            assessed_by_name=principal.name,
            assessed_at=utc_now(),
        )
        session.add(new)
        session.flush()
        for earlier in session.scalars(
            select(RiskAssessment).where(
                RiskAssessment.risk_id == risk.id,
                RiskAssessment.kind == kind,
                RiskAssessment.superseded_by.is_(None),
                RiskAssessment.id != new.id,
            )
        ):
            earlier.superseded_by = new.id
        setattr(risk, f"{kind}_likelihood", new.likelihood)
        setattr(risk, f"{kind}_impact", new.impact)
        setattr(risk, f"{kind}_rating", new.rating)
        if kind == "residual":
            risk.residual_in_doubt, risk.residual_doubt_reason = False, None
        risk.version += 1
        risk.updated_at = utc_now()
        refresh(session, risk)
    return new


def view_assessment(session: Session, row: RiskAssessment) -> dict[str, Any]:
    """An assessment with everything needed to show its reasoning as it was made: the levels
    chosen, their definitions under the method version in force then, who, when, and why."""
    method = methods.by_id(session, row.method_id)
    definition = method.definition
    labels = {level["level"]: level for level in definition["likelihood"]}
    impact_labels = {level["level"]: level["label"] for level in definition["impact_levels"]}
    ratings = {rating["key"]: rating["label"] for rating in definition["ratings"]}
    dimensions = [
        {
            "key": dimension["key"],
            "label": dimension["label"],
            "level": row.impact_levels[dimension["key"]],
            "level_label": impact_labels.get(row.impact_levels[dimension["key"]]),
            "definition": dimension["levels"].get(str(row.impact_levels[dimension["key"]])),
        }
        for dimension in definition["dimensions"]
        if dimension["key"] in row.impact_levels
    ]
    place = scoring.position(definition, row.rating)
    return {
        "id": row.id,
        "kind": row.kind,
        "likelihood": row.likelihood,
        "likelihood_label": labels.get(row.likelihood, {}).get("label"),
        "likelihood_definition": labels.get(row.likelihood, {}).get("definition"),
        "impact": row.impact,
        "impact_label": impact_labels.get(row.impact),
        "dimensions": dimensions,
        "rating": row.rating,
        "rating_label": ratings.get(row.rating, row.rating),
        "ramp_level": scoring.ramp_level(place, len(ratings)),
        "rationale": row.rationale,
        "suggested": row.suggested,
        "method_version": method.version,
        "assessed_by": row.assessed_by_name,
        "assessed_at": row.assessed_at,
        "superseded": row.superseded_by is not None,
    }


def assessments(session: Session, risk: Risk) -> list[dict[str, Any]]:
    """Every judgment ever made of the risk, newest first."""
    rows = session.scalars(
        select(RiskAssessment)
        .where(RiskAssessment.risk_id == risk.id)
        .order_by(RiskAssessment.id.desc())
    ).all()
    return [view_assessment(session, row) for row in rows]


# --- What a risk concerns -----------------------------------------------------------------


def subjects_of(session: Session, principal: Principal, risk: Risk) -> dict[str, Any]:
    """The processes, systems, and third parties the risk concerns, cut to what the person
    may see, with a count of those they may not."""
    rows = session.scalars(
        select(RiskSubject).where(RiskSubject.risk_id == risk.id).order_by(RiskSubject.id)
    ).all()
    wanted: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        wanted[row.subject_type].add(row.subject_id)
    shown, hidden = [], 0
    for key, ids in wanted.items():
        record_type = TYPES.get(key)
        if record_type is None:
            continue
        model: Any = record_type.model
        for record in session.scalars(select(model).where(model.id.in_(ids)).order_by(model.name)):
            if access.can_see(session, principal, record_type, record):
                shown.append(records.chip(record_type, record))
            else:
                hidden += 1
    return {"records": shown, "hidden": hidden}


def set_subjects(session: Session, principal: Principal, risk: Risk, refs: list[str]) -> None:
    """Say which processes, systems, and third parties the risk concerns."""
    if not access.can_edit(session, principal, RISK, risk):
        raise PermissionDenied("You cannot edit this risk.")
    wanted: set[tuple[str, int]] = set()
    for ref in dict.fromkeys(refs):
        try:
            record_type, record = find_any(session, ref)
        except NotFound as exc:
            raise Invalid("What the risk concerns was not saved.", {"subjects": str(exc)}) from exc
        if not record_type.is_thing:
            raise Invalid(
                "What the risk concerns was not saved.",
                {"subjects": "A risk concerns processes, systems, and third parties."},
            )
        if not access.can_see(session, principal, record_type, record):
            raise Invalid(
                "What the risk concerns was not saved.", {"subjects": f"There is no record {ref}."}
            )
        wanted.add((record_type.key, record.id))
    existing = session.scalars(select(RiskSubject).where(RiskSubject.risk_id == risk.id)).all()
    have = {(row.subject_type, row.subject_id): row for row in existing}
    with audit.operation(session, "risk.subjects"):
        for key, row in have.items():
            # What the person cannot see, they did not choose to remove.
            record_type = TYPES.get(key[0])
            record = session.get(record_type.model, key[1]) if record_type else None
            visible = record is not None and access.can_see(session, principal, record_type, record)  # type: ignore[arg-type]
            if key not in wanted and visible:
                session.delete(row)
        for subject_type, subject_id in sorted(wanted - set(have)):
            session.add(
                RiskSubject(risk_id=risk.id, subject_type=subject_type, subject_id=subject_id)
            )
        session.flush()


# --- Escalation ---------------------------------------------------------------------------


def can_escalate(session: Session, principal: Principal, risk: Risk) -> bool:
    return principal.leads_unit(risk.org_unit_id) or access.can_edit(session, principal, RISK, risk)


def escalate(
    session: Session, principal: Principal, risk: Risk, unit_id: int | None, reason: str | None
) -> Risk:
    """Raise a risk to a unit above its own, or, with no unit, take it back down."""
    if not can_escalate(session, principal, risk):
        raise PermissionDenied("You cannot escalate this risk.")
    cleaned = records.text(reason)
    if unit_id is None:
        with audit.operation(session, "risk.deescalate"):
            risk.escalated_to_unit_id, risk.escalation_reason = None, None
            records.touch(session, risk)
        return risk
    above = [unit.id for unit in units.ancestors(session, risk.org_unit_id)]
    target = session.get(OrgUnit, unit_id)
    if target is None or unit_id not in above:
        raise Invalid(
            "The risk was not escalated.",
            {"unit_id": "Choose a unit above the one the risk belongs to."},
        )
    if not cleaned:
        raise Invalid("The risk was not escalated.", {"reason": "Say why it needs to go higher."})
    with audit.operation(session, "risk.escalate"):
        risk.escalated_to_unit_id, risk.escalation_reason = unit_id, cleaned
        records.touch(session, risk)
    return risk
