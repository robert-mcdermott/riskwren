"""Framework versions: what changed from one to the next, what that touches, and moving a
scope across (CMP-10).

A new version of a framework is loaded beside the old, never over it: each has a key of its
own, and the new one says which it follows. Nothing that uses the old version changes when
the new one arrives. A scope moves when its keepers say so, and then what can be carried
goes with it: its decisions about requirements whose code is unchanged, the exceptions to
those requirements, and, for the whole organization, the crosswalks and documents mapped to
them. Where the publisher says a withdrawn code was moved to, or incorporated into, another,
crosswalks follow it there.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.compliance import frameworks
from riskwren.controls.service import CONTROL
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    Baseline,
    Control,
    ControlRequirement,
    DocumentRequirement,
    ExceptionRequest,
    Framework,
    FrameworkMapping,
    PolicyDocument,
    Requirement,
    Scope,
    ScopeFramework,
    ScopeRequirement,
)
from riskwren.events import audit
from riskwren.inventory import access, records

MOVES = ("moved_to", "incorporated_into")


# --- The line of versions -------------------------------------------------------------------


def earlier(session: Session, framework: Framework) -> Framework | None:
    if not framework.follows:
        return None
    return session.scalars(select(Framework).where(Framework.key == framework.follows)).first()


def later(session: Session, framework: Framework) -> list[Framework]:
    return list(
        session.scalars(
            select(Framework).where(Framework.follows == framework.key).order_by(Framework.id)
        )
    )


def line(session: Session, framework: Framework) -> list[Framework]:
    """Every loaded version, oldest first: those it follows, it, and those that follow it."""
    before: list[Framework] = []
    seen = {framework.id}
    step = earlier(session, framework)
    while step is not None and step.id not in seen:
        before.insert(0, step)
        seen.add(step.id)
        step = earlier(session, step)
    after: list[Framework] = []
    queue = later(session, framework)
    while queue:
        step = queue.pop(0)
        if step.id in seen:
            continue
        seen.add(step.id)
        after.append(step)
        queue += later(session, step)
    return [*before, framework, *after]


def _chip(framework: Framework) -> dict[str, Any]:
    return {"key": framework.key, "title": framework.title, "version": framework.version,
            "status": framework.status}  # fmt: skip


def versions(session: Session, framework: Framework) -> dict[str, Any]:
    """What a framework's page says of its versions."""
    found = line(session, framework)
    return {
        "line": [{**_chip(each), "current": each.id == framework.id} for each in found],
        "earlier": _chip(prior) if (prior := earlier(session, framework)) else None,
        "later": [_chip(each) for each in later(session, framework)],
    }


def _is_later(session: Session, old: Framework, new: Framework) -> bool:
    chain = line(session, old)
    return new in chain and chain.index(new) > chain.index(old)


# --- What changed ---------------------------------------------------------------------------


def _citable(session: Session, framework: Framework) -> dict[str, Requirement]:
    return {
        row.code: row
        for row in session.scalars(
            select(Requirement)
            .where(Requirement.framework_id == framework.id, Requirement.is_citable.is_(True))
            .order_by(Requirement.sequence)
        )
    }


def _plain(text: str | None) -> str:
    return " ".join((text or "").split())


def moves(session: Session, old: Framework, new: Framework) -> dict[str, list[tuple[str, str]]]:
    """Where the publisher says each code of the old version went in the new: code → [(how,
    code)]."""
    found: dict[str, list[tuple[str, str]]] = {}
    for row in session.scalars(
        select(FrameworkMapping).where(
            FrameworkMapping.from_key == old.key,
            FrameworkMapping.to_key == new.key,
            FrameworkMapping.relation.in_(MOVES),
        )
    ):
        found.setdefault(row.from_code, []).append((row.relation, row.to_code))
    return found


def _line(row: Requirement) -> dict[str, Any]:
    return {"code": row.code, "title": row.title, "excerpt": frameworks.card(row)["excerpt"]}


