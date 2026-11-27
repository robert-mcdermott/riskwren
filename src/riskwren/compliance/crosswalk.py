"""Crosswalks: which requirements each control helps to satisfy.

A control is described once and mapped to every requirement it answers, in any number of
frameworks, so that it is tested once and counts everywhere. A requirement may need several
controls; a mapping says whether this control answers it in full or in part.

What a person sees here follows what they may see of controls: a requirement's controls,
and every count of them, leave out the controls that person could not open.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from riskwren.access.principal import Principal
from riskwren.compliance import frameworks
from riskwren.controls import service as controls
from riskwren.controls.service import CONTROL
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    Control,
    ControlLibraryEntry,
    ControlRequirement,
    Framework,
    FrameworkMapping,
    Requirement,
    SuggestionSetAside,
)
from riskwren.db.models.compliance import COVERAGE
from riskwren.events import audit
from riskwren.inventory import access, records

COVERAGE_LABELS = {"full": "Answers it in full", "partial": "Answers it in part"}


# --- A control's requirements -------------------------------------------------------------


def suggestions(session: Session, control: Control) -> list[Requirement]:
    """What the library suggests for a control that was started from it, and is not yet
    mapped. Only frameworks that are loaded and in use are suggested from."""
    if not control.library_key:
        return []
    entry = session.scalars(
        select(ControlLibraryEntry).where(ControlLibraryEntry.key == control.library_key)
    ).first()
    if entry is None or not entry.requirements:
        return []
    have = set(
        session.scalars(
            select(ControlRequirement.requirement_id).where(
                ControlRequirement.control_id == control.id
            )
        )
    )
    found: list[Requirement] = []
    for key, codes in entry.requirements.items():
        framework = session.scalars(
            select(Framework).where(Framework.key == key, Framework.status == "active")
        ).first()
        if framework is None:
            continue
        rows = session.scalars(
            select(Requirement)
            .where(
                Requirement.framework_id == framework.id,
                Requirement.code.in_(codes),
                Requirement.is_citable.is_(True),
            )
            .order_by(Requirement.sequence)
        )
        found += [row for row in rows if row.id not in have]
    return found


def apply_library(session: Session, control: Control, *, account_id: int | None = None) -> int:
    """Map a control to what the library suggests for it. Each mapping is marked as coming
    from the pack and as partial, until a person says it is more."""
    wanted = suggestions(session, control)
    now = utc_now()
    session.add_all(
        ControlRequirement(
            control_id=control.id, requirement_id=row.id, coverage="partial", source="pack",
            created_by=account_id, created_at=now,
        )
        for row in wanted
    )  # fmt: skip
    session.flush()
    return len(wanted)


def apply_suggestions(session: Session, principal: Principal, control: Control) -> int:
    if not access.can_edit(session, principal, CONTROL, control):
        raise PermissionDenied("You cannot edit this control.")
    with audit.operation(session, "control.crosswalk"):
        return apply_library(session, control, account_id=principal.account_id)


def of_control(session: Session, principal: Principal, control: Control) -> dict[str, Any]:
    """A control's requirements, framework by framework."""
    rows = session.execute(
        select(ControlRequirement, Requirement, Framework)
        .join(Requirement, Requirement.id == ControlRequirement.requirement_id)
        .join(Framework, Framework.id == Requirement.framework_id)
        .where(ControlRequirement.control_id == control.id)
        .order_by(Framework.title, Requirement.sequence)
    ).all()
    groups: dict[str, dict[str, Any]] = {}
    for mapping, requirement, framework in rows:
        group = groups.setdefault(
            framework.key,
            {"key": framework.key, "title": framework.title, "status": framework.status,
             "requirements": []},
        )  # fmt: skip
        group["requirements"].append(
            {
                "id": mapping.id,
                "code": requirement.code,
                "title": requirement.title,
                "excerpt": frameworks.card(requirement)["excerpt"],
                "coverage": mapping.coverage,
                "note": mapping.note,
                "source": mapping.source,
            }
        )
    return {
        "frameworks": list(groups.values()),
        "total": len(rows),
        "suggested": len(suggestions(session, control)),
        "can_edit": access.can_edit(session, principal, CONTROL, control),
    }


