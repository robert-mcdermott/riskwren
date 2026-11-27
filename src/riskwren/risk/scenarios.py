"""Scenarios (RSK-18): what might happen, told on purpose, and what was concluded.

A scenario describes something that could happen ("ransomware takes research computing down
for two weeks"), what it assumes, the risks and processes it would touch, and, once it has
been worked through, what was concluded. It is a record of its own, kept by those who keep
risks in its unit and by assessors and managers, who work through scenarios with them.

Where the risks it touches have estimates in ranges, the scenario shows what a simulation of
them together comes to, with what it assumes, and which of its risks have no estimate.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid, NotFound, PermissionDenied
from riskwren.db.models import Risk, Scenario, ScenarioSubject
from riskwren.db.models.scenarios import SCENARIO_STATUSES
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.registry import PROCESS, RecordType, find_any, register
from riskwren.risk import estimates, simulation

KEY = "scenario"


def can_add(principal: Principal, org_unit_id: int | None) -> bool:
    return (
        principal.stewards_unit(org_unit_id)
        or principal.leads_unit(org_unit_id)
        or principal.assesses_unit(org_unit_id)
    )


def can_edit(session: Session, principal: Principal, scenario: Scenario) -> bool:
    if can_add(principal, scenario.org_unit_id):
        return True
    kinds = access.owner_kinds(session, SCENARIO, scenario.id, principal.account_id)
    return bool(kinds & set(access.EDITING_KINDS))


def _new(scenario: Scenario) -> None:
    scenario.status = "draft"


def _apply(
    session: Session, scenario: Scenario, values: Mapping[str, Any], errors: records.Errors,
    creating: bool,
) -> None:  # fmt: skip
    if "assumptions" in values:
        scenario.assumptions = records.text(values.get("assumptions"))
    if "conclusion" in values:
        scenario.conclusion = records.text(values.get("conclusion"))
    status = values.get("status")
    if status is not None:
        if status not in SCENARIO_STATUSES:
            errors.add("status", "Use draft, concluded, or retired.")
        elif status == "concluded" and not (
            records.text(values.get("conclusion")) or scenario.conclusion
        ):
            errors.add("conclusion", "Say what was concluded.")
        else:
            if status == "concluded" and scenario.status != "concluded":
                scenario.concluded_on = utc_now().date()
            elif status == "draft":
                scenario.concluded_on = None
            scenario.status = status


def _history_title(event: Any, lookups: Any) -> str | None:
    if event.subject_type != "scenario_subject":
        return None
    changes = event.changes or {}

    def now(field: str) -> Any:
        pair = changes.get(field) or [None, None]
        return pair[1] if pair[1] is not None else pair[0]

    name = lookups.name(now("subject_type"), now("subject_id"))
    return f"Now touches {name}" if event.action == "created" else f"No longer touches {name}"


def _subject_rows(session: Session, ids: list[int]) -> dict[int, list[ScenarioSubject]]:
    found: dict[int, list[ScenarioSubject]] = {each: [] for each in ids}
    for row in session.scalars(
        select(ScenarioSubject)
        .where(ScenarioSubject.scenario_id.in_(ids or [0]))
        .order_by(ScenarioSubject.id)
    ):
        found[row.scenario_id].append(row)
    return found


def _cards(session: Session, rows: list[Scenario]) -> list[dict[str, Any]]:
    subjects = _subject_rows(session, [row.id for row in rows])
    return [
        {
            "status": row.status,
            "concluded_on": row.concluded_on,
            "risks": sum(1 for each in subjects[row.id] if each.subject_type == "risk"),
            "processes": sum(1 for each in subjects[row.id] if each.subject_type == "process"),
        }
        for row in rows
    ]


def subjects_of(session: Session, principal: Principal, scenario: Scenario) -> dict[str, Any]:
    """The risks and processes the scenario touches, as much as the person may see, each risk
    with its rating and whether it has an estimate."""
    from riskwren.risk.register import RISK

    risks, processes, hidden = [], [], 0
    for row in _subject_rows(session, [scenario.id])[scenario.id]:
        record_type = RISK if row.subject_type == "risk" else PROCESS
        record = session.get(record_type.model, row.subject_id)
        if record is None:
            continue
        if not access.can_see(session, principal, record_type, record):
            hidden += 1
            continue
        chip = records.chip(record_type, record)
        if row.subject_type == "risk":
            estimate = estimates.current(session, record.id)
            risks.append({**chip, "status": record.status, "standing": record.standing,
                          "residual_rating": record.residual_rating,
                          "estimated": estimate is not None})  # fmt: skip
        else:
            processes.append({**chip, "criticality": record.criticality})
    return {"risks": risks, "processes": processes, "hidden": hidden}


def simulate(session: Session, principal: Principal, scenario: Scenario) -> dict[str, Any] | None:
    """What the estimates of the scenario's risks come to together, if any have one."""
    touched = subjects_of(session, principal, scenario)
    inputs = []
    for chip in touched["risks"]:
        risk = session.scalars(select(Risk).where(Risk.ref == chip["ref"])).one()
        estimate = estimates.current(session, risk.id)
        if estimate is not None:
            inputs.append((estimate.currency, estimates.inputs(risk, estimate)))
    if not inputs:
        return None
    currencies = {currency for currency, _ in inputs}
    if len(currencies) > 1:
        return {
            "refused": "Its risks are estimated in different currencies, so they are not added up."
        }
    result = simulation.run([each for _, each in inputs])
    return {
        **result,
        "currency": currencies.pop(),
        "included": [each.label for _, each in inputs],
        "without": [chip["ref"] for chip in touched["risks"] if not chip["estimated"]],
    }