def changes(session: Session, old: Framework, new: Framework) -> dict[str, Any]:
    """Requirements added, changed in their title or text, and withdrawn, by code; each
    withdrawn one with where the publisher says it went."""
    before, after = _citable(session, old), _citable(session, new)
    went = moves(session, old, new)
    added = [_line(row) for code, row in after.items() if code not in before]
    withdrawn = [
        {**_line(row), "went": [{"how": how, "code": code} for how, code in went.get(row.code, [])]}
        for code, row in before.items()
        if code not in after
    ]
    changed = []
    same = 0
    for code, row in after.items():
        prior = before.get(code)
        if prior is None:
            continue
        if _plain(prior.text) == _plain(row.text) and _plain(prior.title) == _plain(row.title):
            same += 1
            continue
        changed.append({
            **_line(row),
            "title_before": prior.title,
            "retitled": _plain(prior.title) != _plain(row.title),
        })  # fmt: skip
    return {
        "from": _chip(old),
        "to": _chip(new),
        "added": added,
        "changed": changed,
        "withdrawn": withdrawn,
        "counts": {
            "added": len(added),
            "changed": len(changed),
            "withdrawn": len(withdrawn),
            "same": same,
        },
    }


def compare_one(session: Session, old: Framework, new: Framework, code: str) -> dict[str, Any]:
    """One requirement as it was and as it is, line by line, with the words that differ."""
    from riskwren.policy import compare  # the same comparison documents use

    before = _citable(session, old).get(code)
    after = _citable(session, new).get(code)
    if before is None and after is None:
        raise NotFound(f"Neither version has a requirement {code}.")
    return {
        "code": code,
        "before": {"title": before.title, "text": before.text} if before else None,
        "after": {"title": after.title, "text": after.text} if after else None,
        **compare.compare(before.text if before else "", after.text if after else ""),
    }


def affects(
    session: Session, principal: Principal, old: Framework, new: Framework
) -> dict[str, Any]:
    """What uses the old version, and what moving to the new one would carry or leave."""
    from riskwren.compliance.exceptions import EXCEPTION
    from riskwren.compliance.scopes import SCOPE
    from riskwren.policy.documents import DOCUMENT

    before, after = _citable(session, old), _citable(session, new)
    went = moves(session, old, new)
    by_id = {row.id: row for row in before.values()}
    touched = {
        row.id for code, row in before.items()
        if code not in after or _plain(row.text) != _plain(after[code].text)
    }  # fmt: skip
    held = []
    for row, scope in session.execute(
        select(ScopeFramework, Scope)
        .join(Scope, Scope.id == ScopeFramework.scope_id)
        .where(ScopeFramework.framework_id == old.id)
        .order_by(Scope.name)
    ).all():
        if access.can_see(session, principal, SCOPE, scope):
            baseline = session.get(Baseline, row.baseline_id) if row.baseline_id else None
            held.append({
                **records.chip(SCOPE, scope),
                "baseline": baseline.title if baseline else None,
                "by_agreement": row.agreement_id is not None,
                "can_move": access.can_edit(session, principal, SCOPE, scope)
                and scope.status == "active" and row.agreement_id is None,
            })  # fmt: skip
    mapped = session.execute(
        select(ControlRequirement, Control)
        .join(Control, Control.id == ControlRequirement.control_id)
        .where(ControlRequirement.requirement_id.in_(list(by_id) or [0]))
        .order_by(Control.ref)
    ).all()
    controls: dict[int, dict[str, Any]] = {}
    already = set(
        session.execute(
            select(ControlRequirement.control_id, ControlRequirement.requirement_id).where(
                ControlRequirement.requirement_id.in_([row.id for row in after.values()] or [0])
            )
        ).all()
    )
    carry = stays = 0
    for mapping, control in mapped:
        code = by_id[mapping.requirement_id].code
        targets = [after[code]] if code in after else [
            after[to] for _how, to in went.get(code, []) if to in after
        ]  # fmt: skip
        if not targets:
            stays += 1
        elif any((mapping.control_id, target.id) not in already for target in targets):
            carry += 1
        if mapping.requirement_id not in touched or not access.can_see(
            session, principal, CONTROL, control
        ):
            continue
        entry = controls.setdefault(control.id, {**records.chip(CONTROL, control), "codes": []})
        entry["codes"].append(code)
    exceptions = [
        {**records.chip(EXCEPTION, item), "code": by_id[item.subject_id].code,
         "carries": by_id[item.subject_id].code in after, "status": item.status}
        for item in session.scalars(
            select(ExceptionRequest).where(
                ExceptionRequest.subject_type == "requirement",
                ExceptionRequest.subject_id.in_(list(by_id) or [0]),
                ExceptionRequest.status.in_(("requested", "approved")),
            )
        )
        if access.can_see(session, principal, EXCEPTION, item)
    ]  # fmt: skip
    documents = [
        {**records.chip(DOCUMENT, document), "code": by_id[link.requirement_id].code}
        for link, document in session.execute(
            select(DocumentRequirement, PolicyDocument)
            .join(PolicyDocument, PolicyDocument.id == DocumentRequirement.document_id)
            .where(DocumentRequirement.requirement_id.in_(list(by_id) or [0]))
        ).all()
        if access.can_see(session, principal, DOCUMENT, document)
    ]  # fmt: skip
    return {
        "scopes": held,
        "controls": list(controls.values()),
        "crosswalks": {"carried": carry, "left": stays},
        "exceptions": exceptions,
        "documents": documents,
    }


