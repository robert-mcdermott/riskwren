# Getting started

This guide takes you from nothing to a running RiskWren that your organization can sign in to. It is for whoever installs it and sets it up. Allow about fifteen minutes.

If you only want to look around first, skip to [Explore the demo organization](#explore-the-demo-organization).

## What you need

- [uv](https://docs.astral.sh/uv/), which provides the right Python (3.12 or later).
- A copy of this repository.

Every command in these guides is run through `uv run riskwren …` from the repository directory. The full list is in the [command reference](cli.md).

## Install

```bash
uv sync
```

## Set up the installation

```bash
uv run riskwren init
```

`init` does five things:

1. Writes `riskwren.toml`, the deployment settings, in the current directory.
2. Creates the data home, `./var`, which holds everything that is not in the database.
3. Creates the database. With no other setting, this is a SQLite file inside the data home.
4. Loads the default program: nine families of risk with an appetite for each, a scoring method with defined scales, review cadences, the table of who may accept what, a library of 57 common risks, and a library of 56 common controls.
5. Asks for your email address, your name, and a password, and creates the first administrator.

The password needs at least 12 characters. Length matters more than symbols: a few unrelated words make a good one.

`init` is safe to run again. It leaves an existing configuration file alone, adds only what is missing from the program, and creates an administrator only if there is none.

To set up without being asked anything, name the administrator and pipe the password in:

```bash
printf '%s' "$ADMIN_PASSWORD" | uv run riskwren init \
  --admin-email you@example.org --admin-name "Your Name" --password-stdin
```

## Check it

```bash
uv run riskwren doctor
```

`doctor` checks the configuration, the data home, that the database answers, that its schema is the one this version expects, that the database still refuses changes to the history, and that the history verifies. It exits with 1 if anything must be fixed.

## Run it

```bash
uv run riskwren serve
```

The server prints its address, by default `http://127.0.0.1:8000`. Use `--port` to pick another port.

`serve` refuses to start in three cases, and says what to do in each:

| It says | Do this |
|---|---|
| The database schema is behind | `uv run riskwren db upgrade` |
| There is no administrator yet | `uv run riskwren users add you@example.org --name "Your Name" --role admin` |
| The port is already in use | Stop what is using it, or pass `--port` |

As installed, RiskWren listens only on the machine it runs on. To put it in front of other people, read [Configuration](configuration.md) first.

## Sign in for the first time

Open the address in a browser and sign in with the email address and password you gave `init`.

This release signs in with local accounts: an email address and a password held by RiskWren. Single sign-on comes later; see the [roadmap](../spec/roadmap.md).

- Five failed attempts within fifteen minutes stop sign-in for that account from that address for a few minutes.
- A sign-in ends after 12 hours without activity, and after 7 days in any case. Both are [settings](configuration.md#server).
- To change your password, open the account menu at the top right and choose **Your account**. Changing it signs out your other sessions.
- If you cannot sign in at all, reset the password from the command line: `uv run riskwren users reset-password you@example.org`.

## Set up the organization

The administrator account sets the installation up. It does not assess or accept risk: that belongs to the roles below, and an administrator who also does that work is given a second role.

### Units

**Admin → Units** holds the organization as a hierarchy of any depth: divisions, departments, labs, cores, clinics, offices. Every record belongs to a unit, roles can be limited to a unit and everything beneath it, and figures roll up the tree. Give each unit a short code; imports and the command line refer to units by it.

### People and roles

**Admin → People** adds accounts and gives them roles. A person with no role is a member: they see what they are named on, and their own unit's register if the program allows it.

| Role | What it is for |
|---|---|
| **Manager** | The risk and compliance team. Edits any record, shapes the program, reads everything. Can be limited to a unit |
| **Assessor** | Assesses risks and rates controls they do not own. Can be limited to a unit |
| **Auditor** | Reads everything, including the full history, and changes nothing |
| **Leader** | Leads a unit. Sees it and everything beneath it, and may accept risk in it up to a limit set on the role |
| **Steward** | Keeps a unit's records: adds and edits its processes, systems, third parties, risks, and controls |
| **Admin** | Accounts, units, appearance, and system settings |

A leader's limit is the highest rating they may accept: moderate, high, or critical. [Running the program](running-the-program.md#who-may-accept-what) explains how it is used.

### Import units and people

Both screens take a CSV file, which is the quick way to load an organization. Each import can be run dry first and reports every problem by row, so nothing is half-loaded. The import dialog shows the columns it expects.

### Appearance

**Admin → Appearance** sets the product's name, your organization's name, a logo, an accent color, the default palette, and how ratings are colored. See [Running the program](running-the-program.md#appearance).

## Explore the demo organization

To see RiskWren with data in it before you set anything up, build the demo:

```bash
uv run riskwren demo                                 # builds ./demo
uv run riskwren --config demo/riskwren.toml serve    # runs it at http://127.0.0.1:8020
```

The demo is the Northmere Institute for Health Research, a fictional research institute with an outpatient clinic and two years of history: 60 units, about 210 people, 220 processes, systems, and third parties, 180 risks, and 110 controls, with their assessments, ratings, plans, and acceptances. Nothing in it is real, and every record was made by the same code the app uses, so its history verifies like any other.

Its sign-in page offers nine sample people and asks for no password:

| Sign in as | To see |
|---|---|
| The risk manager | The whole register, the dashboard, the heat map, and records that have lost their owner |
| The steward of the Biospecimen Repository | A unit's inventory and risks, and a critical risk brought to high by controls, with its plan |
| The unit leader | A leader whose limit is moderate, and a high risk they were not allowed to accept |
| The division leader | Acceptances given, one of them expiring next month |
| The executive | The one person who may accept a critical risk |
| The assessor | Rating controls and assessing risks across the organization |
| The auditor | Everything, read-only, with the full history |
| The administrator | People, units, and appearance, and no part in the register's judgments |
| A staff member | Home for someone with one action to finish and one risk to review |

`riskwren demo --seed 2` builds a different Northmere with the same shape, and `--force` rebuilds one that is already there.

A demo listens only on the machine it runs on. See [Configuration](configuration.md#the-demo-and-the-network) before changing that.

## Next

- To start recording what you have and what could go wrong, read [The register](the-register.md).
- To set appetite, cadences, and who sees what, read [Running the program](running-the-program.md).
