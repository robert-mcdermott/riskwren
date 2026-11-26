# Requirements

The capability catalog. IDs are stable: code, tests, and changelog entries can cite them.

**Priority:** **M**ust (required for the capability to ship), **S**hould (high value, next in line), **C**ould (optional expansion).
**Wave:** the release that delivers it (see [roadmap.md](roadmap.md)). `—` means not yet scheduled.

## Inventory (INV)

The things risk attaches to.

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| INV-01 | M | Units are the backbone | Every record belongs to one unit in a hierarchy of any depth; every list and figure can be narrowed to a unit and everything beneath it | 1 |
| INV-02 | M | Processes, systems, and third parties | Each is a record with a permanent reference, a unit, a description, a criticality, and the highest class of data it handles | 1 |
| INV-03 | M | Named owners | Every record has at least one accountable owner and may name a delegate and other contacts; a record whose owner has left is shown as orphaned | 1 |
| INV-04 | M | Typed links | Records are joined by named relationships (a process *relies on* a system, a system is *supplied by* a third party); each record shows what it depends on and what depends on it | 1 |
| INV-05 | M | History on every record | Each record shows who changed what and when, with the value before and after | 1 |
| INV-06 | M | Lists that hold their state | Every list searches, filters, sorts, and pages, with its state in the address so any view can be shared | 1 |
| INV-07 | S | Information assets | A record for a body of information: what it is, its data class and categories, where it is held, who it is shared with, and under what agreement | 2 |
| INV-08 | S | Spreadsheet import | Any record type is imported from CSV with column mapping and a dry run that reports every problem by row; nothing is loaded unless all of it can be | 2 |
| INV-09 | S | External references | A record can carry its identifier in another system (an asset tag, a contract number), shown as a link where a pattern is configured | 2 |
| INV-10 | S | Search and saved views | One search across every record type, filtered by what the searcher may see; a filtered list can be saved and shared | 3 |
| INV-11 | S | Dependency graph | A focused picture of what a record depends on and what depends on it, with a list beside it | 3 |
| INV-12 | S | Completeness and duplicates | Each record shows which expected facts are missing; likely duplicates are suggested and can be merged, keeping both histories | 3 |
| INV-13 | S | Sites | Buildings, floors, and facilities as records, for continuity planning and physical risk | 8 |
| INV-14 | C | Custom fields | An organization adds its own fields to a record type without code | 9 |

## Risk (RSK)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| RSK-01 | M | The risk register | A risk has a title, a statement of cause, event, and consequence, a category, a unit, an owner, and a status, and a permanent reference | 1 |
| RSK-02 | M | Taxonomy as data | Risk categories form a tree the organization edits; a category in use can be renamed or retired, never removed | 1 |
| RSK-03 | M | A scoring method as data | Likelihood levels, impact dimensions and their levels, the matrix that combines them, and the rating bands are one versioned document with a written definition for every level | 1 |
| RSK-04 | M | Inherent, residual, and target | A risk carries all three ratings; each comes from a dated assessment by a named person with a rationale; an assessment is never edited, only superseded | 1 |
| RSK-05 | M | Every rating explains itself | A rating opens to the likelihood chosen, the level on each impact dimension, the definitions of those levels, and the method version in force | 1 |
| RSK-06 | M | Risks attach to things | A risk is linked to the processes, systems, and third parties it concerns, and each of those shows its risks | 1 |
| RSK-07 | M | Appetite | Each category has a highest acceptable residual rating; every risk shows whether it is within appetite, and a risk above it needs a treatment plan or a named acceptance | 1 |
| RSK-08 | M | Heat map | Risks plotted by likelihood and impact, inherent or residual, with the appetite boundary drawn; every cell opens the risks in it and has a table behind it | 1 |
| RSK-09 | M | Risk library | Reusable risk statements by category, each suggesting controls, from which a risk can be started in one step | 1 |
| RSK-10 | M | Review dates by rating | Each risk has a next review date set from its residual rating by rule; an overdue review is shown on the risk and on its owner's home page | 1 |
| RSK-11 | M | Roll-up | A leader sees the risks of their unit and everything beneath it; a risk can be escalated to a higher unit with a reason | 1 |
| RSK-12 | S | Self-assessment campaigns | Owners are asked to re-assess their risks and controls by a date, with tracking of who has, reminders, and coverage by unit | 3 |
| RSK-13 | S | Indicators | A measure with thresholds, readings over time, and a trend, linked to the risks it warns of; a breach raises a notice | 3 |
| RSK-14 | S | Method and appetite editors | Program staff edit the scales, matrix, appetite, and cadences in the app; before publishing, the app lists the risks whose rating or standing would change | 3 |
| RSK-15 | S | Structured risk assessments | An assessment exercise over a named scope that walks its assets and threats and produces or refreshes risks, with a report of what was considered | 3 |
| RSK-16 | S | Objectives | Strategic objectives as records; a risk can name the objectives it threatens, and each objective shows its risks | 4 |
| RSK-17 | S | Loss events and near misses | What happened, when, the amount or the harm, and the risk it belongs to; totals by category and period | 8 |
| RSK-18 | S | Scenarios | A described scenario with its assumptions, the risks and processes it touches, and what was concluded | 6 |
| RSK-19 | C | Estimates in ranges | A risk may carry a low, likely, and high estimate of frequency and loss; a simulation reports the range of annual loss, with its assumptions shown | 6 |
| RSK-20 | C | Bow-tie view | Causes, preventive controls, the event, mitigating controls, and consequences on one diagram, with a table behind it | 6 |

