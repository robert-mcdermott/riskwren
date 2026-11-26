# Changelog

RiskWren follows semantic versioning. Each wave of the [roadmap](spec/roadmap.md) is a
release. Before 1.0, a release may contain breaking changes; they are listed under
**Breaking**.

## Unreleased

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
- **Safe file storage.** Files are stored by the SHA-256 of their content, outside anything
  the server serves. Their kind is judged by content, not name: PDF, common images, Word,
  Excel, and PowerPoint documents, and plain text, up to 25 MB; programs are refused. A file
  is only ever returned as a download that cannot run in the browser, to someone who may see
  the item, and each download is recorded in the history.
- **Framework packs.** A framework is one JSON document, checked whole before anything is
  loaded and refused whole if anything is wrong. Each pack declares what text it may carry,
  and a test holds every built-in pack to it. `riskwren frameworks list`, `show`, and `load`.

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
