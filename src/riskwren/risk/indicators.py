"""Indicators: early warning (RSK-13).

An indicator is a number someone reads on a schedule: failed sign-ins a week, days to patch,
staff who have not done their training. It has a level at which it should worry people and
a level at which it has gone too far. It is linked to the risks it warns of. When a reading
crosses the second level, the people who own the indicator and those risks are told, and
the risks are flagged so that someone looks at their rating again.

RiskWren is passive: it never reads the number itself. A person records it here.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.db.models import Indicator, IndicatorReading, IndicatorRisk, Risk
from riskwren.db.models.indicators import INDICATOR_DIRECTIONS, INDICATOR_FREQUENCIES
from riskwren.db.models.inventory import RECORD_STATUSES
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.completeness import Expected
from riskwren.inventory.registry import RecordType, find, register
from riskwren.people import notices

EVERY = {"weekly": 7, "monthly": 31, "quarterly": 92, "annually": 366}
KEPT = 60  # readings shown on an indicator's page
WORDS = {"ok": "within its limits", "warn": "past its warning level", "breach": "past its limit"}


# --- What a reading means -------------------------------------------------------------------


def state_for(indicator: Indicator, value: float | None) -> str:
    """ok, warn, or breach: how a value stands against the indicator's levels."""
    if value is None:
        return "no_reading"
    worse = (lambda level: value >= level) if indicator.direction == "up" else (
        lambda level: value <= level
    )  # fmt: skip
    if worse(indicator.breach_at):
        return "breach"
    if indicator.warn_at is not None and worse(indicator.warn_at):
        return "warn"
    return "ok"


def next_due(indicator: Indicator) -> date | None:
    """When the next reading is due: one period after the last, or after it was set up."""
    if indicator.status != "active":
        return None
    since = indicator.last_read_on or indicator.created_at.date()
    return since + timedelta(days=EVERY[indicator.frequency])


def trend(indicator: Indicator, values: list[float]) -> str:
    """worse, better, or steady, from the newest readings (newest last). A move of less than
    a twentieth of the distance to the limit is steady."""
    if len(values) < 2:
        return "steady"
    before = values[-3:-1] if len(values) >= 3 else values[-2:-1]
    change = values[-1] - sum(before) / len(before)
    scale = abs(indicator.breach_at - (indicator.warn_at or 0)) or abs(indicator.breach_at) or 1
    if abs(change) < scale / 20:
        return "steady"
    return "worse" if (change > 0) == (indicator.direction == "up") else "better"


def _number(value: Any, field: str, errors: records.Errors, *, required: bool = False) -> Any:
    if value is None or value == "":
        if required:
            errors.add(field, "Give a number.")
        return None
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        errors.add(field, "Give a number.")
        return None
    try:
        number = float(value)
    except ValueError:
        errors.add(field, "Give a number.")
        return None
    if number != number or number in (float("inf"), float("-inf")):
        errors.add(field, "Give a number.")
        return None
    return number


# --- The record -----------------------------------------------------------------------------


def _new(indicator: Indicator) -> None:
    indicator.status, indicator.direction, indicator.frequency = "active", "up", "monthly"
    indicator.state = "no_reading"


def _apply(
    session: Session, indicator: Indicator, values: Mapping[str, Any], errors: records.Errors,
    creating: bool,
) -> None:  # fmt: skip
    if "measure" in values:
        indicator.measure = (records.text(values["measure"]) or "")[:40] or None
    if "source" in values:
        indicator.source = records.text(values["source"])
    if values.get("direction") is not None:
        if values["direction"] not in INDICATOR_DIRECTIONS:
            errors.add("direction", "Say whether higher or lower is worse.")
        else:
            indicator.direction = values["direction"]
    if values.get("frequency") is not None:
        if values["frequency"] not in INDICATOR_FREQUENCIES:
            errors.add("frequency", f"Use one of: {', '.join(INDICATOR_FREQUENCIES)}.")
        else:
            indicator.frequency = values["frequency"]
    if values.get("status") is not None:
        if values["status"] not in RECORD_STATUSES:
            errors.add("status", "Use active or retired.")
        else:
            indicator.status = values["status"]
    if "breach_at" in values or creating:
        limit = _number(values.get("breach_at"), "breach_at", errors, required=True)
        if limit is not None:
            indicator.breach_at = limit
    if "warn_at" in values:
        indicator.warn_at = _number(values["warn_at"], "warn_at", errors)
    if (
        indicator.warn_at is not None
        and indicator.breach_at is not None
        and "warn_at" not in errors
        and "breach_at" not in errors
    ):
        up = indicator.direction == "up"
        if (up and indicator.warn_at >= indicator.breach_at) or (
            not up and indicator.warn_at <= indicator.breach_at
        ):
            side = "below" if up else "above"
            errors.add("warn_at", f"The warning level comes first: {side} the limit.")
    if not errors and not creating:
        # New levels are applied to the reading already on record.
        indicator.state = state_for(indicator, indicator.last_value)


