# Changelog

RiskWren follows semantic versioning. Each wave of the [roadmap](spec/roadmap.md) is a
release. Before 1.0, a release may contain breaking changes; they are listed under
**Breaking**.

## 0.8.0 (unreleased)

Wave 8, *Incidents and resilience*.

### Added

- **Incidents:** anyone signed in reports an incident, a near miss, or a concern in one short
  form, under **Incidents → Report something**. A report is seen by its reporter, those who
  handle it, those who triage for its unit (managers, and its unit's assessors), the leaders
  and stewards of its unit, and those who read everything; its reporter sees what they
  reported, where it stands, and what is said to them, not the handling. Triage gives it a
  category, a severity, the records it concerns, and a handler, who handles it on their home
  page until it is closed. A new guide, **Incidents**.
- **Restricted cases:** an incident can be kept to those named on it, its handlers, and its
  reporter. Nobody else learns that it exists, those who read everything included: lists,
  search, counts, the history of everything, and their notices leave it out.
- **Breach assessment:** whether an incident involving protected information must be
  notified: when it was discovered, what was involved, the four factors, any exception, and the
  conclusion, with the rules that apply. What each rule requires, to whom, and by when follows
  from it (the HIPAA Breach Notification Rule, as a covered entity or a business associate,
  the FTC Safeguards Rule, DFARS 252.204-7012, and any state's law or contract named), each
  notification is recorded, and what is still to send waits on the handler's home page.
- **Privacy impact assessments:** a built-in questionnaire, asked by a new kind of campaign of
  every process and system whose data class the program's new `privacy` rule names, with the
  answers' concerns flagged, a review, and **Compliance → Privacy impact**.
- **Two frameworks, loaded on request:** the HIPAA Breach Notification Rule (45 CFR Part 164
  Subpart D) and the NIST Privacy Framework 1.0.
- **Reporting without a name,** closed until an administrator opens it under **Admin →
  Program → Who sees what**: a page at `/report` that needs no sign-in and keeps no account,
  name, or address, with a follow-up code shown once.
- **Business impact and recovery:** a process's business impact analysis (how its loss hurts
  over time, how soon it must be back, how much information it can lose, and the least it
  needs), what each system and service can deliver and what that rests on, and every shortfall
  between them. A process's **Business impact** tab, a system's or service's **Recovery** tab,
  and **Reports → Resilience**.
- **Who reads the leadership reports is the program's choice,** under **Admin → Program → Who
  sees what**: only those who lead the whole organization, anyone whose role covers the whole
  organization (the default), or every leader and manager, with named readers on top. A reader
  who may not see a record a report names sees where it stands but not what it is.

### Changed

- **A security leader who assesses everywhere now reads the leadership reports,** as does
  anyone else whose role covers the whole organization. Choose **Nobody else** under
  **Admin → Program → Who sees what** to keep them to those who lead the whole organization.
- **Reports → History leaves out restricted incident cases** for managers, auditors, and
  administrators who are not named on them. Their events stay in the chain that
  `riskwren verify` checks.
- **Protected information** is a new vocabulary, and the program pack has a `privacy` rule.
- **Incident categories** are a new vocabulary, editable under **Admin → Program →
  Vocabularies**. The menu has a new group, **Incidents**.
- In the session's `permissions`, `reports` is now `oversight` (the audit universe and plans),
  and `leadership` says whether the person reads the leadership reports.

## 0.7.0 (2026-11-27)

Wave 7, *Audit*: the third line's own workspace on the same record, without compromising its
independence. The audit universe ranks every unit, process, system, third party, and scope
from the register, with its working shown. A period's plan is approved by a named person and
tracked against. Engagements move through planning, fieldwork, and reporting, with workpapers
reviewed and signed off by someone other than their preparer, and their work is the team's
alone until the report is issued. Requests to the audited are answered with evidence already
on file. Findings are issues in the one register, which internal audit confirms closed. A
report goes to the audit committee, and an outside auditor can be given one engagement or one
scope, read-only, with every look recorded.

### Upgrading from 0.6.0

Run `uv sync`, then `uv run riskwren db upgrade` (migrations 0035 to 0038). Every row is
kept, and the history still verifies. A few things look different afterwards:

- **The menu has a new group, Audit,** with Universe, Plans, and Outside access, for those who
  read everything and those who lead the whole organization. Only auditors change them.
- **The universe is there at once,** worked out from the register; nothing needs entering. Every
  thing in it counts as never audited until audit records an earlier audit or reports one.
- **Closing an issue raised by internal audit is confirmed by an auditor,** not by the second
  line. Issues raised before 0.7.0 are unchanged. The route that confirms a closure is now open
  to everyone signed in, and the issue decides who may.

### Added

- **The audit universe:** every unit beneath the organization, and every process, system,
  third party, and scope in use, ranked from the register (its worst open risk, risks above
  appetite, open issues, criticality, a scope's readiness, and how long since it was last
  audited), with each part of the ranking shown. An auditor may move a thing with a reason,
  record an audit from before RiskWren, or leave a thing out. **Audit → Universe**.
- **Audit plans:** a period's engagements, each on one thing with its reason, approved by an
  auditor other than the drafter or by a leader of the whole organization, then tracked
  against; engagements dropped with a reason. **Audit → Plans**.
- **Engagements and workpapers:** a team and a lead; planning, fieldwork, reporting, and
  reported, with a summary and an opinion; a program of work whose workpapers say what was
  done and found with the evidence, are reviewed with notes, and are signed off by someone
  other than their preparer. Until the report is issued, the work is its team's alone, and
  the history keeps its words out.
- **Findings and follow-up:** a finding is an issue in the one register, from its engagement,
  with management's action plan as its actions; internal audit, not the second line, confirms
  it closed. **The committee report:** a plan's engagements with their opinions, findings by
  severity, and what is past its date.
- **Outside auditors:** a link for someone outside the organization to one reported
  engagement or one scope, read-only, for at most 90 days, kept only as a digest, withdrawn at
  will, and every use recorded in the history. **Audit → Outside access**.
- **Requests to the audited:** what an engagement needs, asked of one person by a date and
  on their home page, answered with words and evidence, offered first from what is already on
  file, and accepted by the team or sent back with what is still needed.

## 0.6.0 (2026-11-27)

Wave 6, *Insight*: the record read back to those who answer for it. Measures say what they
count and open the list behind each figure, with a trend from a daily snapshot. The portfolio
cuts risk and compliance by unit, family, framework, and third party over a period. A
leadership report is frozen when issued, with a fingerprint the history records, and reopens
exactly as it was. Any record, and the register, can be seen as it stood on a chosen day. A
scope, a risk, or a third party is packed as a dossier whose manifest proves nothing was
changed, and a scope's security plan prints in the customary order and is written in OSCAL.
Scenarios, estimates in ranges with a simulation, and the bow-tie put a risk in a story, in
numbers, and in a picture.

### Upgrading from 0.5.0

Run `uv sync`, then `uv run riskwren db upgrade` (migrations 0032 to 0034). Every row is
kept, and the history still verifies. A few things look different afterwards:

- **The scheduler has a new job, Measures,** which takes the organization's figure for each
  measure every six hours, keeping one a day. Their trends start on the day of the upgrade.
- **Reports has five new pages:** Measures, Portfolio, Leadership reports, As of a date, and
  Check a dossier; and **Risks** has Scenarios. Leadership reports are read by those who read
  everything and by those who lead the whole organization; a unit's leader does not see them.
- **Every record's page has As of a date,** and scopes, risks, and third parties have
  **Dossier**. A risk has two new tabs, **Bow-tie** and **In numbers**, and a scope's
  Requirements tab downloads its **security plan** and its plan in **OSCAL**.
- `riskwren verify` checks leadership reports as well as documents, and there is a new
  command, `riskwren check-dossier`.

### Added

- **Measures:** a catalog of defined measures of risk, treatment, compliance, issues, and third
  parties, each saying what it counts and among which records, with its figure as the reader
  may see it, opening the list it counts. A daily snapshot, taken by the scheduler, gives each
  a trend over the last quarter. **Reports → Measures**, for managers, auditors, and
  administrators.
- **The portfolio:** the register and compliance by unit, category, framework, and third
  party over the last quarter, half year, or year, and issues by root cause, source, and age
  with a year month by month. Every figure opens its list. **Reports → Portfolio**.
- **Leadership reports:** a periodic report of the top risks and how they moved, appetite,
  posture by framework, the third parties with most at stake, the measures against the last
  report, and what is overdue. Issued, it is frozen with a SHA-256 fingerprint that the
  history records too, and reopens exactly as it was; the page says whether the fingerprint
  still verifies. **Reports → Leadership reports**, read by those who read everything and
  those who lead the whole organization, and issued by managers.
- **As of a date:** any record, and the register of risks, controls, issues, exceptions, or
  third parties, as it stood at the end of a chosen day, rebuilt from the history, with what
  has changed since. **Reports → As of a date**, and **As of a date** on every record.
- **Dossiers:** a scope, a risk, or a third party with everything known about it, as one ZIP
  with a page to read and print and a manifest of every file's SHA-256 whose fingerprint the
  history records. **Reports → Check a dossier** and `riskwren check-dossier` check one.
- **The security plan and OSCAL:** a scope's system security plan in the customary order, as a
  page that prints by itself, and in OSCAL 1.1.2; its plan of action and milestones in OSCAL.
- `riskwren verify` also checks every leadership report against the fingerprint the history
  took when it was issued.
- **Scenarios:** what might happen, told on purpose, with what it assumes, the risks and
  processes it touches, and what was concluded. **Risks → Scenarios**.
- **Estimates in ranges:** a risk's frequency and loss as low, likely, and high values, with
  a reproducible simulation of a year's loss and its assumptions in words; a scenario adds
  up its risks'. A risk's **In numbers** tab.
- **The bow-tie:** a risk's causes, preventive controls, event, mitigating controls, and
  consequences on one diagram, with a table behind it. A risk's **Bow-tie** tab.
- **Lists cut to a period:** risks by when they were added, issues by when they were raised
  or closed, issues by root cause, and issues and exceptions about a framework's requirements.

## 0.5.0 (2026-11-27)

Wave 5, *Third parties*: who the organization depends on, what each can reach, and whether
the paper covers it. A third party has services, each with the systems it reaches and the
information it handles, and a tier set by the program's rules from a few questions the
inventory mostly answers. A security questionnaire chosen by the tier is sent to its contact
through a link that needs no account and reaches nothing else. Reports and certificates are
read for what they cover and what they leave to the organization. Wherever regulated
information is shared and no agreement of the kind the program requires covers it, every
record involved shows a stop. Findings, review again, offboarding, and subcontractors follow
the relationship over time.

### Upgrading from 0.4.0

Run `uv sync`, then `uv run riskwren db upgrade` (migrations 0027 to 0031). Every row is
kept, and the history still verifies. The upgrade loads the questionnaire tiering asks and the
three due diligence questionnaires. A few things look different afterwards:

- **Third parties have a menu of their own,** with Services, Due diligence, and Coverage;
  Inventory keeps processes, systems, and information.
- **Every third party is missing a tier** in Tidy until it is tiered, and has no review date
  until then.
- **Coverage shows stops as soon as information is linked as shared with a third party** and
  no agreement says it is with that third party. Agreements made before 0.5.0 name their
  parties in words only: say who each is with, on its page, and the stops it meets go.
- **The program has two new tables,** the tiers and the sharing rules, taken from the default
  program until the organization sets its own, and a new kind of link, *subcontracts to*.

### Added

- **Services** (`SVC`): what a third party provides, in the inventory beside it, with the
  systems each reaches and the information each handles. Processes rely on services, and
  systems are supplied by them. A third party's page lists its services, and both are in the
  Connections picture.
- **Tiering.** A few questions, answered partly from the inventory, give a third party's tier
  by the program's rules, with each reason that applies. Those who keep a third party, and
  assessors, tier it. The tier recorded is a judgment by a named person: a different tier from
  the rules' needs a reason, and both are kept. Lists show,
  sort, and cut by tier, and Tidy lists third parties not yet tiered.
- **Contacts** at third parties: the people who can be asked. They are not accounts.
- **Due diligence reviews** (`DDR`): a questionnaire, the one the third party's tier names, sent
  to a contact through a link that needs no account. The link is a long random token kept only
  as a digest, carried after `#` so that no server logs it, reaching that questionnaire and
  nothing else, and ending when it expires, is withdrawn or replaced, or has been used. The
  contact can save to finish later. The answers the questionnaire marks as concerns are listed
  first, and the reviewer records the conclusion: approved, approved with conditions, or not
  approved. Answers to read, and answers late, wait on the review's owners' Home.
- **Three due diligence questionnaires,** short, standard, and full, written for organizations
  in the United States. A choice or a yes-or-no question can mark an answer as a concern.
- **A link sent by email is cleared once sent,** so the token is not kept in the outbox.
- **Assurance documents:** reports and certificates as evidence of a third party, with their
  period and expiry, kept to those who keep it and assessors. A review of each records what it
  is, its opinion, the services it covers and does not, what is carved out, each exception and
  whether it matters here, and each responsibility it leaves to the organization, joined to the
  control that does it, which lists it. A contact can send reports through the review's link.
- **Who an agreement is with:** the third parties it binds, beside the words of its parties.
  An agreement can cover services as well as systems, information, and scopes, and a third
  party's page lists the agreements it is party to.
- **The stop for uncovered sharing.** The program's rules say which kinds of agreement
  information needs when it is shared with a third party (a business associate agreement for
  patient records handled for the organization, a data use agreement for controlled-access
  data, and so on). Where information is shared, directly or through a service, and no open
  agreement of a required kind with that third party covers it, the information, the third
  party, and the service each show the stop, and **Third parties → Coverage** gathers them.
- **Findings from a review** are issues about the third party, found by review, naming the
  review they came from. An action on one can be done by the third party's contact, followed
  up by its owner here.
- **Review again** on the tier's cadence, from the last concluded review or from the first
  tiering, or at once when an event calls for it (an incident, a breach notice, a change of
  service or owner). A review due or late is on Home and in the reminders, and the list of
  third parties can be cut to it.
- **Offboarding:** ending a relationship opens a checklist (access removed, information
  returned or destroyed, agreements ended, an attestation recorded), and the third party and
  its services are retired when the last step is recorded.
- **Subcontractors:** a third party *subcontracts to* others, shown on both and in the
  Connections picture.
- **A Third parties menu,** with third parties, services, and due diligence, and a new guide,
  [Third parties](docs/third-parties.md).

### Changed

- A kind of link a release adds, or a pair of records it may now join, reaches an installation
  that has renamed its kinds of link.
- An answer to a questionnaire may be a contact's, given through a link, with no account.

## 0.4.0 (2026-11-27)

Wave 4, *Policy and obligations*: the organization's own word, and what it has promised
others. Policies, standards, procedures, and guidelines are written or linked here, approved
by named people, published as versions that never change, reviewed on a cadence, read in a
library on any device, and acknowledged by the people they apply to. Each is tied to the
controls it directs and the requirements it answers. Agreements carry their dates and the
terms they impose on the scopes that hold what they cover. A framework's new version is
loaded beside the old, and a scope moves to it when its keepers say so. Strategic objectives
and committee sessions connect the register to the organization's aims and its committees.

### Upgrading from 0.3.0

Run `uv sync`, then `uv run riskwren db upgrade` (migrations 0021 to 0026). Every row is
kept, and the history still verifies. The upgrade brings the publishers' mappings into the
frameworks already loaded: where each SP 800-53 Rev. 4 control went in Rev. 5, and the
SP 800-53 controls each SP 800-171 requirement comes from. A few things look different
afterwards:

- **The Policies menu** has **Policy library** for everyone and **Documents** for those who
  write and keep them. Nothing is in either until documents are added.
- **Compliance has Agreements, and Risks has Objectives**; **Reports has Committee
  sessions**. Each starts empty.
- **A framework page may suggest crosswalks.** Where a control is mapped to SP 800-171 or
  SP 800-53, the other is suggested from the publisher's mapping. Nothing is mapped until a
  person confirms it.
- **The program has a new cadence,** how often a document is reviewed: 12 months, until the
  organization sets its own.

### Added

- **Policy documents.** Policies, standards, procedures, and guidelines as records, each
  implementing one of its own kind or a broader one, with owners, a unit, and a history.
  A version is written here in a simple Markdown, linked to where the organization keeps it,
  or attached as a file.
- **Approval by named people.** A draft is sent to the people who must approve it, none of
  whom may have written or sent it. Each approves it or returns it with a reason; once all
  have approved, it can be published.
- **Published versions that never change.** A published version is numbered and supersedes
  the one before. The history keeps its fingerprint, and `riskwren verify` checks every
  published version against it.
- **Comparing versions,** side by side, with the words that differ marked.
- **Review dates.** Each document is reviewed on the program's cadence (12 months as
  shipped) or its own. A review that is due shows on the document, on its owners' Home, and
  in the reminders; it is recorded as kept, or a new version is started.