## Treatment (TRT)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| TRT-01 | M | A recorded response | Each risk has a response (reduce, accept, transfer, or avoid) with a rationale, by a named person | 1 |
| TRT-02 | M | Treatment plans | A plan has an objective, a target rating, an owner, a due date, and actions; its progress shows on the risk | 1 |
| TRT-03 | M | Named, time-limited acceptance | An acceptance names who accepts what remains, why, and until when; on expiry the risk returns to its owner for a decision | 1 |
| TRT-04 | M | Authority to accept | Rules say who may accept a risk at each rating; nobody accepts a risk they own, and an acceptance by anyone without the authority is refused | 1 |
| TRT-05 | M | One list of actions | Every action, whatever it came from, has an owner, a due date, and a status, and appears in one list and on its owner's home page | 1 |
| TRT-06 | S | Extensions are visible | Moving a due date needs a reason; the original date and the number of extensions stay on the record | 2 |
| TRT-07 | C | Transfer records | A transferred risk names the insurance policy or contract that carries it, with its renewal date | 5 |

## Controls (CTL)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| CTL-01 | M | The control library | A control has a statement, an objective, a kind (preventive, detective, corrective, directive), a nature (manual, automated, or both), a frequency, a unit, and an owner | 1 |
| CTL-02 | M | Controls reduce risks | A link from a control to a risk says what it reduces (likelihood, impact, or both) and how much it is relied on | 1 |
| CTL-03 | M | Effectiveness is recorded, not assumed | A control's design and operation are each rated by a named person on a date, or shown as not assessed; a rating older than its cadence is shown as stale | 1 |
| CTL-04 | M | A suggested residual rating | From a risk's inherent rating and the known effectiveness of its controls, the app suggests a residual rating and shows the arithmetic; an assessor confirms or overrides it with a reason | 1 |
| CTL-05 | M | Starter control library | A set of common controls in plain words, loaded at installation and meant to be edited | 1 |
| CTL-06 | M | Implementations per scope | Within a scope, each applicable control has an implementation record: status, who is responsible, how it is done here, and any parameter values | 2 |
| CTL-07 | M | Inheritance | A scope can offer its controls to others; an inheriting scope shows whose control it relies on and that control's current state, and cannot mark it effective itself | 2 |
| CTL-08 | S | Shared responsibility | An inherited control may be fully inherited or shared, in which case the inheriting scope records and evidences its own part | 2 |
| CTL-09 | S | Attestation campaigns | Control owners confirm, by a date, that each control still operates as described, or say what has changed | 3 |
| CTL-10 | S | Key controls | A control can be marked key, which shortens its cadences and puts it on leadership views | 3 |