# --- Moving a scope -------------------------------------------------------------------------


def carry_mappings(session: Session, old: Framework, new: Framework) -> dict[str, int]:
    """Bring the crosswalks and the documents mapped to the old version across to the new,
    for the whole organization: to the same code, or where the publisher says a code went.
    Safe to run again: what is there already is left as it is."""
    before, after = _citable(session, old), _citable(session, new)
    went = moves(session, old, new)
    by_id = {row.id: row for row in before.values()}

    def targets(code: str) -> list[tuple[Requirement, bool]]:
        if code in after:
            return [(after[code], True)]
        return [(after[to], False) for _how, to in went.get(code, []) if to in after]

    counts = {"crosswalks": 0, "documents": 0}
    now = utc_now()
    with audit.operation(session, "framework.carry", was=old.title, now=new.title):
        have = {
            (row.control_id, row.requirement_id)
            for row in session.scalars(
                select(ControlRequirement).where(
                    ControlRequirement.requirement_id.in_([row.id for row in after.values()] or [0])
                )
            )
        }
        for mapping in session.scalars(
            select(ControlRequirement).where(
                ControlRequirement.requirement_id.in_(list(by_id) or [0])
            )
        ):
            for target, same in targets(by_id[mapping.requirement_id].code):
                if (mapping.control_id, target.id) in have:
                    continue
                have.add((mapping.control_id, target.id))
                session.add(
                    ControlRequirement(
                        control_id=mapping.control_id, requirement_id=target.id,
                        coverage=mapping.coverage if same else "partial",
                        note=mapping.note if same else (
                            f"Carried from {by_id[mapping.requirement_id].code} of {old.title}."
                        )[:300],
                        source="carried", created_by=mapping.created_by, created_at=now,
                    )
                )  # fmt: skip
                counts["crosswalks"] += 1
        answered = {
            (row.document_id, row.requirement_id)
            for row in session.scalars(
                select(DocumentRequirement).where(
                    DocumentRequirement.requirement_id.in_(
                        [row.id for row in after.values()] or [0]
                    )
                )
            )
        }
        for link in session.scalars(
            select(DocumentRequirement).where(
                DocumentRequirement.requirement_id.in_(list(by_id) or [0])
            )
        ):
            for target, _same in targets(by_id[link.requirement_id].code):
                if (link.document_id, target.id) in answered:
                    continue
                answered.add((link.document_id, target.id))
                session.add(
                    DocumentRequirement(
                        document_id=link.document_id, requirement_id=target.id, note=link.note,
                        created_by=link.created_by, created_at=now,
                    )
                )  # fmt: skip
                counts["documents"] += 1
        session.flush()
    return counts


