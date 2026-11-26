"""The words of the demo organization: its units, people, systems, suppliers, and stories.

Everything here is invented. The institute, its labs, its people, its suppliers, and what
happened to them do not exist, and nothing is taken from a real organization.
"""

from __future__ import annotations

ORGANIZATION = "Northmere Institute for Health Research"
SHORT_NAME = "Northmere"
DOMAIN = "northmere.example"

# code, name, kind, parent code
UNITS: list[tuple[str, str, str, str | None]] = [
    ("NMI", ORGANIZATION, "organization", None),
    ("PRES", "Office of the President", "office", "NMI"),
    ("RISK", "Risk and Audit", "office", "NMI"),
    ("RES", "Research", "division", "NMI"),
    ("CB", "Cancer Biology", "department", "RES"),
    ("II", "Immunology and Infectious Disease", "department", "RES"),
    ("PS", "Population Sciences", "department", "RES"),
    ("CDS", "Computational and Data Science", "department", "RES"),
    ("CR", "Clinical Research", "department", "RES"),
    ("CORES", "Core Facilities", "division", "NMI"),
    ("GEN", "Genomics Core", "core", "CORES"),
    ("BIO", "Biospecimen Repository", "core", "CORES"),
    ("IMG", "Imaging Core", "core", "CORES"),
    ("CMP", "Comparative Medicine", "core", "CORES"),
    ("RC", "Research Computing", "core", "CORES"),
    ("CLIN", "Northmere Research Clinic", "division", "NMI"),
    ("INF", "Infusion", "clinic", "CLIN"),
    ("CLAB", "Clinical Laboratory", "clinic", "CLIN"),
    ("PHARM", "Pharmacy", "clinic", "CLIN"),
    ("PA", "Patient Access", "clinic", "CLIN"),
    ("ADMIN", "Administration", "division", "NMI"),
    ("IT", "Information Technology", "department", "ADMIN"),
    ("SEC", "Information Security", "department", "ADMIN"),
    ("CMPL", "Compliance and Privacy", "department", "ADMIN"),
    ("SP", "Sponsored Programs", "department", "ADMIN"),
    ("FIN", "Finance", "department", "ADMIN"),
    ("HR", "Human Resources", "department", "ADMIN"),
    ("FAC", "Facilities and Safety", "department", "ADMIN"),
    ("LEGAL", "Legal", "department", "ADMIN"),
    ("COMM", "Communications", "department", "ADMIN"),
    ("PHIL", "Philanthropy", "department", "ADMIN"),
]
# Research departments get labs, each named for its principal investigator.
LAB_DEPARTMENTS = {"CB": 7, "II": 6, "PS": 5, "CDS": 5, "CR": 6}

GIVEN = [
    "Amara", "Benedikt", "Chidi", "Dalia", "Elan", "Farah", "Goran", "Hana", "Idris", "Jun",
    "Katya", "Leandro", "Maren", "Nikhil", "Oona", "Pavel", "Quentin", "Rosalind", "Soren",
    "Tamsin", "Uma", "Viktor", "Wren", "Ximena", "Yusuf", "Zofia", "Anselm", "Bryn", "Cosima",
    "Dev", "Esme", "Florian", "Greta", "Henrik", "Ines", "Joaquin", "Keiko", "Lior", "Mireille",
    "Nadim", "Odette", "Priya", "Rafael", "Sunniva", "Tobias", "Ulla", "Vesna", "Wilhelmina",
]  # fmt: skip
FAMILY = [
    "Abara", "Lindqvist", "Okonjo", "Marchetti", "Halvorsen", "Nakashima", "Petrov", "Achterberg",
    "Delacroix", "Ferreira", "Gallagher", "Haddad", "Ibekwe", "Jovanovic", "Kowalczyk", "Larsen",
    "Mbeki", "Novak", "Oyelaran", "Pellegrino", "Quispe", "Rasmussen", "Sandoval", "Takeda",
    "Udoka", "Varga", "Wachira", "Yamamoto", "Zielinski", "Adeyemi", "Bergstrom", "Castellanos",
    "Dimitrov", "Eriksen", "Fofanah", "Grigoryan", "Hoang", "Iyer", "Jaramillo", "Kimathi",
    "Lachance", "Moreau", "Ndlovu", "Ostrowski", "Paredes", "Rahimi", "Soderberg", "Thackeray",
    "Uzun", "Vandermeer", "Whitlock", "Xuereb", "Yilmaz", "Zamora", "Aldana", "Brandvold",
    "Chaudhry", "Dragomir", "Ekström", "Fairweather",
]  # fmt: skip

# The people whose jobs the stories need. key, name, title, home unit, roles.
# A role is (role, unit code or None, acceptance limit or None).
CAST: list[tuple[str, str, str, str, list[tuple[str, str | None, str | None]]]] = [
    ("president", "Rosalind Achterberg", "President and Director", "PRES",
     [("leader", "NMI", "critical")]),
    ("coo", "Henrik Soderberg", "Chief Operating Officer", "ADMIN",
     [("leader", "ADMIN", "critical"), ("leader", "CLIN", "critical"), ("leader", "CORES", "critical")]),
    ("cso", "Amara Okonjo", "Chief Scientific Officer", "RES", [("leader", "RES", "critical")]),
    ("cro", "Mireille Lachance", "Chief Risk and Compliance Officer", "RISK", [("manager", None, None)]),
    ("risk1", "Nikhil Iyer", "Enterprise Risk Manager", "RISK", [("manager", None, None)]),
    ("risk2", "Tamsin Whitlock", "Compliance Manager", "RISK", [("manager", None, None)]),
    ("risk3", "Joaquin Paredes", "Risk Analyst", "RISK", [("manager", None, None)]),
    ("assess1", "Keiko Nakashima", "Security Assurance Lead", "SEC", [("assessor", None, None)]),
    ("assess2", "Idris Rahimi", "Compliance Analyst", "CMPL", [("assessor", None, None)]),
    ("auditor", "Greta Bergstrom", "Director of Internal Audit", "RISK", [("auditor", None, None)]),
    ("admin", "Tobias Larsen", "Systems Administrator", "IT", [("admin", None, None)]),
    ("cio", "Priya Chaudhry", "Chief Information Officer", "IT", [("leader", "IT", "high")]),
    ("ciso", "Goran Dimitrov", "Chief Information Security Officer", "SEC", [("leader", "SEC", "high")]),
    ("cfo", "Odette Moreau", "Chief Financial Officer", "FIN", [("leader", "FIN", "high")]),
    ("cores_lead", "Soren Eriksen", "Director of Core Facilities", "CORES", [("leader", "CORES", "high")]),
    ("clinic_lead", "Farah Haddad", "Medical Director", "CLIN", [("leader", "CLIN", "high")]),
    ("bio_dir", "Ines Castellanos", "Director, Biospecimen Repository", "BIO", [("leader", "BIO", "moderate")]),
    ("bio_mgr", "Chidi Udoka", "Repository Manager", "BIO", [("steward", "BIO", None)]),
    ("rc_dir", "Lior Grigoryan", "Director, Research Computing", "RC", [("leader", "RC", "moderate")]),
    ("img_dir", "Katya Petrov", "Director, Imaging Core", "IMG", [("leader", "IMG", "moderate")]),
    ("sp_dir", "Rafael Jaramillo", "Director, Sponsored Programs", "SP", [("leader", "SP", "moderate")]),
    ("fac_dir", "Bryn Gallagher", "Director, Facilities and Safety", "FAC", [("leader", "FAC", "moderate")]),
    ("gen_dir", "Anselm Vandermeer", "Director, Genomics Core", "GEN", [("leader", "GEN", "moderate")]),
    ("gen_mgr", "Maren Takeda", "Genomics Core Manager", "GEN", [("steward", "GEN", None)]),
    ("img_mgr", "Dev Rasmussen", "Imaging Core Manager", "IMG", [("steward", "IMG", None)]),
    ("sec_mgr", "Viktor Novak", "Security Operations Manager", "SEC", [("steward", "SEC", None)]),
    ("it_mgr", "Esme Wachira", "Infrastructure Manager", "IT", [("steward", "IT", None)]),
    ("sp_mgr", "Zofia Kowalczyk", "Post-Award Manager", "SP", [("steward", "SP", None)]),
    ("pharm_mgr", "Uma Sandoval", "Pharmacy Manager", "PHARM", [("steward", "PHARM", None)]),
    ("member", "Dalia Ferreira", "Specimen Technician", "BIO", []),
]  # fmt: skip

