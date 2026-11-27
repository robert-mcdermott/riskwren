"""Strategic objectives: what the organization means to achieve, and the risks that threaten
each (RSK-16).

An objective is a record of its own, set by a unit's leaders or a manager. A risk names the
objectives it threatens, from the risk's side, by those who keep the risk; each objective
shows exactly the risks that name it, with how each stands.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.errors import Invalid, NotFound, PermissionDenied
from riskwren.db.models import Objective, Risk, RiskObjective
from riskwren.db.models.governance import OBJECTIVE_STATUSES
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.registry import RecordType, find, register

KEY = "objective"


def can_add(principal: Principal, org_unit_id: int | None) -> bool:
    """A unit's leaders, and managers: objectives are set by those who lead."""
    return principal.leads_unit(org_unit_id) or principal.manages_unit(org_unit_id)


def can_edit(session: Session, principal: Principal, objective: Objective) -> bool:
    if can_add(principal, objective.org_unit_id):
        return True
    kinds = access.owner_kinds(session, OBJECTIVE, objective.id, principal.account_id)
    return bool(kinds & set(access.EDITING_KINDS))


def _new(objective: Objective) -> None:
    objective.status = "active"


def _apply(
    session: Session, objective: Objective, values: Mapping[str, Any], errors: records.Errors,
    creating: bool,
) -> None:  # fmt: skip
    if "status" in values and values["status"] is not None:
        if values["status"] not in OBJECTIVE_STATUSES:
            errors.add("status", "Use active, achieved, or retired.")
        else:
            objective.status = values["status"]
    if "period" in values:
        period = records.text(values.get("period"))
        if period and len(period) > 120:
            errors.add("period", "Keep this to 120 characters.")
        else:
            objective.period = period
    if "measure" in values:
        objective.measure = records.text(values.get("measure"))


def _risk_rows(session: Session, ids: list[int]) -> dict[int, list[Risk]]:
    found: dict[int, list[Risk]] = {each: [] for each in ids}
    for objective_id, risk in session.execute(
        select(RiskObjective.objective_id, Risk)
        .join(Risk, Risk.id == RiskObjective.risk_id)
        .where(RiskObjective.objective_id.in_(ids or [0]))
        .order_by(Risk.ref)
    ).all():
        found[objective_id].append(risk)
    return found


def _cards(session: Session, rows: list[Objective]) -> list[dict[str, Any]]:
    risks = _risk_rows(session, [row.id for row in rows])
    out = []
    for row in rows:
        open_ = [risk for risk in risks[row.id] if risk.status == "open"]
        by_rating: dict[str, int] = {}
        for risk in open_:
            if risk.residual_rating:
                by_rating[risk.residual_rating] = by_rating.get(risk.residual_rating, 0) + 1
        out.append({
            "status": row.status, "period": row.period, "risks": len(open_),
            "by_rating": by_rating,
        })  # fmt: skip
    return out


def risks_of(session: Session, principal: Principal, objective: Objective) -> dict[str, Any]:
    """The risks that name the objective, open ones first, as much as the person may see."""
    from riskwren.risk.register import RISK  # it builds on this module

    shown, hidden = [], 0
    for risk in _risk_rows(session, [objective.id])[objective.id]:
        if not access.can_see(session, principal, RISK, risk):
            hidden += 1
            continue
        shown.append({
            **records.chip(RISK, risk), "status": risk.status, "standing": risk.standing,
            "residual_rating": risk.residual_rating, "inherent_rating": risk.inherent_rating,
            "org_unit_id": risk.org_unit_id,
        })  # fmt: skip
    shown.sort(key=lambda row: (row["status"] != "open", row["ref"]))
    return {"risks": shown, "hidden": hidden}


def _detail(session: Session, principal: Principal, objective: Objective) -> dict[str, Any]:
    return {
        "measure": objective.measure,
        "threatened_by": risks_of(session, principal, objective),
        "can": {
            "edit": can_edit(session, principal, objective),
            "assess": False,
        },
    }


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    status = filters.get("status")
    if status in OBJECTIVE_STATUSES:
        found.append(Objective.status == status)
    elif status != "all" and not filters.get("anywhere"):
        found.append(Objective.status != "retired")
    return found


OBJECTIVE = register(
    RecordType(
        KEY,
        Objective,
        "OBJ",
        "objectives",
        "objective",
        "objectives",
        is_thing=False,
        open=True,
        sorts=("updated_at", "name", "ref", "status"),
        filters=("status",),
        extra={
            "new": _new,
            "apply": _apply,
            "cards": _cards,
            "detail": _detail,
            "conditions": _conditions,
            "can_add": can_add,
            "can_edit": can_edit,
            "add_refusal": "Objectives are set by a unit's leaders, or by a manager.",
            "live_statuses": ("active",),
            "history_labels": {"period": "Period", "measure": "How it is known to be met"},
        },
    )
)


# --- From the risk's side -------------------------------------------------------------------


def objectives_of(session: Session, principal: Principal, risk: Risk) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Objective)
        .join(RiskObjective, RiskObjective.objective_id == Objective.id)
        .where(RiskObjective.risk_id == risk.id)
        .order_by(Objective.ref)
    ).all()
    return [
        {**records.chip(OBJECTIVE, row), "status": row.status}
        for row in rows
        if access.can_see(session, principal, OBJECTIVE, row)
    ]


def set_objectives(session: Session, principal: Principal, risk: Risk, refs: list[str]) -> None:
    """Say every objective the risk threatens, by reference."""
    from riskwren.risk.register import RISK

    if not access.can_edit(session, principal, RISK, risk):
        raise PermissionDenied("You cannot edit this risk.")
    errors = records.Errors()
    wanted: dict[int, Objective] = {}
    for ref in dict.fromkeys(str(each).strip().upper() for each in refs):
        try:
            objective = find(session, OBJECTIVE, ref)
        except NotFound as missing:
            errors.add("objectives", str(missing))
            continue
        if objective.status == "retired":
            errors.add("objectives", f"{objective.ref} is retired.")
            continue
        wanted[objective.id] = objective
    if errors:
        raise Invalid("The objectives were not changed.", errors)
    have = {
        row.objective_id: row
        for row in session.scalars(select(RiskObjective).where(RiskObjective.risk_id == risk.id))
    }
    with audit.operation(session, "risk.objectives"):
        for objective_id, row in have.items():
            if objective_id not in wanted:
                session.delete(row)
        for objective_id in wanted:
            if objective_id not in have:
                session.add(RiskObjective(risk_id=risk.id, objective_id=objective_id))
        records.touch(session, risk)
        session.flush()


def counts(session: Session) -> dict[int, int]:
    """How many open risks name each objective."""
    return dict(
        session.execute(
            select(RiskObjective.objective_id, func.count())
            .join(Risk, Risk.id == RiskObjective.risk_id)
            .where(Risk.status == "open")
            .group_by(RiskObjective.objective_id)
        ).all()
    )
