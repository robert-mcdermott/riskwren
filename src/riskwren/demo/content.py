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
    ("auditor2", "Ruben Castillo", "Senior Internal Auditor", "RISK", [("auditor", None, None)]),
    ("admin", "Tobias Larsen", "Systems Administrator", "IT", [("admin", None, None)]),
    ("cio", "Priya Chaudhry", "Chief Information Officer", "IT", [("leader", "IT", "high")]),
    ("ciso", "Goran Dimitrov", "Chief Information Security Officer", "SEC",
     [("leader", "SEC", "high"), ("assessor", None, None)]),
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
    (
        "ciso",
        "Security leader",
        "Leads Information Security: decides its exceptions, sees every scope",
    ),
    ("assess1", "Assessor", "Tests controls, reviews results, and confirms closures, everywhere"),
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
    "access_approved": "IT", "unique_accounts": "IT", "session_lock": "IT", "remote_access": "IT",
    "encryption_in_transit": "IT", "media_disposal": "IT", "asset_inventory": "IT",
    "secure_configuration": "IT", "disaster_recovery": "IT", "physical_access": "IT",
    "vulnerability_scanning": "SEC", "log_protection": "SEC", "incident_reporting": "SEC",
    "security_policy": "SEC", "security_roles": "SEC", "security_oversight": "SEC",
    "security_risk_assessment": "SEC", "security_testing": "SEC", "personnel_screening": "HR",
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

# What each third party provides. key, name, party, unit, kind, criticality, data class, the
# systems it reaches, and the information it handles. ``added`` is days before the build.
SERVICES: list[tuple[str, str, str, str, str, str, str | None, list[str], list[str]]] = [
    ("svc_tracking", "Hosted specimen tracking", "trackco", "BIO", "software_service", "high", "restricted", ["tracking"], ["info_specimens"]),
    ("svc_freezers", "Freezer farm maintenance", "coldline", "BIO", "maintenance", "high", None, ["monitor", "freezers"], []),
    ("svc_nitrogen", "Liquid nitrogen delivery", "cryogas", "BIO", "supply", "critical", None, [], []),
    ("svc_courier", "Specimen shipping", "courier", "BIO", "logistics", "moderate", "restricted", [], ["info_specimens"]),
    ("svc_chemistry", "Sequencing chemistry", "reagents", "GEN", "supply", "critical", None, [], []),
    ("svc_sequencers", "Sequencer service contract", "seqmaker", "GEN", "maintenance", "high", "confidential", ["sequencer1", "sequencer2"], []),
    ("svc_microscopes", "Microscope service and remote support", "optics", "IMG", "maintenance", "high", "internal", ["confocal", "cryo", "imgws"], []),
    ("svc_feed", "Feed, bedding, and caging", "feed", "CMP", "supply", "high", None, [], []),
    ("svc_record", "Hosted clinical record system", "recordco", "CLIN", "software_service", "critical", "restricted", ["record"], ["info_patients"]),
    ("svc_pumps", "Infusion pump drug library and service", "pumpco", "INF", "maintenance", "high", "restricted", ["pumps"], []),
    ("svc_cabinets", "Dispensing cabinet service", "pharmaco", "PHARM", "maintenance", "high", "restricted", ["cabinets"], ["info_patients"]),
    ("svc_reference", "Reference laboratory testing", "labref", "CLAB", "laboratory", "high", "restricted", ["lis"], ["info_patients"]),
    ("svc_edc", "Hosted data capture and trial management", "edcco", "CR", "software_service", "high", "restricted", ["edc", "ctms"], ["info_trials"]),
    ("svc_monitoring", "Trial monitoring visits", "cro", "CR", "professional", "moderate", "restricted", ["edc"], ["info_trials"]),
    ("svc_surveys", "Hosted participant surveys", "surveyco", "PS", "software_service", "moderate", "restricted", ["survey"], ["info_cohort"]),
    ("svc_identity", "Identity and sign-in", "cloud", "IT", "software_service", "critical", "confidential", ["identity"], []),
    ("svc_network", "Network equipment support", "netco", "IT", "maintenance", "high", "internal", ["network"], []),
    ("svc_vault", "Offsite backup vaulting", "backupco", "IT", "hosting", "high", "restricted", ["backup"], ["info_patients", "info_people"]),
    ("svc_watch", "Out-of-hours security monitoring", "soc", "SEC", "professional", "high", "confidential", ["siem"], []),
    ("svc_notebook", "Hosted lab notebook", "elnco", "RC", "software_service", "high", "confidential", ["eln"], ["info_results"]),
    ("svc_grants", "Hosted grants management", "grantsco", "SP", "software_service", "high", "confidential", ["grants"], ["info_awards"]),
    ("svc_finance", "Hosted finance and payroll", "financeco", "FIN", "software_service", "critical", "restricted", ["finance", "payroll"], ["info_people", "info_awards"]),
    ("svc_people", "Hosted people and learning systems", "hrco", "HR", "software_service", "high", "restricted", ["hris", "learning"], ["info_people"]),
    ("svc_building", "Building controls support", "bmsco", "FAC", "maintenance", "critical", None, ["bms"], []),
    ("svc_generators", "Generator service and load tests", "gensvc", "FAC", "maintenance", "high", None, ["generators"], []),
    ("svc_waste", "Hazardous waste collection", "waste", "FAC", "logistics", "moderate", None, [], []),
    ("svc_cleaning", "Laboratory and clinic cleaning", "cleaning", "FAC", "maintenance", "moderate", None, [], []),
    ("svc_donors", "Hosted donor database", "donorco", "PHIL", "software_service", "moderate", "confidential", ["donors"], ["info_donors"]),
    ("svc_website", "Website design and hosting", "webco", "COMM", "hosting", "low", "public", ["website"], []),
    ("svc_counsel", "Outside counsel", "lawfirm", "LEGAL", "professional", "moderate", "confidential", [], []),
    ("svc_insurance", "Property, liability, and cyber insurance", "insurer", "FIN", "professional", "high", "confidential", [], []),
    ("svc_audit", "Annual financial audit", "auditfirm", "FIN", "professional", "moderate", "confidential", ["finance"], ["info_awards"]),
    ("svc_staffing", "Temporary laboratory staff", "staffing", "HR", "staffing", "low", "internal", [], []),
    ("svc_cohort", "The shared cohort", "univ1", "RES", "collaboration", "high", "restricted", [], ["info_cohort"]),
    ("svc_linkage", "Data linkage for the community cohort", "sub2", "SP", "data_service", "moderate", "restricted", [], ["info_cohort"]),
    ("svc_genomes", "Controlled-access genomic data", "genomevault", "RC", "data_service", "high", "restricted", ["enclave"], ["info_genomic"]),
]  # fmt: skip
# Added later than the rest: the email service, once the institute moved its mail to the
# same supplier as its identity service. Its supplier is tiered again when it arrives.
LATER_SERVICE = ("svc_mail", "Email and collaboration", "cloud", "IT", "software_service", "critical", "restricted", ["email"], ["info_people", "info_results"])  # fmt: skip

# How each third party reaches the institute, beyond what its services' links suggest, and
# anything else its tiering said that the inventory could not. The rest are suggested.
TIERING_ANSWERS: dict[str, dict[str, object]] = {
    "trackco": {"access": ["integration", "accounts"], "people": "many"},
    "coldline": {"access": ["on_site", "physical", "remote"], "dependency": "stops"},
    "cryogas": {"access": ["on_site"], "dependency": "stops"},
    "courier": {"access": ["physical"], "people": "many"},
    "reagents": {"dependency": "stops"},
    "seqmaker": {"access": ["remote", "on_site"]},
    "optics": {"access": ["remote", "on_site"]},
    "feed": {"access": ["on_site"]},
    "recordco": {"access": ["privileged", "integration", "accounts"], "people": "many", "subcontractors": True},
    "pumpco": {"access": ["remote", "on_site"], "people": "many"},
    "pharmaco": {"access": ["remote", "on_site", "integration"], "people": "many"},
    "labref": {"access": ["integration"], "people": "many"},
    "edcco": {"access": ["integration", "accounts"], "people": "many", "subcontractors": True},
    "cro": {"access": ["accounts", "on_site"], "people": "few"},
    "surveyco": {"access": ["integration"], "people": "many", "offshore": True},
    "cloud": {"access": ["privileged", "integration", "accounts"], "people": "many", "subcontractors": True},
    "netco": {"access": ["remote", "privileged"]},
    "backupco": {"access": ["integration"], "people": "many"},
    "soc": {"access": ["remote", "accounts"]},
    "elnco": {"access": ["integration", "accounts"]},
    "grantsco": {"access": ["integration", "accounts"]},
    "financeco": {"access": ["integration", "accounts"], "people": "many"},
    "hrco": {"access": ["integration", "accounts"], "people": "many"},
    "bmsco": {"access": ["remote", "on_site"]},
    "gensvc": {"access": ["on_site", "physical"]},
    "waste": {"access": ["no_access"], "dependency": "little"},
    "cleaning": {"access": ["physical"]},
    "donorco": {"access": ["integration"], "people": "many"},
    "webco": {"access": ["remote"]},
    "lawfirm": {"access": ["no_access"]},
    "insurer": {"access": ["no_access"]},
    "auditfirm": {"access": ["accounts"]},
    "staffing": {"access": ["accounts", "on_site", "physical"]},
    "univ1": {"access": ["integration"], "people": "many"},
    "sub2": {"access": ["integration"], "people": "many"},
    "genomevault": {"access": ["integration"], "people": "many", "offshore": True},
}  # fmt: skip
# Where the person tiering it recorded a different tier from the rules', and why.
TIERING_JUDGED: dict[str, tuple[str, str]] = {
    "webco": (
        "tier_3",
        "It reaches only the public website, which holds nothing that is not "
        "already published, and the site is kept apart from the campus network.",
    ),
}
# Partners and sponsors not yet tiered: none of them holds or reaches anything of the
# institute's through a service on record.
UNTIERED = ("funder1", "funder2", "funder3", "pharma1", "hospital", "univ2", "sub1")

# The people at third parties who answer questionnaires. They are not accounts.
CONTACTS: dict[str, list[tuple[str, str, str]]] = {
    "recordco": [("Dana Whitcombe", "dana.whitcombe@pellham.example", "Director of information security")],
    "cloud": [("Priya Raman", "trust@quillon.example", "Customer trust team"),
              ("Marcus Hale", "marcus.hale@quillon.example", "Account manager")],
    "financeco": [("Ines Okafor", "security@ledgerwell.example", "Security and compliance manager")],
    "edcco": [("Tomasz Wierzbicki", "t.wierzbicki@castellan.example", "Head of quality and security")],
    "backupco": [("Ruth Calloway", "compliance@stonebridge.example", "Compliance officer")],
    "surveyco": [("Ana Ruiz", "ana.ruiz@tallyfield.example", "Security lead")],
    "trackco": [("Kenji Mori", "kenji.mori@specimenledger.example", "Chief technology officer")],
    "labref": [("Helen Ashdown", "privacy@lakeshorelab.example", "Privacy and security officer")],
    "soc": [("Femi Adeyemi", "femi@lanternwatch.example", "Service delivery manager")],
    "genomevault": [("Lars Nygaard", "access@genomecommons.example", "Data access committee")],
    "elnco": [("Sophie Brandt", "security@foliobench.example", "Security engineer")],
    "hrco": [("Olivia Grant", "trust@peoplebook.example", "Trust and safety")],
}  # fmt: skip

