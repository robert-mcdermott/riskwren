# Your part in it

This guide says what each kind of person does in RiskWren: what they see when they sign in, what to do in the first week, the rhythm after that, and which guides to read. It ends with advice on giving roles in an organization, which is the first decision whoever sets RiskWren up has to make. The ideas behind it are in [How RiskWren works](concepts.md).

To see each of these for yourself before you set anything up, build the demo organization and sign in as its sample people: [Explore the demo organization](getting-started.md#explore-the-demo-organization).

## Choosing roles for your organization

Give each person the least they need. Most people need no role at all: they are members who own a few records, finish their actions, report what goes wrong, and acknowledge policies.

| Who | Usually given | Why |
|---|---|---|
| The chief information security officer | **Leader** of the security unit, and **assessor** for the whole organization | They decide the security unit's exceptions and accept its risks, see every scope, and confirm closures. If they also run the program day to day, add **manager**; a manager cannot accept risk, so the leader role stays |
| The risk and compliance team, or the security office's governance staff | **Manager** for the whole organization | They shape the program, keep the register in order, prepare leadership reports, and help everyone else |
| Security analysts and engineers who test controls | **Assessor**, for the whole organization or a unit | They plan assessments, record and confirm test results, and confirm that issues are put right |
| Central IT, and whoever runs controls for everyone | **Steward** of their unit, and **owner** of the controls they run | They keep their systems and controls current; other units' scopes inherit their controls |
| Lab managers, practice managers, department administrators | **Steward** of their unit | They keep the unit's inventory, risks, and controls complete, and import what they already have |
| Heads of departments, divisions, and clinics | **Leader** of their unit, with a limit | They see their part of the register and accept risks in it up to their limit |
| The chief executive, and any executive who accepts the gravest risks | **Leader** of the whole organization, or of the units they answer for, with a limit of critical | A critical risk needs a leader whose limit is critical; leaders of the whole organization also read what leadership is given |
| Internal audit | **Auditor** | They read the whole record and run their own universe, plans, and engagements |
| The privacy officer | **Assessor**, or **manager** if they run privacy reviews for the whole organization | They review privacy impact assessments, which needs an assessor or a manager |
| Outside auditors | No account: an **outside access** link to one engagement or one scope, read-only, until a date | They see what they are given and nothing else, and every look is recorded. See [Outside auditors](internal-audit.md#outside-auditors) |
| Whoever looks after the installation | **Admin**, for two people at most | They manage accounts, units, sign-in, appearance, and the program's settings |
| Everyone else | Nothing: they are members | They see what they own and are named on, and their unit's register if the program allows it |

Roles are given under **Admin → People**, imported with people from a spreadsheet, or, with single sign-on, read from the identity provider's roles or groups on each sign-in. See [People and roles](getting-started.md#people-and-roles) and [Roles from the provider](configuration.md#roles-from-the-provider).

### Before you give roles, know this

- **An administrator reads the whole record,** restricted records included (all but incident cases restricted to the people named on them), and can change the program's rules. Give it to as few people as can keep the installation running, and not to someone who should not read restricted records.
- **A manager cannot accept risk.** Acceptance belongs to leaders, each up to the limit on their role. Someone who runs the program and also accepts risk for a unit holds both roles.
- **Independence needs two people.** The owner of a control cannot test it, and a result counts only when a second assessor or manager, who neither recorded it nor owns the control, confirms it. So every assessment needs at least two people who can assess the unit: a team with one assessor needs a manager, or an assessor from elsewhere, to confirm.
- **Internal audit needs two auditors.** A workpaper's preparer cannot sign it off, so each engagement needs a second auditor. A plan's drafter cannot approve it, so another auditor, or a leader of the whole organization, approves it.
- **Under the default visibility a steward sees only their unit's risks and controls,** so they cannot link a risk to a control another unit runs. A manager links shared controls, such as central backup, to other units' risks. See [Who sees what](running-the-program.md#who-sees-what).
- **A leader's limit is on the role,** not in the program: moderate, high, or critical. As shipped, any leader of the unit, or of a unit above it, may accept a moderate risk; a high or critical one needs a leader whose limit reaches it. The program says how long each acceptance may last ([Who may accept what](running-the-program.md#who-may-accept-what)).
- **Owners are not roles.** Name the person who answers for each system, risk, and control as its owner. They need no role to edit what they own.

## The security leader

**On Home:** the figures for everything they may see, and what is waiting on them: exceptions to decide, closures to confirm, risks in the units they lead that need a decision, acceptances of theirs about to expire. The compliance dashboard shows where each scope stands against its frameworks.

**In the first week:**

1. Read [How RiskWren works](concepts.md) and [The program handbook](handbook.md), and make the decisions in [Decide](adopting.md#decide) with the risk and compliance team.
2. Agree who gets which role, from the table above, and who leads each unit.
3. Name the scopes the organization is held to (the clinical systems, a research data enclave) and the framework for each, and ask the team to set them up: [Scopes](compliance.md#scopes).
4. Look at the gaps in coverage of third parties: [Coverage](third-parties.md#coverage).

**After that:** decide exceptions as they come, confirm closures of serious issues, read the compliance dashboard and the portfolio monthly, and read each leadership report once it is issued; the risk team can show them the draft before.

**Read next:** [Compliance](compliance.md), [Issues and exceptions](issues-and-exceptions.md), [Third parties](third-parties.md), [Incidents](incidents.md).

## The risk and compliance team (managers)

**On Home:** the whole register's figures, each opening its list (risks needing a decision among them); records with nobody answering for them; and whatever is theirs to finish.

**In the first week:**

1. Shape the program under **Admin → Program**: the families of risk and their appetite, the scales, the cadences, who sees the register. Preview each change before you publish it: [Shape the program](running-the-program.md#shape-the-program).
2. Load the inventory, beginning with the systems and information that matter most: [Import and export](the-register.md#import-and-export).
3. Raise the first risks, from the library or the organization's existing register, and have their owners assess them.
4. Adopt controls from the library and map them to the frameworks the organization is held to: [Map controls to requirements](compliance.md#map-controls-to-requirements).

**After that:** keep the register in order (**Reports → Tidy** lists what is incomplete or written down twice), prepare committee sessions, run campaigns, issue the leadership report each quarter, and watch the measures.

**Read next:** [The register](the-register.md), [Running the program](running-the-program.md), [The program handbook](handbook.md).

## Assessors

**On Home:** tests they have been asked to do, results waiting for their review, and closures to confirm. An assessor with no other role sees no figures. What scanners and other systems report waits under **Compliance → From other systems**, and drafts of issues under **Drafts**; neither is on Home.

**In the first week:**

1. Read [Evidence and testing](evidence-and-testing.md), especially [Independence, and a second pair of eyes](evidence-and-testing.md#independence-and-a-second-pair-of-eyes).
2. Start an assessment of one scope against its framework, and plan its tests: [Assessments](evidence-and-testing.md#assessments).
3. Rate the key controls by judgment where no test has been done yet, so that the risks they reduce can be weighed.

**After that:** record results with the evidence they rest on, confirm colleagues' results, confirm or return proposed closures of issues, and look at **From other systems** each week, because reports from scanners wait there for a person and do not appear on Home.

**Read next:** [Evidence and testing](evidence-and-testing.md), [Issues and exceptions](issues-and-exceptions.md), [Compliance](compliance.md#readiness).

## Stewards

**On Home:** the unit's figures, each opening its list: risks needing a decision or above appetite, reviews and actions overdue, controls failing a test, issues overdue. Below them, what is theirs: risks they own to assess or review, records in the unit with nobody answering for them. Late work in the unit comes to them as a notice under the bell (and by email, if it is set up) after a week; the figures and the lists' overdue filters find it all. Risks, issues, and controls that an assistant or another system has drafted for the unit wait under **Drafts**, beside Home in the menu.

**In the first week:**

1. Check the unit's inventory: every process, system, and supplier the unit depends on, each with an owner. Import what you already have in a spreadsheet: [Import and export](the-register.md#import-and-export).
2. Raise the unit's risks, or bring in its existing register, and name an owner for each: [Raise a risk](the-register.md#raise-a-risk).
3. Link each risk to the controls that reduce it: [Link a control to a risk](the-register.md#link-a-control-to-a-risk).

**After that:** keep the unit's records current, chase late actions (they come to you after a week), and look under **Drafts** for what an assistant or another system has proposed for the unit: open each in the ordinary form, or set it aside.

**Read next:** [The register](the-register.md), [Third parties](third-parties.md) if the unit has suppliers.

## Owners of systems, risks, and controls

Anyone can be an owner. **On Home:** a risk of theirs due for review, a control to rate, evidence of theirs that has stopped counting or soon will, a third party of theirs due for its review, an action that is theirs, an issue that is theirs to put right.

**What they do:** assess their risks when asked, with a reason; attach evidence that their controls work, before it lapses; finish their actions by their dates; and put right the issues raised on what they own, then propose closure. They are reminded two weeks ahead, and again when late.

**Read next:** [The register](the-register.md#assess-it), [Evidence](evidence-and-testing.md#evidence), [Work on an issue](issues-and-exceptions.md).

## Leaders

**On Home:** the figures for their units; every risk in their units that needs a decision; acceptances they gave that are about to expire; and exceptions to decide. Late actions, issues, and reviews in their units come to them as notices under the bell after three weeks.

**What they do:** for each risk above appetite, either see that it is being treated or accept it, with a reason and an end date, up to their limit; a risk beyond their limit goes to someone with a higher one. They decide exceptions asked for in their units, and approve policies when named as an approver.

**Read next:** [Accept a risk](the-register.md#accept-a-risk), [Exceptions](issues-and-exceptions.md#exceptions), [Rating and standing](the-register.md#rating-and-standing).

## Staff

**On Home:** the actions that are theirs, policies to acknowledge, and questionnaires a campaign has sent them; and, when something is owed, the risks and controls they own.

**What they do:** finish their actions, acknowledge policies, answer campaigns, and report anything that goes wrong under **Incidents → Report something**, which takes a minute. They read the organization's policies in the **Policy library**.

**Read next:** [Report something](incidents.md), [The policy library](policies.md#the-policy-library).

## Internal audit (auditors)

**On Home and in the menu:** the whole record, read-only, with its full history; and the **Audit** menu: the universe, plans, and outside access.

**In the first weeks:** read the universe, ranked from the register, and record what audit has to say about each thing in it; draft the plan for the period and have it approved; start the first engagement with at least two auditors.

**After that:** fieldwork in workpapers, requests to the audited, findings raised as issues, the report, the committee report, and confirming that findings are put right.

**Read next:** [Internal audit](internal-audit.md), [The history](running-the-program.md#the-history), [As of a date](running-the-program.md#as-of-a-date), [Dossiers](running-the-program.md#dossiers).

## Administrators

**In the menu:** **Admin**: people, units, appearance, single sign-on, other systems (tokens and webhooks), the assistant if it is turned on, and operations.

**In the first week:**

1. Load the units and people: [Set up the organization](getting-started.md#set-up-the-organization).
2. Give roles as agreed with the security leader.
3. Set up single sign-on and email if the organization wants them: [Configuration](configuration.md).
4. Check **Admin → Operations**: the version, the database, the last backup, and what stands between the installation and production.

**After that:** add and remove people as they come and go, take backups and check they restore, upgrade when a release comes out, and make tokens for other systems when asked.

**Read next:** [Configuration](configuration.md), [Deployment](deployment.md), [Other systems and assistants](other-systems.md), [When something goes wrong](help.md).