HEAD_TITLES = {"lab": "Principal Investigator", "clinic": "Clinical Director"}
STEWARD_TITLES = {
    "lab": "Lab Manager", "core": "Core Manager", "clinic": "Nurse Manager",
    "division": "Division Administrator", "office": "Chief of Staff",
}  # fmt: skip
STAFF_TITLES = {
    "lab": ["Postdoctoral Fellow", "Research Technician", "Graduate Student", "Staff Scientist"],
    "core": ["Research Technician", "Staff Scientist", "Core Specialist"],
    "clinic": ["Registered Nurse", "Clinical Coordinator", "Clinical Specialist"],
    "department": ["Analyst", "Specialist", "Coordinator", "Senior Analyst"],
    "division": ["Program Coordinator", "Analyst"],
    "office": ["Executive Assistant", "Program Coordinator"],
}

# Who the demo's sign-in page offers, and what each is there to show.
SAMPLE = [
    ("cro", "Risk manager", "Runs the program and sees everything"),
    ("bio_mgr", "Steward", "Keeps the Biospecimen Repository's records and owns its risks"),
    ("bio_dir", "Unit leader", "Leads a core; may accept only moderate risks"),
    ("cores_lead", "Division leader", "May accept risks rated high in Core Facilities"),
    ("president", "Executive", "May accept risks rated critical, anywhere"),
    ("assess1", "Assessor", "Assesses risks and rates controls, everywhere"),
    ("auditor", "Auditor", "Reads everything and changes nothing"),
    ("admin", "Administrator", "Accounts, units, and appearance; not the register"),
    ("member", "Staff member", "Sees their own unit's risks and what they owe"),
]

# What each unit does. unit code: [(name, kind, criticality, data class)]
PROCESSES: dict[str, list[tuple[str, str, str, str | None]]] = {
    "BIO": [("Specimen storage and retrieval", "research_support", "critical", "confidential"),
            ("Specimen receipt and processing", "research_support", "high", "restricted")],
    "GEN": [("Sequencing service", "research_support", "high", "confidential"),
            ("Library preparation", "research_support", "moderate", "confidential")],
    "IMG": [("Microscopy service", "research_support", "high", "internal"),
            ("Image analysis support", "research_support", "moderate", "confidential")],
    "CMP": [("Animal husbandry", "research_support", "critical", "internal"),
            ("Veterinary care", "research_support", "high", "internal")],
    "RC": [("Research data storage", "technology", "critical", "restricted"),
           ("High-performance computing", "technology", "high", "confidential"),
           ("Controlled-access data hosting", "technology", "critical", "restricted")],
    "INF": [("Infusion therapy", "clinical", "critical", "restricted")],
    "CLAB": [("Clinical laboratory testing", "clinical", "critical", "restricted")],
    "PHARM": [("Medication dispensing", "clinical", "critical", "restricted"),
              ("Investigational drug service", "clinical", "high", "restricted")],
    "PA": [("Scheduling and registration", "clinical", "high", "restricted")],
    "CR": [("Clinical trial enrollment", "research", "high", "restricted"),
           ("Trial data management", "research", "high", "restricted"),
           ("Safety reporting", "research", "critical", "restricted")],
    "PS": [("Cohort follow-up", "research", "high", "restricted"),
           ("Survey data collection", "research", "moderate", "restricted")],
    "CDS": [("Analysis pipelines", "research", "moderate", "confidential")],
    "IT": [("Service desk", "technology", "moderate", "internal"),
           ("Identity and access administration", "technology", "critical", "confidential"),
           ("Backup and recovery", "technology", "critical", "restricted"),
           ("Network operations", "technology", "critical", "internal")],
    "SEC": [("Security monitoring", "technology", "high", "confidential"),
            ("Vulnerability management", "technology", "high", "confidential")],
    "CMPL": [("Privacy incident handling", "administrative", "high", "restricted"),
             ("Research compliance review", "administrative", "high", "confidential")],
    "SP": [("Award setup and management", "administrative", "high", "confidential"),
           ("Effort certification", "administrative", "moderate", "confidential"),
           ("Subaward administration", "administrative", "moderate", "confidential")],
    "FIN": [("Accounts payable", "administrative", "high", "confidential"),
            ("Payroll", "administrative", "critical", "restricted"),
            ("Purchasing", "administrative", "moderate", "internal")],
    "HR": [("Hiring and onboarding", "administrative", "moderate", "confidential"),
           ("Required training", "education", "moderate", "internal")],
    "FAC": [("Building operations", "facilities", "critical", "internal"),
            ("Laboratory safety program", "facilities", "high", "internal"),
            ("Emergency power", "facilities", "critical", "internal")],
    "LEGAL": [("Agreement review", "administrative", "moderate", "confidential")],
    "COMM": [("Public website and media", "administrative", "moderate", "public")],
    "PHIL": [("Donor stewardship", "administrative", "moderate", "confidential")],
    "PRES": [("Strategic planning", "administrative", "moderate", "confidential")],
}  # fmt: skip
LAB_PROCESSES = [
    ("{lab} bench research", "research", "moderate", "confidential"),
]

