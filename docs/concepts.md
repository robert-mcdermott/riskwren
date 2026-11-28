# How RiskWren works

This guide explains the ideas the rest of the guides take for granted: what RiskWren is, the pieces of the record and how they fit together, who does what, and the rules it keeps. Read it first, whatever your part. It takes about twenty minutes, and the other guides will make sense faster for it.

## What it is, and what it is not

RiskWren is a **system of record** for governance, risk, and compliance: one place where an organization writes down what it depends on, what could go wrong, what it does about it, what it is held to, and the proof that it does what it says. Every judgment in it is made by a named person, with a reason, on a date, and nothing in it can be changed without the change being kept.

It is built for an organization that has to show its work: to its leaders, its auditors, its regulators, its funders, and the people whose information it holds. It was written first for the information security team of a research or health organization, and works the same for a risk office, a compliance office, internal audit, or a privacy office.

**It is passive.** It does not scan networks, collect logs, install agents, or reach into any other system. It never sits in the path of anything else. It records what people know and decide, and what other systems choose to tell it. When it sends anything out (an email, a webhook, a question to an assistant), it is because someone set that up.

**It describes, it does not hold.** Its records describe systems, information, and third parties: that a system holds patient records, that a supplier handles controlled information. The patient records and the controlled information themselves do not belong in it. Evidence is a file or a link that shows a control works, not a copy of the data the control protects. Files people attach are kept as they are; they are not scanned for viruses, so attach what your organization would attach to any internal system.

**It is not** a vulnerability scanner, a ticketing system, a document management system, or a learning management system. It works beside them: a scanner can report a failed check onto a control, a service desk can be told when an issue is raised, and a policy can link to where the full text is kept.

**One organization per installation.** Units, people, and the program (its scales, appetite, and rules) belong to the organization. Several organizations need several installations.

## The pieces, and how they fit

Everything in RiskWren is one connected record. A system is written down once, and every risk, control, scope, incident, and third party that concerns it points at the same record. The pieces, in the order an organization usually fills them in:

