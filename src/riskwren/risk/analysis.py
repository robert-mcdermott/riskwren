"""Structured risk assessment over a scope (RSK-15).

A risk analysis takes what is in a scope, or what a unit holds, and a list of threats from
the risk library, and asks of each pair: does this apply here, and if it does, is there a
risk on the register for it? Each answer is one of three: it does not apply; an existing
risk covers it; a new risk is raised. When every pair has an answer the analysis can be
closed, and what it considered stays on record as its report.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    RecordOwner,
    Risk,
    RiskAnalysis,
    RiskAnalysisItem,
    RiskLibraryEntry,
    RiskSubject,
    ScopeMember,
)
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.registry import TYPES, RecordType, register
from riskwren.people import notices, units
from riskwren.risk import categories
from riskwren.risk import register as risks
from riskwren.risk.register import RISK

MOST = 1500  # pairs in one analysis: beyond this it is two exercises
OUTCOMES = {
    "not_applicable": "Does not apply",
    "covered": "Covered by a risk on the register",
    "raised": "A risk was raised",
}


def can_add(principal: Principal, org_unit_id: int | None) -> bool:
    """Started by whoever keeps the unit's records, or assesses it."""
    return access.can_add(principal, org_unit_id) or principal.assesses_unit(org_unit_id)


def _new(analysis: RiskAnalysis) -> None:
    analysis.status = "open"


def _apply(
    session: Session,
    analysis: RiskAnalysis,
    values: Mapping[str, Any],
    errors: records.Errors,
    creating: bool,
) -> None:
    if "conclusion" in values:
        analysis.conclusion = records.text(values["conclusion"])


def _things() -> list[RecordType]:
    return [each for each in TYPES.values() if each.is_thing]


def assets(
    session: Session, principal: Principal, *, scope: Any | None, unit: int | None
) -> list[tuple[RecordType, Any]]:
    """What an analysis would look at: what the scope names, or what the unit and the units
    beneath it hold, cut to what is in use and to what the person may see."""
    found: list[tuple[RecordType, Any]] = []
    if scope is not None:
        # A boundary names records, and units: a unit brings everything it and the units
        # beneath it hold.
        wanted: dict[str, set[int]] = defaultdict(set)
        for row in session.scalars(select(ScopeMember).where(ScopeMember.scope_id == scope.id)):
            wanted[row.subject_type].add(row.subject_id)
        within = units.with_descendants(session, wanted.pop("unit", set()))
        for record_type in _things():
            model: Any = record_type.model
            named = model.id.in_(wanted.get(record_type.key) or {0})
            held = model.org_unit_id.in_(within or {0})
            for row in session.scalars(
                select(model).where(named | held, model.status == "active").order_by(model.ref)
            ):
                if access.can_see(session, principal, record_type, row):
                    found.append((record_type, row))
        return found
    if unit is None:
        return found
    for record_type in _things():
        rows, _ = records.search(
            session, principal, record_type, {"unit": unit, "status": "active"},
            sort="ref", limit=MOST + 1,
        )  # fmt: skip
        found += [(record_type, row) for row in rows]
    return found


def threats(session: Session, values: Mapping[str, Any]) -> list[RiskLibraryEntry]:
    """The library risks to consider: those named, and every one in the categories named."""
    keys = [str(key) for key in values.get("threats") or []]
    tree = categories.Tree(session)
    for key in values.get("categories") or []:
        top = next((row for row in tree.rows if row.key == key), None)
        if top is None:
            raise Invalid(
                "The analysis was not started.", {"categories": f"There is no category {key!r}."}
            )
        within = {row.key for row in tree.rows if row.id in tree.with_descendants(top.id)}
        keys += list(
            session.scalars(
                select(RiskLibraryEntry.key)
                .where(RiskLibraryEntry.category_key.in_(within))
                .order_by(RiskLibraryEntry.id)
            )
        )
    keys = list(dict.fromkeys(keys))
    rows = {
        row.key: row
        for row in session.scalars(select(RiskLibraryEntry).where(RiskLibraryEntry.key.in_(keys)))
    }
    unknown = [key for key in keys if key not in rows]
    if unknown:
        raise Invalid(
            "The analysis was not started.",
            {"threats": f"There is no library risk {unknown[0]!r}."},
        )
    return [rows[key] for key in keys]


