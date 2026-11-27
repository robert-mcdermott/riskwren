#!/usr/bin/env python3
"""Write the default program pack and the starter libraries: what a new installation has.

The packs are data, kept in ``src/riskwren/resources/packs/``. They are written from this
script so that the content can be reviewed as code and regenerated in one step:

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
    "control_kinds": items(
        ("preventive", "Preventive", "Stops the event from happening"),
        ("detective", "Detective", "Notices that it is happening, or has"),
        ("corrective", "Corrective", "Limits the damage and puts things right"),
        ("directive", "Directive", "Tells people what to do: a policy, a standard, training"),
    ),
    "control_natures": items(
        ("manual", "Manual", "Done by a person"),
        ("automated", "Automated", "Done by a system without anyone acting"),
        ("both", "Both", "A system and a person together"),
    ),
    "control_frequencies": items(
        ("continuous", "Continuous"),
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("twice_a_year", "Twice a year"),
        ("annually", "Annually"),
        ("as_needed", "When the occasion arises"),
    ),
    "third_party_kinds": items(
        ("supplier", "Supplier", "Sells goods the organization depends on"),
        ("service_provider", "Service provider", "Runs a service or a system for it"),
        ("contractor", "Contractor", "Does work on its behalf"),
        ("collaborator", "Collaborator", "A research or clinical partner"),
        ("sponsor", "Sponsor or funder"),
        ("subrecipient", "Subrecipient", "Receives funds the organization passes through"),
    ),
    # What a third party provides. A service is what reaches systems and handles information.
    "service_kinds": items(
        (
            "software_service",
            "Software as a service",
            "An application it runs and the organization uses",
        ),
        (
            "hosting",
            "Hosting or infrastructure",
            "Computing, storage, or networks it runs for the organization",
        ),
        ("data_service", "Data processing or analysis", "Work it does on the organization's data"),
        ("laboratory", "Laboratory or testing", "Tests, sequencing, or analysis of specimens"),
        (
            "clinical",
            "Clinical service",
            "Care, or a service to patients, given on the organization's behalf",
        ),
        ("maintenance", "Maintenance and support", "Keeping equipment or systems working"),
        ("professional", "Professional services", "Advice, audit, legal, or consulting work"),
        ("staffing", "Staffing", "People who work alongside the organization's own"),
        (
            "supply",
            "Goods and supplies",
            "Things delivered, with no access to systems or information",
        ),
        ("logistics", "Logistics", "Moving or storing specimens, equipment, or records"),
        ("collaboration", "Research collaboration", "Shared work under a protocol or an award"),
        ("funding", "Funding", "Money the organization receives, with its terms"),
    ),
    "information_kinds": items(
        ("research_data", "Research data", "Data produced or collected by research"),
        ("participant_data", "Participant data", "About people who take part in research"),
        ("patient_records", "Patient records", "Records of care"),
        ("specimen_records", "Specimen records", "What is known about stored specimens"),
        ("controlled_data", "Controlled-access data", "Held under another party's terms"),
        ("personnel_records", "Personnel records", "About staff, students, and applicants"),
        ("financial_records", "Financial records", "Accounts, awards, payments, and donors"),
        ("intellectual_property", "Intellectual property", "Unpublished results and inventions"),
        ("operational", "Operational", "What the organization needs to run"),
    ),
}

# The named relationships between records. ``label`` reads from the first to the second;
# ``reverse`` reads back. ``between`` lists the pairs of record types a kind may join.
LINK_KINDS: list[dict[str, Any]] = [
    {
        "key": "relies_on",
        "label": "Relies on",
        "reverse": "Supports",
        "between": [["process", "system"], ["process", "service"]],
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
        "between": [["system", "third_party"], ["system", "service"]],
    },
    {
        "key": "holds",
        "label": "Holds",
        "reverse": "Is held in",
        "between": [["system", "information"]],
    },
    {
        "key": "uses",
        "label": "Uses",
        "reverse": "Is used by",
        "between": [["process", "information"]],
    },
    {
        "key": "shared_with",
        "label": "Is shared with",
        "reverse": "Receives",
        "between": [["information", "third_party"]],
    },
    {
        "key": "reaches",
        "label": "Reaches",
        "reverse": "Is reached by",
        "between": [["service", "system"]],
    },
    {
        "key": "handles",
        "label": "Handles",
        "reverse": "Is handled by",
        "between": [["service", "information"]],
    },
    {
        "key": "subcontracts",
        "label": "Subcontracts to",
        "reverse": "Is a subcontractor of",
        "between": [["third_party", "third_party"]],
    },
    {
        "key": "depends_on",
        "label": "Depends on",
        "reverse": "Is depended on by",
        "between": [["process", "process"], ["system", "system"]],
    },
    {
        "key": "part_of",
        "label": "Is part of",
        "reverse": "Includes",
        "between": [["process", "process"], ["system", "system"]],
    },
]

# --- The scoring method -----------------------------------------------------------------

LIKELIHOOD = [
    {"level": 1, "key": "rare", "label": "Rare", "definition": "Not expected within ten years"},
    {
        "level": 2,
        "key": "unlikely",
        "label": "Unlikely",
        "definition": "Could happen once in five to ten years",
    },
    {
        "level": 3,
        "key": "possible",
        "label": "Possible",
        "definition": "Could happen once in two to five years",
    },
    {"level": 4, "key": "likely", "label": "Likely", "definition": "Expected about once a year"},
    {
        "level": 5,
        "key": "almost_certain",
        "label": "Almost certain",
        "definition": "Expected several times a year",
    },
]

IMPACT_LEVELS = [
    {"level": 1, "key": "negligible", "label": "Negligible"},
    {"level": 2, "key": "minor", "label": "Minor"},
    {"level": 3, "key": "moderate", "label": "Moderate"},
    {"level": 4, "key": "major", "label": "Major"},
    {"level": 5, "key": "severe", "label": "Severe"},
]


def dimension(key: str, label: str, question: str, *levels: str) -> dict[str, Any]:
    assert len(levels) == 5, key
    return {
        "key": key,
        "label": label,
        "question": question,
        "levels": {str(number): text for number, text in enumerate(levels, 1)},
    }


DIMENSIONS = [
    dimension(
        "mission",
        "Mission",
        "How far would research, care, or teaching be set back, and could the loss be recovered?",
        "No noticeable effect on research, care, or teaching.",
        "A delay of days to one group's work, fully recovered.",
        "Weeks of delay to several groups, or a study's timeline at risk; recoverable with effort.",
        "Months of work lost, a major program or service halted, or a study compromised.",
        "Irreplaceable material, data, or years of work lost, or the organization unable to "
        "carry out its mission.",
    ),
    dimension(
        "safety",
        "Safety",
        "Could patients, participants, staff, or the public be harmed?",
        "No harm to anyone.",
        "Minor injury or distress needing no more than first aid or reassurance.",
        "Harm needing medical treatment, or a patient or participant exposed to avoidable risk.",
        "Serious harm to one person, or lesser harm to many.",
        "Death, permanent harm, or serious harm to many.",
    ),
    dimension(
        "financial",
        "Financial",
        "What would it cost, as a share of the annual operating budget?",
        "Under one hundredth of one percent of the annual operating budget.",
        "Up to one tenth of one percent.",
        "Up to one percent.",
        "Up to five percent.",
        "More than five percent, or the organization's solvency in question.",
    ),
    dimension(
        "legal",
        "Legal and regulatory",
        "Would an obligation be breached, and what would follow?",
        "No obligation breached.",
        "A minor lapse, corrected internally, with nothing to report.",
        "A reportable breach, or a finding that needs a corrective action plan.",
        "Sanctions, repayment of funds, or an award or approval suspended.",
        "Loss of eligibility for funding, loss of a license or accreditation, or prosecution.",
    ),
    dimension(
        "trust",
        "Trust",
        "How would it affect the confidence of participants, patients, funders, partners, and "
        "the public?",
        "Not noticed outside the team.",
        "Noticed inside the organization, with no lasting effect.",
        "Complaints or local coverage; some participants, donors, or partners ask questions.",
        "Sustained coverage; participants withdraw, or a partner or funder steps back.",
        "Lasting loss of public confidence; recruitment, giving, or partnerships damaged for years.",
    ),
]

RATINGS = [
    {"key": "low", "label": "Low", "description": "Managed as part of ordinary work"},
    {
        "key": "moderate",
        "label": "Moderate",
        "description": "Watched, with an owner and a review each year",
    },
    {
        "key": "high",
        "label": "High",
        "description": "Needs a plan or a formal acceptance, and leadership's attention",
    },
    {
        "key": "critical",
        "label": "Critical",
        "description": "Needs action now, and the attention of the most senior leaders",
    },
]

# matrix[impact - 1][likelihood - 1]. It leans toward impact: a severe consequence is never
# rated below high, however rare.
MATRIX = [
    ["low", "low", "low", "low", "moderate"],
    ["low", "low", "moderate", "moderate", "moderate"],
    ["low", "moderate", "moderate", "high", "high"],
    ["moderate", "moderate", "high", "high", "critical"],
    ["high", "high", "high", "critical", "critical"],
]

SCORING_METHOD: dict[str, Any] = {
    "title": "Five by five, by the highest impact",
    "likelihood": LIKELIHOOD,
    "impact_levels": IMPACT_LEVELS,
    "dimensions": DIMENSIONS,
    "ratings": RATINGS,
    "matrix": MATRIX,
    # How far known-effective controls lower a suggested residual rating (see spec/engine.md).
    "control_effect": {
        "reliance": {"primary": 1.0, "supporting": 0.5},
        "strength": {"effective": 1.0, "partly": 0.5, "ineffective": 0.0, "not_assessed": 0.0},
        "limit": 2,
    },
}

# What wave 2 added. Severities are ordered from most to least: an issue's date follows from
# its severity by the table in CADENCES.
COMPLIANCE_VOCABULARIES: dict[str, list[dict[str, Any]]] = {
    "issue_severities": items(
        (
            "critical",
            "Critical",
            "Leaves people, patients, or regulated data exposed now, or breaks a legal obligation",
        ),
        (
            "high",
            "High",
            "A control the organization relies on does not work, with nothing making up for it",
        ),
        (
            "moderate",
            "Moderate",
            "A control works in part, or something else partly makes up for it",
        ),
        (
            "low",
            "Low",
            "A weakness in how something is done or recorded that does not yet leave anything exposed",
        ),
    ),
    # What can find an issue.
    "issue_sources": items(
        ("test", "Test", "A test in an assessment found a control wanting"),
        ("gap", "Gap", "A requirement that nothing answers, or a control with no evidence"),
        (
            "security_test",
            "Security testing",
            "A penetration test, a scan, or an exercise found it",
        ),
        ("audit", "Audit", "A finding from an internal or external audit"),
        ("incident", "Incident", "Something that went wrong showed it"),
        ("review", "Review", "A review of a supplier, a system, or a process"),
        ("observation", "Observation", "Somebody noticed it and said so"),
    ),
    # Why it happened, said when an issue is closed, so that causes can be counted.
    "root_causes": items(
        ("procedure", "Procedure", "There was no procedure, or it was unclear or out of date"),
        ("people", "People and time", "Not enough people, time, or training to do it"),
        (
            "ownership",
            "Ownership",
            "Nobody was clearly responsible, or it changed hands and was dropped",
        ),
        ("technology", "Technology", "A system could not do what was needed, or failed"),
        ("design", "Design", "The control was done as described and still did not meet the need"),
        ("change", "Change", "A change elsewhere was not followed through here"),
        ("third_party", "Third party", "A supplier or partner did not do its part"),
        ("other", "Other", "None of these, or not known"),
    ),
    # The other systems a record can be known in. An entry may carry a ``url`` with ``{id}``
    # in it, and identifiers in that system then become links.
    "external_systems": items(
        ("asset_tag", "Asset tag", "The number on the label, or in the asset register"),
        ("contract", "Contract number", "As the contracts or purchasing system knows it"),
        ("ticket", "Ticket", "A request or change in the service desk"),
        ("configuration_item", "Configuration item", "Its entry in a configuration database"),
        ("award", "Award number", "A grant or sponsored agreement"),
        ("other", "Other", "An identifier in any other system"),
    ),
}

# How often a risk is reviewed, by its residual rating; how long a control's rating, a test
# result, and evidence hold; how long after it is raised an issue is due, by severity; and
# the longest an exception may run.
CADENCES: dict[str, Any] = {
    "risk_review_months": {"critical": 3, "high": 6, "moderate": 12, "low": 24},
    "unrated_risk_review_months": 3,
    "control_rating_months": 12,
    "issue_due_days": {"critical": 30, "high": 90, "moderate": 180, "low": 365},
    "exception_max_months": 12,
    # A key control is tested more often than what is known of a control otherwise holds.
    "key_control_test_months": 6,
    # How long a policy, standard, procedure, or guideline goes before it is looked at again.
    "document_review_months": 12,
    # When reminders go: so many days before a date, and how long something stays late
    # before the unit's steward, and then its leader, is told.
    "reminders": {"soon_days": 14, "steward_after_days": 7, "leader_after_days": 21},
}

# Who may accept a risk above appetite, by its residual rating, and for how long.
AUTHORITY: dict[str, Any] = {
    "acceptance": {
        "moderate": {"max_months": 24, "needs_limit": False},
        "high": {"max_months": 12, "needs_limit": True},
        "critical": {"max_months": 6, "needs_limit": True},
    }
}

# How a third party is tiered (TPR-02). A tiering asks the questions of the questionnaire
# named here, with answers suggested from the inventory. The tiers are read in order: the
# first with a rule that holds is the one suggested, with every rule of it that holds as the
# reasons. The last tier has no rules: it is what a third party is when nothing above holds.
# Each rule is in the one condition language, over ``answers`` and ``facts`` (what the
# inventory says). ``review_months`` is how often a third party of the tier is reviewed;
# none means only when something calls for it.
REGULATED = ["health", "participant", "controlled", "cards", "identifiers", "students", "export"]
TIERING: dict[str, Any] = {
    "questionnaire": "third-party-tiering",
    "tiers": [
        {
            "key": "tier_1",
            "label": "Tier 1",
            "description": "Holds or can see restricted or regulated information, has privileged "
            "access to systems, or is relied on for critical work and reaches information or "
            "systems.",
            "review_months": 12,
            "rules": [
                {
                    "reason": "It holds, receives, or can see restricted information.",
                    "when": {"field": "answers.information", "op": "eq", "value": "restricted"},
                },
                {
                    "reason": "Some of the information is regulated, such as identifiable health "
                    "information or controlled-access data.",
                    "when": {
                        "field": "answers.regulated",
                        "op": "contains_any",
                        "value": REGULATED,
                    },
                },
                {
                    "reason": "It has administrator or privileged access to the organization's systems.",
                    "when": {"field": "answers.access", "op": "contains", "value": "privileged"},
                },
                {
                    "reason": "Critical work stops without it, and it reaches the organization's "
                    "information or systems.",
                    "when": {
                        "all": [
                            {"field": "answers.dependency", "op": "eq", "value": "stops"},
                            {
                                "any": [
                                    {
                                        "field": "answers.information",
                                        "op": "in",
                                        "value": ["confidential", "restricted"],
                                    },
                                    {
                                        "field": "answers.access",
                                        "op": "contains_any",
                                        "value": ["remote", "accounts", "integration"],
                                    },
                                ]
                            },
                        ]
                    },
                },
            ],
        },
        {
            "key": "tier_2",
            "label": "Tier 2",
            "description": "Holds confidential information, reaches systems, holds records about "
            "many people, or is relied on for critical work.",
            "review_months": 24,
            "rules": [
                {
                    "reason": "It holds, receives, or can see confidential information.",
                    "when": {"field": "answers.information", "op": "eq", "value": "confidential"},
                },
                {
                    "reason": "It reaches the organization's network, accounts, or systems.",
                    "when": {
                        "field": "answers.access",
                        "op": "contains_any",
                        "value": ["remote", "accounts", "integration"],
                    },
                },
                {
                    "reason": "It holds records about 500 or more people.",
                    "when": {"field": "answers.people", "op": "eq", "value": "many"},
                },
                {
                    "reason": "Critical work stops without it.",
                    "when": {"field": "answers.dependency", "op": "eq", "value": "stops"},
                },
            ],
        },
        {
            "key": "tier_3",
            "label": "Tier 3",
            "description": "Holds internal information, works on the premises, passes work to "
            "others, or would be missed.",
            "review_months": 36,
            "rules": [
                {
                    "reason": "It holds, receives, or can see internal information.",
                    "when": {"field": "answers.information", "op": "eq", "value": "internal"},
                },
                {
                    "reason": "It works on the premises, or has unescorted access to them.",
                    "when": {
                        "field": "answers.access",
                        "op": "contains_any",
                        "value": ["on_site", "physical"],
                    },
                },
                {
                    "reason": "Work would slow without it.",
                    "when": {"field": "answers.dependency", "op": "eq", "value": "slows"},
                },
                {
                    "reason": "It passes the organization's information or access on to others.",
                    "when": {"field": "answers.subcontractors", "op": "eq", "value": True},
                },
                {
                    "reason": "The information is held or reached from outside the United States.",
                    "when": {"field": "answers.offshore", "op": "eq", "value": True},
                },
            ],
        },
        {
            "key": "tier_4",
            "label": "Tier 4",
            "description": "Little is at stake: no information beyond what is public, no access, "
            "and easily replaced.",
            "review_months": None,
            "rules": [],
        },
    ],
}

# Which kinds of agreement information needs when it is shared with a third party (TPR-06).
# Each rule is in the condition language over ``information`` (its kind and data class),
# ``third_party`` (its kind and tier), and ``service`` (the kind of the service it is shared
# through, if any). Where a rule holds and no agreement of one of its kinds with that third
# party covers what is shared, the sharing is a stop. Written for the United States.
HANDLES_FOR_US = ["service_provider", "contractor", "supplier"]
SHARING: dict[str, Any] = {
    "rules": [
        {
            "key": "health_information",
            "reason": "Identifiable health information that a third party creates, receives, "
            "keeps, or sends on the organization's behalf needs a business associate agreement "
            "under HIPAA.",
            "when": {
                "all": [
                    {"field": "information.kind", "op": "eq", "value": "patient_records"},
                    {"field": "third_party.kind", "op": "in", "value": HANDLES_FOR_US},
                ]
            },
            "kinds": ["business_associate"],
        },
        {
            "key": "participant_data",
            "reason": "Information about research participants shared with a collaborator, "
            "sponsor, or subrecipient is shared under a data use agreement, or the terms of the "
            "award or contract it is shared for.",
            "when": {
                "all": [
                    {
                        "field": "information.kind",
                        "op": "in",
                        "value": ["participant_data", "patient_records"],
                    },
                    {
                        "field": "third_party.kind",
                        "op": "in",
                        "value": ["collaborator", "sponsor", "subrecipient"],
                    },
                ]
            },
            "kinds": ["data_use", "award", "contract"],
        },
        {
            "key": "controlled_data",
            "reason": "Data held under another party's terms is shared only as a data use "
            "agreement allows.",
            "when": {"field": "information.kind", "op": "eq", "value": "controlled_data"},
            "kinds": ["data_use"],
        },
        {
            "key": "restricted",
            "reason": "Restricted information is shared only under an agreement that binds the "
            "third party to protect it.",
            "when": {"field": "information.data_class", "op": "eq", "value": "restricted"},
            "kinds": ["contract", "confidentiality", "business_associate", "data_use", "award"],
        },
    ],
}

# --- The risk taxonomy ------------------------------------------------------------------


def category(
    key: str, name: str, appetite: str, description: str, *children: tuple[str, str]
) -> dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "appetite": appetite,
        "description": description,
        "children": [{"key": child[0], "name": child[1]} for child in children],
    }


CATEGORIES = [
    category(
        "strategic", "Strategic", "high",
        "The organization's direction, standing, and sources of support.",
        ("funding_environment", "Funding environment"),
        ("scientific_direction", "Scientific direction"),
        ("partnerships", "Partnerships and affiliations"),
        ("reputation", "Reputation and standing"),
    ),
    category(
        "research", "Research and scientific integrity", "moderate",
        "The conduct of research and the soundness of what it produces.",
        ("integrity", "Research integrity"),
        ("human_subjects", "Human participants"),
        ("animals", "Animal research"),
        ("data_quality", "Data and specimen integrity"),
        ("research_security", "Research security"),
    ),
    category(
        "clinical", "Clinical and participant safety", "low",
        "The safety of patients and of participants in clinical research.",
        ("patient_safety", "Patient safety"),
        ("medication", "Medication"),
        ("infection", "Infection prevention"),
        ("clinical_trial_conduct", "Conduct of clinical trials"),
    ),
    category(
        "regulatory", "Regulatory and legal", "low",
        "What the law, regulators, sponsors, and agreements require.",
        ("privacy", "Privacy"),
        ("grants", "Award and agreement terms"),
        ("licensing", "Licensing and accreditation"),
        ("employment", "Employment and conduct"),
    ),
    category(
        "technology", "Information and technology", "moderate",
        "The confidentiality, integrity, and availability of information and systems.",
        ("confidentiality", "Confidentiality of information"),
        ("availability", "Availability of systems"),
        ("integrity_change", "Integrity and change"),
        ("ai", "Use of AI and automation"),
    ),
    category(
        "operations", "Operations and facilities", "moderate",
        "The buildings, equipment, and services that work depends on.",
        ("facilities", "Facilities and utilities"),
        ("equipment", "Equipment and instruments"),
        ("biosafety", "Biological, chemical, and radiation safety"),
        ("continuity", "Continuity of operations"),
    ),
    category(
        "people", "People and culture", "moderate",
        "The people who do the work, and how they are treated.",
        ("workforce", "Workforce and succession"),
        ("wellbeing", "Safety and wellbeing of staff"),
        ("conduct", "Conduct and training"),
    ),
    category(
        "financial", "Financial and stewardship", "low",
        "The organization's money, and the money entrusted to it.",
        ("stewardship", "Stewardship of sponsored funds"),
        ("fraud", "Fraud and misuse"),
        ("liquidity", "Liquidity and reserves"),
        ("philanthropy", "Philanthropy"),
    ),
    category(
        "third_party", "Third party", "moderate",
        "What the organization depends on others for.",
        ("supplier_dependence", "Dependence on a supplier"),
        ("supplier_security", "A supplier's handling of information"),
        ("subrecipients", "Subrecipients and collaborators"),
    ),
]  # fmt: skip

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
    "vocabularies": {**VOCABULARIES, "link_kinds": LINK_KINDS, **COMPLIANCE_VOCABULARIES},
    "categories": CATEGORIES,
    "scoring_method": SCORING_METHOD,
    "cadences": CADENCES,
    "authority": AUTHORITY,
    "tiering": TIERING,
    "sharing": SHARING,
}

# --- The risk library -------------------------------------------------------------------
# Reusable statements to start a risk from. Each names a cause, an event, and a consequence,
# and is meant to be made specific by whoever raises the risk.

LIBRARY_ROWS: list[tuple[str, str, str, str, str, str]] = [
    # Strategic
    ("funding_concentration", "funding_environment", "Dependence on a single funder",
     "A large share of research funding comes from one sponsor or program",
     "that sponsor's priorities or budget change",
     "programs lose support faster than they can be wound down or funded again"),
    ("indirect_cost_change", "funding_environment", "Change to indirect cost recovery",
     "Sponsors revise what overhead they will pay",
     "recovery falls well below the cost of supporting research",
     "shared services and facilities are cut or run at a loss"),
    ("key_program_decline", "scientific_direction", "A leading program loses its edge",
     "Investment follows established strengths while the field moves",
     "a leading program falls behind its peers",
     "recruitment, funding, and standing decline together"),
    ("affiliation_dispute", "partnerships", "Breakdown of a major affiliation",
     "Shared governance with a partner institution rests on agreements that have aged",
     "the partner changes strategy or leadership and the arrangement is contested",
     "shared programs, appointments, and facilities are disrupted"),
    ("public_controversy", "reputation", "Public controversy over research or conduct",
     "Work or behavior that some will object to is not anticipated",
     "it becomes a public story before the organization has responded",
     "trust among participants, donors, and partners is damaged"),
    # Research and scientific integrity
    ("misconduct_undetected", "integrity", "Research misconduct goes undetected",
     "Pressure to publish, and supervision that varies from lab to lab",
     "fabricated, falsified, or plagiarized work is published",
     "retractions, sanctions from sponsors, and lasting harm to reputations"),
    ("unreproducible_results", "integrity", "Results that cannot be supported",
     "Laboratory records are kept inconsistently and leave with people",
     "published results cannot be reproduced or supported when questioned",
     "corrections or retractions, and loss of confidence in the lab's work"),
    ("protocol_lapse", "human_subjects", "Research outside its approved protocol",
     "Amendments, renewals, and consent versions are tracked by hand",
     "participants are enrolled or procedures carried out without current approval",
     "participants are put at risk, data cannot be used, and the study may be suspended"),
    ("participant_privacy", "human_subjects", "Identifiable participant data disclosed",
     "Research data is copied, shared, and analyzed outside managed systems",
     "identifiable information reaches someone not entitled to it",
     "harm to participants, a duty to notify, and loss of trust in the organization's research"),
    ("animal_welfare", "animals", "Animal welfare failure",
     "Environmental controls or staffing in an animal facility fail out of hours",
     "animals suffer or die",
     "loss of research, regulatory findings, and public concern"),
    ("specimen_loss", "data_quality", "Loss of irreplaceable specimens",
     "Freezers, the supply of liquid nitrogen, or their monitoring fail",
     "stored specimens thaw before anyone responds",
     "years of collection are lost and the studies that depend on them cannot be completed"),
    ("research_data_loss", "data_quality", "Loss of research data",
     "Data sits on instruments, laptops, and portable drives without managed backup",
     "a device fails, is lost, or is encrypted by an attacker",
     "results cannot be reproduced and funded work must be repeated or abandoned"),
    ("undisclosed_support", "research_security", "Undisclosed outside support or affiliation",
     "Researchers are unsure what must be disclosed, and nobody checks",
     "a sponsor finds support, an appointment, or a conflict that was not reported",
     "repayment, loss of awards, and exclusion of people or the organization from funding"),
    ("controlled_technology", "research_security", "Controlled items shared without authorization",
     "Controlled technology and information are not identified at the start of a project",
     "they are shared with a person or place the law restricts",
     "penalties, loss of privileges, and personal liability"),
    # Clinical and participant safety
    ("medication_error", "medication", "Medication error",
     "Products that look alike, interruptions, and transcription by hand",
     "a patient receives the wrong drug or dose",
     "harm to the patient and loss of confidence in the service"),
    ("patient_identification", "patient_safety", "Wrong patient or wrong procedure",
     "Identity is confirmed inconsistently at handoffs",
     "a test, treatment, or specimen is attributed to the wrong person",
     "harm, repeated procedures, and results that cannot be relied on"),
    ("care_infection", "infection", "Infection acquired during care",
     "Lapses in hygiene, cleaning, or isolation among vulnerable patients",
     "an infection spreads within a clinical area",
     "serious harm to patients and closure of the area"),
    ("trial_deviation", "clinical_trial_conduct", "Serious deviation in a clinical trial",
     "Complex protocols and stretched study staff",
     "eligibility, dosing, or safety reporting departs from the protocol",
     "participants are put at risk and the trial's data may be rejected"),
    ("clinical_downtime", "patient_safety", "Clinical systems unavailable during care",
     "Care depends on electronic records and connected devices",
     "they are unavailable for hours and working without them has not been practiced",
     "care is delayed and errors become more likely"),
    ("missed_deterioration", "patient_safety", "A patient's decline is missed",
     "Monitoring and escalation depend on individual vigilance",
     "a patient's deterioration is noticed or acted on late",
     "avoidable harm or death"),
    # Regulatory and legal
    ("health_information_breach", "privacy", "Breach of protected health information",
     "Health information is held in many systems and handled by many people",
     "it is lost, stolen, or seen by someone with no need to",
     "harm to individuals, notification to them and to regulators, and penalties"),
    ("access_not_removed", "privacy", "Access kept after a person leaves or changes role",
     "Access is granted readily and removed only when someone remembers",
     "a former or reassigned person still reaches sensitive systems",
     "unauthorized use or disclosure that the organization must answer for"),
    ("award_terms", "grants", "Terms of an award not met",
     "Each award has its own conditions, known mainly to its investigator",
     "a condition on reporting, data sharing, or spending is missed",
     "funds are withheld or repaid and future applications are prejudiced"),
    ("data_agreement", "grants", "Data used outside its agreement",
     "Data received under an agreement is passed between projects and people",
     "it is used, combined, or shared in a way the agreement forbids",
     "the provider withdraws the data and declines to share again"),
    ("accreditation_lapse", "licensing", "Loss of a license or accreditation",
     "Standards change, and evidence of meeting them is assembled only before a visit",
     "an inspection finds serious gaps",
     "a service is suspended and its work must stop or move"),
    ("conduct_not_addressed", "employment", "Harassment or retaliation not addressed",
     "People doubt that reporting is safe or leads anywhere",
     "serious conduct continues after it could have been stopped",
     "harm to individuals, legal action, and loss of talent"),
    # Information and technology
    ("ransomware", "availability", "Ransomware",
     "Phishing, unpatched systems, and broad access rights",
     "an attacker encrypts systems and data across the network",
     "research and care stop for days or weeks, and data may be lost or published"),
    ("compromised_account", "confidentiality", "Compromised account",
     "Passwords are reused and some access lacks a second factor",
     "an attacker signs in as a member of staff",
     "information is stolen, and the account is used to reach further"),
    ("unsupported_systems", "integrity_change", "Unsupported systems in use",
     "Instruments and applications outlive the software they run on",
     "a known weakness is exploited, or the system fails beyond repair",
     "the work that depends on it stops, and the weakness reaches other systems"),
    ("failed_change", "integrity_change", "A change breaks a critical system",
     "Changes are made under time pressure with limited testing",
     "an update or a change of configuration takes a critical system out of service",
     "work stops until it is undone, and data may be corrupted"),
    ("backup_failure", "availability", "Backups cannot be restored",
     "Backups run unattended and restores are rarely tested",
     "data must be restored and the backup is incomplete or unusable",
     "permanent loss of data the organization believed was safe"),
    ("exposed_storage", "confidentiality", "Data exposed by misconfiguration",
     "Cloud storage and sharing are set up by people outside central teams",
     "sensitive data is left open to the internet or to everyone in the organization",
     "disclosure that may go unnoticed for months"),
    ("unreviewed_ai", "ai", "Unreviewed use of AI with sensitive data",
     "AI tools are easy to adopt without anyone's approval",
     "sensitive or regulated data is entered into a tool with no agreement covering it",
     "data is disclosed, and results are relied on that nobody has checked"),
    ("sign_in_outage", "availability", "Sign-in service unavailable",
     "Every system depends on one identity service",
     "it fails or is locked by an attacker",
     "nobody can work until it is restored"),
    # Operations and facilities
    ("power_failure", "facilities", "Extended loss of power",
     "Backup generation is sized and tested for short outages",
     "power is lost for longer than the backup can carry",
     "specimens, animals, experiments, and systems are lost"),
    ("environmental_control", "facilities", "Loss of environmental control",
     "Ventilation and cooling serve laboratories, animal rooms, and data rooms with little to spare",
     "a plant failure takes temperature or air handling out of range",
     "work stops, materials are lost, and spaces become unsafe"),
    ("critical_instrument", "equipment", "Failure of a critical instrument",
     "A core service depends on one instrument with a long repair time",
     "it fails with no alternative arranged",
     "many groups' work waits for weeks"),
    ("hazard_exposure", "biosafety", "Exposure to a hazardous agent",
     "Hazardous biological, chemical, or radioactive materials are handled daily",
     "a spill, release, or sharps injury exposes someone",
     "injury or illness, regulatory findings, and suspension of the work"),
    ("fire_or_flood", "facilities", "Fire or flood in a research building",
     "Laboratories hold flammable materials and water-cooled equipment",
     "a fire or major leak damages a building",
     "people are endangered, and space, equipment, and materials are lost for months"),
    ("regional_disaster", "continuity", "Regional disaster",
     "The organization is concentrated in one place",
     "an earthquake, storm, or epidemic closes it for an extended period",
     "research and care are interrupted well beyond what plans assume"),
    # People and culture
    ("key_person", "workforce", "Loss of a key person",
     "Essential knowledge or relationships rest with one person",
     "they leave or are suddenly unavailable",
     "a program, service, or system cannot continue as it was"),
    ("recruitment", "workforce", "Unable to recruit or keep skilled staff",
     "Pay and career paths lag behind competing employers",
     "critical roles stay vacant or turn over repeatedly",
     "services degrade and the staff who remain are overloaded"),
    ("workplace_injury", "wellbeing", "Serious workplace injury",
     "Laboratory, clinical, and facilities work carries physical hazards",
     "someone is seriously injured at work",
     "harm to the person, an investigation, and loss of confidence among colleagues"),
    ("sustained_overload", "wellbeing", "Sustained overload",
     "Demands rise faster than staffing",
     "exhaustion becomes widespread in a team",
     "errors, absence, and departures increase together"),
    ("training_lapse", "conduct", "Required training not completed",
     "Training requirements multiply and are tracked in several places",
     "people do work they are not currently trained or authorized for",
     "avoidable incidents, and findings at inspection"),
    # Financial and stewardship
    ("unallowable_costs", "stewardship", "Unallowable costs charged to an award",
     "Charges are approved by people unfamiliar with each sponsor's rules",
     "costs the sponsor does not allow are charged and certified",
     "repayment, audit findings, and closer scrutiny of every award"),
    ("effort_certification", "stewardship", "Effort not certified accurately",
     "Effort is certified after the fact by busy investigators",
     "salary charged to awards does not match the work done",
     "repayment, and findings that reach across the organization"),
    ("subrecipient_monitoring", "stewardship", "Subrecipient not monitored",
     "Funds pass to partner organizations whose controls are unknown",
     "a subrecipient misspends the funds or cannot account for them",
     "the organization must repay them and answer for the failure"),
    ("payment_fraud", "fraud", "Payment fraud",
     "Requests to change bank details are accepted by email",
     "a payment is sent to an impostor",
     "the money is lost and rarely recovered"),
    ("purchasing_misuse", "fraud", "Misuse of purchasing authority",
     "Many people can buy with little review",
     "personal or improper purchases are made over time",
     "loss of funds, and of confidence in the organization's stewardship"),
    ("operating_shortfall", "liquidity", "Operating shortfall",
     "Costs are committed years ahead while income is awarded year by year",
     "income falls well short of plan",
     "reserves are drawn down and programs are cut at short notice"),
    ("gift_terms", "philanthropy", "Gift used against its terms",
     "Restrictions on gifts are recorded at the time and forgotten later",
     "a restricted gift is spent on something else",
     "the donor's trust is lost and the gift may have to be restored"),
    # Third party
    ("sole_supplier", "supplier_dependence", "Dependence on a single supplier",
     "A critical material, reagent, or service has one source",
     "the supplier fails, is acquired, or cannot deliver",
     "the work that depends on it stops until another source is found and qualified"),
    ("hosted_service_outage", "supplier_dependence", "A hosted service is unavailable",
     "A critical system is run entirely by a supplier",
     "the supplier has a prolonged outage or ends the service",
     "the organization cannot work and cannot fix it"),
    ("supplier_breach", "supplier_security", "A supplier discloses the organization's information",
     "Sensitive information is held by suppliers whose safeguards are taken on trust",
     "the supplier is breached or misuses the information",
     "the organization must notify those affected and answer for a failure it could not see"),
    ("missing_agreement", "supplier_security", "Regulated information shared without an agreement",
     "Services are bought and data shared before anyone checks what agreement is needed",
     "protected information is held by a party with no agreement covering it",
     "a violation exists from the first day, whether or not anything goes wrong"),
    ("collaborator_failure", "subrecipients", "A collaborator does not deliver",
     "A study depends on work at another institution",
     "the collaborator falls behind, loses staff, or withdraws",
     "the study is delayed or cannot be completed as funded"),
]  # fmt: skip

# The starter controls each library risk suggests, by key.
SUGGESTED: dict[str, list[str]] = {
    "funding_concentration": ["funding_diversified", "budget_monitoring"],
    "indirect_cost_change": ["budget_monitoring", "funding_diversified"],
    "key_program_decline": ["funding_diversified"],
    "affiliation_dispute": ["issues_communication"],
    "public_controversy": ["issues_communication", "reporting_channel"],
    "misconduct_undetected": ["integrity_training", "research_records", "reporting_channel"],
    "unreproducible_results": ["research_records", "integrity_training"],
    "protocol_lapse": ["protocol_tracking", "training_tracked"],
    "participant_privacy": [
        "data_classified",
        "encryption_at_rest",
        "data_sharing_approved",
        "access_reviewed",
    ],
    "animal_welfare": ["animal_care_checks", "environmental_monitoring", "backup_power_tested"],
    "specimen_loss": [
        "freezer_monitoring",
        "preventive_maintenance",
        "specimen_split",
        "backup_capacity",
        "backup_power_tested",
    ],
    "research_data_loss": ["backups_tested", "data_classified", "encryption_at_rest"],
    "undisclosed_support": ["disclosure_review", "integrity_training"],
    "controlled_technology": ["export_screening", "training_tracked"],
    "medication_error": ["medication_double_check", "two_identifiers"],
    "patient_identification": ["two_identifiers"],
    "care_infection": ["infection_prevention"],
    "trial_deviation": ["trial_monitoring", "protocol_tracking", "training_tracked"],
    "clinical_downtime": ["downtime_procedures", "continuity_plan"],
    "missed_deterioration": ["early_warning"],
    "health_information_breach": [
        "access_reviewed",
        "encryption_at_rest",
        "logging_monitoring",
        "security_training",
        "encryption_in_transit",
        "access_approved",
        "media_disposal",
    ],
    "access_not_removed": ["access_removed_on_leaving", "access_reviewed", "access_approved"],
    "award_terms": ["agreements_recorded", "cost_review"],
    "data_agreement": ["agreements_recorded", "data_sharing_approved"],
    "accreditation_lapse": ["standards_tracked"],
    "conduct_not_addressed": ["reporting_channel"],
    "ransomware": [
        "backups_tested",
        "patching",
        "second_factor",
        "security_training",
        "network_segmentation",
        "incident_response",
        "vulnerability_scanning",
        "disaster_recovery",
    ],
    "compromised_account": [
        "second_factor",
        "security_training",
        "logging_monitoring",
        "privileged_access",
        "unique_accounts",
        "session_lock",
        "remote_access",
    ],
    "unsupported_systems": [
        "unsupported_contained",
        "network_segmentation",
        "patching",
        "asset_inventory",
    ],
    "failed_change": ["change_review", "backups_tested"],
    "backup_failure": ["backups_tested", "disaster_recovery"],
    "exposed_storage": [
        "data_classified",
        "logging_monitoring",
        "access_reviewed",
        "secure_configuration",
    ],
    "unreviewed_ai": ["ai_use_reviewed", "data_classified", "agreements_in_place"],
    "sign_in_outage": [
        "continuity_plan",
        "privileged_access",
        "incident_response",
        "disaster_recovery",
    ],
    "power_failure": ["backup_power_tested", "continuity_plan"],
    "environmental_control": ["environmental_monitoring", "preventive_maintenance"],
    "critical_instrument": ["preventive_maintenance", "alternate_supplier", "backup_capacity"],
    "hazard_exposure": ["safety_training"],
    "fire_or_flood": ["safety_training", "continuity_plan", "specimen_split"],
    "regional_disaster": ["continuity_plan", "backups_tested"],
    "key_person": ["succession"],
    "recruitment": ["workload_review", "succession"],
    "workplace_injury": ["safety_training"],
    "sustained_overload": ["workload_review"],
    "training_lapse": ["training_tracked"],
    "unallowable_costs": ["cost_review", "separation_of_duties"],
    "effort_certification": ["effort_certified", "cost_review"],
    "subrecipient_monitoring": ["subrecipient_review"],
    "payment_fraud": ["payment_verification", "separation_of_duties"],
    "purchasing_misuse": ["separation_of_duties"],
    "operating_shortfall": ["budget_monitoring", "funding_diversified"],
    "gift_terms": ["gift_terms_recorded"],
    "sole_supplier": ["alternate_supplier", "backup_capacity"],
    "hosted_service_outage": ["exit_plan", "continuity_plan"],
    "supplier_breach": ["supplier_assessed", "agreements_in_place"],
    "missing_agreement": ["agreements_in_place", "supplier_assessed"],
    "collaborator_failure": ["subrecipient_review", "agreements_recorded"],
}

# --- The starter controls ---------------------------------------------------------------
# Common controls in plain words: each a sentence a control owner would recognize as their
# own job. key, title, statement, kind, nature, frequency, and what it mainly reduces.

CONTROL_ROWS: list[tuple[str, str, str, str, str, str, str]] = [
    # Access and identity
    ("access_removed_on_leaving", "Access removed when people leave",
     "Access to systems is removed on the day a person leaves, and reviewed when they change role.",
     "preventive", "both", "as_needed", "likelihood"),
    ("access_reviewed", "Access reviewed",
     "Owners of sensitive systems confirm twice a year that everyone with access still needs it.",
     "detective", "manual", "twice_a_year", "likelihood"),
    ("second_factor", "Second factor at sign-in",
     "Signing in from outside the organization, or to anything holding restricted data, needs a second factor.",
     "preventive", "automated", "continuous", "likelihood"),
    ("privileged_access", "Administrative access limited",
     "Administrative rights are held by named people, used from separate accounts, and recorded.",
     "preventive", "both", "continuous", "likelihood"),
    # Information
    ("encryption_at_rest", "Devices and storage encrypted",
     "Laptops, portable drives, and storage that hold confidential or restricted data are encrypted.",
     "preventive", "automated", "continuous", "impact"),
    ("backups_tested", "Backups tested by restoring",
     "Critical data is backed up to a place an attacker on the network cannot reach, and a restore is tested every quarter.",
     "corrective", "both", "quarterly", "impact"),
    ("data_classified", "Data classified and handled accordingly",
     "Each body of data has a class, and where it may be stored and shared follows from that class.",
     "directive", "manual", "as_needed", "likelihood"),
    ("data_sharing_approved", "Data sharing approved",
     "Sharing restricted data outside the organization needs an agreement in place and a named approver.",
     "preventive", "manual", "as_needed", "likelihood"),
    # Systems
    ("patching", "Systems kept patched",
     "Security updates are applied within a set time, and systems that cannot be patched are isolated and listed.",
     "preventive", "both", "monthly", "likelihood"),
    ("malware_protection", "Protection against malicious software",
     "Servers and workstations run managed protection that is monitored centrally.",
     "preventive", "automated", "continuous", "likelihood"),
    ("network_segmentation", "Networks separated",
     "Instruments, clinical devices, and systems that cannot be patched sit on networks separated from general use.",
     "preventive", "automated", "continuous", "impact"),
    ("unsupported_contained", "Unsupported systems listed and contained",
     "Each system that no longer receives updates has an owner, an end date, and compensating safeguards.",
     "directive", "manual", "annually", "likelihood"),
    ("change_review", "Changes reviewed and reversible",
     "Changes to critical systems are tested, approved by a second person, and can be undone.",
     "preventive", "manual", "as_needed", "likelihood"),
    ("logging_monitoring", "Security events monitored",
     "Sign-ins and administrative actions on critical systems are logged and watched, and alerts are acted on.",
     "detective", "both", "continuous", "impact"),
    ("incident_response", "Incident response rehearsed",
     "There is a written plan for a security incident, with named roles, and it is exercised each year.",
     "corrective", "manual", "annually", "impact"),
    ("security_training", "Security awareness training",
     "Everyone completes security training when they join and each year, and phishing exercises are run.",
     "preventive", "manual", "annually", "likelihood"),
    # Running a security program
    ("access_approved", "Access approved before it is given",
     "Access to a system is requested, approved by the system's owner, limited to what the role needs, and recorded.",
     "preventive", "manual", "as_needed", "likelihood"),
    ("unique_accounts", "Everyone signs in as themselves",
     "Each person has an account of their own, shared accounts are not used, and passwords meet a written standard.",
     "preventive", "both", "continuous", "likelihood"),
    ("session_lock", "Screens lock and sessions end",
     "Workstations lock after a short time unused, repeated failed sign-ins lock the account, and idle sessions are ended.",
     "preventive", "automated", "continuous", "likelihood"),
    ("remote_access", "Remote and wireless access controlled",
     "Access from outside comes through managed gateways, wireless networks are separated and encrypted, and personal and mobile devices reach only what is approved.",
     "preventive", "both", "continuous", "likelihood"),
    ("personnel_screening", "People screened and bound by rules of use",
     "People are screened as their role requires before they are given access, agree to the rules for using systems, and know what follows from breaking them.",
     "preventive", "manual", "as_needed", "likelihood"),
    ("encryption_in_transit", "Information encrypted in transit",
     "Connections that carry confidential or restricted data are encrypted with current protocols, inside the network and out.",
     "preventive", "automated", "continuous", "likelihood"),
    ("media_disposal", "Devices and media wiped before they leave",
     "Storage is erased or destroyed before a device is reused, returned, or disposed of, and a record is kept.",
     "preventive", "manual", "as_needed", "likelihood"),
    ("asset_inventory", "Systems and software inventoried",
     "Hardware, software, and services are listed with an owner, and the list is checked against what is found on the network.",
     "detective", "both", "quarterly", "likelihood"),
    ("secure_configuration", "Systems built to a secure standard",
     "Servers, workstations, and network devices are built from a hardened standard with only what they need, and drift from it is found and corrected.",
     "preventive", "both", "continuous", "likelihood"),
    ("vulnerability_scanning", "Vulnerabilities found and followed up",
     "Systems are scanned for known weaknesses on a schedule, advisories are read, and what is found is ranked, assigned, and followed to closure.",
     "detective", "both", "monthly", "likelihood"),
    ("log_protection", "Logs kept and protected",
     "Logs from critical systems go to a central store, are kept for a set time, are protected from change, and take their time from one clock.",
     "detective", "automated", "continuous", "impact"),
    ("incident_reporting", "Security incidents reported and followed up",
     "Anyone can report a suspected incident at any hour. Each one is triaged, contained, recorded, reviewed afterwards, and reported to those who must be told.",
     "corrective", "manual", "as_needed", "impact"),
    ("disaster_recovery", "Recovery of systems planned and tested",
     "Critical systems have a recovery plan with an order of restoration and target times, and it is tested each year.",
     "corrective", "manual", "annually", "impact"),
    ("physical_access", "Physical access to systems limited",
     "Data rooms, network closets, and rooms with sensitive equipment are locked, entry is limited to named people and recorded, and visitors are escorted.",
     "preventive", "both", "continuous", "likelihood"),
    ("security_policy", "Security policies kept current",
     "Written security policies and standards are approved by leadership, reviewed each year, kept with their earlier versions, and available to everyone they bind.",
     "directive", "manual", "annually", "likelihood"),
    ("security_roles", "Security responsibilities assigned",
     "A named person answers for security, and the roles and authority of everyone with a part in it are written down.",
     "directive", "manual", "annually", "likelihood"),
    ("security_oversight", "Security reported to leadership",
     "Leadership says how much security risk it will take, hears where security stands at least twice a year, and decides what is resourced.",
     "directive", "manual", "twice_a_year", "likelihood"),
    ("security_risk_assessment", "Security risks assessed",
     "Risks to systems and information are assessed each year and when something significant changes, and the result decides what is done.",
     "detective", "manual", "annually", "likelihood"),
    ("security_testing", "Security assessed independently",
     "Each year the controls are assessed, and a penetration test is run, by people who do not operate the systems, and what they find is tracked to closure.",
     "detective", "manual", "annually", "likelihood"),
    ("ai_use_reviewed", "Use of AI tools reviewed",
     "A new AI tool, or a new use of one with sensitive data, is reviewed before use, and approved tools are listed.",
     "preventive", "manual", "as_needed", "likelihood"),
    # Facilities and research operations
    ("freezer_monitoring", "Cold storage monitored and alarmed",
     "Freezers and liquid nitrogen stores are monitored continuously, and an alarm reaches a person who can respond at any hour.",
     "detective", "both", "continuous", "likelihood"),
    ("preventive_maintenance", "Critical equipment maintained",
     "Critical equipment is maintained on a schedule under contract, and the records are kept.",
     "preventive", "manual", "quarterly", "likelihood"),
    ("specimen_split", "Irreplaceable material held in two places",
     "Irreplaceable specimens are divided between two locations with separate power and cooling.",
     "corrective", "manual", "as_needed", "impact"),
    ("backup_power_tested", "Backup power tested under load",
     "Generators and their fuel supply are tested under load each month, and critical equipment is confirmed to be on backup circuits.",
     "preventive", "manual", "monthly", "impact"),
    ("backup_capacity", "Spare capacity kept ready",
     "Empty backup freezers and spare critical parts are kept ready for use.",
     "corrective", "manual", "quarterly", "impact"),
    ("environmental_monitoring", "Environment monitored",
     "Temperature, humidity, and air handling in laboratories, animal rooms, and data rooms are monitored and alarmed.",
     "detective", "automated", "continuous", "likelihood"),
    ("safety_training", "Laboratory safety training and inspection",
     "People who work with hazardous materials are trained before they start, and laboratories are inspected each year.",
     "preventive", "manual", "annually", "likelihood"),
    ("continuity_plan", "Continuity plans exercised",
     "Critical services have a plan for carrying on without their systems or space, and it is exercised each year.",
     "corrective", "manual", "annually", "impact"),
    ("animal_care_checks", "Animal facilities checked daily",
     "Animal rooms are checked every day, weekends included, and environmental alarms reach on-call staff.",
     "detective", "manual", "daily", "likelihood"),
    # Research integrity and compliance
    ("protocol_tracking", "Protocols tracked to renewal",
     "Every study's approvals, amendments, and consent versions are tracked, with reminders before anything lapses.",
     "preventive", "both", "monthly", "likelihood"),
    ("research_records", "Research records kept to a standard",
     "Laboratories keep records to a written standard, in a system the organization holds, and they stay when people leave.",
     "preventive", "manual", "continuous", "likelihood"),
    ("integrity_training", "Research integrity training and review",
     "Researchers are trained in responsible conduct, and data is reviewed within the lab before publication.",
     "preventive", "manual", "annually", "likelihood"),
    ("disclosure_review", "Outside interests disclosed and reviewed",
     "Researchers disclose outside support, appointments, and interests each year and when they change, and disclosures are checked against applications.",
     "detective", "manual", "annually", "likelihood"),
    ("export_screening", "Controlled items identified at the start",
     "Projects are screened for controlled technology, information, and restricted parties before work begins.",
     "preventive", "manual", "as_needed", "likelihood"),
    ("agreements_recorded", "Agreements recorded with their terms",
     "Each award and data use agreement is recorded with its conditions and an owner who answers for meeting them.",
     "directive", "manual", "as_needed", "likelihood"),
    ("standards_tracked", "Standards tracked all year",
     "Each license and accreditation has an owner who tracks its standards and keeps the evidence current all year.",
     "preventive", "manual", "quarterly", "likelihood"),
    # Clinical
    ("two_identifiers", "Two identifiers before any procedure",
     "Identity is confirmed with two identifiers before any test, treatment, or specimen collection.",
     "preventive", "manual", "continuous", "likelihood"),
    ("medication_double_check", "High-risk medication double-checked",
     "High-risk medications are checked independently by a second person or by scanning before they are given.",
     "preventive", "both", "continuous", "likelihood"),
    ("infection_prevention", "Infection prevention audited",
     "Hand hygiene, cleaning, and isolation practice are audited each month and the results shared.",
     "detective", "manual", "monthly", "likelihood"),
    ("downtime_procedures", "Downtime procedures practiced",
     "Clinical areas keep procedures for working without their systems, and practice them twice a year.",
     "corrective", "manual", "twice_a_year", "impact"),
    ("trial_monitoring", "Trials monitored against protocol",
     "Each trial is monitored against its protocol, and deviations are reviewed and reported.",
     "detective", "manual", "quarterly", "impact"),
    ("early_warning", "Deterioration recognized and escalated",
     "Vital signs are scored at set intervals, and a score above the threshold brings a rapid response.",
     "detective", "both", "continuous", "impact"),
    # Financial
    ("cost_review", "Charges to awards reviewed",
     "Charges to sponsored awards are reviewed against the award's terms each month by someone trained in them.",
     "detective", "manual", "monthly", "likelihood"),
    ("effort_certified", "Effort certified on time",
     "Effort charged to awards is certified by someone with direct knowledge, within the set period.",
     "detective", "manual", "twice_a_year", "likelihood"),
    ("subrecipient_review", "Subrecipients assessed and monitored",
     "Subrecipients are assessed before funds are passed to them, and their reports and invoices are reviewed.",
     "preventive", "manual", "annually", "likelihood"),
    ("payment_verification", "Changes to payment details verified",
     "A request to change bank details is confirmed by calling a known number before any payment is made.",
     "preventive", "manual", "as_needed", "likelihood"),
    ("separation_of_duties", "Purchasing duties separated",
     "Nobody both requests and approves a purchase, and card spending is reviewed each month.",
     "preventive", "both", "monthly", "likelihood"),
    ("budget_monitoring", "Budgets monitored and reserves held",
     "Income and spending are compared with plan each month, and reserves are held to a set level.",
     "detective", "manual", "monthly", "impact"),
    ("gift_terms_recorded", "Gift restrictions recorded and checked",
     "The terms of each restricted gift are recorded, and spending from it is checked against them.",
     "preventive", "manual", "as_needed", "likelihood"),
    # People
    ("succession", "Knowledge shared and deputies named",
     "Critical roles have a named deputy, and the knowledge they depend on is written down.",
     "corrective", "manual", "annually", "impact"),
    ("training_tracked", "Required training tracked",
     "Required training is recorded in one place, and people are reminded before it lapses.",
     "detective", "both", "monthly", "likelihood"),
    ("reporting_channel", "A safe way to raise concerns",
     "Concerns can be raised in confidence and are followed up, and retaliation is not tolerated.",
     "detective", "manual", "continuous", "impact"),
    ("workload_review", "Workload and staffing reviewed",
     "Leaders review workload, vacancies, and turnover each quarter and act on what they find.",
     "detective", "manual", "quarterly", "likelihood"),
    # Third parties
    ("supplier_assessed", "Suppliers assessed before use",
     "A supplier that will hold restricted data or run a critical service is assessed before it is engaged, and again on a schedule.",
     "preventive", "manual", "annually", "likelihood"),
    ("agreements_in_place", "Required agreements in place",
     "No regulated information is shared with a third party until the agreement it requires is signed.",
     "preventive", "manual", "as_needed", "likelihood"),
    ("alternate_supplier", "A second source identified",
     "For each critical material or service, a second source has been identified and, where possible, qualified.",
     "corrective", "manual", "annually", "impact"),
    ("exit_plan", "A way out of each critical service",
     "For each critical hosted service, the organization knows how it would get its data back and carry on elsewhere.",
     "corrective", "manual", "annually", "impact"),
    # Strategy
    ("funding_diversified", "Funding sources watched and spread",
     "Leadership reviews the mix of funding each year and sets limits on dependence on any one source.",
     "directive", "manual", "annually", "impact"),
    ("issues_communication", "Sensitive issues anticipated",
     "Sensitive work is identified in advance, and there is a plan for who speaks and what is said.",
     "corrective", "manual", "as_needed", "impact"),
]  # fmt: skip

# Which requirements of the built-in frameworks each starter control helps to satisfy. A
# starting point, written for RiskWren and meant to be corrected: a control adopted from the
# library arrives mapped, each mapping marked as partial until someone says it is more.
# Every code here is checked against the framework packs by a test.
CROSSWALK: dict[str, dict[str, list[str]]] = {
    "access_removed_on_leaving": {
        "nist-csf": ["PR.AA-01", "PR.AA-05", "GV.RR-04"],
        "nist-800-53": ["PS-4", "PS-5", "AC-2"],
        "nist-800-171": ["03.09.02", "03.01.01"],
        "hipaa-security": ["164.308(a)(3)(ii)(C)"],
    },
    "access_reviewed": {
        "nist-csf": ["PR.AA-05"],
        "nist-800-53": ["AC-2", "AC-6(7)"],
        "nist-800-171": ["03.01.01", "03.01.05"],
        "hipaa-security": ["164.308(a)(4)(ii)(C)"],
    },
    "second_factor": {
        "nist-csf": ["PR.AA-03"],
        "nist-800-53": ["IA-2", "IA-2(1)", "IA-2(2)"],
        "nist-800-171": ["03.05.03", "03.05.04"],
        "hipaa-security": ["164.312(d)"],
    },
    "privileged_access": {
        "nist-csf": ["PR.AA-05"],
        "nist-800-53": ["AC-6", "AC-6(2)", "AC-6(5)", "AC-6(9)"],
        "nist-800-171": ["03.01.05", "03.01.06", "03.01.07"],
        "hipaa-security": ["164.308(a)(4)(ii)(B)", "164.312(a)(2)(i)"],
    },
    "encryption_at_rest": {
        "nist-csf": ["PR.DS-01"],
        "nist-800-53": ["SC-28", "SC-28(1)"],
        "nist-800-171": ["03.13.08", "03.13.11"],
        "hipaa-security": ["164.312(a)(2)(iv)"],
    },
    "backups_tested": {
        "nist-csf": ["PR.DS-11", "RC.RP-03"],
        "nist-800-53": ["CP-9", "CP-9(1)", "CP-10"],
        "hipaa-security": ["164.308(a)(7)(ii)(A)", "164.308(a)(7)(ii)(D)", "164.310(d)(2)(iv)"],
    },
    "data_classified": {
        "nist-csf": ["ID.AM-07", "ID.AM-05"],
        "nist-800-53": ["RA-2", "MP-3"],
        "nist-800-171": ["03.08.04", "03.04.11"],
    },
    "data_sharing_approved": {
        "nist-csf": ["GV.OC-03"],
        "nist-800-53": ["AC-21", "CA-3"],
        "nist-800-171": ["03.12.05"],
        "hipaa-security": ["164.308(b)(1)", "164.314(a)(1)"],
    },
    "patching": {
        "nist-csf": ["PR.PS-02", "ID.RA-01"],
        "nist-800-53": ["SI-2", "RA-5"],
        "nist-800-171": ["03.14.01", "03.11.02"],
        "hipaa-security": ["164.308(a)(1)(ii)(B)"],
    },
    "malware_protection": {
        "nist-csf": ["DE.CM-09", "PR.PS-05"],
        "nist-800-53": ["SI-3"],
        "nist-800-171": ["03.14.02"],
        "hipaa-security": ["164.308(a)(5)(ii)(B)"],
    },
    "network_segmentation": {
        "nist-csf": ["PR.IR-01"],
        "nist-800-53": ["SC-7", "AC-4"],
        "nist-800-171": ["03.13.01", "03.01.03"],
    },
    "unsupported_contained": {
        "nist-csf": ["PR.PS-02", "ID.AM-08"],
        "nist-800-53": ["SA-22"],
        "nist-800-171": ["03.16.02"],
        "hipaa-security": ["164.308(a)(1)(ii)(B)"],
    },
    "change_review": {
        "nist-csf": ["PR.PS-01", "ID.RA-07"],
        "nist-800-53": ["CM-3", "CM-4", "CM-5"],
        "nist-800-171": ["03.04.03", "03.04.04", "03.04.05"],
    },
    "logging_monitoring": {
        "nist-csf": ["PR.PS-04", "DE.CM-01", "DE.CM-03", "DE.AE-02"],
        "nist-800-53": ["AU-2", "AU-6", "AU-12", "SI-4"],
        "nist-800-171": ["03.03.01", "03.03.05", "03.14.06"],
        "hipaa-security": ["164.312(b)", "164.308(a)(1)(ii)(D)", "164.308(a)(5)(ii)(C)"],
    },
    "incident_response": {
        "nist-csf": ["RS.MA-01", "ID.IM-04", "ID.IM-02"],
        "nist-800-53": ["IR-8", "IR-3", "IR-4", "IR-2"],
        "nist-800-171": ["03.06.01", "03.06.03", "03.06.04", "03.06.05"],
        "hipaa-security": ["164.308(a)(6)(i)", "164.308(a)(6)(ii)"],
    },
    "security_training": {
        "nist-csf": ["PR.AT-01", "PR.AT-02"],
        "nist-800-53": ["AT-2", "AT-2(3)", "AT-3"],
        "nist-800-171": ["03.02.01", "03.02.02"],
        "hipaa-security": ["164.308(a)(5)(i)", "164.308(a)(5)(ii)(A)"],
    },
    "access_approved": {
        "nist-csf": ["PR.AA-05", "PR.AA-01"],
        "nist-800-53": ["AC-2", "AC-3", "AC-6"],
        "nist-800-171": ["03.01.01", "03.01.02", "03.01.05"],
        "hipaa-security": [
            "164.308(a)(4)(i)",
            "164.308(a)(4)(ii)(B)",
            "164.308(a)(4)(ii)(C)",
            "164.308(a)(3)(ii)(A)",
            "164.312(a)(1)",
            "164.306(a)(3)",
        ],
    },
    "unique_accounts": {
        "nist-csf": ["PR.AA-01", "PR.AA-03"],
        "nist-800-53": ["IA-2", "IA-4", "IA-5", "IA-5(1)"],
        "nist-800-171": ["03.05.01", "03.05.05", "03.05.07", "03.05.12"],
        "hipaa-security": ["164.312(a)(2)(i)", "164.312(d)", "164.308(a)(5)(ii)(D)"],
    },
    "session_lock": {
        "nist-csf": ["PR.AA-03"],
        "nist-800-53": ["AC-7", "AC-11", "AC-12"],
        "nist-800-171": ["03.01.08", "03.01.10", "03.01.11", "03.13.09"],
        "hipaa-security": ["164.312(a)(2)(iii)", "164.310(b)", "164.310(c)"],
    },
    "remote_access": {
        "nist-csf": ["PR.AA-05", "PR.IR-01"],
        "nist-800-53": ["AC-17", "AC-18", "AC-19", "AC-20"],
        "nist-800-171": ["03.01.12", "03.01.16", "03.01.18", "03.01.20"],
    },
    "personnel_screening": {
        "nist-csf": ["GV.RR-04"],
        "nist-800-53": ["PS-3", "PS-6", "PS-8", "PL-4"],
        "nist-800-171": ["03.09.01", "03.15.03"],
        "hipaa-security": [
            "164.308(a)(3)(i)",
            "164.308(a)(3)(ii)(B)",
            "164.308(a)(1)(ii)(C)",
        ],
    },
    "encryption_in_transit": {
        "nist-csf": ["PR.DS-02"],
        "nist-800-53": ["SC-8", "SC-8(1)", "SC-13"],
        "nist-800-171": ["03.13.08", "03.13.11", "03.13.15"],
        "hipaa-security": ["164.312(e)(1)", "164.312(e)(2)(i)", "164.312(e)(2)(ii)"],
    },
    "media_disposal": {
        "nist-csf": ["PR.PS-03", "ID.AM-08"],
        "nist-800-53": ["MP-6"],
        "nist-800-171": ["03.08.03"],
        "hipaa-security": [
            "164.310(d)(1)",
            "164.310(d)(2)(i)",
            "164.310(d)(2)(ii)",
            "164.310(d)(2)(iii)",
        ],
    },
    "asset_inventory": {
        "nist-csf": ["ID.AM-01", "ID.AM-02", "ID.AM-08", "ID.AM-04"],
        "nist-800-53": ["CM-8", "CM-8(1)", "PM-5"],
        "nist-800-171": ["03.04.10"],
        "hipaa-security": ["164.310(d)(2)(iii)"],
    },
    "secure_configuration": {
        "nist-csf": ["PR.PS-01", "PR.PS-05"],
        "nist-800-53": ["CM-2", "CM-6", "CM-7"],
        "nist-800-171": ["03.04.01", "03.04.02", "03.04.06", "03.04.08"],
    },
    "vulnerability_scanning": {
        "nist-csf": ["ID.RA-01", "ID.RA-02", "ID.RA-08"],
        "nist-800-53": ["RA-5", "RA-5(2)", "SI-5"],
        "nist-800-171": ["03.11.02", "03.14.03"],
        "hipaa-security": ["164.308(a)(1)(ii)(B)"],
    },
    "log_protection": {
        "nist-csf": ["PR.PS-04", "DE.AE-03"],
        "nist-800-53": ["AU-3", "AU-8", "AU-9", "AU-11"],
        "nist-800-171": ["03.03.02", "03.03.03", "03.03.07", "03.03.08", "03.03.06"],
        "hipaa-security": ["164.312(b)"],
    },
    "incident_reporting": {
        "nist-csf": [
            "RS.MA-02",
            "RS.MA-03",
            "RS.MA-04",
            "RS.CO-02",
            "RS.CO-03",
            "RS.MI-01",
            "RS.MI-02",
            "RS.AN-03",
            "DE.AE-06",
            "DE.AE-08",
            "ID.IM-03",
            "DE.AE-04",
            "RS.AN-06",
        ],
        "nist-800-53": ["IR-4", "IR-5", "IR-6", "IR-7"],
        "nist-800-171": ["03.06.01", "03.06.02"],
        "hipaa-security": ["164.308(a)(6)(i)", "164.308(a)(6)(ii)"],
    },
    "disaster_recovery": {
        "nist-csf": ["RC.RP-01", "RC.RP-02", "RC.RP-04", "RC.RP-05", "PR.IR-03", "ID.IM-04"],
        "nist-800-53": ["CP-2", "CP-4", "CP-10"],
        "hipaa-security": [
            "164.308(a)(7)(i)",
            "164.308(a)(7)(ii)(B)",
            "164.308(a)(7)(ii)(D)",
            "164.308(a)(7)(ii)(E)",
        ],
    },
    "physical_access": {
        "nist-csf": ["PR.AA-06", "DE.CM-02"],
        "nist-800-53": ["PE-2", "PE-3", "PE-6", "PE-8"],
        "nist-800-171": ["03.10.01", "03.10.02", "03.10.07", "03.10.08"],
        "hipaa-security": [
            "164.310(a)(1)",
            "164.310(a)(2)(ii)",
            "164.310(a)(2)(iii)",
            "164.310(c)",
        ],
    },
    "security_policy": {
        "nist-csf": ["GV.PO-01", "GV.PO-02"],
        "nist-800-53": ["PL-1", "PM-1"],
        "nist-800-171": ["03.15.01"],
        "hipaa-security": [
            "164.316(a)",
            "164.316(b)(1)",
            "164.316(b)(1)(i)",
            "164.316(b)(2)(i)",
            "164.316(b)(2)(ii)",
            "164.316(b)(2)(iii)",
            "164.306(a)(1)",
            "164.306(a)(4)",
        ],
    },
    "security_roles": {
        "nist-csf": ["GV.RR-01", "GV.RR-02"],
        "nist-800-53": ["PM-2"],
        "hipaa-security": ["164.308(a)(2)"],
    },
    "security_oversight": {
        "nist-csf": [
            "GV.OV-01",
            "GV.OV-02",
            "GV.RM-01",
            "GV.RM-02",
            "GV.RM-04",
            "GV.RR-03",
            "GV.RM-03",
        ],
        "nist-800-53": ["PM-9", "PM-3"],
    },
    "security_risk_assessment": {
        "nist-csf": ["ID.RA-03", "ID.RA-04", "ID.RA-05", "ID.RA-06", "GV.RM-06"],
        "nist-800-53": ["RA-3", "RA-7", "PM-9"],
        "nist-800-171": ["03.11.01", "03.11.04"],
        "hipaa-security": [
            "164.308(a)(1)(i)",
            "164.308(a)(1)(ii)(A)",
            "164.308(a)(1)(ii)(B)",
            "164.306(a)(2)",
        ],
    },
    "security_testing": {
        "nist-csf": ["ID.IM-01", "ID.IM-02", "GV.OV-03"],
        "nist-800-53": ["CA-2", "CA-5", "CA-7", "CA-8"],
        "nist-800-171": ["03.12.01", "03.12.02", "03.12.03"],
        "hipaa-security": ["164.308(a)(8)", "164.306(e)"],
    },
    "backup_power_tested": {"nist-csf": ["PR.IR-02"], "nist-800-53": ["PE-11"]},
    "environmental_monitoring": {"nist-csf": ["PR.IR-02"], "nist-800-53": ["PE-14"]},
    "continuity_plan": {
        "nist-csf": ["ID.IM-04", "PR.IR-03", "RC.RP-01"],
        "nist-800-53": ["CP-2", "CP-4"],
        "hipaa-security": ["164.308(a)(7)(i)", "164.308(a)(7)(ii)(C)", "164.308(a)(7)(ii)(D)"],
    },
    "downtime_procedures": {
        "nist-csf": ["RC.RP-01"],
        "nist-800-53": ["CP-2", "CP-4"],
        "hipaa-security": ["164.308(a)(7)(ii)(C)", "164.310(a)(2)(i)", "164.312(a)(2)(ii)"],
    },
    "agreements_recorded": {"nist-csf": ["GV.OC-03"]},
    "standards_tracked": {"nist-csf": ["GV.OC-03"]},
    "training_tracked": {
        "nist-csf": ["PR.AT-01"],
        "nist-800-53": ["AT-4"],
        "hipaa-security": ["164.308(a)(5)(i)"],
    },
    "supplier_assessed": {
        "nist-csf": ["GV.SC-06", "GV.SC-07", "ID.RA-10"],
        "nist-800-53": ["SR-6", "SA-9"],
        "nist-800-171": ["03.16.03", "03.17.02", "03.17.03"],
        "hipaa-security": ["164.308(b)(1)"],
    },
    "agreements_in_place": {
        "nist-csf": ["GV.SC-05", "GV.SC-02"],
        "nist-800-53": ["SA-9", "CA-3"],
        "nist-800-171": ["03.16.03", "03.12.05"],
        "hipaa-security": [
            "164.308(b)(1)",
            "164.308(b)(3)",
            "164.314(a)(1)",
            "164.314(a)(2)",
            "164.314(a)(2)(i)(A)",
            "164.314(a)(2)(i)(B)",
            "164.314(a)(2)(i)(C)",
        ],
    },
    "alternate_supplier": {"nist-800-53": ["SR-3(1)"]},
    "exit_plan": {"nist-csf": ["GV.SC-10"]},
}

CONTROL_LIBRARY: dict[str, Any] = {
    "pack": {
        "key": "starter-controls",
        "kind": "control_library",
        "title": "Starter controls",
        "version": "1",
        "pack_version": "0.3.0",
        "publisher": "The RiskWren Authors",
        "license": "Apache-2.0",
        "text_policy": "verbatim",
    },
    "controls": [
        {
            "key": row[0],
            "title": row[1],
            "statement": row[2],
            "kind": row[3],
            "nature": row[4],
            "frequency": row[5],
            "reduces": row[6],
            **({"requirements": CROSSWALK[row[0]]} if row[0] in CROSSWALK else {}),
        }
        for row in CONTROL_ROWS
    ],
}

RISK_LIBRARY: dict[str, Any] = {
    "pack": {
        "key": "risk-library",
        "kind": "risk_library",
        "title": "Starter risk library",
        "version": "1",
        "pack_version": "0.3.0",
        "publisher": "The RiskWren Authors",
        "license": "Apache-2.0",
        "text_policy": "verbatim",
    },
    "risks": [
        {
            "key": row[0],
            "category": row[1],
            "title": row[2],
            "cause": row[3],
            "event": row[4],
            "consequence": row[5],
            "controls": SUGGESTED.get(row[0], []),
        }
        for row in LIBRARY_ROWS
    ],
}


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    known = {row[0] for row in CONTROL_ROWS}
    unknown = {key for keys in SUGGESTED.values() for key in keys} - known
    assert not unknown, f"suggested controls that are not in the library: {sorted(unknown)}"
    assert set(SUGGESTED) == {row[0] for row in LIBRARY_ROWS}, (
        "every library risk suggests controls"
    )
    packs = (
        (OUT, PACK),
        (OUT.with_name("risk-library.json"), RISK_LIBRARY),
        (OUT.with_name("starter-controls.json"), CONTROL_LIBRARY),
    )
    for path, pack in packs:
        path.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(OUT.parents[4])}")


if __name__ == "__main__":
    main()
