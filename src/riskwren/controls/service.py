"""The control library: describing a control once, rating it, and saying which risks it bears on.

What is known about a control is a rating by a named person on a date, on some basis. A
control nobody has rated, or whose rating has aged out, counts for nothing when a residual
rating is suggested (see spec/engine.md).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core import scoring
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid, NotFound, PermissionDenied
from riskwren.db.models import Control, ControlLibraryEntry, ControlRating, Event, Risk, RiskControl
from riskwren.db.models.controls import BASES, EFFECTIVENESS, REDUCES, RELIANCE
from riskwren.db.models.inventory import RECORD_STATUSES
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.registry import Field, RecordType, register
from riskwren.program import rules
from riskwren.risk import method as methods
from riskwren.risk import register as risks
from riskwren.risk.register import RISK

# --- What a control is, for the code every record type shares -------------------------------


def _new(control: Control) -> None:
    control.status, control.is_key = "active", False
    control.design, control.operation = "not_assessed", "not_assessed"


def _apply(
    session: Session,
    control: Control,
    values: Mapping[str, Any],
    errors: records.Errors,
    creating: bool,
) -> None:
    if values.get("status") is not None:
        if values["status"] not in RECORD_STATUSES:
            errors.add("status", "Use active or retired.")
        else:
            control.status = values["status"]
    if values.get("is_key") is not None:
        control.is_key = bool(values["is_key"])
    if "library_key" in values and creating:
        control.library_key = records.text(values["library_key"])


def is_stale(session: Session, control: Control, *, today: date | None = None) -> bool:
    """Whether what is known about the control is too old to rely on."""
    if control.rated_at is None:
        return False
    months = int(rules.get(session, "cadences").get("control_rating_months", 12))
    return rules.add_months(control.rated_at.date(), months) < (today or utc_now().date())


def state_of(session: Session, control: Control, *, today: date | None = None) -> str:
    """What is known about the control, as one word: effective, partly, ineffective,
    not_assessed, or stale."""
    return scoring.control_state(
        control.design, control.operation, stale=is_stale(session, control, today=today)
    )


def _cards(session: Session, rows: list[Control]) -> list[dict[str, Any]]:
    counts = dict(
        session.execute(
            select(RiskControl.control_id, func.count())
            .where(RiskControl.control_id.in_([row.id for row in rows] or [0]))
            .group_by(RiskControl.control_id)
        ).all()
    )
    today = utc_now().date()
    return [
        {
            "status": row.status,
            "statement": row.statement,
            "is_key": row.is_key,
            "design": row.design,
            "operation": row.operation,
            "state": state_of(session, row, today=today),
            "rated_at": row.rated_at,
            "risks": counts.get(row.id, 0),
        }
        for row in rows
    ]


def _detail(session: Session, principal: Principal, control: Control) -> dict[str, Any]:
    return {
        "library_key": control.library_key,
        "rating": next(iter(ratings(session, control)), None),
        "reduces": risks_of(session, principal, control),
    }


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    state = filters.get("state")
    if state == "not_assessed":
        found.append(or_(Control.design == "not_assessed", Control.operation == "not_assessed"))
    elif state in ("effective", "partly", "ineffective"):
        found.append(Control.design != "not_assessed")
        found.append(Control.operation != "not_assessed")
        if state == "ineffective":
            found.append(or_(Control.design == "ineffective", Control.operation == "ineffective"))
        else:
            found += [Control.design != "ineffective", Control.operation != "ineffective"]
            partly = or_(Control.design == "partly", Control.operation == "partly")
            found.append(partly if state == "partly" else ~partly)
    if filters.get("is_key"):
        found.append(Control.is_key.is_(True))
    if filters.get("risk"):
        risk = records.load(session, principal, RISK, str(filters["risk"]))
        found.append(
            Control.id.in_(select(RiskControl.control_id).where(RiskControl.risk_id == risk.id))
        )
    return found


def _history_title(event: Event, lookups: Any) -> str | None:
    changes = event.changes or {}

    def now(field: str) -> Any:
        pair = changes.get(field) or [None, None]
        return pair[1] if pair[1] is not None else pair[0]

    if event.subject_type == "control_rating" and event.action == "created":
        design = WORDS.get(now("design"), now("design"))
        operation = WORDS.get(now("operation"), now("operation"))
        return f"Rated: design {design}, operation {operation}".replace(
            "design Effective, operation Effective", "effective in design and operation"
        )
    if event.subject_type == "control_rating":
        return "An earlier rating was superseded"
    return None


WORDS = {
    "effective": "Effective",
    "partly": "Partly effective",
    "ineffective": "Ineffective",
    "not_assessed": "Not assessed",
    "stale": "Rating out of date",
}


def _history_value(lookups: Any, field: str, value: Any) -> Any:
    return WORDS.get(value) if field in ("design", "operation") else None


CONTROL = register(
    RecordType(
        "control",
        Control,
        "CTL",
        "controls",
        "control",
        "controls",
        fields=(
            Field("statement", "Statement", "long", required=True),
            Field("objective", "Objective", "long"),
            Field("kind", "Kind", "choice", vocab="control_kinds", required=True),
            Field("nature", "Nature", "choice", vocab="control_natures"),
            Field("frequency", "Frequency", "choice", vocab="control_frequencies"),
        ),
        is_thing=False,
        sorts=("updated_at", "name", "ref", "kind", "status", "rated_at"),
        filters=("status", "kind", "nature", "frequency"),
        extra={
            "new": _new,
            "apply": _apply,
            "cards": _cards,
            "detail": _detail,
            "conditions": _conditions,
            "history_title": _history_title,
            "history_value": _history_value,
            "history_quiet": ("design", "operation", "rated_at"),
            "history_labels": {
                "is_key": "Key control",
                "design": "Design",
                "operation": "Operation",
                "rated_at": "Last rated",
            },
        },
    )
)


# --- Rating -------------------------------------------------------------------------------


def ratings(session: Session, control: Control) -> list[dict[str, Any]]:
    """Every rating the control has had, newest first."""
    rows = session.scalars(
        select(ControlRating)
        .where(ControlRating.control_id == control.id)
        .order_by(ControlRating.id.desc())
    ).all()
    return [
        {
            "id": row.id,
            "design": row.design,
            "operation": row.operation,
            "state": scoring.control_state(row.design, row.operation),
            "basis": row.basis,
            "note": row.note,
            "rated_by": row.rated_by_name,
            "rated_at": row.rated_at,
            "superseded": row.superseded_by is not None,
        }
        for row in rows
    ]


def rate(
    session: Session,
    principal: Principal,
    control: Control,
    *,
    design: str | None,
    operation: str | None,
    note: str | None,
    basis: str = "judgment",
    at: datetime | None = None,
) -> ControlRating:
    """Record what is known about whether a control works. It supersedes the last rating and
    is never edited. Risks that leaned on the control are told if it now suggests worse."""
    if not access.can_assess(session, principal, CONTROL, control):
        raise PermissionDenied("You cannot rate this control.")
    errors = records.Errors()
    for field, value in (("design", design), ("operation", operation)):
        if value not in EFFECTIVENESS:
            errors.add(field, "Choose effective, partly effective, ineffective, or not assessed.")
    if basis not in BASES:
        errors.add("basis", f"Use one of: {', '.join(BASES)}.")
    reason = records.text(note)
    if not reason:
        errors.add("note", "Say what this rests on: what was looked at, or what is known.")
    if errors:
        raise Invalid("The rating was not recorded.", errors)
    assert design is not None and operation is not None and reason is not None
    with audit.operation(session, "control.rate"):
        new = ControlRating(
            control_id=control.id,
            design=design,
            operation=operation,
            basis=basis,
            note=reason,
            rated_by=principal.account_id,
            rated_by_name=principal.name,
            rated_at=at or utc_now(),
        )
        session.add(new)
        session.flush()
        for earlier in session.scalars(
            select(ControlRating).where(
                ControlRating.control_id == control.id,
                ControlRating.superseded_by.is_(None),
                ControlRating.id != new.id,
            )
        ):
            earlier.superseded_by = new.id
        control.design, control.operation, control.rated_at = design, operation, new.rated_at
        control.version += 1
        control.updated_at = utc_now()
        session.flush()
        for risk in session.scalars(
            select(Risk).join(RiskControl, RiskControl.risk_id == Risk.id).where(
                RiskControl.control_id == control.id, Risk.status != "closed"
            )
        ):  # fmt: skip
            check_doubt(session, risk)
    return new


# --- Controls and risks -------------------------------------------------------------------


def _links(session: Session, risk: Risk) -> list[tuple[RiskControl, Control]]:
    return [
        (link, control)
        for link, control in session.execute(
            select(RiskControl, Control)
            .join(Control, Control.id == RiskControl.control_id)
            .where(RiskControl.risk_id == risk.id)
            .order_by(RiskControl.id)
        )
    ]


def for_scoring(session: Session, risk: Risk) -> list[dict[str, Any]]:
    """A risk's controls as the scoring arithmetic takes them."""
    today = utc_now().date()
    return [
        {
            "ref": control.ref,
            "name": control.name,
            "reduces": link.reduces,
            "reliance": link.reliance,
            "design": control.design,
            "operation": control.operation,
            "stale": is_stale(session, control, today=today),
        }
        for link, control in _links(session, risk)
        if control.status == "active"
    ]


