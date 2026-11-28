# Roadmap

RiskWren ships in **waves**. Each wave is a release (wave 1 → v0.1.0, wave 2 → v0.2.0, …) and is split into **slices**: coherent chunks of related work. The last slice of every wave prepares the release. See [process.md](process.md) for how this works day to day.

The order follows how a program grows. Wave 1 gets the register right: what the organization has, what could go wrong, what is done about it, and who answers for it. Wave 2 adds what it must comply with, and the tests and evidence that prove it. Wave 3 keeps all of it current without a central team chasing. Waves 4 and 5 widen it to policy, obligations, and third parties. Wave 6 turns the record into answers for leadership. Waves 7 and 8 add audit and what happens when things go wrong. Waves 9 and 10 make it something another organization can adopt and connect. Wave 11, once adopters have seen it, makes it stable. Every wave ends with something that can be demonstrated on the demo organization.

**Whose work comes first.** The first adopters are security teams (see [vision.md](vision.md)). Within every wave, what a chief information security officer and a security assurance team use is built first and polished most: frameworks, scopes, tests, evidence, issues, exceptions, and the compliance dashboard in wave 2; attestations, evidence renewal, and reminders in wave 3; supplier security reviews in wave 5. The order of the waves is unchanged.

| Wave | Version | Theme | The demo at the end |
|---|---|---|---|
| 1 | v0.1.0 | **The register** | Install, sign in, and hold a risk register over an inventory of processes, systems, and third parties: rated, linked to controls of known effectiveness, treated or formally accepted, on a heat map that explains itself |
| 2 | v0.2.0 | **Compliance** | Load a framework, see it mapped to the organization's controls, define a scope, test each control once, hold the evidence, and follow failures through issues to validated closure |
| — | — | **Documentation site** | A product site with illustrated guides, screenshots of the demo organization, and an API reference |
| 3 | v0.3.0 | **Keeping watch** | The program stays current: single sign-on, schedules and reminders, self-assessment and attestation campaigns, indicators, search |
| 4 | v0.4.0 | **Policy and obligations** | Policies from draft to acknowledgment; agreements and awards as obligations with dates; framework updates with their impact; committee sessions |
| 5 | v0.5.0 | **Third parties** | Suppliers and partners tiered by what they touch, questioned through a link, reviewed, covered by agreements, and re-assessed on schedule |
| 6 | v0.6.0 | **Insight** | Leaders see risk and compliance with defined measures and trends; an auditor exports a complete, verifiable package; the register as of any date |
| 7 | v0.7.0 | **Audit** | The audit universe, a risk-based plan, engagements with workpapers and requests, findings followed to closure |
| 8 | v0.8.0 | **Incidents and resilience** | Anyone reports a concern; restricted cases; breach assessment; business impact, continuity plans, and exercises |
| 9 | v0.9.0 | **Adoption** | Another organization installs, brands, and runs RiskWren in production, with scoped tokens, deployment recipes, starter programs, and a security review |
| 10 | v0.10.0 | **Connected** | Other systems push results in and check a reference; assistants read and draft; all optional |
| 11 | v1.0.0 | **Stable** | After adopters have seen it: their changes, then an upgrade path and a compatibility promise |

Status key: ☐ planned · ◐ in progress · ☑ done

---

## Wave 1: The register (v0.1.0) ☑

**Goal:** prove the core loop. Something the organization depends on has a risk; the risk is rated with reasons; controls of known effectiveness bring it down; what remains is treated or accepted by someone with the authority; and all of it is on a record that cannot be quietly changed.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | Foundation | Project skeleton, configuration, data home, the ORM model and migrations on SQLite and PostgreSQL, the service layer with the event log and hash chain, command line and API skeletons, tooling and continuous integration | ☑ |
| 2 | Accounts, roles, and units | Local accounts and sessions, the seven roles with scopes, the route policy table, the unit hierarchy, import of units and people | ☑ |
| 3 | Web app and design system | Vanilla JS shell, tokens, three palettes in light and dark, the wren mark, branding settings with live preview, command palette, core components | ☑ |
| 4 | Inventory | Processes, systems, and third parties with owners, typed links, lists, detail pages, and history; the default program's vocabularies | ☑ |
| 5 | Risk register | The taxonomy with appetite, the scoring method in Python and JavaScript, risks, assessments with reasons, standing, review dates, roll-up and escalation, the risk library | ☑ |
| 6 | Controls and treatment | The control library and starter controls, effectiveness ratings, the suggested residual with its working, responses, treatment plans, actions, and acceptance under the authority table | ☑ |
| 7 | Home, heat map, and dashboard | What each person owes; the heat map with the appetite boundary; the risk dashboard with every figure linked to its records | ☑ |
| 8 | Demo organization | The fictional institute, built through the services under a simulated clock, with storylines for every wave 1 screen | ☑ |
| 9 | Release prep | Guides, quickstart, changelog, accessibility check, version, release | ☑ |

