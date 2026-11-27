# RiskWren

**Risk and compliance people actually keep current.**

**Documentation, with pictures: <https://robert-mcdermott.github.io/riskwren/>**

RiskWren is an open system of record for governance, risk, and compliance: one connected register of what an organization has, what could go wrong, what it must comply with, what it does about both, and the proof.

It is built first for research and health organizations that are not large corporations: research institutes, academic medical centers, universities, and the nonprofits around them. Within them it is built first for the security team, whose work of frameworks, assessments, findings, and exceptions is the path it gets right before anything else. Nothing in it is specific to either, and any organization that wants a lightweight, self-hosted risk and compliance system can adopt it.

- **One connected register, not a suite of modules.** A control is described once, reduces the risks it is linked to, answers every requirement it is mapped to, and is tested once.
- **Test once, satisfy many.** One test result shows against every framework and every scope that relies on the control, and readiness is worked out from tests and evidence, never typed in.
- **Working on the first day.** A risk taxonomy, a scoring method with defined scales, libraries of common risks and controls, and four public frameworks already mapped to those controls arrive loaded.
- **Built for the people who own the risks.** One page of what each person owes, each item a short task.
- **Rating and standing are different things.** How much is at stake, and whether it is in order, are always two signals.
- **Show the reasoning; people decide.** Every suggested rating opens to the arithmetic behind it. Named people assess and accept, and say why.
- **A history that cannot be quietly changed.** Every change is in an append-only, hash-chained log.
- **Passive by design.** No scanners, collectors, or agents, and no access to anything else on the network.
- **Open and yours.** Apache 2.0, no paid edition, SQLite on a laptop or PostgreSQL on a server, and your own name and colors.

## Quickstart

