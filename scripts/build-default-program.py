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
        }
        for row in LIBRARY_ROWS
    ],
}


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for path, pack in ((OUT, PACK), (OUT.with_name("risk-library.json"), RISK_LIBRARY)):
        path.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(OUT.parents[4])}")


if __name__ == "__main__":
    main()
