# Architecture

RiskWren is a **modular monolith**: one Python package, one web process, one database, and a command-line tool that runs the same code. There are no message brokers, caches, search clusters, or worker fleets. A single machine is the reference deployment, and a laptop is enough to try it.

## System overview

```text
                              PEOPLE
        browser (vanilla JS app)          scripts and other systems
                 │                                   │
                 │ HTTPS / JSON                      │ API tokens, webhooks (wave 9)
                 ▼                                   ▼
  ┌────────────────────────────────────────────────────────────────┐
  │ Web API (FastAPI + uvicorn)                                     │
  │ /api/v1 · static web app · generated theme · access policy      │
  └───────────────────────────────┬────────────────────────────────┘
                                  │
  ┌───────────────────────────────▼────────────────────────────────┐
  │ Services  (the only code that writes)                           │
  │ inventory · risk · controls · treatment · compliance ·          │
  │ assurance · oversight · reporting · program settings            │
  │        every write ──▶ permission check ──▶ event               │
  └──────┬───────────────────────┬───────────────────────┬─────────┘
         │ SQLAlchemy ORM        │ files by hash         │ queued mail
         ▼                       ▼                       ▼
  ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
  │ Database     │        │ Data home    │        │ SMTP         │
  │ SQLite, or   │        │ files/       │        │ (optional)   │
  │ PostgreSQL   │        │ exports/     │        └──────────────┘
  └──────▲───────┘        └──────────────┘
         │
  ┌──────┴───────────────────────────────────────────────────────┐
  │ Command line (riskwren)                                       │
  │ init · serve · db · users · program · demo · verify · doctor  │
  └───────────────────────────────────────────────────────────────┘
```

Nothing in this picture reaches out to the rest of the network. The only outbound connections RiskWren ever makes are to the mail server and identity provider an administrator configures, and, from wave 9, to webhook addresses an administrator registers. See [ADR-0003](decisions/0003-passive-by-design.md).

## Layers

| Layer | Package | Rule |
|---|---|---|
| **API** | `riskwren.api` | Parses requests, calls one service function, shapes the response. No business rules, no queries |
| **Services** | `riskwren.inventory`, `.risk`, `.controls`, … | All business rules. Every function that changes data takes the acting principal, checks permission, and writes through an audited session, which records an event for each change in the same transaction |
| **Model** | `riskwren.db` | SQLAlchemy ORM models, portable column types, the engine and session, and migrations |
| **Core** | `riskwren.core` | Shared, dependency-free pieces: the scoring arithmetic, the condition evaluator, clock, errors, references |

The one rule that matters most: **only services write.** The API, the command line, the demo generator, imports, and scheduled jobs all go through the same service functions, so permission checks, validation, and history cannot be bypassed by taking a different door.

## Components

- **Program settings** (`riskwren.program`). Everything the program team configures: vocabularies, the taxonomy and appetite, the scoring method, cadences, the authority table, and branding. Stored in the database, versioned, edited in the app, and exported or imported as a program pack. A built-in default pack is loaded by `riskwren init`.
- **Scoring** (`riskwren.core.scoring`). Pure functions over a scoring method: the rating for a likelihood and an impact, a control's strength, and the suggested residual rating with its working. Data in, data out, no database. The same method document is sent to the browser, where a JavaScript twin shows a rating as the assessor chooses levels; a shared set of test cases keeps the two in agreement.
- **Condition evaluator** (`riskwren.core.conditions`, wave 3). One small interpreter for the declarative conditions used by applicability rules, questionnaires, and tiering. Data in, boolean out; no expression strings and no evaluation of code.
- **Inventory** (`riskwren.inventory`). Processes, systems, third parties, and later information assets and sites; owners, links, and tags.
- **Risk** (`riskwren.risk`). The register, categories, assessments, standing, review dates, roll-up, and the risk library.
- **Controls** (`riskwren.controls`). The control library, ratings, and the links from controls to risks.
- **Treatment** (`riskwren.treatment`). Responses, plans, acceptances with the authority check, and the one table of actions.
- **Compliance** (`riskwren.compliance`, wave 2). Frameworks and requirements, crosswalks, scopes, applicability, implementations and inheritance, and readiness.
- **Assurance** (`riskwren.assurance`, wave 2). Assessments, tests, evidence, issues, and exceptions.
- **Oversight** (`riskwren.oversight`, wave 3). Schedules, campaigns and attestations, questionnaires, and indicators.
- **Reporting** (`riskwren.reporting`). The home page of what a person owes, dashboards, and later measures, snapshots, dossiers, and exports.
- **History** (`riskwren.events`). The append-only event log, its hash chain, verification, and as-of reconstruction.
- **Access** (`riskwren.auth`, `riskwren.access`). Local accounts, sessions, single sign-on, role grants, and the policy table that every route and service call is checked against.
- **Files** (`riskwren.evidence`, wave 2). Content-addressed storage in the data home, with size and type limits, and downloads that are always served as attachments.
- **Notifications and jobs** (wave 2 and 3). In-app notices; then an email outbox and a small scheduler whose jobs are rows with a lease, so exactly one process runs each.
- **Demo** (`riskwren.demo`). Builds the fictional organization by calling the services in order with a simulated clock, so every record, assessment, and event in the demo is real output of the real code. See [demo-organization.md](demo-organization.md).