Detail: [waves/wave-1.md](waves/wave-1.md)

## Wave 2: Compliance (v0.2.0) ☑

**Goal:** test once, satisfy many. One set of controls answers every framework the organization is held to, and readiness is worked out from tests and evidence, never typed in.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | Frameworks | The pack loader and text policies; the four built-in frameworks generated from their publishers' files; the organization's own frameworks; requirement browsing | ☑ |
| 2 | Crosswalks | Controls mapped to requirements; the starter controls' crosswalk; coverage and gaps per framework | ☑ |
| 3 | Scopes and inheritance | Scopes with their boundary and frameworks, baselines, applicability with reasons, implementations, offered and inherited controls, the statement of applicability; information assets | ☑ |
| 4 | Evidence and files | Content-addressed file storage, evidence items with owners and validity, reuse across controls, freshness | ☑ |
| 5 | Assessments and tests | Assessments, the test queue, procedures and results with review, results flowing to controls, requirements, and risks; readiness in five states | ☑ |
| 6 | Issues and exceptions | The issue register, severity clocks, action plans, validated closure, root cause, exceptions with compensating controls and expiry, the plan-of-action view; in-app notices | ☑ |
| 7 | Import and export | Spreadsheet import with mapping and a dry run for every record type; CSV and JSON export of every list; external references | ☑ |
| 8 | Dashboard, graph, and demo | Readiness by scope and framework, stale evidence, issues by age; the dependency graph around any record; an organization-wide history view; the demo's scopes, assessment, and issues | ☑ |
| 9 | Release prep | Guides, changelog, dependency review, release | ☑ |

Detail: [waves/wave-2.md](waves/wave-2.md) · Detail of the content: [content-packs.md](content-packs.md)

## Documentation site (between v0.2.0 and v0.3.0) ☑

**Goal:** a product site that lets someone outside the project find RiskWren, see it, and try it. Released with v0.2.1, together with a wider library of common controls and a demo whose scopes show a program in working order.

It waited until the main screens had settled; screenshots taken during wave 1 would have been stale within weeks. The Markdown in the repository is still the documentation, and the site is built from it unchanged.

- **The guides stay the source.** `README.md` and `docs/*.md` are what the repository shows and what the site is built from, so the two never disagree.
- **Site generator:** `scripts/site/build.mjs`, a script needing Node 22 and no packages. It builds a home page and one page per guide, with a menu in reading order, client-side search, light and dark themes from RiskWren's own design tokens, the changelog, and an API reference generated from the OpenAPI document. The build checks every link, anchor, and image and fails on a broken one, and the test suite runs the build.
- **Screenshots of the real app.** A capture script drives headless Chrome over its debugging protocol. It builds a fresh demo organization in a temporary directory, starts RiskWren on it, signs in as the right sample person for each scene, and saves each scene in both themes. Each scene is one line: a URL, who is signed in, a size, and an optional step. Named scenes can be retaken alone. The pictures a guide or the home page names are kept in `docs/img`, in both themes, and no others.
- **An accessibility audit** runs over the same scenes and fails on any finding. The site has its own (`scripts/site/audit.mjs`): the same checks on every page, by day and after dark, at desk and phone widths, and that nothing is wider than the screen.
- **Publishing:** the site is whatever is committed on the `gh-pages` branch. The build writes into a worktree of that branch only when asked to publish, so nothing is published by accident. The site states the version it describes.
- **Each release from then on:** retake screenshots for screens that changed, check the guides against the changelog, review in both themes and at phone width, then publish.

Decision record: [ADR-0009](decisions/0009-documentation-toolchain.md)

## Wave 3: Keeping watch (v0.3.0) ☑