# What the work runs on. key, name, unit, kind, criticality, data class, hosting, lifecycle
SYSTEMS: list[tuple[str, str, str, str, str, str | None, str, str]] = [
    ("storage", "Research storage", "RC", "infrastructure", "critical", "restricted", "on_premises", "in_service"),
    ("cluster", "Compute cluster", "RC", "platform", "high", "confidential", "on_premises", "in_service"),
    ("enclave", "Controlled-access data enclave", "RC", "platform", "critical", "restricted", "on_premises", "in_service"),
    ("eln", "Electronic lab notebook", "RC", "application", "high", "confidential", "hosted", "in_service"),
    ("identity", "Identity service", "IT", "infrastructure", "critical", "confidential", "cloud", "in_service"),
    ("email", "Email and collaboration", "IT", "application", "high", "confidential", "hosted", "in_service"),
    ("network", "Campus network", "IT", "infrastructure", "critical", "internal", "on_premises", "in_service"),
    ("backup", "Backup service", "IT", "infrastructure", "critical", "restricted", "on_premises", "in_service"),
    ("servers", "Virtual server platform", "IT", "platform", "high", "confidential", "on_premises", "in_service"),
    ("endpoints", "Endpoint management", "IT", "application", "high", "internal", "cloud", "in_service"),
    ("siem", "Security event monitoring", "SEC", "application", "high", "confidential", "hosted", "in_service"),
    ("scanner", "Vulnerability scanner", "SEC", "application", "moderate", "confidential", "on_premises", "in_service"),
    ("record", "Clinical record system", "CLIN", "application", "critical", "restricted", "hosted", "in_service"),
    ("lis", "Laboratory information system", "CLAB", "application", "critical", "restricted", "on_premises", "in_service"),
    ("analyzers", "Chemistry analyzers", "CLAB", "instrument", "high", "restricted", "standalone", "in_service"),
    ("cabinets", "Dispensing cabinets", "PHARM", "device", "critical", "restricted", "on_premises", "in_service"),
    ("pumps", "Infusion pumps", "INF", "device", "critical", "restricted", "on_premises", "in_service"),
    ("scheduling", "Scheduling system", "PA", "application", "high", "restricted", "hosted", "in_service"),
    ("ctms", "Clinical trial management system", "CR", "application", "high", "restricted", "hosted", "in_service"),
    ("edc", "Electronic data capture", "CR", "application", "high", "restricted", "hosted", "in_service"),
    ("cohortdb", "Cohort database", "PS", "data_store", "high", "restricted", "on_premises", "in_service"),
    ("survey", "Survey platform", "PS", "application", "moderate", "restricted", "hosted", "in_service"),
    ("freezers", "Freezer farm", "BIO", "device", "critical", None, "on_premises", "in_service"),
    ("monitor", "Freezer monitoring", "BIO", "device", "critical", None, "on_premises", "in_service"),
    ("tracking", "Specimen tracking", "BIO", "application", "high", "restricted", "hosted", "in_service"),
    ("nitrogen", "Liquid nitrogen supply", "BIO", "infrastructure", "critical", None, "on_premises", "in_service"),
    ("sequencer1", "Sequencer A", "GEN", "instrument", "high", "confidential", "standalone", "in_service"),
    ("sequencer2", "Sequencer B", "GEN", "instrument", "high", "confidential", "standalone", "sunsetting"),
    ("lims", "Genomics sample manager", "GEN", "application", "moderate", "confidential", "on_premises", "in_service"),
    ("confocal", "Confocal microscope", "IMG", "instrument", "high", "internal", "standalone", "in_service"),
    ("cryo", "Cryo-electron microscope", "IMG", "instrument", "critical", "internal", "standalone", "in_service"),
    ("imgws", "Microscope control workstation", "IMG", "instrument", "high", "internal", "standalone", "unsupported"),
    ("vivarium", "Animal facility environmental controls", "CMP", "device", "critical", None, "on_premises", "in_service"),
    ("colony", "Colony management system", "CMP", "application", "moderate", "internal", "hosted", "in_service"),
    ("grants", "Grants management system", "SP", "application", "high", "confidential", "hosted", "in_service"),
    ("finance", "Finance system", "FIN", "application", "critical", "restricted", "hosted", "in_service"),
    ("payroll", "Payroll service", "FIN", "application", "critical", "restricted", "hosted", "in_service"),
    ("hris", "People system", "HR", "application", "high", "restricted", "hosted", "in_service"),
    ("learning", "Learning system", "HR", "application", "moderate", "internal", "hosted", "in_service"),
    ("bms", "Building management system", "FAC", "device", "critical", None, "on_premises", "unsupported"),
    ("generators", "Emergency generators", "FAC", "infrastructure", "critical", None, "on_premises", "in_service"),
    ("badges", "Door access system", "FAC", "device", "high", "confidential", "on_premises", "in_service"),
    ("contracts", "Agreement tracker", "LEGAL", "application", "moderate", "confidential", "hosted", "in_service"),
    ("website", "Public website", "COMM", "application", "moderate", "public", "hosted", "in_service"),
    ("donors", "Donor database", "PHIL", "application", "moderate", "confidential", "hosted", "in_service"),
]  # fmt: skip
LAB_SYSTEMS = [
    ("{lab} analysis workstation", "application", "moderate", "confidential", "standalone", "in_service"),
    ("{lab} instrument computer", "instrument", "moderate", "internal", "standalone", "in_service"),
]  # fmt: skip

# Who the institute depends on. key, name, unit, kind, criticality, data class, summary
PARTIES: list[tuple[str, str, str, str, str, str | None, str]] = [
    ("coldline", "Coldline Service", "BIO", "service_provider", "high", None, "Maintenance contract for the freezer farm."),
    ("cryogas", "Aldermoor Gases", "BIO", "supplier", "critical", None, "Bulk liquid nitrogen, delivered weekly."),
    ("trackco", "Specimen Ledger Systems", "BIO", "service_provider", "high", "restricted", "Hosts the specimen tracking application."),
    ("reagents", "Brightwater Reagents", "GEN", "supplier", "critical", None, "Sole source of the sequencing chemistry."),
    ("seqmaker", "Arbor Vale Instruments", "GEN", "supplier", "high", None, "Maker and servicer of the sequencers."),
    ("optics", "Kestrel Optics", "IMG", "supplier", "high", None, "Maker of the microscopes and their control software."),
    ("feed", "Greenholm Animal Supply", "CMP", "supplier", "high", None, "Feed, bedding, and caging."),
    ("recordco", "Pellham Clinical Systems", "CLIN", "service_provider", "critical", "restricted", "Hosts the clinical record system."),
    ("pumpco", "Vireo Medical Devices", "INF", "supplier", "high", "restricted", "Infusion pumps and their drug library."),
    ("pharmaco", "Meridian Pharmacy Automation", "PHARM", "supplier", "high", "restricted", "Dispensing cabinets and their service."),
    ("labref", "Lakeshore Reference Laboratory", "CLAB", "service_provider", "high", "restricted", "Tests the clinical laboratory sends out."),
    ("edcco", "Castellan Trial Systems", "CR", "service_provider", "high", "restricted", "Hosts electronic data capture and trial management."),
    ("cro", "Halden Research Partners", "CR", "contractor", "moderate", "restricted", "Monitors two multi-site trials."),
    ("surveyco", "Tallyfield Surveys", "PS", "service_provider", "moderate", "restricted", "Hosts participant surveys."),
    ("cloud", "Quillon Cloud", "IT", "service_provider", "critical", "restricted", "Identity, email, and collaboration services."),
    ("netco", "Farrow Networks", "IT", "supplier", "high", None, "Network equipment and support."),
    ("backupco", "Stonebridge Data Vaulting", "IT", "service_provider", "high", "restricted", "Holds the offsite copy of the backups."),
    ("soc", "Lanternwatch Security", "SEC", "service_provider", "high", "confidential", "Watches security alerts out of hours."),
    ("elnco", "Folio Bench", "RC", "service_provider", "high", "confidential", "Hosts the electronic lab notebook."),
    ("grantsco", "Awardline", "SP", "service_provider", "high", "confidential", "Hosts the grants management system."),
    ("financeco", "Ledgerwell", "FIN", "service_provider", "critical", "restricted", "Hosts finance and payroll."),
    ("hrco", "Peoplebook", "HR", "service_provider", "high", "restricted", "Hosts the people and learning systems."),
    ("bmsco", "Thornfield Controls", "FAC", "supplier", "critical", None, "Maker of the building management system, now out of support."),
    ("gensvc", "Ironhaven Power Services", "FAC", "contractor", "high", None, "Services and load-tests the generators."),
    ("waste", "Cleanreach Environmental", "FAC", "contractor", "moderate", None, "Hazardous waste collection."),
    ("donorco", "Givewell Systems", "PHIL", "service_provider", "moderate", "confidential", "Hosts the donor database."),
    ("webco", "Papermill Digital", "COMM", "contractor", "low", "public", "Builds and hosts the public website."),
    ("lawfirm", "Ashcombe and Reyes", "LEGAL", "contractor", "moderate", "confidential", "Outside counsel."),
    ("insurer", "Harbourline Mutual", "FIN", "service_provider", "high", "confidential", "Property, liability, and cyber insurance."),
    ("auditfirm", "Wexley Marsh", "FIN", "contractor", "moderate", "confidential", "Annual financial audit."),
    ("univ1", "Calder Bay University", "RES", "collaborator", "high", "restricted", "Partner on the shared cohort and three awards."),
    ("univ2", "Saint Elric Medical College", "RES", "collaborator", "moderate", "restricted", "Clinical partner on two trials."),
    ("hospital", "Riverbend Children's Hospital", "CR", "collaborator", "moderate", "restricted", "Enrolling site for a pediatric trial."),
    ("sub1", "Tidewater Community Health", "SP", "subrecipient", "moderate", "confidential", "Subrecipient on a community cohort award."),
    ("sub2", "Northfield Data Collaborative", "SP", "subrecipient", "moderate", "restricted", "Subrecipient providing data linkage."),
    ("funder1", "National Health Research Fund", "SP", "sponsor", "critical", None, "The institute's largest sponsor."),
    ("funder2", "Halcyon Foundation", "PHIL", "sponsor", "high", None, "Foundation funding three programs."),
    ("funder3", "Open Cohort Trust", "SP", "sponsor", "moderate", None, "Funds the population cohort."),
    ("pharma1", "Verdance Therapeutics", "CR", "sponsor", "high", "restricted", "Industry sponsor of two trials."),
    ("courier", "Swiftcold Logistics", "BIO", "contractor", "moderate", "restricted", "Ships specimens between sites."),
    ("staffing", "Benchmark Scientific Staffing", "HR", "contractor", "low", "internal", "Temporary laboratory staff."),
    ("cleaning", "Brightway Facility Services", "FAC", "contractor", "moderate", None, "Cleaning of laboratories and the clinic."),
    ("genomevault", "Genome Commons Repository", "RC", "collaborator", "high", "restricted", "Controlled-access repository the enclave draws data from."),
]  # fmt: skip