def _plan(
    session: Session, principal: Principal, values: Mapping[str, Any]
) -> tuple[Any | None, list[tuple[RecordType, Any]], list[RiskLibraryEntry]]:
    from riskwren.compliance.scopes import SCOPE  # it builds on the register

    errors: dict[str, str] = {}
    scope = None
    if values.get("scope"):
        try:
            scope = records.load(session, principal, SCOPE, str(values["scope"]))
        except NotFound:
            errors["scope"] = f"There is no scope {values['scope']}."
    unit = values.get("org_unit_id")
    wanted = threats(session, values)
    looked_at = assets(session, principal, scope=scope, unit=int(unit) if unit else None)
    if "scope" not in errors and not looked_at:
        errors["scope" if scope is not None else "org_unit_id"] = (
            "This scope names nothing in use to look at. Add what is in it first."
            if scope is not None
            else "This unit and those beneath it hold nothing in use to look at."
        )
    if not wanted:
        errors["threats"] = "Choose the threats to consider: library risks, or whole categories."
    if len(looked_at) * len(wanted) > MOST:
        errors["threats"] = (
            f"{len(looked_at)} things against {len(wanted)} threats is "
            f"{len(looked_at) * len(wanted)} questions. Keep an analysis under {MOST}: "
            "choose fewer threats, or a narrower scope."
        )
    if errors:
        raise Invalid("The analysis was not started.", errors)
    return scope, looked_at, wanted


def preview(session: Session, principal: Principal, values: Mapping[str, Any]) -> dict[str, int]:
    """How big an analysis would be, before it is started."""
    _, looked_at, wanted = _plan(session, principal, values)
    return {"assets": len(looked_at), "threats": len(wanted), "items": len(looked_at) * len(wanted)}


def start(session: Session, principal: Principal, values: Mapping[str, Any]) -> RiskAnalysis:
    """Start an analysis: one question for each thing against each threat."""
    scope, looked_at, wanted = _plan(session, principal, values)
    if scope is not None and not values.get("org_unit_id"):
        values = {**values, "org_unit_id": scope.org_unit_id}
    analysis: RiskAnalysis = records.create(session, principal, ANALYSIS, values)
    with audit.operation(session, "risk_analysis.start"):
        analysis.scope_id = scope.id if scope is not None else None
        for record_type, row in looked_at:
            for threat in wanted:
                session.add(
                    RiskAnalysisItem(
                        analysis_id=analysis.id, subject_type=record_type.key,
                        subject_id=row.id, subject_ref=row.ref, subject_name=row.name,
                        threat_key=threat.key, threat_title=threat.title, outcome="pending",
                    )
                )  # fmt: skip
        session.flush()
    return analysis


def _open(analysis: RiskAnalysis) -> None:
    if analysis.status != "open":
        raise Conflict("This analysis is closed. Reopen it to change what it found.")


def _may(session: Session, principal: Principal, analysis: RiskAnalysis) -> None:
    if not access.can_assess(session, principal, ANALYSIS, analysis):
        raise PermissionDenied(
            "An analysis is worked through by its owners, the unit's steward, a manager, or "
            "an assessor."
        )


def _subject(session: Session, item: RiskAnalysisItem) -> tuple[RecordType, Any] | None:
    record_type = TYPES.get(item.subject_type)
    row = session.get(record_type.model, item.subject_id) if record_type else None
    return (record_type, row) if record_type is not None and row is not None else None