- **Who a document applies to:** everyone, or the people in chosen units and those who
  hold chosen roles.
- **The policy library.** Everyone reads the published documents that apply to them, or
  every one they may read, found by their words, and laid out for a phone.
- **Acknowledgment.** A document can ask the people it applies to to say they have read it.
  Each acknowledgment is of a version; a new version asks everyone again unless its author
  says the change does not need it. Its page shows who has and who has not, by unit and by
  person, and what someone still has to acknowledge is on their Home.
- **Acknowledgment campaigns** ask those who have not acknowledged a document by a date, with
  reminders and coverage by unit.
- **What a document governs:** the controls it directs and the requirements it answers,
  shown from each side. A requirement lists the published documents that answer it beside
  its controls, and a control the documents that direct it.
- **Exceptions to a document,** asked for by a unit's steward, leader, or manager and
  decided by a leader or manager of the unit that keeps the document. They end by their
  dates like every exception.
- **Documents in the web of records:** in the Connections picture, in search, in Tidy (a
  policy, standard, or procedure that governs nothing is listed as missing it), and with
  what each governs in the export of the document list.
- **Agreements** (`AGR`): awards, data use agreements, business associate agreements,
  contracts, and the like, with their parties, dates, notice periods, and what they cover.
  The framework an agreement imposes is held by every scope that holds what it covers, and
  is said to be because of it; covering less, or closing the agreement, takes it away.
