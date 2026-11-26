#!/usr/bin/env python3
"""Write the default program pack: what a new installation starts with.

The pack is data, kept in ``src/riskwren/resources/packs/default-program.json``. It is written
from this script so that the content can be reviewed as code and regenerated in one step:

    uv run python scripts/build-default-program.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parent.parent / "src/riskwren/resources/packs/default-program.json"


def items(*rows: tuple[str, ...]) -> list[dict[str, Any]]:
    return [
        {"key": row[0], "label": row[1], **({"description": row[2]} if len(row) > 2 else {})}
        for row in rows
    ]


# Ordered from least to most: rules and lists compare them.
CRITICALITIES = items(
    ("low", "Low", "Could be done without for weeks with little effect"),
    ("moderate", "Moderate", "Its loss would be felt within days and worked around"),
    ("high", "High", "Its loss would stop important work within a day or two"),
    ("critical", "Critical", "Research, care, or safety depends on it hour by hour"),
)

# Ordered from least to most sensitive.
DATA_CLASSES: list[dict[str, Any]] = [
    {
        "key": "public",
        "label": "Public",
        "description": "Poses little or no risk if disclosed, and may be shared with anyone.",
        "examples": {
            "Research": ["Published papers and results", "Data already in a public repository"],
            "Health": ["Published population statistics"],
            "People": ["Public staff directory entries"],
            "Business": ["Press releases", "Figures in a published annual report"],
        },
    },
    {
        "key": "internal",
        "label": "Internal",
        "description": "Meant for the organization's own people and work. Not to be shared "
        "outside without a reason.",
        "examples": {
            "Research": ["Drafts and plans for future work", "Laboratory procedures"],
            "Health": ["Aggregate counts in which nobody can be identified"],
            "People": ["Work contact details", "Organization charts"],
            "Business": ["Internal policies and procedures", "Most correspondence and minutes"],
        },
    },
    {
        "key": "confidential",
        "label": "Confidential",
        "description": "Could harm people or the organization if seen by the wrong person, "
        "inside or out. Access is limited to those who need it.",
        "examples": {
            "Research": [
                "Unpublished data, results, and manuscripts",
                "De-identified participant data",
                "Data held under a data use agreement",
            ],
            "Health": ["Staff immunization and fitness-for-work records"],
            "People": ["Personnel records", "Student and trainee records"],
            "Business": ["Budgets and financial records", "Contracts", "Security plans"],
        },
    },
    {
        "key": "restricted",
        "label": "Restricted",
        "description": "Governed by specific legal, regulatory, or contractual obligations. "
        "Loss or disclosure may require notifying people, partners, or authorities.",
        "examples": {
            "Research": [
                "Identifiable participant data",
                "Controlled-access genomic data",
                "Export-controlled information",
            ],
            "Health": ["Identifiable health information", "Health insurance numbers"],
            "People": [
                "A name with a government identifier or full date of birth",
                "Payroll and bank details",
            ],
            "Business": ["Payment card numbers", "Passwords, keys, and access codes"],
        },
    },
]

VOCABULARIES: dict[str, list[dict[str, Any]]] = {
    "criticalities": CRITICALITIES,
    "data_classes": DATA_CLASSES,
    "unit_kinds": items(
        ("organization", "Organization"),
        ("division", "Division"),
        ("department", "Department"),
        ("center", "Center"),
        ("core", "Core facility"),
        ("lab", "Lab"),
        ("clinic", "Clinic"),
        ("office", "Office"),
    ),
    "owner_kinds": items(
        ("owner", "Owner", "Accountable for the record and for keeping it current"),
        ("delegate", "Delegate", "Acts for the owner day to day"),
        ("contact", "Contact", "Knows the detail and can be asked"),
    ),
    "process_kinds": items(
        ("research", "Research", "Carrying out research"),
        ("research_support", "Research support", "Cores, shared services, and facilities"),
        ("clinical", "Clinical", "Care of patients and participants"),
        ("education", "Education and training"),
        ("administrative", "Administrative", "Finance, people, legal, and the like"),
        ("technology", "Technology", "Running information systems and services"),
        ("facilities", "Facilities and safety"),
    ),
    "system_kinds": items(
        ("application", "Application", "Software people use to do their work"),
        ("platform", "Platform", "Something other systems are built or run on"),
        ("infrastructure", "Infrastructure", "Networks, storage, compute, and identity"),
        ("instrument", "Instrument", "Laboratory or imaging equipment and its computer"),
        ("device", "Device", "A medical, building, or other connected device"),
        ("data_store", "Data store", "A database, repository, or archive"),
    ),
    "hosting": items(
        ("on_premises", "On premises", "Run in the organization's own facilities"),
        ("cloud", "Cloud, run by us", "In a cloud account the organization administers"),
        ("hosted", "Hosted by a supplier", "Run entirely by a third party"),
        ("hybrid", "Hybrid"),
        ("standalone", "Standalone", "A single machine, often not on the network"),
    ),
    "lifecycles": items(
        ("planned", "Planned"),
        ("in_service", "In service"),
        ("sunsetting", "Being retired", "Still in use, with an end date"),
        ("unsupported", "Unsupported", "In use, and no longer maintained by its maker"),
    ),
    "third_party_kinds": items(
        ("supplier", "Supplier", "Sells goods the organization depends on"),
        ("service_provider", "Service provider", "Runs a service or a system for it"),
        ("contractor", "Contractor", "Does work on its behalf"),
        ("collaborator", "Collaborator", "A research or clinical partner"),
        ("sponsor", "Sponsor or funder"),
        ("subrecipient", "Subrecipient", "Receives funds the organization passes through"),
    ),
}

# The named relationships between records. ``label`` reads from the first to the second;
# ``reverse`` reads back. ``between`` lists the pairs of record types a kind may join.
LINK_KINDS: list[dict[str, Any]] = [
    {
        "key": "relies_on",
        "label": "Relies on",
        "reverse": "Supports",
        "between": [["process", "system"]],
    },
    {
        "key": "performed_by",
        "label": "Performed by",
        "reverse": "Performs",
        "between": [["process", "third_party"]],
    },
    {
        "key": "supplied_by",
        "label": "Supplied by",
        "reverse": "Supplies",
        "between": [["system", "third_party"]],
    },
    {
        "key": "depends_on",
        "label": "Depends on",
        "reverse": "Is depended on by",
        "between": [["process", "process"], ["system", "system"]],
    },
]

PACK: dict[str, Any] = {
    "pack": {
        "key": "default-program",
        "kind": "program",
        "title": "Default program",
        "version": "1",
        "pack_version": "0.1.0",
        "publisher": "The RiskWren Authors",
        "license": "Apache-2.0",
        "text_policy": "verbatim",
    },
    "vocabularies": {**VOCABULARIES, "link_kinds": LINK_KINDS},
}


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(PACK, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(OUT.parents[4])}")


if __name__ == "__main__":
    main()
