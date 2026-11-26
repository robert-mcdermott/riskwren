"""Scopes: a boundary, what it must meet, and how each control is done inside it.

A scope names what is inside it (units, processes, systems, information, third parties) and
the frameworks it is held to. Within it each requirement is applicable or left out with a
reason, and each control it uses has an implementation: where it stands, who answers for
it, and how it is done here.

In a federated organization most safeguards are provided once and relied on many times, so
a scope may offer its controls, and another may inherit them: wholly, or sharing the work.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.compliance import frameworks
from riskwren.controls import service as controls
from riskwren.controls.service import CONTROL
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    Baseline,
    BaselineRequirement,
    Control,
    ControlRequirement,
    Framework,
    Implementation,
    OrgUnit,
    Requirement,
    Scope,
    ScopeFramework,
    ScopeMember,
    ScopeRequirement,
)
from riskwren.db.models.compliance import IMPLEMENTATION_STATUSES
from riskwren.db.models.inventory import RECORD_STATUSES
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.registry import TYPES, Field, RecordType, find, find_any, register

STATUS_LABELS = {
    "planned": "Planned",
    "partly": "Partly in place",
    "in_place": "In place",
    "not_applicable": "Not applicable here",
}
# From weakest to strongest: what a requirement takes when its controls differ.
ORDER = ("planned", "partly", "in_place")
# From weakest to strongest. A requirement takes the weakest state among its controls.
STATES = {
    "failing": "Failing",
    "gap": "Gap",
    "planned": "Planned",
    "excepted": "Excepted",
    "in_place": "In place",
    "verified": "Verified",
    "excluded": "Not applicable",
}

# The states an exception in force stands in for. One that is in place or verified is not
# made to look worse by an exception nobody needs.
COVERED = ("failing", "gap", "planned")


# --- The record type ----------------------------------------------------------------------


def _new(scope: Scope) -> None:
    scope.status, scope.offers_controls = "active", False


def _apply(
    session: Session, scope: Scope, values: Mapping[str, Any], errors: records.Errors,
    creating: bool,
) -> None:  # fmt: skip
    if values.get("status") is not None:
        if values["status"] not in RECORD_STATUSES:
            errors.add("status", "Use active or retired.")
        else:
            scope.status = values["status"]
    if values.get("offers_controls") is not None:
        offers = bool(values["offers_controls"])
        if not offers and scope.id is not None and _relied_on(session, scope):
            errors.add("offers_controls", "Other scopes inherit controls from this one.")
        else:
            scope.offers_controls = offers


def _relied_on(session: Session, scope: Scope) -> bool:
    mine = select(Implementation.id).where(Implementation.scope_id == scope.id)
    return (
        session.scalars(
            select(Implementation.id).where(Implementation.inherits_from_id.in_(mine))
        ).first()
        is not None
    )


def _cards(session: Session, rows: list[Scope]) -> list[dict[str, Any]]:
    ids = [row.id for row in rows] or [0]
    held = session.execute(
        select(ScopeFramework.scope_id, Framework.key, Framework.title)
        .join(Framework, Framework.id == ScopeFramework.framework_id)
        .where(ScopeFramework.scope_id.in_(ids))
        .order_by(Framework.title)
    ).all()
    counts = dict(
        session.execute(
            select(Implementation.scope_id, func.count())
            .where(Implementation.scope_id.in_(ids))
            .group_by(Implementation.scope_id)
        ).all()
    )
    return [
        {
            "status": row.status,
            "offers_controls": row.offers_controls,
            "frameworks": [{"key": k, "title": t} for sid, k, t in held if sid == row.id],
            "controls": counts.get(row.id, 0),
        }
        for row in rows
    ]


def _detail(session: Session, principal: Principal, scope: Scope) -> dict[str, Any]:
    return {
        "members": members_of(session, principal, scope),
        "held_to": held_to(session, scope),
    }


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    if filters.get("framework"):
        found.append(
            Scope.id.in_(
                select(ScopeFramework.scope_id)
                .join(Framework, Framework.id == ScopeFramework.framework_id)
                .where(Framework.key == str(filters["framework"]))
            )
        )
    if filters.get("offers"):
        found.append(Scope.offers_controls.is_(True))
    return found


SCOPE = register(
    RecordType(
        "scope",
        Scope,
        "SCP",
        "scopes",
        "scope",
        "scopes",
        fields=(Field("boundary", "Boundary", "long"),),
        is_thing=False,
        sorts=("updated_at", "name", "ref", "status"),
        filters=("status",),
        extra={
            "new": _new,
            "apply": _apply,
            "cards": _cards,
            "detail": _detail,
            "conditions": _conditions,
            "history_labels": {"offers_controls": "Offers its controls", "boundary": "Boundary"},
        },
    )
)


def _editable(session: Session, principal: Principal, scope: Scope) -> None:
    if not access.can_edit(session, principal, SCOPE, scope):
        raise PermissionDenied("You cannot edit this scope.")
    if scope.status != "active":
        raise Conflict("This scope is retired.")


# --- What is inside it --------------------------------------------------------------------


def members_of(session: Session, principal: Principal, scope: Scope) -> dict[str, Any]:
    rows = session.scalars(
        select(ScopeMember).where(ScopeMember.scope_id == scope.id).order_by(ScopeMember.id)
    ).all()
    units, shown, hidden = [], [], 0
    for row in rows:
        if row.subject_type == "unit":
            unit = session.get(OrgUnit, row.subject_id)
            if unit is not None:
                units.append({"id": unit.id, "name": unit.name})
            continue
        record_type = TYPES.get(row.subject_type)
        record = session.get(record_type.model, row.subject_id) if record_type else None
        if record is None or record_type is None:
            continue
        if access.can_see(session, principal, record_type, record):
            shown.append(records.chip(record_type, record))
        else:
            hidden += 1
    return {"units": units, "records": shown, "hidden": hidden}


def set_members(
    session: Session, principal: Principal, scope: Scope, refs: list[str], unit_ids: list[int]
) -> None:
    """Say what is inside the boundary: units, and records from the inventory."""
    _editable(session, principal, scope)
    wanted: set[tuple[str, int]] = set()
    for unit_id in dict.fromkeys(unit_ids):
        if session.get(OrgUnit, int(unit_id)) is None:
            raise Invalid("The boundary was not saved.", {"units": "There is no such unit."})
        wanted.add(("unit", int(unit_id)))
    for ref in dict.fromkeys(refs):
        try:
            record_type, record = find_any(session, ref)
        except NotFound as missing:
            raise Invalid("The boundary was not saved.", {"records": str(missing)}) from missing
        if not record_type.is_thing or not access.can_see(session, principal, record_type, record):
            raise Invalid(
                "The boundary was not saved.",
                {"records": f"{ref} is not a process, system, information asset, or third party."},
            )
        wanted.add((record_type.key, record.id))
    have = {
        (row.subject_type, row.subject_id): row
        for row in session.scalars(select(ScopeMember).where(ScopeMember.scope_id == scope.id))
    }
    with audit.operation(session, "scope.members"):
        for key, row in have.items():
            if key not in wanted:
                session.delete(row)
        for subject_type, subject_id in sorted(wanted - set(have)):
            session.add(
                ScopeMember(scope_id=scope.id, subject_type=subject_type, subject_id=subject_id)
            )
        records.touch(session, scope)


# --- What it must meet --------------------------------------------------------------------


def held_to(session: Session, scope: Scope) -> list[dict[str, Any]]:
    rows = session.execute(
        select(ScopeFramework, Framework, Baseline)
        .join(Framework, Framework.id == ScopeFramework.framework_id)
        .outerjoin(Baseline, Baseline.id == ScopeFramework.baseline_id)
        .where(ScopeFramework.scope_id == scope.id)
        .order_by(Framework.title)
    ).all()
    return [
        {
            "key": framework.key,
            "title": framework.title,
            "version": framework.version,
            "baseline": {"key": baseline.key, "title": baseline.title} if baseline else None,
        }
        for _, framework, baseline in rows
    ]


def _held(session: Session, scope: Scope, framework: Framework) -> ScopeFramework:
    row = session.scalars(
        select(ScopeFramework).where(
            ScopeFramework.scope_id == scope.id, ScopeFramework.framework_id == framework.id
        )
    ).first()
    if row is None:
        raise NotFound(f"{scope.name} is not held to {framework.title}.")
    return row


def hold_to(
    session: Session, principal: Principal, scope: Scope, framework_key: str,
    baseline_key: str | None,
) -> None:  # fmt: skip
    """Say that the scope must meet a framework, starting from a baseline if it has one."""
    _editable(session, principal, scope)
    errors = records.Errors()
    framework = None
    try:
        framework = frameworks.by_key(session, framework_key)
        if framework.status != "active":
            errors.add("framework", f"{framework.title} is retired.")
    except NotFound as missing:
        errors.add("framework", str(missing))
    baseline = None
    if framework is not None and baseline_key:
        baseline = session.scalars(
            select(Baseline).where(
                Baseline.framework_id == framework.id, Baseline.key == baseline_key
            )
        ).first()
        if baseline is None:
            errors.add("baseline", f"{framework.title} has no baseline {baseline_key!r}.")
    if errors:
        raise Invalid("The framework was not added.", errors)
    assert framework is not None
    row = session.scalars(
        select(ScopeFramework).where(
            ScopeFramework.scope_id == scope.id, ScopeFramework.framework_id == framework.id
        )
    ).first()
    with audit.operation(session, "scope.framework"):
        if row is None:
            session.add(
                ScopeFramework(
                    scope_id=scope.id, framework_id=framework.id,
                    baseline_id=baseline.id if baseline else None,
                )
            )  # fmt: skip
        else:
            row.baseline_id = baseline.id if baseline else None
        records.touch(session, scope)


def release_from(session: Session, principal: Principal, scope: Scope, framework_key: str) -> None:
    """Take a framework off a scope, with the decisions made about its requirements."""
    _editable(session, principal, scope)
    framework = frameworks.by_key(session, framework_key)
    row = _held(session, scope, framework)
    with audit.operation(session, "scope.framework"):
        for decision in session.scalars(
            select(ScopeRequirement)
            .join(Requirement, Requirement.id == ScopeRequirement.requirement_id)
            .where(ScopeRequirement.scope_id == scope.id, Requirement.framework_id == framework.id)
        ):
            session.delete(decision)
        session.delete(row)
        records.touch(session, scope)


# --- Applicability ------------------------------------------------------------------------


def _starting_point(session: Session, held: ScopeFramework) -> set[int]:
    """Where a scope begins: the baseline's selection, or every requirement that can be cited."""
    if held.baseline_id is not None:
        return set(
            session.scalars(
                select(BaselineRequirement.requirement_id).where(
                    BaselineRequirement.baseline_id == held.baseline_id
                )
            )
        )
    return set(
        session.scalars(
            select(Requirement.id).where(
                Requirement.framework_id == held.framework_id, Requirement.is_citable.is_(True)
            )
        )
    )