risks.CONTROLS.append(for_scoring)


def of_risk(session: Session, principal: Principal, risk: Risk) -> dict[str, Any]:
    """The controls that bear on a risk, cut to what the person may see, with what they
    suggest for its residual rating."""
    shown, hidden = [], 0
    today = utc_now().date()
    for link, control in _links(session, risk):
        if not access.can_see(session, principal, CONTROL, control):
            hidden += 1
            continue
        shown.append(
            {
                "id": link.id,
                "reduces": link.reduces,
                "reliance": link.reliance,
                "note": link.note,
                "control": {
                    **records.chip(CONTROL, control),
                    "statement": control.statement,
                    "status": control.status,
                    "is_key": control.is_key,
                    "state": state_of(session, control, today=today),
                    "rated_at": control.rated_at,
                    "library_key": control.library_key,
                },
            }
        )
    return {"controls": shown, "hidden": hidden, "suggestion": risks.suggestion(session, risk)}


def risks_of(session: Session, principal: Principal, control: Control) -> dict[str, Any]:
    """The risks a control bears on, cut to what the person may see."""
    rows = session.execute(
        select(RiskControl, Risk)
        .join(Risk, Risk.id == RiskControl.risk_id)
        .where(RiskControl.control_id == control.id)
        .order_by(Risk.name)
    ).all()
    shown, hidden = [], 0
    for link, risk in rows:
        if not access.can_see(session, principal, RISK, risk):
            hidden += 1
            continue
        shown.append(
            {
                **records.chip(RISK, risk),
                "reduces": link.reduces,
                "reliance": link.reliance,
                "residual_rating": risk.residual_rating,
                "standing": risk.standing,
            }
        )
    return {"risks": shown, "hidden": hidden}


