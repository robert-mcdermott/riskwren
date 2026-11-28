# RiskWren documentation

These guides describe RiskWren 0.10.1. They are also published, with search, at <https://robert-mcdermott.github.io/riskwren/>.

## Start here

RiskWren is a system of record for governance, risk, and compliance: one connected register of what an organization depends on, what could go wrong, what it does about it, what it is held to, and the proof, with every judgment made by a named person and every change kept. It is passive: it never scans, collects from, or sits in the path of another system.

If you are new, read in this order:

1. [How RiskWren works](concepts.md): the pieces, how they fit, the rules it keeps, and the words it uses. Twenty minutes, and everything else reads faster for it.
2. [Your part in it](roles.md): what each role does, the first week for each, and which role to give whom.
3. [Getting started](getting-started.md), to install it or to look around the demo organization.
4. [Adopting RiskWren](adopting.md), to decide, bring in what you have, pilot it, and roll it out.

Then go to the guide for your part.

## The guides

| | Guide | For | Covers |
|---|---|---|---|
| **Start** | [How RiskWren works](concepts.md) | Everyone, first | What it is and is not; the pieces of the record and how they fit; people, units, roles, and owners; the rules it keeps; the program; what people see each day; the words it uses |
| | [Your part in it](roles.md) | Everyone | Choosing roles for an organization and what to know first; for the security leader, managers, assessors, stewards, owners, leaders, staff, internal audit, and administrators: what they see, their first week, and what to read |
| | [Getting started](getting-started.md) | Whoever installs RiskWren | Installing, `init` and its starter programs, `doctor`, `serve`, first sign-in and the account page, units and people and importing them, the demo organization |
| | [Adopting RiskWren](adopting.md) | Whoever decides whether to use it, and puts it into use | Looking at the demo, the decisions to make (roles, sign-in, sessions, visibility, data classes, email, backups, the database), bringing in what you have, a pilot, rolling it out, going live, and keeping it current |
| **Use** | [The program handbook](handbook.md) | The risk and compliance team, most often the security office | The first decisions, the first month and quarter, the yearly rhythm, who does what, and what to watch |
| | [The register](the-register.md) | Everyone who owns, assesses, or reads a risk | Home; the inventory, links, and import; risks, their ratings and standing, reviews, escalation, objectives, the bow-tie, estimates, and scenarios; controls and what they suggest; treatment and acceptance; drafts and the assistant; risk analyses; search, saved views, and tidying; indicators; the heat map; business impact, recovery, and continuity; a worked example from a system to a treated risk |
| | [Compliance](compliance.md) | Security and compliance leads, and the stewards of what must comply | Frameworks, packs, versions, and frameworks of your own; mapping controls to requirements; scopes, inherited and shared controls, and the statement of applicability; agreements; readiness and what moves it; good standing; privacy impact; the security plan and OSCAL; the compliance dashboard; connections; a scope from nothing to a statement of applicability |
| | [Evidence and testing](evidence-and-testing.md) | Control owners and assessors | Evidence, its dates and files, and who sees it; assessments and tests; independence and a second pair of eyes; what a confirmed result changes; testing again; what other systems report; attestations; a yearly assessment, start to finish |
| | [Issues and exceptions](issues-and-exceptions.md) | Whoever fixes, checks, or decides | The issue register; issues from a failed test, another system's report, or internal audit; severity and dates; actions; closure confirmed by someone else; who sees an issue; a failed test through to closure; exceptions and their life; the plan of action; drafts of issues; notices |
| | [Policies](policies.md) | Whoever writes, approves, or keeps the organization's policies | Policies, standards, procedures, and guidelines; versions, approval, publishing, and comparing; review; what a document governs; exceptions to a document; who it applies to; the policy library; acknowledgment |
| | [Third parties](third-parties.md) | Whoever looks after suppliers and partners, most often the security office | Third parties and their services, recovery, and incidents about them; tiering; contacts; due diligence through a link that needs no account; reviewing answers; reports and certificates; coverage by agreements, and clearing a stop; findings, review again, good standing for another process, offboarding, subcontractors; seeing them all together; a supplier from first contact to covered |
| | [Internal audit](internal-audit.md) | Internal audit, the third line | The universe ranked from the register, the plan and its approval, engagements and workpapers, requests to the audited, independence, findings and follow-up, the committee report, outside auditors, who sees what |
| | [Incidents](incidents.md) | Everyone who reports something, and those who triage and handle it | Reporting an incident, a near miss, or a concern, with or without a name; who sees a report; triage and who handles it; restricted cases; what it taught; breach assessment, deadlines, and notifications; an incident from report to closure |
| | [Running the program](running-the-program.md) | The risk, compliance, and security assurance team, and administrators | Roles and scope, who sees what, shaping the program and changing it with a pack, questionnaires, campaigns and privacy impact assessments, committee sessions, when someone leaves, reminders, the dashboards, measures, the portfolio, leadership reports, the history, as of a date, dossiers, administration, appearance, backups |
| | [Other systems and assistants](other-systems.md) | Whoever connects other systems, and those who see what they send | Tokens, webhooks for programs, service desks, and chat, results reported by scanners, good standing, drafts, a tool server for an assistant on someone's computer, and the optional assistant in RiskWren |
| **Run** | [Configuration](configuration.md) | Whoever runs the server | `riskwren.toml` and every key, environment overrides, secrets, the data home, single sign-on, scheduled work, email, PostgreSQL, backup and restore, sizing, upgrading, reverse proxies, the demo guard, branding fixed in the file, the assistant |
| | [Deployment](deployment.md) | Whoever puts it into production | A container with PostgreSQL, a service on the host, the proxy, backups and testing a restore, `doctor --production`, keeping an eye on it, and upgrades |
| | [When something goes wrong](help.md) | Anyone who is stuck, and whoever looks after the installation | Checking the installation, the logs, signing in, records you cannot see, refusals and why, figures that look wrong, email and webhooks, restoring a backup, getting help |
| **Connect** | [The API](api.md) | Anyone connecting another system | Signing in and tokens, webhooks, reporting onto a control, good standing and its recipes, the tool server and drafts, the contract, changes and the CSRF token, answers, errors, lists, every route, and what the API will not do |