| Piece | What it is | Where it is explained |
|---|---|---|
| **Units** | The organization as a tree: divisions, departments, labs, clinics, offices. Every record belongs to one | [Getting started](getting-started.md#units) |
| **The inventory** | What the organization depends on: processes, systems, third parties and their services, information, and sites, each with its owners, how critical it is, and, for information and systems, how sensitive | [The register](the-register.md#the-inventory) |
| **Risks** | Something that could happen and would matter, written as a cause, an event, and a consequence, about something in the inventory | [The register](the-register.md#risks) |
| **Controls** | Something the organization does to make a risk less likely or less harmful, described once, with its owners and a rating of how well it works | [The register](the-register.md#controls) |
| **Treatment** | A plan, with actions, to bring a risk down; or an acceptance, by someone with the authority, to live with it until a date | [The register](the-register.md#treatment) |
| **Frameworks and requirements** | What the organization is held to: a standard, a regulation, an agreement's terms, its own policies. Controls are mapped to the requirements they answer | [Compliance](compliance.md#frameworks) |
| **Scopes** | A boundary held to a framework: the clinical systems under the HIPAA Security Rule, a data enclave under NIST SP 800-171. A scope says which requirements apply and which controls it uses | [Compliance](compliance.md#scopes) |
| **Evidence** | Proof that a control works: a file, a link, a note, or an attestation, which counts until a date | [Evidence and testing](evidence-and-testing.md#evidence) |
| **Assessments and tests** | A planned check of a scope's controls; each test's result counts once a second person confirms it | [Evidence and testing](evidence-and-testing.md#assessments) |
| **Issues** | Something wrong that must be put right, from a failed test, an audit, an incident, or anyone who sees it, with a severity, a date, and actions | [Issues and exceptions](issues-and-exceptions.md) |
| **Exceptions** | An approved, time-limited departure from a control, a requirement, or a policy | [Issues and exceptions](issues-and-exceptions.md#exceptions) |
| **Policies and agreements** | The organization's own documents, approved, published, and acknowledged; and its obligations to others, with their dates | [Policies](policies.md), [Compliance](compliance.md#agreements) |
| **Third parties** | Suppliers and partners: what they reach and handle, their tier, their due diligence, their reports and certificates, and the agreements that cover them | [Third parties](third-parties.md) |
| **Incidents** | Something that went wrong, a near miss, or a concern, reported by anyone, handled, assessed for breach, and learned from | [Incidents](incidents.md) |
| **Resilience** | What each process cannot afford to lose and how soon it must be back, checked against what its systems and suppliers can deliver; continuity plans and exercises | [The register](the-register.md#business-impact-and-recovery) |
| **Internal audit** | The audit universe, a plan, engagements, and findings, kept apart until reported | [Internal audit](internal-audit.md) |
| **Insight** | Measures, the portfolio, leadership reports, the record as it stood on a date, and dossiers that prove themselves | [Running the program](running-the-program.md#read-the-dashboards) |

The links between them are where the value is. A failed test of a control raises an issue on that control, moves every requirement it answers in every scope that relies on it, and casts doubt on the rating of every risk it reduces. An incident names the risks it realized and the controls that failed, and each of those pages shows it. A third party that handles patient records with no business associate agreement is stopped, and so is everything that depends on it.

### Two kinds of question it answers

RiskWren answers two questions about the same record, and keeps them apart.

- **Risk: what could go wrong, and is it in order?** A risk has three **ratings**: *inherent* (if the controls were not there), *residual* (with the controls as they are), and *target* (once treatment is done), each a likelihood and an impact on the program's scales. Its **standing** says whether it is in order: within appetite, being treated, accepted, or needing a decision. A critical risk that is accepted is in order; a moderate one above appetite with no plan is not. See [Rating and standing](the-register.md#rating-and-standing).
- **Compliance: are we doing what we are held to, and can we prove it?** For a scope and a framework, each requirement that applies is **verified**, **in place**, **planned**, a **gap**, **failing**, or **excepted**. See [Readiness](compliance.md#readiness).

A control is the bridge. The same control reduces risks and answers requirements, and the same test result moves both.

## People, units, roles, and owners

**Units.** Every record belongs to a unit. Figures roll up the tree, and roles can be limited to a unit and everything beneath it.

**Roles** say what someone may do across the organization or within a unit. There are six that are given, and everyone who can sign in is also a member:

| Role | What it is for |
|---|---|
| **Manager** | The risk and compliance team. Runs the program, edits any record, and reads everything it covers. Can be limited to a unit |
| **Assessor** | Assesses risks, rates controls, tests them, and confirms others' work. Can be limited to a unit |
| **Leader** | Leads a unit: sees it and everything beneath it, and may accept its risks up to a limit |
| **Steward** | Keeps a unit's records complete and current |
| **Auditor** | Reads the whole record, including the history, and runs internal audit's own work |
| **Admin** | Accounts, units, sign-in, appearance, and the program's settings. Reads the whole record |
| **Member** | Everyone: sees what they are named on, and does what is assigned to them |

**Owners** are named on a record and answer for it. Being an owner is not a role: anyone may own a system, a risk, a control, or an issue. Owners edit what they own, are reminded of what it needs, and see it on their Home. A record whose owners have all left is listed for someone to name a new one.

The difference matters. A steward keeps a unit's records; the owner of a control answers for that control. A person can be both, and most people in an organization will be owners and members and nothing else.

[Your part in it](roles.md) says what each role does day to day and how to choose who gets which. [Running the program](running-the-program.md#roles-and-scope) has the full table of who may do what.

## The rules it keeps

These are the ideas behind most of what RiskWren will and will not let you do. When something is refused, one of them is usually the reason.

**Worked out, never typed in.** Standing, readiness, what the controls suggest a residual rating should be, a supplier's tier, a deadline for a breach notice, the measures: each is worked out from the record by a rule that is shown beside it. Nobody can type "verified" or "within appetite". To change the answer, change what it rests on.

**Judgments are dated and named, and never edited.** An assessment of a risk, a rating of a control, a test result, an acceptance, a decision on an exception: each is made by a person, with a reason, on a date. A later one supersedes it; nothing overwrites it. The record says who judged what, and when.

**Nobody marks their own work.** The owner of a control cannot record its test or confirm its result. A result counts only when a second person confirms it. Whoever owns an issue, or proposed closing it, cannot confirm its closure, and an owner cannot withdraw it. Whoever asked for an exception cannot decide it. A plan's drafter cannot approve it, and a workpaper's preparer cannot sign it off. This is why some steps need two people, and why a very small team may need to share roles across units.

**Authority is explicit.** Who may accept a risk at each rating is a table the program keeps, and a leader's limit is set on their role. A manager runs the program but does not accept risk: acceptance belongs to those who lead.

**Nothing changes unnoticed.** Every change is an event in the history: who, when, what it was, and what it became. The events are chained, each to the one before, so a change made behind RiskWren's back is found by `riskwren verify`. The database refuses to alter or delete them. A record can be shown as it stood at the end of any day.

**Things stop counting on their own.** Evidence counts until its date. A test result holds for as long as a rating does, twelve months by default. An exception ends on its date. An acceptance expires. When one of these lapses, what rested on it moves back, and its owner is told before it does.

**Restricted means restricted.** A record marked restricted is known only to whoever made it, its owners, the stewards, leaders, and managers who cover its unit, auditors, and administrators. Lists, search, counts, and the history leave it out for everyone else. An incident case can be closed further, to the people named on it: then even auditors and administrators do not see it unless they are named. Internal audit's work on an engagement is its team's alone until the report is issued.

**Others tell it, or ask it.** Another system may report a check onto a control, ask whether a supplier is in good standing, or be told when something happens. What it reports counts only once a person confirms it. An assistant may read what it is allowed to and draft, but a draft becomes a record only when a person saves it. See [Other systems and assistants](other-systems.md).

## The program

The **program** is the organization's own rules, kept in RiskWren. It holds:

- the families of risk, and the appetite for each;
- the scales of likelihood and impact, and the matrix that turns them into a rating;
- how often each kind of thing is reviewed;
- the vocabularies: kinds of control, sources of issues, data classes, and so on;
- who may accept what;
- the tiers for third parties, and which information needs which agreements.

Most of it is edited under **Admin → Program**; the rest, such as the number of levels on a scale or the tiers, changes with a program pack. It ships with a default written for a research institute with a clinic, and with starters for an academic medical center, a university, and a nonprofit. Changing it changes what is worked out from it: a new appetite re-reads every open risk's standing. See [Shape the program](running-the-program.md#shape-the-program).

The **configuration file**, `riskwren.toml`, is different: it says how the server runs (its address, its database, sign-in, email, the optional assistant), not how the organization judges risk. See [Configuration](configuration.md).

## What people see each day

- **Home** is the list of what each person owes, most urgent first. Stewards, leaders, managers, auditors, and administrators also see figures above it, such as risks needing a decision and actions overdue, for everything they may see. See [Home](the-register.md#home).
- **The bell** counts what has been assigned to them or decided for them since they last looked. See [Notices](issues-and-exceptions.md#notices).
- **Email**, if the organization sets it up, sends the same notices, as they happen or once a day, as each person chooses.
- **Reminders** come two weeks before something is due and again when it is late. An action, an issue, or a campaign's request that stays late goes to the unit's steward, and then to its leader. See [Reminders](running-the-program.md#reminders).

## Words

The words RiskWren uses, with the meaning it gives them. An organization may rename the kinds of record and units under **Admin → Appearance → Your own words**; the meanings stay the same.

| Word | Meaning |
|---|---|
| **Acceptance** | A dated decision by someone with the authority to live with a risk above appetite, for a reason, until a date |
| **Action** | Something a named person must do by a date, from a treatment plan, an issue, or an incident |
| **Appetite** | The highest residual rating the organization is content to live with in a family of risk |
| **Assessment (of a risk)** | A dated judgment of likelihood and impact, with a reason. Never edited, only superseded |
| **Assessment (of a scope)** | A planned set of tests of a scope's controls against a framework |
| **Attestation** | A dated statement by a named person that something is true. It is evidence, not a test |
| **Baseline** | A selection of a framework's requirements, such as NIST SP 800-53's moderate baseline, used as a scope's starting point |
| **Campaign** | A request to a set of people to answer a questionnaire or acknowledge something by a date, followed until they have |
| **Criticality** | How much the organization depends on a process, system, third party, or site |
| **Data class** | How sensitive information is, from public to restricted |
| **Draft** | A risk, an issue, or a control proposed by an assistant or another system, made into a record only when a person saves it |
| **Engagement** | One piece of internal audit's work, from planning through fieldwork to its report |
| **Evidence** | A file, link, note, or attestation that supports a control, a test, or a closure, counting until a date |
| **Exception** | An approved, time-limited departure from a control, a requirement, or a policy |
| **Framework** | Any source of requirements: a standard, a regulation, an agreement, an internal policy |
| **Implementation** | How one control is done within one scope: in place, partly, planned, or not applicable, and whether it is the scope's own, inherited, or shared |
| **Inherited control** | A control one scope runs and another relies on, such as central backup; the provider's test moves both |
| **Issue** | Something wrong that must be put right, with a severity, a due date, and actions; closed only when someone else confirms it |
| **Readiness** | Where each requirement of a scope stands: verified, in place, planned, a gap, failing, or excepted |
| **Requirement** | One thing a framework asks for, identified by its code |
| **Restricted** | A record known only to its owners and the few roles that must see it |
| **Scope** | A boundary (units, systems, information) held to one or more frameworks |
| **Standing** | Whether a risk is in order: within appetite, being treated, accepted, needing a decision, not assessed, or closed |
| **Statement of applicability** | For a scope and a framework, which requirements apply, which are left out and why, and the controls that answer each |
| **Tier** | A third party's level of scrutiny, worked out from what it reaches and handles, which sets how often it is reviewed |
| **Unit** | A part of the organization: a division, department, lab, clinic, or office |
