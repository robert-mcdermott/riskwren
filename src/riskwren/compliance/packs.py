"""Framework packs: checking one whole, and loading it (see spec/content-packs.md).

A pack is one JSON document: a header that names the framework, its publisher, its license,
and its text policy, then a tree of requirements with stable codes and, optionally,
baselines. A pack is checked completely before anything is written, every problem is
reported together, and a pack with any problem is refused whole.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from importlib import resources
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid
from riskwren.db.models import Baseline, BaselineRequirement, Framework, Requirement
from riskwren.db.models.compliance import FRAMEWORK_KINDS
from riskwren.events import audit

BUILTIN = ("nist-csf", "nist-800-53", "nist-800-171", "hipaa-security")
# What a pack may declare. ``own`` is for frameworks entered here, never for a pack.
PACK_POLICIES = ("verbatim", "attributed", "identifiers", "summary")
# Under ``identifiers`` a pack carries codes and RiskWren's own short labels, and none of the
# source's wording: no text, no guidance, and labels short enough that they cannot be it.
LABEL_LIMIT = 80
SUMMARY_LIMIT = 240
MAX_DEPTH = 8
FIELDS = {"code", "title", "text", "guidance", "kind", "group", "children"}


def builtin(key: str) -> dict[str, Any]:
    path = resources.files("riskwren.resources").joinpath("packs", "frameworks", f"{key}.json")
    return dict(json.loads(path.read_text("utf-8")))


def walk(items: list[Any], depth: int = 0) -> Iterator[tuple[dict[str, Any], int]]:
    for item in items:
        if isinstance(item, dict):
            yield item, depth
            children = item.get("children", [])
            if isinstance(children, list):
                yield from walk(children, depth + 1)


def digest(pack: dict[str, Any]) -> str:
    """A fingerprint of what the pack requires, so that two loads can be told apart."""
    body = {"requirements": pack.get("requirements", []), "baselines": pack.get("baselines", [])}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def policy_problems(pack: dict[str, Any]) -> list[str]:
    """Where a pack carries text its declared policy does not allow."""
    policy = pack.get("pack", {}).get("text_policy")
    found: list[str] = []
    for item, _ in walk(pack.get("requirements", [])):
        code = item.get("code", "?")
        if policy == "identifiers":
            if item.get("text") or item.get("guidance"):
                found.append(f"{code}: an identifiers pack carries no text or guidance.")
            if len(str(item.get("title") or "")) > LABEL_LIMIT:
                found.append(f"{code}: a label is at most {LABEL_LIMIT} characters.")
        elif policy == "summary":
            if item.get("guidance"):
                found.append(f"{code}: a summary pack carries no guidance.")
            if len(str(item.get("text") or "")) > SUMMARY_LIMIT:
                found.append(f"{code}: a summary is at most {SUMMARY_LIMIT} characters.")
    if policy == "attributed" and not str(pack.get("pack", {}).get("attribution") or "").strip():
        found.append("An attributed pack says how its source is to be credited.")
    return found


def problems(pack: Any) -> list[str]:
    """Everything wrong with a pack, or an empty list."""
    if not isinstance(pack, dict) or not isinstance(pack.get("pack"), dict):
        return ["A pack is an object with a `pack` header and a list of `requirements`."]
    head = pack["pack"]
    found: list[str] = []
    if head.get("kind") != "framework":
        found.append("pack.kind must be `framework`.")
    for name, limit in (("key", 80), ("title", 200)):
        value = head.get(name)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            found.append(f"pack.{name} is needed, in up to {limit} characters.")
    key = head.get("key")
    if isinstance(key, str) and not all(c.isalnum() or c in "-_." for c in key):
        found.append("pack.key uses letters, digits, hyphens, underscores, and dots.")
    if head.get("framework_kind", "standard") not in FRAMEWORK_KINDS:
        found.append(f"pack.framework_kind is one of: {', '.join(FRAMEWORK_KINDS)}.")
    if head.get("text_policy") not in PACK_POLICIES:
        found.append(f"pack.text_policy is one of: {', '.join(PACK_POLICIES)}.")
    for name in ("publisher", "license"):
        if not str(head.get(name) or "").strip():
            found.append(f"pack.{name} is needed: a framework says where it comes from.")
    items = pack.get("requirements")
    if not isinstance(items, list) or not items:
        return [*found, "A pack has at least one requirement."]
    seen: set[str] = set()
    citable = 0
    for item, depth in walk(items):
        code = item.get("code")
        if not isinstance(code, str) or not code.strip() or len(code) > 120:
            found.append(f"A requirement needs a code of up to 120 characters (near {code!r}).")
            continue
        if code in seen:
            found.append(f"{code}: the code is used twice.")
        seen.add(code)
        if depth >= MAX_DEPTH:
            found.append(f"{code}: requirements nest at most {MAX_DEPTH} deep.")
        unknown = set(item) - FIELDS
        if unknown:
            found.append(f"{code}: unknown field {sorted(unknown)[0]!r}.")
        if len(str(item.get("title") or "")) > 300:
            found.append(f"{code}: a title is at most 300 characters.")
        for name in ("title", "text", "guidance", "kind"):
            if item.get(name) is not None and not isinstance(item[name], str):
                found.append(f"{code}: {name} is text.")
        if not isinstance(item.get("children", []), list):
            found.append(f"{code}: children is a list.")
        if not item.get("group"):
            citable += 1
            if not (item.get("text") or item.get("title")):
                found.append(f"{code}: a requirement that can be cited has a title or text.")
    if not citable:
        found.append("A pack has at least one requirement that can be cited.")
    keys: set[str] = set()
    for baseline in pack.get("baselines", []) or []:
        name = baseline.get("key") if isinstance(baseline, dict) else None
        if not isinstance(name, str) or not name or name in keys:
            found.append(f"A baseline needs a key of its own (near {name!r}).")
            continue
        keys.add(name)
        if not str(baseline.get("title") or "").strip():
            found.append(f"Baseline {name}: a title is needed.")
        missing = [code for code in baseline.get("codes", []) if code not in seen]
        if missing:
            found.append(f"Baseline {name}: {missing[0]!r} is not a requirement of this pack.")
    return [*found, *policy_problems(pack)][:50]


def _place(
    session: Session, framework: Framework, items: list[dict[str, Any]]
) -> tuple[dict[str, Requirement], int]:
    """Write the tree, a level at a time so that each row knows its parent."""
    rows: dict[str, Requirement] = {}
    citable = 0
    level: list[tuple[dict[str, Any], Requirement | None]] = [(item, None) for item in items]
    depth = 0
    while level:
        made = []
        positions: dict[int | None, int] = {}
        for item, parent in level:
            parent_id = parent.id if parent is not None else None
            position = positions.get(parent_id, 0)
            positions[parent_id] = position + 1
            row = Requirement(
                framework_id=framework.id,
                parent_id=parent_id,
                code=item["code"].strip(),
                title=(item.get("title") or "").strip() or None,
                text=item.get("text") or None,
                guidance=item.get("guidance") or None,
                kind=item.get("kind") or None,
                position=position,
                depth=depth,
                is_citable=not item.get("group"),
                status="active",
            )
            session.add(row)
            rows[row.code] = row
            citable += row.is_citable
            made.append((item, row))
        session.flush()
        level = [(child, row) for item, row in made for child in item.get("children", [])]
        depth += 1
    return rows, citable


def load(session: Session, pack: dict[str, Any], *, account_id: int | None = None) -> Framework:
    """Load a framework from a pack. Refused whole if anything is wrong with it, and refused
    if a framework with its key is already here: a new version is loaded beside the old
    (wave 4), never over it."""
    found = problems(pack)
    if found:
        raise Invalid("The pack was not loaded.", {"pack": " ".join(found[:8])})
    head = pack["pack"]
    if session.scalars(select(Framework.id).where(Framework.key == head["key"])).first():
        raise Conflict(f"The framework {head['key']} is already loaded.")
    now = utc_now()
    with audit.operation(session, "framework.load", pack=head["key"]):
        framework = Framework(
            key=head["key"].strip(),
            title=head["title"].strip(),
            version=head.get("version"),
            kind=head.get("framework_kind", "standard"),
            summary=head.get("summary"),
            publisher=head.get("publisher"),
            license=head.get("license"),
            text_policy=head["text_policy"],
            attribution=head.get("attribution"),
            source_url=head.get("source_url"),
            built_from=head.get("built_from"),
            pack_version=head.get("pack_version"),
            origin="pack",
            status="active",
            digest=digest(pack),
            created_by=account_id,
            created_at=now,
            updated_at=now,
        )
        session.add(framework)
        session.flush()
        rows, citable = _place(session, framework, pack["requirements"])
        for item in pack.get("baselines", []) or []:
            codes = list(dict.fromkeys(item.get("codes", [])))
            baseline = Baseline(
                framework_id=framework.id,
                key=item["key"],
                title=item["title"],
                requirement_count=len(codes),
            )
            session.add(baseline)
            session.flush()
            session.add_all(
                BaselineRequirement(baseline_id=baseline.id, requirement_id=rows[code].id)
                for code in codes
            )
        framework.requirement_count, framework.citable_count = len(rows), citable
        session.flush()
    return framework


def install(session: Session, keys: tuple[str, ...] = BUILTIN) -> int:
    """Load whichever built-in frameworks are not here yet. Safe to run again."""
    have = set(session.scalars(select(Framework.key)))
    added = 0
    for key in keys:
        if key not in have:
            load(session, builtin(key))
            added += 1
    return added