# Due diligence reviews: the third party, who keeps the review, the questionnaire (by tier
# unless named), and when each step happened, in days before the build. ``saved`` is when
# the contact saved some answers without sending them. ``answers`` departs from a sound
# answer to every question; ``link_days`` is how long the link lasted.
REVIEWS: list[dict[str, object]] = [
    {"party": "elnco", "by": "assess1", "started": 420, "sent": 418, "answered": 409,
     "concluded": 404, "conclusion": "approved", "note": None},
    {"party": "recordco", "by": "ciso", "started": 335, "sent": 332, "answered": 318,
     "concluded": 311, "conclusion": "approved", "note": None,
     "answers": {"phi": True, "baa": True, "hipaa_assessment": True, "subprocessors": True,
                 "subprocessor_list": "A hosting provider for the servers, and a support desk for out-of-hours calls.",
                 "subprocessor_terms": True, "subprocessor_review": True,
                 "certifications": ["soc2_type2", "hitrust", "pentest"]}},
    {"party": "cloud", "by": "ciso", "started": 302, "sent": 300, "answered": 291,
     "concluded": 286, "conclusion": "conditions",
     "note": "Administrators of the institute's tenant to use security keys by the end of June; their own staff already do.",
     "answers": {"mfa_admin": False, "certifications": ["soc2_type2", "iso27001", "fedramp"],
                 "subprocessors": True, "subprocessor_list": "Data centre operators in three regions.",
                 "subprocessor_terms": True, "subprocessor_review": True}},
    {"party": "financeco", "by": "assess1", "started": 262, "sent": 260, "answered": 251,
     "concluded": 246, "conclusion": "approved", "note": None},
    {"party": "edcco", "by": "ciso", "started": 204, "sent": 201, "answered": 188,
     "concluded": 181, "conclusion": "conditions",
     "note": "Restores to be tested before the next trial starts, and the result sent to Clinical Research.",
     "answers": {"backups": False, "phi": True, "baa": True, "hipaa_assessment": True,
                 "recovery": "week"}},
    {"party": "backupco", "by": "ciso", "started": 158, "sent": 156, "answered": 149,
     "concluded": 145, "conclusion": "approved", "note": None,
     "answers": {"phi": True, "baa": True, "hipaa_assessment": True}},
    # Answered last week, with four concerns: waiting for the security leader.
    {"party": "surveyco", "by": "ciso", "started": 33, "sent": 31, "saved": 15, "answered": 6,
     "sends": "SOC 2 Type II report 2026.pdf",
     "answers": {"us_only": False, "locations": "Survey responses are processed by our team in Dublin, Ireland.",
                 "breach_last": True,
                 "breach_detail": "In 2025 a misconfigured export exposed one customer's survey links for two days. Exports now need a second person's approval.",
                 "patching": "longer", "subprocessors": True,
                 "subprocessor_list": "A cloud hosting provider and an email delivery service.",
                 "subprocessor_terms": True, "subprocessor_review": False,
                 "phi": True, "baa": True, "hipaa_assessment": False}},
    # Sent, with some answers saved and not yet sent.
    {"party": "trackco", "by": "assess1", "started": 13, "sent": 12, "saved": 3, "due": -9},
    # Answers late: the date has passed and the link still works.
    {"party": "labref", "by": "ciso", "started": 44, "sent": 40, "due": 19, "link_days": 60},
    # The link ran out before anyone answered.
    {"party": "soc", "by": "assess1", "started": 22, "sent": 20, "due": -1, "link_days": 14},
    # Started, not yet sent.
    {"party": "genomevault", "by": "ciso", "started": 2},
]  # fmt: skip

# Reports and certificates about third parties, and what a careful reading of each found.
# Days are before the build (negative: after it). Each responsibility is what the report
# leaves to the institute, with the control here that does it (by its library key and the
# unit that runs it), or None.
ASSURANCE: list[dict[str, object]] = [
    {"party": "recordco", "by": "ciso", "name": "HITRUST r2 certification",
     "kind": "hitrust", "issuer": "Calloway Certification Services", "opinion": "none",
     "received": 320, "from": 380, "to": 380, "until": -350, "reviewed": 314,
     "services": ["svc_record"], "reliance": "relies",
     "duties": [("Customers remove their own users' access when they leave.",
                 ("access_removed_on_leaving", "IT"), "in_place")]},
    {"party": "cloud", "by": "ciso", "name": "SOC 2 Type II report, October 2024 to September 2025",
     "kind": "soc2_type2", "issuer": "Harrowgate Assurance LLP", "opinion": "qualified",
     "received": 282, "from": 785, "to": 422, "until": -40, "reviewed": 276,
     "services": ["svc_identity"], "reliance": "partly",
     "carve_outs": "The data centres the service runs in are carved out; their own reports cover them.",
     "exceptions": [{"control": "CC6.2", "description": "For 3 of 25 leavers sampled, access was removed more than 30 days after they left.",
                     "matters": True, "response": "The institute's own administrators are removed by its identity team on the day they leave."},
                    {"control": "CC7.4", "description": "One incident's review was finished late.", "matters": False, "response": None}],
     "duties": [("Customers require a second factor for their own users.", ("second_factor", "IT"), "in_place"),
                ("Customers review who holds administrative roles in their tenant each quarter.", ("access_reviewed", "SEC"), "in_place"),
                ("Customers set how long mail is kept, to meet their own obligations.", None, "not_in_place")],
     "note": "The supplier's own removal of leavers is weak; the institute's administrators are removed by its own process. Mail, added since, is outside the report's period."},
    {"party": "financeco", "by": "assess1", "name": "SOC 2 Type II report, 2024",
     "kind": "soc2_type2", "issuer": "Pennock and Hale", "opinion": "unqualified",
     "received": 430, "from": 790, "to": 425, "until": 60, "reviewed": 424,
     "services": ["svc_finance"], "reliance": "relies",
     "duties": [("Customers check each payment run before it is released.", ("payment_verification", "FIN"), "in_place")]},
    {"party": "backupco", "by": "ciso", "name": "SOC 2 Type II report, 2025",
     "kind": "soc2_type2", "issuer": "Harrowgate Assurance LLP", "opinion": "unqualified",
     "received": 162, "from": 540, "to": 175, "until": -190, "reviewed": 152,
     "services": ["svc_vault"], "reliance": "relies",
     "duties": [("Customers test that they can restore what is vaulted.", ("backups_tested", "IT"), "in_place")]},
    {"party": "edcco", "by": "ciso", "name": "ISO/IEC 27001 certificate",
     "kind": "iso27001", "issuer": "Northway Registrar", "opinion": "none",
     "received": 196, "from": None, "to": None, "until": -520, "reviewed": 190,
     "services": [], "reliance": "partly",
     "note": "The certificate's scope is the hosting operation, not the trial applications themselves."},
    {"party": "trackco", "by": "assess1", "name": "Penetration test summary, 2026",
     "kind": "pentest", "received": 38, "from": 70, "to": 60, "until": -320},
]  # fmt: skip

# Who the institute's agreements are with, and the agreements with its suppliers that the
# third-party program entered. Days are before the build (negative: after it). Three gaps are
# left: the pharmacy cabinets' supplier handles patient records with no business associate
# agreement; the shared cohort with Calder Bay University went on after its memorandum was
# closed; and the courier's contract has ended and is still open.
AGREEMENT_PARTIES = {
    "cohort_dua": ["funder3"], "genomic_cert": ["genomevault"], "vault_baa": ["backupco"],
    "imaging_mou": ["univ1"],
}  # fmt: skip
# What an existing agreement also covers, now that services are on record.
AGREEMENT_SERVICES = {"vault_baa": ["svc_vault"], "genomic_cert": ["svc_genomes"]}
SUPPLIER_AGREEMENTS: list[dict[str, object]] = [
    {"name": "Business associate agreement: Pellham Clinical Systems", "kind": "business_associate",
     "party": "recordco", "unit": "CLIN", "starts": 1100, "ends": -295, "notice": 90, "renews": True,
     "covers": ["svc_record"]},
    {"name": "Business associate agreement: Lakeshore Reference Laboratory", "kind": "business_associate",
     "party": "labref", "unit": "CLAB", "starts": 820, "ends": None, "covers": ["info_patients"]},
    {"name": "Master services agreement: Quillon Cloud", "kind": "contract", "party": "cloud",
     "unit": "IT", "starts": 1300, "ends": -210, "notice": 60, "renews": True,
     "covers": ["svc_identity", "svc_mail"]},
    {"name": "Hosting agreement: Ledgerwell", "kind": "contract", "party": "financeco",
     "unit": "FIN", "starts": 1500, "ends": -500, "notice": 120, "covers": ["svc_finance"]},
    {"name": "Subscription agreement: Peoplebook", "kind": "contract", "party": "hrco",
     "unit": "HR", "starts": 700, "ends": -30, "notice": 60, "renews": True, "covers": ["svc_people"]},
    {"name": "Services agreement: Castellan Trial Systems", "kind": "contract", "party": "edcco",
     "unit": "CR", "starts": 600, "ends": -400, "covers": ["svc_edc"]},
    {"name": "Monitoring services agreement: Halden Research Partners", "kind": "contract",
     "party": "cro", "unit": "CR", "starts": 420, "ends": -310, "covers": ["svc_monitoring"]},
    {"name": "Clinical trial agreement: Verdance Therapeutics", "kind": "contract", "party": "pharma1",
     "unit": "CR", "starts": 480, "ends": -700, "covers": ["info_trials"]},
    {"name": "Subscription: Tallyfield Surveys", "kind": "contract", "party": "surveyco",
     "unit": "PS", "starts": 350, "ends": -15, "renews": True, "notice": 30, "covers": ["svc_surveys"]},
    {"name": "Subaward: Northfield Data Collaborative", "kind": "award", "party": "sub2",
     "unit": "SP", "starts": 300, "ends": -430, "covers": ["svc_linkage"]},
    {"name": "Hosting agreement: Specimen Ledger Systems", "kind": "contract", "party": "trackco",
     "unit": "BIO", "starts": 900, "ends": -365, "covers": ["svc_tracking"]},
    {"name": "Courier agreement: Swiftcold Logistics", "kind": "contract", "party": "courier",
     "unit": "BIO", "starts": 760, "ends": 25, "covers": ["svc_courier"]},
]  # fmt: skip

# A relationship over time. Days are before the build (negative: after it).
SUBCONTRACTORS = [("recordco", "cloud"), ("surveyco", "cloud"), ("edcco", "cloud")]
FINDINGS: list[dict[str, object]] = [
    {"review": "cloud", "by": "ciso", "raised": 284, "severity": "high",
     "name": "Quillon Cloud: administrators' second factor can be phished",
     "summary": "Its own staff use security keys; the institute's tenant administrators still use codes sent by text.",
     "action": "Move every tenant administrator to a security key", "contact": "cloud", "due": -20,
     "agreed": "Agreed with the supplier: security keys for every tenant administrator with its next release."},
    {"review": "edcco", "by": "ciso", "raised": 179, "severity": "moderate",
     "name": "Castellan Trial Systems: restoring trial data has not been tested",
     "summary": "It answered that backups are not restored to test them. The condition was a tested restore before the next trial starts.",
     "action": "Restore a trial's data to a test system, and send the result to Clinical Research", "contact": "edcco", "due": 15},
]  # fmt: skip
CALLED_REVIEWS = [
    {"party": "backupco", "by": "ciso", "on": 12, "event": "breach_notice",
     "note": "On the 14th it told customers that a misconfigured storage area exposed other customers' backup catalogues for a day. It says the institute's were not among them."},
]  # fmt: skip
OFFBOARDING = {
    "party": "webco", "started": 25,
    "reason": "The public website moves to the institute's own platform at the end of the month.",
    "steps": [("access", 20, "The supplier's accounts on the web servers and in the content system were removed."),
              ("information", 9, "The site's content and analytics were exported, and the supplier deleted its copies.")],
}  # fmt: skip

