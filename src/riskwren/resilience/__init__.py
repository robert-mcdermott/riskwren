"""Resilience (RES): what each process cannot afford to lose, and whether what it relies on
can deliver it.

A **business impact analysis** says, for one process, how much its loss hurts as time goes
on, how soon it must be back (its recovery time), how much information it can afford to lose
(its recovery point), and the least it needs to run. It is a judgment by a named person,
never edited: a new one supersedes it, and every one is kept.

A **recovery capability** says what a system or a service can actually be restored within,
and how much information it can lose, with what that rests on: a tested restore, a contract,
a design. The check reads each process's analysis against the capabilities of the systems and
services it relies on, and lists every shortfall: a dependency that cannot be back in time,
that would lose more than the process can afford, or whose capability nobody has said.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.db.models import (
    ImpactAnalysis,
    Process,
    RecordLink,
    RecoveryCapability,
    Service,
    System,
)
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.registry import PROCESS, TYPES

AFTER = (("4h", "4 hours"), ("1d", "1 day"), ("3d", "3 days"), ("1w", "1 week"), ("1m", "1 month"))
LEVELS = ((1, "Negligible"), (2, "Minor"), (3, "Moderate"), (4, "Major"), (5, "Severe"))
MOST_HOURS = 24 * 365
MODELS: dict[str, Any] = {"system": System, "service": Service}


def _hours(values: Mapping[str, Any], key: str, errors: records.Errors) -> int | None:
    try:
        hours = int(values.get(key))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        errors.add(key, "Give a whole number of hours.")
        return None
    if not 0 <= hours <= MOST_HOURS:
        errors.add(key, "From 0 hours to a year.")
        return None
    return hours


def current_analysis(session: Session, process_id: int) -> ImpactAnalysis | None:
    return session.scalars(
        select(ImpactAnalysis)
        .where(ImpactAnalysis.process_id == process_id, ImpactAnalysis.superseded_by.is_(None))
        .order_by(ImpactAnalysis.id.desc())
        .limit(1)
    ).first()


def current_capability(session: Session, kind: str, subject_id: int) -> RecoveryCapability | None:
    return session.scalars(
        select(RecoveryCapability)
        .where(
            RecoveryCapability.subject_type == kind,
            RecoveryCapability.subject_id == subject_id,
            RecoveryCapability.superseded_by.is_(None),
        )
        .order_by(RecoveryCapability.id.desc())
        .limit(1)
    ).first()


def analyse(
    session: Session, principal: Principal, process: Process, values: Mapping[str, Any]
) -> ImpactAnalysis:
    """Record a business impact analysis of a process, superseding the last."""
    if not access.can_edit(session, principal, PROCESS, process):
        raise PermissionDenied("Those who keep the process analyse it.")
    errors = records.Errors()
    known = {key for key, _ in AFTER}
    levels = {level for level, _ in LEVELS}
    impacts = []
    for row in values.get("impacts") or []:
        after, level = (row or {}).get("after"), (row or {}).get("level")
        if after not in known or level not in levels:
            errors.add("impacts", "Each impact is a time and a level from 1 to 5.")
            break
        impacts.append({"after": after, "level": int(level)})
    order = [key for key, _ in AFTER]
    impacts.sort(key=lambda row: order.index(row["after"]))
    if [row["level"] for row in impacts] != sorted(row["level"] for row in impacts):
        errors.add("impacts", "A loss hurts no less as time goes on.")
    recovery = _hours(values, "recovery_hours", errors)
    loss = _hours(values, "data_loss_hours", errors)
    if errors or recovery is None or loss is None:
        raise Invalid("The analysis was not recorded.", errors)
    earlier = current_analysis(session, process.id)
    with audit.operation(session, "process.impact"):
        analysis = ImpactAnalysis(
            process_id=process.id,
            impacts=impacts,
            recovery_hours=recovery,
            data_loss_hours=loss,
            minimum=records.text(values.get("minimum")),
            note=records.text(values.get("note")),
            analysed_by=principal.account_id,
            analysed_by_name=principal.name,
            analysed_at=utc_now(),
        )
        session.add(analysis)
        session.flush()
        if earlier is not None:
            earlier.superseded_by = analysis.id
        records.touch(session, process)
    return analysis


def record_capability(
    session: Session, principal: Principal, kind: str, subject: Any, values: Mapping[str, Any]
) -> RecoveryCapability:
    """Say what a system or service can be restored within, superseding what was said."""
    if not access.can_edit(session, principal, TYPES[kind], subject):
        raise PermissionDenied(f"Those who keep the {TYPES[kind].label.lower()} say this.")
    errors = records.Errors()
    recovery = _hours(values, "recovery_hours", errors)
    loss = _hours(values, "data_loss_hours", errors)
    basis = records.text(values.get("basis"))
    if not basis:
        errors.add("basis", "Say what it rests on: a tested restore, a contract, a design.")
    if errors or recovery is None or loss is None:
        raise Invalid("The capability was not recorded.", errors)
    earlier = current_capability(session, kind, subject.id)
    with audit.operation(session, f"{kind}.recovery"):
        capability = RecoveryCapability(
            subject_type=kind,
            subject_id=subject.id,
            recovery_hours=recovery,
            data_loss_hours=loss,
            basis=str(basis),
            recorded_by=principal.account_id,
            recorded_by_name=principal.name,
            recorded_at=utc_now(),
        )
        session.add(capability)
        session.flush()
        if earlier is not None:
            earlier.superseded_by = capability.id
        records.touch(session, subject)
    return capability


def _capability_view(row: RecoveryCapability | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "recovery_hours": row.recovery_hours,
        "data_loss_hours": row.data_loss_hours,
        "basis": row.basis,
        "recorded_by": row.recorded_by_name,
        "recorded_at": row.recorded_at,
    }


def dependencies(session: Session, process: Process) -> list[tuple[str, Any]]:
    """The systems and services the process relies on."""
    found: list[tuple[str, Any]] = []
    for link in session.scalars(
        select(RecordLink).where(
            RecordLink.from_type == "process",
            RecordLink.from_id == process.id,
            RecordLink.relation == "relies_on",
        )
    ):
        model = MODELS.get(link.to_type)
        thing = session.get(model, link.to_id) if model is not None else None
        if thing is not None and thing.status == "active":
            found.append((link.to_type, thing))
    return sorted(found, key=lambda pair: pair[1].ref)


def check(
    session: Session, process: Process, analysis: ImpactAnalysis | None
) -> list[dict[str, Any]]:
    """Each dependency against what the process needs: in time, within what may be lost,
    or not known."""
    out = []
    for kind, thing in dependencies(session, process):
        capability = current_capability(session, kind, thing.id)
        problems = []
        if analysis is not None:
            if capability is None:
                problems.append("Nobody has said what it can be restored within.")
            else:
                if capability.recovery_hours > analysis.recovery_hours:
                    problems.append(
                        f"It is back in {capability.recovery_hours} hours; the process needs "
                        f"it in {analysis.recovery_hours}."
                    )
                if capability.data_loss_hours > analysis.data_loss_hours:
                    problems.append(
                        f"It can lose {capability.data_loss_hours} hours of information; the "
                        f"process can afford {analysis.data_loss_hours}."
                    )
        out.append(
            {
                **records.chip(TYPES[kind], thing),
                "type": kind,
                "capability": _capability_view(capability),
                "problems": problems,
            }
        )
    return out


def _analysis_view(row: ImpactAnalysis) -> dict[str, Any]:
    return {
        "id": row.id,
        "impacts": row.impacts,
        "recovery_hours": row.recovery_hours,
        "data_loss_hours": row.data_loss_hours,
        "minimum": row.minimum,
        "note": row.note,
        "analysed_by": row.analysed_by_name,
        "analysed_at": row.analysed_at,
        "superseded": row.superseded_by is not None,
    }


def process_view(session: Session, principal: Principal, process: Process) -> dict[str, Any]:
    rows = session.scalars(
        select(ImpactAnalysis)
        .where(ImpactAnalysis.process_id == process.id)
        .order_by(ImpactAnalysis.id.desc())
    ).all()
    now = next((row for row in rows if row.superseded_by is None), None)
    found = check(session, process, now)
    return {
        "analysis": _analysis_view(now) if now else None,
        "earlier": [_analysis_view(row) for row in rows if row is not now],
        "dependencies": found,
        "shortfalls": sum(1 for each in found if each["problems"]),
        "after": dict(AFTER),
        "levels": dict(LEVELS),
        "can_analyse": access.can_edit(session, principal, PROCESS, process),
    }


def capability_view(
    session: Session, principal: Principal, kind: str, subject: Any
) -> dict[str, Any]:
    rows = session.scalars(
        select(RecoveryCapability)
        .where(RecoveryCapability.subject_type == kind, RecoveryCapability.subject_id == subject.id)
        .order_by(RecoveryCapability.id.desc())
    ).all()
    now = next((row for row in rows if row.superseded_by is None), None)
    relied = session.scalars(
        select(Process)
        .join(RecordLink, (RecordLink.from_type == "process") & (RecordLink.from_id == Process.id))
        .where(
            RecordLink.relation == "relies_on",
            RecordLink.to_type == kind,
            RecordLink.to_id == subject.id,
            Process.status == "active",
        )
        .order_by(Process.ref)
    ).all()
    needs = []
    for process in relied:
        analysis = current_analysis(session, process.id)
        needs.append(
            {
                **records.chip(PROCESS, process),
                "recovery_hours": analysis.recovery_hours if analysis else None,
                "data_loss_hours": analysis.data_loss_hours if analysis else None,
            }
        )
    return {
        "capability": _capability_view(now),
        "earlier": [_capability_view(row) for row in rows if row is not now],
        "needed_by": needs,
        "can_record": access.can_edit(session, principal, TYPES[kind], subject),
    }


def overview(session: Session, principal: Principal) -> dict[str, Any]:
    """Every process the person may see that has an analysis, most critical first, with its
    needs and its shortfalls; and how many have none."""
    rows, _ = records.search(session, principal, PROCESS, {"status": "active"}, limit=500)
    out, missing = [], 0
    for process in rows:
        analysis = current_analysis(session, process.id)
        if analysis is None:
            missing += 1
            continue
        found = check(session, process, analysis)
        out.append(
            {
                **records.chip(PROCESS, process),
                "criticality": process.criticality,
                "recovery_hours": analysis.recovery_hours,
                "data_loss_hours": analysis.data_loss_hours,
                "dependencies": len(found),
                "shortfalls": [each for each in found if each["problems"]],
            }
        )
    out.sort(key=lambda row: (-len(row["shortfalls"]), row["recovery_hours"], row["ref"]))
    return {"processes": out, "without": missing}


def _history_title(earlier: Any) -> Any:
    def title(event: Any, lookups: Any) -> str | None:
        changes = event.changes or {}

        def now(field: str) -> Any:
            pair = changes.get(field) or [None, None]
            return pair[1] if pair[1] is not None else pair[0]

        if event.subject_type == "impact_analysis":
            if event.action == "created":
                return (
                    f"Analysed its business impact: back within {now('recovery_hours')} hours, "
                    f"losing no more than {now('data_loss_hours')} hours of information"
                )
            return "An earlier analysis was superseded"
        if event.subject_type == "recovery_capability":
            if event.action == "created":
                return (
                    f"Said what it can deliver: back within {now('recovery_hours')} hours, "
                    f"losing up to {now('data_loss_hours')} hours of information"
                )
            return "What it can deliver was said again"
        return earlier(event, lookups) if earlier else None

    return title


def install() -> None:
    """Name analyses and capabilities in the histories of processes, systems, and services."""
    from riskwren.thirdparty.services import SERVICE

    for record_type in (PROCESS, TYPES["system"], SERVICE):
        if not record_type.extra.get("_resilience"):
            record_type.extra["history_title"] = _history_title(
                record_type.extra.get("history_title")
            )
            record_type.extra["_resilience"] = True


install()