# What relies on what. (from, relation, to), by the keys above; processes by their name.
LINKS: list[tuple[str, str, str]] = [
    ("Specimen storage and retrieval", "relies_on", "freezers"),
    ("Specimen storage and retrieval", "relies_on", "monitor"),
    ("Specimen storage and retrieval", "relies_on", "tracking"),
    ("Specimen storage and retrieval", "relies_on", "nitrogen"),
    ("Specimen storage and retrieval", "performed_by", "coldline"),
    ("Specimen receipt and processing", "relies_on", "tracking"),
    ("Specimen receipt and processing", "performed_by", "courier"),
    ("Sequencing service", "relies_on", "sequencer1"),
    ("Sequencing service", "relies_on", "sequencer2"),
    ("Sequencing service", "relies_on", "lims"),
    ("Sequencing service", "relies_on", "storage"),
    ("Microscopy service", "relies_on", "confocal"),
    ("Microscopy service", "relies_on", "cryo"),
    ("Microscopy service", "relies_on", "imgws"),
    ("Animal husbandry", "relies_on", "vivarium"),
    ("Animal husbandry", "relies_on", "colony"),
    ("Animal husbandry", "performed_by", "feed"),
    ("Research data storage", "relies_on", "storage"),
    ("Research data storage", "relies_on", "backup"),
    ("High-performance computing", "relies_on", "cluster"),
    ("Controlled-access data hosting", "relies_on", "enclave"),
    ("Infusion therapy", "relies_on", "pumps"),
    ("Infusion therapy", "relies_on", "record"),
    ("Clinical laboratory testing", "relies_on", "lis"),
    ("Clinical laboratory testing", "relies_on", "analyzers"),
    ("Clinical laboratory testing", "performed_by", "labref"),
    ("Medication dispensing", "relies_on", "cabinets"),
    ("Medication dispensing", "relies_on", "record"),
    ("Scheduling and registration", "relies_on", "scheduling"),
    ("Clinical trial enrollment", "relies_on", "ctms"),
    ("Trial data management", "relies_on", "edc"),
    ("Trial data management", "performed_by", "cro"),
    ("Cohort follow-up", "relies_on", "cohortdb"),
    ("Survey data collection", "relies_on", "survey"),
    ("Analysis pipelines", "relies_on", "cluster"),
    ("Analysis pipelines", "relies_on", "storage"),
    ("Identity and access administration", "relies_on", "identity"),
    ("Backup and recovery", "relies_on", "backup"),
    ("Backup and recovery", "performed_by", "backupco"),
    ("Network operations", "relies_on", "network"),
    ("Security monitoring", "relies_on", "siem"),
    ("Security monitoring", "performed_by", "soc"),
    ("Vulnerability management", "relies_on", "scanner"),
    ("Award setup and management", "relies_on", "grants"),
    ("Effort certification", "relies_on", "grants"),
    ("Accounts payable", "relies_on", "finance"),
    ("Payroll", "relies_on", "payroll"),
    ("Required training", "relies_on", "learning"),
    ("Building operations", "relies_on", "bms"),
    ("Emergency power", "relies_on", "generators"),
    ("Emergency power", "performed_by", "gensvc"),
    ("Donor stewardship", "relies_on", "donors"),
    ("Public website and media", "relies_on", "website"),
    ("monitor", "supplied_by", "coldline"),
    ("nitrogen", "supplied_by", "cryogas"),
    ("tracking", "supplied_by", "trackco"),
    ("sequencer1", "supplied_by", "seqmaker"),
    ("sequencer2", "supplied_by", "seqmaker"),
    ("confocal", "supplied_by", "optics"),
    ("cryo", "supplied_by", "optics"),
    ("imgws", "supplied_by", "optics"),
    ("record", "supplied_by", "recordco"),
    ("pumps", "supplied_by", "pumpco"),
    ("cabinets", "supplied_by", "pharmaco"),
    ("ctms", "supplied_by", "edcco"),
    ("edc", "supplied_by", "edcco"),
    ("survey", "supplied_by", "surveyco"),
    ("identity", "supplied_by", "cloud"),
    ("email", "supplied_by", "cloud"),
    ("network", "supplied_by", "netco"),
    ("eln", "supplied_by", "elnco"),
    ("grants", "supplied_by", "grantsco"),
    ("finance", "supplied_by", "financeco"),
    ("payroll", "supplied_by", "financeco"),
    ("hris", "supplied_by", "hrco"),
    ("learning", "supplied_by", "hrco"),
    ("bms", "supplied_by", "bmsco"),
    ("donors", "supplied_by", "donorco"),
    ("website", "supplied_by", "webco"),
    ("cluster", "depends_on", "storage"),
    ("enclave", "depends_on", "storage"),
    ("enclave", "depends_on", "identity"),
    ("storage", "depends_on", "network"),
    ("backup", "depends_on", "storage"),
    ("lis", "depends_on", "record"),
    ("cabinets", "depends_on", "record"),
    ("pumps", "depends_on", "network"),
    ("email", "depends_on", "identity"),
    ("tracking", "depends_on", "identity"),
    ("vivarium", "part_of", "bms"),
    ("imgws", "part_of", "cryo"),
    ("monitor", "part_of", "freezers"),
]  # fmt: skip