def map_(
    session: Session,
    principal: Principal,
    control: Control,
    *,
    framework: str | None,
    code: str | None,
    coverage: str | None,
    note: str | None = None,
) -> ControlRequirement:
    """Say that a control helps to satisfy a requirement, or change how. One control is
    mapped to a requirement once."""
    if not access.can_edit(session, principal, CONTROL, control):
        raise PermissionDenied("You cannot edit this control.")
    errors = records.Errors()
    requirement = None
    try:
        source = frameworks.by_key(session, str(framework or ""))
        if source.status != "active":
            errors.add("framework", f"{source.title} is retired.")
        requirement = frameworks.find(session, source, str(code or ""))
        if not requirement.is_citable:
            errors.add("code", "That is a heading. Choose a requirement beneath it.")
    except NotFound as missing:
        errors.add("code", str(missing))
    if coverage not in COVERAGE:
        errors.add("coverage", "Say whether it answers the requirement in full or in part.")
    cleaned = records.text(note)
    if cleaned and len(cleaned) > 300:
        errors.add("note", "Keep the note to 300 characters.")
    if control.status != "active":
        errors.add("control", "That control has been retired.")
    if errors:
        raise Invalid("The requirement was not mapped.", errors)
    assert requirement is not None and coverage is not None
    existing = session.scalars(
        select(ControlRequirement).where(
            ControlRequirement.control_id == control.id,
            ControlRequirement.requirement_id == requirement.id,
        )
    ).first()
    with audit.operation(session, "control.crosswalk"):
        if existing is None:
            existing = ControlRequirement(
                control_id=control.id, requirement_id=requirement.id, coverage=coverage,
                note=cleaned, source="person", created_by=principal.account_id,
                created_at=utc_now(),
            )  # fmt: skip
            session.add(existing)
        else:
            # A person who changes a suggestion has made it their own.
            existing.coverage, existing.note, existing.source = coverage, cleaned, "person"
        session.flush()
    return existing


def unmap(session: Session, principal: Principal, control: Control, mapping_id: int) -> None:
    if not access.can_edit(session, principal, CONTROL, control):
        raise PermissionDenied("You cannot edit this control.")
    row = session.get(ControlRequirement, mapping_id)
    if row is None or row.control_id != control.id:
        raise NotFound("That requirement is not mapped to this control.")
    with audit.operation(session, "control.crosswalk"):
        session.delete(row)
        session.flush()


# --- A requirement's controls -------------------------------------------------------------


def controls_of(session: Session, principal: Principal, requirement: Requirement) -> dict[str, Any]:
    """The controls mapped to a requirement, cut to what the person may see."""
    shown, hidden = [], 0
    rows = session.execute(
        select(ControlRequirement, Control)
        .join(Control, Control.id == ControlRequirement.control_id)
        .where(ControlRequirement.requirement_id == requirement.id)
        .order_by(Control.ref)
    ).all()
    for mapping, control in rows:
        if not access.can_see(session, principal, CONTROL, control):
            hidden += 1
            continue
        shown.append(
            {
                "id": mapping.id,
                "coverage": mapping.coverage,
                "note": mapping.note,
                "source": mapping.source,
                "control": {
                    **records.chip(CONTROL, control),
                    "status": control.status,
                    "state": controls.state_of(session, control),
                },
            }
        )
    return {"controls": shown, "hidden": hidden}


def _mapped(session: Session, principal: Principal) -> Any:
    """The requirements that have at least one control in use that this person may see."""
    statement = (
        select(ControlRequirement.requirement_id)
        .join(Control, Control.id == ControlRequirement.control_id)
        .where(Control.status == "active")
    )
    visible = access.visible(session, principal, CONTROL)
    return statement.where(visible) if visible is not None else statement


def counts(session: Session, principal: Principal, requirement_ids: list[int]) -> dict[int, int]:
    """How many controls each of these requirements has, for lists."""
    if not requirement_ids:
        return {}
    statement = (
        select(ControlRequirement.requirement_id, func.count())
        .join(Control, Control.id == ControlRequirement.control_id)
        .where(ControlRequirement.requirement_id.in_(requirement_ids), Control.status == "active")
        .group_by(ControlRequirement.requirement_id)
    )
    visible = access.visible(session, principal, CONTROL)
    if visible is not None:
        statement = statement.where(visible)
    return {int(key): int(count) for key, count in session.execute(statement).all()}


def condition(session: Session, principal: Principal, *, mapped: bool) -> ColumnElement[bool]:
    """A filter for a framework's list: the requirements with a control, or the ones that
    can be cited and have none."""
    have = _mapped(session, principal)
    if mapped:
        return Requirement.id.in_(have)
    return and_(Requirement.id.not_in(have), Requirement.is_citable.is_(True))


def coverage(session: Session, principal: Principal, framework: Framework) -> dict[str, Any]:
    """How much of a framework has a control mapped to it. A gap is a requirement with none."""
    mapped = session.execute(
        select(func.count())
        .select_from(Requirement)
        .where(
            Requirement.framework_id == framework.id,
            Requirement.is_citable.is_(True),
            Requirement.id.in_(_mapped(session, principal)),
        )
    ).scalar_one()
    return {
        "citable": framework.citable_count,
        "mapped": int(mapped),
        "unmapped": framework.citable_count - int(mapped),
    }


# --- What a publisher's mapping suggests ------------------------------------------------------


def _publisher_pairs(session: Session, framework: Framework) -> list[tuple[str, str, str]]:
    """(code here, other framework's key, its code): what a publisher says relates this
    framework's requirements to another's, in either direction."""
    found: list[tuple[str, str, str]] = []
    for row in session.scalars(
        select(FrameworkMapping).where(
            FrameworkMapping.relation == "derived_from",
            (FrameworkMapping.from_key == framework.key)
            | (FrameworkMapping.to_key == framework.key),
        )
    ):
        if row.from_key == framework.key:
            found.append((row.from_code, row.to_key, row.to_code))
        else:
            found.append((row.to_code, row.from_key, row.from_code))
    return found


