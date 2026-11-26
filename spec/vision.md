# Vision

## The idea

A wren is one of the smallest birds in the garden and one of the most watchful. It works close to the ground, knows every gap in the hedge, and raises the alarm long before anything larger has noticed.

That is the kind of risk and compliance program most organizations need and few have. The usual picture is different. The risk register is a spreadsheet that one person understands. Each regulation has its own checklist, so the same control is described five ways and tested five times. Evidence is gathered in a panic the month before an audit. Findings are tracked in email until they are forgotten. And the people who actually run the controls, in labs, clinics, and offices, see the whole thing as paperwork that belongs to somebody else.

The systems sold to fix this are built for the largest enterprises. They take a year and a team of consultants to install, they need full-time administrators, and the people on the front line still go back to their spreadsheets.

**RiskWren is the smaller, sharper alternative.** It gives an organization one connected record of what it has, what could go wrong, what it must comply with, what it does about both, and the proof. It runs on one machine, works on its first day with content already loaded, asks the least it can of busy people, and keeps a history an auditor can rely on.

## Positioning

> RiskWren is an open system of record for governance, risk, and compliance: one connected register of risks, controls, obligations, and evidence, with the effort spent in proportion to what is at stake.

RiskWren is a records and workflow product. It manages the *program*: identifying and assessing risk, mapping obligations to controls, testing those controls, holding the evidence, following issues to closure, and reporting to leadership. It is **passive by design**: everything it knows comes from people, from documents, and from results that another system chooses to send it. It never scans a network, reads a log, or needs access to anything else an organization runs.

## Who it is for

RiskWren is built first for **research and health organizations that are not large corporations**: independent research institutes, academic medical centers, universities, teaching hospitals, and the nonprofits around them. These organizations share a shape that general-purpose tools handle poorly:

- **Many semi-autonomous groups.** Dozens or hundreds of labs, cores, clinics, and departments, each with its own funding, its own systems, and a leader who is used to deciding things. Risk is owned where the work is, not at the center.
- **Obligations from every direction.** Health privacy and security rules, research regulations, the terms of every grant and data use agreement, funder security requirements for controlled data, payment card rules in the gift shop, and accreditation standards, all landing on the same small set of people.
- **Shared services and inherited safeguards.** A central team provides the network, identity, backup, and facilities that a hundred local systems rely on. Whether a lab's system is compliant depends on controls somebody else runs.
- **Mission risk that is not financial.** A failed freezer, a lapsed protocol, a breach of participants' trust, or a lost decade of data cannot be expressed as a loss figure, and a tool that thinks only in currency misses what matters most.
- **A small risk and compliance team.** Often two to five people covering enterprise risk, compliance, security assurance, and vendor reviews between them, with no budget for a platform administrator.
- **No shareholders.** The financial-reporting control regimes that commercial tools are organized around apply only by analogy; stewardship of grant funds matters far more.

**The security team comes first.** In most organizations of this shape, the people who adopt a system like this first are the chief information security officer and the security assurance team: they already hold the frameworks, run the assessments, chase the findings, and answer the questionnaires. So the path they walk every week has to be right before anything else is: a security framework mapped to controls, a scope for each boundary, controls tested once, evidence that goes stale by itself, findings followed to a closure someone else confirms, exceptions that end, and one page that says where all of it stands. The rest of a risk and compliance program is built around that path and not instead of it.

Nothing in RiskWren is specific to research or to health care, though. The taxonomy, scales, frameworks, cadences, and vocabulary are all configuration, and any organization that wants a lightweight, self-hosted risk and compliance system can adopt it.

| Persona | What they need from RiskWren |
|---|---|
| **Staff member** | To read the policies that apply to them, confirm they have, and report a concern without knowing who to tell |
| **Risk, control, or system owner** (the first line) | One list of what they owe: a risk to re-assess, a control to attest, evidence to renew, an action to finish. Each done in minutes, without training |
| **Lab manager or unit steward** | A view of their unit's risks, systems, and open items, and a simple way to confirm the picture is complete |
| **Division or department leader** | Their unit's top risks and overdue items on one page, and a clear record when they accept a risk |
| **Risk manager** (the second line) | A register they can trust, a scoring method they control, campaigns that chase themselves, and a heat map that explains itself |
| **Compliance or security assurance lead** | Each framework's requirements mapped to controls that are tested once; a scope for every boundary that must comply; gaps and stale evidence surfaced without asking |
| **Assessor** | A work queue of controls to test, the procedure and the previous result beside each, and a place to record what was examined and found |
| **Vendor and privacy reviewers** | Third parties ranked by what they touch, questionnaires that send themselves, agreements that warn before they expire |
| **Internal auditor** (the third line) | Read-only access to everything with its history, and later the audit plan, workpapers, and findings in the same record |
| **Executive, board, or audit committee member** | The handful of risks that matter, whether each is inside appetite, what changed since last quarter, and how compliant the organization is against each obligation |
| **Administrator at an adopting organization** | A system that installs in minutes, signs people in with the identity they already have, carries the organization's own name and colors, and keeps its data portable |