# Leadership reports, issued by the risk manager each quarter: days ago, and what they said.
LEADERSHIP_REPORTS = [
    (119, "The register now covers every division: each unit's risks have owners, and most "
          "have a residual rating.\n\nRansomware reaching research computing is the risk "
          "above appetite that most needs attention. The plan to keep the backups apart from "
          "the campus network is under way, and its actions are tracked here."),
    (28, "Third parties are now part of the record: those that matter most are tiered, and "
         "their due diligence, findings, and agreements are kept here.\n\nIssues past their "
         "date are the figure to watch. The security team asks each owner to agree a new date "
         "or close the issue before the next report."),
]  # fmt: skip

# Estimates in ranges, put to the risks the security team most wanted figures for: days ago,
# the risk by name, how often a year (low, likely, high), each time in dollars, and why.
ESTIMATES = [
    (130, "Ransomware reaching research storage", (0.05, 0.2, 0.5), (250_000, 1_200_000, 6_000_000),
     "Two peer institutes were hit in the last three years; one lost three weeks of research "
     "computing. Each time: recovery labor and outside responders, grant extensions, and "
     "re-running lost experiments, from their published costs and our own staffing."),
    (128, "Ransomware: Information Technology", (0.1, 0.25, 0.6), (150_000, 600_000, 2_500_000),
     "Central systems are better separated than research storage. The figures follow the "
     "incident response exercise in the autumn and the vendor's quote for a rebuild."),
    (40, "Ransomware reaching research storage", (0.05, 0.15, 0.4), (250_000, 900_000, 4_000_000),
     "Estimated again after research storage was taken off the lab networks: a smaller "
     "chance, and a faster recovery from the offline copy."),
]  # fmt: skip

# Scenarios the security team worked through with the units that would be hit.
SCENARIOS = [
    {"name": "Ransomware takes research computing down for two weeks", "unit": "SEC",
     "by": "ciso", "started": 125, "concluded": 112,
     "summary": "On a Friday night, an attacker who came in through a phished lab account "
                "encrypts research storage and the cluster's file systems. The backups are "
                "intact, but restoring everything takes two weeks.",
     "assumptions": "The offline copy of research storage is no more than a day old. "
                    "Clinical and administrative systems are not reached. Sequencing and "
                    "imaging keep their instruments' local disks.",
     "conclusion": "Two weeks is survivable for most labs, not for the sequencing service, "
                   "whose sponsors' samples expire. Restore its data first, and test a full "
                   "restore of research storage this year.",
     "risks": ["Ransomware reaching research storage", "Ransomware: Information Technology"],
     "processes": ["Research data storage", "High-performance computing", "Sequencing service"]},
    {"name": "A supplier holding trial data is breached", "unit": "SEC", "by": "ciso",
     "started": 20, "concluded": None,
     "summary": "The electronic data capture vendor tells us an attacker copied a customer "
                "database that held our trial participants' records.",
     "assumptions": "The vendor tells us within the 72 hours its agreement requires. The "
                    "data is identifiable.",
     "conclusion": None,
     "risks": [], "processes": ["Trial data management", "Safety reporting"]},
]  # fmt: skip

# Internal audit: what the auditor says about a few things in the universe (kind, name, what),
# and two plans: this year's, approved by the president for the audit committee, mostly under
# way, one engagement dropped; and next year's, in draft. Days are relative to the build.
AUDIT_SAYS = [
    ("process", "Medication dispensing", {"adjustment": 15, "adjustment_reason": "Two dispensing near misses were reported to the pharmacy and therapeutics committee this year."}),
    ("system", "Identity service", {"last_audited_on": 400, "last_audit_note": "Identity and access review by the external auditors, before RiskWren."}),
    ("unit", "Facilities and Safety", {"left_out": True, "left_out_reason": "Audited by the state's fire marshal and the insurer's engineers; internal audit relies on their reports."}),
]  # fmt: skip
AUDIT_PLANS = [
    {"name": "Internal audit plan, this year", "from": 245, "to": -120, "drafted": 250,
     "approved": 243, "by": "president",
     "note": "Approved by the audit committee of the board.",
     "summary": "Three engagements chosen from the top of the universe, with the security office's two highest risks first.",
     "engagements": [
         ("Backups and recovery of research data", "process", "Research data storage", "Ransomware reaching research storage is the security office's worst open risk, and a full restore has not been tested in two years.", 230, 180, None),
         ("Clinical systems: access and change", "scope", "Clinical systems", "Its readiness against the HIPAA Security Rule is the lowest of the four scopes.", 200, 150, None),
         ("Trial data vendor oversight", "third_party", "Castellan Trial Systems", "Tier 1 vendor holding identifiable trial data; its due diligence found restores untested.", 120, 60, None),
         ("Travel and expense claims", "unit", "Finance", "Asked for by the CFO after a new card program.", 90, 60, "Moved to next year when the card program was delayed."),
     ]},
    {"name": "Internal audit plan, next year", "from": -121, "to": -485, "drafted": 10,
     "approved": None, "by": None, "note": None,
     "summary": "In draft for the committee's December meeting.",
     "engagements": [
         ("Medication dispensing controls", "process", "Medication dispensing", "Moved up by audit after two near misses; critical to patient safety.", -140, -180, None),
         ("Travel and expense claims", "unit", "Finance", "Carried from this year's plan.", -200, -230, None),
     ]},
]  # fmt: skip

# Engagements from this year's plan as they were carried out: when each moved on (days ago),
# its steps (title, what was to be done, what was done, what was found, who prepared it, who
# signed it off, and a review note with its answer), and its report.
ENGAGEMENTS = [
    {"name": "Backups and recovery of research data", "lead": "auditor", "members": ["auditor2"],
     "start": 230, "fieldwork": 221, "reporting": 186, "reported": 178,
     "scope": "Whether research storage is backed up, whether a restore works, and who can delete backups. The twelve months before fieldwork.",
     "steps": [
         ("Backups are taken as scheduled", "Compare the backup schedule with the job history for a sample of nights.",
          "Compared the schedule with the job history for the first night of each month.",
          "Every scheduled backup ran. Two finished with no data, and nobody noticed.", "auditor2", "auditor",
          ("Which job history: the console's, or the exported logs?", "The exported logs, kept with the job reports.")),
         ("A restore has been tested", "Ask for the last full restore test and its result.",
          "Asked Research Computing for restore tests in the period, and read the one report given.",
          "The last full restore of research storage was two years ago. Partial restores are done on request.", "auditor2", "auditor", None),
         ("Deleting backups is limited", "List who can delete or expire backups, and check each against their job.",
          "Listed the backup administrators and compared them with Research Computing's staff list.",
          "Five people can delete backups; one left the institute in the spring.", "auditor", "auditor2", None),
     ],
     "requests": [
         # asked (days ago), by, of, what, due (days after asking), answered (days ago) and
         # the answer, accepted (days ago)
         (219, "auditor2", "it_mgr", "The backup job history for research storage for the last twelve months, as exported from the backup console.", 10,
          (214, "Exported the job history for every night of the twelve months and attached the summary report."), 212),
     ],
     "findings": [
         # raised (days ago), by, name, what was found, severity, owner, the action plan
         # (title, due days after raising, done days ago), and its closure (proposed days ago,
         # what was done, why it happened, confirmed by audit days ago)
         (188, "auditor2", "Empty backups go unnoticed", "Two of twelve sampled nightly backups of research storage finished with no data, and nobody was told.", "high", "it_mgr",
          [("Alert the on-call engineer when any backup finishes with no data", 25, 152)],
          (149, "Every backup job now alerts the on-call engineer if it finishes with no data; tested by emptying a job on purpose.", "technology", 141)),
         (188, "auditor", "No full restore of research storage in two years", "Partial restores are done on request, but research storage has not been restored in full since the cluster moved.", "moderate", "it_mgr",
          [("Restore research storage in full to the test system, and record how long it takes", 70, None)], None),
     ],
     "summary": "Backups of research storage are taken as scheduled, but two empty backups went unnoticed, a full restore has not been tested in two years, and one person who has left could still delete backups. Management has agreed to check every backup, test a full restore this year, and review backup administrators each quarter.",
     "opinion": "needs_improvement"},
    {"name": "Clinical systems: access and change", "lead": "auditor2", "members": ["auditor"],
     "start": 198, "fieldwork": 190, "reporting": 152, "reported": 146,
     "scope": "Who has access to the clinic's systems, and how changes to them are approved. The six months before fieldwork.",
     "steps": [
         ("Access is approved", "For a sample of accounts made in the period, find the approval.",
          "Found the approval for each of twenty-five accounts made in the period.",
          "Every account was approved before it was made.", "auditor", "auditor2", None),
         ("Changes are approved and tested", "For a sample of changes, find the approval and the test.",
          "Read fifteen changes to the electronic health record and their tickets.",
          "Each change was approved and tested; one emergency change was approved the next day, as the procedure allows.", "auditor", "auditor2", None),
     ],
     "requests": [], "findings": [],
     "summary": "Access to the clinic's systems is approved before it is given, and changes are approved and tested as the procedure says.",
     "opinion": "effective"},
    {"name": "Trial data vendor oversight", "lead": "auditor", "members": ["auditor2"],
     "start": 118, "fieldwork": 110, "reporting": None, "reported": None,
     "scope": "How Clinical Research and the security office oversee Castellan Trial Systems: due diligence, the agreement, and findings.",
     "steps": [
         ("Due diligence is done and read", "Read the last review and its conclusion.",
          "Read the standard due diligence review and the reviewer's conclusion.",
          "The review was answered and concluded with conditions; one finding is open.", "auditor2", "auditor", None),
         ("The agreement covers what is shared", "Compare what the vendor holds with what its agreement covers.",
          "Compared the trial data the vendor hosts with its services agreement.",
          "The agreement covers the data it holds.", "auditor2", None,
          ("Is the business associate agreement needed too, for the clinic's patients?", None)),
         ("Findings are followed up", "Follow each finding to its actions and dates.", None, None, None, None, None),
     ],
     "requests": [
         (108, "auditor", "ciso", "The conditions set when Castellan's due diligence review was concluded, and how each has been followed up.", 10,
          (101, "One condition: a tested restore before the next trial starts. It is an open finding with the vendor, due next month; the report we rely on is attached."), None),
         (20, "auditor2", "ciso", "The business associate agreement with Castellan Trial Systems, or the reason none is needed.", 14, None, None),
     ],
     "findings": [],
     "summary": None, "opinion": None},
]  # fmt: skip

# Outside access: the external auditors, relying on internal audit's backups work this year;
# and the trial sponsor's monitor, who had the trial data platform for a fortnight last spring.
OUTSIDE = [
    {"name": "Dana Reyes", "organization": "Halvard & Associates, the external auditors",
     "purpose": "Relying on internal audit's work on backups for the year-end audit.",
     "kind": "engagement", "ref": "AUD-0001", "days": 30},
    {"name": "Sam Ortiz", "organization": "Verdance Therapeutics, the trial's sponsor",
     "purpose": "The sponsor's annual review of how trial data is kept.",
     "kind": "scope", "ref": "SCP-0001", "days": 14},
]  # fmt: skip