def link(
    session: Session,
    principal: Principal,
    risk: Risk,
    control: Control,
    *,
    reduces: str | None,
    reliance: str | None,
    note: str | None = None,
) -> RiskControl:
    """Say that a control bears on a risk, or change how. One control bears on a risk once."""
    if not access.can_edit(session, principal, RISK, risk):
        raise PermissionDenied("You cannot edit this risk.")
    if not access.can_see(session, principal, CONTROL, control):
        raise NotFound(f"There is no control {control.ref}.")
    errors = records.Errors()
    if reduces not in REDUCES:
        errors.add("reduces", "Say what it reduces: likelihood, impact, or both.")
    if reliance not in RELIANCE:
        errors.add(
            "reliance", "Say whether the risk relies on it (primary) or it helps (supporting)."
        )
    cleaned = records.text(note)
    if cleaned and len(cleaned) > 300:
        errors.add("note", "Keep the note to 300 characters.")
    if control.status != "active":
        errors.add("control", "That control has been retired.")
    if errors:
        raise Invalid("The control was not linked.", errors)
    assert reduces is not None and reliance is not None
    existing = session.scalars(
        select(RiskControl).where(
            RiskControl.risk_id == risk.id, RiskControl.control_id == control.id
        )
    ).first()
    with audit.operation(session, "risk.control"):
        if existing is None:
            existing = RiskControl(
                risk_id=risk.id,
                control_id=control.id,
                reduces=reduces,
                reliance=reliance,
                note=cleaned,
            )
            session.add(existing)
        else:
            existing.reduces, existing.reliance, existing.note = reduces, reliance, cleaned
        session.flush()
        check_doubt(session, risk)
    return existing


