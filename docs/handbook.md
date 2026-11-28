# The program handbook

For a risk and compliance team, most often the security office, running its program in RiskWren: what to decide first, what to do in the first months, and the rhythm of a year. The other guides say how each part works; this one says when to use it, and why.

## Decide first

A few decisions shape everything after them. Make them before you enter much, and write them down: each one is a setting you can change later, but records made under one setting are not remade under the next.

| Decision | Where it is set | A good start |
|---|---|---|
| **Who runs the program** | Roles: managers run it, administrators keep the installation | Two managers from the security or risk office, and an administrator who is not one of them |
| **What the first year covers** | Your plan, not a setting | The systems and processes that hold restricted information, and the frameworks you are already held to |
| **The program to start from** | `riskwren init --program` | The one nearest your organization; adjust it under **Admin → Program** |
| **The units** | **Admin → Units** | The units that answer for things, as the organization chart has them, two or three levels deep. Not every team |
| **Who sees the register** | **Admin → Program → Who sees what** | Everyone sees the inventory; the register of risks as the program decides |
| **Appetite** | **Admin → Program → Categories and appetite** | Agreed with leadership, one rating for each family of risk |
| **Who accepts what** | The program pack's authority table | Unit leaders up to moderate, division leaders up to high, the head of the organization above that |
| **Your own words** | **Admin → Appearance → Your own words** | Only where the standard word would confuse people |

Keep the first version of the program small. A scale with five levels that everyone understands beats a precise one that nobody applies the same way. Preview every change to the program before publishing it: [Admin → Program](running-the-program.md#shape-the-program) shows every risk the change would move.

## The first month: the record

1. **Units and people.** Import them from a spreadsheet ([Import units and people](getting-started.md#import-units-and-people)), or connect single sign-on and let roles come from the identity provider ([Single sign-on](configuration.md#single-sign-on)). Name a steward for each unit in the first year's scope.
2. **The inventory.** Start with what matters most: the critical processes and the systems they rely on, then the third parties and information assets behind them. Link them as you go: *relies on*, *holds*, *shared with*. A record without links is a list; with them it is a picture ([Connections](compliance.md#connections)).
3. **Controls.** Take the common controls from the library and write what each does here; add your own. Name an owner for each. Map them to your frameworks: the library's controls arrive mapped ([Map controls to requirements](compliance.md#map-controls-to-requirements)).
4. **Scopes.** One scope for each boundary you answer for: the clinical systems, a data enclave, the whole organization. Say which controls each uses and how ([Scopes](compliance.md#scopes)).
5. **Risks.** Start from the library and the risk analyses rather than a blank page ([Risk analyses](the-register.md#risk-analyses)). Rate each with reasons, inherent first; let the controls suggest the residual ([What the controls suggest](the-register.md#what-the-controls-suggest)).

At the end of the month, readiness on the compliance dashboard is honest and mostly *planned* or *in place*. That is the right place to start.

## The first quarter: the evidence

1. **Test what matters.** An assessment of each scope's key controls, results recorded by someone who does not own the control and confirmed by a second person ([Assessments and tests](evidence-and-testing.md)). Readiness moves to *verified* only here.
2. **Collect evidence once.** Attach each piece to everything it supports, with the date it holds to. It stops counting on its own ([Evidence stops counting](evidence-and-testing.md#evidence-stops-counting)).
3. **Put failures right.** A failed test opens an issue; an issue has a date from its severity, actions with owners, and is closed by someone who did not fix it ([Issues and exceptions](issues-and-exceptions.md)). What cannot be fixed yet is an exception, decided and dated.
4. **Policies.** Load the documents you have, link each to the controls it directs and the requirements it answers, and ask the people each applies to to acknowledge it ([Policies](policies.md)).
5. **Suppliers.** Tier the third parties that hold restricted information, send each its questionnaire, and read their reports for what they cover ([Third parties](third-parties.md)).
6. **Incidents.** Open reporting to everyone, and decide whether to open reporting without a name ([Incidents](incidents.md)).

## The yearly rhythm

Once the record is in place, the program is the same work on a calendar. Scheduled work reminds owners before things are due, then their stewards and leaders when they are late ([Reminders](running-the-program.md#reminders)), so the team chases less and reads more.

| When | What | Where |
|---|---|---|
| **Every week** | Triage new incidents and concerns; read what is waiting on home | Incidents; Home |
| **Every month** | Issues past their date, exceptions ending, indicators past their limit, evidence about to stop counting | The compliance and risk dashboards; Indicators |
| **Every quarter** | The risk committee meets on an agenda drawn from the register; a leadership report is issued and kept as it was given; control owners attest | Committee sessions; Leadership reports; Campaigns |
| **Twice a year** | Key controls tested again; risks rated high and critical reviewed | Assessments; the review cadence |
| **Every year** | Appetite agreed with leadership; the program reviewed and published; each policy reviewed; risk owners asked to look again; suppliers reviewed on their tier's cadence; internal audit's plan approved; business impact analysed again for critical processes and continuity plans exercised; privacy impact assessments repeated where the program says | Admin → Program; Policies; Campaigns; Third parties; Audit; Reports → Resilience and Continuity plans |
| **When something changes** | A new system or supplier tiered and linked; a framework's new version loaded and a scope moved to it when ready; a risk looked at again when its picture changes | The inventory; Frameworks; the register |

The cadences behind this (how often each rating is reviewed, how long an exception may last, how often a key control is tested, when a plan is exercised) are the program's, under **Admin → Program → Cadences**.

## Who does what

| Role | In the program |
|---|---|
| **Security leader, risk manager** (managers) | Shape the program, run campaigns and committee sessions, issue leadership reports, decide exceptions within their authority |
| **Stewards** | Keep their unit's records current: inventory, risks, controls, owners |
| **Owners** of risks, controls, and actions | Answer for one thing each, and are reminded when it is due |
| **Assessors** | Test controls, review results, confirm closures, triage incidents |
| **Leaders** | Accept risks within their authority, and read their units' standing |
| **Auditors** | Read everything and change nothing; internal audit plans and works on the same record |
| **Administrators** | Accounts, units, the look, single sign-on, tokens, and the installation |
| **Everyone** | Reads the policies that apply to them, reports what goes wrong, and answers what they are asked |

## What to watch

[Measures](running-the-program.md#measures) say what they count and open the list behind each figure. Early on, watch coverage: how much of the inventory has owners, risks rated, and controls mapped. Later, watch movement: risks above appetite, issues past their date, controls failing a test, and readiness by scope against each framework. A figure that never moves is a figure nobody is acting on.