**Goal:** a register that stays true without a central team chasing it.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | Single sign-on | Optional, beside local accounts: OpenID Connect with discovery, PKCE, and verified tokens; works with Microsoft Entra ID; accounts created at first sign-in; application roles or groups mapped to roles and unit scopes | ☑ |
| 2 | Schedules and email | The job scheduler, the cadence table for reviews, tests, attestations, and evidence, reminders and escalation, optional SMTP delivery, digests, preferences | ☑ |
| 3 | Questionnaires | Questionnaires as versioned data with conditional questions; the condition evaluator in Python and JavaScript | ☑ |
| 4 | Campaigns | Risk and control self-assessment, control attestation, and unit completeness campaigns, with coverage by unit; evidence requests; attestation as a basis of assurance, shown apart from a test | ☑ |
| 5 | Indicators | Indicators with thresholds, readings, and trends, linked to risks; breaches raise notices | ☑ |
| 6 | Find and tidy | Search across all records, saved views, completeness, duplicates, and reassignment when someone leaves | ☑ |
| 7 | Program editors | Editing the taxonomy, scoring method, appetite, cadences, and vocabularies in the app with an impact preview; structured risk assessments over a scope | ☑ |
| 8 | Release prep | Guides, changelog, release | ☑ |

Detail: [waves/wave-3.md](waves/wave-3.md)

## Wave 4: Policy and obligations (v0.4.0) ☑

**Goal:** the governance in governance, risk, and compliance: what the organization has said it will do, and what it has promised others.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | Policy documents | Policies, standards, procedures, and guidelines with versions, review, approval, publishing, and review dates | ☑ |
| 2 | Library and acknowledgment | A searchable library for all staff; acknowledgment campaigns by unit and role | ☑ |
| 3 | Policies in the web of records | Documents mapped to controls and requirements; exceptions to policy | ☑ |
| 4 | Agreements | Awards, data use agreements, and contracts as records with dates, parties, coverage, and the requirements they impose | ☑ |
| 5 | Framework updates | Loading a new version beside the old, what changed, what it affects, and moving a scope across; publisher mappings as suggested crosswalks; further framework packs | ☑ |
| 6 | Objectives and sessions | Strategic objectives linked to risks; committee sessions with agendas, decisions, and minutes | ☑ |
| 7 | Release prep | Guides, changelog, release | ☑ |

Detail: [waves/wave-4.md](waves/wave-4.md)

## Wave 5: Third parties (v0.5.0) ☑

**Goal:** know who the organization depends on, what each can reach, and whether the paper covers it.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | Services and tiering | What each third party provides and touches; tiering by rule with reasons | ☑ |
| 2 | Due diligence | Questionnaires by tier, sent through an expiring link to a contact with no account; review and scoring | ☑ |
| 3 | Assurance documents | Reports and certificates with validity; a structured review of scope, exceptions, and the organization's own responsibilities | ☑ |
| 4 | Coverage | Agreements joined to services, systems, and information; the stop for regulated information with no covering agreement | ☑ |
| 5 | Lifecycle | Findings tracked with the third party, re-assessment by tier and by event, offboarding, subcontractors | ☑ |
| 6 | Release prep | Guides, changelog, release | ☑ |

Detail: [waves/wave-5.md](waves/wave-5.md)

## Wave 6: Insight (v0.6.0) ☑

**Goal:** answer leadership's questions from the record, with figures that explain themselves.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | Measures | Defined measures of risk, treatment, compliance, and timeliness, each with its period and cohort; daily snapshots for trends | ☑ |
| 2 | Portfolio | Views by unit, category, framework, and third party over a period, drilling down to records; root causes | ☑ |
| 3 | Leadership report | A periodic report frozen as a snapshot that reopens unchanged | ☑ |
| 4 | As of | Any record, and the register, as it stood on a chosen date | ☑ |
| 5 | Dossier and open formats | A complete, verifiable package for a scope, risk, or third party; export in the open assessment language; the security plan document | ☑ |
| 6 | Scenarios and ranges | Scenarios; estimates in ranges with simulation; the bow-tie view | ☑ |
| 7 | Release prep | Guides, changelog, release | ☑ |

Detail: [waves/wave-6.md](waves/wave-6.md)

## Wave 7: Audit (v0.7.0) ☑

**Goal:** give the third line its own workspace on the same record, without compromising its independence.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | Universe and plan | Auditable entities drawn from the inventory with a risk ranking; the period plan | ☑ |
| 2 | Engagements and workpapers | Stages, the program of work, workpapers with review and sign-off, restricted until issued | ☑ |
| 3 | Requests | Requests to the audited, answered with evidence | ☑ |
| 4 | Findings and follow-up | Findings as issues with management action plans; validation by audit; the committee report | ☑ |
| 5 | Outside auditors | Scoped, time-limited, read-only access with every view recorded | ☑ |
| 6 | Release prep | Guides, changelog, release | ☑ |