## Request flow: assessing a risk

1. The browser loads the risk, its linked controls with their current effectiveness, and the scoring method from `/api/v1`. As the assessor chooses a likelihood and impact levels, the JavaScript scoring module shows the rating; for a residual assessment it shows the suggestion and its working beside the form.
2. On submit, `POST /api/v1/risks/{ref}/assessments` calls `risk.assess()`. In one transaction it checks that the principal may assess this risk, validates the levels against the current method, computes the rating and the suggestion on the server (the browser's figures are only ever a preview), writes the assessment, supersedes the previous one of the same kind, updates the copies on the risk, works out the new standing and next review date, and appends an event for each change.
3. The response carries the risk with its new ratings and standing, which the assessor sees at once.

## Storage

- **Database.** SQLAlchemy 2 ORM with a synchronous engine and one session per request. SQLite is the default: a single file in the data home, in write-ahead-log mode, with foreign keys on. PostgreSQL is selected by a URL. The model uses only portable types (a JSON type that becomes `JSONB` on PostgreSQL, and a UTC date-time type that refuses naive values), a fixed naming convention for constraints, and no database-specific SQL in application code.
- **Migrations.** Alembic, driven from inside the package with no `alembic.ini`. Revisions are numbered in order and written to run on both databases (batch mode on SQLite). Migrations run when an administrator says so (`riskwren init`, `riskwren db upgrade`), never silently at startup; `riskwren serve` refuses to start against a schema that is behind and says what to run.
- **Both databases from the first commit.** The whole test suite runs on SQLite and on PostgreSQL in continuous integration. Supporting a second database is cheap when it is never allowed to drift and expensive to retrofit.
- **Data home.** One directory holds everything that is not in the database: `files/` (evidence and attachments, stored by SHA-256), `brand/` (uploaded logos), `exports/`, and `logs/`. With SQLite the database file is here too, so backing up an installation is copying one directory.

## Web app

- **A static shell and a JSON API.** There are no server-side templates. `index.html` loads CSS and one ES module; the app fetches `/api/v1/meta` and `/api/v1/session`, then renders. Unknown paths return the shell so that the client-side router can handle them.
- **No build step, no frameworks.** Plain ES modules, a small DOM helper, a History API router in which the URL holds all view state, and one module per page. What is in the repository is what the browser runs.
- **Strict content security policy.** `default-src 'self'` with no inline script or style and no third-party origins. The DOM helper only ever inserts data as text.
- **Generated theme.** `/theme.css` is produced by the server from the branding settings and loaded after the built-in palettes, so an organization's colors apply without touching a file. See [ux.md](ux.md).
- **Charts, the heat map, and graphs** are drawn as SVG by small modules in the app. No charting library.
- **Budgets.** The gzipped app shell stays under 100 KB and each lazily loaded part under 40 KB; tests enforce both, along with the rules above.

## API

- Everything the web app does, it does through `/api/v1`. There is no private back channel.
- Success responses are `{"data": …, "meta": …}`. Lists take `limit` and an opaque `cursor`. Errors are `application/problem+json`.
- Every route appears in one **policy table** that names the permission it requires. A route missing from the table is refused, and a test fails the build if one is added without a policy.
- The OpenAPI document is generated, committed as `docs/openapi.json`, and kept current by a test. The documentation site renders the API reference from it.
- Uploads are sent as the raw request body with the file name in a header, which avoids a multipart parser.

## Configuration

RiskWren separates two kinds of configuration by one rule: **the deployment lives in a file; the program lives in the database.**

| | Deployment | Program |
|---|---|---|
| **What** | Server address and port, database URL, data home, sign-in providers, mail server, session lifetimes | Vocabularies, taxonomy, appetite, the scoring method, cadences, authority, libraries, frameworks, branding |
| **Where** | `riskwren.toml`, with environment overrides (`RISKWREN_<SECTION>_<KEY>`) | The database |
| **Who** | The administrator who runs the server | The manager and admin roles, in the app |
| **Changes** | Take effect on restart | Take effect at once, on every worker, and are recorded as events |
| **Moves by** | Copying the file | Exporting and importing a program pack |

The file is read with the standard library's TOML parser into typed, frozen settings. Unknown sections and keys are errors, every problem is reported in one pass, and relative paths resolve against the file's own directory so an installation moves as a unit. **Secrets never go in the file**: a key that looks like a secret is rejected, and the file instead names the environment variable that holds it.

## Runtime and deployment

- `riskwren serve` runs uvicorn with one or more workers. All state is in the database, so workers share nothing in memory that matters.
- Sign-in is always required. `riskwren init` creates the first administrator, and the server refuses to start without one.
- Behind a reverse proxy that terminates TLS, RiskWren reads `X-Forwarded-Proto` and `X-Forwarded-Host` to set secure cookies, check request origins, and build sign-in redirects.
- Health endpoints: `/api/v1/health/live` and `/api/v1/health/ready` (database reachable and schema current).
- Deployment recipes (a container image, a compose file with PostgreSQL, a hardened systemd unit, and proxy examples) arrive in wave 9 under `deploy/`.

## Directory layout

```text
riskwren/
├── pyproject.toml · uv.lock · .python-version
├── README.md · CHANGELOG.md · CONTRIBUTING.md · SECURITY.md · LICENSE · NOTICE
├── riskwren.example.toml
├── spec/                      this folder
├── docs/                      guides (the site's source), images, openapi.json
├── deploy/                    container, systemd, proxy (wave 9)
├── scripts/                   check_terms.py, dev-postgres.sh, test-both.sh, pack builders, site/
├── tests/                     pytest suite, js/ tests, fixtures
└── src/riskwren/
    ├── __init__.py · __main__.py · config.py · home.py
    ├── core/                  scoring, conditions, clock, errors, log
    ├── db/                    engine, session, types, refs, models/, migrations/
    ├── auth/                  passwords, sessions, (wave 3) oidc
    ├── access/                roles, principal, policy table
    ├── events/                event log, chain, actor
    ├── people/                accounts, units, imports
    ├── program/               settings, vocabularies, method, packs, branding
    ├── inventory/ · risk/ · controls/ · treatment/
    ├── compliance/ · assurance/        (wave 2)
    ├── oversight/                      (wave 3)
    ├── reporting/
    ├── demo/                  the fictional organization
    ├── api/                   app factory, routers/, problems, security headers, static
    ├── cli/                   argparse commands, doctor, generated reference
    ├── resources/             example config, default program pack, libraries, framework packs
    └── web/static/            index.html, css/, js/core, js/components, js/pages, img/
```

## Cross-cutting concerns

| Concern | Approach |
|---|---|
| **Time** | UTC everywhere in storage; an injectable clock, so tests and the demo can run at any date |
| **Identifiers** | Integer keys inside; permanent prefixed references outside ([data-model.md](data-model.md#conventions)) |
| **Errors** | One exception hierarchy; the API maps it to problem documents and the command line to messages and exit codes |
| **Validation** | At the service boundary, so the API, imports, and the command line get the same answers |
| **Concurrency** | Optimistic: records carry a version, and a stale edit is refused with the current values, never silently overwritten |
| **Visibility** | One function per record type decides what a principal may see; single records, lists, counts, and exports all call it |
| **Logging** | Standard library logging to the console and the data home; no request bodies or answers are logged |
| **Security** | [security.md](security.md) |
| **Testing** | pytest, offline, on both databases; a role-by-route matrix test; JavaScript tests with Node's built-in runner; the demo build as an end-to-end test |
| **Private terms** | A script checks committed content against a local, untracked list of words that must not appear |

## Dependency budget

Every runtime dependency must justify itself, and adding one requires a decision record.

| Package | Why |
|---|---|
| `fastapi` | The web framework and OpenAPI generation (brings `pydantic` and `starlette`) |
| `uvicorn` | The server |
| `sqlalchemy` | The ORM, and one model for two databases |
| `alembic` | Migrations |
| `httpx` | Calls to the identity provider and, later, webhooks; also the test client |
| `psycopg` *(optional extra)* | The PostgreSQL driver, installed only when PostgreSQL is used |

Deliberately absent, with what is used instead:

| Not used | Instead |
|---|---|
| A template engine | A static shell and the JSON API |
| A password-hashing package | `hashlib.scrypt` from the standard library |
| A JOSE or OpenID Connect package | A few hundred lines over the standard library and `httpx` ([ADR-0008](decisions/0008-accounts-and-single-sign-on.md)) |
| A multipart parser | Raw-body uploads |
| A task queue or broker | Leased job rows in the database |
| A search engine | A search table in the same database |
| A PDF library | Print styles; the browser prints to PDF |
| A spreadsheet library | CSV, read and written with the standard library |
| A numerical library | The standard library's `random` and `statistics` for simulation |
| A YAML parser | TOML for the deployment file and JSON for packs, both in the standard library |
| Any JavaScript package | Hand-written ES modules |

Development adds only `pytest` and `ruff`. The documentation site and screenshot capture need Node 22 and no packages ([ADR-0009](decisions/0009-documentation-toolchain.md)).