## Frameworks, obligations, and scopes (CMP)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| CMP-01 | M | Frameworks as packs | A framework is a tree of requirements with stable codes, loaded from a validated data file with its publisher, version, and license | 2 |
| CMP-02 | M | Only text that may be shipped | Each pack declares a text policy; a test fails the build if a pack carries text its policy does not allow | 2 |
| CMP-03 | M | Built-in public frameworks | The frameworks listed in [content-packs.md](content-packs.md) load with one command and arrive mapped to the starter controls | 2 |
| CMP-04 | M | Crosswalk | A control is mapped to every requirement it helps satisfy, in any number of frameworks; a requirement shows its controls and a control shows its requirements | 2 |
| CMP-05 | M | The organization's own frameworks | A contract, a grant's terms, a data use agreement, or an internal standard is entered or imported as a framework of its own and treated like any other | 2 |
| CMP-06 | M | Scopes | A scope names a boundary (units, processes, systems, information) and the frameworks or baselines it must meet, with an owner | 2 |
| CMP-07 | M | Applicability and tailoring | Within a scope each requirement is applicable or not, with a reason for any exclusion; the result prints as a statement of applicability | 2 |
| CMP-08 | M | Readiness that explains itself | For a scope and a framework, each requirement is in one of five states worked out from its controls, their tests, and their evidence; the summary opens to the requirements behind it | 2 |
| CMP-09 | M | Gaps | Requirements with no control, controls with no test, and tests with no current evidence are listed, each with a way to raise an issue | 2 |
| CMP-10 | S | Framework updates | A new version of a framework is loaded beside the old; the app lists what was added, changed, and withdrawn, and which controls and scopes are affected | 4 |
| CMP-11 | S | Suggested mappings | Where a publisher provides a mapping between two frameworks, it is used to suggest crosswalks, which a person confirms | 4 |
| CMP-12 | S | Agreements as obligations | An agreement record carries its parties, dates, what it covers, and the requirements it imposes, with a warning before it expires | 4 |
| CMP-13 | S | Open assessment formats | Catalogs, baselines, control implementations, assessment results, and plans of action are exported in the Open Security Controls Assessment Language; catalogs and baselines are imported from it | 6 |
| CMP-14 | C | Security plan document | A scope's implementation statements print as a system security plan in the customary order | 6 |

## Assessments and testing (AST)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| AST-01 | M | Assessments | An assessment covers a scope against a framework, a baseline, or a chosen set of controls, over a period, with a lead and a plan | 2 |
| AST-02 | M | Tests with procedures | Each control in an assessment has a test: the procedure, the method (examine, interview, test), what was sampled, and a result for design and for operation | 2 |
| AST-03 | M | Independence | Nobody records the result of a test on a control they own; a result is reviewed by a second person before it counts | 2 |
| AST-04 | M | Test once | One result updates the control's effectiveness, every requirement it is mapped to, in every scope that relies on it, and every risk it reduces | 2 |
| AST-05 | M | Results are permanent | A recorded result is never edited; a correction is a new result that supersedes it, and both stay in the history | 2 |
| AST-06 | M | Failed tests raise issues | A result of ineffective or partly effective opens an issue, prefilled, linked to the test | 2 |
| AST-07 | S | Test cadence | How often a control is tested follows from whether it is key and what relies on it; the next test date shows on the control | 3 |
| AST-08 | S | Self-assessment and independent test are told apart | An owner's attestation and an assessor's test are shown as different kinds of assurance, and rules say which a readiness figure may rest on | 3 |

## Evidence (EVD)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| EVD-01 | M | Evidence items | A file, a link, a note, or an attestation, with an owner, the date it was collected, the period it covers, and the date until which it holds | 2 |
| EVD-02 | M | Safe file storage | Files are stored by hash outside any served folder, limited in size and type by content, and returned only as downloads to someone entitled to the thing they are attached to | 2 |
| EVD-03 | M | Collect once, use many times | One evidence item supports any number of controls, tests, requirements, and issues | 2 |
| EVD-04 | M | Freshness | Evidence past its date no longer counts toward readiness and is shown as stale; evidence close to its date is flagged to its owner | 2 |
| EVD-05 | S | Evidence requests | An owner is asked for a named piece of evidence by a date; the request closes when the evidence is attached | 3 |
| EVD-06 | S | Classified evidence | An evidence item carries a data class, and access to it follows that class | 2 |
| EVD-07 | S | Provenance | Evidence pushed by another system records which system, when, and under which token, and is labelled as such wherever it appears | 10 |

