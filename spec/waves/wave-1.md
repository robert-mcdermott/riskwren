# Wave 1: The register (v0.1.0)

**Goal:** prove the core loop. Something the organization depends on has a risk; RiskWren rates it and shows why; controls of known effectiveness bring it down, and the arithmetic is on the screen; what remains above appetite is treated through a plan or accepted by a named person with the authority; and every step is on a record that cannot be quietly changed. Everything else in the roadmap builds on this loop being quick, clear, and trustworthy.

**Branch:** `wave-1` · **Target version:** `0.1.0` · **Status:** ◐ in progress

## Exit criteria

The wave is done when, on a fresh checkout:

1. `uv sync`, `uv run riskwren init`, and `uv run riskwren serve` produce a running system on SQLite with a first administrator, in under five minutes, with no other software installed (PLT-01).
2. The full test suite passes on SQLite and on PostgreSQL (PLT-02).
3. Signed in as each of the seven roles, a person sees and can do exactly what [security.md](../security.md) says, in the API and in the web app; a test fails if any route lacks a policy (PLT-03, PLT-04).
4. A steward records a process, the systems it relies on, and the third party that supplies one of them, each with an owner, and every record shows what it depends on and what depends on it (INV-01 to INV-06).
5. A manager raises a risk from the library against those records, and an assessor rates it: each level shows its definition as it is chosen, the rating appears as they go, and the saved risk shows the reasons for its rating (RSK-01 to RSK-06, RSK-09).
6. Controls are linked to the risk and rated; the residual assessment shows a suggested rating with its working; an unassessed control counts for nothing and the screen says so; the assessor can depart from the suggestion with a reason (CTL-01 to CTL-05).
7. A risk above appetite shows as needing a decision until it has a plan or an acceptance. A plan's actions appear on their owners' home pages. An acceptance by the risk's own owner, or by a leader above their limit, is refused; an acceptance by the right person changes the standing and expires on its date (RSK-07, TRT-01 to TRT-05).
8. When a linked control's rating gets worse, the risk is flagged as possibly out of date and names the control.
9. The heat map shows every open risk the viewer may see, inherent or residual, with the appetite boundary; each cell opens its risks; the dashboard's every figure opens the records behind it; a leader sees their unit and everything beneath it, and nothing else (RSK-08, RSK-10, RSK-11, RPT-01, RPT-02, RPT-04).
10. Every change above appears in the record's history with who, when, and before and after; `riskwren verify` confirms the chain, and reports the exact event after a row is altered by hand (INV-05, PLT-05).
11. An administrator sets the product name, logo, palette, accent, and rating ramp in the app and sees them applied at once, in light and dark, with contrast checked (PLT-07, PLT-08).
12. `riskwren demo` builds the demo organization in under a minute, and every wave 1 screen has convincing data (PLT-10).
13. The app passes the automated accessibility checks in every palette and mode (PLT-12); lint and the private-terms check are clean.

Requirements delivered: INV-01 to INV-06; RSK-01 to RSK-11; TRT-01 to TRT-05; CTL-01 to CTL-05; RPT-01, RPT-02, RPT-04; PLT-01 to PLT-12, PLT-14; INT-01; DOC-01.

## Decisions needed from the maintainer

None block the start. These defaults have been taken and can be changed before the slice that depends on them:

- **Rating names:** Low, Moderate, High, Critical, on a five-by-five matrix that leans toward impact (slice 5).
- **Impact dimensions:** Mission, Safety, Financial, Legal and regulatory, Trust; the overall impact is the highest rated (slice 5).
- **Default palette:** Wren, with a harbor-blue accent; ratings on an ordinal plum ramp, with a signal ramp as a setting (slice 3).
- **Demo organization name:** Northmere Institute for Health Research (slice 8).
- **Member visibility default:** Unit (slice 4).
- **Role names:** admin, manager, assessor, auditor, leader, steward, member (slice 2).
- **Repository hosting and continuous integration:** GitHub with a workflow that runs the suite on both databases (slice 1).

---

## Slice 1: Foundation ☑