- **Warnings before an agreement's notice date and its end,** further ahead than other
  reminders, on its owners' Home and under the bell. One that has ended stays open, and goes
  up to the steward and the leader, until it is renewed or closed.
- **New versions of a framework, loaded beside the old.** What changed is listed by code
  (changed, with the words that differ; added; withdrawn, with where each went), with what
  uses the old version. Nothing changes until a scope is moved; then its decisions and
  exceptions go with it where the code is unchanged, and the organization's crosswalks and
  documents are carried across. A framework of your own can start a new version, and a
  pack can be loaded from a file.
- **NIST SP 800-53 Rev. 4,** with its Low, Moderate, and High baselines, ships to be loaded
  when a program or an agreement still names it; Rev. 5 records where 179 of the 182 Rev. 4
  controls it withdrew went.
- **Crosswalks suggested by a publisher's mapping:** SP 800-171 Rev. 3 names the SP 800-53
  controls each requirement comes from, so a control mapped to one is suggested for the
  other. A person maps each suggestion, or sets it aside.
- **Strategic objectives** (`OBJ`). A risk names the objectives it threatens, and each
  objective shows exactly the risks that name it, with how each stands.
- **Committee sessions** (`SES`): an agenda drawn from the register, the decision taken on
  each item, and the minutes. A decision shows on the record it was about, and its owners are
  told.
