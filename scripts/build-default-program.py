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

# How often a risk is reviewed, by its residual rating; and how long a control's rating holds.
CADENCES: dict[str, Any] = {
    "risk_review_months": {"critical": 3, "high": 6, "moderate": 12, "low": 24},
    "unrated_risk_review_months": 3,
    "control_rating_months": 12,
}

# Who may accept a risk above appetite, by its residual rating, and for how long.
AUTHORITY: dict[str, Any] = {
    "acceptance": {
        "moderate": {"max_months": 24, "needs_limit": False},
        "high": {"max_months": 12, "needs_limit": True},
        "critical": {"max_months": 6, "needs_limit": True},
    }
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
    "vocabularies": {**VOCABULARIES, "link_kinds": LINK_KINDS},
    "categories": CATEGORIES,
    "scoring_method": SCORING_METHOD,
    "cadences": CADENCES,
    "authority": AUTHORITY,
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
    ],
    "access_not_removed": ["access_removed_on_leaving", "access_reviewed"],
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
    ],
    "compromised_account": [
        "second_factor",
        "security_training",
        "logging_monitoring",
        "privileged_access",
    ],
    "unsupported_systems": ["unsupported_contained", "network_segmentation", "patching"],
    "failed_change": ["change_review", "backups_tested"],
    "backup_failure": ["backups_tested"],
    "exposed_storage": ["data_classified", "logging_monitoring", "access_reviewed"],
    "unreviewed_ai": ["ai_use_reviewed", "data_classified", "agreements_in_place"],
    "sign_in_outage": ["continuity_plan", "privileged_access", "incident_response"],
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
        "nist-800-171": ["03.05.03"],
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
        "nist-800-171": ["03.13.08"],
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
        "nist-800-171": ["03.08.04"],
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
        "nist-800-53": ["CM-3", "CM-4"],
        "nist-800-171": ["03.04.03", "03.04.04"],
    },
    "logging_monitoring": {
        "nist-csf": ["PR.PS-04", "DE.CM-01", "DE.CM-03", "DE.AE-02"],
        "nist-800-53": ["AU-2", "AU-6", "AU-12", "SI-4"],
        "nist-800-171": ["03.03.01", "03.03.05", "03.14.06"],
        "hipaa-security": ["164.312(b)", "164.308(a)(1)(ii)(D)", "164.308(a)(5)(ii)(C)"],
    },
    "incident_response": {
        "nist-csf": ["RS.MA-01", "ID.IM-04", "ID.IM-02"],
        "nist-800-53": ["IR-8", "IR-3", "IR-4"],
        "nist-800-171": ["03.06.01", "03.06.03", "03.06.05"],
        "hipaa-security": ["164.308(a)(6)(i)", "164.308(a)(6)(ii)"],
    },
    "security_training": {
        "nist-csf": ["PR.AT-01", "PR.AT-02"],
        "nist-800-53": ["AT-2", "AT-2(3)", "AT-3"],
        "nist-800-171": ["03.02.01", "03.02.02"],
        "hipaa-security": ["164.308(a)(5)(i)", "164.308(a)(5)(ii)(A)"],
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
        "hipaa-security": ["164.308(a)(7)(ii)(C)", "164.310(a)(2)(i)"],
    },
    "agreements_recorded": {"nist-csf": ["GV.OC-03"]},
    "standards_tracked": {"nist-csf": ["GV.OC-03"]},
    "training_tracked": {
        "nist-csf": ["PR.AT-01"],
        "nist-800-53": ["AT-4"],
        "hipaa-security": ["164.308(a)(5)(i)"],
    },
    "supplier_assessed": {
        "nist-csf": ["GV.SC-06", "GV.SC-07"],
        "nist-800-53": ["SR-6", "SA-9"],
        "nist-800-171": ["03.16.03", "03.17.03"],
        "hipaa-security": ["164.308(b)(1)"],
    },
    "agreements_in_place": {
        "nist-csf": ["GV.SC-05"],
        "nist-800-53": ["SA-9", "CA-3"],
        "nist-800-171": ["03.16.03", "03.12.05"],
        "hipaa-security": ["164.308(b)(1)", "164.308(b)(3)", "164.314(a)(1)"],
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
        "pack_version": "0.2.0",
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
        "pack_version": "0.1.0",
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