# Which library risks each unit raises. A unit's risks are its own to assess.
UNIT_RISKS: dict[str, list[str]] = {
    "PRES": ["funding_concentration", "key_program_decline", "affiliation_dispute", "public_controversy", "regional_disaster"],
    "RES": ["misconduct_undetected", "undisclosed_support", "controlled_technology", "recruitment"],
    "CB": ["unreproducible_results", "hazard_exposure"],
    "II": ["hazard_exposure", "unreproducible_results"],
    "PS": ["participant_privacy", "data_agreement", "collaborator_failure"],
    "CDS": ["research_data_loss", "unreviewed_ai"],
    "CR": ["protocol_lapse", "trial_deviation", "participant_privacy", "collaborator_failure"],
    "BIO": ["specimen_loss", "sole_supplier", "hosted_service_outage"],
    "GEN": ["critical_instrument", "sole_supplier", "research_data_loss"],
    "IMG": ["critical_instrument", "unsupported_systems", "key_person"],
    "CMP": ["animal_welfare", "environmental_control", "hazard_exposure"],
    "RC": ["research_data_loss", "backup_failure", "exposed_storage", "key_person"],
    "INF": ["medication_error", "missed_deterioration", "care_infection"],
    "CLAB": ["patient_identification", "critical_instrument"],
    "PHARM": ["medication_error", "hosted_service_outage"],
    "PA": ["patient_identification", "clinical_downtime"],
    "CLIN": ["clinical_downtime", "accreditation_lapse", "sustained_overload"],
    "IT": ["ransomware", "sign_in_outage", "failed_change", "backup_failure", "unsupported_systems"],
    "SEC": ["compromised_account", "ransomware", "supplier_breach", "exposed_storage"],
    "CMPL": ["health_information_breach", "access_not_removed", "missing_agreement", "training_lapse"],
    "SP": ["unallowable_costs", "effort_certification", "subrecipient_monitoring", "award_terms"],
    "FIN": ["payment_fraud", "purchasing_misuse", "operating_shortfall", "indirect_cost_change"],
    "HR": ["recruitment", "conduct_not_addressed", "workplace_injury"],
    "FAC": ["power_failure", "environmental_control", "fire_or_flood", "hazard_exposure", "unsupported_systems"],
    "LEGAL": ["missing_agreement"],
    "COMM": ["public_controversy"],
    "PHIL": ["gift_terms", "funding_concentration"],
}  # fmt: skip
LAB_RISKS = [
    "research_data_loss", "key_person", "hazard_exposure", "unreproducible_results",
    "protocol_lapse", "data_agreement", "training_lapse", "critical_instrument",
    "specimen_loss", "participant_privacy",
]  # fmt: skip

# How each library risk tends to be judged before controls: likelihood, and impact by dimension.
INHERENT: dict[str, tuple[int, dict[str, int]]] = {
    "funding_concentration": (3, {"mission": 4, "financial": 5}),
    "indirect_cost_change": (3, {"financial": 4, "mission": 3}),
    "key_program_decline": (2, {"mission": 4, "trust": 3}),
    "affiliation_dispute": (2, {"mission": 4, "legal": 3}),
    "public_controversy": (3, {"trust": 4}),
    "misconduct_undetected": (3, {"trust": 5, "legal": 4, "mission": 4}),
    "unreproducible_results": (4, {"trust": 3, "mission": 3}),
    "protocol_lapse": (4, {"legal": 4, "safety": 3, "mission": 3}),
    "participant_privacy": (4, {"trust": 4, "legal": 4}),
    "animal_welfare": (3, {"mission": 4, "legal": 4, "trust": 4}),
    "specimen_loss": (4, {"mission": 5, "financial": 3, "trust": 4}),
    "research_data_loss": (4, {"mission": 4, "financial": 2}),
    "undisclosed_support": (3, {"legal": 5, "financial": 4, "trust": 4}),
    "controlled_technology": (2, {"legal": 5}),
    "medication_error": (4, {"safety": 5, "trust": 4}),
    "patient_identification": (3, {"safety": 4, "legal": 3}),
    "care_infection": (3, {"safety": 4}),
    "trial_deviation": (4, {"safety": 4, "legal": 4, "mission": 4}),
    "clinical_downtime": (4, {"safety": 4, "mission": 3}),
    "missed_deterioration": (3, {"safety": 5}),
    "health_information_breach": (4, {"legal": 4, "trust": 4, "financial": 3}),
    "access_not_removed": (5, {"legal": 3, "trust": 3}),
    "award_terms": (4, {"legal": 3, "financial": 3}),
    "data_agreement": (3, {"legal": 3, "mission": 3, "trust": 3}),
    "accreditation_lapse": (2, {"legal": 5, "mission": 4}),
    "conduct_not_addressed": (3, {"safety": 3, "legal": 4, "trust": 4}),
    "ransomware": (4, {"mission": 5, "financial": 4, "trust": 4}),
    "compromised_account": (5, {"trust": 3, "legal": 3}),
    "unsupported_systems": (4, {"mission": 3, "legal": 2}),
    "failed_change": (4, {"mission": 3}),
    "backup_failure": (3, {"mission": 5}),
    "exposed_storage": (3, {"legal": 4, "trust": 4}),
    "unreviewed_ai": (4, {"legal": 3, "trust": 3}),
    "sign_in_outage": (3, {"mission": 4, "safety": 3}),
    "power_failure": (3, {"mission": 5, "safety": 3, "financial": 3}),
    "environmental_control": (3, {"mission": 4, "safety": 3}),
    "critical_instrument": (4, {"mission": 3, "financial": 2}),
    "hazard_exposure": (3, {"safety": 4, "legal": 3}),
    "fire_or_flood": (2, {"safety": 5, "mission": 5, "financial": 4}),
    "regional_disaster": (1, {"mission": 5, "safety": 4, "financial": 5}),
    "key_person": (4, {"mission": 3}),
    "recruitment": (4, {"mission": 3, "financial": 2}),
    "workplace_injury": (3, {"safety": 4, "legal": 3}),
    "sustained_overload": (4, {"safety": 3, "mission": 3}),
    "training_lapse": (5, {"legal": 2, "safety": 2}),
    "unallowable_costs": (4, {"financial": 3, "legal": 4, "trust": 3}),
    "effort_certification": (4, {"financial": 3, "legal": 3}),
    "subrecipient_monitoring": (3, {"financial": 3, "legal": 3}),
    "payment_fraud": (4, {"financial": 3}),
    "purchasing_misuse": (3, {"financial": 2, "trust": 3}),
    "operating_shortfall": (2, {"financial": 5, "mission": 4}),
    "gift_terms": (2, {"trust": 4, "financial": 2}),
    "sole_supplier": (3, {"mission": 4}),
    "hosted_service_outage": (3, {"mission": 4, "safety": 3}),
    "supplier_breach": (3, {"legal": 4, "trust": 4}),
    "missing_agreement": (4, {"legal": 4}),
    "collaborator_failure": (3, {"mission": 3, "financial": 2}),
}

# Controls that one unit runs for everyone. A risk anywhere links to that unit's control.
CENTRAL = {
    "access_removed_on_leaving": "IT", "access_reviewed": "SEC", "second_factor": "IT",
    "privileged_access": "IT", "encryption_at_rest": "IT", "backups_tested": "IT",
    "patching": "IT", "malware_protection": "SEC", "network_segmentation": "IT",
    "logging_monitoring": "SEC", "incident_response": "SEC", "security_training": "SEC",
    "ai_use_reviewed": "CMPL", "data_classified": "CMPL", "data_sharing_approved": "CMPL",
    "backup_power_tested": "FAC", "environmental_monitoring": "FAC", "safety_training": "FAC",
    "protocol_tracking": "CMPL", "integrity_training": "CMPL", "disclosure_review": "CMPL",
    "export_screening": "CMPL", "agreements_recorded": "SP", "cost_review": "SP",
    "effort_certified": "SP", "subrecipient_review": "SP", "payment_verification": "FIN",
    "separation_of_duties": "FIN", "budget_monitoring": "FIN", "training_tracked": "HR",
    "reporting_channel": "CMPL", "supplier_assessed": "SEC", "agreements_in_place": "LEGAL",
    "funding_diversified": "PRES", "issues_communication": "COMM", "standards_tracked": "CMPL",
    "gift_terms_recorded": "PHIL", "unsupported_contained": "SEC", "change_review": "IT",
}  # fmt: skip