- **A new guide, [Policies](docs/policies.md),** and new sections in the others on
  agreements, framework versions, suggested crosswalks, objectives, and committee sessions.

### Changed

- A rule a later release adds to the program's cadences is taken from the default program
  until the organization sets it, so a table saved earlier still has it.
- A record of a kind a unit's leaders keep, such as an objective or a document, is no
  longer refused for its unit when a leader saves it.
- Lists of agreements and objectives show those still in use unless asked; search finds
  them all.

## 0.3.0 (2026-11-26)

Wave 3, *Keeping watch*: a register that stays true without a central team chasing it.
People sign in with the identity they already have, the app knows what is due and says so,
owners are asked on a schedule to confirm what they own, a number that warns of a risk is
watched, and anything on record can be found, tidied, and passed on. The program itself is
edited in the app, with a preview of every risk a change would move.

### Upgrading from 0.2.1

Run `uv sync`, then `uv run riskwren db upgrade` (migrations 0014 to 0020). Every row is
kept, and the history still verifies. The upgrade loads the four built-in questionnaires.
Three things behave differently afterwards:

- **Reminders start.** The server now runs scheduled work, and the first pass tells people
  about everything already nearly due or late, once each. To hold that back, set
  `scheduler = false` under `[server]` before starting the server, and run
  `riskwren jobs run reminders` when you are ready. Nothing is emailed unless email is set
  up; see [Configuration](docs/configuration.md#email).
- **Disabling an account passes on what it owned.** Accounts already disabled are not
  touched: what they alone owned still shows on Home as needing an owner, and under
  Reports → Tidy.
- **A risk's rating follows the scoring method in force.** Nothing changes at upgrade. The
  next time a scoring method is published or a program pack is loaded, every open risk is
  read again from it.

Sign-in is unchanged: local accounts, until an administrator sets up single sign-on.

### Added

- **Optional single sign-on with OpenID Connect,** beside local accounts. A new installation
  still signs in with an email address and a password and needs nothing else. Naming an
  issuer and a client under `[sso]` adds a button for the organization's own sign-in, with
  the password form folded beneath it. It works with Microsoft Entra ID and any provider that
  follows the standard: the authorization-code flow with PKCE, and an ID token whose
  signature, issuer, audience, expiry, and nonce are all checked, with no new dependency.
- **Roles from the provider.** Under Admin, Single sign-on, an application role or a group at
  the provider gives a role here, for the whole organization or one unit, with a leader's
  limit, or membership of a unit. Those roles are set again at every sign-in; roles given by
  hand are left alone; the last administrator is never removed.
- **A way in that does not depend on the provider.** An administrator can always sign in with
  a password. Passwords can be kept for everyone, or for administrators only.
- **Admin, Single sign-on** shows what is set up, the redirect address to give the provider,
  and a check that the provider answers. `riskwren doctor` makes the same check.
- **Scheduled work.** The server brings risks up to date with the calendar, sends reminders,
  and sends email, by itself. Each job is claimed in the database before it runs, so several
  workers or servers run it once between them, and a server that was down catches up.
  Admin, Scheduled work shows each job and its runs and can run or pause one;
  `riskwren jobs` and `riskwren jobs run` do the same from the command line.
- **Reminders and escalation.** Whoever an action, risk review, issue, piece of evidence,
  acceptance, exception, or control test is waiting on is reminded two weeks before its date
  and the day after. Actions and issues that stay late go to the unit's steward after a
  week and its leader after three. Each is said once for a given date.
- **Key controls are tested more often.** Each control shows when its next test is due:
  twelve months after it was last rated, or six for a key control.
- **Optional email.** Naming an SMTP server under `[mail]` sends notices to people's inboxes
  as well as the bell. Each person chooses each notice as it happens, one summary a day, or
  none. Messages wait in an outbox in the database, so a mail server that is down is tried
  again, and turning email on does not send anyone their history. `riskwren mail test`
  and `doctor` check the settings.
- **Questionnaires as data.** A questionnaire is a document of sections and questions that
  can appear only when an earlier answer makes them relevant. Four are built in: control
  attestation, risk self-assessment, a unit completeness check, and a system security
  profile. Those who run the program edit them in the app, with the form as it will be asked
  shown as they go.
- **Versions that are never changed.** Saving changed questions publishes a new version, and
  an answer is always read against the version it was given to, so it reads as it was asked.
- **One condition language,** evaluated by the server and by the browser with the same
  rules, held together by shared test cases. No expression is ever run as code.
- **Campaigns.** An assessor or manager asks a set of people for one thing by a date: owners
  to attest that their controls still operate, owners to look again at their risks, stewards
  to check a unit's records, owners to describe how a system is protected, or owners for a
  named piece of evidence. A campaign is about a unit and what lies beneath it, or the
  controls a scope uses. Its page shows how far it has got, what was answered, coverage by
  unit, and every item, including anything with nobody to ask.
- **Answers that set things in motion.** An owner who says a control does not operate as
  described, that a risk's rating is no longer right, or that a unit's records need
  attention is heard by the people who have to act. An evidence request closes by itself
  when the evidence is attached.
- **Attestation, shown apart from a test.** What a control's owner last said of it is on the
  control with who and when. It never makes a requirement verified, and it takes one out of
  verified when the owner says, after a test, that the control no longer operates.
- **Indicators.** A number someone already reads, with which way is worse, a warning level,
  a limit, how often it is read, and where it is read from. Readings are recorded by hand,
  placed against the levels, charted, and given a trend. An indicator is linked to the risks
  it warns of and shown on each of them.
- **A breach is heard.** A reading past its limit tells the indicator's owners and the
  owners of each risk it warns of, and marks those risks' ratings as in doubt until they are
  assessed again. Readings that fall due are on Home and in the reminders, and the risk
  dashboard counts indicators by where they stand.
- **One search.** ⌘K and the box at the top of every page find records of every kind, and
  actions, by name, reference, summary, or what they are called elsewhere. Every word must
  be on the record. A search returns only what its searcher may open.
- **Saved views.** Any list as it is filtered and sorted can be kept under a name, and
  shared by those who look after a list. A view keeps the question, never the answer.
- **What a record is missing.** Each kind of record has a short list of expected facts. A
  record says which it lacks, any list can be cut to the records lacking one, and
  **Reports → Tidy** counts them, each figure opening the list it counts.
- **Likely duplicates.** Typing the name of a new record shows what it might already be,
  and Tidy lists pairs that look like one thing. Nothing is merged: a person decides, or
  says they are different things.
- **Passing on what a person held.** A page lists everything someone answers for, and an
  administrator, or a steward for their own units, passes it to someone else in one step.
- **The program is edited where it is used.** Admin → Program has editors for the risk
  categories, the scales and the matrix, appetite, the cadences, and the vocabularies.
  Categories are added, renamed, ordered, and retired; values of a vocabulary are renamed,
  ordered, added, and retired, and never re-keyed.
- **A preview before anything moves.** A change to the matrix, to appetite, or to the
  cadences is held as a draft. Preview lists every open risk whose rating, standing, or
  next review would change, and publishing changes exactly those. The preview is the change
  itself, made and then undone, so the two cannot disagree.
- **Risk analyses.** A structured assessment over a scope or a unit: each thing in it is
  taken against each threat from the risk library, and the answer is that it does not
  apply, that a risk on the register covers it, or that a risk is raised for the thing's
  owner. It closes when every question has an answer, and its report says what was
  considered, what was decided, and why.
- `scripts/dev_identity_provider.py`, a stand-in provider for trying single sign-on on a
  laptop. Its signing key is public; it is not for real use.

### Changed

- **Disabling an account leaves nothing without an owner.** What the person alone answered
  for (records, open actions, treatment plans, and what campaigns were waiting on them for)
  passes to the steward of its unit, who is told, until someone is named for good. Before,
  such records were shown as having nobody answering for them.
- **Publishing a scoring method re-reads the register.** Every open risk takes its ratings
  from the matrix now in force, then its standing and its next review, whether the method
  is published in the app or loaded from a program pack. Before, a risk kept the rating its
  last assessment gave it until it was assessed again. Each assessment still keeps the
  rating it was given and the version it was made under.
- **A list's search needs every word, in any order.** Before, the words had to appear
  together as typed.
- Risks are brought up to date with the calendar every hour by a scheduled job, as well as
  when the register is read.
- The accessibility audit and the screenshot capture start their demo on a port the
  operating system says is free. A fixed port could already belong to something else on
  the machine, which would then have been audited in its place.
- `riskwren doctor` reports how people sign in, whether email is set up, and whether
  scheduled work is being done.

### Known limits

- Single sign-on has been tested against the stand-in provider in
  `scripts/dev_identity_provider.py`, which speaks the same protocol, and not yet against a
  live Microsoft Entra ID tenant.
- Email has been tested against a test server, not through an organization's mail service.
- Two records that are the same thing can be found, and not yet merged.
- The questionnaire editor writes a condition with one part. A condition with several parts
  is written in the questionnaire's document.
- Who may accept what, the number of levels and ratings, and how much a control may reduce
  a rating are changed with a program pack, not in the app.

## 0.2.1 (2026-11-26)

The common controls reach the frameworks, and the documentation has a site with pictures.

### Upgrading from 0.2.0

Run `uv sync`, then `uv run riskwren db upgrade`. There are no migrations. The upgrade adds
the new controls to the library of common controls and refreshes its suggested mappings.
Nothing already on record is changed.

### Added

- **Nineteen security controls in the library of common controls,** which now has 75: access
  approved before it is given, accounts of one's own, screens that lock, remote and wireless
  access, screening and rules of use, encryption in transit, wiping devices and media, an
  inventory of systems and software, secure configuration, vulnerability scanning, logs kept
  and protected, incident reporting, recovery of systems, physical access, security policies,
  assigned responsibilities, reporting to leadership, risk assessment, and independent
  testing. Each is a sentence its owner would recognize, with suggested mappings.
- **A documentation site,** built from the guides in `docs/` by `scripts/site/build.mjs`
  (Node 22, no packages): a home page, a page for each guide, the changelog, an API
  reference written from the OpenAPI document, search, and light and dark themes from
  RiskWren's own design tokens. The build fails on a broken link, anchor, or picture, and
  the test suite runs it.
- **Pictures in the guides:** 29 screens of the demo organization, each by day and after
  dark, taken by `scripts/capture.mjs` and kept in `docs/img`.
- `scripts/site/audit.mjs` checks every page of the built site in both themes at desk and
  phone widths.

### Changed

- **The common controls reach much further into the frameworks.** 46 of them carry suggested
  mappings, up from 27. Between them they answer 80 of the NIST Cybersecurity Framework's 106
  outcomes (it was 34), 72 of the 97 requirements of NIST SP 800-171 (27), and 66 of the 91
  entries of the HIPAA Security Rule (24). An organization that adopts them starts with most
  of each framework answered. Controls already adopted are not changed: on each, the new
  mappings are offered as suggestions to take or leave.
- **Library risks suggest the new controls** where they bear on them: ransomware, a
  compromised account, a breach of health information, unsupported systems, exposed storage,
  and others.
- **The demo organization runs a believable security program.** Central information
  technology uses 35 controls and offers them; the clinic and the data enclave inherit most
  of what they need. The three scopes come out about half, three quarters, and half ready,
  with failures, plans, exceptions, and real gaps in each. The assessment tests 35 controls:
  32 results count, one waits for review, and the two controls not yet in place wait to be
  tested. The clinic leaves out the entries of the HIPAA Security Rule that do not apply to
  it, each with its reason.

### Fixed

- The private-terms hooks could not run in a worktree of a branch that does not carry the
  script, such as the published site. They now find it through the repository itself.

## 0.2.0 (2026-11-26)

Wave 2, *Compliance*: test once, satisfy many. Load a framework, see it mapped to the
organization's controls, define the scope that must meet it, test each control once, hold
the evidence, and follow what fails through an issue to a closure someone else confirms.
Readiness against every framework is worked out from tests and evidence, never typed in.

### Upgrading from 0.1.0

Run `uv sync`, then `uv run riskwren db upgrade` (migrations 0007 to 0013). Every row is
kept. The upgrade loads the four public frameworks and the mappings the common controls
carry to them. It does not map the controls you already have: each one that came from the
library offers its mappings on its Requirements tab.

### Added

- **Frameworks.** Four public frameworks load at installation, each built from its
  publisher's own machine-readable file and carried as published: the NIST Cybersecurity
  Framework 2.0, NIST SP 800-53 Rev. 5 (release 5.2.0) with the Low, Moderate, High, and
  Privacy baselines, NIST SP 800-171 Rev. 3, and the HIPAA Security Rule. Each shows its
  publisher, version, license, and source. Anyone signed in can browse a framework's tree,
  search it, narrow it to a baseline, and read any requirement in full (migration 0007).
- **Frameworks of your own.** An agreement's terms, a sponsor's requirements, or an internal
  standard is entered as a framework and behaves like any other. Requirements are added one
  at a time or pasted in after a dry run, and every change to them is in the history.
- **Crosswalks.** A control is mapped to every requirement it helps to satisfy, in any
  number of frameworks, from the control or from the requirement, in full or in part, with
  a note. Twenty-seven starter controls carry suggested mappings to the built-in frameworks:
  a control started from the library arrives mapped, and others are offered the suggestions.
  Each framework shows how many of its requirements have a control and lists those with
  none. Counts leave out controls their reader may not see (migration 0008).
- **Scopes.** A scope is a boundary that must meet one or more frameworks. It lists the
  units, processes, systems, information, and third parties inside it; starts from a
  baseline or from every requirement; and decides applicability a requirement at a time,
  with a reason required to leave one out. Each control it uses has an implementation:
  where it stands, who answers for it, and how it is done there (migration 0009).
- **Inherited controls.** A scope can offer its controls. Another scope inherits one whole,
  and it then stands wherever the provider's does, or shares it and records its own part.
  A provider cannot withdraw a control others rely on.
- **Statement of applicability.** For a scope and a framework: every requirement that
  applies, the controls that answer it there and where they stand, and every requirement
  left out with its reason, who decided, and when. It prints as a document.
- **Information assets.** A fourth kind of inventory record for a body of information:
  what it is, its data class, where it is held, who it is shared with, and under what
  agreement. Systems hold it, processes use it, and it is shared with third parties.
- **Evidence.** An item is a file, a link, a note of what was seen, or an attestation, with
  who collected it, the period it covers, and the date it holds until (a year after
  collection unless said otherwise). One item is attached to as many controls and scopes as
  it supports. Past its date it stays on the record, is shown as no longer counting, and
  its owner is reminded on Home a month beforehand (migration 0010).
- **Assessments and tests.** An assessment of a scope plans a test for each control the
  scope does itself: all of them, those that answer one framework, or a chosen few. Each
  test has a method, a procedure, and a person it is assigned to, who sees it on Home. A
  result records design and operation, what was looked at, what was found, and the evidence
  it cites. It is recorded by someone who does not own the control and counts once a second
  person confirms it; a result sent back is recorded again and the first is kept
  (migration 0011).
- **Test once.** A confirmed result becomes the control's rating. It shows in the scope that
  does the control, in every scope that inherits it, and in the suggested residual rating
  of every risk the control reduces. While a test result holds, a rating by judgment does
  not replace it.
- **Readiness worked out, never typed in.** Each applicable requirement of a scope is
  failing, a gap, planned, excepted, in place, or verified, as weak as the weakest control
  that answers it, and each control says in words why it is where it is. Verified takes a test found effective and
  evidence that still counts; when the evidence goes stale the requirement drops back by
  itself.
- **Issues.** One register of what is wrong, whatever found it: a test, a gap, an audit, an
  incident, a review, or somebody noticing. Each has a severity with a stated meaning and
  is due on a date that follows from it (30, 90, 180, or 365 days, a table the program can
  change). Moving the date needs a reason and is counted. A test that finds a control
  partly effective or ineffective opens an issue for the control's owners, filled in from
  the result and naming every scope that relies on the control (migration 0012).
- **Closure confirmed by someone else.** An issue is put right through actions, the same
  ones treatment plans use, on the one list of everything owed. Its owner proposes closure
  with what was done, a root cause, and evidence. An assessor or a manager who neither owns
  it nor proposed it confirms, or sends it back saying what is missing.
- **Exceptions.** A departure from a control, or from a requirement within a scope, is asked
  for with the reason and what makes up for it, and decided by a leader or manager who did
  not ask. It runs between two dates, at most twelve months apart by default. While it is
  in force a failing, missing, or planned state is shown as excepted with what lies
  underneath; the day after it ends, that state is back by itself. Carrying on is a new
  request.
- **Plan of action.** A scope lists the open issues that bear on it, its own and those of
  the controls it uses or inherits, most severe first, each with its milestones. It prints.
- **Notices.** Each person has a list of what has been assigned to them or decided for
  them, with a count in the top bar. Home gained issues to put right, closures to confirm,
  and exceptions to decide or renew.
- **Export.** Every list has an Export button: CSV or JSON, filtered as the page is, and
  holding only what the person may see. Each export is recorded in the history with who
  took it, how many rows, and under what filters. `GET /api/v1/exports/{list}`.
- **Import from a spreadsheet.** Processes, systems, third parties, information, risks, and
  controls are imported from CSV. The file's columns are matched to fields by their
  headings and corrected by hand; a dry run reports every problem by row; nothing is added
  unless every row can be. Each row is added by the same rules as one added by hand, in the
  importer's name. A CSV exported from one installation imports into another with its
  references kept. Ratings and other judgments are never imported.
- **Requirements from a spreadsheet.** A framework of the organization's own takes its
  requirements from a CSV of codes, titles, text, and parents.
- **External references.** A record can carry what it is called in other systems: an asset
  tag, a contract number, a ticket. It is found by them in search, and they are links
  where the system has an address pattern (migration 0013).
- **Compliance dashboard.** Beside the risk dashboard: each scope against each framework it
  is held to, open issues by severity and age, the longest overdue, what the controls'
  ratings rest on, evidence that still counts and that does not, exceptions waiting, in
  force, and ended, and assessments in progress, for the whole organization or one unit.
  Every figure opens the list that makes it. Home shows controls failing a test and
  issues overdue.
- **Connections.** Every record has a picture of what it is joined to: what it relies on
  and what relies on it, its risks, controls, scopes, evidence, issues, exceptions, and
  assessments. A neighbor can be opened in place or put in the middle, by mouse or
  keyboard, and a list beside the picture says the same in full.
- **History of everything.** Those who may read everything can browse every change in one
  place, narrowed by person, record, kind of record, and date.
- **More to filter by.** Issues by how long ago they were raised, exceptions ending within a
  month, and controls by what a test that still holds found. Issues can name security
  testing as what found them.
- **Safe file storage.** Files are stored by the SHA-256 of their content, outside anything
  the server serves. Their kind is judged by content, not name: PDF, common images, Word,
  Excel, and PowerPoint documents, and plain text, up to 25 MB; programs are refused. A file
  is only ever returned as a download that cannot run in the browser, to someone who may see
  the item, and each download is recorded in the history.
- **Framework packs.** A framework is one JSON document, checked whole before anything is
  loaded and refused whole if anything is wrong. Each pack declares what text it may carry,
  and a test holds every built-in pack to it. `riskwren frameworks list`, `show`, and `load`.

### Changed

- **Reports** has three pages: Compliance, Risk (the dashboard of 0.1.0), and, for those
  who may read everything, History.
- **A test outranks a judgment.** A control whose rating came from a confirmed test cannot
  be re-rated by judgment until that result is out of date. `POST /controls/{ref}/ratings`
  answers 409 meanwhile.
- **Actions belong to a plan or an issue.** The list of actions shows both, and an action
  in the API carries a `source` when it is an issue's.
- **Search** also finds a record by what it is called in another system.
- **The inventory is four kinds of record**, with information assets beside processes,
  systems, and third parties, and three more kinds of link between them.
- **Guides:** three new ones (Compliance, Evidence and testing, Issues and exceptions), and
  the rest brought up to date. The register guide called two buttons by names the app does
  not use; it now says Raise a risk and Add a control.

### Fixed

- The picture of a record's connections keeps the keyboard focus where it was when a
  neighbor is opened or closed.
- The accessibility audit now fails when a screen it means to open has no such button,
  where before it passed over it.
- The default program is written by a script, and a test now holds the shipped file to it.
- On a narrow screen, a list's name column keeps enough room to be read while the table
  scrolls, and a bar with two figures keeps its track.

## 0.1.0 (2026-11-25)

Wave 1, *The register*: install, sign in, and hold a risk register over an inventory of
processes, systems, and third parties, with risks rated, linked to controls of known
effectiveness, and treated or formally accepted.

### Added

- **Foundation.** `riskwren init`, `serve`, `db upgrade`, `db current`, `verify`, and `doctor`.
  Deployment settings in `riskwren.toml` with environment overrides; secrets are refused in
  the file. A data home for files. SQLite by default and PostgreSQL by address, on one model
  and one set of migrations (migration 0001).
- **History.** Every change to a record is written to an append-only history in the same
  transaction, with who, when, and each value before and after. Events are chained by hash;
  `riskwren verify` finds the first event that has been altered, removed, or cut from the end.
  The database itself refuses updates and deletes on the history.
- **API.** `/api/v1` with health and product information, problem-document errors, and
  strict security headers; the OpenAPI document at `/api/openapi.json`.
- **Accounts and roles.** Local accounts with scrypt-hashed passwords, server-side sessions
  in `HttpOnly`, `SameSite=Strict` cookies, a CSRF token on every change, refusal of requests
  from other sites, and throttled sign-in. Seven roles: admin, manager, assessor, auditor,
  leader, steward, and member. Managers, assessors, leaders, and stewards can be limited to a
  unit and those beneath it, and a leader carries the highest rating they may accept. Every
  API route is checked against one policy table, and a route with no policy is refused. The
  last active administrator cannot be removed. `riskwren init` creates the first
  administrator, and `riskwren users` manages accounts from the command line (migration 0002).
- **Units.** The organization as a hierarchy of any depth, with CSV import of units and
  people that can be run dry first and reports every problem by row.
- **The web app.** A sign-in page, an app shell with a sidebar and a command palette (⌘K),
  your account and password, and admin screens for people, roles, units, and imports. Plain
  ES modules with no build step, under a strict content security policy.
- **Themes.** Light, dark, and system modes, and three palettes (Wren, Slate, Garnet), each
  checked for readable contrast in both modes. Each person's choice is remembered.
- **Branding.** Admin → Appearance sets the product name, organization name, default
  palette, accent color, logos, and tab icon, with a live preview. Ratings are colored on
  an ordinal ramp kept apart from the colors of standing, or, if the organization prefers,
  on a green-to-red signal ramp. An accent is lifted automatically for dark mode and refused
  if it cannot be read. Uploaded SVG is reduced to drawing and served so that it cannot run
  anything (migration 0003).
- **Inventory.** Processes, systems, and third parties, each with a permanent reference
  (`SYS-0042`), a unit, a criticality, the highest class of data it handles, named owners,
  and a page of its own. Records are joined by named links (a process *relies on* a system,
  a system is *supplied by* a third party) that read both ways, so every record shows what
  it depends on and what depends on it. Lists search, filter, sort, and page, with their
  state in the address so any view can be shared. The inventory is open to everyone signed
  in; a record can be marked restricted. An edit made against an older version is refused,
  and a record whose owner has left is shown as needing one (migration 0004).
- **History you can read.** Every record has a History tab: who did what, and each changed
  field with what it was and what it became, in the organization's own words.
- **Vocabularies.** Criticality, data classes with definitions and examples, kinds of
  process, system, and third party, hosting, lifecycle, owner capacities, and kinds of link
  are lists the organization can relabel, extend, and retire. They start from the default
  program pack.
- **The risk register.** A risk is a cause, an event, and a consequence, in a category, owned
  by a unit and by named people, attached to the processes, systems, and third parties it
  concerns. Each of those shows its risks. Risks can be raised from a library of 57 starting
  statements and then made specific (migration 0005).
- **Ratings that explain themselves.** Likelihood and impact are judged against written
  definitions; impact is judged on five dimensions (mission, safety, financial, legal and
  regulatory, trust) and the overall impact is the highest of them. A matrix combines the
  two into Low, Moderate, High, or Critical. The rating appears as the levels are chosen.
  Every assessment keeps who made it, when, why, and the version of the scoring method in
  force; it is never edited, only superseded, and both stay on the record.
- **Inherent, residual, and target.** A risk carries all three, shown side by side, each
  opening the judgment behind it.
- **Appetite and standing.** Each category of risk has a highest residual rating the
  organization will live with. A risk is within appetite, or needs a decision; how much is at
  stake and whether it is in order are always shown as two separate signals. Changing an
  appetite says how many risks changed standing.
- **Review dates.** A risk is due for review sooner the more is at stake: every three months
  when critical, every two years when low. An overdue review is flagged.
- **Roll-up and escalation.** A list narrowed to a unit includes everything beneath it. A risk
  can be escalated to a unit above its own, with a reason.
- **The program as a pack.** `riskwren program export` writes the vocabularies, risk
  categories, scoring method, cadences, and acceptance authority as one file;
  `riskwren program import` loads one, checking all of it first, with `--dry-run` to see what
  would change. A new scoring method is a new version. Admin → Program shows the method, the
  matrix, and every definition.
- **Controls.** A control is described once: who does what, how often, of what kind, owned
  by a unit and by named people. A library of 56 common controls in plain words offers a
  starting point, and a risk raised from the risk library is shown the controls commonly
  used for it (migration 0006).
- **Effectiveness that is recorded, not assumed.** A control's design and its operation are
  each rated by a named person on a date, with what the rating rests on. A rating is never
  edited, only superseded. A control nobody has rated, or whose rating is more than a year
  old, is shown as such and counts for nothing.
- **A suggested residual rating, with its working.** Controls are linked to the risks they
  bear on, saying whether each reduces likelihood or impact and whether the risk relies on
  it. From the inherent rating and what is known of the controls, RiskWren suggests a
  residual rating and shows the arithmetic; the assessor agrees or judges otherwise, and
  both are kept. No number of controls lowers a risk by more than two levels on either axis.
- **When a control gets worse.** If what is known about a risk's controls later suggests a
  worse rating than the one on record, the risk is flagged, the controls responsible are
  named, and its owner is asked to assess it again. The rating is never changed for them.
- **Treatment plans and actions.** A risk above appetite gets a response and a plan: an
  objective, a target rating, an owner, a date, and actions each with an owner and a date.
  Moving an action's date needs a reason, and the original date stays on the record. When
  the last action is done the plan is complete, and the owner is asked for a new assessment.
- **Acceptance.** A leader of the risk's unit, or of a unit above it, can accept a risk above
  appetite, in their own name, with a rationale and conditions, until a date. How high a
  rating a leader may accept is set on their role; how long is set by the rating. Nobody
  accepts a risk they own. An acceptance is never edited; it can be withdrawn, and when it
  expires the risk needs a decision again.
- **Standing.** A risk above appetite is *being treated* while a plan is on time, *accepted*
  while an acceptance covers it, and otherwise *needs a decision*.
- **One list of actions**, with lists of treatment plans and of acceptances.
- **Home.** Each person's home page is one list of what they owe, overdue first: risks to
  assess or review, ratings in doubt, actions, controls to rate, and acceptances about to
  expire. A leader also sees the risks in their units that need a decision; a steward sees
  records nobody answers for.
- **Heat map.** Every open risk the viewer may see, counted by likelihood and impact, for
  the inherent, residual, or target rating, for the whole organization or one unit. Choosing
  a category marks the cells above its appetite. Each cell opens its risks.
- **Dashboard.** Open risks, how many are above appetite, need a decision, are overdue for
  review, or have a rating in doubt; the highest risks; risks by standing, rating, category,
  and unit; and what is known about the controls. Every figure opens the records behind it,
  and counts only what the viewer may see.
- **Grouping and printing.** The register can be grouped by category or unit, and any page
  prints as the record without the application around it.
- **The demo organization.** `riskwren demo` builds the Northmere Institute for Health
  Research, a fictional research institute with a clinic, in its own directory in a few
  seconds: 60 units, about 210 people, 220 processes, systems, and third parties, 180 risks,
  110 controls, and two years of assessments, ratings, plans, and acceptances. Nothing is
  inserted: every record is made by the services the app uses, as the person who would have
  done it, under a simulated clock, so its history verifies. The same seed gives the same
  organization. Twelve storylines are written by hand, among them a critical risk brought to
  high by controls of known effectiveness, an acceptance refused above a leader's limit, a
  plan gone late, and a departed owner's orphaned records. A demo marks itself on every
  page, signs in any of nine sample people with one click from the machine it runs on, and
  will not listen on the network unless started with `--demo-on-network`.
- **Who sees the register.** Admin → Program has the setting for what a person with no role
  sees of risks and controls: everything not restricted, their own units, or only what they
  are named on.
- **Guides.** Getting started, the register, running the program, configuration, and the API,
  with a command reference and an OpenAPI document written from the code.
- **An accessibility audit.** `node scripts/a11y-audit.mjs` builds a fresh demo and checks
  every screen, in three palettes by day and after dark, for names on controls, labels,
  headings, landmarks, click-target sizes, and the contrast of every piece of text.

### Fixed

- A day with no time, such as a due date, was shown as the day before in time zones west of
  Greenwich.
