"""Packs: the program and its content as data files (see spec/content-packs.md).

A new installation is given the built-in default program and the starter libraries. An
organization's whole configuration exports as one program pack and imports into another
installation, checked in full before any of it is loaded.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.controls import service as controls
from riskwren.core import scoring
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.db.models import RiskCategory, ScoringMethod
from riskwren.events import audit
from riskwren.program import rules, vocab
from riskwren.risk import categories, library
from riskwren.risk import method as methods
from riskwren.treatment import service as treatment  # noqa: F401  (what treatment says of standing)

LIBRARY_PACKS = ("risk-library.json",)
CONTROL_PACKS = ("starter-controls.json",)


def builtin(name: str) -> dict[str, Any]:
    text = resources.files("riskwren.resources").joinpath("packs", name).read_text("utf-8")
    return json.loads(text)


def _add_categories(session: Session, items: list[dict[str, Any]]) -> int:
    """Add the categories that are not there yet. Those that are stay as the organization
    has shaped them."""
    have = {row.key: row for row in session.scalars(select(RiskCategory))}
    added = 0

    def place(item: dict[str, Any], parent_id: int | None, position: int) -> None:
        nonlocal added
        row = have.get(item["key"])
        if row is None:
            row = RiskCategory(
                key=item["key"],
                parent_id=parent_id,
                name=item["name"],
                description=item.get("description"),
                appetite=item.get("appetite"),
                status=item.get("status", "active"),
                position=position,
            )
            session.add(row)
            session.flush()
            have[row.key] = row
            added += 1
        for index, child in enumerate(item.get("children", [])):
            place(child, row.id, index)

    for index, item in enumerate(items):
        place(item, None, index)
    return added


def install(session: Session, *, frameworks: bool = True) -> dict[str, int]:
    """Give an installation what it needs to work on its first day. Safe to run again: it
    adds what is missing and leaves what is there. ``frameworks`` loads the built-in
    public frameworks too."""
    pack = vocab.default_pack()
    done = {"scoring_method": 0, "categories": 0, "library": 0, "controls": 0, "frameworks": 0,
            "questionnaires": 0}  # fmt: skip
    with audit.operation(session, "program.install"):
        if session.scalars(select(ScoringMethod.id)).first() is None:
            methods.publish(session, None, pack["scoring_method"])
            done["scoring_method"] = 1
        done["categories"] = _add_categories(session, pack["categories"])
        for name in LIBRARY_PACKS:
            done["library"] += library.load(session, builtin(name))
        for name in CONTROL_PACKS:
            done["controls"] += controls.load_library(session, builtin(name))
        from riskwren.oversight import questionnaires

        done["questionnaires"] = questionnaires.install(
            session, builtin("questionnaires.json")["questionnaires"]
        )
    if frameworks:
        from riskwren.compliance import packs as framework_packs

        done["frameworks"] = framework_packs.install(session)
    return done


# --- Moving a program between installations -------------------------------------------------


def export(session: Session) -> dict[str, Any]:
    """The whole program as one document that can be read, kept, and imported elsewhere."""

    def node(row: dict[str, Any]) -> dict[str, Any]:
        out = {key: row[key] for key in ("key", "name", "description", "appetite", "status")}
        out["children"] = [node(child) for child in row["children"]]
        return out

    row = methods.current_row(session)
    return {
        "pack": {
            "key": "program",
            "kind": "program",
            "title": "Program",
            "version": str(row.version),
            "pack_version": "1.0.0",
            "publisher": "",
            "license": "",
            "text_policy": "verbatim",
        },
        "vocabularies": vocab.all_(session),
        "categories": [node(item) for item in categories.Tree(session).view()],
        "scoring_method": row.definition,
        "cadences": rules.get(session, "cadences"),
        "authority": rules.get(session, "authority"),
    }


def problems(pack: Any) -> list[str]:
    """Everything wrong with a program pack, found before any of it is loaded."""
    if not isinstance(pack, dict) or (pack.get("pack") or {}).get("kind") != "program":
        return ["This is not a program pack."]
    found: list[str] = []
    method = pack.get("scoring_method") or {}
    found += scoring.problems(method)
    ratings = [rating.get("key") for rating in method.get("ratings") or []]
    for name, items in (pack.get("vocabularies") or {}).items():
        if name not in vocab.DEFAULTS:
            found.append(f"There is no vocabulary called {name}.")
        elif not isinstance(items, list) or any(
            not (isinstance(i, dict) and i.get("key") and i.get("label")) for i in items
        ):
            found.append(f"Every value of {name} needs a key and a label.")
    seen: set[str] = set()

    def check(item: Any, top: bool) -> None:
        if not isinstance(item, dict) or not item.get("key") or not item.get("name"):
            found.append("Every risk category needs a key and a name.")
            return
        if item["key"] in seen:
            found.append(f"The risk category {item['key']} appears twice.")
        seen.add(item["key"])
        appetite = item.get("appetite")
        if appetite and appetite not in ratings:
            found.append(f"The appetite of {item['key']} is not one of the ratings.")
        if top and not appetite:
            found.append(f"The top-level category {item['key']} needs an appetite.")
        for child in item.get("children", []):
            check(child, False)

    for item in pack.get("categories") or []:
        check(item, True)
    if not pack.get("categories"):
        found.append("A program needs at least one risk category.")
    cadences = pack.get("cadences") or {}
    months = cadences.get("risk_review_months") or {}
    if set(months) != set(ratings) or not all(
        isinstance(v, int) and 1 <= v <= 120 for v in months.values()
    ):
        found.append("The review cadence needs a number of months for every rating.")
    acceptance = (pack.get("authority") or {}).get("acceptance") or {}
    if not set(acceptance) <= set(ratings) or not all(
        isinstance(rule, dict) and isinstance(rule.get("max_months"), int)
        for rule in acceptance.values()
    ):
        found.append("The acceptance authority must name ratings, each with a limit in months.")
    return found


def import_(
    session: Session, principal: Principal, pack: Any, *, dry_run: bool = False
) -> dict[str, Any]:
    """Load a program pack. Nothing is loaded unless all of it can be."""
    if not principal.configures:
        raise PermissionDenied("Only those who run the program can import a program pack.")
    found = problems(pack)
    if found:
        raise Invalid("The pack was not loaded.", {"pack": " ".join(found)})
    changed: list[str] = []
    with audit.operation(session, "program.import"):
        for name, items in pack.get("vocabularies", {}).items():
            if vocab.get(session, name) != items:
                changed.append(f"vocabulary {name}")
                if not dry_run:
                    vocab.put(session, name, items)
        if methods.current(session) != pack["scoring_method"]:
            changed.append("scoring method")
            if not dry_run:
                methods.publish(session, principal, pack["scoring_method"])
        have = {row.key: row for row in categories.all_(session)}

        def place(item: dict[str, Any], parent: RiskCategory | None, position: int) -> None:
            row = have.get(item["key"])
            values = {
                "name": item["name"],
                "description": item.get("description"),
                "appetite": item.get("appetite"),
                "status": item.get("status", "active"),
                "parent_id": parent.id if parent is not None else None,
                "position": position,
            }
            if row is None:
                changed.append(f"category {item['key']} (new)")
                if dry_run:
                    return  # its children are new too; one line says so
                row = RiskCategory(key=item["key"], **values)
                session.add(row)
                session.flush()
                have[row.key] = row
            elif any(getattr(row, name) != value for name, value in values.items()):
                changed.append(f"category {item['key']}")
                if not dry_run:
                    for name, value in values.items():
                        setattr(row, name, value)
            for index, child in enumerate(item.get("children", [])):
                place(child, row, index)

        for index, item in enumerate(pack["categories"]):
            place(item, None, index)
        for name in rules.NAMES:
            if name in pack and rules.get(session, name) != pack[name]:
                changed.append(name)
                if not dry_run:
                    rules.put(session, name, pack[name])
        session.flush()
    return {"dry_run": dry_run, "changed": changed}