def unlink(session: Session, principal: Principal, risk: Risk, control: Control) -> None:
    if not access.can_edit(session, principal, RISK, risk):
        raise PermissionDenied("You cannot edit this risk.")
    existing = session.scalars(
        select(RiskControl).where(
            RiskControl.risk_id == risk.id, RiskControl.control_id == control.id
        )
    ).first()
    if existing is None:
        raise NotFound("That control is not linked to this risk.")
    with audit.operation(session, "risk.control_removed"):
        session.delete(existing)
        session.flush()
        check_doubt(session, risk)


def check_doubt(session: Session, risk: Risk) -> bool:
    """After something about a risk's controls changes: does what is now known suggest a
    worse rating than the one on record? If so the risk is flagged, the reason named, and its
    owner asked to assess it again. The rating itself is never changed by the system."""
    newest = risks.latest(session, risk).get("residual")
    now = risks.suggestion(session, risk)
    if newest is None or now is None:
        return False
    method = methods.current(session)
    place = scoring.position(method, now["rating"])
    then = newest.suggested or {}
    worse_than_record = place > scoring.position(method, newest.rating)
    worse_than_then = place > scoring.position(method, then.get("rating")) if then else True
    doubt = worse_than_record and worse_than_then
    reason = None
    if doubt:
        was = {line.get("ref"): line for line in then.get("controls", [])}
        ratings_ = {r["key"]: r["label"] for r in method["ratings"]}
        changed = [
            f"{line['name']} is now {WORDS[line['state']].lower()}"
            for line in now["controls"]
            if line.get("ref") in was and line["counts"] < was[line["ref"]]["counts"]
        ]
        gone = [
            f"{line.get('name', 'a control')} is no longer linked"
            for ref, line in was.items()
            if ref not in {c.get("ref") for c in now["controls"]} and line.get("counts", 0) > 0
        ]
        because = "; ".join(changed + gone) or "what is known about its controls has changed"
        reason = (
            f"Since it was assessed, {because}. The controls now suggest "
            f"{ratings_.get(now['rating'], now['rating'])}."
        )
    if risk.residual_in_doubt != doubt or risk.residual_doubt_reason != reason:
        risk.residual_in_doubt, risk.residual_doubt_reason = doubt, reason
        session.flush()
    return doubt


# --- The starter library --------------------------------------------------------------------


def load_library(session: Session, pack: dict[str, Any]) -> int:
    source = str(pack["pack"]["key"])
    have = {row.key: row for row in session.scalars(select(ControlLibraryEntry))}
    changed = 0
    for item in pack["controls"]:
        values = {
            "title": item["title"],
            "statement": item["statement"],
            "kind": item["kind"],
            "nature": item.get("nature"),
            "frequency": item.get("frequency"),
            "reduces": item.get("reduces", "likelihood"),
            "source_pack": source,
        }
        row = have.get(item["key"])
        if row is None:
            session.add(ControlLibraryEntry(key=item["key"], **values))
            changed += 1
        elif any(getattr(row, name) != value for name, value in values.items()):
            for name, value in values.items():
                setattr(row, name, value)
            changed += 1
    session.flush()
    return changed


def library(
    session: Session, *, query: str | None = None, keys: list[str] | None = None
) -> list[dict[str, Any]]:
    statement = select(ControlLibraryEntry).order_by(ControlLibraryEntry.id)
    if keys is not None:
        statement = statement.where(ControlLibraryEntry.key.in_(keys or [""]))
    words = (query or "").strip().lower()
    if words:
        like = f"%{words}%"
        statement = statement.where(
            or_(
                func.lower(ControlLibraryEntry.title).like(like),
                func.lower(ControlLibraryEntry.statement).like(like),
            )
        )
    return [
        {
            "key": row.key,
            "title": row.title,
            "statement": row.statement,
            "kind": row.kind,
            "nature": row.nature,
            "frequency": row.frequency,
            "reduces": row.reduces,
        }
        for row in session.scalars(statement)
    ]