def _detail(session: Session, principal: Principal, scenario: Scenario) -> dict[str, Any]:
    return {
        "assumptions": scenario.assumptions,
        "conclusion": scenario.conclusion,
        "touches": subjects_of(session, principal, scenario),
        "simulation": simulate(session, principal, scenario),
        "can": {"edit": can_edit(session, principal, scenario)},
    }


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    status = filters.get("status")
    if status in SCENARIO_STATUSES:
        found.append(Scenario.status == status)
    elif status != "all" and not filters.get("anywhere"):
        found.append(Scenario.status != "retired")
    if filters.get("risk"):
        try:
            record_type, record = find_any(session, str(filters["risk"]))
        except NotFound:
            return [Scenario.id < 0]
        found.append(
            Scenario.id.in_(
                select(ScenarioSubject.scenario_id).where(
                    ScenarioSubject.subject_type == record_type.key,
                    ScenarioSubject.subject_id == record.id,
                )
            )
        )
    return found


SCENARIO = register(
    RecordType(
        KEY,
        Scenario,
        "SCN",
        "scenarios",
        "scenario",
        "scenarios",
        is_thing=False,
        open=True,
        sorts=("updated_at", "name", "ref", "status"),
        filters=(),
        extra={
            "new": _new,
            "apply": _apply,
            "cards": _cards,
            "detail": _detail,
            "conditions": _conditions,
            "can_add": can_add,
            "can_edit": can_edit,
            "add_refusal": "Scenarios are kept by a unit's stewards and leaders, and by "
            "assessors and managers.",
            "live_statuses": ("draft", "concluded"),
            "history_title": _history_title,
            "history_labels": {
                "assumptions": "What it assumes",
                "conclusion": "What was concluded",
                "concluded_on": "Concluded on",
            },
        },
    )
)


def set_subjects(
    session: Session, principal: Principal, scenario: Scenario, refs: list[str]
) -> None:
    """Say every risk and process the scenario touches, by reference."""
    if not can_edit(session, principal, scenario):
        raise PermissionDenied("You cannot edit this scenario.")
    errors = records.Errors()
    wanted: dict[tuple[str, int], Any] = {}
    for ref in dict.fromkeys(str(each).strip().upper() for each in refs):
        try:
            record_type, record = find_any(session, ref)
        except NotFound as missing:
            errors.add("subjects", str(missing))
            continue
        if record_type.key not in ("risk", "process") or not access.can_see(
            session, principal, record_type, record
        ):
            errors.add("subjects", f"{ref} is not a risk or a process you can see.")
            continue
        wanted[(record_type.key, record.id)] = record
    if errors:
        raise Invalid("What the scenario touches was not changed.", errors)
    have = {
        (row.subject_type, row.subject_id): row
        for row in session.scalars(
            select(ScenarioSubject).where(ScenarioSubject.scenario_id == scenario.id)
        )
    }
    with audit.operation(session, "scenario.subjects"):
        for key, row in have.items():
            if key not in wanted:
                session.delete(row)
        for kind, identifier in wanted:
            if (kind, identifier) not in have:
                session.add(
                    ScenarioSubject(
                        scenario_id=scenario.id, subject_type=kind, subject_id=identifier
                    )
                )
        records.touch(session, scenario)
        session.flush()


def of_risk(session: Session, principal: Principal, risk: Risk) -> list[dict[str, Any]]:
    """The scenarios that touch a risk."""
    rows = session.scalars(
        select(Scenario)
        .join(ScenarioSubject, ScenarioSubject.scenario_id == Scenario.id)
        .where(ScenarioSubject.subject_type == "risk", ScenarioSubject.subject_id == risk.id)
        .order_by(Scenario.ref)
    ).all()
    return [
        {**records.chip(SCENARIO, row), "status": row.status}
        for row in rows
        if access.can_see(session, principal, SCENARIO, row)
    ]