## Issues, actions, and exceptions (ISS)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| ISS-01 | M | One issue register | Issues from tests, audits, incidents, vendor reviews, and people's own observations live in one register, each naming its source | 2 |
| ISS-02 | M | Severity sets the clock | An issue has a severity with a defined meaning; its due date follows from severity by rule | 2 |
| ISS-03 | M | Action plans | An issue is resolved through actions with owners and dates; its progress is the progress of its actions | 2 |
| ISS-04 | M | Closure is validated | An owner proposes closure with evidence; someone else confirms it before the issue closes | 2 |
| ISS-05 | M | Root cause | A closed issue records a root cause category, so causes can be counted | 2 |
| ISS-06 | M | Exceptions | A request to depart from a control, a requirement, or a policy states the justification and compensating controls, is approved by someone with authority, expires, and can be renewed | 2 |
| ISS-07 | S | Plan of action view | The open issues of a scope print as a plan of action and milestones | 2 |
| ISS-08 | C | Likely duplicates | A new issue is compared with open ones on the same control and the reporter is shown any that look the same | 3 |

## Keeping watch (OVS)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| OVS-01 | M | Scheduled work | Daily jobs open what is due, send reminders, and mark what has lapsed; exactly one process runs each job | 3 |
| OVS-02 | M | Cadences as data | How often risks are reviewed, controls tested and attested, evidence renewed, and third parties re-assessed is one editable table keyed by rating and criticality | 3 |
| OVS-03 | M | Reminders and escalation | An overdue item reminds its owner, then their steward, then their leader, on a schedule the program sets | 3 |
| OVS-04 | M | Campaigns | A request to a set of people to do one thing by a date, with tracking, reminders, and coverage by unit | 3 |
| OVS-05 | M | Email | Notices go by email through an SMTP server the administrator names, as they happen or as a digest, by each person's choice | 3 |
| OVS-06 | M | Notices in the app | Each person has a list of what has been assigned to them or changed for them, with a count in the top bar | 2 |
| OVS-07 | S | Questionnaires as data | A questionnaire is a versioned document of sections and questions that appear by condition; answers always display as they were asked | 3 |
| OVS-08 | S | When someone leaves | Disabling an account lists what they owned and lets a steward reassign it in one step | 3 |
| OVS-09 | S | Committee sessions | An agenda of items for a risk or compliance committee, the decisions taken on each, and the minutes | 4 |

## Policies (POL)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| POL-01 | M | A hierarchy of documents | Policies, standards, procedures, and guidelines, each with an owner and a unit, arranged so that a procedure names the policy it implements | 4 |
| POL-02 | M | Versions and approval | A draft is reviewed and approved by named people before it is published; a published version is never altered | 4 |
| POL-03 | M | Review dates | Each document has a next review date; an overdue review shows on the document and on its owner's home page | 4 |
| POL-04 | M | Mapped to controls and requirements | A document shows the controls it directs and the requirements it answers | 4 |
| POL-05 | M | Acknowledgment | People are asked, by unit or role, to confirm they have read a version; who has and has not is tracked | 4 |
| POL-06 | M | A library for everyone | Anyone signed in can search and read the published documents that apply to them | 4 |
| POL-07 | S | Held here or held elsewhere | A document's text may live in RiskWren or be a link to the place the organization already keeps it; either way the lifecycle is tracked here | 4 |
| POL-08 | C | What changed | Two versions of a document are shown side by side with the differences marked | 4 |

## Third parties (TPR)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| TPR-01 | M | Third parties and what they provide | A third party has services or products as records of their own, each with the systems and information it touches | 5 |
| TPR-02 | M | Tiering | A short set of questions about what a third party does and touches sets its tier by rule, with the reasons shown | 5 |
| TPR-03 | M | Due diligence | A questionnaire, chosen by tier, is sent to a named contact through a link that expires; no account is needed; answers are reviewed and scored | 5 |
| TPR-04 | M | Assurance documents | Reports and certificates are held as evidence with their period and expiry, and a structured review records what was in scope, what exceptions were noted, and what the organization must do itself | 5 |
| TPR-05 | M | Agreements and what they cover | Each agreement names its kind, its dates, and the services, systems, and information it covers; an expiring agreement warns its owner | 5 |
| TPR-06 | M | A stop for uncovered data | Where regulated information is shared with a third party and no agreement of the required kind covers it, the gap is shown as a stop on every record involved | 5 |
| TPR-07 | M | Findings tracked with the third party | A concern from a review is an issue whose actions may belong to the third party's contact | 5 |
| TPR-08 | M | Re-assessment | Each third party is re-assessed on a cadence set by its tier, and when an incident or a change of service calls for it | 5 |
| TPR-09 | S | Offboarding | Ending a relationship opens a checklist: access removed, information returned or destroyed, and an attestation recorded | 5 |
| TPR-10 | S | Subcontractors | A third party can name the parties it depends on, which appear in the dependency graph | 5 |
| TPR-11 | C | Answering other people's questionnaires | A library of approved answers with their evidence, from which a response to an incoming questionnaire is assembled | — |