def publisher_suggestions(
    session: Session, principal: Principal, framework: Framework
) -> dict[str, Any]:
    """Crosswalks suggested by a publisher's mapping: a control mapped to a requirement of
    another framework, which the publisher relates to one of this framework's, and not mapped
    to that one yet nor set aside. Grouped by control; each says what suggests it."""
    pairs = _publisher_pairs(session, framework)
    if not pairs:
        return {"controls": [], "total": 0, "sources": []}
    keys = {other for _here, other, _there in pairs}
    others = {
        row.key: row for row in session.scalars(select(Framework).where(Framework.key.in_(keys)))
    }
    wanted_codes = {(other, there) for _here, other, there in pairs if other in others}
    requirement_of: dict[tuple[str, str], Requirement] = {}
    for row, key in session.execute(
        select(Requirement, Framework.key)
        .join(Framework, Framework.id == Requirement.framework_id)
        .where(Framework.key.in_([*keys, framework.key]), Requirement.is_citable.is_(True))
    ).all():
        requirement_of[(key, row.code)] = row
    mapped: dict[int, set[int]] = {}
    for control_id, requirement_id in session.execute(
        select(ControlRequirement.control_id, ControlRequirement.requirement_id)
    ).all():
        mapped.setdefault(requirement_id, set()).add(control_id)
    set_aside = set(
        session.execute(
            select(SuggestionSetAside.control_id, SuggestionSetAside.requirement_id)
        ).all()
    )
    found: dict[tuple[int, int], dict[str, Any]] = {}
    for here, other, there in pairs:
        target = requirement_of.get((framework.key, here))
        source = requirement_of.get((other, there))
        if target is None or source is None or (other, there) not in wanted_codes:
            continue
        for control_id in mapped.get(source.id, set()):
            if control_id in mapped.get(target.id, set()) or (control_id, target.id) in set_aside:
                continue
            entry = found.setdefault(
                (control_id, target.id),
                {"code": target.code, "title": target.title,
                 "excerpt": frameworks.card(target)["excerpt"], "because": []},
            )  # fmt: skip
            entry["because"].append({"framework": others[other].title, "key": other, "code": there})
    by_control: dict[int, list[dict[str, Any]]] = {}
    for (control_id, _requirement_id), entry in found.items():
        by_control.setdefault(control_id, []).append(entry)
    shown = []
    for control in session.scalars(
        select(Control).where(Control.id.in_(list(by_control) or [0])).order_by(Control.ref)
    ):
        if control.status != "active" or not access.can_see(session, principal, CONTROL, control):
            continue
        shown.append({
            "control": records.chip(CONTROL, control),
            "can_edit": access.can_edit(session, principal, CONTROL, control),
            "suggestions": sorted(by_control[control.id], key=lambda each: each["code"]),
        })  # fmt: skip
    return {
        "controls": shown,
        "total": sum(len(each["suggestions"]) for each in shown),
        "sources": sorted(
            {others[other].title for _here, other, _there in pairs if other in others}
        ),
    }


def confirm_suggestion(
    session: Session, principal: Principal, framework: Framework, control: Control, code: str
) -> ControlRequirement:
    """A person agrees with a suggestion: the control is mapped, in part, and it is theirs."""
    suggested = [
        each for each in publisher_suggestions(session, principal, framework)["controls"]
        if each["control"]["ref"] == control.ref
    ]  # fmt: skip
    match = next(
        (each for group in suggested for each in group["suggestions"] if each["code"] == code), None
    )
    if match is None:
        raise NotFound(f"{code} is not suggested for {control.ref}.")
    because = ", ".join(f"{each['code']} of {each['framework']}" for each in match["because"])
    return map_(
        session, principal, control, framework=framework.key, code=code, coverage="partial",
        note=f"Suggested by the publisher's mapping from {because}."[:300],
    )  # fmt: skip


def set_aside(
    session: Session, principal: Principal, framework: Framework, control: Control, code: str
) -> None:
    """A person says a suggestion does not hold: it is not suggested again."""
    if not access.can_edit(session, principal, CONTROL, control):
        raise PermissionDenied("You cannot edit this control.")
    requirement = frameworks.find(session, framework, code)
    exists_already = session.scalars(
        select(SuggestionSetAside.id).where(
            SuggestionSetAside.control_id == control.id,
            SuggestionSetAside.requirement_id == requirement.id,
        )
    ).first()
    if exists_already is None:
        with audit.operation(session, "control.set_aside", code=code, framework=framework.title):
            session.add(
                SuggestionSetAside(
                    control_id=control.id, requirement_id=requirement.id,
                    account_id=principal.account_id, set_aside_at=utc_now(),
                )
            )  # fmt: skip
            session.flush()