# Business impact: what the critical processes cannot afford to lose (days ago, process, impacts
# over time, back within hours, loses at most hours, the least it needs), and what the systems
# they rely on can deliver (days ago, system, back within, loses at most, what it rests on).
IMPACT = [
    (60, "Research data storage", [("4h", 2), ("1d", 3), ("3d", 4), ("1w", 5)], 72, 24,
     "The storage administrators, the backup service, and the cluster network."),
    (55, "Medication dispensing", [("4h", 4), ("1d", 5)], 4, 1,
     "Two pharmacists, the dispensing cabinets or the paper override procedure, and the clinical record."),
    (50, "Clinical laboratory testing", [("4h", 3), ("1d", 4), ("3d", 5)], 8, 1,
     "The laboratory information system, the chemistry analyzers, and their technologists."),
    (45, "Sequencing service", [("1d", 2), ("3d", 3), ("1w", 4), ("1m", 5)], 168, 24,
     "One sequencer, the sample manager, and research storage."),
]  # fmt: skip
CAPABILITY = [
    (58, "Research storage", 24, 24, "Replicated to the second data center; failed over in a test in June."),
    (58, "Backup service", 120, 24, "Partial restores only; a full restore of research storage was last done two years ago and took five days."),
    (52, "Dispensing cabinets", 2, 0, "Each cabinet runs on its own when the network is down; tested in the spring drill."),
    (52, "Clinical record system", 4, 0, "The supplier's hosted service: four hours and no loss, in the contract."),
    (48, "Laboratory information system", 12, 1, "Restored to the standby server in last year's exercise in twelve hours."),
    (44, "Genomics sample manager", 24, 4, "Nightly backups, restored on request."),
]  # fmt: skip

# Incidents, near misses, and concerns, each reported some days ago by one of the cast or by
# someone without a name (None), triaged, written about, and perhaps closed. A step's first
# number is days ago; a message is (days ago, who wrote it or "reporter", shared, what).
# Reporting without a name was opened this many days ago, and the demo's reports made that
# way take these codes, so that the follow-up page can be shown.
ANONYMOUS_OPENED = 200
INCIDENTS = [
    {"by": "member", "on": 96, "kind": "near_miss", "unit": "BIO", "occurred": 96, "where": "Email",
     "name": "Email asking me to confirm my mailbox password",
     "summary": "An email that looked as if it came from IT asked me to sign in to keep my "
                "mailbox. The link went to a site that was not ours. I did not sign in, and I "
                "forwarded it to the security team.",
     "triage": (96, "assess1", "security", "low", [("system", "Email and collaboration")],
                "sec_mgr"),
     "said": [(96, "sec_mgr", True, "Thank you for sending it on. We blocked the sender and "
                                    "took the same email out of 46 other mailboxes.")],
     "closed": (95, "sec_mgr", "Sender blocked and 46 copies removed. The sign-in records show "
                               "that nobody entered a password on the false site.")},
    {"by": "rc_dir", "on": 61, "kind": "near_miss", "unit": "RC", "occurred": 61,
     "where": "Compute cluster, login node 2",
     "name": "Ransomware stopped on a cluster login node",
     "summary": "Endpoint protection quarantined a file that began encrypting a user's scratch "
                "directory on login node 2. The account had signed in from an unusual country "
                "an hour before. We took the node out of service.",
     "triage": (61, "ciso", "security", "high",
                [("system", "Compute cluster"), ("system", "Research storage"),
                 ("risk", "Ransomware reaching research storage")], "sec_mgr"),
     "said": [(61, "sec_mgr", False, "The account's password was reused from a breached site. "
                                     "Reset, sessions revoked, and the node rebuilt from its "
                                     "image."),
              (60, "sec_mgr", True, "The node is back in service. Nothing reached research "
                                    "storage: its snapshots were checked file by file.")],
     "learned": (59, "ciso", {
         "realized": ["Ransomware reaching research storage",
                      "Staff accounts taken over through stolen passwords"],
         "failed": ["Second factor at sign-in"],
         "held": ["Protection against malicious software", "Backups tested by restoring"],
         "root_cause": "design",
         "lessons": "The cluster's login nodes were outside the second-factor rollout, so a "
                    "password reused from a breached site was enough. Endpoint protection and "
                    "the tested snapshots held. Every system that faces the internet is now on "
                    "the second-factor list, and the list is checked each quarter.",
     }),
     "losses": [(59, "sec_mgr", "response", 6400, "Forty hours of the security team and "
                                                   "the cluster administrators."),
                (58, "sec_mgr", "recovery", 1800, "Rebuilding the node and checking the "
                                                  "snapshots.")],
     "closed": (58, "sec_mgr", "Contained on one node; no data lost or taken. Multi-factor "
                               "sign-in is now required on the cluster's login nodes.")},
    {"by": "sp_mgr", "on": 23, "kind": "incident", "unit": "CR", "occurred": 24,
     "where": "Email to a trial sponsor",
     "name": "Spreadsheet with participant names sent to a sponsor",
     "summary": "A monthly enrollment report went to the sponsor with a tab that still had "
                "participants' names and dates of birth. It should have had study numbers only.",
     "triage": (23, "assess2", "privacy", "high", [("system", "Electronic data capture")],
                "assess2"),
     # Whether it must be notified: still being decided, and the clock is running.
     "breach": (22, "assess2", {
         "information": ["participant", "personal"], "people": 38, "most_in_one_state": 31,
         "factors": {
             "nature": ("moderate", "Names and dates of birth, with the study the person is in."),
             "recipient": ("low", "The sponsor, bound by the clinical trial agreement."),
             "acquired": ("high", "The sponsor's coordinator opened the file."),
             "mitigated": ("moderate", "Deleted, and confirmed in writing; backups take a week to "
                                       "roll off."),
         },
         "conclusion": "undecided",
         "regimes": [{"key": "contract", "name": "The sponsor's clinical trial agreement", "days": 5},
                     {"key": "state", "name": "Washington", "days": 30}],
     }),
     "notified": [(21, "assess2", "contract:The sponsor's clinical trial agreement", "party",
                   "The sponsor's privacy office, by email", "Email")],
     "said": [(22, "assess2", False, "The sponsor's privacy office confirmed in writing that "
                                     "the file was deleted from the inbox and from backups."),
              (22, "assess2", True, "Thank you for reporting it the same day. We are working "
                                    "out with the privacy office whether anyone must be told.")]},
    {"by": None, "on": 15, "kind": "concern", "unit": None, "occurred": None,
     "where": "Infusion, third floor",
     "code": "7KQ2M-PX4RT-9WZ3H-C6V8N",
     "name": "Shared password on the infusion pumps' admin console",
     "summary": "The pump management console at the nurses' station is signed in with one "
                "account that everyone uses. Its password is on a note under the keyboard.",
     "triage": (14, "ciso", "security", "moderate", [("system", "Infusion pumps")], "sec_mgr",
                "INF"),
     "said": [(13, "sec_mgr", True, "Thank you. Is it the console at the nurses' station by "
                                    "the elevators, or the one in the medication room?"),
              (12, "reporter", True, "By the elevators. The note has been there since the "
                                     "summer.")],
     "issue": (11, "ciso", {
         "name": "Infusion pump console signed in with a shared account", "severity": "high",
         "summary": "Everyone at the nurses' station uses one account, and its password is on "
                    "a note. Each nurse needs their own sign-in, through single sign-on.",
         "subjects": ["Compromised account: Infusion therapy"], "owner": "it_mgr"})},
    # A restricted case: known only to those named on it, not to the pharmacy's leaders.
    {"by": "pharm_mgr", "on": 9, "kind": "concern", "unit": "PHARM", "occurred": 10,
     "where": "Pharmacy, the controlled substance vault",
     "name": "Controlled substance counts signed without counting",
     "summary": "On two night shifts this month the end-of-shift count was signed by both "
                "witnesses, but only one of them was in the vault. The cabinet's own log shows "
                "a single badge both times.",
     "triage": (9, "cro", "compliance", "high", [("system", "Dispensing cabinets")], "assess2"),
     "restrict": (9, "cro", []),
     "said": [(8, "assess2", False, "The cabinet's access log for the month is exported and "
                                    "kept with the case, not on the shared drive."),
              (8, "assess2", True, "Thank you for raising this. Only the people named on this "
                                   "case can see it. We may ask you more here.")]},
    {"by": "gen_mgr", "on": 6, "kind": "incident", "unit": "GEN", "occurred": 7,
     "where": "A parked car, overnight",
     "name": "Laptop stolen from a car",
     "summary": "A core laptop was taken from my car overnight. It had the sample manager's "
                "export of last month's runs on it, with sample identifiers but no names.",
     "triage": (6, "assess1", "security", "high",
                [("system", "Endpoint management"), ("system", "Genomics sample manager")],
                "sec_mgr"),
     "breach": (5, "sec_mgr", {
         "information": ["participant"], "people": 212, "secured": True,
         "factors": {"nature": ("low", "Sample identifiers, with no names or dates of birth.")},
         "conclusion": "no_notification",
         "rationale": "The disk was encrypted and the laptop was locked; endpoint management "
                      "shows the encryption key was never used after it was taken. It is not a "
                      "breach of unsecured information.",
         "regimes": [{"key": "contract", "name": "The genomics data use agreement", "days": 10}],
     }),
     "losses": [(4, "sec_mgr", "recovery", 2150, "A replacement laptop, set up.")],
     "learned": (4, "ciso", {"realized": [], "failed": [],
                                "held": ["Devices and storage encrypted"]}),
     "said": [(6, "sec_mgr", False, "Endpoint management shows the disk was encrypted and the "
                                    "laptop last checked in at 7:12 pm. Remote wipe sent."),
              (5, "sec_mgr", True, "Thank you. Please file a police report and send us its "
                                   "number when you have it.")]},
    {"by": None, "on": 2, "kind": "concern", "unit": None, "occurred": None,
     "where": "Imaging Core, the back door",
     "code": "4DHN8-T2WQ6-MB9KX-3RF7P",
     "name": "Visitors let into the imaging core without a badge",
     "summary": "Visitors are being let in through the back door without signing in or wearing "
                "a badge, and are left alone with the microscopes."},
    {"by": "bio_mgr", "on": 1, "kind": "incident", "unit": "BIO", "occurred": 1,
     "where": "Freezer room B",
     "name": "Freezer alarm did not page anyone overnight",
     "summary": "Freezer 12 rose to minus 62 at 2 am. The monitor showed the alarm, but no page "
                "reached whoever was on call. The morning shift moved its boxes to the spare."},
]  # fmt: skip

# Privacy impact assessments: a campaign started some days ago over every process and system
# that handles restricted information; some answered, one reviewed. Answers by system name.
PRIVACY_CAMPAIGN = 40
PRIVACY_ANSWERS = {
    "Scheduling system": (36, {
        "information": ["contact", "health"], "whose": ["patients"], "how_many": 18000,
        "purpose": "Booking appointments and sending reminders.", "basis": "care",
        "least": True, "shared": True, "shared_with": "The supplier hosts it.",
        "agreement": "business_associate", "access": True,
        "retention": "Seven years after the last visit, then deleted.", "deidentified": "cannot",
        "harms": "Someone could learn that a person is a patient here.",
        "reduced": "Only clinic staff sign in, with the organization's single sign-on.",
    }, "ciso", "Nothing to change. Reviewed with the clinic's privacy lead."),
    "Survey platform": (30, {
        "information": ["contact", "health", "research"], "whose": ["participants"],
        "how_many": 2600, "purpose": "Population study questionnaires.", "basis": "protocol",
        "least": False, "least_why": "It keeps email addresses after the survey closes.",
        "shared": True, "shared_with": "The survey supplier hosts it.", "agreement": "none",
        "access": True, "retention": "Until the study ends.", "deidentified": "partly",
        "harms": "Participants' answers about their health could be linked to their email.",
        "reduced": "Answers are exported with study numbers only.",
    }, None, None),
}  # fmt: skip