RATING_NOTES = {
    "effective": [
        "Walked through with the owner and checked against the last four quarters of records.",
        "Sampled ten instances from the past year; all were done as described.",
        "Confirmed in the system's own reports, and by asking the people who do it.",
    ],
    "partly": [
        "Done, but not everywhere: two of the five areas sampled had gaps.",
        "The procedure is sound, but records show it was skipped in three months of twelve.",
        "Works in working hours. Out of hours, nobody is assigned.",
    ],
    "ineffective": [
        "The procedure exists on paper. Nobody could show it had been done this year.",
        "Relies on one person who left in the spring; it has not been done since.",
    ],
}

WHY_INHERENT = [
    "Judged against what has happened here and at similar organizations over the last five years.",
    "It has happened here before, and the conditions that allowed it have not changed.",
    "Peer organizations report this regularly, and we are exposed in the same way.",
    "Without the safeguards we now rely on, nothing would stand in its way.",
]
WHY_RESIDUAL_AGREE = [
    "The controls are rated as shown, and I agree with what they suggest.",
    "Agreed with the suggestion after reviewing each control's latest rating with its owner.",
    "Nothing known beyond the controls' ratings changes the picture.",
]
WHY_RESIDUAL_LOWER = [
    "Lower than suggested: a compensating practice in this unit is not yet recorded as a control.",
    "Lower than the controls suggest, because the exposure here is smaller than for the organization as a whole.",
]
WHY_RESIDUAL_HIGHER = [
    "Higher than suggested: the controls are rated effective, but two near misses this year say otherwise.",
    "Higher than the controls suggest, because the most important one depends on a single person.",
]
WHY_REVIEW = [
    "Reviewed on schedule. No change in the controls or in what we know.",
    "Reviewed with the unit's leader at the quarterly meeting.",
    "Reviewed after the annual planning cycle; the picture is unchanged.",
]
ACCEPT_WHY = [
    "The cost of reducing this further is out of proportion to what it would buy this year.",
    "The remaining exposure is understood, and the replacement is funded for next year.",
    "No practical alternative exists until the current award ends.",
    "Reducing it further would stop work that the mission depends on.",
]
ACCEPT_CONDITIONS = [
    "Reviewed at each quarterly leadership meeting.",
    "No new work is added that would increase the exposure.",
    "The interim safeguards stay in place and are checked monthly.",
    None,
]
PLAN_ACTIONS = [
    [
        "Agree the approach and the budget",
        "Put the missing safeguard in place",
        "Confirm it works, and assess again",
    ],
    [
        "Write the procedure",
        "Train the people who will follow it",
        "Check the first quarter's records",
    ],
    [
        "Select a supplier",
        "Install and configure",
        "Hand over to operations",
        "Test under realistic conditions",
    ],
    ["Name an owner for each gap", "Close the two largest gaps", "Review what remains"],
]
PLAN_OBJECTIVES = {
    "specimen_loss": "Have the freezer alarm answered at any hour",
    "ransomware": "Keep an offline copy of critical data, tested each quarter",
    "research_data_loss": "Move data off instruments and laptops onto managed storage",
    "unsupported_systems": "Isolate what cannot be patched, and schedule its replacement",
    "access_not_removed": "Remove access automatically from the people system",
    "key_person": "Write down what only one person knows, and name a deputy",
    "protocol_lapse": "Track every approval to its renewal in one place",
    "unallowable_costs": "Review charges to awards monthly, by someone trained in the terms",
    "medication_error": "Scan every high-risk medication before it is given",
    "clinical_downtime": "Practice working without the record system twice a year",
    "critical_instrument": "Arrange an alternative before the instrument next fails",
    "power_failure": "Carry critical loads for seventy-two hours on backup power",
    "sole_supplier": "Qualify a second source",
    "missing_agreement": "Check for the required agreement before any data is shared",
    "participant_privacy": "Keep identifiable data in managed systems only",
}
DONE_NOTES = [
    "Done and checked.",
    "Completed; evidence is with the owner.",
    "Finished ahead of the date.",
    None,
]
MOVE_REASONS = [
    "The supplier's delivery slipped.",
    "Waiting on a budget decision.",
    "The person doing it was reassigned for a month.",
    "A dependency on another team's change.",
]
CLOSE_REASONS = [
    "The activity has stopped.",
    "The system was retired and its data moved.",
    "The work moved to a partner organization.",
]

RESPOND_REDUCE = [
    "Above appetite, and worth the cost of bringing down.",
    "The gap is known and can be closed within the year.",
    "Leaders asked for a plan instead of an acceptance.",
]
TARGET_WHY = "Where the plan should leave it, once its actions are done and shown to work."
PLAN_DONE_WHY = (
    "The plan is complete. Its work is not yet recorded as a control, so this is lower than "
    "the controls alone suggest."
)
ESCALATE_REASONS = [
    "The unit cannot fund what would reduce this.",
    "The same exposure exists in neighbouring units; it needs one answer.",
    "The decision is beyond what this unit's leader may accept.",
    "It depends on a service another unit runs.",
]
WITHDRAW_REASONS = [
    "The conditions of the acceptance were not being met.",
    "Circumstances changed: the exposure is larger than when it was accepted.",
]
RETIRE_NOTE = "Replaced, and its data moved to managed storage."

# A framework of the institute's own: the terms of one of its agreements.
AGREEMENT = {
    "title": "Data use agreement: Open Cohort Trust",
    "kind": "agreement",
    "publisher": "Open Cohort Trust",
    "version": "Signed March 2025; renews every three years",
    "summary": "The terms under which the trust shares its cohort data with Population "
    "Sciences: who may use it, where it may be held, and what the trust must be told.",
}
AGREEMENT_TERMS = """\
DUA-2.1 The data are used only for the approved study, by people named in the access list.
DUA-2.2 The access list is reviewed by the principal investigator every six months, and the trust is told of each change within thirty days.
DUA-3.1 The data are held only on systems the institute manages, in the country where they were provided.
DUA-3.2 The data are encrypted wherever they are stored and whenever they are moved.
DUA-3.3 No copy is made onto a personally owned device or removable media.
DUA-4.1 No attempt is made to identify a participant, or to link the data to another source, without the trust's written agreement.
DUA-4.2 Results are released only in a form in which no participant can be identified, with no cell smaller than ten.
DUA-5.1 Any loss of, or unauthorized access to, the data is reported to the trust within seventy-two hours of discovery.
DUA-6.1 The data and every copy are destroyed within ninety days of the agreement ending, and the destruction is certified in writing.
"""

# control (library key), the unit that runs it, the term it answers, how far, and a note.
AGREEMENT_CONTROLS = [
    ("access_reviewed", "SEC", "DUA-2.2", "partial",
     "The review happens twice a year. Telling the trust of changes is not yet anyone's job."),
    ("encryption_at_rest", "IT", "DUA-3.2", "partial",
     "Covers storage and managed laptops. Transfers are covered by the network standard."),
    ("data_classified", "CMPL", "DUA-3.1", "partial", None),
    ("incident_response", "SEC", "DUA-5.1", "partial",
     "The plan names the privacy office; the seventy-two hours is in the checklist."),
    ("data_sharing_approved", "CMPL", "DUA-4.1", "full", None),
]  # fmt: skip

