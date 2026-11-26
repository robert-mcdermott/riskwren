#!/usr/bin/env python3
"""Build the built-in framework packs from their publishers' machine-readable files.

Each pack in ``src/riskwren/resources/packs/frameworks/`` is generated here, never typed, so
that a new release of a source is a rebuild and a comparison. The sources are works of the
United States government and in the public domain; their text is carried as published.

    uv run python scripts/build-framework-packs.py            download what is missing, build all
    uv run python scripts/build-framework-packs.py --offline  build from the files already fetched

Sources are fetched once into ``.cache/sources`` (ignored by git) and checked against the
digest recorded below, so a pack can only be built from the file it says it was built from.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "sources"
OUT = ROOT / "src" / "riskwren" / "resources" / "packs" / "frameworks"

OSCAL = "https://raw.githubusercontent.com/usnistgov/oscal-content/v1.6.0/nist.gov"
OSCAL_RELEASE = "usnistgov/oscal-content v1.6.0"
ECFR_DATE = "2026-01-01"
PUBLIC_DOMAIN = "Public domain (a work of the United States government)"

# name → (address, sha256)
SOURCES: dict[str, tuple[str, str]] = {
    "NIST_CSF_v2.0_catalog.json": (
        f"{OSCAL}/CSF/v2.0/json/NIST_CSF_v2.0_catalog.json",
        "0ac12904a4bcd877ec91be8e7ddc27278c88b0088c7db77d60ee24918e2563e2",
    ),
    "NIST_SP800-171_rev3_catalog.json": (
        f"{OSCAL}/SP800-171/rev3/json/NIST_SP800-171_rev3_catalog.json",
        "fd68bad4c1fee98dd1b2511884b585fb1f14265d4c5693d0492a25dd66e73dde",
    ),
    "NIST_SP-800-53_rev5_catalog.json": (
        f"{OSCAL}/SP800-53/rev5/json/NIST_SP-800-53_rev5_catalog.json",
        "64ca6b4161de51ab6af098a7d101d326f14c95e1abf721396cd8a049e8115eeb",
    ),
    "NIST_SP-800-53_rev5_LOW-baseline_profile.json": (
        f"{OSCAL}/SP800-53/rev5/json/NIST_SP-800-53_rev5_LOW-baseline_profile.json",
        "cfd4f5d9a192eb42dc04b745d82f95a85926a2a85a45418034a380a42bda9424",
    ),
    "NIST_SP-800-53_rev5_MODERATE-baseline_profile.json": (
        f"{OSCAL}/SP800-53/rev5/json/NIST_SP-800-53_rev5_MODERATE-baseline_profile.json",
        "e3a0f11237cfaac24dfcf1586e07683f17423757fd84208deb33196b12e8f590",
    ),
    "NIST_SP-800-53_rev5_HIGH-baseline_profile.json": (
        f"{OSCAL}/SP800-53/rev5/json/NIST_SP-800-53_rev5_HIGH-baseline_profile.json",
        "d2ef340986b9f1ee820ad866a0f964d9a9d1088b24080c74b795ddb0148b9f83",
    ),
    "NIST_SP-800-53_rev5_PRIVACY-baseline_profile.json": (
        f"{OSCAL}/SP800-53/rev5/json/NIST_SP-800-53_rev5_PRIVACY-baseline_profile.json",
        "c0e3d54d9f474bc6c33338a8e524bc52ad070f94f9274db7ec48242242fecacc",
    ),
    "title-45-part-164-subpart-C.xml": (
        f"https://www.ecfr.gov/api/versioner/v1/full/{ECFR_DATE}/title-45.xml?part=164&subpart=C",
        "0cd78cafe337e87719da3966e4bfa59e2cb3e322165692c320baf1f64d7cdd1c",
    ),
}


# --- Fetching -----------------------------------------------------------------------------


def fetch(name: str, *, offline: bool) -> bytes:
    address, digest = SOURCES[name]
    path = CACHE / name
    if not path.is_file():
        if offline:
            raise SystemExit(f"{name} has not been fetched. Run without --offline.")
        CACHE.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(  # noqa: S310 - a fixed https address from SOURCES
            address, headers={"User-Agent": "framework-pack-builder", "Accept-Encoding": "gzip"}
        )
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
            body = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
        path.write_bytes(body)
        print(f"fetched {name} ({len(body):,} bytes)")
    data = path.read_bytes()
    found = hashlib.sha256(data).hexdigest()
    if found != digest:
        raise SystemExit(
            f"{name} is not the file this script was written for.\n"
            f"  expected {digest}\n  found    {found}\n"
            "If the source has been revised, review the change and record the new digest."
        )
    return data


# --- Reading the publisher's catalogs -------------------------------------------------------

INSERT = re.compile(r"\{\{\s*insert:\s*param,\s*([^\s}]+)\s*\}\}")
HOW_MANY = {"one-or-more": "Selection (one or more)", "one": "Selection"}


def prop(item: dict[str, Any], name: str, *, plain: bool = False) -> str | None:
    for entry in item.get("props", []):
        if entry["name"] == name and not (plain and entry.get("class")):
            return str(entry["value"])
    return None


def withdrawn(item: dict[str, Any]) -> bool:
    return prop(item, "status") == "withdrawn"


class Parameters:
    """What a statement's placeholders stand for, written as the publication writes them:
    ``[Assignment: organization-defined frequency]`` and ``[Selection: a; b]``."""

    def __init__(self) -> None:
        self.known: dict[str, dict[str, Any]] = {}

    def learn(self, item: dict[str, Any]) -> None:
        for param in item.get("params", []):
            self.known[param["id"]] = param

    def fill(self, prose: str, depth: int = 0) -> str:
        def shown(match: re.Match[str]) -> str:
            param = self.known.get(match.group(1))
            if param is None or depth > 3:
                return "[Assignment: organization-defined value]"
            select = param.get("select")
            if select:
                choices = "; ".join(self.fill(choice, depth + 1) for choice in select["choice"])
                return f"[{HOW_MANY.get(select.get('how-many', 'one'), 'Selection')}: {choices}]"
            label = str(param.get("label", "value")).strip()
            if not label.startswith("organization-defined"):
                label = f"organization-defined {label}"
            return f"[Assignment: {label}]"

        return INSERT.sub(shown, prose)


def squeeze(text: str) -> str:
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


def statement(part: dict[str, Any], params: Parameters, label: Any, depth: int = -1) -> list[str]:
    """A statement and its lettered and numbered items, one to a line, indented by depth."""
    lines = []
    prose = squeeze(params.fill(part.get("prose", "")))
    if prose or depth >= 0:
        mark = label(part) if depth >= 0 else ""
        lines.append("  " * max(depth, 0) + " ".join(x for x in (mark, prose) if x))
    for child in part.get("parts", []):
        if child["name"] == "item":
            lines += statement(child, params, label, depth + 1)
    return lines


def part_named(item: dict[str, Any], name: str) -> dict[str, Any] | None:
    return next((part for part in item.get("parts", []) if part["name"] == name), None)


def text_of(item: dict[str, Any], params: Parameters, label: Any) -> str:
    part = part_named(item, "statement")
    return "\n".join(statement(part, params, label)) if part else ""


def guidance_of(item: dict[str, Any], params: Parameters) -> str | None:
    part = part_named(item, "guidance")
    return squeeze(params.fill(part.get("prose", ""))) or None if part else None


def node(code: str, **fields: Any) -> dict[str, Any]:
    made: dict[str, Any] = {"code": code}
    made.update({key: value for key, value in fields.items() if value not in (None, "", [], False)})
    return made


def header(key: str, title: str, version: str, **more: Any) -> dict[str, Any]:
    return {
        "key": key,
        "kind": "framework",
        "framework_kind": "standard",
        "title": title,
        "version": version,
        "pack_version": "1.0.0",
        "publisher": "National Institute of Standards and Technology",
        "license": PUBLIC_DOMAIN,
        "text_policy": "verbatim",
        **more,
    }


# --- NIST SP 800-53 -------------------------------------------------------------------------


def build_800_53(offline: bool) -> dict[str, Any]:
    catalog = json.loads(fetch("NIST_SP-800-53_rev5_catalog.json", offline=offline))["catalog"]
    params = Parameters()
    codes: dict[str, str] = {}  # the catalog's id → the code people cite

    def label(part: dict[str, Any]) -> str:
        return prop(part, "label") or ""

    def control(item: dict[str, Any], kind: str) -> dict[str, Any] | None:
        if withdrawn(item):
            return None
        params.learn(item)
        code = prop(item, "label", plain=True)
        assert code, item["id"]
        codes[item["id"]] = code
        children = [control(child, "enhancement") for child in item.get("controls", [])]
        return node(
            code,
            title=item["title"],
            kind=kind,
            text=text_of(item, params, label),
            guidance=guidance_of(item, params),
            children=[child for child in children if child],
        )

    families = []
    for group in catalog["groups"]:
        controls = [control(item, "control") for item in group["controls"]]
        families.append(
            node(
                group["id"].upper(),
                title=group["title"],
                kind="family",
                group=True,
                children=[item for item in controls if item],
            )
        )

    baselines = []
    for key, title in (
        ("low", "Low-impact baseline"),
        ("moderate", "Moderate-impact baseline"),
        ("high", "High-impact baseline"),
        ("privacy", "Privacy baseline"),
    ):
        name = f"NIST_SP-800-53_rev5_{key.upper()}-baseline_profile.json"
        profile = json.loads(fetch(name, offline=offline))["profile"]
        chosen = [
            codes[identifier]
            for imported in profile["imports"]
            for include in imported.get("include-controls", [])
            for identifier in include.get("with-ids", [])
            if identifier in codes
        ]
        baselines.append({"key": key, "title": title, "codes": chosen})

    version = catalog["metadata"]["version"]
    return {
        "pack": header(
            "nist-800-53",
            "NIST SP 800-53 Rev. 5: Security and Privacy Controls",
            f"Rev. 5, release {version}",
            source_url="https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final",
            built_from=f"{OSCAL_RELEASE}: NIST_SP-800-53_rev5_catalog.json and the SP 800-53B "
            "baseline profiles",
            summary="The federal catalog of security and privacy controls, with the Low, "
            "Moderate, High, and Privacy baselines of SP 800-53B. Withdrawn controls are left out.",
        ),
        "requirements": families,
        "baselines": baselines,
    }


# --- NIST SP 800-171 ------------------------------------------------------------------------


def build_800_171(offline: bool) -> dict[str, Any]:
    catalog = json.loads(fetch("NIST_SP800-171_rev3_catalog.json", offline=offline))["catalog"]
    params = Parameters()

    def label(part: dict[str, Any]) -> str:
        last = (prop(part, "label") or "").rsplit(".", 1)[-1]
        return f"{int(last)}." if last.isdigit() else f"{last}."

    families = []
    for group in catalog["groups"]:
        requirements = []
        for item in group["controls"]:
            if withdrawn(item):
                continue
            params.learn(item)
            requirements.append(
                node(
                    prop(item, "sort-id") or item["id"],
                    title=item["title"],
                    kind="requirement",
                    text=text_of(item, params, label),
                    guidance=guidance_of(item, params),
                )
            )
        families.append(
            node(
                group["id"].rsplit("_", 1)[-1],
                title=group["title"],
                kind="family",
                group=True,
                children=requirements,
            )
        )
    return {
        "pack": header(
            "nist-800-171",
            "NIST SP 800-171 Rev. 3: Protecting Controlled Unclassified Information",
            "Rev. 3",
            source_url="https://csrc.nist.gov/pubs/sp/800/171/r3/final",
            built_from=f"{OSCAL_RELEASE}: NIST_SP800-171_rev3_catalog.json",
            summary="Security requirements for protecting controlled unclassified information "
            "in nonfederal systems and organizations. Withdrawn requirements are left out.",
        ),
        "requirements": families,
    }


# --- NIST Cybersecurity Framework -----------------------------------------------------------


def build_csf(offline: bool) -> dict[str, Any]:
    catalog = json.loads(fetch("NIST_CSF_v2.0_catalog.json", offline=offline))["catalog"]

    def prose(item: dict[str, Any], name: str) -> str:
        part = part_named(item, name)
        return squeeze(part.get("prose", "")) if part else ""

    def examples(item: dict[str, Any]) -> str | None:
        found = [
            squeeze(part.get("prose", ""))
            for part in item.get("parts", [])
            if part["name"] == "guidance" and part.get("class") == "example"
        ]
        return "\n".join(f"- {line}" for line in found if line) or None

    functions = []
    for function in catalog["groups"]:
        categories = []
        for category in function["controls"]:
            outcomes = [
                node(
                    outcome["id"],
                    kind="subcategory",
                    text=prose(outcome, "statement"),
                    guidance=examples(outcome),
                )
                for outcome in category.get("controls", [])
                if not withdrawn(outcome)
            ]
            if not outcomes:
                continue  # a category of an earlier version, kept by the publisher as withdrawn
            categories.append(
                node(
                    category["id"],
                    title=category["title"],
                    kind="category",
                    group=True,
                    text=prose(category, "statement"),
                    children=outcomes,
                )
            )
        functions.append(
            node(
                function["id"],
                title=function["title"].title(),
                kind="function",
                group=True,
                text=prose(function, "overview"),
                children=categories,
            )
        )
    return {
        "pack": header(
            "nist-csf",
            "NIST Cybersecurity Framework",
            "2.0",
            source_url="https://www.nist.gov/cyberframework",
            built_from=f"{OSCAL_RELEASE}: NIST_CSF_v2.0_catalog.json",
            summary="Six functions, their categories, and the outcomes under each, with the "
            "publisher's implementation examples as guidance.",
        ),
        "requirements": functions,
    }


# --- The HIPAA Security Rule ----------------------------------------------------------------

SECTIONS = ("164.306", "164.308", "164.310", "164.312", "164.314", "164.316")
DESIGNATOR = re.compile(r"^\(([a-z]+|[0-9]+|[A-Z]+)\)\s*")
ROMAN = re.compile(r"^[ivxl]+$")


def level_of(mark: str, depth: int) -> int:
    """Where a paragraph sits: (a) is first, (1) second, (i) third, (A) fourth. In this
    subpart no section reaches paragraph (i) at the first level, so a roman numeral is
    always the third."""
    if mark.isdigit():
        return 2
    if mark.isupper():
        return 4
    if ROMAN.match(mark) and depth >= 2:
        return 3
    return 1


def build_hipaa(offline: bool) -> dict[str, Any]:
    root = ET.fromstring(fetch("title-45-part-164-subpart-C.xml", offline=offline))  # noqa: S314
    sections = []
    for section in root.iter("DIV8"):
        number = section.get("N", "")
        if number not in SECTIONS:
            continue
        head = squeeze("".join(section.find("HEAD").itertext()))  # type: ignore[union-attr]
        top = node(number, title=head.split(" ", 2)[2].rstrip("."), kind="section", group=True)
        top["children"] = []
        path: list[tuple[str, dict[str, Any]]] = []  # the open paragraph at each level
        for paragraph in section.findall("P"):
            text = squeeze("".join(paragraph.itertext()))
            headings = [squeeze("".join(lead.itertext())) for lead in paragraph.findall("I")]
            heading = headings[0] if headings else ""
            marks = []
            while (found := DESIGNATOR.match(text)) is not None:
                marks.append(found.group(1))
                text = text[found.end() :]
            if not marks:
                # A paragraph that continues the one before it.
                if path:
                    path[-1][1]["text"] = f"{path[-1][1].get('text', '')}\n{text}".strip()
                continue
            for position, mark in enumerate(marks):
                level = level_of(
                    mark, len(path) if position == 0 else level_of(marks[0], len(path)) + position
                )
                del path[level - 1 :]
                code = number + "".join(f"({m})" for m, _ in path) + f"({mark})"
                made: dict[str, Any] = {"code": code}
                parent = path[-1][1] if path else top
                parent.setdefault("children", []).append(made)
                path.append((mark, made))
            last = path[-1][1]
            last["text"] = text
            if heading and text.startswith(heading):
                title = heading.rstrip(".:")
                if title.startswith("Standard:"):
                    last["kind"], title = "standard", title.removeprefix("Standard:").strip()
                elif title.endswith(("(Required)", "(Addressable)")):
                    last["kind"] = "specification"
                last["title"] = title
                rest = text[len(heading) :].lstrip(" \u2014\u2013-")
                if (inner := DESIGNATOR.match(rest)) is not None:
                    # "(b) Flexibility of approach. (1) Covered entities…": a heading, then
                    # its first numbered paragraph on the same line.
                    last["text"] = heading
                    code = number + "".join(f"({m})" for m, _ in path) + f"({inner.group(1)})"
                    first = {"code": code, "text": rest[inner.end() :]}
                    named = next((h for h in headings[1:] if first["text"].startswith(h)), None)
                    if named:
                        first["title"] = named.rstrip(".:")
                    last.setdefault("children", []).append(first)
                    path.append((inner.group(1), first))
        sections.append(top)

    def settle(item: dict[str, Any]) -> None:
        """A paragraph that only introduces others is a heading, not something to cite."""
        children = item.get("children", [])
        for child in children:
            settle(child)
        if children and item.get("kind") not in ("standard", "specification"):
            item["group"] = True
        bare = children and not item.get("text") and not item.get("title")
        if bare and children[0].get("kind") == "standard":
            item["title"] = children[0]["title"]  # "(a)(1)" holds one standard and its parts
        if not children:
            item.pop("children", None)

    for top in sections:
        settle(top)
    return {
        "pack": {
            **header(
                "hipaa-security",
                "HIPAA Security Rule",
                f"45 CFR Part 164 Subpart C, as in force on {ECFR_DATE}",
                source_url="https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164/subpart-C",
                built_from=f"The electronic Code of Federal Regulations, title 45, part 164, "
                f"subpart C, as of {ECFR_DATE}",
                summary="The security standards for electronic protected health information "
                "and their implementation specifications: sections 164.306 to 164.316.",
            ),
            "framework_kind": "regulation",
            "publisher": "United States Department of Health and Human Services",
        },
        "requirements": sections,
    }


# --- Writing ------------------------------------------------------------------------------


def count(items: list[dict[str, Any]]) -> tuple[int, int]:
    total = citable = 0
    for item in items:
        inner = count(item.get("children", []))
        total += 1 + inner[0]
        citable += (0 if item.get("group") else 1) + inner[1]
    return total, citable


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--offline", action="store_true", help="use only files already fetched")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for build in (build_csf, build_800_53, build_800_171, build_hipaa):
        pack = build(args.offline)
        path = OUT / f"{pack['pack']['key']}.json"
        path.write_text(json.dumps(pack, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        total, citable = count(pack["requirements"])
        extra = f", {len(pack['baselines'])} baselines" if pack.get("baselines") else ""
        print(
            f"{path.name}: {total} entries, {citable} that can be cited{extra}, {path.stat().st_size:,} bytes"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