def _decisions(session: Session, scope: Scope, framework: Framework) -> dict[int, ScopeRequirement]:
    rows = session.scalars(
        select(ScopeRequirement)
        .join(Requirement, Requirement.id == ScopeRequirement.requirement_id)
        .where(ScopeRequirement.scope_id == scope.id, Requirement.framework_id == framework.id)
    )
    return {row.requirement_id: row for row in rows}


def decide(
    session: Session,
    principal: Principal,
    scope: Scope,
    *,
    framework: str,
    code: str,
    applicable: bool,
    reason: str | None,
) -> None:
    """Say that a requirement does or does not apply within the scope. Leaving one out needs
    a reason; so that the statement of applicability can give it."""
    _editable(session, principal, scope)
    source = frameworks.by_key(session, framework)
    held = _held(session, scope, source)
    requirement = frameworks.find(session, source, code)
    if not requirement.is_citable:
        raise Invalid(
            "The decision was not recorded.",
            {"code": "That is a heading. Decide the requirements beneath it."},
        )
    why = records.text(reason)
    if not applicable and not why:
        raise Invalid(
            "The decision was not recorded.",
            {"reason": "Say why this requirement does not apply here."},
        )
    by_default = requirement.id in _starting_point(session, held)
    existing = _decisions(session, scope, source).get(requirement.id)
    with audit.operation(session, "scope.applicability"):
        if applicable == by_default:
            # Back to where the scope started: nothing to keep but the history.
            if existing is not None:
                session.delete(existing)
        elif existing is None:
            session.add(
                ScopeRequirement(
                    scope_id=scope.id, requirement_id=requirement.id, applicable=applicable,
                    reason=why, decided_by=principal.account_id, decided_by_name=principal.name,
                    decided_at=utc_now(),
                )
            )  # fmt: skip
        else:
            existing.applicable, existing.reason = applicable, why
            existing.decided_by, existing.decided_by_name = principal.account_id, principal.name
            existing.decided_at = utc_now()
        records.touch(session, scope)


