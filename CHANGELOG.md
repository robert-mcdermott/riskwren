# Changelog

RiskWren follows semantic versioning. Each wave of the [roadmap](spec/roadmap.md) is a
release. Before 1.0, a release may contain breaking changes; they are listed under
**Breaking**.

## Unreleased

### Changed

- Risks are brought up to date with the calendar every hour by a scheduled job, as well as
  when the register is read.
- The accessibility audit and the screenshot capture start their demo on a port the
  operating system says is free. A fixed port could already belong to something else on
  the machine, which would then have been audited in its place.
- `riskwren doctor` reports how people sign in, whether email is set up, and whether
  scheduled work is being done.

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
- `scripts/dev_identity_provider.py`, a stand-in provider for trying single sign-on on a
  laptop. Its signing key is public; it is not for real use.

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