def _view(indicator: Indicator, today: date) -> dict[str, Any]:
    due = next_due(indicator)
    return {
        "status": indicator.status,
        "measure": indicator.measure,
        "direction": indicator.direction,
        "warn_at": indicator.warn_at,
        "breach_at": indicator.breach_at,
        "frequency": indicator.frequency,
        "state": indicator.state,
        "last_value": indicator.last_value,
        "last_read_on": indicator.last_read_on,
        "next_due": due,
        "reading_overdue": bool(due and due < today),
    }


def _cards(session: Session, rows: list[Indicator]) -> list[dict[str, Any]]:
    today = utc_now().date()
    counts = dict(
        session.execute(
            select(IndicatorRisk.indicator_id, func.count())
            .where(IndicatorRisk.indicator_id.in_([row.id for row in rows] or [0]))
            .group_by(IndicatorRisk.indicator_id)
        ).all()
    )
    return [{**_view(row, today), "risks": counts.get(row.id, 0)} for row in rows]


def readings_of(
    session: Session, indicator: Indicator, limit: int = KEPT
) -> list[IndicatorReading]:
    """The newest readings, oldest first."""
    rows = session.scalars(
        select(IndicatorReading)
        .where(IndicatorReading.indicator_id == indicator.id)
        .order_by(IndicatorReading.read_on.desc())
        .limit(limit)
    ).all()
    return list(reversed(rows))


def risks_of(session: Session, principal: Principal, indicator: Indicator) -> list[dict[str, Any]]:
    """The risks it warns of, as far as the reader may see them."""
    from riskwren.risk.register import RISK

    rows = session.scalars(
        select(Risk)
        .join(IndicatorRisk, IndicatorRisk.risk_id == Risk.id)
        .where(IndicatorRisk.indicator_id == indicator.id)
        .order_by(Risk.ref)
    ).all()
    return [
        {"ref": risk.ref, "name": risk.name, "standing": risk.standing, "status": risk.status}
        for risk in rows
        if access.can_see(session, principal, RISK, risk)
    ]


def _detail(session: Session, principal: Principal, indicator: Indicator) -> dict[str, Any]:
    rows = readings_of(session, indicator)
    return {
        **_view(indicator, utc_now().date()),
        "source": indicator.source,
        "trend": trend(indicator, [row.value for row in rows]),
        "readings": [
            {
                "read_on": row.read_on,
                "value": row.value,
                "note": row.note,
                "by": row.entered_by_name,
                "state": state_for(indicator, row.value),
            }
            for row in rows
        ],
        "risks": risks_of(session, principal, indicator),
        "can_read": indicator.status == "active"
        and access.can_edit(session, principal, INDICATOR, indicator),
    }


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    if filters.get("state") in ("ok", "warn", "breach", "no_reading"):
        found.append(Indicator.state == filters["state"])
    if filters.get("status") in RECORD_STATUSES:
        found.append(Indicator.status == filters["status"])
    if filters.get("risk"):
        found.append(
            exists(
                select(IndicatorRisk.id)
                .join(Risk, Risk.id == IndicatorRisk.risk_id)
                .where(
                    IndicatorRisk.indicator_id == Indicator.id,
                    Risk.ref == str(filters["risk"]).strip().upper(),
                )
            )
        )
    return found