# --- Implementations ----------------------------------------------------------------------


def _find_implementation(session: Session, scope: Scope, implementation_id: int) -> Implementation:
    row = session.get(Implementation, implementation_id)
    if row is None or row.scope_id != scope.id:
        raise NotFound("That control is not used in this scope.")
    return row


def _provider(session: Session, row: Implementation) -> tuple[Implementation, Scope] | None:
    if row.inherits_from_id is None:
        return None
    provided = session.get(Implementation, row.inherits_from_id)
    if provided is None:
        return None
    scope = session.get(Scope, provided.scope_id)
    assert scope is not None
    return provided, scope


def standing(session: Session, row: Implementation) -> str:
    """Where a control stands in a scope. One that is wholly inherited stands where its
    provider's does; one that is shared is only as far along as the weaker half."""
    provider = _provider(session, row)
    if provider is None or row.inheritance == "none":
        return row.status
    theirs = provider[0].status
    if row.inheritance == "inherited":
        return theirs
    if "not_applicable" in (row.status, theirs):
        return row.status if theirs == "not_applicable" else theirs
    return min(row.status, theirs, key=ORDER.index)


def implementation_view(
    session: Session, principal: Principal, row: Implementation
) -> dict[str, Any]:
    control = session.get(Control, row.control_id)
    assert control is not None
    provider = _provider(session, row)
    relied = session.execute(
        select(func.count())
        .select_from(Implementation)
        .where(Implementation.inherits_from_id == row.id)
    ).scalar_one()
    # A control offered to others is shown to them by name and state, whoever may open it.
    seen = access.can_see(session, principal, CONTROL, control)
    return {
        "id": row.id,
        "control": {
            **records.chip(CONTROL, control),
            "statement": control.statement,
            "state": controls.state_of(session, control),
            "open": seen,
        },
        "status": row.status,
        "standing": standing(session, row),
        "responsibility": row.responsibility,
        "statement": row.statement,
        "inheritance": row.inheritance,
        "provider": {
            "scope": {"ref": provider[1].ref, "name": provider[1].name},
            "status": provider[0].status,
            "responsibility": provider[0].responsibility,
            "statement": provider[0].statement,
        }
        if provider
        else None,
        "relied_on_by": int(relied),
    }