Detail: [waves/wave-7.md](waves/wave-7.md)

## Wave 8: Incidents and resilience (v0.8.0) ☑

**Goal:** when something goes wrong, it is reported, handled, and learned from; and the organization knows what it cannot afford to lose.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | Reporting and triage | A one-minute report from anyone; reporting without a name through a link; triage, severity, and links | ☑ |
| 2 | Cases | Restricted cases with named members | ☑ |
| 3 | Breach assessment | The structured assessment, deadlines, and notifications; privacy impact assessments; privacy and breach framework packs | ☑ |
| 4 | Learning and losses | Incidents joined to risks and controls; corrective actions; loss events and near misses | ☑ |
| 5 | Business impact | Sites; impact analysis per process; recovery needs checked against what dependencies can deliver | ☑ |
| 6 | Plans and exercises | Versioned plans that print for use offline; exercises with findings | ☑ |
| 7 | Release prep | Guides, changelog, release | ☑ |

Detail: [waves/wave-8.md](waves/wave-8.md)

## Wave 9: Adoption (v0.9.0) ☑

**Goal:** an organization that has never seen RiskWren installs it, makes it its own, and runs it in production.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | Production | Measured performance at 10,000 records and many people at once; several workers; backup, restore, and moving between SQLite and PostgreSQL | ☑ |
| 2 | Brand kit | The organization's own terms, an email header; exact colors, the sign-in message and picture, footer links, and contrast checks arrived in 0.8.0 | ☑ |
| 3 | Starter programs | Program packs for a research institute, an academic medical center, a university, and a general nonprofit; custom fields; identifier-only framework packs | ☑ |
| 4 | API for others | Scoped tokens, signed webhooks, a recorded API contract | ☑ |
| 5 | Deployment | A container image, a compose file, a hardened systemd unit, proxy examples, the operations view, `doctor --production` | ☑ |
| 6 | Security and accessibility review | The standard security verification review; the full accessibility audit and screen-reader check | ☑ |
| 7 | The program handbook | One guide for a risk and compliance team, from first decisions to the yearly rhythm; the adopter's guide | ☑ |
| 8 | Release prep | Guides, changelog, release | ☑ |

Detail: [waves/wave-9.md](waves/wave-9.md)

## Wave 10: Connected (v0.10.0) ☐

**Goal:** fit into the systems around it while staying passive: others tell RiskWren, or ask it; it never goes looking.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | Results pushed in | An endpoint through which another system posts a test result or evidence onto a control, recorded with its source and never overriding a person | ☐ |
| 2 | A reference others can check | Other processes ask whether a third party, scope, or exception is in good standing; recipes for purchasing and data-access processes; ticket and chat notifications by webhook | ☐ |
| 3 | Tool server for assistants | An optional server through which an AI assistant reads records and drafts changes that a person confirms | ☐ |
| 4 | Optional assistant | Off and invisible by default; drafts risk statements and summarizes records, with any compatible provider including a local one; every exchange logged | ☐ |
| 5 | Release prep | Guides, changelog, release | ☐ |

## Wave 11: Stable (v1.0.0) ☐

**Goal:** something an organization can build on. It waits until adopters have seen RiskWren and said what they need changed.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | Changes adopters ask for | What the first demonstrations turn up | ☐ |
| 2 | Upgrades | The release adopters first run upgrades with every row and file kept, on both databases, checked by script | ☐ |
| 3 | The 1.0 promise | A compatibility statement for the API, configuration file, pack formats, and data home; deprecation rules | ☐ |
| 4 | Hardened | The threat table walked by a second reviewer; load and soak tests | ☐ |
| 5 | Release prep | Guides, changelog, release | ☐ |

## Later

Ideas that are deliberately not scheduled. Each needs evidence from adopters before it earns a wave.

- **Scheduled, read-only collection** of evidence from a system the organization names, opt-in per source, with results as suggestions for a person to confirm.
- **Answering other people's questionnaires** from a library of approved answers.
- **Localization** of the interface.
- **Several organizations in one installation**, for consortia and shared service centers.
- **Directory provisioning** of accounts and units from an identity system.
- **Object storage** for files.
- **Training records**: who has completed which required training.
- **A shared pack library** where organizations publish and reuse program and content packs.

## Never

Kept here so the question does not need to be asked again. These would change what RiskWren is. See [ADR-0003](decisions/0003-passive-by-design.md).

- Network, log, endpoint, code, vulnerability, or cloud scanning.
- Anything that blocks, changes, or sits in the path of another system.
- Holding the regulated data that records describe.
