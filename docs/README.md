# RiskWren documentation

These guides describe RiskWren 0.2.1. Read them in this order if you are new, or go straight to the one for your part. They are also published, with search, at <https://robert-mcdermott.github.io/riskwren/>.

## The guides

| | Guide | For | Covers |
|---|---|---|---|
| 1 | [Getting started](getting-started.md) | Whoever installs RiskWren | Installing, `init`, `doctor`, `serve`, first sign-in, the demo organization, units and people |
| 2 | [The register](the-register.md) | Everyone who owns, assesses, or reads a risk | The inventory, risks and their three ratings, controls, what the controls suggest, plans, actions, and acceptance |
| 3 | [Compliance](compliance.md) | Security and compliance leads, and the stewards of what must comply | Frameworks, mapping controls to requirements, scopes, inherited controls, readiness, the compliance dashboard, connections |
| 4 | [Evidence and testing](evidence-and-testing.md) | Control owners and assessors | Evidence and its dates, files, assessments, tests, independence, and what a result changes |
| 5 | [Issues and exceptions](issues-and-exceptions.md) | Whoever fixes, checks, or decides | The issue register, severity and dates, actions, closure confirmed by someone else, exceptions, the plan of action, notices |
| 6 | [Running the program](running-the-program.md) | The risk, compliance, and security assurance team, and administrators | Roles and scope, who sees what, appetite, the scoring method, cadences, who may accept what, program packs, the dashboards, the history, appearance |
| 7 | [Configuration](configuration.md) | Whoever runs the server | `riskwren.toml`, environment overrides, the data home, optional single sign-on, PostgreSQL, upgrading, reverse proxies, the demo guard |
| 8 | [API](api.md) | Anyone connecting another system | Sign-in, the CSRF token, responses, errors, lists, and a table of routes |

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
| How do I bring in the systems, risks, or controls I already have in a spreadsheet? | [Import and export](the-register.md#import-and-export) |
| Where are we against a framework? | [The compliance dashboard](compliance.md#the-compliance-dashboard) |
| What is the difference between in place and verified? | [Readiness](compliance.md#readiness) |
| A team relies on a control somebody else runs. How is that recorded? | [Inherited controls](compliance.md#inherited-controls) |
| How do I enter a data use agreement or a sponsor's requirements? | [A framework of your own](compliance.md#a-framework-of-your-own) |
| Why can I not record this test result, or confirm it? | [Independence, and a second pair of eyes](evidence-and-testing.md#independence-and-a-second-pair-of-eyes) |
| Why did a requirement stop being verified? | [Evidence stops counting](evidence-and-testing.md#evidence-stops-counting) |
| A test failed. What happens now? | [From a failed test](issues-and-exceptions.md#from-a-failed-test) |
| Why can I not close my own issue? | [Close it](issues-and-exceptions.md#close-it) |
| We cannot meet a requirement yet. What do we do? | [Exceptions](issues-and-exceptions.md#exceptions) |
| What is everything connected to this system? | [Connections](compliance.md#connections) |
| Who changed this, and when? | [The history](running-the-program.md#the-history) |
| Who can see a risk? | [Who sees what](running-the-program.md#who-sees-what) |
| How do I change appetite, the scales, or the review cadence? | [Shape the program](running-the-program.md#shape-the-program) |
| What does a dashboard figure count? | [Read the dashboards](running-the-program.md#read-the-dashboards) |
| How do I move to PostgreSQL? | [Use PostgreSQL](configuration.md#use-postgresql) |
| How do I put it behind a proxy? | [Run behind a reverse proxy](configuration.md#run-behind-a-reverse-proxy) |
| How do I let people sign in with Entra ID or another identity provider? | [Single sign-on](configuration.md#single-sign-on) |
| Nobody can sign in. How do I get back in? | [`riskwren users`](cli.md#riskwren-users) |

## What this release does not do yet

Version 0.2.1 is the register and compliance: an inventory, risks, controls, and treatment; frameworks, scopes, evidence, tests, issues, and exceptions. It signs in with local accounts and sends no email: notices are in the app. Single sign-on, email, reminders, attestations, and scheduled jobs arrive in the next release, and until then dates are caught up when the register is read. Policies, supplier reviews, audits, and incidents follow in later ones. The [roadmap](../spec/roadmap.md) says what comes next and in what order, and the [changelog](../CHANGELOG.md) lists what is in each release.

## More

- The design behind the product is in [`spec/`](../spec/README.md).
- To work on RiskWren itself, see [CONTRIBUTING.md](../CONTRIBUTING.md).
- To report a security problem, see [SECURITY.md](../SECURITY.md).
