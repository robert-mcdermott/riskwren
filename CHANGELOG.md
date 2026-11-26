# Changelog

RiskWren follows semantic versioning. Each wave of the [roadmap](spec/roadmap.md) is a
release. Before 1.0, a release may contain breaking changes; they are listed under
**Breaking**.

## Unreleased

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

### Fixed

- A day with no time, such as a due date, was shown as the day before in time zones west of
  Greenwich.