## Reference

These are written from the code, so they always match the version they ship with.

| Reference | What it is |
|---|---|
| [Command reference](cli.md) | Every `riskwren` command and option |
| [openapi.json](openapi.json) | The OpenAPI document for the API. A running server also serves it at `/api/openapi.json` |

## Find the answer to a question

### Getting going

| Question | Where |
|---|---|
| What is RiskWren, and what will it not do? | [What it is, and what it is not](concepts.md#what-it-is-and-what-it-is-not) |
| Can it hold our patient records or controlled information? | [What it is, and what it is not](concepts.md#what-it-is-and-what-it-is-not): it describes them, it does not hold them |
| How do the pieces fit together? | [The pieces, and how they fit](concepts.md#the-pieces-and-how-they-fit) |
| What does a word mean here? | [Words](concepts.md#words) |
| How do I try it without setting anything up? | [Explore the demo organization](getting-started.md#explore-the-demo-organization) |
| Which starter program should we begin from? | [Set up the installation](getting-started.md#set-up-the-installation) |
| Which role should each person have? | [Choosing roles for your organization](roles.md#choosing-roles-for-your-organization) |
| What does my role do in the first week? | [Your part in it](roles.md) |
| How do I bring in my units and people? | [Import units and people](getting-started.md#import-units-and-people) |
| How do people get a password? | [People and roles](getting-started.md#people-and-roles), [Single sign-on](configuration.md#single-sign-on) |
| What do we need to decide before we start? | [Decide](adopting.md#decide) |
| How do we bring in our existing risk register and spreadsheets, and what does not import? | [Bring in what you have](adopting.md#bring-in-what-you-have) |
| What will staff be asked to do, and how often? | [Roll it out](adopting.md#roll-it-out) |
| How do I change my password, or choose how notices reach me by email? | [Your account](getting-started.md#your-account) |
| How do I let people sign in with Entra ID or another identity provider? | [Single sign-on](configuration.md#single-sign-on) |

### Risks

| Question | Where |
|---|---|
| How do I raise a risk and rate it? | [Raise a risk](the-register.md#raise-a-risk), [Assess it](the-register.md#assess-it) |
| Is there an example from a system to a treated risk? | [A worked example](the-register.md#a-worked-example-from-a-system-to-a-treated-risk) |
| What is the difference between a rating and a standing? | [Rating and standing](the-register.md#rating-and-standing) |
| Where does the suggested residual rating come from? | [What the controls suggest](the-register.md#what-the-controls-suggest) |
| Why can I not accept this risk? | [Accept a risk](the-register.md#accept-a-risk) |
| Why is a risk flagged as in doubt? | [When the picture changes](the-register.md#when-the-picture-changes) |
| How do I bring in the systems, risks, or controls I already have in a spreadsheet? | [Import and export](the-register.md#import-and-export) |
| Which of the strategic plan's aims are most at risk? | [The objectives it threatens](the-register.md#the-objectives-it-threatens) |
| Which controls stand between the causes of this risk and what follows it? | [The bow-tie](the-register.md#the-bow-tie) |
| What would two weeks of ransomware cost us, and how sure are we? | [Estimates in ranges](the-register.md#estimates-in-ranges), [Scenarios](the-register.md#scenarios) |
| How do I run a security risk analysis over a scope? | [Risk analyses](the-register.md#risk-analyses) |
| How do I get warning of a risk before it happens? | [Indicators](the-register.md#indicators) |
| If research storage is lost, can the backups bring it back in time? | [Business impact and recovery](the-register.md#business-impact-and-recovery) |
| What do we do when research storage is down, and have we tried it? | [Continuity plans and exercises](the-register.md#continuity-plans-and-exercises) |
| How do I find a record when I only remember a word of it? | [Find anything](the-register.md#find-anything) |
| How do I keep a filtered list and share it? | [Saved views](the-register.md#saved-views) |
| Which records are incomplete, or written down twice? | [What a record is missing](the-register.md#what-a-record-is-missing) |
| What is everything connected to this system? | [Connections](compliance.md#connections) |

### Compliance, evidence, and testing

| Question | Where |
|---|---|
| Where are we against a framework? | [The compliance dashboard](compliance.md#the-compliance-dashboard) |
| How do we set up a scope for a framework, from nothing to a statement of applicability? | [From nothing to a statement of applicability](compliance.md#from-nothing-to-a-statement-of-applicability), [Scopes](compliance.md#scopes) |
| What is the difference between in place and verified? | [Readiness](compliance.md#readiness) |
| Why did a requirement stop being verified? | [Evidence stops counting](evidence-and-testing.md#evidence-stops-counting), [Readiness](compliance.md#readiness), [A figure looks wrong](help.md#a-figure-looks-wrong) |
| A team relies on a control somebody else runs. How is that recorded? | [Inherited controls](compliance.md#inherited-controls) |
| How do I load ISO/IEC 27001, or a framework of our own? | [Frameworks](compliance.md#frameworks), [A framework of your own](compliance.md#a-framework-of-your-own) |
| How do I enter a data use agreement or a sponsor's requirements? | [A framework of your own](compliance.md#a-framework-of-your-own) |
| A framework has a new version. What changed, and how does a scope move to it? | [A new version of a framework](compliance.md#a-new-version-of-a-framework) |
| Which scopes does an agreement bind, and when must it be renewed? | [Agreements](compliance.md#agreements) |
| Can we give our system security plan to an agency that reads OSCAL? | [The security plan and OSCAL](compliance.md#the-security-plan-and-oscal) |
| Which systems need a privacy impact assessment? | [Privacy impact](compliance.md#privacy-impact), [Privacy impact assessments](running-the-program.md#privacy-impact-assessments) |
| How do I run an assessment and record a test? | [A yearly assessment, start to finish](evidence-and-testing.md#a-yearly-assessment-start-to-finish), [Record a result](evidence-and-testing.md#record-a-result) |
| Why can I not record this test result, or confirm it? | [Independence, and a second pair of eyes](evidence-and-testing.md#independence-and-a-second-pair-of-eyes) |
| How do I add evidence, and how long does it count? | [Evidence](evidence-and-testing.md#evidence) |
| Does an owner saying a control works make it verified? | [An attestation is not a test](evidence-and-testing.md#an-attestation-is-not-a-test) |
| A scanner reported a failure. What do I do with it? | [What other systems report](evidence-and-testing.md#what-other-systems-report), [Results reported by other systems](other-systems.md#results-reported-by-other-systems) |

### Issues, exceptions, and policies

| Question | Where |
|---|---|
| A test failed. What happens now, through to closure? | [From a failed test](issues-and-exceptions.md#from-a-failed-test), [A failed test, through to closure](issues-and-exceptions.md#a-failed-test-through-to-closure) |
| Why can I not close my own issue? | [Close it](issues-and-exceptions.md#close-it) |
| We cannot meet a requirement yet. What do we do? | [Exceptions](issues-and-exceptions.md#exceptions), [An exception, from asking to ending](issues-and-exceptions.md#an-exception-from-asking-to-ending) |
| How do I get a policy approved and published? | [Approval](policies.md#approval) |
| What changed between two versions of a procedure? | [Publishing](policies.md#publishing) |
| Is there a policy for this requirement? | [What it governs](policies.md#what-it-governs) |
| A lab cannot meet a standard yet: how does it ask for an exception? | [Exceptions to a document](policies.md#exceptions-to-a-document) |
| Where do staff read the policies that apply to them? | [The policy library](policies.md#the-policy-library) |
| Who has not yet acknowledged the acceptable use policy? | [Who has acknowledged it](policies.md#who-has-acknowledged-it) |

### Third parties, incidents, and audit

| Question | Where |
|---|---|
| Which suppliers hold our restricted information, and through what? | [Third parties and their services](third-parties.md#third-parties-and-their-services) |
| How do we take a new supplier from first contact to approved and covered? | [A worked example](third-parties.md#a-worked-example-from-first-contact-to-covered) |
| Why is this supplier Tier 1? | [Tiering](third-parties.md#tiering) |
| How do I send a supplier a security questionnaire without giving them an account, and is the link safe? | [Send it](third-parties.md#send-it) |
| What does a supplier's SOC 2 report leave for us to do? | [Review a report](third-parties.md#review-a-report) |
| Who holds our patient records without a business associate agreement? | [Coverage](third-parties.md#coverage) |
| A supplier told us of a breach. How do we review it again now? | [Review again](third-parties.md#review-again) |
| How do we end a supplier relationship properly? | [Ending a relationship](third-parties.md#ending-a-relationship) |
| Can purchasing check a supplier before it buys, and what does the answer prove? | [In good standing, for another process](third-parties.md#in-good-standing-for-another-process), [Is it in good standing?](other-systems.md#is-it-in-good-standing) |
| Something went wrong. How do I report it? | [Reporting something](incidents.md#reporting-something) |
| Can people report a concern without giving their name? | [Reporting without a name](incidents.md#reporting-without-a-name) |
| How do I keep a sensitive case to the few who must know? | [Restricted cases](incidents.md#restricted-cases) |
| Do we have to notify anyone about this breach, and by when? | [Breach assessment](incidents.md#breach-assessment) |
| Is there an example of an incident from report to closure? | [A worked example](incidents.md#a-worked-example-from-report-to-closure) |
| Which risks have actually happened, and what have they cost? | [What it taught](incidents.md#what-it-taught) |
| What should internal audit look at next year, and why? | [The universe](internal-audit.md#the-universe) |
| Why does internal audit need at least two auditors? | [Why one auditor is not enough](internal-audit.md#why-one-auditor-is-not-enough) |
| How does an engagement run, from the plan to the committee report? | [A worked example](internal-audit.md#a-worked-example-from-plan-to-committee-report) |

### Running the program

| Question | Where |
|---|---|
| Who can see a risk? | [Who sees what](running-the-program.md#who-sees-what) |
| Who changed this, and when? | [The history](running-the-program.md#the-history) |
| What is each Admin page for? | [Administration](running-the-program.md#administration) |
| How do I change appetite, the scales, or the review cadence? | [Shape the program](running-the-program.md#shape-the-program) |
| Which risks would change if I changed the matrix? | [See what a change would do](running-the-program.md#see-what-a-change-would-do-before-you-make-it) |
| How do I add a kind of system, or rename a data class? | [Vocabularies](running-the-program.md#vocabularies) |
| How do we record a cost center on every system? | [Fields of your own](running-the-program.md#fields-of-your-own) |
| How does a committee's decision reach the record it was about? | [Committee sessions](running-the-program.md#committee-sessions) |
| How do I ask every control owner to attest, and see who has? | [Campaigns](running-the-program.md#campaigns) |
| How do I change the questions people are asked, without changing what they already answered? | [Questionnaires](running-the-program.md#questionnaires) |
| Who is reminded of what, and when does it go to their steward? | [Reminders](running-the-program.md#reminders) |
| Someone has left. What happens to what they owned? | [When someone leaves](running-the-program.md#when-someone-leaves) |
| What does a dashboard figure count? | [Read the dashboards](running-the-program.md#read-the-dashboards) |
| Are we getting better? Which figures moved this quarter? | [Measures](running-the-program.md#measures) |
| Which units, frameworks, or suppliers need attention, and why do issues happen? | [Portfolio](running-the-program.md#portfolio) |
| What did we tell leadership last quarter, and has the report been changed since? | [Leadership reports](running-the-program.md#leadership-reports) |
| What did the register say on the day of the audit? Who owned this risk in March? | [As of a date](running-the-program.md#as-of-a-date) |
| The auditor wants everything about this scope, in a form they can check | [Dossiers](running-the-program.md#dossiers) |

### Other systems and assistants

| Question | Where |
|---|---|
| How does another system read from RiskWren, or hear when an issue is raised or closed? | [Tokens](other-systems.md#tokens), [Webhooks](other-systems.md#being-told-what-happens-webhooks) |
| Can our service desk open a ticket, or a chat channel hear, when an issue is raised? | [Being told what happens](other-systems.md#being-told-what-happens-webhooks) |
| How does a scanner report a failed check onto a control? | [Results reported by other systems](other-systems.md#results-reported-by-other-systems), [Reporting onto a control](api.md#reporting-onto-a-control) |
| What are drafts, and who makes them into records? | [Drafts](other-systems.md#drafts) |
| How do I let an assistant on my computer read RiskWren? | [An assistant on your own computer](other-systems.md#an-assistant-on-your-own-computer) |
| How do I turn on the assistant, with a model of our own? | [The assistant](configuration.md#the-assistant) |

### Running the server

| Question | Where |
|---|---|
| How do I move to PostgreSQL? | [Use PostgreSQL](configuration.md#use-postgresql) |
| How do I back it up, restore it, or move it between databases? | [Back up and restore](configuration.md#back-up-and-restore) |
| How do I know a backup will actually restore? | [Test a restore](deployment.md#test-a-restore) |
| How do I run it in a container, or as a locked-down service? | [Deployment](deployment.md) |
| How do I upgrade to a new release? | [Upgrade](configuration.md#upgrade) |
| How do I put it behind a proxy? | [Run behind a reverse proxy](configuration.md#run-behind-a-reverse-proxy) |
| How do I send notices and reminders by email? | [Email](configuration.md#email) |
| Our brand has exact colors, logo files, and typefaces. Can RiskWren use them? | [`[branding]`](configuration.md#branding) |
| Is the installation healthy? | [Check the installation](help.md#check-the-installation) |

### When you are stuck

| Question | Where |
|---|---|
| I cannot sign in, or nobody can | [Signing in](help.md#signing-in) |
| Why can I not see this record? | [I cannot see a record](help.md#i-cannot-see-a-record) |
| Why was I refused? | [I am not allowed to do something](help.md#i-am-not-allowed-to-do-something) |
| A figure looks wrong | [A figure looks wrong](help.md#a-figure-looks-wrong) |
| Reminders, email, or webhooks are not arriving | [Email, reminders, and webhooks](help.md#email-reminders-and-webhooks-are-not-arriving) |
| Where do I ask for help, or report a problem? | [Get help, and report a problem](help.md#get-help-and-report-a-problem) |

## Where RiskWren stops

RiskWren covers the register, compliance, evidence and testing, issues and exceptions, policies and agreements, third parties, internal audit, incidents and resilience, insight, and connections to other systems. It does not:

- **Collect evidence on a schedule.** Other systems may report what they find; RiskWren does not go and look.
- **Let a third party's contact report progress on an action** through a link; they answer due diligence through one.
- **Let an outside auditor download evidence files** through their link; it lists the evidence on file.
- **Merge two records** that are the same thing; it finds them, and one is retired by hand.
- **Let people see and end their own other sessions,** or check passwords against a list of breached ones. The [security review](../spec/security-review.md) lists these and its other findings.
- **Have its own assistant draft issues or controls**; an assistant through the tool server may.
- **Hold several organizations** in one installation, **provision accounts** from a directory, **keep training records**, or **translate its interface**.

It will never scan networks, logs, endpoints, code, or clouds; block, change, or sit in the path of another system; or hold the regulated data its records describe. The [roadmap](../spec/roadmap.md) sets out what is planned, and the [changelog](../CHANGELOG.md) lists what is in each release.

## More

- The design behind the product is in [`spec/`](../spec/README.md).
- To work on RiskWren itself, see [CONTRIBUTING.md](../CONTRIBUTING.md).
- To report a security problem, see [SECURITY.md](../SECURITY.md).