# Bodies of information. key, name, unit, kind, criticality, data class, held in, shared with, agreement
INFORMATION: list[tuple[str, str, str, str, str, str, str, str | None, str | None]] = [
    ("info_cohort", "Cohort survey responses", "PS", "participant_data", "high", "restricted",
     "The cohort database and the survey platform.", "Calder Bay University, under the shared cohort protocol.", "Consent form, version 4"),
    ("info_specimens", "Specimen records", "BIO", "specimen_records", "critical", "restricted",
     "The specimen tracking service.", None, "Repository consent and the material transfer agreements"),
    ("info_patients", "Patient records", "CLIN", "patient_records", "critical", "restricted",
     "The clinical record system and the laboratory information system.", "Lakeshore Reference Laboratory, for tests sent out.", None),
    ("info_trials", "Trial participant data", "CR", "participant_data", "high", "restricted",
     "Electronic data capture and the trial management system.", "Each trial's sponsor, as its protocol provides.", "Trial agreements"),
    ("info_genomic", "Controlled-access genomic data", "RC", "controlled_data", "critical", "restricted",
     "The data enclave, and nowhere else.", None, "The repository's data use certification"),
    ("info_open_cohort", "Open Cohort Trust data", "PS", "controlled_data", "high", "restricted",
     "Research storage, in the cohort project's own area.", None, "Data use agreement: Open Cohort Trust"),
    ("info_people", "Personnel records", "HR", "personnel_records", "high", "restricted",
     "The people system.", None, None),
    ("info_awards", "Award and effort records", "SP", "financial_records", "high", "confidential",
     "The grants management system and the finance system.", "Sponsors, in required reports.", None),
    ("info_donors", "Donor records", "PHIL", "financial_records", "moderate", "confidential",
     "The donor database.", None, None),
    ("info_results", "Unpublished research results", "RES", "intellectual_property", "high", "confidential",
     "Research storage and the electronic lab notebook.", None, None),
]  # fmt: skip
INFORMATION_LINKS: list[tuple[str, str, str]] = [
    ("cohortdb", "holds", "info_cohort"), ("survey", "holds", "info_cohort"),
    ("Cohort follow-up", "uses", "info_cohort"), ("info_cohort", "shared_with", "univ1"),
    ("tracking", "holds", "info_specimens"), ("Specimen storage and retrieval", "uses", "info_specimens"),
    ("record", "holds", "info_patients"), ("lis", "holds", "info_patients"),
    ("Infusion therapy", "uses", "info_patients"), ("info_patients", "shared_with", "labref"),
    ("edc", "holds", "info_trials"), ("ctms", "holds", "info_trials"),
    ("Trial data management", "uses", "info_trials"), ("info_trials", "shared_with", "pharma1"),
    ("enclave", "holds", "info_genomic"), ("Controlled-access data hosting", "uses", "info_genomic"),
    ("storage", "holds", "info_open_cohort"), ("hris", "holds", "info_people"),
    ("grants", "holds", "info_awards"), ("finance", "holds", "info_awards"),
    ("donors", "holds", "info_donors"), ("storage", "holds", "info_results"), ("eln", "holds", "info_results"),
]  # fmt: skip

# Scopes. Central IT provides; the clinic and the enclave rely on it.
SCOPE_PROVIDER = {
    "name": "Central information technology",
    "unit": "IT",
    "summary": "The services Information Technology and Information Security run for the whole institute.",
    "boundary": "Identity, the campus network, backup, the server platform, email, and endpoint "
    "management, and the people who run them. Systems that units run for themselves are outside it.",
    "members": ["identity", "network", "backup", "servers", "email", "endpoints", "siem", "scanner"],
    "units": ["IT", "SEC"],
    "framework": ("nist-csf", None),
    # control (library key), the unit that runs it, who answers for it
    "controls": [
        ("second_factor", "IT", "Identity team"), ("privileged_access", "IT", "Identity team"),
        ("access_removed_on_leaving", "IT", "Identity team"), ("backups_tested", "IT", "Infrastructure team"),
        ("patching", "IT", "Infrastructure team"), ("network_segmentation", "IT", "Network team"),
        ("encryption_at_rest", "IT", "Endpoint team"), ("change_review", "IT", "Change board"),
        ("access_reviewed", "SEC", "Security operations"), ("malware_protection", "SEC", "Security operations"),
        ("logging_monitoring", "SEC", "Security operations"), ("incident_response", "SEC", "Security operations"),
        ("security_training", "SEC", "Security awareness lead"), ("supplier_assessed", "SEC", "Security assurance"),
    ],
}  # fmt: skip
# The assessment the security team is carrying out on what central IT provides.
ASSESSMENT = {
    "name": "Central information technology: security assessment",
    "approach": "Each control is examined against its own records for the last four quarters, and "
    "the team that runs it is interviewed. Results are recorded by one assessor and confirmed by "
    "the other. Systems that units run for themselves are assessed with their own scopes.",
    # The one control the assessment finds wanting, whatever was believed of it before.
    "finding": ("access_removed_on_leaving", "effective", "partly",
                "Leavers between July and September, from the personnel system: 25 people.",
                "Twenty-two accounts were disabled on the last working day. Three stayed active for "
                "between nine and twenty-three days, all of them people on fixed-term contracts whose "
                "end dates were not sent to the identity team."),
    "returned": "Say which quarter was sampled, and how many were looked at.",
}  # fmt: skip
# What a test looked at and what it found, by outcome.
TESTS = {
    "effective": [
        ("The last four quarters of records, and ten instances chosen at random.",
         "All ten were done as described, on time, with the record kept where the procedure says."),
        ("Settings exported from the system on the day, and the change history for the year.",
         "The settings match the standard. No change in the year weakened them."),
        ("An interview with the team lead, and the team's own log for the past six months.",
         "Done as described every time it fell due. Exceptions were recorded and followed up."),
    ],
    "partly": [
        ("Twenty instances from the past year, chosen at random.",
         "Sixteen were done as described. Four were late by more than a month, all in one team."),
        ("Settings exported from every system in the boundary.",
         "In force on all but two older systems, which cannot support it and have no plan yet."),
    ],
    "ineffective": [
        ("The records for the past year, and an interview with the people named in the procedure.",
         "No record that it has been done since the person responsible moved to another team."),
    ],
}  # fmt: skip
SCOPE_CLINIC = {
    "name": "Clinical systems",
    "unit": "CLIN",
    "summary": "The systems that hold and use patient records in the research clinic.",
    "boundary": "The clinical record system, the laboratory information system, dispensing "
    "cabinets, infusion pumps, and scheduling, with the clinic staff who use them.",
    "members": ["record", "lis", "cabinets", "pumps", "scheduling", "info_patients", "recordco"],
    "units": ["CLIN"],
    "framework": ("hipaa-security", None),
    "inherited": ["second_factor", "backups_tested", "patching", "malware_protection",
                  "logging_monitoring", "incident_response", "encryption_at_rest",
                  "access_removed_on_leaving"],
    # control, where the clinic's part stands, what the clinic does
    "shared": [
        ("access_reviewed", "in_place",
         "Clinic managers review who can open the clinical record each quarter, and Security reviews the rest."),
        ("security_training", "partly",
         "The clinic adds a module on patient privacy. A third of agency staff have not yet taken it."),
    ],
    "own": [("downtime_procedures", "in_place", "Nurse managers",
             "Each area keeps paper forms and a downtime box, and practices in spring and autumn.")],
    "excluded": [
        (["164.308(a)(4)(ii)(A)"], "Northmere is not, and does not include, a health care clearinghouse."),
        (["164.314(b)(1)", "164.314(b)(2)", "164.314(b)(2)(i)", "164.314(b)(2)(ii)",
          "164.314(b)(2)(iii)", "164.314(b)(2)(iv)"],
         "These apply to group health plans. The clinic is a provider, not a plan."),
    ],
}  # fmt: skip
SCOPE_ENCLAVE = {
    "name": "Controlled-access data enclave",
    "unit": "RC",
    "summary": "Where genomic data obtained under a repository's certification is held and analysed.",
    "boundary": "The enclave's hosts and storage in racks 4 to 6, its own network segment, and "
    "the twelve approved users. Nothing leaves it except results a data steward has released.",
    "members": ["enclave", "info_genomic", "genomevault", "Controlled-access data hosting"],
    "units": [],
    "framework": ("nist-800-171", None),
    "inherited": ["second_factor", "network_segmentation", "malware_protection", "incident_response"],
    "shared": [
        ("patching", "in_place",
         "Research Computing patches the enclave's own hosts on the institute's schedule; IT patches what is beneath them."),
        ("logging_monitoring", "planned",
         "The enclave's hosts do not yet send their logs to security monitoring. Due with the next storage refresh."),
        ("backups_tested", "partly",
         "The enclave is backed up to its own encrypted set. A full restore has not been tried."),
    ],
    "own": [("privileged_access", "in_place", "Enclave administrators",
             "Two named administrators, separate accounts, and every session recorded.")],
    "excluded": [],
}  # fmt: skip