## What makes RiskWren different

These are the product bets. Each is a deliberate design choice.

1. **One connected register, not a suite of modules.** Units, processes, systems, vendors, risks, controls, requirements, evidence, issues, and actions are separate records with typed links between them. A control is described once, reduces the risks it is linked to, satisfies every requirement it is mapped to, and is tested once. A failed test is visible on every risk and every framework that leaned on it. Any record is one click from its neighbors.

2. **Working on the first day.** A new installation already has a risk taxonomy, a scoring method with defined scales, a library of common controls written in plain words, and public frameworks mapped to those controls. An existing risk register or control list comes in from a spreadsheet with a dry run that reports every problem by row. Nobody configures a data model before they can record a risk.

3. **Built for the first line.** Most of the people who use a risk system do so a few times a year and did not ask to. RiskWren gives each of them one page of what they owe, overdue first, and makes each item a short, guided task. If owners would rather answer in a spreadsheet, the design has failed.

4. **Proportionate by construction.** How much is at stake decides everything downstream: how often a risk is revisited, how deeply a control is tested, how fresh its evidence must be, and who may accept what remains. A low risk costs minutes a year. Depth is spent where harm is possible.

5. **Built for federated organizations.** Units form a hierarchy with as many levels as the organization has. Every record belongs to a unit and has named owners. A central service provides a control once, and the scopes that rely on it **inherit** it, each seeing whose control it is and whether it is working. Leaders see roll-ups; stewards see their own unit; nobody at the center retypes anyone's records.

6. **Obligations are wider than regulations.** A framework in RiskWren is any source of requirements: a federal rule, a security standard, a grant's terms and conditions, a data use agreement, a sponsor contract, an internal policy. Each is broken into citable requirements, applied to a named **scope**, and answered by the same controls.

7. **Rating and standing are different things.** A critical risk that is well controlled and inside appetite is the program working, not a problem. RiskWren always shows *how much is at stake* and *is this in order* as two separate signals, and never lets a color do the work of both.

8. **Show the reasoning; people decide.** A rating shows the scale definitions and the judgment that produced it. A suggested residual rating shows which controls moved it and how well each is known to work. A readiness figure opens to the requirements and tests behind it. Rules propose and route; named people assess, approve, and accept.

9. **Unknown is not zero.** A control nobody has tested is shown as untested, not effective. Evidence that has expired no longer counts. Coverage and freshness are measured and displayed, never assumed.

10. **Evidence and an unbroken history.** Every change to every record is written to an append-only log, chained by hash, with who, when, and what changed. Assessments, acceptances, and test results are never edited, only superseded. Any record, and the whole register, can be shown as it stood on any past date.

11. **Passive by design.** No scanners, collectors, or agents, and no access to anything else on the network. That makes RiskWren safe to deploy anywhere and quick to approve, which matters for a system that holds a map of an organization's weaknesses. Other tools can push results to it; it never goes looking.

12. **Open, portable, and yours.** Apache 2.0 licensed, with no paid edition and no license keys. Runs on a laptop with SQLite or on a server with PostgreSQL. Everything exports in open formats, including the open security assessment language used across United States federal programs. Name, logo, colors, and wording are settings, so an adopting organization presents it as its own.

## Scope

### RiskWren does