**Goal:** a skeleton in which the rules of the architecture are already enforced.

- [x] Project: `pyproject.toml` with the five runtime dependencies and the optional PostgreSQL driver, `uv.lock`, `.python-version`, `src/riskwren` layout, `riskwren` entry point, ruff and pytest configuration, Apache 2.0 `LICENSE` and `NOTICE`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`
- [x] Configuration: `riskwren.toml` read with the standard library into frozen typed settings; unknown keys are errors; all problems reported together; environment overrides; secrets refused in the file
- [x] Data home: creation, marker, and checks
- [x] Database: engine for SQLite (write-ahead log, foreign keys on) and PostgreSQL; portable JSON and UTC date-time types; a naming convention for constraints; declarative ORM base; one session per request
- [x] Migrations: Alembic inside the package with no `alembic.ini`; revision `0001`; `riskwren db upgrade | current`; `serve` refuses a schema that is behind
- [x] History: the `event` table; sessions that record every change to an audited row, with before and after values, in the same transaction; refusal of writes with no actor and of bulk statements on audited tables; the hash chain; `riskwren verify`; triggers on both databases refusing update and delete
- [x] References: per-prefix counters that never reuse a number
- [x] Command line: `init`, `serve`, `db`, `verify`, `doctor`, with a reference page generated from the parser
- [x] API: the app factory, the envelope and problem-document conventions, security headers, health and `meta` endpoints, the static shell with a fallback route, `docs/openapi.json` kept current by a test
- [x] Tests on both databases: fixtures, a script to start a local PostgreSQL, `scripts/test-both.sh`
- [x] Continuous integration: lint, format check, tests on SQLite and PostgreSQL (the private-terms check runs locally, from git hooks, because its list is never published)
- [x] `scripts/check_terms.py` with pre-commit and commit-message hooks

**Acceptance (met):** a fresh clone initializes and serves an empty shell; the suite passes on both databases; altering an event row by hand is caught by `riskwren verify`; a write that bypasses the service helper fails a test that compares table changes with events.

## Slice 2: Accounts, roles, and units ☑

**Goal:** people can sign in, and the system knows who may do what, where.

- [x] `account`, `credential`, `membership`, `role_grant`, `session_token`, `failed_sign_in`; scrypt hashing; password rules; throttling per account and address; `HttpOnly`, `SameSite=Strict` cookies; CSRF token and origin checks
- [x] `riskwren init` creates the first administrator; `riskwren users add | list | disable | enable | reset-password | roles`; `serve` refuses to start with no administrator
- [x] `role_grant` with unit scope and, for a leader, an acceptance limit; the principal, with the units each scoped role covers worked out at sign-in; the policy table as an app-wide dependency; refusal of any route without a policy
- [x] `org_unit` tree and `membership`; import of units and people from CSV with a dry run that lists every problem by row
- [x] API: session, accounts, roles, units, and imports

**Acceptance (met):** the role-by-route matrix test signs in as each role and exercises every route, and a second test fails when a route has no policy or a policy has no route; a steward of a division covers its labs and no others; the last administrator can be neither demoted nor disabled, in the app or at the command line; CSRF, cross-site requests, throttling, idle and absolute expiry, sign-out, and the ending of sessions on disablement and password change are tested.

## Slice 3: Web app and design system ☑

**Goal:** a shell that already looks and behaves like a finished product.

- [x] The sign-in page, user menu, password change, and Admin → People and units (accounts, roles, units, and the import screens)
- [x] `tokens.css`, `palettes.css` (Wren, Slate, Garnet), `base.css`, `components.css`, `pages.css`; light, dark, and system modes; the rating ramp in its ordinal and signal forms
- [x] The wren mark as SVG: mark, mark with wordmark, single color; the default favicon
- [x] Core modules: DOM helper, router with URL state, API client with CSRF and caching, session and permissions, preferences
- [x] Components: shell, sidebar, top bar, page header, tabs, drawer, dialog, table, record chip, rating badge, standing pill, stat tile, toast, form fields with server errors on their fields, empty and error states, skeletons
- [x] Command palette (⌘K, Ctrl-K, or `/`) and Escape to close anything open
- [x] Branding: the `setting` table, `/theme.css` generated from it, logo and tab-icon upload with type sniffing and SVG sanitizing, Admin → Appearance with a live preview in both modes and contrast results before saving
- [x] Home: for a new installation's administrator, a setup checklist that ticks itself off
- [x] Tests: no inline script or style, no third-party origins, no parsing of data as HTML, every import and route resolves, every script parses, size budgets, and contrast for the token pairs in every palette and mode

**Acceptance (met):** an administrator changes the organization name, palette, accent, and rating ramp in the browser and sees them applied at once, with no file touched; every palette passes AA for text, standing, rating, and control-border tokens in both modes, on the ordinal ramp and on the signal ramp; the shell is within its size budget. 194 tests pass on SQLite and 190 on PostgreSQL (four are about the SQLite file). Checked in the browser: sign-in, the shell, Admin → Appearance with both ramps, and the roles editor.

## Slice 4: Inventory ☑

**Goal:** the things risk attaches to, done properly.

- [x] Models and services for processes, systems, and third parties with the shared header; owners in three capacities; typed links with forward and reverse labels; tags (migration 0004)
- [x] A registry that describes each record type as data, so that adding, editing, finding, owners, links, visibility, and history are written once and later record types join by registering
- [x] Vocabularies as settings, with defaults from the default program pack: criticality, data classes (each with a definition and examples), process, system, and third-party kinds, hosting, lifecycle, owner capacities, link kinds, and unit kinds. A value in use can be relabelled or retired, never removed
- [x] The default program pack as a file, written by `scripts/build-default-program.py` and read as the defaults
- [x] List pages with search, filters, sort, and paging, all in the URL; detail pages with a shared header and tabs; what a record relies on and what relies on it, with a count of links the viewer may not see
- [x] The History tab as a readable timeline: who did what, and each changed field with what it was and what it became, in the organization's own labels
- [x] Visibility: the inventory open to everyone signed in; restricted records; the open, unit, and assigned setting kept for the register of risks and controls; one rule used for single records and for lists
- [x] Optimistic concurrency on edits; orphaned records shown when an owner's account is disabled
- [ ] Moved to slice 5, where the program gains its taxonomy and scoring method: `riskwren program export | import`, with the whole pack checked before any of it is loaded

**Acceptance (met):** each record type can be created, edited, linked, and found; every edit is in its history under a named operation; a table of what each of the seven roles sees is tested for single records and for lists, which must agree; a stale edit is refused and an invalid one leaves the record as it was. 209 tests pass on SQLite. Checked in the browser: the three lists with filters and sorting, a record page, adding a link, editing owners, and the history timeline.

## Slice 5: Risk register ☑

**Goal:** a rating that explains itself, and a register that knows what is in order.

- [x] `risk_category` as a tree with appetite, its own or inherited from above; the default taxonomy of nine categories; `scoring_method` with immutable versions and the default method, with a definition for every level (migration 0005)
- [x] The scoring module in Python and its JavaScript twin, held to one shared file of 70 cases: rating from likelihood and impact levels, overall impact as the highest dimension rated, the matrix lookup, and (ready for slice 6) control strength and the suggested residual with its working
- [x] A method that cannot be used says everything wrong with it in one pass: a matrix in which a rating falls as likelihood or impact rises is refused
- [x] Risks with a statement of cause, event, and consequence; category, unit, owners; the processes, systems, and third parties a risk concerns, and each of those showing its risks
- [x] Assessments: inherent, residual, and target, each with levels by dimension, a rationale, and the method version; never edited, only superseded; the copies on the risk
- [x] Standing worked out from rating and appetite; the *review overdue* flag; next review date from the cadence table; closing a risk with a reason, and reopening it
- [x] The assess screen: the level picker with definitions, the rating appearing as levels are chosen; the *journey* strip and the reasoning behind each rating on the risk
- [x] The register: a dense list with filters for category, rating, standing, unit, and owner, sorted by what is at stake
- [x] Roll-up by unit; escalation to a higher unit with a reason
- [x] The risk library pack of 57 statements, and starting a risk from an entry
- [x] From slice 4: `riskwren program export | import`, with the whole pack checked before any of it is loaded and a dry run that says what would change; the default program and the library loaded by `riskwren init` and `riskwren db upgrade`
- [x] Admin → Program: the categories with their appetite, which can be changed there and says how many risks changed standing; the matrix; what follows from each rating; every definition
- [ ] Moved to slice 7, with the dashboard: grouping the register by category or unit

**Acceptance (met):** the two scoring implementations agree on every shared case; an assessment always shows the method version it was made under after the method changes; changing a category's appetite changes the standing of its risks and nothing else; a leader's list contains their unit's risks and those beneath it; an assessment cannot be altered through any route. A table of which risks each of the seven roles sees under each of the three visibility settings is tested for single risks and for lists, which must agree. 302 tests pass on SQLite. Checked in the browser: the register, a risk page, the assessment form with its live rating, the recorded reasoning, and the Program page.

## Slice 6: Controls and treatment ☑

**Goal:** controls that are known to work, and a named person behind whatever remains.

- [x] Controls with statement, objective, kind, nature, frequency, unit, and owners; a library of 56 starter controls in plain words, from which a control is started and made the organization's own; every library risk suggests the controls commonly used for it (migration 0006)
- [x] Control ratings for design and operation with a basis and a note; never edited; strength as the weaker part; stale when older than the cadence
- [x] Links from controls to risks with what each reduces and how much it is relied on; one control bears on a risk once
- [x] The suggested residual rating with its working, in Python and JavaScript on the same cases; kept on the assessment beside the assessor's judgment
- [x] The *residual may be out of date* flag when what is now known suggests worse than it did at the assessment and worse than the rating on record, naming the controls responsible; the rating itself is never changed by the system
- [x] Responses with a rationale; treatment plans with a target rating and actions; the one `action` table and the Actions list; moving an action's date needs a reason, and the original date and every move stay on the record
- [x] A plan completes when its last action does; that asks the owner for a new assessment and does not change the rating
- [x] Acceptance: the authority table, the limit on a leader's grant, the maximum period by rating, refusal for an owner or above the limit, withdrawal, and expiry changing the standing
- [x] Standing kept in step with the calendar: when an acceptance expires or a plan runs late, the risk returns to needing a decision the next time the register is read
- [x] Separation of duties in the service layer, tested for every role
- [x] Screens: the control library and control page with its ratings; the Controls and Treatment tabs of a risk; lists of treatment plans, acceptances, and actions
- [x] Found on the way: a day with no time (a due date, a review date) was shown a day early west of Greenwich. Fixed, with a test that runs the browser's modules in such a time zone

**Acceptance (met):** the worked example in [engine.md](../engine.md) produces the figures shown there; a control that is not assessed or is stale contributes nothing; no number of controls lowers an axis by more than the limit; an acceptance is refused for the risk's owner and for a leader above their limit, in the API and the app; an expired acceptance returns the risk to *needs a decision*; closing a plan's last action asks its owner for a new assessment and does not change the rating. 316 tests pass on SQLite. Checked in the browser: adding and linking a suggested control, the suggestion's arithmetic, a plan with an overdue action, the actions list, and a control page.

## Slice 7: Home, heat map, and dashboard ☐

**Goal:** one place to see what you owe, and one to see where the register stands.

- [ ] Home: one list of what the person owes, overdue first: reviews due, actions, acceptances expiring, orphaned records for stewards; for leaders, their unit's risks that need a decision
- [ ] The heat map: counts by likelihood and impact for inherent, residual, or target; filters by unit and category; the appetite boundary; a cell opens its risks beside the grid; a table of the same figures
- [ ] The dashboard: top risks, risks by standing, by category and unit, reviews and actions overdue, controls by effectiveness including not assessed; each tile linked to its records
- [ ] Print styles for a risk, the register, the heat map, and the dashboard

**Acceptance:** every figure on the dashboard and every cell of the heat map opens a list whose length equals the figure, for each of the seven roles; the heat map has a complete table alternative and passes the accessibility audit.

## Slice 8: Demo organization ☐

**Goal:** a believable institute that exercises everything in the wave.

- [ ] The generator: units, people, processes, systems, third parties, risks, controls, plans, acceptances, and actions, built through the services under a simulated clock, deterministic by seed
- [ ] The storylines in [demo-organization.md](../demo-organization.md), written by hand
- [ ] The "Demo data" marker, one-click sign-in as each sample person, and the refusal to listen beyond the local machine unless told to
- [ ] The demo build as an end-to-end test, with its history verified

**Acceptance:** `riskwren demo` builds in under a minute; the same seed gives the same organization; every wave 1 screen has data worth reading; `riskwren verify` passes on the result.

## Slice 9: Release prep ☐

- [ ] Guides in `docs/`: getting started, configuration, the register (inventory, risks, controls, treatment), running the program, the command-line reference, the API guide
- [ ] `README.md` with the quickstart; `CHANGELOG.md` for 0.1.0
- [ ] The automated accessibility audit over every wave 1 screen in every palette and mode
- [ ] Fresh-clone install and quickstart checked on both databases
- [ ] Version `0.1.0`; pull request from `wave-1`; tag and release

## Notes

Decisions and discoveries made during the wave are logged here, newest last.

- **A scoped role held with no unit covers the whole organization.** A manager or assessor may be limited to units; only a manager for the whole organization runs the program (edits the taxonomy and scoring method, reads everything). A manager of one division manages that division's records and no more.
- **Administration is not judgment.** The admin role reads and configures; it does not edit records, assess, or accept. An administrator who also does that work holds a second role.
- **A leader's limit is the key of a rating**, not a number, so it stays meaningful when an organization renames or reshapes its ratings. It is checked against the scoring method when an acceptance is made (slice 6).
- **Sign-in is throttled three ways:** five failures for one account from one address, and a much higher limit for the account alone and for the address alone, so nobody can lock a colleague out by typing their address. Each attempt is counted before the password is checked.
- **The inventory is open; the register follows the setting.** Under the planned default, a steward could not link their system to a supplier recorded by another unit, because they could not see it. Processes, systems, and third parties are now visible to everyone signed in unless restricted, and the visibility setting governs risks and controls. [security.md](../security.md) says so.
- **A link is recorded once and read both ways.** Its changes appear in the history of the record it starts from.
- **Starter controls are a library, not records.** A control needs a unit and an owner to mean anything, so an installation is not seeded with fifty ownerless controls. The library offers them where they are wanted: on a risk started from the library, the controls commonly used for it are one step away.
- **Doubt is about change, not disagreement.** An assessor who judges a residual rating lower than the controls suggest has made a judgment, and it is kept with its reason. The flag is raised only when what is known about the controls later gets worse than it was at that assessment.
- **An acceptance covers what was accepted.** If the residual rating later rises above the rating that was accepted, the acceptance no longer covers the risk and it needs a decision again.
- **Until scheduled jobs arrive (wave 3), the calendar is caught up on reading.** Reading the register checks, cheaply, whether any acceptance has expired or plan has run late, and writes only if one has, as the system and not as the reader.
- **Escalation is prominence, not ownership.** A risk escalated to a higher unit still belongs to its own; the unit above already sees it in its roll-up. Escalating says "this needs you", with a reason, and puts it among the risks that sit at that level.
- **A matrix must never run backwards.** A scoring method in which a rating falls as likelihood or impact rises cannot be published, whether typed in or imported.
- **The program is installed, not migrated.** Migrations build tables; `init` and `db upgrade` then add whatever of the default program and libraries is missing, as ordinary audited writes, and never overwrite what an organization has shaped.
- **Parts and wholes are links, not record types.** A system built on a platform, or a service within a broader line of work, is said with an *is part of* link between two systems or two processes. The dependency graph that makes these links visible moves forward from wave 3 to wave 2, where scopes, controls, and requirements give it more to show.
- **The rating ramp has five steps.** A method with fewer ratings spreads them across the ramp, so the lowest and the highest always sit at its ends.