def _history_title(event: Any, lookups: Any) -> str | None:
    """A reading and a linked risk, said in the indicator's own history as what they are."""
    changes = event.changes or {}
    if event.subject_type == "indicator_reading":
        value = (changes.get("value") or [None, None])[1]
        day = (changes.get("read_on") or [None, None])[1]
        if event.action == "created":
            return f"Recorded a reading of {value:g}" + (f" for {day}" if day else "")
        return f"Corrected a reading to {value:g}" if value is not None else "Corrected a reading"
    if event.subject_type == "indicator_risk":
        return "Linked a risk it warns of" if event.action == "created" else "Unlinked a risk"
    return None


def _warns_of_nothing(model: Any) -> Any:
    return ~exists(select(IndicatorRisk.id).where(IndicatorRisk.indicator_id == model.id))


INDICATOR: RecordType = register(
    RecordType(
        "indicator",
        Indicator,
        "IND",
        "indicators",
        "indicator",
        "indicators",
        is_thing=False,
        sorts=("updated_at", "name", "ref", "state", "last_read_on"),
        filters=("status", "state"),
        extra={
            "expected": [
                Expected(
                    "reading",
                    "a reading",
                    lambda model: model.state == "no_reading",
                    "It has never been read, so it warns of nothing.",
                ),
                Expected(
                    "risks",
                    "a risk it warns of",
                    _warns_of_nothing,
                    "A breach would reach nobody but its own owners.",
                ),
                Expected(
                    "source",
                    "where it is read from",
                    lambda model: model.source.is_(None),
                    "Whoever reads it next may read something else.",
                ),
            ],
            "new": _new,
            "apply": _apply,
            "cards": _cards,
            "detail": _detail,
            "conditions": _conditions,
            "history_title": _history_title,
            "history_keeps_titled": True,  # a corrected reading is worth saying
            "history_labels": {
                "measure": "Counted in",
                "direction": "Which way is worse",
                "warn_at": "Warning level",
                "breach_at": "Limit",
                "frequency": "Read",
                "source": "Read from",
            },
            "history_quiet": ("last_value", "last_read_on", "state"),
        },
    )
)


# --- Readings -------------------------------------------------------------------------------


def _say(indicator: Indicator, value: float) -> str:
    amount = f"{value:g}{'' if not indicator.measure else ' ' + indicator.measure}"
    limit = f"{indicator.breach_at:g}"
    return f"{indicator.ref} {indicator.name} is at {amount}, past its limit of {limit}"


def record_reading(
    session: Session,
    principal: Principal,
    indicator: Indicator,
    *,
    value: Any,
    read_on: Any = None,
    note: str | None = None,
) -> IndicatorReading:
    """Record what the indicator stood at on a day. A second reading for the same day
    corrects the first. If the newest reading takes it past its limit, those who answer for
    it and for the risks it warns of are told, and those risks are flagged."""
    if not access.can_edit(session, principal, INDICATOR, indicator):
        raise PermissionDenied(
            "A reading is recorded by the indicator's owners, or the unit's steward or manager."
        )
    errors = records.Errors()
    if indicator.status != "active":
        errors.add("value", "This indicator is retired, and takes no more readings.")
    number = _number(value, "value", errors, required=True)
    today = utc_now().date()
    day = today
    if read_on not in (None, ""):
        try:
            day = read_on if isinstance(read_on, date) else date.fromisoformat(str(read_on))
        except ValueError:
            errors.add("read_on", "Give the day it was read.")
    if day > today:
        errors.add("read_on", "A reading cannot be from the future.")
    if errors:
        raise Invalid("The reading was not recorded.", errors)
    was = indicator.state
    with audit.operation(session, "indicator.reading"):
        row = session.scalars(
            select(IndicatorReading).where(
                IndicatorReading.indicator_id == indicator.id, IndicatorReading.read_on == day
            )
        ).first()
        if row is None:
            row = IndicatorReading(indicator_id=indicator.id, read_on=day, created_at=utc_now())
            session.add(row)
        row.value, row.note = number, records.text(note)
        row.entered_by, row.entered_by_name = principal.account_id, principal.name
        session.flush()
        newest = session.scalars(
            select(IndicatorReading)
            .where(IndicatorReading.indicator_id == indicator.id)
            .order_by(IndicatorReading.read_on.desc())
        ).first()
        assert newest is not None
        indicator.last_value, indicator.last_read_on = newest.value, newest.read_on
        indicator.state = state_for(indicator, newest.value)
        indicator.updated_at = utc_now()
        session.flush()
        if indicator.state == "breach" and was != "breach":
            _breached(session, principal, indicator, newest.value)
    return row