def consider(
    session: Session,
    principal: Principal,
    analysis: RiskAnalysis,
    item: RiskAnalysisItem,
    values: Mapping[str, Any],
) -> RiskAnalysisItem:
    """Answer one question: the threat does not apply to the thing, a risk already on the
    register covers it, or a risk is raised for it now."""
    _may(session, principal, analysis)
    _open(analysis)
    outcome = str(values.get("outcome") or "")
    note = records.text(values.get("note"))
    errors: dict[str, str] = {}
    if outcome not in ("pending", *OUTCOMES):
        errors["outcome"] = f"Use one of: {', '.join(OUTCOMES)}."
    risk: Risk | None = None
    if outcome == "covered":
        try:
            risk = records.load(session, principal, RISK, str(values.get("risk") or ""))
        except NotFound:
            errors["risk"] = "Choose the risk on the register that covers this."
        else:
            if risk.status == "closed":
                errors["risk"] = f"{risk.ref} is closed, so it covers nothing now."
    if errors:
        raise Invalid("That was not recorded.", errors)
    found = _subject(session, item)
    with audit.operation(session, "risk_analysis.consider", outcome=outcome):
        if outcome == "raised":
            if found is None:
                raise Invalid("That was not recorded.", {"outcome": "The thing is no longer here."})
            record_type, thing = found
            threat = session.scalars(
                select(RiskLibraryEntry).where(RiskLibraryEntry.key == item.threat_key)
            ).first()
            if threat is None:
                raise Invalid(
                    "That was not recorded.", {"outcome": "That threat has left the library."}
                )
            name = records.text(values.get("name")) or f"{threat.title}: {thing.name}"[:200]
            # Whoever may work the analysis may raise what it finds, in the thing's own unit.
            risk = risks.create(
                session, principal,
                {"name": name, "category": threat.category_key, "org_unit_id": thing.org_unit_id,
                 "cause": threat.cause, "event": threat.event, "consequence": threat.consequence,
                 "library_key": threat.key, "summary": note},
                checked=True,
            )  # fmt: skip
            session.add(
                RiskSubject(risk_id=risk.id, subject_type=record_type.key, subject_id=thing.id)
            )
            _hand_to_owners(session, principal, analysis, risk, record_type, thing)
        elif outcome == "covered" and risk is not None and found is not None:
            record_type, thing = found
            already = session.scalars(
                select(RiskSubject.id).where(
                    RiskSubject.risk_id == risk.id,
                    RiskSubject.subject_type == record_type.key,
                    RiskSubject.subject_id == thing.id,
                )
            ).first()
            # The analysis found that the risk concerns this thing, so the risk says so.
            if already is None and access.can_edit(session, principal, RISK, risk):
                session.add(
                    RiskSubject(risk_id=risk.id, subject_type=record_type.key, subject_id=thing.id)
                )
            if values.get("look_again") and risk.standing != "not_assessed":
                risk.residual_in_doubt = True
                risk.residual_doubt_reason = (
                    f"Looked at in {analysis.ref} {analysis.name} against {item.subject_name}"
                    + (f": {note}" if note else ".")
                )[:1000]
                notices.tell_all(
                    session, notices.owners(session, "risk", risk.id), "risk",
                    f"{analysis.ref} asks for another look at {risk.ref} {risk.name}.",
                    f"/risks/{risk.ref}", by=principal,
                )  # fmt: skip
        item.outcome = outcome
        item.risk_id = risk.id if risk is not None and outcome in ("covered", "raised") else None
        item.note = note
        answered = outcome != "pending"
        item.considered_by_name = principal.name if answered else None
        item.considered_at = utc_now() if answered else None
        records.touch(session, analysis)
        session.flush()
    return item


