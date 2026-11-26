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
    Requirement,
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
            .order_by(Requirement.id)
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
        .order_by(Framework.title, Requirement.id)
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