def move(
    session: Session, principal: Principal, scope: Scope, from_key: str, to_key: str
) -> dict[str, Any]:
    """Hold a scope to a later version in place of the one it holds, carrying what can be
    carried. Returns what was carried, and what was left behind."""
    from riskwren.compliance import scopes

    scopes._editable(session, principal, scope)
    errors = records.Errors()
    old = new = None
    try:
        old = frameworks.by_key(session, from_key)
    except NotFound as missing:
        errors.add("from", str(missing))
    try:
        new = frameworks.by_key(session, to_key)
        if new.status != "active":
            errors.add("to", f"{new.title} is retired.")
    except NotFound as missing:
        errors.add("to", str(missing))
    if old is not None and new is not None and not _is_later(session, old, new):
        errors.add("to", f"{new.title} is not a later version of {old.title}.")
    if errors:
        raise Invalid("The scope was not moved.", errors)
    assert old is not None and new is not None
    held = session.scalars(
        select(ScopeFramework).where(
            ScopeFramework.scope_id == scope.id, ScopeFramework.framework_id == old.id
        )
    ).first()
    if held is None:
        raise Conflict(f"{scope.name} is not held to {old.title}.")
    if held.agreement_id is not None:
        raise Conflict(
            f"{scope.name} is held to {old.title} because an agreement imposes it. Name the new "
            "version as the agreement's terms instead."
        )
    before, after = _citable(session, old), _citable(session, new)
    by_id = {row.id: row for row in before.values()}
    summary: dict[str, Any] = {"decisions": 0, "decisions_left": 0, "exceptions": 0,
                               "exceptions_left": 0}  # fmt: skip
    with audit.operation(session, "scope.move", was=old.title, now=new.title):
        target = session.scalars(
            select(ScopeFramework).where(
                ScopeFramework.scope_id == scope.id, ScopeFramework.framework_id == new.id
            )
        ).first()
        baseline = None
        if held.baseline_id is not None:
            was = session.get(Baseline, held.baseline_id)
            baseline = session.scalars(
                select(Baseline).where(Baseline.framework_id == new.id, Baseline.key == was.key)
            ).first() if was else None  # fmt: skip
        if target is None:
            target = ScopeFramework(
                scope_id=scope.id, framework_id=new.id,
                baseline_id=baseline.id if baseline else None,
            )  # fmt: skip
            session.add(target)
        summary["baseline"] = baseline.title if baseline else None
        decided = {
            row.requirement_id
            for row in session.scalars(
                select(ScopeRequirement).where(ScopeRequirement.scope_id == scope.id)
            )
        }
        for decision in session.scalars(
            select(ScopeRequirement).where(
                ScopeRequirement.scope_id == scope.id,
                ScopeRequirement.requirement_id.in_(list(by_id) or [0]),
            )
        ).all():
            code = by_id[decision.requirement_id].code
            if code in after and after[code].id not in decided:
                # The same decision, now about the same requirement in the new version.
                decision.requirement_id = after[code].id
                summary["decisions"] += 1
            else:
                summary["decisions_left"] += 1
                session.delete(decision)
        for item in session.scalars(
            select(ExceptionRequest).where(
                ExceptionRequest.subject_type == "requirement",
                ExceptionRequest.subject_id.in_(list(by_id) or [0]),
                ExceptionRequest.scope_id == scope.id,
                ExceptionRequest.status.in_(("requested", "approved")),
            )
        ).all():
            code = by_id[item.subject_id].code
            if code in after:
                item.subject_id = after[code].id
                summary["exceptions"] += 1
            else:
                summary["exceptions_left"] += 1
        session.delete(held)
        records.touch(session, scope)
        session.flush()
    summary.update(carry_mappings(session, old, new))
    summary["from"], summary["to"] = _chip(old), _chip(new)
    return summary


# --- A new version of a framework of the organization's own -------------------------------


def start_version(
    session: Session, principal: Principal, framework: Framework, values: dict[str, Any]
) -> Framework:
    """Copy a framework of the organization's own into a new version beside it, to be
    edited: an agreement's terms as renewed, an internal standard as revised."""
    if not principal.configures:
        raise PermissionDenied("Only those who run the program can change frameworks.")
    if framework.origin != "local":
        raise Conflict(
            "A published framework's new version is loaded from its publisher's pack, not "
            "copied here."
        )
    title = records.text(values.get("title"))
    version = records.text(values.get("version"))
    errors = records.Errors()
    if not title:
        errors.add("title", "Give the new version a title.")
    if errors:
        raise Invalid("The new version was not started.", errors)
    assert title is not None
    made = frameworks.create(
        session, principal,
        {"title": title, "version": version, "kind": framework.kind,
         "summary": framework.summary, "publisher": framework.publisher},
    )  # fmt: skip
    with audit.operation(session, "framework.version", follows=framework.key):
        made.follows = framework.key
        rows = list(
            session.scalars(
                select(Requirement)
                .where(Requirement.framework_id == framework.id)
                .order_by(Requirement.depth, Requirement.sequence)
            )
        )
        copies: dict[int, Requirement] = {}
        for row in rows:
            copy = Requirement(
                framework_id=made.id,
                parent_id=copies[row.parent_id].id if row.parent_id in copies else None,
                code=row.code, title=row.title, text=row.text, guidance=row.guidance,
                kind=row.kind, position=row.position, depth=row.depth, sequence=row.sequence,
                is_citable=row.is_citable, status=row.status,
            )  # fmt: skip
            session.add(copy)
            session.flush()
            copies[row.id] = copy
        made.requirement_count = framework.requirement_count
        made.citable_count = framework.citable_count
        session.flush()
    return made