# Issues at every stage. Each: where it is, what found it, how serious, what is wrong, the
# detail, and its actions as (what, days from the build that it is due, whether it is done).
ISSUES = {
    "alarm": {
        "unit": "BIO", "source": "observation", "severity": "high",
        "name": "The freezer alarm call list names people who have left",
        "summary": "When the minus-eighty in bay 3 alarmed on a Sunday, the first two numbers on "
        "the call list belonged to people who left in the spring. The third answered after forty minutes.",
        "actions": [("Rebuild the call list from this quarter's rota", -40, True),
                    ("Test the call-out at night, unannounced", -12, False)],
    },
    "cabinets": {
        "unit": "PHARM", "source": "audit", "severity": "high",
        "name": "Override reports from the dispensing cabinets are not reviewed",
        "summary": "Internal audit found that the weekly report of overrides was produced and filed, "
        "and that nobody had signed one off since the pharmacy manager changed.",
        "actions": [("Name a reviewer and a deputy for the weekly report", -70, True),
                    ("Review the backlog of unsigned reports and follow up the outliers", -30, True)],
        "done": "A pharmacist and a deputy now sign the report each Monday. The backlog was reviewed: "
        "three overrides were followed up with the nurses concerned, and none was a diversion.",
        "cause": "ownership",
        "proof": ("Signed override reports, eight weeks", "The eight most recent weekly reports, each signed and dated."),
    },
    "visitors": {
        "unit": "FAC", "source": "observation", "severity": "low",
        "name": "Contractors are let into plant rooms without signing the log",
        "summary": "Three visits by the chiller contractor in one month have no entry in the plant room log.",
        "actions": [("Move the log to the security desk, where keys are issued", -190, True)],
        "done": "Keys to plant rooms are now issued at the security desk against a signature. "
        "A month of entries was checked against the contractor's invoices.",
        "cause": "procedure",
        "proof": ("Plant room log against invoices", "Every invoiced visit in the month has an entry."),
    },
    "letters": {
        "unit": "SP", "source": "review", "severity": "moderate",
        "name": "Monitoring letters are missing for two sub-recipients",
        "summary": "The annual review of sub-awards found no monitoring letter on file for two of "
        "the fourteen sub-recipients.",
        "actions": [("Obtain and file the two letters", -25, True)],
        "done": "Both letters have been requested and filed.",
        "cause": "people",
        "returned": "Only one of the two letters is on file. The other is a request for it.",
        "moved": (45, "The second sub-recipient's finance office is closed until the new year."),
    },
    "duplicate": {
        "unit": "IT", "source": "observation", "severity": "moderate",
        "name": "Two legacy hosts cannot be patched",
        "summary": "The hosts behind the old instrument booking system have had no patches this year.",
        "actions": [],
        "withdrawn": "Recorded twice: the assessment has opened an issue for the same control.",
    },
    "gap": {
        "unit": "CLIN", "source": "gap", "severity": "moderate",
        "summary": "Nothing the clinic does, and nothing it inherits, answers this. It was noted "
        "when the clinic's requirements were first gone through, and nobody has taken it up.",
        "actions": [],
    },
}  # fmt: skip
# What is done about the control the assessment found wanting.
FINDING_ACTIONS = [
    (
        "Send contract end dates from the personnel system to the identity team each night",
        20,
        False,
    ),
    ("Disable the three accounts found, and check the last year's leavers for others", -15, True),
]
# Exceptions at every stage.
EXCEPTIONS = {
    "leavers": {
        "why": "Agency nurses are engaged through the agency, and their end dates are not in the "
        "personnel system that the identity team works from. That feed is being built.",
        "instead": "Each Friday the nurse managers send the identity team the names of agency staff "
        "who have finished, and the accounts are disabled that day.",
        "note": "Until the feed is in. Not to be renewed without a date for it.",
    },
    "rooms": {
        "why": "The enclave shares a machine room with other tenants until it moves to the new data "
        "hall, and this cannot be met there before then.",
        "instead": "Racks 4 to 6 are locked, the two administrators hold the only keys, and the "
        "room's door log is reviewed against their visits every month.",
        "note": None,
    },
    "training": {
        "why": "Agency staff cannot be enrolled in the learning system, so a third of them have "
        "not taken the privacy module.",
        "instead": "A printed briefing is signed on the first shift, and kept by the nurse manager.",
    },
    "logs": {
        "why": "The enclave's hosts cannot send their logs to security monitoring until the storage "
        "refresh gives them a route out that the data-use terms allow.",
        "instead": "The administrators review the hosts' own logs each week and record that they did.",
        "note": "For the length of the refresh project.",
    },
    "patching": {
        "why": "Two hosts behind the old instrument booking system run a release the maker no "
        "longer patches, and the system cannot move until the cores agree a replacement.",
        "instead": "The hosts are on their own network segment, reachable only from the booking desk.",
        "refused": "This has been the answer for two years. Retire them or move them, and bring a date.",
    },
}

# Evidence collected when a control is rated. kind: (name, what the item says)
EVIDENCE = {
    "file": [
        ("Sample of records", "sample"),
        ("Quarterly report", "report"),
        ("Export from the system", "export"),
    ],
    "link": [
        (
            "Procedure and its last run",
            "The procedure, with the log of when it was last carried out.",
        ),
        ("Ticket queue for the period", "Every request and how long each took."),
    ],
    "note": [
        ("Walkthrough notes", None),
        ("Interview with the owner", None),
    ],
    "attestation": [
        (
            "Owner's attestation",
            "I confirm that this control operated as described throughout the period.",
        ),
    ],
}
EVIDENCE_ROWS = [
    "date,item,done,checked_by",
    "{d1},1,yes,owner",
    "{d2},2,yes,owner",
    "{d3},3,yes,deputy",
    "{d4},4,no,owner",
    "{d5},5,yes,owner",
]
