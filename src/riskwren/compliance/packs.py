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
from riskwren.db.models import (
    Baseline,
    BaselineRequirement,
    Framework,
    FrameworkMapping,
    Requirement,
)
from riskwren.db.models.compliance import FRAMEWORK_KINDS, MAPPING_RELATIONS
from riskwren.events import audit

BUILTIN = ("nist-csf", "nist-800-53", "nist-800-171", "hipaa-security")
# Shipped, and loaded when someone asks: an earlier version that some programs still name.
OPTIONAL = ("nist-800-53-r4",)
AVAILABLE = BUILTIN + OPTIONAL
KEY_CHARACTERS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
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
    found += relation_problems(pack, seen)
    return [*found, *policy_problems(pack)][:50]


def relation_problems(pack: dict[str, Any], codes: set[str]) -> list[str]:
    """What a pack says of other frameworks: the version it follows, where codes of that
    version went, and how its requirements stand to another framework's."""
    found: list[str] = []
    follows = pack["pack"].get("follows")
    if follows is not None and (
        not isinstance(follows, str) or not follows or not set(follows) <= KEY_CHARACTERS
    ):
        found.append("pack.follows is the key of the version this one follows.")
    moved = pack.get("moved", [])
    if moved and follows is None:
        found.append("moved says where codes of an earlier version went: name it in pack.follows.")
    if not isinstance(moved, list):
        return [*found, "moved is a list of [earlier code, relation, code here]."]
    for entry in moved:
        if (
            not isinstance(entry, list)
            or len(entry) != 3
            or not all(isinstance(part, str) and part for part in entry)
        ):
            found.append(f"moved: {entry!r} is not [earlier code, relation, code here].")
        elif entry[1] not in ("moved_to", "incorporated_into"):
            found.append(f"moved: {entry[1]!r} is moved_to or incorporated_into.")
        elif entry[2] not in codes:
            found.append(f"moved: {entry[2]!r} is not a requirement of this pack.")
    mappings = pack.get("mappings", [])
    if not isinstance(mappings, list):
        return [*found, "mappings is a list of {framework, relation, pairs}."]
    for mapping in mappings:
        if not isinstance(mapping, dict) or not isinstance(mapping.get("pairs"), list):
            found.append("A mapping names a framework, a relation, and its pairs.")
            continue
        other = mapping.get("framework")
        if not isinstance(other, str) or not other or not set(other) <= KEY_CHARACTERS:
            found.append("A mapping names the key of the other framework.")
        if mapping.get("relation") not in MAPPING_RELATIONS:
            found.append(f"A mapping's relation is one of: {', '.join(MAPPING_RELATIONS)}.")
        for pair in mapping["pairs"]:
            if (
                not isinstance(pair, list)
                or len(pair) != 2
                or not all(isinstance(part, str) and part for part in pair)
            ):
                found.append(f"A mapping pair is [code here, code there], not {pair!r}.")
            elif pair[0] not in codes:
                found.append(f"A mapping names {pair[0]!r}, which is not a requirement here.")
    return found


def relate(session: Session, pack: dict[str, Any]) -> int:
    """Keep what a pack says of other frameworks, adding only what is not here already.
    Returns how many were added."""
    head = pack["pack"]
    key = head["key"].strip()
    wanted: set[tuple[str, str, str, str, str]] = set()
    follows = head.get("follows")
    for old, relation, new in pack.get("moved", []) or []:
        wanted.add((follows, old, relation, key, new))
    for mapping in pack.get("mappings", []) or []:
        for here, there in mapping["pairs"]:
            wanted.add((key, here, mapping["relation"], mapping["framework"], there))
    if not wanted:
        return 0
    have = set(
        session.execute(
            select(
                FrameworkMapping.from_key, FrameworkMapping.from_code, FrameworkMapping.relation,
                FrameworkMapping.to_key, FrameworkMapping.to_code,
            ).where(FrameworkMapping.pack_key == key)
        ).all()
    )  # fmt: skip
    fresh = sorted(wanted - have)
    session.add_all(
        FrameworkMapping(from_key=a, from_code=b, relation=c, to_key=d, to_code=e, pack_key=key)
        for a, b, c, d, e in fresh
    )
    session.flush()
    return len(fresh)


def _place(
    session: Session, framework: Framework, items: list[dict[str, Any]]
) -> tuple[dict[str, Requirement], int]:
    """Write the tree, a level at a time so that each row knows its parent."""
    rows: dict[str, Requirement] = {}
    citable = 0
    order = {item["code"].strip(): place for place, (item, _) in enumerate(walk(items))}
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
                sequence=order[item["code"].strip()],
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
            follows=head.get("follows"),
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
        relate(session, pack)
        session.flush()
    return framework


def install(session: Session, keys: tuple[str, ...] = BUILTIN) -> int:
    """Load whichever built-in frameworks are not here yet. Safe to run again. A built-in
    framework already loaded gains what a later release of its pack says of other frameworks:
    the version it follows, and the publisher's mappings."""
    have = {row.key: row for row in session.scalars(select(Framework))}
    added = 0
    for key in keys:
        if key not in have:
            load(session, builtin(key))
            added += 1
    for key, framework in have.items():
        if key in AVAILABLE and framework.origin == "pack":
            pack = builtin(key)
            with audit.operation(session, "framework.relate", pack=key):
                if framework.follows is None and pack["pack"].get("follows"):
                    framework.follows = pack["pack"]["follows"]
                relate(session, pack)
    return added