def implementations(session: Session, principal: Principal, scope: Scope) -> dict[str, Any]:
    rows = session.execute(
        select(Implementation)
        .join(Control, Control.id == Implementation.control_id)
        .where(Implementation.scope_id == scope.id)
        .order_by(Control.ref)
    ).scalars()
    return {
        "controls": [implementation_view(session, principal, row) for row in rows],
        "candidates": len(candidates(session, principal, scope)),
        "can_edit": access.can_edit(session, principal, SCOPE, scope) and scope.status == "active",
    }


def _status(value: Any, errors: records.Errors) -> None:
    if value not in IMPLEMENTATION_STATUSES:
        errors.add("status", f"Use one of: {', '.join(IMPLEMENTATION_STATUSES)}.")


def implement(
    session: Session,
    principal: Principal,
    scope: Scope,
    control: Control,
    *,
    status: str | None,
    responsibility: str | None = None,
    statement: str | None = None,
) -> Implementation:
    """Say that a control is used in this scope, or change where it stands. One the scope
    inherits whole takes its standing from its provider, and has none of its own to set."""
    _editable(session, principal, scope)
    if not access.can_see(session, principal, CONTROL, control):
        raise NotFound(f"There is no control {control.ref}.")
    errors = records.Errors()
    row = session.scalars(
        select(Implementation).where(
            Implementation.scope_id == scope.id, Implementation.control_id == control.id
        )
    ).first()
    whole = row is not None and row.inheritance == "inherited"
    if whole and status not in (None, row.status if row else None):
        errors.add(
            "status",
            "This control is inherited whole: it stands where its provider's does.",
        )
    elif not whole:
        _status(status, errors)
    who = records.text(responsibility)
    if who and len(who) > 200:
        errors.add("responsibility", "Keep this to 200 characters.")
    if row is None and control.status != "active":
        errors.add("control", "That control has been retired.")
    if errors:
        raise Invalid("The control was not saved.", errors)
    now = utc_now()
    with audit.operation(session, "scope.implement"):
        if row is None:
            assert status is not None
            row = Implementation(
                scope_id=scope.id, control_id=control.id, status=status, responsibility=who,
                statement=records.text(statement), inheritance="none",
                created_by=principal.account_id, created_at=now, updated_at=now,
            )  # fmt: skip
            session.add(row)
        else:
            if not whole and status is not None:
                row.status = status
            row.responsibility, row.statement = who, records.text(statement)
            row.updated_at = now
        session.flush()
        records.touch(session, scope)
    return row


