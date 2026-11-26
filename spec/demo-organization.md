# The demo organization

`riskwren demo` builds a complete, fictional organization to explore: the **Northmere Institute for Health Research**. It exists so that anyone can see every feature working with realistic content within a minute of installing, so that every screenshot in the documentation shows the real application, and so that the test suite has an end-to-end exercise of the whole system.

Northmere is invented. Its people, labs, systems, vendors, and incidents do not exist, and nothing in it is taken from a real organization.

## Rules

1. **Built by the real code.** The generator does not insert rows. It calls the same services the app uses, in order, under a simulated clock: accounts are created, risks are raised and assessed, controls are rated, plans are opened and worked, risks are accepted and the acceptances expire. Every record, assessment, and event in the demo is genuine output, and the history chain verifies.
2. **Deterministic.** The same seed produces the same organization, record for record. A different seed produces different people and details with the same shape.
3. **Relative to today.** History is generated backward from the day the demo is built, so there is always something due this week, something overdue, and an acceptance about to expire.
4. **Invented and unmistakably so.** Email addresses use `northmere.example`. Vendor and product names are made up and checked against the private-terms list. Identifiers for things in other systems (awards, agreements, asset tags) use formats that cannot be mistaken for real ones.
5. **Clearly marked.** A demo installation shows a "Demo data" marker on every page, and its sign-in page offers one-click sign-in as each sample person.
6. **Grows with the product.** Each wave extends the generator to cover what the wave adds. The last check of every release is that the demo shows every documented screen with data.

## The institute

Northmere is a mid-sized, independent, nonprofit research institute with an outpatient research clinic, about 1,800 staff, and a risk and compliance program that moved out of spreadsheets two years ago.

| Area | Units |
|---|---|
| **Research divisions** | Cancer Biology · Immunology and Infectious Disease · Population Sciences · Computational and Data Science · Clinical Research |
| **Labs** | About 30, each named for its principal investigator |
| **Core facilities** | Genomics · Biospecimen Repository · Imaging · Comparative Medicine · Research Computing |
| **Clinic** | Northmere Research Clinic: Infusion · Clinical Laboratory · Pharmacy · Patient Access |
| **Administration** | Information Technology · Information Security · Compliance and Privacy · Sponsored Programs · Finance · Human Resources · Facilities and Safety · Legal · Communications · Philanthropy |

Units nest three and four deep, so scoped roles, roll-ups, and escalation all have something to show.

### People

About 210 accounts, including a chief risk and compliance officer and a team of four, assessors in security and compliance, an internal auditor, leaders for every division with different acceptance limits, stewards for most units, and principal investigators, lab managers, clinicians, engineers, and administrators who own risks, controls, and systems.

Sample accounts for signing in as each role are listed on the demo's sign-in page.

### Scale

Enough to look like an organization that has used RiskWren for a while, and small enough to build in under a minute. Wave 1 figures:

| Records | About | Notes |
|---|---|---|
| Org units | 60 | Four levels |
| Accounts | 210 | Every role represented; one departed |
| Processes | 75 | Research, clinical, and administrative; every criticality |
| Systems | 105 | Applications, platforms, instruments, and infrastructure; some unsupported, some retired |
| Third parties | 45 | Suppliers, collaborators, sponsors, and subrecipients |
| Risks | 180 | Every category, rating, and standing; a dozen escalated; some not yet assessed |
| Risk assessments | 480 | Inherent, residual, and target, with re-assessments over time |
| Controls | 135 | Starter controls made specific, and local ones; varied effectiveness, some never assessed, some gone stale |
| Treatment plans | 30 | Active, complete, overdue |
| Acceptances | 25 | In force, expiring soon, expired, withdrawn |
| Actions | 100 | Open, done, overdue, extended |
| Events | 6,000 | Twenty-four months of history |

The figures move a little with the seed and with the day it is built.

The mix is realistic: most risks are low or moderate and within appetite; a few dozen are high; a handful are critical. Residual ratings improve as plans complete, and a few risks have got worse.

## Storylines

Generated volume makes the lists and charts convincing. A set of hand-written storylines makes the detail pages worth reading, and each one demonstrates a capability.

| Storyline | What it shows |
|---|---|
| **Loss of irreplaceable specimens from freezer failure** in the Biospecimen Repository | A critical inherent risk brought to high by controls of known effectiveness; the suggested residual with its working; a treatment plan to split collections across two buildings |
| **Ransomware reaching research storage** | A risk that concerns a process, three systems, and a third party; controls owned by two different units; a residual assessment that departs from the suggestion, with the reason |
| **An unsupported instrument workstation** that cannot be patched without invalidating the instrument | A named, time-limited acceptance by a division leader with conditions; the acceptance expiring next month |
| **A high risk the core's own director tried to accept** | The authority table refusing an acceptance above the leader's limit, and the acceptance later given by the right person |
| **Emergency power that cannot carry the freezer farm** | A critical risk resting on a control that failed its test; escalated, planned, and accepted for six months by the one executive who may |
| **Unallowable costs charged to a federal award** | A financial stewardship risk with a low appetite; a detective control rated partly effective; a plan with overdue actions and the risk's standing changed to *needs a decision* |
| **Departure of a principal investigator** | Orphaned risks and controls, shown to those who can name a new owner; one reassigned |
| **A participant-privacy risk escalated from a lab to its division** | Escalation with a reason, and the roll-up a division leader sees |
| **Sole-source dependence on a sequencing reagent supplier** | A third-party risk, a transfer and reduce response, and the link from process to system to supplier |
| **A control nobody has assessed** | *Not assessed* counting for nothing in the suggestion, and the risk flagged because of it |
| **A risk that got worse** | A re-assessment after an incident elsewhere raises likelihood; the earlier assessment kept, superseded |
| **The clinic's medication-refrigeration risk, closed** | A risk closed when the activity moved, kept for the record |

Wave 2 adds scopes (the clinical systems under the health security rule, a controlled-access data enclave under the federal standard for protecting controlled information, and central information technology as a provider of inherited controls), an assessment in progress, evidence going stale, and issues at every stage.

The scopes show a security program in working order with work left, because that is what an adopter needs to see and what most have. Central information technology uses about 35 controls and offers them; the other two inherit most of what they need and add their own. Each scope comes out between a half and three quarters ready, with every state present: verified, in place, excepted, planned, failing, and gaps that nothing answers yet. What is known of each central control is written down, not left to chance, so the picture is the same whenever it is built.

## Using it

```bash
uv run riskwren demo                       # builds ./demo
uv run riskwren --config demo/riskwren.toml serve
```

`riskwren demo --seed N` builds a different Northmere; `--force` rebuilds in place. The demo directory is ignored by git. The documentation's screenshot capture starts its own demo in a temporary directory, so screenshots are always of a fresh, known state.
