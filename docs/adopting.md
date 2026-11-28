# Adopting RiskWren

For an organization deciding whether to use RiskWren, and then putting it into use: what to look at, how to pilot it, what to decide, and how to go live. [The program handbook](handbook.md) takes over once it is running.

## Look at it

Build the demo organization on a laptop and sign in as each of its sample people ([Explore the demo organization](getting-started.md#explore-the-demo-organization)). It is a fictional research institute with two years of history, and every screen has something on it. Look at it as the people who would use it:

- **The security leader** and **the risk manager**: the dashboards, the register, the program, and the reports to leadership.
- **A steward** and **a staff member**: what a person who answers for a few things sees, and how little they are asked.
- **The auditor**: whether the record can be shown to be what it says it was, on any date.

Then read the [changelog](../CHANGELOG.md), which lists what each release does, and the end of the guides' index in the repository (`docs/README.md`), which says what this release does not do yet: together they say where it stops.

## Pilot it

A pilot of six to twelve weeks answers the questions that matter: will the people who must keep it current do so, and does what it shows hold up?

1. **Install it as you would for production** ([Deployment](deployment.md)), with PostgreSQL, behind your proxy, with backups, but with a starter program and nothing imported yet.
2. **Choose a slice** of the organization: one division, or the systems in one compliance scope. Large enough to have real risks and real owners; small enough to finish.
3. **Do the first month and the first quarter of the [handbook](handbook.md#the-first-month-the-record)** for that slice, with its real stewards and owners.
4. **Judge it** by what the pilot's people did, not by what they said: did owners answer their reminders, did a test result move readiness, did the leadership report survive a question?

Keep the pilot's installation: it becomes production, and nothing needs moving. If it was on SQLite, move it to PostgreSQL with a backup and a restore ([Move between SQLite and PostgreSQL](configuration.md#move-between-sqlite-and-postgresql)).

## Decide

Before going wider, settle the decisions in [Decide first](handbook.md#decide-first), and these about the installation:

| Decision | Where |
|---|---|
| Who runs the installation, and who is the second administrator | Roles; [Deployment](deployment.md#check-before-going-live) |
| How people sign in: local accounts, single sign-on, or both | [Single sign-on](configuration.md#single-sign-on) |
| Whether to send email, and from what address | [Email](configuration.md#email) |
| How backups are taken, kept, and tested | [Back up and restore](configuration.md#back-up-and-restore) |
| The look: your names, logos, colors, and words, in the app or fixed in the file | [Appearance](running-the-program.md#appearance), [`[branding]`](configuration.md#branding) |
| Which other systems read from it, and with what token; which are told of events | [Tokens](api.md#another-system-tokens), [webhooks](api.md#being-told-webhooks) |
| Whether reports may be made without a name | [Reporting without a name](incidents.md#reporting-without-a-name) |

## Go live

1. Run `riskwren doctor --production` until it has nothing to fix ([Check before going live](deployment.md#check-before-going-live)).
2. Bring in what you have: units and people, then the inventory, risks, and controls from spreadsheets, each with a dry run that reports every problem by row before anything is loaded ([Import and export](the-register.md#import-and-export)).
3. Widen one division or scope at a time, each with its stewards shown what is theirs. Campaigns do the asking ([Campaigns](running-the-program.md#campaigns)).
4. Turn on what reaches people last: email, then reminders' escalation to stewards and leaders, once records have owners who know they are owners.

## Keep it current

- **Upgrades** come as releases, each with a changelog that says what looks different afterwards. Back up, then upgrade ([Upgrade](deployment.md#upgrade)). Within 0.x, a release may change the API; the changes are listed under **Breaking**, and the [contract](api.md#the-contract) catches them before they ship.
- **Security problems** are reported as [SECURITY.md](../SECURITY.md) says. The application was reviewed against the OWASP Application Security Verification Standard at level 2; the review and what was done about each finding are in the repository's `spec/security-review.md`.
- **Your program** is yours: export it as one file (`riskwren program export`) to keep it under version control or carry it to another installation.
