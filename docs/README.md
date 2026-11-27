# RiskWren documentation

These guides describe RiskWren 0.6.0. Read them in this order if you are new, or go straight to the one for your part. They are also published, with search, at <https://robert-mcdermott.github.io/riskwren/>.

## The guides

| | Guide | For | Covers |
|---|---|---|---|
| 1 | [Getting started](getting-started.md) | Whoever installs RiskWren | Installing, `init`, `doctor`, `serve`, first sign-in, the demo organization, units and people |
| 2 | [The register](the-register.md) | Everyone who owns, assesses, or reads a risk | The inventory, risks and their three ratings, controls, what the controls suggest, plans, actions, and acceptance; the objectives a risk threatens; risk analyses, search, saved views, what a record is missing, and indicators |
| 3 | [Compliance](compliance.md) | Security and compliance leads, and the stewards of what must comply | Frameworks, new versions and moving a scope to one, mapping controls to requirements and the crosswalks a publisher suggests, scopes, inherited controls, agreements and the terms they impose, readiness, the compliance dashboard, connections |
| 4 | [Evidence and testing](evidence-and-testing.md) | Control owners and assessors | Evidence and its dates, files, assessments, tests, independence, and what a result changes |
| 5 | [Issues and exceptions](issues-and-exceptions.md) | Whoever fixes, checks, or decides | The issue register, severity and dates, actions, closure confirmed by someone else, exceptions, the plan of action, notices |
| 6 | [Policies](policies.md) | Whoever writes, approves, or keeps the organization's policies | Policies, standards, procedures, and guidelines; writing a version; approval; publishing; comparing versions; review; what a document governs; exceptions to a document; who a document applies to; the policy library; acknowledgment |
| 7 | [Third parties](third-parties.md) | Whoever looks after the organization's suppliers and partners, most often the security office | Third parties and their services; what each reaches and handles; tiering by the program's rules; contacts; due diligence questionnaires sent through a link that needs no account; reviewing the answers and their concerns; reports and certificates, and what each covers and leaves to the organization; who agreements are with, and the stop where shared information has no covering agreement; findings followed up with the third party; review again; offboarding; subcontractors |
| 8 | [Running the program](running-the-program.md) | The risk, compliance, and security assurance team, and administrators | Roles and scope, who sees what, the program and its editors, questionnaires, campaigns, committee sessions, when someone leaves, reminders, the dashboards, the history, appearance |
| 9 | [Configuration](configuration.md) | Whoever runs the server | `riskwren.toml`, environment overrides, the data home, optional single sign-on and email, scheduled work, PostgreSQL, upgrading, reverse proxies, the demo guard |
| 10 | [API](api.md) | Anyone connecting another system | Sign-in, the CSRF token, responses, errors, lists, and a table of routes |

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
| Which of the strategic plan's aims are most at risk? | [The objectives it threatens](the-register.md#the-objectives-it-threatens) |
| How does a committee's decision reach the record it was about? | [Committee sessions](running-the-program.md#committee-sessions) |
| Which scopes does an agreement bind, and when must it be renewed? | [Agreements](compliance.md#agreements) |
| A framework has a new version. What changed, and how does a scope move to it? | [A new version of a framework](compliance.md#a-new-version-of-a-framework) |
| Why can I not record this test result, or confirm it? | [Independence, and a second pair of eyes](evidence-and-testing.md#independence-and-a-second-pair-of-eyes) |
| Why did a requirement stop being verified? | [Evidence stops counting](evidence-and-testing.md#evidence-stops-counting) |
| A test failed. What happens now? | [From a failed test](issues-and-exceptions.md#from-a-failed-test) |
| Why can I not close my own issue? | [Close it](issues-and-exceptions.md#close-it) |
| We cannot meet a requirement yet. What do we do? | [Exceptions](issues-and-exceptions.md#exceptions) |
| What is everything connected to this system? | [Connections](compliance.md#connections) |
| Who changed this, and when? | [The history](running-the-program.md#the-history) |
| Who can see a risk? | [Who sees what](running-the-program.md#who-sees-what) |
| How do I get a policy approved and published? | [Approval](policies.md#approval) |
| What changed between two versions of a procedure? | [Publishing](policies.md#publishing) |
| Is there a policy for this requirement? | [What it governs](policies.md#what-it-governs) |
| A lab cannot meet a standard yet: how does it ask for an exception? | [Exceptions to a document](policies.md#exceptions-to-a-document) |
| Where do staff read the policies that apply to them? | [The policy library](policies.md#the-policy-library) |
| Who has not yet acknowledged the acceptable use policy? | [Who has acknowledged it](policies.md#who-has-acknowledged-it) |
| Which suppliers hold our restricted information, and through what? | [Third parties and their services](third-parties.md#third-parties-and-their-services) |
| Why is this supplier Tier 1? | [Tiering](third-parties.md#tiering) |
| How do I send a supplier a security questionnaire without giving them an account? | [Send it](third-parties.md#send-it) |
| Is the link we send a supplier safe? | [Send it](third-parties.md#send-it) |
| What does a supplier's SOC 2 report leave for us to do? | [Review a report](third-parties.md#review-a-report) |
| Who holds our patient records without a business associate agreement? | [Coverage](third-parties.md#coverage) |
| A supplier told us of a breach. How do we review it again now? | [Review again](third-parties.md#review-again) |
| How do we end a supplier relationship properly? | [Ending a relationship](third-parties.md#ending-a-relationship) |
| Are we getting better? Which figures moved this quarter? | [Measures](running-the-program.md#measures) |
| Which units, frameworks, or suppliers need attention, and why do issues happen? | [Portfolio](running-the-program.md#portfolio) |
| What did we tell leadership last quarter, and has the report been changed since? | [Leadership reports](running-the-program.md#leadership-reports) |
| What did the register say on the day of the audit? Who owned this risk in March? | [As of a date](running-the-program.md#as-of-a-date) |
| The auditor wants everything about this scope, in a form they can check | [Dossiers](running-the-program.md#dossiers) |
| Can we give our system security plan to an agency that reads OSCAL? | [The security plan and OSCAL](compliance.md#the-security-plan-and-oscal) |
| How do I change appetite, the scales, or the review cadence? | [Shape the program](running-the-program.md#shape-the-program) |
| Which risks would change if I changed the matrix? | [See what a change would do](running-the-program.md#see-what-a-change-would-do-before-you-make-it) |
| How do I add a kind of system, or rename a data class? | [Vocabularies](running-the-program.md#vocabularies) |
| How do I run a security risk analysis over a scope? | [Risk analyses](the-register.md#risk-analyses) |
| What would two weeks of ransomware cost us, in dollars, and how sure are we? | [Estimates in ranges](the-register.md#estimates-in-ranges), [Scenarios](the-register.md#scenarios) |
| Which controls stand between the causes of this risk and what follows it? | [The bow-tie](the-register.md#the-bow-tie) |
| What does a dashboard figure count? | [Read the dashboards](running-the-program.md#read-the-dashboards) |
| How do I move to PostgreSQL? | [Use PostgreSQL](configuration.md#use-postgresql) |
| How do I put it behind a proxy? | [Run behind a reverse proxy](configuration.md#run-behind-a-reverse-proxy) |
| How do I send notices and reminders by email? | [Email](configuration.md#email) |
| How do I ask every control owner to attest, and see who has? | [Campaigns](running-the-program.md#campaigns) |
| How do I get warning of a risk before it happens? | [Indicators](the-register.md#indicators) |
| Does an owner saying a control works make it verified? | [An attestation is not a test](evidence-and-testing.md#an-attestation-is-not-a-test) |
| How do I change the questions people are asked, without changing what they already answered? | [Questionnaires](running-the-program.md#questionnaires) |
| Who is reminded of what, and when does it go to their steward? | [Reminders](running-the-program.md#reminders) |
| How do I find a record when I only remember a word of it? | [Find anything](the-register.md#find-anything) |
| How do I keep a filtered list and share it? | [Saved views](the-register.md#saved-views) |
| Which records are incomplete, or written down twice? | [What a record is missing](the-register.md#what-a-record-is-missing) |
| Someone has left. What happens to what they owned? | [When someone leaves](running-the-program.md#when-someone-leaves) |
| How do I let people sign in with Entra ID or another identity provider? | [Single sign-on](configuration.md#single-sign-on) |
| Nobody can sign in. How do I get back in? | [`riskwren users`](cli.md#riskwren-users) |

## What this release does not do yet

Version 0.5.0 is the register, compliance, the means of keeping both current, the organization's own word, and its third parties: services and tiers, due diligence through a link that needs no account, assurance reports read for what they cover, the stop where shared information has no covering agreement, and the relationship over time. It does not yet produce leadership reports, run audits, or handle incidents; those follow in later releases. A contact at a third party answers through a link and cannot yet be sent a link to report progress on an action; the action's owner here records it. Two records that are the same thing cannot yet be merged, only found. The [roadmap](../spec/roadmap.md) says what comes next and in what order, and the [changelog](../CHANGELOG.md) lists what is in each release.

## More

- The design behind the product is in [`spec/`](../spec/README.md).
- To work on RiskWren itself, see [CONTRIBUTING.md](../CONTRIBUTING.md).
- To report a security problem, see [SECURITY.md](../SECURITY.md).