def _breached(session: Session, principal: Principal, indicator: Indicator, value: float) -> None:
    """Tell whoever answers for the indicator and for the risks it warns of, and put those
    risks' ratings in doubt: something they were judged on has changed."""
    text = _say(indicator, value)
    href = f"/indicators/{indicator.ref}"
    people = list(notices.owners(session, "indicator", indicator.id))
    for risk in session.scalars(
        select(Risk)
        .join(IndicatorRisk, IndicatorRisk.risk_id == Risk.id)
        .where(IndicatorRisk.indicator_id == indicator.id, Risk.status == "open")
    ):
        people += notices.owners(session, "risk", risk.id)
        if risk.standing != "not_assessed" and not risk.residual_in_doubt:
            risk.residual_in_doubt = True
            risk.residual_doubt_reason = f"{text}. Look at whether the residual rating still holds."
    notices.tell_all(session, people, "indicator", text, href, by=principal)
    session.flush()


def set_risks(
    session: Session, principal: Principal, indicator: Indicator, refs: list[str]
) -> None:
    """Say which risks the indicator warns of. They must be risks the person may see."""
    from riskwren.risk.register import RISK

    if not access.can_edit(session, principal, INDICATOR, indicator):
        raise PermissionDenied("The indicator's owners, or the unit's steward, link its risks.")
    wanted: dict[int, Risk] = {}
    for ref in dict.fromkeys(str(each).strip().upper() for each in refs if str(each).strip()):
        risk = records.load(session, principal, RISK, ref)
        wanted[risk.id] = risk
    have = {
        row.risk_id: row
        for row in session.scalars(
            select(IndicatorRisk).where(IndicatorRisk.indicator_id == indicator.id)
        )
    }
    with audit.operation(session, "indicator.risks"):
        for risk_id, row in have.items():
            if risk_id not in wanted:
                session.delete(row)
        for risk_id in wanted:
            if risk_id not in have:
                session.add(IndicatorRisk(indicator_id=indicator.id, risk_id=risk_id))
        session.flush()


def of_risk(session: Session, principal: Principal, risk: Risk) -> list[dict[str, Any]]:
    """The indicators that warn of a risk, with where each stands."""
    today = utc_now().date()
    rows = session.scalars(
        select(Indicator)
        .join(IndicatorRisk, IndicatorRisk.indicator_id == Indicator.id)
        .where(IndicatorRisk.risk_id == risk.id, Indicator.status == "active")
        .order_by(Indicator.ref)
    ).all()
    out = []
    for row in rows:
        if not access.can_see(session, principal, INDICATOR, row):
            continue
        values = [reading.value for reading in readings_of(session, row, 12)]
        out.append({"ref": row.ref, "name": row.name, **_view(row, today),
                    "trend": trend(row, values), "values": values})  # fmt: skip
    return out


def due(session: Session, principal: Principal) -> list[Indicator]:
    """Indicators this person owns whose next reading is due."""
    if principal.account_id is None:
        return []
    today = utc_now().date()
    mine = set(
        session.scalars(
            select(Indicator)
            .where(Indicator.status == "active")
            .where(Indicator.id.in_(_owned(principal.account_id)))
        )
    )
    return sorted(
        (row for row in mine if (when := next_due(row)) is not None and when <= today),
        key=lambda row: next_due(row) or today,
    )


def _owned(account_id: int) -> Any:
    from riskwren.db.models import RecordOwner

    return select(RecordOwner.record_id).where(
        RecordOwner.record_type == "indicator", RecordOwner.account_id == account_id
    )


def breached(session: Session, principal: Principal) -> int:
    """How many active indicators the person may see are past their limit."""
    visible = access.visible(session, principal, INDICATOR)
    query = select(func.count()).select_from(Indicator).where(
        Indicator.status == "active", Indicator.state == "breach"
    )  # fmt: skip
    if visible is not None:
        query = query.where(visible)
    return int(session.execute(query).scalar_one())


__all__ = ["INDICATOR", "find", "record_reading", "set_risks"]