## Audit (AUD)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| AUD-01 | M | Audit universe | The auditable units, processes, and systems, each with its last audit and a risk ranking drawn from the register | 7 |
| AUD-02 | M | The plan | A period's planned engagements with their reasons, approved and then tracked against | 7 |
| AUD-03 | M | Engagements | Planning, fieldwork, and reporting stages with a program of work, a team, and dates | 7 |
| AUD-04 | M | Workpapers | Each step of the work has a workpaper with what was done, what was found, the evidence, review notes, and sign-off | 7 |
| AUD-05 | M | Requests to the audited | A list of what is needed, each item assigned to a person with a date, answered with evidence | 7 |
| AUD-06 | M | Findings and follow-up | A finding becomes an issue with management's action plan; audit validates closure | 7 |
| AUD-07 | M | Independence | Work in progress is visible only to the audit team until the report is issued | 7 |
| AUD-08 | S | Outside auditors | A person outside the organization is given read-only access to one engagement or scope for a set period, and everything they open is recorded | 7 |
| AUD-09 | S | Committee report | A period's engagements, findings by severity, and overdue actions in one printable report | 7 |

## Incidents, cases, and privacy (INC)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| INC-01 | M | Report in a minute | Anyone signed in can report an incident, a near miss, or a concern in one short form | 8 |
| INC-02 | M | Reporting without a name | Where the organization opens it, a concern can be reported through a link with no sign-in and no identity kept; the reporter receives a code to follow up with | 8 |
| INC-03 | M | Triage | Each report is given a category and severity, linked to the records it concerns, and assigned | 8 |
| INC-04 | M | Restricted cases | A case can be limited to named people; its existence is hidden from everyone else, including in search and history | 8 |
| INC-05 | M | Breach assessment | A structured assessment of whether an incident involving protected information must be notified, with the factors, the conclusion, the deadlines, and each notification made | 8 |
| INC-06 | M | Learning | An incident links to the risks it realized and the controls that failed, opens corrective actions, and records what was learned | 8 |
| INC-07 | S | Privacy impact assessments | A questionnaire required by rule when a process or system handles named categories of information, reviewed and kept with the record | 8 |

## Resilience (RES)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| RES-01 | M | Business impact analysis | For a process: the impact of its loss over time, how soon it must be restored, how much information can be lost, and the least it needs to run | 8 |
| RES-02 | M | Dependencies checked against need | A process's required recovery times are compared with what each system, site, and third party it relies on can deliver; shortfalls are listed | 8 |
| RES-03 | M | Plans | Continuity and recovery plans with versions, owners, and review dates, which print cleanly for use when systems are down | 8 |
| RES-04 | M | Exercises | A test of a plan records what was tried, what happened, and findings, which become issues | 8 |

## Insight (RPT)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| RPT-01 | M | What I owe | Each person's home page lists their reviews, actions, attestations, and requests in one list, overdue first | 1 |
| RPT-02 | M | Risk dashboard | The heat map, top risks, risks above appetite, distribution by category and unit, and overdue reviews and actions; every figure opens the records behind it | 1 |
| RPT-03 | M | Compliance dashboard | Readiness by scope and framework, open issues by severity and age, stale evidence, and exceptions about to expire | 2 |
| RPT-04 | M | One visibility rule | A list, a count, a chart, and an export all apply the same rule about what the viewer may see, and so always agree | 1 |
| RPT-05 | S | Exports | Every list exports to CSV and JSON as filtered | 2 |
| RPT-06 | M | Measures with definitions | Each figure states what it counts, over what period, and for which records; a daily snapshot gives trends | 6 |
| RPT-07 | M | Portfolio views | Risk and compliance by unit, category, framework, and third party over a chosen period, drilling down to records | 6 |
| RPT-08 | M | Leadership report | A periodic report of top risks, movement, appetite, posture, and overdue items, frozen as a snapshot that reopens unchanged | 6 |
| RPT-09 | M | As of | Any record, and the register, as it stood on a chosen date | 6 |
| RPT-10 | M | Dossier | A complete, printable package for a scope, a risk, or a third party, with a manifest that verifies | 6 |
| RPT-11 | S | Root causes and trends | Issues by root cause, age, and source over time | 6 |

