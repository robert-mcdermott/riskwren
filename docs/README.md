# RiskWren documentation

These guides describe RiskWren 0.1.0. Read them in this order if you are new, or go straight to the one for your part.

## The guides

| | Guide | For | Covers |
|---|---|---|---|
| 1 | [Getting started](getting-started.md) | Whoever installs RiskWren | Installing, `init`, `doctor`, `serve`, first sign-in, the demo organization, units and people |
| 2 | [The register](the-register.md) | Everyone who owns, assesses, or reads a risk | The inventory, risks and their three ratings, controls, what the controls suggest, plans, actions, and acceptance |
| 3 | [Running the program](running-the-program.md) | Risk managers and administrators | Roles and scope, who sees what, appetite, the scoring method, cadences, who may accept what, program packs, the dashboard, the history, appearance |
| 4 | [Configuration](configuration.md) | Whoever runs the server | `riskwren.toml`, environment overrides, the data home, PostgreSQL, reverse proxies, the demo guard |
| 5 | [API](api.md) | Anyone connecting another system | Sign-in, the CSRF token, responses, errors, lists, and a table of routes |

## Reference

These two are written from the code, so they always match the version they ship with.

| Reference | What it is |
|---|---|
| [Command reference](cli.md) | Every `riskwren` command and option |
| [openapi.json](openapi.json) | The OpenAPI document for the API. A running server also serves it at `/api/openapi.json` |

## Find the answer to a question

| Question | Where |
|---|---|
| How do I try it without setting anything up? | [Explore the demo organization](getting-started.md#explore-the-demo-organization) |
| What is the difference between a rating and a standing? | [Rating and standing](the-register.md#rating-and-standing) |
| Where does the suggested residual rating come from? | [What the controls suggest](the-register.md#what-the-controls-suggest) |
| Why can I not accept this risk? | [Accept a risk](the-register.md#accept-a-risk) |
| Why is a risk flagged as in doubt? | [When the picture changes](the-register.md#when-the-picture-changes) |
| How do I bring in my units and people? | [Import units and people](getting-started.md#import-units-and-people) |
| Who can see a risk? | [Who sees what](running-the-program.md#who-sees-what) |
| How do I change appetite, the scales, or the review cadence? | [Shape the program](running-the-program.md#shape-the-program) |
| What does a dashboard figure count? | [Read the dashboard](running-the-program.md#read-the-dashboard) |
| How do I move to PostgreSQL? | [Use PostgreSQL](configuration.md#use-postgresql) |
| How do I put it behind a proxy? | [Run behind a reverse proxy](configuration.md#run-behind-a-reverse-proxy) |
| Nobody can sign in. How do I get back in? | [`riskwren users`](cli.md#riskwren-users) |

## What this release does not do yet

Version 0.1.0 is the register: an inventory, risks, controls, and treatment. Frameworks and requirements, evidence, control testing, issues, and the dependency graph arrive in the next release. This release signs in with local accounts and sends no email; single sign-on, reminders, and scheduled jobs follow. The [roadmap](../spec/roadmap.md) says what comes next and in what order, and the [changelog](../CHANGELOG.md) lists what is in each release.

## More

- The design behind the product is in [`spec/`](../spec/README.md).
- To work on RiskWren itself, see [CONTRIBUTING.md](../CONTRIBUTING.md).
- To report a security problem, see [SECURITY.md](../SECURITY.md).
