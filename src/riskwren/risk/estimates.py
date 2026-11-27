"""Estimates in ranges (RSK-19): a risk in numbers, and what a simulation makes of them.

An estimate is optional, and it does not replace the rating: the rating on the program's
scales is what the register is run by. An estimate is for the risks worth putting a figure
on, by those who keep the risk. It is never edited; a new one supersedes the last, and all
are kept.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.db.models import Risk, RiskEstimate
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.risk import simulation

MOST_EVENTS = 365.0  # a year's rate above this is a different kind of risk
MOST_LOSS = 10**12


def current(session: Session, risk_id: int) -> RiskEstimate | None:
    return session.scalars(
        select(RiskEstimate)
        .where(RiskEstimate.risk_id == risk_id, RiskEstimate.superseded_by.is_(None))
        .order_by(RiskEstimate.id.desc())
        .limit(1)
    ).first()


def inputs(risk: Risk, estimate: RiskEstimate) -> simulation.Inputs:
    return simulation.Inputs(
        risk.ref,
        simulation.Range(
            estimate.frequency_low, estimate.frequency_likely, estimate.frequency_high
        ),
        simulation.Range(estimate.loss_low, estimate.loss_likely, estimate.loss_high),
    )


def _number(values: Mapping[str, Any], key: str, errors: records.Errors) -> float | None:
    value = values.get(key)
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        errors.add(key, "Give a number.")
        return None
    if math_bad(number):
        errors.add(key, "Give a number.")
        return None
    return number


def math_bad(number: float) -> bool:
    return number != number or number in (float("inf"), float("-inf"))


def _range(
    values: Mapping[str, Any], name: str, errors: records.Errors, *, most: float
) -> tuple[float, float, float] | None:
    low, likely, high = (_number(values, f"{name}_{part}", errors) for part in
                         ("low", "likely", "high"))  # fmt: skip
    if low is None or likely is None or high is None:
        return None
    if low < 0:
        errors.add(f"{name}_low", "It cannot be below nothing.")
    elif not low <= likely <= high:
        errors.add(f"{name}_likely", "Low, likely, and high must be in that order.")
    elif high > most:
        errors.add(f"{name}_high", f"At most {most:,.0f}.")
    return low, likely, high


def record(
    session: Session, principal: Principal, risk: Risk, values: Mapping[str, Any]
) -> RiskEstimate:
    """Put numbers to a risk, superseding its last estimate."""
    from riskwren.risk.register import RISK

    if not access.can_edit(session, principal, RISK, risk):
        raise PermissionDenied("Those who keep the risk estimate it.")
    errors = records.Errors()
    frequency = _range(values, "frequency", errors, most=MOST_EVENTS)
    loss = _range(values, "loss", errors, most=MOST_LOSS)
    assumptions = records.text(values.get("assumptions"))
    if not assumptions:
        errors.add("assumptions", "Say what the numbers assume: where they came from.")
    currency = str(values.get("currency") or "USD").upper()
    if len(currency) != 3 or not currency.isalpha():
        errors.add("currency", "A three-letter currency code, such as USD.")
    if errors or frequency is None or loss is None:
        raise Invalid("The estimate was not recorded.", errors)
    earlier = current(session, risk.id)
    with audit.operation(session, "risk.estimate"):
        estimate = RiskEstimate(
            risk_id=risk.id,
            frequency_low=frequency[0], frequency_likely=frequency[1], frequency_high=frequency[2],
            loss_low=round(loss[0]), loss_likely=round(loss[1]), loss_high=round(loss[2]),
            currency=currency, assumptions=assumptions, estimated_by=principal.account_id,
            estimated_by_name=principal.name, estimated_at=utc_now(),
        )  # fmt: skip
        session.add(estimate)
        session.flush()
        if earlier is not None:
            earlier.superseded_by = estimate.id
        records.touch(session, risk)
    return estimate


def _row(estimate: RiskEstimate) -> dict[str, Any]:
    return {
        "id": estimate.id,
        "frequency": {"low": estimate.frequency_low, "likely": estimate.frequency_likely,
                      "high": estimate.frequency_high},
        "loss": {"low": estimate.loss_low, "likely": estimate.loss_likely,
                 "high": estimate.loss_high},
        "currency": estimate.currency,
        "assumptions": estimate.assumptions,
        "estimated_by": estimate.estimated_by_name,
        "estimated_at": estimate.estimated_at,
        "superseded": estimate.superseded_by is not None,
    }  # fmt: skip


def view(session: Session, principal: Principal, risk: Risk) -> dict[str, Any]:
    """The risk's estimate, what a simulation makes of it, and the estimates before it."""
    from riskwren.risk.register import RISK

    rows = session.scalars(
        select(RiskEstimate).where(RiskEstimate.risk_id == risk.id).order_by(RiskEstimate.id.desc())
    ).all()
    now = next((row for row in rows if row.superseded_by is None), None)
    return {
        "estimate": _row(now) if now else None,
        "simulation": simulation.run([inputs(risk, now)]) if now else None,
        "earlier": [_row(row) for row in rows if row is not now],
        "can_estimate": access.can_edit(session, principal, RISK, risk),
    }