You need [uv](https://docs.astral.sh/uv/), which provides the right Python (3.12 or later). Clone this repository, then run these from its directory:

```bash
uv sync                   # install RiskWren
uv run riskwren init      # write riskwren.toml, create ./var and the database, create your administrator
uv run riskwren doctor    # check the installation
uv run riskwren serve     # run it at http://127.0.0.1:8000
```

`init` asks for your email address, your name, and a password of at least 12 characters. Open the address `serve` prints and sign in.

The administrator account sets the installation up: units, people, and appearance. To run the register, give someone the manager role under Admin → People, and stewards and leaders for the units that will use it. [Getting started](docs/getting-started.md) walks through all of it.

## Try the demo

To see RiskWren with data in it before you set anything up, build the demo organization:

```bash
uv run riskwren demo                                 # builds ./demo
uv run riskwren --config demo/riskwren.toml serve    # runs it at http://127.0.0.1:8020
```

The demo is the Northmere Institute for Health Research, a fictional research institute with a clinic and two years of history: 60 units, about 210 people, 230 inventory records, 180 risks, and about 135 controls, with four scopes held to frameworks and between a half and three quarters ready, an assessment in progress, evidence going stale, issues and exceptions at every stage, the security office's policies and the standards and procedures beneath them, agreements with their dates, and a risk committee that meets each quarter. Nothing in it is real.

Its sign-in page offers ten sample people and asks for no password. Try a few:

| Sign in as | To see |
|---|---|
| The security leader | The compliance dashboard: readiness by scope, controls failing a test, issues by age, and exceptions about to end; the security policies, an exception to one waiting for a decision, and an agreement whose notice date is near |
| The risk manager | The whole register, the risk dashboard, the heat map, the program, where a change to the matrix can be previewed, and the risk committee's next session |
| The steward | One unit's inventory and risks, and a critical risk brought to high by controls, with its plan |
| The unit leader | A high risk that is beyond their authority to accept |
| The assessor | An assessment in progress, a result to review, an attestation campaign most of the way through, and a risk analysis half done |
| The auditor | Everything, read-only, with every change in one place |
| A staff member | Home for someone with one action to finish and a policy to acknowledge, the policy library, and only their own unit's part of the register |

A demo listens only on the machine it runs on. See [Configuration](docs/configuration.md#the-demo-and-the-network) before changing that.

## What is in this release

Version 0.4.0 is *Policy and obligations*: the organization's own word, and what it has promised others. It follows 0.3.0, which keeps the register current, and 0.2.0, which added compliance to it.

**Policy and obligations, new in 0.4.0**

- **Policies, standards, procedures, and guidelines** written here in a simple Markdown, linked to where they are kept, or attached as files, each implementing the one above it.
- **Approval by named people,** none of whom wrote it, and **published versions that never change:** each is fingerprinted, and `riskwren verify` checks it. Any two versions compare side by side, and each document is reviewed on a cadence.
- **A policy library** where everyone reads what applies to them, on a phone as well as a desk, and **acknowledges** it. A new version asks again; who has and who has not is shown by unit, and a campaign chases the rest.
- **A document directs controls and answers requirements,** shown on each side, so "is there a policy for this?" has an answer with a date. A unit that cannot follow one for a time asks for an **exception** to it.
- **Agreements:** awards, data use agreements, business associate agreements, and contracts, with their dates and notice periods. The terms an agreement imposes reach every scope that holds what it covers, and its owners are warned before its notice date and its end.
- **A framework's new version is loaded beside the old,** with what changed by code and what it touches. A scope moves when its keepers say so, taking its decisions and exceptions with it. SP 800-53 Rev. 4 ships for programs that still name it, and a publisher's mapping suggests crosswalks a person confirms.
- **Strategic objectives** that risks name, and **committee sessions** whose agenda is drawn from the register and whose every decision shows on the record it was about.

**Keeping watch, from 0.3.0**

- **Single sign-on, if you want it.** OpenID Connect beside local accounts, tested against a stand-in provider and built to work with Microsoft Entra ID: roles and units come from the provider's roles or groups. Out of the box it is local accounts and passwords, as before.
- **It knows what is due.** A scheduler brings the register up to date and reminds whoever a thing is waiting on: before its date, when it passes, then their steward, then their leader. Email is optional, and each person chooses how much of it they get.
- **Questionnaires as versioned data,** with questions that appear by condition. An answer always reads as it was asked.
- **Campaigns:** ask every control owner to attest, every risk owner to look again, every steward to check a unit's records, or for a named piece of evidence, and see who has answered, by unit.
- **An attestation is never mistaken for a test.** What an owner says of a control is shown apart from its rating and never makes a requirement verified.
- **Indicators:** a number someone already reads, with a warning level and a limit. Past the limit, its owners and the owners of the risks it warns of are told.
- **One search** across every kind of record, cut to what the searcher may open; **saved views** of any list; what each record is **missing**; and likely **duplicates**.
- **When someone leaves,** nothing is left without an owner: what they alone answered for passes to the steward of its unit, and is passed on for good in one step.
- **The program is edited in the app:** categories, scales, the matrix, appetite, cadences, and vocabularies, with a **preview of every risk a change would move** before anything is published.
- **Risk analyses:** each thing in a scope taken against each threat, raising risks or refreshing the ones already there, with a report of what was considered.

**Compliance, from 0.2.0**

- **Frameworks** carried as published: the NIST Cybersecurity Framework 2.0, NIST SP 800-53 Rev. 5 with its baselines, NIST SP 800-171 Rev. 3, and the HIPAA Security Rule. An agreement or an internal standard is entered as a framework of your own.
- **Crosswalks:** a control is mapped to every requirement it answers, in any number of frameworks. The common controls arrive mapped.
- **Scopes:** a boundary held to one or more frameworks, with what applies in it and how each control is done there. One scope provides controls and others **inherit** them.
- **Evidence** collected once, attached to everything it supports, and no longer counting after its date. Files are stored by content and only ever downloaded.
- **Assessments and tests:** a result is recorded by someone who does not own the control and counts once a second person confirms it. It then moves the control, every requirement it answers in every scope that relies on it, and every risk it reduces.
- **Readiness** in six states, each with its reason, and a **compliance dashboard** whose every figure opens the list it counts.
- **Issues** with a date that follows from severity, worked through actions, and closed only when someone who does not own them confirms it. A failed test opens one.
- **Exceptions** decided by someone who did not ask, that end by themselves.
- **A picture of how any record is connected,** every change in one place, and notices in the app.
- **Import and export:** every list as CSV or JSON, and records in from a spreadsheet with a dry run that reports every problem by row.

**The register, from 0.1.0**

- **An inventory** of processes, systems, third parties, and information assets, each with a permanent reference, a unit, named owners, a criticality, and links that say what relies on what.
- **A risk register** with a library of 57 common risks, nine families of risk each with an appetite, and inherent, residual, and target ratings that are judgments by named people with reasons.
- **A scoring method you can read:** five levels of likelihood and of impact on five dimensions, each with a written definition, combined by a matrix.
- **Controls of known effectiveness,** from a library of 75, and a residual rating **suggested from the controls with its working shown.**
- **Standing, apart from rating:** within appetite, being treated, accepted, or needing a decision.
- **Treatment:** plans with owned, dated actions, and acceptance by a leader with the authority for that rating, until a date, never of their own risk.
- **Home, a heat map, and a risk dashboard.**
- **Roles and units:** seven roles, four of them limited to a unit and everything beneath it, and a hierarchy of any depth.
- **An append-only history** chained by hash, checked with `riskwren verify`.
- **Branding and themes,** a JSON API under `/api/v1`, a command line for setup and recovery, and the program as a file.

Third parties come next, then reporting, audits, and incidents. The [roadmap](spec/roadmap.md) says what is next, and the [changelog](CHANGELOG.md) lists everything in each release.

## Documentation

Start with the [guide index](docs/README.md), or go straight to the guide for your part:

| Guide | For |
|---|---|
| [Getting started](docs/getting-started.md) | Whoever installs RiskWren and sets it up |
| [The register](docs/the-register.md) | Everyone who owns, assesses, or reads a risk |
| [Compliance](docs/compliance.md) | Security and compliance leads, and the stewards of what must comply |
| [Evidence and testing](docs/evidence-and-testing.md) | Control owners and assessors |
| [Issues and exceptions](docs/issues-and-exceptions.md) | Whoever fixes, checks, or decides |
| [Policies](docs/policies.md) | Whoever writes, approves, or keeps the organization's policies |
| [Running the program](docs/running-the-program.md) | The risk, compliance, and security assurance team, and administrators |
| [Configuration](docs/configuration.md) | Whoever runs the server |
| [API](docs/api.md) | Anyone connecting another system |
| [Command reference](docs/cli.md) | Every `riskwren` command and option |

The design behind the product is in [`spec/`](spec/README.md): the [vision](spec/vision.md), the [engine](spec/engine.md), and the [roadmap](spec/roadmap.md).

## Development

```bash
uv sync                           # install RiskWren and its development tools
uv run riskwren serve --reload    # restart when the code changes
uv run pytest                     # the tests, on SQLite
scripts/test-both.sh              # the tests on SQLite and on a disposable PostgreSQL
uv run ruff check && uv run ruff format --check
node scripts/a11y-audit.mjs       # the accessibility audit, over a fresh demo
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for how the work is organized, and [SECURITY.md](SECURITY.md) to report a vulnerability.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