# Continuity plans: documents of their own kind, approved and published, the processes each
# restores, and their exercises. Days ago for each step; an exercise's finding is an issue.
CONTINUITY_PLANS = [
    {"name": "Research data storage continuity plan", "unit": "RC", "by": "rc_dir",
     "approver": "cio", "written": 150, "published": 140,
     "summary": "Keeping research computing's storage going, or bringing it back, when the "
                "primary data center is lost or the storage is encrypted.",
     "body": """# When research storage is lost

## First hour
1. The on-call storage administrator declares an outage and calls the **security operations
   manager** if encryption or tampering is suspected.
2. Stop jobs that write to storage. Do not power off encrypted volumes: they are evidence.
3. Tell the core directors that research storage is down, and how long it is expected to be.

## Bringing it back
- Fail over to the second data center's replica if it is clean.
- If the replica is not clean, restore from the offline copy, newest first: lab shares,
  then project data, then scratch.
- Check each restore against its snapshot list before anyone is let back in.

## Telling people
Every four hours, the director of research computing writes to the core directors and the
lab heads: what is back, what is next, and when.
""",
     "covers": ["Research data storage"],
     "exercises": [
         {"days": 34, "by": "ciso", "kind": "tabletop", "result": "partly", "achieved": 120,
          "scenario": "Ransomware encrypts the primary storage and its replica on a Friday night.",
          "participants": "Research computing, security operations, two core directors.",
          "outcome": "Restoring everything from the offline copy took five days on paper, "
                     "against the three days research needs. Lab shares came back first, "
                     "as planned.",
          "finding": {"name": "A full restore of research storage takes five days",
                      "severity": "high", "owner": "rc_dir",
                      "summary": "The exercise found that a restore from the offline copy "
                                 "takes five days; research needs storage back in three."}},
     ]},
    {"name": "Medication dispensing downtime plan", "unit": "PHARM", "by": "pharm_mgr",
     "approver": "clinic_lead", "written": 120, "published": 112,
     "summary": "Dispensing medication when the cabinets or the network are down.",
     "body": """# When the dispensing cabinets are down

1. Switch the cabinets to their own override mode; each runs without the network.
2. Pharmacists dispense from the paper override log, two signatures for each dose.
3. When the cabinets are back, enter every override within four hours.
""",
     "covers": ["Medication dispensing"],
     "exercises": [
         {"days": 70, "by": "pharm_mgr", "kind": "simulation", "result": "met", "achieved": 1,
          "scenario": "The network to the pharmacy is cut for four hours during the day shift.",
          "participants": "The pharmacy team and the infusion nurses on shift.",
          "outcome": "Override mode came up in minutes; every dose was logged and entered "
                     "within the hour after."},
     ]},
]  # fmt: skip