def _hand_to_owners(
    session: Session, principal: Principal, analysis: RiskAnalysis, risk: Risk,
    record_type: RecordType, thing: Any,
) -> None:  # fmt: skip
    """A risk raised about a thing is answered for by whoever answers for the thing, not by
    whoever happened to be running the analysis. They are told."""
    owners = [
        each["account_id"]
        for each in records.owners_of(session, record_type, [thing.id]).get(thing.id, [])
        if each["kind"] == records.OWNER and each["active"]
    ]
    if not owners:
        return  # the person who raised it keeps it until someone is named
    have = session.scalars(
        select(RecordOwner).where(
            RecordOwner.record_type == RISK.key, RecordOwner.record_id == risk.id
        )
    ).all()
    for row in have:
        if row.account_id not in owners:
            session.delete(row)
    for account_id in owners:
        if not any(row.account_id == account_id for row in have):
            session.add(
                RecordOwner(record_type=RISK.key, record_id=risk.id, account_id=account_id,
                            kind=records.OWNER)
            )  # fmt: skip
    session.flush()
    notices.tell_all(
        session, owners, "risk",
        f"{analysis.ref} raised {risk.ref} {risk.name}. It is yours to assess.",
        f"/risks/{risk.ref}", by=principal,
    )  # fmt: skip


def rest_do_not_apply(
    session: Session, principal: Principal, analysis: RiskAnalysis, subject_ref: str,
    note: str | None,
) -> int:  # fmt: skip
    """Say that none of the threats not yet answered apply to one thing."""
    _may(session, principal, analysis)
    _open(analysis)
    rows = session.scalars(
        select(RiskAnalysisItem).where(
            RiskAnalysisItem.analysis_id == analysis.id,
            RiskAnalysisItem.subject_ref == subject_ref.strip().upper(),
            RiskAnalysisItem.outcome == "pending",
        )
    ).all()
    for item in rows:
        consider(session, principal, analysis, item, {"outcome": "not_applicable", "note": note})
    return len(rows)


def close(
    session: Session, principal: Principal, analysis: RiskAnalysis, conclusion: str | None
) -> None:
    """Finish the analysis. Every question needs an answer first: a report that passed over
    things in silence would not say what was considered."""
    _may(session, principal, analysis)
    _open(analysis)
    left = session.execute(
        select(func.count())
        .select_from(RiskAnalysisItem)
        .where(RiskAnalysisItem.analysis_id == analysis.id, RiskAnalysisItem.outcome == "pending")
    ).scalar_one()
    errors: dict[str, str] = {}
    if left:
        things = "1 question has" if left == 1 else f"{left} questions have"
        errors["conclusion"] = f"{things} no answer yet. Answer each, or say the rest do not apply."
    said = records.text(conclusion)
    if not said and not errors:
        errors["conclusion"] = "Say in a few sentences what the analysis found."
    if errors:
        raise Invalid("The analysis was not closed.", errors)
    with audit.operation(session, "risk_analysis.close"):
        analysis.status, analysis.conclusion = "closed", said
        analysis.closed_at, analysis.closed_by_name = utc_now(), principal.name
        records.touch(session, analysis)
        session.flush()


def reopen(session: Session, principal: Principal, analysis: RiskAnalysis) -> None:
    _may(session, principal, analysis)
    if analysis.status == "open":
        return
    with audit.operation(session, "risk_analysis.reopen"):
        analysis.status, analysis.closed_at, analysis.closed_by_name = "open", None, None
        records.touch(session, analysis)
        session.flush()


# --- Showing ------------------------------------------------------------------------------


def _items(session: Session, analysis_ids: list[int]) -> list[RiskAnalysisItem]:
    return list(
        session.scalars(
            select(RiskAnalysisItem)
            .where(RiskAnalysisItem.analysis_id.in_(analysis_ids))
            .order_by(RiskAnalysisItem.id)
        )
    )


def _counts(items: list[RiskAnalysisItem]) -> dict[str, int]:
    tally = Counter(item.outcome for item in items)
    return {
        "items": len(items),
        "pending": tally["pending"],
        "considered": len(items) - tally["pending"],
        "not_applicable": tally["not_applicable"],
        "covered": tally["covered"],
        "raised": tally["raised"],
    }


def _cards(session: Session, rows: list[RiskAnalysis]) -> list[dict[str, Any]]:
    by_analysis: dict[int, list[RiskAnalysisItem]] = defaultdict(list)
    for item in _items(session, [row.id for row in rows]):
        by_analysis[item.analysis_id].append(item)
    return [
        {"status": row.status, "closed_at": row.closed_at, **_counts(by_analysis[row.id])}
        for row in rows
    ]