def offers(session: Session, principal: Principal, scope: Scope) -> list[dict[str, Any]]:
    """What other scopes offer that this one does not use yet."""
    have = set(
        session.scalars(
            select(Implementation.control_id).where(Implementation.scope_id == scope.id)
        )
    )
    rows = session.execute(
        select(Implementation, Scope)
        .join(Scope, Scope.id == Implementation.scope_id)
        .join(Control, Control.id == Implementation.control_id)
        .where(
            Scope.offers_controls.is_(True),
            Scope.status == "active",
            Scope.id != scope.id,
            Implementation.inheritance != "inherited",
            Implementation.status != "not_applicable",
            Control.status == "active",
        )
        .order_by(Scope.name, Control.ref)
    ).all()
    return [
        {**implementation_view(session, principal, row), "scope": {"ref": s.ref, "name": s.name}}
        for row, s in rows
        if row.control_id not in have
    ]


def inherit(
    session: Session,
    principal: Principal,
    scope: Scope,
    provided_id: int,
    *,
    inheritance: str,
    status: str | None = None,
    responsibility: str | None = None,
    statement: str | None = None,
) -> Implementation:
    """Rely on a control another scope offers: whole, or sharing the work, in which case
    this scope says where its own part stands and how it is done."""
    _editable(session, principal, scope)
    provided = session.get(Implementation, provided_id)
    provider = session.get(Scope, provided.scope_id) if provided else None
    if provided is None or provider is None or not provider.offers_controls:
        raise NotFound("No scope offers that control.")
    errors = records.Errors()
    if provider.id == scope.id:
        errors.add("implementation", "A scope does not inherit from itself.")
    if provided.inheritance == "inherited":
        errors.add("implementation", "Inherit it from the scope that provides it.")
    if inheritance not in ("inherited", "shared"):
        errors.add("inheritance", "Say whether it is inherited whole, or shared.")
    part = records.text(statement)
    if inheritance == "shared":
        _status(status, errors)
        if not part:
            errors.add("statement", "Say what this scope does as its part.")
    taken = session.scalars(
        select(Implementation).where(
            Implementation.scope_id == scope.id, Implementation.control_id == provided.control_id
        )
    ).first()
    if taken is not None and taken.inherits_from_id != provided.id:
        errors.add("implementation", "This scope already uses that control.")
    if errors:
        raise Invalid("The control was not inherited.", errors)
    now = utc_now()
    own = status if inheritance == "shared" and status else provided.status
    with audit.operation(session, "scope.inherit"):
        if taken is None:
            taken = Implementation(
                scope_id=scope.id, control_id=provided.control_id,
                created_by=principal.account_id, created_at=now,
            )  # fmt: skip
            session.add(taken)
        taken.status, taken.inheritance, taken.inherits_from_id = own, inheritance, provided.id
        taken.responsibility, taken.statement = records.text(responsibility), part
        taken.updated_at = now
        session.flush()
        records.touch(session, scope)
    return taken