- Keep an inventory of the things risk attaches to: units, processes, systems, information, sites, and third parties, with ownership, criticality, and links
- Hold a risk register with a taxonomy, a configurable scoring method, inherent, residual, and target ratings, appetite, and named owners
- Run risk assessments from the top down and from the bottom up, including self-assessment campaigns to owners
- Record how each risk is treated, track treatment plans to completion, and record named, time-limited acceptance of what remains
- Hold a library of controls, described once, linked to the risks they reduce and the requirements they satisfy
- Load frameworks, regulations, contracts, and policies as sets of citable requirements, with crosswalks to controls
- Define scopes that must comply, tailor what applies to each, and let a scope inherit controls that another provides
- Plan and record control tests and assessments, with procedures, results, reviewer sign-off, and evidence
- Hold evidence (files, links, attestations) with owners and expiry dates, and say when it has gone stale
- Turn failed tests, audit findings, incidents, and gaps into issues, and follow each through an action plan to validated closure
- Manage exceptions with compensating controls and expiry
- Manage the policy lifecycle: draft, review, approve, publish, acknowledge, revisit, retire
- Assess and monitor third parties, their agreements, and what each agreement covers
- Take reports of incidents and concerns from anyone, and run restricted cases where sensitivity demands it
- Record business impact, continuity plans, and exercises
- Support internal audit: the audit universe, the plan, engagements, workpapers, and findings
- Track indicators against thresholds, and report risk and compliance posture to leadership with figures that explain themselves
- Produce a complete, verifiable package for any scope, risk, or audit

### RiskWren does not (non-goals)

- **Discover or monitor anything by scanning.** No network inspection, log ingestion, endpoint agents, vulnerability scanning, or cloud account crawling. It records the results of tools that do.
- **Enforce anything.** It does not block access, change configurations, or sit in the path of any transaction.
- **Replace other systems of record.** It is not a configuration database, a ticketing system, a contract system, a document management system, a grants system, an ethics board system, a conflict-of-interest system, or a learning system. It links to them by reference.
- **Run a general ledger of controls over financial reporting.** It can hold financial controls like any others; it has no certification workflow built around a public company's reporting cycle.
- **Take in and review proposed uses of artificial intelligence.** AI risk is a category of risk here like any other; an intake and review process for AI use is a different product.
- **Hold the sensitive data it describes.** Records describe systems and data; they never contain patient, participant, or other regulated data. Incident and case forms say so where free text is requested.
- **Give legal advice or certify compliance.** Framework content is a working aid. Conclusions belong to the people who sign them.
- **Require an AI provider.** Optional assistance may come later; the core never depends on one.

## Guiding principles

1. **The least that proves it.** Every screen is judged by how little it asks of an honest person to leave a trustworthy record.
2. **Describe once.** A control, a system, or a vendor is described in one place and referred to everywhere else. Anything RiskWren already knows is never asked again.
3. **Show the reasoning.** A rating, a readiness figure, or a due date always shows the rule and the judgments that produced it.
4. **People decide.** Rules propose and route; named people assess, approve, and accept risk.
5. **The record is permanent.** History is append-only. Corrections are new entries, never erasures.
6. **Stand alone.** Every capability works on one machine with no other system. Integrations are optional additions.
7. **Few dependencies, well chosen.** Each runtime dependency is justified in a decision record. The browser gets no frameworks.
8. **Generic by default.** Nothing in the code or documentation assumes a particular institution. Vocabulary and branding are configuration.
9. **Accessible and fast.** WCAG 2.2 AA, keyboard-friendly, light and dark themes, and pages that load instantly on modest hardware.
10. **Unknown is not zero.** A missing answer is shown as missing, an untested control as untested, and stale evidence as stale.

## What success looks like

- **Wave 1:** A risk manager installs RiskWren, signs in, and within an afternoon has the organization's units, its key processes and systems, and a risk register with ratings, linked controls, and treatment plans. An owner opens one page, sees what they owe, and finishes it. Leadership sees a heat map in which every cell opens to its risks, and every change is in the history.
- **Wave 2:** A compliance lead loads a framework, sees it already mapped to the organization's controls, defines the scope that must meet it, tests each control once, and watches every framework that shares the control update. Gaps become issues with owners and dates.
- **Wave 3:** The program keeps itself current. Risks are re-assessed on schedule, owners attest to their controls, evidence is renewed before it goes stale, and nothing overdue goes unnoticed.
- **Wave 6:** A leader opens one report and sees the top risks, appetite, compliance posture, and what changed since last quarter, and an auditor exports a complete, verifiable package for any scope.
- **v1.0:** Another organization adopts RiskWren, re-brands it, connects single sign-on, loads its own obligations, and runs its risk and compliance program on it without help from the original team.