# Sites: the places work depends on, what relies on each, and how soon work goes on again
# after one is lost. name, unit, kind, criticality, address, processes, systems (by key),
# then (days ago, hours, what that rests on). And a third party's own recovery: (days ago,
# third party key, hours, information lost, what it rests on).
SITES = [
    ("Primary data center", "IT", "data_center", "critical", "Administration building, level B1",
     ["Research data storage"], ["storage", "cluster", "enclave", "servers", "network"],
     (58, 48, "Fail over to the second data center: storage was tested in March; the cluster "
              "has no warm standby, and is rebuilt there by hand.")),
    ("Second data center", "IT", "data_center", "high", "Colocation facility, Northgate",
     [], ["backup"],
     (58, 24, "Its own power and cooling; the backup service moves to the primary if it is "
              "lost.")),
    ("Freezer rooms A and B", "BIO", "storage", "critical", "Research building, level 1",
     ["Specimen storage and retrieval"], ["freezers", "monitor"],
     (52, 4, "The spare freezers on level 2 take the boxes; moved in four hours in the last "
             "exercise.")),
    ("Clinic building", "CLIN", "clinic", "critical", "Northmere Research Clinic",
     ["Medication dispensing", "Infusion therapy", "Clinical laboratory testing"],
     ["cabinets", "pumps", "lis", "analyzers"],
     (50, 24, "The outpatient unit on the second campus takes infusions and dispensing within "
              "a day; nothing is set up there to start sooner.")),
]  # fmt: skip
THIRD_PARTY_RECOVERY = [
    (48, "labref", 24, 0, "Its contract: results within a day of a sample arriving."),
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
    # control (library key), the unit that runs it, who answers for it, how well it is known
    # to work unless a storyline has already said, and where it stands if not yet in place
    "controls": [
        ("second_factor", "IT", "Identity team", "effective", None),
        ("privileged_access", "IT", "Identity team", "effective", None),
        ("access_removed_on_leaving", "IT", "Identity team", "effective", None),
        ("access_approved", "IT", "Identity team", "effective", None),
        ("unique_accounts", "IT", "Identity team", "effective", None),
        ("backups_tested", "IT", "Infrastructure team", "partly", None),
        ("patching", "IT", "Infrastructure team", "effective", None),
        ("asset_inventory", "IT", "Infrastructure team", "effective", None),
        ("physical_access", "IT", "Infrastructure team", "effective", None),
        ("secure_configuration", "IT", "Infrastructure team", "never", "partly"),
        ("disaster_recovery", "IT", "Infrastructure team", "never", "planned"),
        ("network_segmentation", "IT", "Network team", "partly", None),
        ("remote_access", "IT", "Network team", "effective", None),
        ("encryption_in_transit", "IT", "Network team", "effective", None),
        ("encryption_at_rest", "IT", "Endpoint team", "effective", None),
        ("session_lock", "IT", "Endpoint team", "effective", None),
        ("media_disposal", "IT", "Endpoint team", "effective", None),
        ("change_review", "IT", "Change board", "effective", None),
        ("access_reviewed", "SEC", "Security operations", "effective", None),
        ("malware_protection", "SEC", "Security operations", "effective", None),
        ("logging_monitoring", "SEC", "Security operations", "partly", None),
        ("log_protection", "SEC", "Security operations", "effective", None),
        ("vulnerability_scanning", "SEC", "Security operations", "effective", None),
        ("incident_response", "SEC", "Security operations", "effective", None),
        ("incident_reporting", "SEC", "Security operations", "effective", None),
        ("security_training", "SEC", "Security awareness lead", "partly", None),
        ("supplier_assessed", "SEC", "Security assurance", "effective", None),
        ("security_risk_assessment", "SEC", "Security assurance", "effective", None),
        ("security_testing", "SEC", "Security assurance", "effective", None),
        ("security_policy", "SEC", "Chief information security officer", "effective", None),
        ("security_roles", "SEC", "Chief information security officer", "effective", None),
        ("security_oversight", "SEC", "Chief information security officer", "effective", None),
        ("data_classified", "CMPL", "Privacy office", "effective", None),
        ("agreements_in_place", "LEGAL", "Contracts counsel", "effective", None),
        ("environmental_monitoring", "FAC", "Building operations", "effective", None),
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
                  "access_removed_on_leaving", "privileged_access", "unique_accounts",
                  "session_lock", "encryption_in_transit", "log_protection",
                  "vulnerability_scanning", "incident_reporting", "disaster_recovery",
                  "media_disposal", "security_policy", "security_roles",
                  "security_risk_assessment", "security_testing"],
    # control, where the clinic's part stands, what the clinic does
    "shared": [
        ("access_reviewed", "in_place",
         "Clinic managers review who can open the clinical record each quarter, and Security reviews the rest."),
        ("security_training", "partly",
         "The clinic adds a module on patient privacy. A third of agency staff have not yet taken it."),
        ("access_approved", "in_place",
         "A clinic manager approves each request to open the clinical record, and the identity team grants it."),
    ],
    "own": [
        ("downtime_procedures", "in_place", "Nurse managers",
         "Each area keeps paper forms and a downtime box, and practices in spring and autumn."),
        ("physical_access", "in_place", "Clinic operations",
         "Clinical areas open by badge, screens face away from waiting areas, and the records room is locked."),
        ("agreements_in_place", "in_place", "Clinic operations",
         "Every supplier that handles patient records has a business associate agreement, held by Legal and listed here."),
        ("personnel_screening", "in_place", "Clinic operations",
         "Clinic staff are screened before they start and sign the rules for using the clinical record."),
    ],
    "excluded": [
        (["164.308(a)(4)(ii)(A)"], "Northmere is not, and does not include, a health care clearinghouse."),
        (["164.314(b)(1)", "164.314(b)(2)", "164.314(b)(2)(i)", "164.314(b)(2)(ii)",
          "164.314(b)(2)(iii)", "164.314(b)(2)(iv)"],
         "These apply to group health plans. The clinic is a provider, not a plan."),
        (["164.306(b)(1)", "164.306(b)(2)(i)", "164.306(b)(2)(ii)", "164.306(b)(2)(iii)",
          "164.306(b)(2)(iv)", "164.306(c)", "164.306(d)(1)", "164.306(d)(2)"],
         "These say how the rule is to be read. What they ask is asked in full by the standards "
         "and specifications themselves."),
        (["164.308(b)(2)", "164.314(a)(2)(iii)"],
         "These bind a business associate and its subcontractors. The clinic is a covered entity."),
        (["164.314(a)(2)(ii)"],
         "This is for arrangements between government bodies. Northmere is not one."),
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
    "inherited": ["second_factor", "network_segmentation", "malware_protection", "incident_response",
                  "unique_accounts", "session_lock", "encryption_in_transit", "remote_access",
                  "log_protection", "vulnerability_scanning", "incident_reporting",
                  "security_training", "access_removed_on_leaving", "media_disposal",
                  "change_review", "supplier_assessed", "security_policy",
                  "security_risk_assessment", "security_testing"],
    "shared": [
        ("patching", "in_place",
         "Research Computing patches the enclave's own hosts on the institute's schedule; IT patches what is beneath them."),
        ("logging_monitoring", "planned",
         "The enclave's hosts do not yet send their logs to security monitoring. Due with the next storage refresh."),
        ("backups_tested", "partly",
         "The enclave is backed up to its own encrypted set. A full restore has not been tried."),
        ("secure_configuration", "in_place",
         "The enclave's hosts are built from the institute's standard, with the repository's additions on top."),
        ("asset_inventory", "in_place",
         "The administrators keep the enclave's own list of hosts and approved software, checked each quarter."),
        ("encryption_at_rest", "in_place",
         "The enclave's storage is encrypted with keys the two administrators hold."),
    ],
    "own": [
        ("privileged_access", "in_place", "Enclave administrators",
         "Two named administrators, separate accounts, and every session recorded."),
        ("access_approved", "in_place", "Data steward",
         "The data steward approves each of the twelve users against the repository's certification."),
        ("data_classified", "in_place", "Data steward",
         "Everything in the enclave is controlled-access data, marked as such, and nowhere else."),
    ],
    "excluded": [],
}  # fmt: skip

# Risk analyses: a scope taken against kinds of threat. "walked" is how much of it has been
# worked through, "pace" the days between one thing and the next.
ANALYSES = [
    {
        "name": "Clinic systems, security risk analysis",
        "scope": SCOPE_CLINIC["name"], "categories": ["availability", "confidentiality"],
        "summary": "The yearly analysis the security rule asks for. Each system and service "
        "in the clinic's boundary is taken against the ways it could be lost or exposed. "
        "Led by security assurance with the clinic's system owners.",
        "began": 150, "walked": 1.0, "pace": 0.4, "raises": 3,
        "conclusion": "Three risks were not on the register and now are, each with the owner "
        "of the system it concerns. Several risks already there were looked at again against "
        "systems they did not name, and now name them. Paper records and the building were "
        "out of scope and are for the facilities analysis.",
    },
    {
        "name": "Data enclave, threat analysis before the next data release",
        "scope": SCOPE_ENCLAVE["name"], "categories": ["confidentiality", "research_security"],
        "summary": "Asked for by the data access committee before controlled-access data from "
        "a new study is admitted. To be finished before the committee meets.",
        "began": 16, "walked": 0.5, "pace": 1.0, "raises": 1,
    },
]  # fmt: skip
ANALYSIS_NOTES = {
    "covered": "The risk already on the register covers this here as well.",
    "again": "It covers this, but its rating was made before this system was in the picture.",
    "raised": "Nothing on the register covers this here. Raised for its owner to assess.",
    "not_applicable": [
        "It holds no data of this kind.",
        "It is not reachable from outside the unit's network.",
        "The service is run for us; this is the supplier's to manage and is in the contract.",
        "Looked at with its owner: the way this would happen does not exist here.",
    ],
}

# Policy documents. Each has its words, who adds it ("by": a cast key, or a unit's steward
# when "by" names a unit), who approves its versions, and its history: the days ago each
# version was published, with a list of changes from the one before; reviews that kept it as
# it was; and what is being written now. All of it is invented.
INFOSEC_V1 = """# Information security policy

## Purpose

Northmere holds information that patients, research participants, funders, and partners have trusted it with. This policy says how that information, and the systems that hold it, are protected.

## Who it applies to

Everyone who works at Northmere or studies here, contractors and visiting researchers, and anyone else who uses Northmere's systems or handles its information.

## What we require

- Information is classified, and protected according to its class (see the data classification standard).
- Access is given for a purpose, to named people, and removed when the purpose ends.
- Restricted information is kept only in systems approved for it.
- Systems are kept up to date, and weaknesses are found and fixed.
- Anyone who suspects an incident reports it at once to the Information Security office.

## Roles

| Role | Responsibility |
|---|---|
| Chief Information Security Officer | Keeps this policy and the standards beneath it, and reports on them to leadership |
| System owners | Make sure their systems meet the standards |
| Everyone | Follows this policy, and reports what looks wrong |

## Exceptions

An exception to this policy, or to a standard beneath it, is asked for in writing, says what makes up for it, and ends on a date. Exceptions are decided by the Chief Information Security Officer.

## Review

This policy is reviewed every year, and sooner if the law or the organization changes.
"""

INFOSEC_V2 = [
    (
        "- Systems are kept up to date, and weaknesses are found and fixed.",
        "- Systems are kept up to date, and weaknesses are found and fixed in the times the vulnerability management standard sets.",
    ),
    (
        "- Anyone who suspects an incident reports it at once to the Information Security office.",
        "- Anyone who suspects an incident reports it at once to the Information Security office, and does not try to investigate it alone.\n- Suppliers who hold Northmere's information agree to protect it as this policy does.",
    ),
]
INFOSEC_V3 = [
    (
        "Exceptions are decided by the Chief Information Security Officer.",
        "Exceptions are decided by the Chief Information Security Officer, and those that bear on patient or participant information also by the privacy officer.",
    ),
    (
        "## Review\n",
        "## Training\n\nEveryone completes security awareness training when they join and every year after.\n\n## Review\n",
    ),
]

AUP_V1 = """# Acceptable use policy

## Purpose

Northmere's computers, networks, and accounts are provided for its work. This policy says what using them well looks like.

## You may

- Use Northmere systems for your work, and for occasional personal use that does not get in its way.
- Use approved collaboration tools to work with colleagues and partners.

## You must not

- Share your account, or use anyone else's.
- Store restricted information on a personal device or an unapproved service.
- Install software that has not been approved for your role.
- Try to get around a security control.

## Monitoring

Northmere may monitor the use of its systems to keep them secure, within the law and its privacy notice.

## If something goes wrong

Report a lost device, a suspicious message, or anything that looks wrong to the help desk at once.
"""
AUP_V2 = [
    (
        "- Use approved collaboration tools to work with colleagues and partners.",
        "- Use approved collaboration tools to work with colleagues and partners.\n- Use generative tools that Northmere has approved, and never paste restricted information into one that it has not.",
    ),
    (
        "Report a lost device, a suspicious message, or anything that looks wrong to the help desk at once.",
        "Report a lost device, a suspicious message, or anything that looks wrong to the help desk at once. Reporting a mistake is never held against you.",
    ),
]

AUP_V3 = [
    (
        "- Store restricted information on a personal device or an unapproved service.",
        "- Store restricted information on a personal device or an unapproved service.\n- Use a personal email or file-sharing account for Northmere's work.",
    ),
]

ACCESS_V1 = """# Access control standard

This standard puts the information security policy into practice for access to systems.

## Accounts

1. Every account belongs to one named person.
2. Accounts are created only when a manager asks, for a stated purpose.
3. Shared and generic accounts are not allowed, except service accounts with a named owner.

## Privileges

- Access is the least a person needs for their work.
- Administrator rights are held in a separate account, used only for administration.
- Privileged access is reviewed every quarter by the system owner.

## Leavers and movers

- Access is removed within two working days of someone leaving.
- When someone changes role, access they no longer need is removed within ten working days.

## Reviews

System owners review who has access to their systems at least twice a year, and keep the record.
"""

PASSWORDS_V1 = """# Password and authentication standard

## Passwords

- At least 12 characters, with no forced complexity rules.
- Checked against lists of known breached passwords when set.
- Changed only when there is reason to think it is known to someone else.

## Second factor

- Required for remote access and for email.
- Required for every administrator account.

## Service accounts

Service accounts use long random secrets, kept in the approved vault and changed when someone who knew them leaves.
"""
PASSWORDS_V2 = [
    (
        "- Required for remote access and for email.",
        "- Required for every account that can be reached from outside Northmere's network.",
    ),
    (
        "- Required for every administrator account.",
        "- Required for every administrator account, using a phishing-resistant method.\n- Codes sent by text message are no longer accepted for new enrolments.",
    ),
]

CLASSIFICATION_V1 = """# Data classification standard

Every body of information at Northmere has one of four classes. Its owner says which.

| Class | What it is | Examples |
|---|---|---|
| Public | Meant to be shared | Published papers, the public website |
| Internal | For Northmere's work, harmless if seen | Meeting notes, internal procedures |
| Confidential | Would cause harm if seen by the wrong people | Unpublished results, contracts, staff records |
| Restricted | Protected by law or agreement | Patient records, identifiable participant data, controlled-access genomic data |

## Handling

- Restricted information is kept only in systems approved for it, encrypted in storage and in transit.
- Confidential information is shared only with those who need it.
- When in doubt, treat information as the higher class and ask the privacy office.
"""

ENCRYPTION_V1 = """# Encryption standard

## In storage

- Laptops and portable media are encrypted with the approved full-disk encryption.
- Restricted information in databases and file shares is encrypted at rest.

## In transit

- Restricted and confidential information is sent only over encrypted connections.
- Email holding restricted information is sent with the approved secure-mail option.

## Keys

Keys are kept apart from the information they protect, by the system's administrators, and are rotated at least every two years.
"""

VULN_V1 = """# Vulnerability management standard

## Finding weaknesses

- Systems on Northmere's network are scanned at least monthly.
- Systems reachable from the internet are scanned weekly and tested by an outside firm each year.

## Fixing them

| Severity | Fixed within |
|---|---|
| Critical | 15 days |
| High | 30 days |
| Medium | 90 days |
| Low | At the next planned change |

A weakness that cannot be fixed in time needs an exception, with what makes up for it until it is.
"""

INCIDENT_V1 = """# Incident response procedure

## When you suspect an incident

1. Stop, and do not try to investigate on your own.
2. Call the help desk, and say it may be a security incident.
3. Write down what you saw, and when.

## The response team

The Information Security office leads the response, with IT and, when personal information may be involved, the privacy office.

## Steps

1. Contain: isolate what is affected.
2. Assess: what happened, what was reached, whose information.
3. Recover: restore from clean backups.
4. Learn: a review within two weeks, with actions and owners.
"""
INCIDENT_V2 = [
    (
        "1. Contain: isolate what is affected.",
        "1. Contain: isolate what is affected, and keep its logs.",
    ),
    (
        "The Information Security office leads the response, with IT and, when personal information may be involved, the privacy office.",
        "The Information Security office leads the response, with IT and, when personal information may be involved, the privacy office. Out of hours, the on-call security engineer is reached through the help desk.",
    ),
]
INCIDENT_V3 = [
    (
        "2. Assess: what happened, what was reached, whose information.",
        "2. Assess: what happened, what was reached, whose information.\n3. Decide whether anyone must be told: the privacy office decides within 24 hours of learning that personal information may be involved.",
    ),
    ("3. Recover: restore from clean backups.", "4. Recover: restore from clean backups."),
    (
        "4. Learn: a review within two weeks, with actions and owners.",
        "5. Learn: a review within two weeks, with actions and owners, recorded as issues in RiskWren.",
    ),
]

REMOTE_V1 = """# Working away from the office

Some advice for working securely at home and when travelling.

- Use the VPN before reaching internal systems.
- Lock your screen when you step away, even at home.
- Keep work on Northmere devices; do not print restricted information at home.
- On a shared network, assume someone else can see what is not encrypted.
"""

RDM_LINES = [
    "Research data management policy",
    "",
    "1. Every research project names a data steward when it begins.",
    "2. Research data is kept in Research Computing's managed storage, never only on",
    "   a laptop or an instrument computer.",
    "3. Identifiable participant data is kept in the controlled-access enclave.",
    "4. Data is kept for at least seven years after publication, or longer if the",
    "   funder or the agreement under which it was received requires.",
    "5. Data shared outside Northmere is shared under a data use agreement.",
    "",
    "Approved by the Chief Scientific Officer.",
]

DOCUMENTS = [
    {
        "key": "infosec",
        "name": "Information security policy",
        "kind": "policy",
        "unit": "SEC",
        "by": "ciso",
        "approvers": ["president"],
        "summary": "What Northmere requires to protect the information it holds, and who does what.",
        "versions": [
            (720, INFOSEC_V1, None),
            (
                340,
                INFOSEC_V2,
                "Patching follows the vulnerability standard's times; suppliers are bound by the policy.",
            ),
        ],
        "draft": {
            "since": 18,
            "edits": INFOSEC_V3,
            "note": "Privacy decides exceptions that touch personal information; yearly training is required.",
            "approvers": ["president", "cro"],
            "approved": ["cro"],
        },
    },
    {
        "key": "aup",
        "name": "Acceptable use policy",
        "kind": "policy",
        "unit": "SEC",
        "parent": "infosec",
        "by": "ciso",
        "approvers": ["coo"],
        "summary": "What using Northmere's computers, networks, and accounts well looks like.",
        "versions": [
            (690, AUP_V1, None),
            (
                300,
                AUP_V2,
                "Generative tools: only approved ones, and never with restricted information.",
            ),
            (
                40,
                AUP_V3,
                "Work stays in Northmere's own accounts: no personal email or file sharing.",
            ),
        ],
        # Everyone is asked to say they have read each version; most have read the newest,
        # and a campaign has just started to chase the rest. The sample staff member has still to.
        "acknowledge": {
            "shares": [0.97, 0.94, 0.62],
            "campaign": {"ago": 2, "due": 12, "by": "assess1", "name": "Acceptable use, version 3"},
        },
    },
    {
        "key": "access",
        "name": "Access control standard",
        "kind": "standard",
        "unit": "SEC",
        "parent": "infosec",
        "by": "ciso",
        "approvers": ["cio"],
        "summary": "Who gets access to what, how it is given, reviewed, and taken away.",
        "versions": [(400, ACCESS_V1, None)],
    },
    {
        "key": "passwords",
        "name": "Password and authentication standard",
        "kind": "standard",
        "unit": "IT",
        "parent": "infosec",
        "by": "cio",
        "approvers": ["ciso"],
        "summary": "How people prove who they are: passwords, second factors, and service accounts.",
        "versions": [
            (500, PASSWORDS_V1, None),
            (
                120,
                PASSWORDS_V2,
                "A second factor wherever an account can be reached from outside; no more text-message codes for new enrolments.",
            ),
        ],
    },
    {
        "key": "classification",
        "name": "Data classification standard",
        "kind": "standard",
        "unit": "CMPL",
        "parent": "infosec",
        "by": "CMPL",
        "approvers": ["ciso", "cro"],
        "summary": "The four classes of information, and how each is handled.",
        "versions": [(600, CLASSIFICATION_V1, None)],
        "reviews": [
            (
                240,
                "Checked against the new genomic data sharing terms; the restricted class already covers them.",
            )
        ],
    },
    {
        "key": "encryption",
        "name": "Encryption standard",
        "kind": "standard",
        "unit": "SEC",
        "parent": "infosec",
        "by": "ciso",
        "approvers": ["cio"],
        "summary": "What is encrypted, in storage and in transit, and how keys are kept.",
        "versions": [(345, ENCRYPTION_V1, None)],
    },
    {
        "key": "vuln",
        "name": "Vulnerability management standard",
        "kind": "standard",
        "unit": "SEC",
        "parent": "infosec",
        "by": "ciso",
        "approvers": ["cio"],
        "summary": "How weaknesses are found, and how quickly each is fixed.",
        "versions": [(260, VULN_V1, None)],
    },
    {
        "key": "incident",
        "name": "Incident response procedure",
        "kind": "procedure",
        "unit": "SEC",
        "parent": "infosec",
        "by": "ciso",
        "approvers": ["cio", "cro"],
        "review_months": 6,
        "summary": "What to do when a security incident is suspected, and how the response runs.",
        # Those who act in an incident: IT, Information Security, Research Computing, and
        # every steward, who is often the first to hear of one.
        "audience": {"units": ["IT", "SEC", "RC"], "roles": ["steward"]},
        "acknowledge": {"shares": [0.96, 0.92, 0.81]},
        "versions": [
            (560, INCIDENT_V1, None),
            (
                230,
                INCIDENT_V2,
                "After the spring exercise: keep logs when containing, and how to reach us out of hours.",
            ),
            (
                60,
                INCIDENT_V3,
                "The privacy office decides within 24 hours whether anyone must be told.",
            ),
        ],
    },
    {
        "key": "backup",
        "name": "Backup and restore procedure",
        "kind": "procedure",
        "unit": "IT",
        "parent": "infosec",
        "by": "cio",
        "approvers": ["ciso"],
        "summary": "How systems are backed up and restored. Kept on the IT intranet, where the runbooks live.",
        "link": "https://intranet.northmere.example/it/runbooks/backup-and-restore",
        "versions": [(280, None, None)],
    },
    {
        "key": "remote",
        "name": "Working away from the office",
        "kind": "guideline",
        "unit": "SEC",
        "parent": "aup",
        "by": "ciso",
        "approvers": ["cio"],
        "summary": "Advice for working securely at home and when travelling.",
        "versions": [],
        "draft": {
            "since": 26,
            "body": REMOTE_V1,
            "approvers": ["cio"],
            "returned": (
                "cio",
                "The VPN is not needed for the systems we moved to single sign-on last year; say which ones still need it.",
            ),
        },
    },
    {
        "key": "rdm",
        "name": "Research data management policy",
        "kind": "policy",
        "unit": "RES",
        "by": "cso",
        "approvers": ["president"],
        "summary": "Where research data is kept, for how long, and how it is shared. Kept as the signed PDF.",
        "file": RDM_LINES,
        "versions": [(450, None, None)],
    },
]

# What each document governs: the controls it directs and the requirements it answers, said
# by its author once the central controls were on record. The research data policy says
# nothing yet, so that one document shows what is missing.
GOVERNS = {
    "infosec": (
        [("security_policy", "SEC"), ("security_roles", "SEC"), ("security_oversight", "SEC")],
        [("nist-csf", "GV.PO-01"), ("nist-csf", "GV.PO-02"), ("nist-csf", "GV.RR-02"),
         ("nist-800-53", "PL-1"), ("nist-800-53", "PM-1"), ("hipaa-security", "164.316(a)"),
         ("hipaa-security", "164.308(a)(1)(i)"), ("nist-800-171", "03.15.01")],
    ),
    "aup": (
        [("security_training", "SEC")],
        [("nist-800-53", "PL-4"), ("nist-csf", "PR.AT-01"), ("hipaa-security", "164.308(a)(5)(i)")],
    ),
    "access": (
        [("access_approved", "IT"), ("access_reviewed", "SEC"), ("access_removed_on_leaving", "IT"),
         ("unique_accounts", "IT"), ("privileged_access", "IT")],
        [("nist-800-53", "AC-1"), ("nist-800-53", "AC-2"), ("nist-csf", "PR.AA-05"),
         ("hipaa-security", "164.308(a)(4)(i)")],
    ),
    "passwords": (
        [("second_factor", "IT"), ("unique_accounts", "IT")],
        [("nist-800-53", "IA-5"), ("nist-csf", "PR.AA-01")],
    ),
    "classification": (
        [("data_classified", "CMPL")],
        [("nist-800-53", "RA-2"), ("nist-csf", "ID.AM-07")],
    ),
    "encryption": (
        [("encryption_at_rest", "IT"), ("encryption_in_transit", "IT")],
        [("nist-800-53", "SC-13"), ("nist-800-53", "SC-28"), ("nist-csf", "PR.DS-01"),
         ("nist-csf", "PR.DS-02"), ("hipaa-security", "164.312(a)(2)(iv)"),
         ("hipaa-security", "164.312(e)(2)(ii)")],
    ),
    "vuln": (
        [("vulnerability_scanning", "SEC"), ("patching", "IT")],
        [("nist-800-53", "RA-5"), ("nist-800-53", "SI-2"), ("nist-csf", "ID.RA-01"),
         ("nist-csf", "PR.PS-02")],
    ),
    "incident": (
        [("incident_response", "SEC"), ("incident_reporting", "SEC")],
        [("nist-800-53", "IR-1"), ("nist-800-53", "IR-8"), ("nist-csf", "RS.MA-01"),
         ("hipaa-security", "164.308(a)(6)(i)"), ("hipaa-security", "164.308(a)(6)(ii)")],
    ),
    "backup": (
        [("backups_tested", "IT"), ("disaster_recovery", "IT")],
        [("nist-800-53", "CP-9"), ("nist-csf", "PR.DS-11"), ("hipaa-security", "164.308(a)(7)(ii)(A)")],
    ),
}  # fmt: skip

# Departures from a document: asked for by a unit's steward, decided by the leader of the unit
# that keeps the document. One is in force; one waits for the security leader.
DOCUMENT_EXCEPTIONS = [
    {
        "document": "encryption",
        "unit": "IMG",
        "ago": 74,
        "decided": {
            "by": "ciso",
            "ago": 71,
            "note": "Until the vendor's update. Tell me if it slips.",
        },
        "until": 40,
        "name": "Confocal microscope control PC",
        "justification": "The confocal microscope's control PC runs vendor software that stops working when the disk is encrypted. The vendor's update that fixes it is due this winter.",
        "compensating": "The PC is not on the network, sits in a locked room, and holds images only until they are copied to research storage each evening.",
    },
    {
        "document": "vuln",
        "unit": "CLAB",
        "ago": 4,
        "until": 150,
        "name": "Chemistry analyzer patching",
        "justification": "The chemistry analyzers' maker must certify each operating system patch before it may be applied, which takes up to 90 days: longer than the standard allows for a high-severity fix.",
        "compensating": "The analyzers sit on their own network segment that reaches only the laboratory system, they are scanned weekly, and certified patches are applied within a week of release.",
    },
]

# Agreements, with their dates in days from the build. The data use agreement imposes its
# own terms on the scope that holds the backups of the cohort's data; the genomic data
# certification names a published framework the enclave already meets; the backup vaulting
# agreement's notice date is near, and is on the security leader's Home; the imaging pilot's
# memorandum ended and was closed.
AGREEMENTS = [
    {
        "key": "cohort_dua",
        "name": "Open Cohort Trust data use agreement",
        "kind": "data_use",
        "parties": "Open Cohort Trust",
        "reference": "OCT-DUA-2025-117",
        "unit": "PS",
        "owner": "PS",
        "made": 380,
        "starts": -631,
        "ends": 465,
        "notice_days": 90,
        "renews": True,
        "terms": "own",
        "summary": "Lets Population Sciences use the trust's cohort data for the approved study, on the trust's terms.",
        "covers": ["info_open_cohort", "storage", "backup"],
    },
    {
        "key": "genomic_cert",
        "name": "Genomic data access certification",
        "kind": "data_use",
        "parties": "Genome Commons Repository",
        "reference": "GCR-CERT-8841",
        "unit": "RC",
        "owner": "rc_dir",
        "made": 200,
        "starts": -400,
        "ends": 48,
        "renews": False,
        "terms": "nist-800-171",
        "summary": "The repository's conditions for controlled-access genomic data: held only in a system that meets SP 800-171.",
        "covers": ["info_genomic"],
        "scopes": ["Controlled-access data enclave"],
    },
    {
        "key": "vault_baa",
        "name": "Offsite backup vaulting",
        "kind": "business_associate",
        "parties": "Stonebridge Data Vaulting",
        "reference": "SDV-2024-0391",
        "unit": "IT",
        "owner": "ciso",
        "made": 640,
        "starts": -700,
        "ends": 75,
        "notice_days": 60,
        "renews": True,
        "summary": "Stonebridge keeps the offsite copy of the backups, which hold patient records, as a business associate.",
        "covers": ["backup"],
    },
    {
        "key": "imaging_mou",
        "name": "Imaging pilot data sharing",
        "kind": "memorandum",
        "parties": "Calder Bay University",
        "unit": "IMG",
        "owner": "IMG",
        "made": 500,
        "starts": -500,
        "ends": -120,
        "renews": False,
        "summary": "Shared de-identified images with the university's imaging group for a one-year pilot.",
        "covers": [],
        "closed": (110, "Ended on its date; the pilot finished and was not renewed."),
    },
]

# A scope set up on SP 800-53 Rev. 4, because the industry sponsor's contract named it. Rev. 5
# is loaded beside it; the platform has not moved yet. One of its decisions is about a control
# Rev. 5 withdrew, and would be left behind.
SCOPE_TRIALS = {
    "name": "Trial data platform",
    "unit": "CR",
    "summary": "The hosted systems that hold the institute's clinical trial data, kept to the "
    "control baseline the industry sponsor's contract names.",
    "boundary": "Electronic data capture and the trial management system, and the trial "
    "participant data they hold. The hosting company runs both; the institute decides who may "
    "use them.",
    "members": ["edc", "ctms", "info_trials"],
    "units": [],
    "framework": ("nist-800-53-r4", "moderate"),
    "loaded": 560,
    "made": 520,
    "decisions": [
        ("PE-3", False, "The hosting company runs the data center; its physical access "
         "controls are covered by its own attestation report."),
        ("PE-6", False, "As for PE-3: watching physical access is the hosting company's."),
        ("SA-12", True, "The sponsor's contract asks for supply chain protection, though the "
         "moderate baseline does not."),
    ],
    "reviewed": 20,  # days ago, when crosswalks the publisher's mapping suggests were looked at
    # The central controls the platform's keepers mapped to Rev. 4 when it was set up. One is
    # to a control Rev. 5 moved into the supply chain family.
    "mapped": [
        ("access_approved", "IT", "AC-2"), ("second_factor", "IT", "IA-2(1)"),
        ("backups_tested", "IT", "CP-9"), ("encryption_at_rest", "IT", "SC-28"),
        ("access_reviewed", "SEC", "AC-2(3)"), ("supplier_assessed", "SEC", "SA-19"),
    ],
}  # fmt: skip

# The strategic plan's objectives, adopted by the President, and the risk categories whose
# risks threaten each: a category's own key, or the key of a category beneath it.
GOVERNANCE = {
    "period": "Strategic plan 2026 to 2030",
    "adopted": 330,  # days ago
    "named": 320,
    "committee": "Risk and compliance committee",
    "attendees": "The President and Director (chair), the Chief Operating Officer, the Chief "
    "Scientific Officer, the Chief Information Officer, the Chief Information Security Officer, "
    "and the Chief Risk and Compliance Officer (secretary). Apologies from the Chief Financial "
    "Officer.",
}
OBJECTIVES = [
    {
        "name": "Grow the population cohort to 40,000 participants",
        "summary": "The cohort is the institute's longest-running study, and most of Population "
        "Sciences rests on it.",
        "measure": "Enrolled participants, counted each June; consent withdrawals under one in a "
        "hundred a year.",
        "categories": ["human_subjects", "data_quality", "partnerships"],
    },
    {
        "name": "Bring two new therapies into first-in-human trials",
        "summary": "The translational program's aim for the plan's five years.",
        "measure": "Two investigational new drug applications cleared, and the first participant "
        "dosed in each.",
        "categories": ["clinical", "integrity", "scientific_direction"],
    },
    {
        "name": "Keep the trust of participants and patients",
        "summary": "People give the institute their samples, their data, and their care. They do "
        "so only while they trust it.",
        "measure": "No reportable breach of participant or patient information; complaints "
        "answered within ten working days.",
        "categories": ["privacy", "confidentiality", "patient_safety", "reputation",
                       "supplier_security"],
    },
    {
        "name": "Sustain sponsored research funding",
        "summary": "Federal and foundation awards fund most of the research.",
        "measure": "Award income held at or above the plan's baseline each year; no costs "
        "disallowed on audit.",
        "categories": ["financial", "grants", "funding_environment"],
    },
    {
        "name": "Run research infrastructure people can rely on",
        "summary": "The cores, the cluster, and the freezer farm that every lab depends on.",
        "measure": "Core services available nineteen days in twenty; no irreplaceable samples "
        "lost.",
        "categories": ["operations", "availability", "supplier_dependence"],
    },
]  # fmt: skip

# The committee's sessions, in days from the build. Each agenda takes the open risks rated
# highest that it has not yet discussed, then the items named. The third is still to come.
RISK_DECISIONS = [
    ("approved", "Fund the treatment plan as proposed. The owner reports progress at the next "
     "session."),
    ("deferred", "Bring it back with the cost of the second option before anything is agreed."),
    ("approved", "Accept the residual risk for twelve months. The owner tells the committee at "
     "once if anything changes."),
    ("noted", None),
]  # fmt: skip
SESSIONS = [
    {
        "planned": 190, "meets": -170, "held": True,
        "risks": 3,
        "items": [
            ("topic", "The risk appetite, reviewed",
             "Does the appetite for information and technology still stand at moderate?",
             ("approved", "The appetite stands as it is for another year.")),
            ("topic", "Next year's internal audit plan", None,
             ("approved", "Adopted, with research data management added in the second half.")),
        ],
        "minutes": "# Minutes\n\nThe chair opened the meeting and the minutes of the last "
        "session were agreed.\n\n## Risks above appetite\n\nThe committee went through the "
        "risks rated highest, with their owners. Decisions are recorded against each risk.\n\n"
        "## Matters arising\n\n- The security office will report on the tabletop exercise at "
        "the next session.\n- Finance will bring the cost of a second freezer site.",
    },
    {
        "planned": 95, "meets": -78, "held": True,
        "risks": 2,
        "items": [
            ("agreement", "Genomic data access certification",
             "It ends in the new year. Renew it on the repository's terms, or move the data out?",
             ("approved", "Renew it. Research Computing to confirm the enclave still meets "
              "SP 800-171 before the renewal is signed.")),
            ("document", "Incident response procedure",
             "What changed after the spring exercise.",
             ("noted", None)),
            ("topic", "The tabletop exercise: what it found", None,
             ("noted", "Three findings, each raised as an issue with an owner and a date.")),
        ],
        "minutes": "# Minutes\n\nThe chair opened the meeting. The actions from the last "
        "session were reviewed: both are done.\n\n## The tabletop exercise\n\nThe Chief "
        "Information Security Officer described the exercise and its three findings. The "
        "committee thanked the teams who took part.\n\n## Renewals\n\nThe genomic data "
        "certification is to be renewed, subject to the enclave's assessment.",
    },
    {
        "planned": 20, "meets": 12, "held": False,
        "risks": 2,
        "items": [
            ("topic", "The trial data platform: moving to SP 800-53 Rev. 5",
             "Agree a date for the move, and who reviews what changed.", None),
        ],
        "later": (
            3,
            [
                ("exception", "Chemistry analyzer patching",
                 "The laboratory asks to patch on the maker's schedule. The security leader "
                 "wants the committee's view before deciding.", None),
                ("document", "Information security policy",
                 "Version 3 waits for the President's approval: what it changes.", None),
            ],
        ),
    },
]  # fmt: skip

# Saved views: who shares it, its name, the list, and its filters.
VIEWS = [
    (
        "ciso",
        "Technology risks above appetite",
        "/risks",
        "above_appetite=true&category=technology",
    ),
    ("cro", "Reviews overdue", "/risks", "overdue=true&sort=next_review_on"),
    ("ciso", "Controls nobody has rated", "/controls", "missing=rating"),
    ("ciso", "Systems with no data class", "/systems", "missing=data_class"),
    ("assess1", "High issues still open", "/issues", "severity=high&status=open"),
]

# Indicators: numbers the institute already watches. Each: the unit that reads it, what it
# is counted in, which way is worse, the warning level, the limit, how often it is read, where
# it is read from, the library risks it warns of, and its readings, oldest first, one for each
# period up to now. None means nobody has read it yet.
INDICATORS = [
    ("Servers patched within 30 days", "IT", "%", "down", 95, 90, "monthly",
     "The patch compliance report in the endpoint management console, on the first of the month.",
     ["ransomware", "unsupported_systems"],
     [97, 98, 97, 96, 97, 96, 96, 95, 96, 94, 94, 93, 92, 91, 89]),
    ("Days to remove a leaver's access", "IT", "days", "up", 2, 5, "monthly",
     "Leavers in the personnel system against the day each account was disabled, averaged.",
     ["access_not_removed", "compromised_account"],
     [1, 1, 2, 1, 1, 1, 2, 1, 1, 2, 2, 3, 3, 4]),
    ("Accounts with no second factor", "IT", "accounts", "up", 10, 25, "monthly",
     "The identity service's report of accounts exempt from the second factor.",
     ["compromised_account"],
     [44, 41, 37, 30, 26, 22, 19, 15, 12, 9, 8, 6, 6, 5]),
    ("Staff with security training in date", "SEC", "%", "down", 92, 85, "monthly",
     "The learning system's completion report for the security module.",
     ["compromised_account", "health_information_breach"],
     [94, 93, 93, 92, 93, 92, 91, 91, 92, 91, 91, 90, 91, 91]),
    ("Critical vulnerabilities open past 30 days", "SEC", None, "up", 5, 15, "monthly",
     "The vulnerability scanner's ageing report, filtered to critical findings.",
     ["ransomware", "exposed_storage"],
     [3, 2, 4, 3, 2, 3, 5, 4, 6, 7, 6, 8, 9, 9]),
    ("People who entered a password in the phishing exercise", "SEC", "%", "up", 8, 12,
     "quarterly", "The result of each quarter's simulated phishing message.",
     ["compromised_account"],
     [14, 12, 11, 11, 9]),
    ("Freezer alarms not answered within 15 minutes", "BIO", None, "up", 1, 3, "quarterly",
     "The monitoring system's alarm log, counted by the repository manager.",
     ["specimen_loss"],
     [0, 1, 0]),
    ("Restore tests passed", "IT", "%", "down", 100, 90, "quarterly",
     "The backup team's quarterly restore log.", ["backup_failure", "research_data_loss"], None),
]  # fmt: skip

# Campaigns: what was asked, of whom, and what a few of them said.
CAMPAIGNS = {
    "attest": {
        "name": "Central information technology: control attestation",
        "summary": "Before the assessment closes, each owner confirms that their control still "
        "operates as its statement says, or tells us what has changed.",
        # control: what its owner says of it, and why
        "said": {
            "session_lock": (
                "partly",
                "Screens lock everywhere. Idle sessions on the two older "
                "terminal servers are not ended, since the upgrade was put back.",
            ),
        },
        "not_mine": ("physical_access", "Facilities took over the data room doors in the spring."),
        "waiting": 7,
    },
    "risks": {
        "name": "Core Facilities: risk self-assessment",
        "summary": "A look at every open risk in the cores before the annual plan is set.",
    },
    "evidence": {
        "name": "Clinical systems: evidence for the security rule review",
        "wanted": "Whatever shows the control operated this quarter: a report, an export, a signed "
        "log. One item for each control is enough.",
    },
}

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
    "pentest": {
        "unit": "IT", "source": "security_test", "severity": "critical", "urgent": True,
        "name": "Guest wireless can reach the instrument network",
        "summary": "This year's external penetration test reached two instrument controllers from "
        "the guest wireless network through a firewall rule left from the building move. The "
        "testers stopped there, as agreed. The controllers run software that cannot be patched.",
        "actions": [("Remove the rule, and confirm from guest wireless that the path is closed", -8, True),
                    ("Review every rule added during the building move", 9, False),
                    ("Ask the testers to try the path again", 16, False)],
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


# Fields of the organization's own: finance's cost center and the support tier on systems.
SYSTEM_FIELDS = [
    {"key": "cost_center", "label": "Cost center", "kind": "text",
     "help": "The cost center that pays for it, as finance knows it."},
    {"key": "support_tier", "label": "Support tier", "kind": "choice",
     "choices": ["Around the clock", "Business hours", "Best effort"]},
]  # fmt: skip
# system key, cost center, support tier
SYSTEM_FIELD_VALUES = [
    ("storage", "CC-4120", "Around the clock"), ("cluster", "CC-4120", "Business hours"),
    ("identity", "CC-3100", "Around the clock"), ("email", "CC-3100", "Business hours"),
    ("backup", "CC-3100", "Business hours"), ("record", "CC-7200", "Around the clock"),
    ("cabinets", "CC-7350", "Around the clock"), ("survey", "CC-5300", "Best effort"),
]  # fmt: skip


# What the patch scanner reports: days ago, the control, and what it says.
REPORTED = [
    (10, "Systems kept patched", {
        "kind": "result", "outcome": "failed",
        "title": "Nine servers more than 30 days behind on critical patches",
        "detail": "The virtual server platform's hosts in the research network.",
        "url": "https://scanner.northmere.example/reports/2026-11-17"}),
    (3, "Vulnerabilities found and followed up", {
        "kind": "result", "outcome": "partial",
        "title": "Two critical findings open past their date",
        "url": "https://scanner.northmere.example/reports/2026-11-24"}),
    (2, "Systems kept patched", {
        "kind": "evidence", "title": "Patch compliance report, November",
        "url": "https://scanner.northmere.example/reports/2026-11-25/compliance"}),
]  # fmt: skip