def remove_implementation(
    session: Session, principal: Principal, scope: Scope, implementation_id: int
) -> None:
    _editable(session, principal, scope)
    row = _find_implementation(session, scope, implementation_id)
    relying = session.scalars(
        select(Implementation.id).where(Implementation.inherits_from_id == row.id)
    ).first()
    if relying is not None:
        raise Conflict("Other scopes inherit this control from here. They must let go of it first.")
    with audit.operation(session, "scope.implement"):
        session.delete(row)
        records.touch(session, scope)


def applicable_ids(session: Session, scope: Scope, framework: Framework | None = None) -> set[int]:
    """The requirements that apply within a scope, for one framework or for all it is held to."""
    held_to = select(ScopeFramework).where(ScopeFramework.scope_id == scope.id)
    if framework is not None:
        held_to = held_to.where(ScopeFramework.framework_id == framework.id)
    chosen: set[int] = set()
    for held in session.scalars(held_to):
        chosen |= _starting_point(session, held)
    for row in session.scalars(
        select(ScopeRequirement).where(ScopeRequirement.scope_id == scope.id)
    ):
        (chosen.add if row.applicable else chosen.discard)(row.requirement_id)
    return chosen


def candidates(session: Session, principal: Principal, scope: Scope) -> list[dict[str, Any]]:
    """Controls the person may see that answer this scope's requirements and are not used in
    it yet, each with how many of those requirements it answers."""
    wanted = applicable_ids(session, scope)
    if not wanted:
        return []
    have = select(Implementation.control_id).where(Implementation.scope_id == scope.id)
    statement = (
        select(Control, func.count())
        .join(ControlRequirement, ControlRequirement.control_id == Control.id)
        .where(
            ControlRequirement.requirement_id.in_(wanted),
            Control.status == "active",
            Control.id.not_in(have),
        )
        .group_by(Control.id)
        .order_by(func.count().desc(), Control.ref)
    )
    visible = access.visible(session, principal, CONTROL)
    if visible is not None:
        statement = statement.where(visible)
    return [
        {**records.chip(CONTROL, control), "statement": control.statement, "answers": int(count),
         "state": controls.state_of(session, control), "org_unit_id": control.org_unit_id}
        for control, count in session.execute(statement).all()
    ]  # fmt: skip


# --- The statement of applicability ---------------------------------------------------------