def _risk_chips(session: Session, principal: Principal, ids: set[int]) -> dict[int, dict[str, Any]]:
    found = {}
    for risk in session.scalars(select(Risk).where(Risk.id.in_(ids or {0}))):
        if access.can_see(session, principal, RISK, risk):
            found[risk.id] = {
                **records.chip(RISK, risk), "residual_rating": risk.residual_rating,
                "standing": risk.standing, "status": risk.status,
            }  # fmt: skip
    return found


def _item_view(item: RiskAnalysisItem, chips: dict[int, dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": item.id,
        "subject": {"type": item.subject_type, "ref": item.subject_ref, "name": item.subject_name},
        "threat": {"key": item.threat_key, "title": item.threat_title},
        "outcome": item.outcome,
        "risk": chips.get(item.risk_id) if item.risk_id else None,
        # A risk the reader may not see is still said to exist: the report must not read as
        # though the question went unanswered.
        "risk_hidden": bool(item.risk_id and item.risk_id not in chips),
        "note": item.note,
        "by": item.considered_by_name,
        "at": item.considered_at,
    }


def _detail(session: Session, principal: Principal, analysis: RiskAnalysis) -> dict[str, Any]:
    from riskwren.compliance.scopes import SCOPE
    from riskwren.db.models import Scope

    items = _items(session, [analysis.id])
    chips = _risk_chips(session, principal, {item.risk_id for item in items if item.risk_id})
    by_subject: dict[tuple[str, str, str], list[RiskAnalysisItem]] = defaultdict(list)
    by_threat: dict[tuple[str, str], list[RiskAnalysisItem]] = defaultdict(list)
    for item in items:
        by_subject[(item.subject_type, item.subject_ref, item.subject_name)].append(item)
        by_threat[(item.threat_key, item.threat_title)].append(item)
    scope = session.get(Scope, analysis.scope_id) if analysis.scope_id else None
    seen = scope is not None and access.can_see(session, principal, SCOPE, scope)
    working = access.can_assess(session, principal, ANALYSIS, analysis)
    return {
        "status": analysis.status,
        "conclusion": analysis.conclusion,
        "closed_at": analysis.closed_at,
        "closed_by": analysis.closed_by_name,
        "scope": records.chip(SCOPE, scope) if seen and scope is not None else None,
        "counts": _counts(items),
        "assets": [
            {"type": kind, "ref": ref, "name": name, **_counts(rows)}
            for (kind, ref, name), rows in by_subject.items()
        ],
        "threats": [
            {"key": key, "title": title, **_counts(rows)}
            for (key, title), rows in by_threat.items()
        ],
        "items": [_item_view(item, chips) for item in items],
        "can_work": working and analysis.status == "open",
        "can_reopen": working and analysis.status == "closed",
    }


def asset(
    session: Session, principal: Principal, analysis: RiskAnalysis, subject_ref: str
) -> dict[str, Any]:
    """One thing in the analysis: each threat with its answer, and for those not answered,
    the risks already on the register that might be the answer."""
    ref = subject_ref.strip().upper()
    items = [item for item in _items(session, [analysis.id]) if item.subject_ref == ref]
    if not items:
        raise NotFound(f"{analysis.ref} does not look at {subject_ref}.")
    first = items[0]
    found = _subject(session, first)
    thing = None
    known: list[Risk] = []
    if found is not None and access.can_see(session, principal, found[0], found[1]):
        record_type, row = found
        thing = {**records.chip(record_type, row), "org_unit_id": row.org_unit_id,
                 "summary": row.summary, "data_class": row.data_class}  # fmt: skip
        about = select(RiskSubject.risk_id).where(
            RiskSubject.subject_type == record_type.key, RiskSubject.subject_id == row.id
        )
        within = units.with_descendants(session, [row.org_unit_id])
        conditions = [Risk.status != "closed", Risk.id.in_(about) | Risk.org_unit_id.in_(within)]
        seen = access.visible(session, principal, RISK)
        if seen is not None:
            conditions.append(seen)
        known = list(session.scalars(select(Risk).where(*conditions).order_by(Risk.ref)))
        concerning = set(session.scalars(about))
    else:
        concerning = set()
    chips = _risk_chips(session, principal, {item.risk_id for item in items if item.risk_id})
    library = {
        row.key: row
        for row in session.scalars(
            select(RiskLibraryEntry).where(
                RiskLibraryEntry.key.in_([item.threat_key for item in items])
            )
        )
    }
    out = []
    for item in items:
        threat = library.get(item.threat_key)
        # Likeliest first: a risk started from this very threat that names this thing.
        likely = sorted(
            (risk for risk in known if risk.library_key == item.threat_key),
            key=lambda risk: (risk.id not in concerning, risk.ref),
        )
        out.append(
            {
                **_item_view(item, chips),
                "threat": {
                    "key": item.threat_key, "title": item.threat_title,
                    "event": threat.event if threat else None,
                    "consequence": threat.consequence if threat else None,
                },
                "suggested": [
                    {**records.chip(RISK, risk), "residual_rating": risk.residual_rating,
                     "concerns_this": risk.id in concerning}
                    for risk in likely[:5]
                ],
            }
        )  # fmt: skip
    position = list(dict.fromkeys(i.subject_ref for i in _items(session, [analysis.id])))
    at = position.index(ref)
    return {
        "analysis": {"ref": analysis.ref, "name": analysis.name, "status": analysis.status},
        "thing": thing,
        "subject": {
            "type": first.subject_type,
            "ref": first.subject_ref,
            "name": first.subject_name,
        },
        "items": out,
        "counts": _counts(items),
        "previous": position[at - 1] if at > 0 else None,
        "next": position[at + 1] if at + 1 < len(position) else None,
        "can_work": access.can_assess(session, principal, ANALYSIS, analysis)
        and analysis.status == "open",
    }


def find_item(session: Session, analysis: RiskAnalysis, item_id: int) -> RiskAnalysisItem:
    item = session.get(RiskAnalysisItem, item_id)
    if item is None or item.analysis_id != analysis.id:
        raise NotFound(f"{analysis.ref} has no such question.")
    return item


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    if filters.get("status"):
        found.append(RiskAnalysis.status == filters["status"])
    return found


def _history_title(event: Any, lookups: Any) -> str | None:
    changes = event.changes or {}

    def now(field: str) -> Any:
        pair = changes.get(field) or [None, None]
        return pair[1] if pair[1] is not None else pair[0]

    op = (event.context or {}).get("op")
    if event.subject_type == "risk_analysis_item":
        if event.action == "created":
            return None  # one line for the start says it
        item = lookups.session.get(RiskAnalysisItem, event.subject_id)
        about = f"{item.threat_title} against {item.subject_name}" if item else "a question"
        said = OUTCOMES.get(str(now("outcome")), "Left unanswered")
        return f"{said}: {about}"
    if op == "risk_analysis.close":
        return "Closed the analysis"
    if op == "risk_analysis.reopen":
        return "Reopened the analysis"
    return None


ANALYSIS: RecordType = register(
    RecordType(
        "risk_analysis",
        RiskAnalysis,
        "RAN",
        "risk-analyses",
        "risk analysis",
        "risk analyses",
        is_thing=False,
        sorts=("updated_at", "name", "ref", "status"),
        extra={
            "new": _new,
            "apply": _apply,
            "cards": _cards,
            "detail": _detail,
            "conditions": _conditions,
            "can_add": can_add,
            "add_refusal": "An analysis is started by a steward of the unit, a manager, or an "
            "assessor.",
            "history_title": _history_title,
            "history_keeps_titled": True,
            "no_duplicates": True,
            "live_statuses": ("open",),
        },
    )
)
