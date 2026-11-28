# The program handbook

For a risk and compliance team, most often the security office, running its program in RiskWren: what to settle first, what to do in the first months, and the rhythm of a year. The other guides say how each part works; this one says when to use it, and why. It assumes RiskWren is installed with the organization's units and people loaded ([Getting started](getting-started.md)), and that you know the ideas in [How RiskWren works](concepts.md).

## Decide first

A few decisions shape everything after them: who gets which role, how people sign in, the program to start from, the units, appetite, who accepts what, who sees the register, and what the data classes mean. They are listed, with a good start for each, in [Adopting RiskWren](adopting.md#decide). Make them before you enter much, and write them down.

Each is a setting that can be changed later, and changing some of them moves records. Publishing a change to appetite, the matrix, or the cadences reads every open risk again, its rating, its standing, and its next review, so that the register always speaks one language. The judgments already made keep the version of the program they were made under. **Admin → Program** shows every risk a change would move before it is published ([Shape the program](running-the-program.md#shape-the-program)).

Keep the first version of the program small. A scale with five levels that everyone understands beats a precise one that nobody applies the same way.

## The first month: the record

1. **Units and people.** Load them as [Getting started](getting-started.md#set-up-the-organization) describes, and name a steward for each unit in the first year's scope. To name people as owners before they have signed in, import them or add them as invited: single sign-on makes a person's account only at their first sign-in, and never makes units.
2. **The inventory.** Start with what matters most: the critical processes and the systems they rely on, then the third parties and information assets behind them. Bring in what you have from spreadsheets ([Bring in what you have](adopting.md#bring-in-what-you-have)). Link them as you go: *relies on*, *holds*, *shared with*. A record without links is a list; with them it is a picture ([Connections](compliance.md#connections)).
3. **Controls.** Take the common controls from the library and write what each does here; add your own. Name an owner for each. Map them to your frameworks: the library's controls arrive mapped ([Map controls to requirements](compliance.md#map-controls-to-requirements)).
4. **Scopes.** One scope for each boundary you answer for: the clinical systems, a data enclave, the whole organization. Say which controls each uses and how ([Scopes](compliance.md#scopes)).
5. **Risks.** Start from the library, the risk analyses, or your existing register rather than a blank page ([Risk analyses](the-register.md#risk-analyses)). A risk brought in from a spreadsheet arrives not assessed. Rate each with reasons, inherent first; let the controls suggest the residual ([What the controls suggest](the-register.md#what-the-controls-suggest)).

At the end of the month, readiness on the compliance dashboard is honest and mostly *planned* or *in place*. That is the right place to start.

## The first quarter: the evidence

1. **Test what matters.** An assessment of each scope's key controls, results recorded by someone who does not own the control and confirmed by a second person ([Assessments and tests](evidence-and-testing.md)). Readiness moves to *verified* only here.
2. **Collect evidence once.** Attach each piece to everything it supports, with the date it holds to. It stops counting on its own ([Evidence stops counting](evidence-and-testing.md#evidence-stops-counting)).
3. **Put failures right.** A failed test opens an issue; an issue has a date from its severity, actions with owners, and is closed by someone who did not fix it ([Issues and exceptions](issues-and-exceptions.md)). What cannot be fixed yet is an exception, decided and dated.
4. **Policies.** Load the documents you have, link each to the controls it directs and the requirements it answers, and ask the people each applies to to acknowledge it ([Policies](policies.md)).
5. **Suppliers.** Tier the third parties that hold restricted information, send each its questionnaire, and read their reports for what they cover ([Third parties](third-parties.md)).
6. **Incidents.** Tell everyone where to report what goes wrong, and decide whether reports may be made without a name ([Incidents](incidents.md)).

## The yearly rhythm

Once the record is in place, the program is the same work on a calendar. Scheduled work reminds owners before things are due, then their stewards and leaders when actions, issues, and campaign requests are late ([Reminders](running-the-program.md#reminders)), so the team chases less and reads more. The intervals below are the program's as shipped.

| When | What | Where |
|---|---|---|
| **Every week** | Triage new incidents and concerns; read what is waiting on Home. Stewards and assessors look at **Drafts**, and assessors at what other systems have reported, since neither appears on Home or under the bell | Incidents; Home; **Drafts**; **Compliance → From other systems** |
| **Every month** | Issues past their date, exceptions ending, indicators past their limit, evidence about to stop counting | The compliance and risk dashboards; Indicators |
| **Every quarter** | Critical risks reviewed; the risk committee meets on an agenda drawn from the register; a leadership report is issued and kept as it was given; control owners attest | The review cadence; Committee sessions; Leadership reports; Campaigns |
| **Twice a year** | Key controls tested again; high risks reviewed | Assessments; the review cadence |
| **Every year** | Moderate risks reviewed; every control rated or tested again, because a rating and a test result count for twelve months; appetite agreed with leadership; the program reviewed and published; each policy reviewed; tier 1 suppliers reviewed; internal audit's plan approved; business impact analysed again for critical processes, and continuity plans exercised | The review cadence; Assessments; **Admin → Program**; Policies; Third parties; Audit; **Reports → Resilience** and **Continuity plans** |
| **Every two years** | Low risks reviewed; tier 2 suppliers reviewed | The review cadence; Third parties |
| **Every three years** | Tier 3 suppliers reviewed; privacy impact assessments repeated for what handles restricted information | Third parties; **Compliance → Privacy impact** |
| **When something changes** | A new system or supplier tiered and linked; a framework's new version loaded and a scope moved to it when ready; a risk looked at again when its picture changes | The inventory; Frameworks; the register |

The cadences behind this (how often each rating is reviewed, how long a rating and a test result hold, how often a key control is tested, how long an exception may last, when a plan is exercised) are the program's, under **Admin → Program → Cadences** ([Cadences](running-the-program.md#cadences)). A supplier's tier sets how often it is reviewed, and the privacy rule how often an impact assessment is repeated; both are in the program pack.

## Who does what

What each kind of person sees, does in the first week, and reads is in [Your part in it](roles.md). In the program, in short:

| Who | Usually holds | In the program |
|---|---|---|
| **The security leader** | **Leader** of the security unit, and **assessor** for the whole organization | Decides the security unit's exceptions and accepts its risks up to their limit; confirms closures of serious issues; reads the compliance dashboard and the portfolio; reads each leadership report once it is issued, and goes through the next one with the risk team before they issue it, since only a manager can open it beforehand |
| **The risk and compliance team** | **Manager** | Shapes the program, keeps the register in order, links shared controls to other units' risks, runs campaigns and committee sessions, prepares and issues leadership reports, and decides exceptions. Does not accept risk |
| **Assessors** | **Assessor** | Test controls, review and confirm results, confirm closures, triage incidents |
| **Stewards** | **Steward** of a unit | Keep their unit's records current: inventory, risks, controls, owners |
| **Owners** of systems, risks, controls, and actions | No role | Answer for one thing each, and are reminded when it is due |
| **Leaders** | **Leader** of a unit, with a limit | Accept risks within their limit, decide exceptions, and read their units' standing |
| **Auditors** | **Auditor** | Read everything, and run internal audit's universe, plans, and engagements on the same record |
| **Administrators** | **Admin** | Accounts, units, sign-in, appearance, tokens, and the installation. Read everything; make no judgments |
| **Everyone** | No role | Reads the policies that apply to them, reports what goes wrong, and answers what they are asked |

If the security leader also runs the program day to day, they hold **manager** as well; a manager cannot accept risk, so the leader role stays. In the demo organization the chief information security officer is leader of Information Security and assessor everywhere, and the risk managers are managers ([Explore the demo organization](getting-started.md#explore-the-demo-organization)).

## What to watch

[Measures](running-the-program.md#measures) say what they count and open the list behind each figure. Early on, watch coverage: how much of the inventory has owners, risks rated, and controls mapped. Later, watch movement: risks above appetite, issues past their date, controls failing a test, and readiness by scope against each framework. A figure that never moves is a figure nobody is acting on.

## Read next

- [Running the program](running-the-program.md): shaping the program, campaigns, committee sessions, reminders, the dashboards, and the history.
- [The register](the-register.md) and [Compliance](compliance.md): the records the program keeps.
- [Evidence and testing](evidence-and-testing.md) and [Issues and exceptions](issues-and-exceptions.md): the first quarter's work.
- [Internal audit](internal-audit.md), [Third parties](third-parties.md), and [Incidents](incidents.md): the rest of the year.
- [When something goes wrong](help.md): what to check first.
