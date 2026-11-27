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