def statement(
    session: Session,
    principal: Principal,
    scope: Scope,
    framework_key: str,
    *,
    state: str | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    """For a scope and a framework: every requirement that applies, with the controls that
    answer it here and where they stand; and every one left out, with the reason.

    Each requirement is in one state, worked out and never typed in. It is a *gap* when no
    control mapped to it is used in this scope; *planned* when one that is used is not yet
    in place; *in place* when all of them are; *verified* when each has a test result of
    effective that still holds, with evidence that still counts; and *failing* when a test
    that still holds found a control partly effective or ineffective. A requirement takes
    the weakest state among its controls.
    """
    from riskwren.compliance import exceptions, readiness  # they build on scopes and tests

    framework = frameworks.by_key(session, framework_key)
    held = _held(session, scope, framework)
    start = _starting_point(session, held)
    decisions = _decisions(session, scope, framework)
    conditions = [Requirement.framework_id == framework.id, Requirement.is_citable.is_(True)]
    words = (query or "").strip().lower()
    if words:
        like = f"%{words}%"
        conditions.append(
            or_(
                func.lower(Requirement.code).like(like),
                func.lower(func.coalesce(Requirement.title, "")).like(like),
                func.lower(func.coalesce(Requirement.text, "")).like(like),
            )
        )
    requirements = session.scalars(
        select(Requirement).where(*conditions).order_by(Requirement.sequence)
    ).all()
    used = {
        row.control_id: row
        for row in session.scalars(
            select(Implementation).where(Implementation.scope_id == scope.id)
        )
    }
    mapped: dict[int, list[int]] = {}
    for requirement_id, control_id in session.execute(
        select(ControlRequirement.requirement_id, ControlRequirement.control_id).where(
            ControlRequirement.requirement_id.in_([r.id for r in requirements] or [0]),
            ControlRequirement.control_id.in_(list(used) or [0]),
        )
    ):
        mapped.setdefault(requirement_id, []).append(control_id)
    views = {
        control_id: implementation_view(session, principal, row) for control_id, row in used.items()
    }
    assured = readiness.assurance(session, list(used))
    waived = exceptions.in_force_for(session, scope)
    for control_id, view in views.items():
        found, why = readiness.of_control(view["standing"], assured[control_id])
        excepted = waived["control"].get(control_id)
        view["exception"], view["underlying"] = None, found
        if excepted is not None and found in COVERED:
            view["exception"] = exceptions.chip(excepted)
            # An exception covers a weakness for a time. It does not improve on a control
            # that is in place, and what is underneath is said beside it.
            why = f"Excepted until {excepted.expires_on.isoformat()} by {excepted.ref}. {why}"
            found = "excepted"
        view["readiness"], view["why"] = found, why
    rows = []
    counts = dict.fromkeys(STATES, 0)
    for requirement in requirements:
        decision = decisions.get(requirement.id)
        applies = decision.applicable if decision else requirement.id in start
        if not applies and decision is None:
            continue  # outside the baseline, and nobody has said otherwise
        answering = [
            views[control_id]
            for control_id in mapped.get(requirement.id, [])
            if views[control_id]["standing"] != "not_applicable"
        ]
        if not applies:
            found = "excluded"
        elif not answering:
            found = "gap"
        else:
            found = min((view["readiness"] for view in answering), key=list(STATES).index)
        underneath = found
        if applies and answering:
            underneath = min((view["underlying"] for view in answering), key=list(STATES).index)
        excepted = waived["requirement"].get(requirement.id) if applies else None
        if excepted is not None and found in COVERED:
            found = "excepted"
        else:
            excepted = None  # one that covers nothing here is not shown as if it did
        counts[found] += 1
        if state and found != state:
            continue
        rows.append(
            {
                "code": requirement.code,
                "title": requirement.title,
                "excerpt": frameworks.card(requirement)["excerpt"],
                "applicable": applies,
                "state": found,
                # What it would be without the exception, and will be again when that ends.
                "underlying": underneath,
                "exception": exceptions.chip(excepted) if excepted is not None else None,
                "reason": decision.reason if decision else None,
                "decided_by": decision.decided_by_name if decision else None,
                "decided_at": decision.decided_at if decision else None,
                "in_baseline": requirement.id in start,
                "controls": [
                    {"ref": v["control"]["ref"], "name": v["control"]["name"],
                     "standing": v["standing"], "readiness": v["readiness"], "why": v["why"],
                     "exception": v["exception"],
                     "inheritance": v["inheritance"],
                     "provider": v["provider"]["scope"] if v["provider"] else None,
                     "open": v["control"]["open"]}
                    for v in answering
                ],
            }
        )  # fmt: skip
    baseline = session.get(Baseline, held.baseline_id) if held.baseline_id else None
    return {
        "scope": {"ref": scope.ref, "name": scope.name},
        "framework": {"key": framework.key, "title": framework.title,
                      "version": framework.version},
        "baseline": {"key": baseline.key, "title": baseline.title} if baseline else None,
        "counts": counts,
        "applicable": sum(count for key, count in counts.items() if key != "excluded"),
        "requirements": rows,
        "can_edit": access.can_edit(session, principal, SCOPE, scope) and scope.status == "active",
    }  # fmt: skip


def find_scope(session: Session, ref: str) -> Scope:
    return find(session, SCOPE, ref)  # type: ignore[no-any-return]