## Platform (PLT)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| PLT-01 | M | Install in minutes | Three commands produce a running system on SQLite with a first administrator and no other software | 1 |
| PLT-02 | M | SQLite and PostgreSQL | One model and one set of migrations run on both; the whole test suite passes on both | 1 |
| PLT-03 | M | Sign-in always required | Local accounts with hashed passwords, server-side sessions, and throttled sign-in | 1 |
| PLT-04 | M | Roles with scope | Seven roles, some limited to a unit and everything beneath it; every API route is checked against one policy table | 1 |
| PLT-05 | M | A permanent history | Every change is an event in an append-only, hash-chained log; a command verifies the chain | 1 |
| PLT-06 | M | Optimistic concurrency | A change made against an older version of a record is refused with the current values | 1 |
| PLT-07 | M | Themes | Light, dark, and system modes and three palettes, each checked for contrast | 1 |
| PLT-08 | M | Branding in the app | An administrator sets names, logo, palette, and accent with a live preview | 1 |
| PLT-09 | M | A default program | A new installation is loaded with a taxonomy, a scoring method, appetite, cadences, vocabularies, a risk library, and starter controls | 1 |
| PLT-10 | M | Demo organization | One command builds a fictional organization through the real services, with data on every screen | 1 |
| PLT-11 | M | Command line | Installation, accounts, the database, program packs, verification, and health checks from one command | 1 |
| PLT-12 | M | Accessibility | WCAG 2.2 AA, with an automated audit over every documented screen in every palette and mode | 1 |
| PLT-13 | M | Single sign-on | OpenID Connect with any standards-based provider; groups or application roles mapped to roles and unit scopes | 3 |
| PLT-14 | S | Program packs | The whole program configuration exports to one file and imports into another installation, checked before any of it is loaded | 1 |
| PLT-15 | S | Backup and moving | An installation is backed up, restored, and moved between SQLite and PostgreSQL by command | 9 |
| PLT-16 | S | Deployment recipes | A container image, a compose file with PostgreSQL, a hardened service unit, and proxy examples | 9 |
| PLT-17 | S | Brand kit | A full custom palette, sign-in page message, email header, footer links, and the organization's own words for key terms | 9 |
| PLT-18 | S | Starter programs | Program packs for a research institute, an academic medical center, a university, and a general nonprofit | 9 |
| PLT-19 | S | Security review | A review against a published application security verification standard, with findings and their resolution recorded | 9 |
| PLT-20 | C | Other languages | The interface in languages other than English | — |

## Integration (INT)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| INT-01 | M | One API | Everything the web app does, it does through `/api/v1`; the OpenAPI document is generated, committed, and kept current by a test | 1 |
| INT-02 | S | Scoped tokens | An administrator issues a token limited to a role and optionally to reading, shown once, stored as a hash, with an expiry | 9 |
| INT-03 | S | Signed webhooks | Named events are sent, signed, to addresses an administrator registers, carrying references and not record contents | 9 |
| INT-04 | S | Results pushed in | Another system posts a test result or a piece of evidence onto a control; it is recorded with its source and never overrides a person's judgment | 10 |
| INT-05 | S | A reference others can check | Another process asks whether a third party, a scope, or an exception is in good standing and gets a yes, a no, or a not found | 10 |
| INT-06 | C | Tool server for assistants | An optional server through which an AI assistant reads records and drafts changes that a person confirms | 10 |
| INT-07 | C | Optional assistant | Off and invisible by default; drafts risk statements and summarizes records with any compatible provider, including a local one; every exchange logged | 10 |

## Documentation (DOC)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| DOC-01 | M | Guides in the repository | Getting started, configuration, and a guide for each area, written so a site can be built from them unchanged | 1 |
| DOC-02 | M | Documentation site | A product site with illustrated guides, screenshots of the demo organization in both themes, and an API reference | after 2 |
| DOC-03 | S | The program handbook | One guide for a risk and compliance team, from first decisions to the yearly rhythm | 9 |
