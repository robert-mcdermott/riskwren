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
    "NIST_SP-800-53_rev4_catalog.json": (
        f"{OSCAL}/SP800-53/rev4/json/NIST_SP-800-53_rev4_catalog.json",
        "9324021d5d88aeb4ba8f52dd225321bbc64ccc52af0270f9c1b26f1be18ed8ea",
    ),
    "NIST_SP-800-53_rev4_LOW-baseline_profile.json": (
        f"{OSCAL}/SP800-53/rev4/json/NIST_SP-800-53_rev4_LOW-baseline_profile.json",
        "621ef9eb1016ab6dab8e4b57a77bfcf09905e4d3dd6a5d0cb1a1c4f988c400b6",
    ),
    "NIST_SP-800-53_rev4_MODERATE-baseline_profile.json": (
        f"{OSCAL}/SP800-53/rev4/json/NIST_SP-800-53_rev4_MODERATE-baseline_profile.json",
        "c04c9a49b34ce892c9bb29490af3b30e8fb4fb74dee665b63d9473346e6d517d",
    ),
    "NIST_SP-800-53_rev4_HIGH-baseline_profile.json": (
        f"{OSCAL}/SP800-53/rev4/json/NIST_SP-800-53_rev4_HIGH-baseline_profile.json",
        "b2dce874f9d65572bb90956c89c5ed0fd82cd829c1b4000ee4bc41ca41b35d4c",
    ),
    "title-45-part-164-subpart-C.xml": (
        f"https://www.ecfr.gov/api/versioner/v1/full/{ECFR_DATE}/title-45.xml?part=164&subpart=C",
        "0cd78cafe337e87719da3966e4bfa59e2cb3e322165692c320baf1f64d7cdd1c",
    ),
    "title-45-part-164-subpart-D.xml": (
        f"https://www.ecfr.gov/api/versioner/v1/full/{ECFR_DATE}/title-45.xml?part=164&subpart=D",
        "d95a017bc8193f5d1d318c0ce4ca8d0121924c357e35ef9c23acbdb6864b7216",
    ),
    "NIST_PF_1.0_cprt.json": (
        "https://csrc.nist.gov/extensions/nudp/services/json/nudp/framework/version/pf_1_0_0"
        "/export/json?element=all",
        "c20d7fade235a6e2a23abdfab48e091b150ccf82804e89dbb4d1812e0bc96f20",
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

SP_800_53 = re.compile(r"^([A-Z]{2})-0*(\d+)(?:\(0*(\d+)\))?$")
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


REVISIONS = {
    "rev5": {
        "key": "nist-800-53", "title": "NIST SP 800-53 Rev. 5: Security and Privacy Controls",
        "baselines": (("low", "Low-impact baseline"), ("moderate", "Moderate-impact baseline"),
                      ("high", "High-impact baseline"), ("privacy", "Privacy baseline")),
        "source_url": "https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final",
        "summary": "The federal catalog of security and privacy controls, with the Low, Moderate, "
        "High, and Privacy baselines of SP 800-53B. Withdrawn controls are left out; where each "
        "went is carried, so that a scope on Rev. 4 can be moved across.",
        "follows": "nist-800-53-r4",
    },
    "rev4": {
        "key": "nist-800-53-r4", "title": "NIST SP 800-53 Rev. 4: Security and Privacy Controls",
        "baselines": (("low", "Low-impact baseline"), ("moderate", "Moderate-impact baseline"),
                      ("high", "High-impact baseline")),
        "source_url": "https://csrc.nist.gov/pubs/sp/800/53/r4/upd3/final",
        "summary": "The earlier revision of the federal catalog, with its Low, Moderate, and High "
        "baselines, for programs and agreements that still name it. Withdrawn controls are left "
        "out.",
        "follows": None,
    },
}  # fmt: skip


def code_of(catalog: dict[str, Any]) -> dict[str, str]:
    """Every control's id → the code people cite, withdrawn ones too."""
    found: dict[str, str] = {}

    def visit(items: list[dict[str, Any]]) -> None:
        for item in items:
            label = prop(item, "label", plain=True)
            if label:
                found[item["id"]] = label
            visit(item.get("controls", []))

    for group in catalog["groups"]:
        visit(group["controls"])
    return found


def moves(catalog: dict[str, Any]) -> list[list[str]]:
    """Where each withdrawn control went, as the publisher records it: moved to another, or
    incorporated into one (or into part of one, which is that control)."""
    codes = code_of(catalog)
    found: list[list[str]] = []

    def visit(items: list[dict[str, Any]]) -> None:
        for item in items:
            if withdrawn(item) and item["id"] in codes:
                for link in item.get("links", []):
                    relation = {
                        "moved-to": "moved_to",
                        "incorporated-into": "incorporated_into",
                    }.get(link.get("rel", ""))
                    target = link.get("href", "").lstrip("#").split("_", 1)[0]
                    if relation and target in codes and codes[target] != codes[item["id"]]:
                        pair = [codes[item["id"]], relation, codes[target]]
                        if pair not in found:
                            found.append(pair)
            visit(item.get("controls", []))

    for group in catalog["groups"]:
        visit(group["controls"])
    return found


def build_800_53(offline: bool, rev: str = "rev5") -> dict[str, Any]:
    spec = REVISIONS[rev]
    catalog = json.loads(fetch(f"NIST_SP-800-53_{rev}_catalog.json", offline=offline))["catalog"]
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
    for key, title in spec["baselines"]:
        name = f"NIST_SP-800-53_{rev}_{key.upper()}-baseline_profile.json"
        profile = json.loads(fetch(name, offline=offline))["profile"]
        chosen = [
            codes[identifier]
            for imported in profile["imports"]
            for include in imported.get("include-controls", [])
            for identifier in include.get("with-ids", [])
            if identifier in codes
        ]
        baselines.append({"key": key, "title": title, "codes": list(dict.fromkeys(chosen))})

    version = catalog["metadata"]["version"]
    shown = f"Rev. 5, release {version}" if rev == "rev5" else f"Rev. 4, as of {version}"
    head = header(
        spec["key"], spec["title"], shown,
        source_url=spec["source_url"],
        built_from=f"{OSCAL_RELEASE}: NIST_SP-800-53_{rev}_catalog.json and its baseline profiles",
        summary=spec["summary"],
    )  # fmt: skip
    pack: dict[str, Any] = {"pack": head, "requirements": families, "baselines": baselines}
    if spec["follows"]:
        head["follows"] = spec["follows"]
        # Codes that went away, said in the earlier version's terms, and where each went here.
        pack["moved"] = [pair for pair in moves(catalog) if pair[2] in codes.values()]
    return pack


def build_800_53_r4(offline: bool) -> dict[str, Any]:
    return build_800_53(offline, "rev4")


# --- NIST SP 800-171 ------------------------------------------------------------------------


def build_800_171(offline: bool) -> dict[str, Any]:
    catalog = json.loads(fetch("NIST_SP800-171_rev3_catalog.json", offline=offline))["catalog"]
    params = Parameters()

    def label(part: dict[str, Any]) -> str:
        last = (prop(part, "label") or "").rsplit(".", 1)[-1]
        return f"{int(last)}." if last.isdigit() else f"{last}."

    resources = {
        entry["uuid"]: str(entry.get("title", ""))
        for entry in catalog.get("back-matter", {}).get("resources", [])
    }
    derived: list[list[str]] = []
    families = []
    for group in catalog["groups"]:
        requirements = []
        for item in group["controls"]:
            if withdrawn(item):
                continue
            code = prop(item, "sort-id") or item["id"]
            for link in item.get("links", []):
                if link.get("rel") != "reference":
                    continue
                source = SP_800_53.match(resources.get(link["href"].lstrip("#"), ""))
                if source:
                    family, number, enhancement = source.groups()
                    cited = f"{family}-{int(number)}" + (
                        f"({int(enhancement)})" if enhancement else ""
                    )
                    if [code, cited] not in derived:
                        derived.append([code, cited])
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
        # The publisher's own account of where each requirement comes from: the SP 800-53
        # controls it was derived from. Used to suggest crosswalks between the two.
        "mappings": [
            {"framework": "nist-800-53", "relation": "derived_from", "pairs": derived},
        ],
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


# --- The HIPAA Breach Notification Rule ----------------------------------------------------

LETTER = re.compile(r"^\(([a-z])\)\s*")


def build_hipaa_breach(offline: bool) -> dict[str, Any]:
    """Subpart D, a section at a time. Each lettered paragraph is a standard or a
    specification of its own; what is beneath it stays in its text, as published."""
    root = ET.fromstring(fetch("title-45-part-164-subpart-D.xml", offline=offline))  # noqa: S314
    sections = []
    for section in root.iter("DIV8"):
        number = section.get("N", "")
        head = squeeze("".join(section.find("HEAD").itertext()))  # type: ignore[union-attr]
        top = node(number, title=head.split(" ", 2)[2].rstrip("."), kind="section")
        lines: list[str] = []
        children: list[dict[str, Any]] = []
        expected = "a"
        for paragraph in section.findall("P"):
            text = squeeze("".join(paragraph.itertext()))
            lettered = LETTER.match(text)
            if lettered is not None and lettered.group(1) == expected:
                expected = chr(ord(expected) + 1)
                rest = text[lettered.end() :]
                italic = [squeeze("".join(lead.itertext())) for lead in paragraph.findall("I")]
                title = italic[0].rstrip(".:") if italic and rest.startswith(italic[0]) else None
                kind = "specification" if title and title.startswith("Implementation") else None
                if title:
                    # The heading is the title; the text carries on from it, as published.
                    rest = rest[len(italic[0]) :].lstrip(" .:\u2014\u2013-")
                    title = re.sub(r"^Implementation specifications?:\s*", "", title)
                    kind = kind or ("standard" if title == "Standard" else None)
                children.append(node(f"{number}({lettered.group(1)})", title=title, kind=kind,
                                     text=rest))  # fmt: skip
            elif children:
                children[-1]["text"] = f"{children[-1]['text']}\n{text}"
            else:
                lines.append(text)
        if lines:
            top["text"] = "\n".join(lines)
        if children:
            top["children"] = children
            top["group"] = not lines
        sections.append(top)
    return {
        "pack": {
            **header(
                "hipaa-breach",
                "HIPAA Breach Notification Rule",
                f"45 CFR Part 164 Subpart D, as in force on {ECFR_DATE}",
                source_url="https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164/subpart-D",
                built_from=f"The electronic Code of Federal Regulations, title 45, part 164, "
                f"subpart D, as of {ECFR_DATE}",
                summary="Notification in the case of breach of unsecured protected health "
                "information: to individuals, the media, and the Secretary, by a business "
                "associate, and the law enforcement delay: sections 164.400 to 164.414.",
            ),
            "framework_kind": "regulation",
            "publisher": "United States Department of Health and Human Services",
        },
        "requirements": sections,
    }


# --- The NIST Privacy Framework ---------------------------------------------------------------


def build_privacy_framework(offline: bool) -> dict[str, Any]:
    data = json.loads(fetch("NIST_PF_1.0_cprt.json", offline=offline))["response"]["elements"]
    elements = {each["element_identifier"]: each for each in data["elements"]}
    beneath: dict[str, list[str]] = {}
    for link in data["relationships"]:
        if link["relationship_identifier"] == "projection":
            beneath.setdefault(link["source_element_identifier"], []).append(
                link["dest_element_identifier"]
            )

    def plain(text: str) -> str:
        return squeeze(text.replace("\u00a0", " "))

    functions = []
    for each in data["elements"]:
        if each["element_type"] != "function":
            continue
        categories = []
        for category_id in beneath.get(each["element_identifier"], []):
            category = elements[category_id]
            if category["element_type"] != "category":
                continue  # the publisher's sort keys and its notes on the CSF
            outcomes = [
                node(outcome_id, kind="subcategory", text=plain(elements[outcome_id]["text"]))
                for outcome_id in beneath.get(category_id, [])
                if elements[outcome_id]["element_type"] == "subcategory"
            ]
            categories.append(node(category_id, title=plain(category["title"]), kind="category",
                                   group=True, text=plain(category["text"]),
                                   children=outcomes))  # fmt: skip
        functions.append(node(each["element_identifier"], title=each["title"].title(),
                              kind="function", group=True, text=plain(each["text"]),
                              children=categories))  # fmt: skip
    return {
        "pack": header(
            "nist-privacy",
            "NIST Privacy Framework",
            "1.0",
            source_url="https://www.nist.gov/privacy-framework",
            built_from="The NIST Cybersecurity and Privacy Reference Tool: the Privacy "
            "Framework 1.0 core, as exported",
            summary="Five functions, their categories, and the subcategories under each: the "
            "outcomes of managing privacy risk arising from data processing.",
        ),
        "requirements": functions,
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
    builders = (build_csf, build_800_53, build_800_53_r4, build_800_171, build_hipaa,
                build_hipaa_breach, build_privacy_framework)  # fmt: skip
    for build in builders:
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
