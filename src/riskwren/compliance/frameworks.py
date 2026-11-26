"""Frameworks and their requirements: reading them, and keeping the organization's own.

A framework loaded from a pack is published content and is not edited here. A framework the
organization enters for itself, such as an agreement's terms or an internal standard, is its
own to keep: requirements are added, reworded, and removed, and each change is recorded.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from sqlalchemy import Integer, func, or_, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import Baseline, BaselineRequirement, Framework, Requirement
from riskwren.db.models.compliance import FRAMEWORK_KINDS, FRAMEWORK_STATUSES
from riskwren.events import audit
from riskwren.inventory import records

KIND_LABELS = {
    "standard": "Standard",
    "regulation": "Regulation",
    "agreement": "Agreement",
    "internal": "Internal standard",
}
POLICY_LABELS = {
    "verbatim": "The source's own text, which is in the public domain",
    "attributed": "The source's text, used with attribution",
    "identifiers": "Codes and RiskWren's own labels; the source's text is not carried",
    "summary": "Codes, titles, and RiskWren's own summaries",
    "own": "Entered by this organization",
}
EXCERPT = 240


def _require(principal: Principal) -> None:
    if not principal.configures:
        raise PermissionDenied("Only those who run the program can change frameworks.")


def _local(framework: Framework) -> None:
    if framework.origin != "local":
        raise Conflict(
            f"{framework.title} is published content and is not edited here. "
            "Enter a framework of your own to keep requirements of your own."
        )


# --- Reading ------------------------------------------------------------------------------


def by_key(session: Session, key: str) -> Framework:
    found = session.scalars(select(Framework).where(Framework.key == key)).first()
    if found is None:
        raise NotFound(f"There is no framework {key!r}.")
    return found


def all_(session: Session, *, retired: bool = False) -> list[Framework]:
    statement = select(Framework).order_by(Framework.origin.desc(), Framework.title)
    if not retired:
        statement = statement.where(Framework.status == "active")
    return list(session.scalars(statement))


def baselines(session: Session, framework: Framework) -> list[Baseline]:
    return list(
        session.scalars(
            select(Baseline).where(Baseline.framework_id == framework.id).order_by(Baseline.id)
        )
    )


def view(session: Session, principal: Principal, framework: Framework) -> dict[str, Any]:
    local = framework.origin == "local"
    return {
        "key": framework.key,
        "title": framework.title,
        "version": framework.version,
        "kind": framework.kind,
        "kind_label": KIND_LABELS[framework.kind],
        "summary": framework.summary,
        "publisher": framework.publisher,
        "license": framework.license,
        "text_policy": framework.text_policy,
        "text_policy_label": POLICY_LABELS[framework.text_policy],
        "attribution": framework.attribution,
        "source_url": framework.source_url,
        "built_from": framework.built_from,
        "pack_version": framework.pack_version,
        "origin": framework.origin,
        "status": framework.status,
        "requirement_count": framework.requirement_count,
        "citable_count": framework.citable_count,
        "updated_at": framework.updated_at,
        "baselines": [
            {"key": row.key, "title": row.title, "count": row.requirement_count}
            for row in baselines(session, framework)
        ],
        "can": {"edit": principal.configures and local, "retire": principal.configures},
    }


def _excerpt(text: str | None) -> str | None:
    if not text:
        return None
    flat = " ".join(text.split())
    return flat if len(flat) <= EXCERPT else flat[: EXCERPT - 1].rstrip() + "…"


def card(row: Requirement, children: int = 0) -> dict[str, Any]:
    return {
        "id": row.id,
        "code": row.code,
        "title": row.title,
        "excerpt": _excerpt(row.text),
        "kind": row.kind,
        "is_citable": row.is_citable,
        "depth": row.depth,
        "children": children,
    }


def _child_counts(session: Session, ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    rows = session.execute(
        select(Requirement.parent_id, func.count())
        .where(Requirement.parent_id.in_(ids))
        .group_by(Requirement.parent_id)
    ).all()
    return {int(parent): int(count) for parent, count in rows}


def find(session: Session, framework: Framework, code: str) -> Requirement:
    found = session.scalars(
        select(Requirement).where(
            Requirement.framework_id == framework.id, Requirement.code == code
        )
    ).first()
    if found is None:
        raise NotFound(f"{framework.title} has no requirement {code!r}.")
    return found


def listing(
    session: Session,
    framework: Framework,
    *,
    parent: str | None = None,
    query: str | None = None,
    baseline: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """One level of the tree, or, with words or a baseline, the requirements that match
    wherever they sit."""
    conditions = [Requirement.framework_id == framework.id]
    words = (query or "").strip()
    flat = bool(words or baseline)
    if words:
        like = f"%{words.lower()}%"
        conditions.append(
            or_(
                func.lower(Requirement.code).like(like),
                func.lower(func.coalesce(Requirement.title, "")).like(like),
                func.lower(func.coalesce(Requirement.text, "")).like(like),
            )
        )
    if baseline:
        chosen = session.scalars(
            select(Baseline).where(Baseline.framework_id == framework.id, Baseline.key == baseline)
        ).first()
        if chosen is None:
            raise NotFound(f"{framework.title} has no baseline {baseline!r}.")
        conditions.append(
            Requirement.id.in_(
                select(BaselineRequirement.requirement_id).where(
                    BaselineRequirement.baseline_id == chosen.id
                )
            )
        )
    if not flat:
        parent_id = find(session, framework, parent).id if parent else None
        conditions.append(
            Requirement.parent_id == parent_id
            if parent_id is not None
            else Requirement.parent_id.is_(None)
        )
    total = session.execute(
        select(func.count()).select_from(Requirement).where(*conditions)
    ).scalar_one()
    order = (Requirement.id,) if flat else (Requirement.position, Requirement.id)
    rows = list(
        session.scalars(
            select(Requirement).where(*conditions).order_by(*order).limit(limit).offset(offset)
        )
    )
    counts = _child_counts(session, [row.id for row in rows])
    return [card(row, counts.get(row.id, 0)) for row in rows], int(total)


def detail(session: Session, framework: Framework, code: str) -> dict[str, Any]:
    """One requirement in full, with where it sits and what is beneath it."""
    row = find(session, framework, code)
    trail = []
    above = row.parent_id
    while above is not None:
        parent = session.get(Requirement, above)
        assert parent is not None
        trail.append({"code": parent.code, "title": parent.title})
        above = parent.parent_id
    children = list(
        session.scalars(
            select(Requirement)
            .where(Requirement.parent_id == row.id)
            .order_by(Requirement.position, Requirement.id)
        )
    )
    counts = _child_counts(session, [child.id for child in children])
    member_of = session.execute(
        select(Baseline.key, Baseline.title)
        .join(BaselineRequirement, BaselineRequirement.baseline_id == Baseline.id)
        .where(BaselineRequirement.requirement_id == row.id)
        .order_by(Baseline.id)
    ).all()
    return {
        **card(row, len(children)),
        "text": row.text,
        "guidance": row.guidance,
        "status": row.status,
        "framework": {"key": framework.key, "title": framework.title},
        "trail": list(reversed(trail)),
        "children_list": [card(child, counts.get(child.id, 0)) for child in children],
        "baselines": [{"key": key, "title": title} for key, title in member_of],
    }


# --- The organization's own frameworks ------------------------------------------------------


def slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")[:60]


def _apply(framework: Framework, values: Mapping[str, Any], errors: records.Errors) -> None:
    if "title" in values:
        title = records.text(values["title"])
        if not title or len(title) > 200:
            errors.add("title", "Give it a name of up to 200 characters.")
        else:
            framework.title = title
    if "kind" in values and values["kind"] is not None:
        if values["kind"] not in FRAMEWORK_KINDS:
            errors.add("kind", f"Use one of: {', '.join(FRAMEWORK_KINDS)}.")
        else:
            framework.kind = values["kind"]
    for name, limit in (("version", 120), ("publisher", 200)):
        if name in values:
            cleaned = records.text(values[name])
            if cleaned and len(cleaned) > limit:
                errors.add(name, f"Keep this to {limit} characters.")
            else:
                setattr(framework, name, cleaned)
    if "summary" in values:
        framework.summary = records.text(values["summary"])
    if "source_url" in values:
        framework.source_url = records.url(values["source_url"], "source_url", errors)


def create(session: Session, principal: Principal, values: Mapping[str, Any]) -> Framework:
    """Enter a framework of the organization's own: an agreement's terms, a sponsor's
    requirements, an internal standard. Its requirements are added to it afterwards."""
    _require(principal)
    now = utc_now()
    framework = Framework(
        kind="agreement", text_policy="own", origin="local", status="active",
        requirement_count=0, citable_count=0, created_by=principal.account_id,
        created_at=now, updated_at=now,
    )  # fmt: skip
    errors = records.Errors()
    _apply(framework, {"title": None, **values}, errors)
    key = slug(str(values.get("key") or values.get("title") or ""))
    if not key:
        errors.add("key", "Give it a short key: letters, digits, and hyphens.")
    elif session.scalars(select(Framework.id).where(Framework.key == key)).first():
        errors.add("key", f"There is already a framework with the key {key}.")
    if errors:
        raise Invalid("The framework was not saved.", errors)
    framework.key = key
    with audit.operation(session, "framework.create"):
        session.add(framework)
        session.flush()
    return framework


def update(
    session: Session, principal: Principal, framework: Framework, values: Mapping[str, Any]
) -> Framework:
    """Change what a framework of the organization's own says about itself, or retire or
    restore any framework. A retired framework is kept, and is offered to nothing new."""
    _require(principal)
    errors = records.Errors()
    described = {key: value for key, value in values.items() if key != "status"}
    if described:
        _local(framework)
        _apply(framework, described, errors)
    status = values.get("status")
    if status is not None:
        if status not in FRAMEWORK_STATUSES:
            errors.add("status", "Use active or retired.")
        else:
            framework.status = status
    if errors:
        session.expire(framework)
        raise Invalid("The framework was not saved.", errors)
    with audit.operation(session, "framework.edit"):
        framework.updated_at = utc_now()
        session.flush()
    return framework


def _recount(session: Session, framework: Framework) -> None:
    total, citable = session.execute(
        select(func.count(), func.coalesce(func.sum(func.cast(Requirement.is_citable, Integer)), 0))
        .select_from(Requirement)
        .where(Requirement.framework_id == framework.id)
    ).one()
    framework.requirement_count, framework.citable_count = int(total), int(citable)
    framework.updated_at = utc_now()
    session.flush()


def _requirement_values(
    session: Session,
    framework: Framework,
    row: Requirement,
    values: Mapping[str, Any],
    errors: records.Errors,
    *,
    creating: bool,
) -> None:
    if "code" in values or creating:
        code = records.text(values.get("code"))
        if not code or len(code) > 120:
            errors.add("code", "Give it a code of up to 120 characters, such as 4.2 or DUA-7.")
        elif code != row.code:
            taken = session.scalars(
                select(Requirement.id).where(
                    Requirement.framework_id == framework.id, Requirement.code == code
                )
            ).first()
            if taken is not None:
                errors.add("code", f"{code} is already a requirement of this framework.")
            else:
                row.code = code
    if "title" in values:
        title = records.text(values["title"])
        if title and len(title) > 300:
            errors.add("title", "Keep the title to 300 characters.")
        else:
            row.title = title
    if "text" in values:
        row.text = records.text(values["text"])
    if "guidance" in values:
        row.guidance = records.text(values["guidance"])
    if "is_citable" in values and values["is_citable"] is not None:
        row.is_citable = bool(values["is_citable"])
    if row.is_citable and not (row.title or row.text) and "code" not in errors:
        errors.add("text", "Say what is required, or give it a title.")


def _said(row: Requirement) -> dict[str, Any]:
    return {"code": row.code, "title": row.title, "text": row.text, "guidance": row.guidance,
            "is_citable": row.is_citable}  # fmt: skip


def add_requirement(
    session: Session, principal: Principal, framework: Framework, values: Mapping[str, Any]
) -> Requirement:
    _require(principal)
    _local(framework)
    errors = records.Errors()
    parent = None
    if values.get("parent"):
        try:
            parent = find(session, framework, str(values["parent"]))
        except NotFound:
            errors.add("parent", f"There is no requirement {values['parent']!r} to put it under.")
    row = Requirement(
        framework_id=framework.id, code="", is_citable=True, status="active",
        parent_id=parent.id if parent else None, depth=parent.depth + 1 if parent else 0,
    )  # fmt: skip
    _requirement_values(session, framework, row, values, errors, creating=True)
    if errors:
        raise Invalid("The requirement was not added.", errors)
    last = session.execute(
        select(func.max(Requirement.position)).where(
            Requirement.framework_id == framework.id,
            Requirement.parent_id == row.parent_id
            if row.parent_id is not None
            else Requirement.parent_id.is_(None),
        )
    ).scalar_one()
    row.position = 0 if last is None else int(last) + 1
    with audit.operation(session, "requirement.add"):
        session.add(row)
        session.flush()
        _recount(session, framework)
        audit.record(
            session, "requirement.added", framework,
            changes={key: [None, value] for key, value in _said(row).items() if value is not None},
        )  # fmt: skip
    return row


def update_requirement(
    session: Session,
    principal: Principal,
    framework: Framework,
    row: Requirement,
    values: Mapping[str, Any],
) -> Requirement:
    _require(principal)
    _local(framework)
    before = _said(row)
    errors = records.Errors()
    _requirement_values(session, framework, row, values, errors, creating=False)
    if errors:
        session.expire(row)
        raise Invalid("The requirement was not saved.", errors)
    after = _said(row)
    changed = {key: [before[key], after[key]] for key in after if before[key] != after[key]}
    if changed:
        with audit.operation(session, "requirement.edit"):
            session.flush()
            _recount(session, framework)
            audit.record(
                session, "requirement.changed", framework,
                changes={"code": [before["code"], after["code"]], **changed},
            )  # fmt: skip
    return row


def remove_requirement(
    session: Session, principal: Principal, framework: Framework, row: Requirement
) -> None:
    _require(principal)
    _local(framework)
    beneath = session.scalars(select(Requirement.id).where(Requirement.parent_id == row.id)).first()
    if beneath is not None:
        raise Conflict("Remove the requirements beneath this one first.")
    with audit.operation(session, "requirement.remove"):
        said = _said(row)
        session.delete(row)
        session.flush()
        _recount(session, framework)
        audit.record(
            session, "requirement.removed", framework,
            changes={key: [value, None] for key, value in said.items() if value is not None},
        )  # fmt: skip


LINE = re.compile(r"^(\S+)(?:\t+|\s{1,})(.*)$")


def paste(
    session: Session, principal: Principal, framework: Framework, text: str, *, dry_run: bool
) -> dict[str, Any]:
    """Add many requirements at once from pasted lines: a code, then what it requires. A
    line that begins with spaces or a tab continues the requirement above it. Nothing is
    added unless every line can be."""
    _require(principal)
    _local(framework)
    have = set(
        session.scalars(select(Requirement.code).where(Requirement.framework_id == framework.id))
    )
    problems: list[dict[str, Any]] = []
    wanted: list[dict[str, str]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        if raw[0] in " \t" and wanted:
            wanted[-1]["text"] = f"{wanted[-1]['text']}\n{raw.strip()}"
            continue
        matched = LINE.match(raw.strip())
        if matched is None:
            problems.append(
                {"row": number, "message": "A line is a code, a space, then what it requires."}
            )
            continue
        code, said = matched.group(1), matched.group(2).strip()
        if len(code) > 120:
            problems.append({"row": number, "message": "A code is at most 120 characters."})
        elif code in have or any(item["code"] == code for item in wanted):
            problems.append({"row": number, "message": f"{code} is already a requirement."})
        else:
            wanted.append({"code": code, "text": said})
    if not wanted and not problems:
        problems.append({"row": 0, "message": "There is nothing to add."})
    report = {
        "dry_run": dry_run,
        "applied": False,
        "would_add": len(wanted),
        "problems": problems,
        "sample": [item["code"] for item in wanted[:5]],
    }
    if problems or dry_run:
        return report
    last = session.execute(
        select(func.max(Requirement.position)).where(
            Requirement.framework_id == framework.id, Requirement.parent_id.is_(None)
        )
    ).scalar_one()
    start = 0 if last is None else int(last) + 1
    with audit.operation(session, "requirement.paste"):
        session.add_all(
            Requirement(
                framework_id=framework.id, code=item["code"], text=item["text"], depth=0,
                position=start + index, is_citable=True, status="active",
            )
            for index, item in enumerate(wanted)
        )  # fmt: skip
        session.flush()
        _recount(session, framework)
        audit.record(
            session, "requirement.added", framework,
            changes={"count": [None, len(wanted)], "codes": [None, [w["code"] for w in wanted]]},
        )  # fmt: skip
    return {**report, "applied": True}
