# The risk and compliance engine

This document describes how RiskWren works things out: how a risk gets its rating, how controls move it, what "within appetite" means, who may accept what, when things come due, and how readiness against a framework follows from tests and evidence. Every rule here is data the organization can edit, every result shows its reasoning, and nothing is decided without a named person.

## The loop

```text
   THINGS                  RISKS                    CONTROLS                 REQUIREMENTS
 units, processes,   what could go wrong,      what is done about it,    what must be met, from
 systems, third  ◀── rated before and    ◀──── described once,      ────▶ frameworks, rules,
 parties, data       after controls            owned, and tested          contracts, policies
                          │                         │                          │
                          │ above appetite?         │ tested                   │ applied to
                          ▼                         ▼                          ▼
                     TREATMENT                   TESTS ──▶ EVIDENCE          SCOPES
                 plan, or a named,                  │                    readiness per scope
                 time-limited acceptance            │ failed                and framework
                          │                         ▼
                          └──────────────────▶   ISSUES ──▶ ACTIONS ──▶ validated closure
```

Wave 1 builds the left half: things, risks, controls, and treatment. Wave 2 adds the right half: requirements, scopes, tests, evidence, and issues. Later waves add the processes that keep the loop turning.

## The scoring method

A **scoring method** is one versioned document. A published version is never changed; a new version is published beside it, and every assessment records the version it was made under.

### Likelihood

Five levels by default, each with a definition people can apply without a statistician.

| Level | Name | Default definition |
|---|---|---|
| 1 | Rare | Not expected within ten years |
| 2 | Unlikely | Could happen once in five to ten years |
| 3 | Possible | Could happen once in two to five years |
| 4 | Likely | Expected about once a year |
| 5 | Almost certain | Expected several times a year |

### Impact

Impact is judged on several **dimensions**, because the worst consequence of a risk is often not financial. The default method has five, each with five levels (Negligible, Minor, Moderate, Major, Severe) and a written definition for every level.

| Dimension | What it asks |
|---|---|
| **Mission** | How far research, care, or teaching would be set back, and whether the loss could be recovered |
| **Safety** | Harm to patients, participants, staff, or the public |
| **Financial** | Loss or unplanned cost, expressed as a share of the annual operating budget so the scale fits any size of organization |
| **Legal and regulatory** | Findings, sanctions, loss of funding eligibility, or loss of a license to operate |
| **Trust** | The confidence of participants, patients, funders, partners, and the public |

An assessor rates the dimensions that apply and leaves the rest unrated. **The overall impact is the highest level rated.** Averaging would let four small consequences hide one severe one.

### Matrix and rating

Likelihood and overall impact are combined by looking up a cell in a matrix, not by multiplying, so an organization can shape the matrix to its own judgment. The default leans toward impact: a severe consequence is never rated below High, however rare.

```text
              Likelihood
  Impact      1 Rare    2 Unlikely  3 Possible  4 Likely   5 Almost certain
  5 Severe    High      High        High        Critical   Critical
  4 Major     Moderate  Moderate    High        High       Critical
  3 Moderate  Low       Moderate    Moderate    High       High
  2 Minor     Low       Low         Moderate    Moderate   Moderate
  1 Negligible Low      Low         Low         Low        Moderate
```

The result is a **rating**: Low, Moderate, High, or Critical by default. An organization may define three to five ratings and name them as it likes.

## Assessments

A risk carries three ratings, each from an **assessment**: a dated judgment by a named person, with a rationale.

| Kind | The question |
|---|---|
| **Inherent** | How likely and how bad, if the controls were not there or did not work? |
| **Residual** | How likely and how bad, given the controls as they actually are? |
| **Target** | Where should this be once treatment is complete? |

An assessment is never edited. A new assessment supersedes the old one, and both stay on the record. A risk's current ratings are its latest assessment of each kind.

Every rating **explains itself**: one click shows the likelihood chosen, the level on each dimension, the definitions of those levels, who judged it and when, their rationale, and the method version.

## Controls and the suggested residual rating

### What is known about a control

A control's **effectiveness** has two parts, each rated Effective, Partly effective, Ineffective, or **Not assessed**:

- **Design:** would it reduce the risk, if it operated as described?
- **Operation:** does it operate as described?

Each rating records who gave it, when, and on what **basis**: a judgment by the owner, an attestation in a campaign, or a test by someone independent (wave 2). A rating older than the control's cadence is **stale**.

The control's overall strength is the weaker of the two parts:

| Design and operation | Strength |
|---|---|
| Both effective | 1 |
| Either partly effective, neither ineffective | ½ |
| Either ineffective | 0 |
| Either not assessed or stale | 0 |

The last row is the principle that **unknown is not zero risk**: a control nobody has checked reduces nothing in the arithmetic, and the screen says why.

### How a control bears on a risk

A link from a control to a risk records two things:

- **What it reduces:** likelihood (a preventive control), impact (a corrective or mitigating one), or both.
- **Reliance:** *primary* (the risk depends on it; weight 1) or *supporting* (it helps; weight ½).

### The arithmetic

For each axis, add up *strength × reliance weight* over the controls that reduce it. The whole part of the sum is the number of levels the axis comes down, to a limit of two levels and never below level 1.

```text
  Risk: loss of irreplaceable specimens from freezer failure
  Inherent: likelihood 4 (Likely) × impact 5 (Severe)  →  Critical

  Likelihood                                   strength × weight
    Preventive maintenance contract   primary   effective          1   × 1  = 1
    Temperature alarm with call-out   primary   partly effective   ½   × 1  = ½
    Door-ajar signage                 supporting not assessed      0   × ½  = 0
                                                             total 1½  →  down 1 level  →  3

  Impact
    Split of specimens across sites   primary   effective          1   × 1  = 1
    Backup freezer capacity           supporting effective         1   × ½  = ½
                                                             total 1½  →  down 1 level  →  4

  Suggested residual: likelihood 3 × impact 4  →  High
```

The limit of two levels exists because a long list of controls must not be able to argue any risk down to nothing. The weights and the limit are part of the scoring method.

### A suggestion, not a verdict

The arithmetic produces a **suggested** residual rating. The assessor sees it with its working, then confirms it or sets a different likelihood and impact with a reason. Both the suggestion and the judgment are kept on the assessment.

After that, RiskWren keeps comparing. If a control later fails a test, goes stale, or is unlinked, so that today's suggestion is worse than the residual rating on record, the risk is flagged **residual may be out of date**, the reason is named, and its owner is asked to re-assess. This is where a connected register earns its keep: a failed test in one place reaches every risk that leaned on the control.

## Appetite and standing

**Appetite** is set per risk category: the highest residual rating the organization is content to live with there. A research institute might hold Low for participant safety and High for scientific strategy.

**Rating** says how much is at stake. **Standing** says whether the risk is in order. They are separate signals everywhere in the product.

| Standing | Meaning |
|---|---|
| **Within appetite** | The residual rating is at or below the category's appetite |
| **Being treated** | Above appetite, with an active treatment plan that is on time |
| **Accepted** | Above appetite, with a named acceptance in force |
| **Needs a decision** | Above appetite, with no active plan and no acceptance in force; or a plan that is overdue; or an acceptance that has expired |
| **Not assessed** | No residual assessment yet |
| **Closed** | The risk no longer applies; kept for the record |

Two flags can accompany any standing: **review overdue**, and **residual may be out of date**.

## Treatment and acceptance

Every risk above appetite needs a **response**, recorded with a rationale: *reduce* it (a treatment plan), *accept* it, *transfer* it (insurance or contract), or *avoid* it (stop the activity).

- A **treatment plan** has an objective, a target rating, an owner, a due date, and actions. When its last action closes, the owner is asked for a new residual assessment; the plan does not lower the rating by itself.
- An **acceptance** names the person accepting, the rationale, any conditions, and an end date. It is a statement by that person and is never edited. When it expires the risk's standing becomes *needs a decision*.

### Who may accept

Acceptance is governed by an **authority table**, by rating:

| Residual rating | May be accepted by (default) | For at most (default) |
|---|---|---|
| Moderate | A leader of the risk's unit or any unit above it | 24 months |
| High | A leader whose grant carries authority for High | 12 months |
| Critical | A leader whose grant carries authority for Critical | 6 months |

A leader's role grant states the highest rating they may accept. Two rules hold whatever the table says: **nobody accepts a risk they own**, and an acceptance by someone without the authority is refused, in the app and in the API.

## What comes due, and when

Cadences are one table, keyed by rating or criticality.

| Residual rating | Risk reviewed every (default) |
|---|---|
| Critical | 3 months |
| High | 6 months |
| Moderate | 12 months |
| Low | 24 months |

A risk's next review date is set from its latest residual assessment. Until the scheduler arrives in wave 3, dates are computed and shown, and overdue items appear on the owner's home page and the dashboard; from wave 3, reminders, escalation, control test and attestation cadences, and evidence renewal run on the same table.

## Frameworks, scopes, and applicability (wave 2)

- A **framework** is any source of requirements, loaded as a pack: a public standard, a regulation, a grant's terms, a data use agreement, an internal standard. Each **requirement** has a stable code.
- A **crosswalk** maps a control to each requirement it helps satisfy. A requirement may need several controls; a control may serve many requirements in many frameworks.
- A **scope** is a named boundary that must meet one or more frameworks: *the clinical systems*, *the controlled-access data enclave*, *the whole organization*. It lists the units, processes, systems, and information inside it.
- Within a scope, each requirement is **applicable** or excluded with a reason. A **baseline** (a published selection from a framework) sets the starting point.
- Within a scope, each applicable control has an **implementation**: its status (planned, partly in place, in place, not applicable), who is responsible, and how it is done here.

### Inheritance

In a federated organization most safeguards are provided once and relied on many times. A scope may **offer** controls. Another scope may **inherit** an offered control, in one of two ways:

- **Inherited:** the providing scope does all of it. The inheriting scope shows the provider's implementation and its current state, and cannot rate it.
- **Shared:** the provider does part and the inheriting scope does the rest. The inheriting scope records and evidences its own part; the requirement is only as strong as the weaker half.

When a provider's control fails a test, every scope that inherits it shows the failure the same day, and the issue names them all.

## Tests (wave 2)

A **test** examines one control in one scope within an **assessment**. It records the procedure followed, the method (examine, interview, or test), what was sampled, the evidence, and a result for design and for operation.

- The person who records a result may not be an owner of the control, and a second person reviews the result before it counts.
- A result is never edited. A correction is a new result that supersedes it.
- A counted result becomes the control's effectiveness rating with the basis *test*, which outranks a judgment or an attestation of the same age.
- A result of partly effective or ineffective opens an issue.

One result therefore updates the control, every requirement it is mapped to, in every scope that relies on that implementation, and the suggested residual rating of every risk it reduces. This is what *test once* means.

## Evidence and freshness (wave 2)

An evidence item has an owner, the date it was collected, the period it covers, and a **valid-until** date, defaulted from the cadence of what it supports. Evidence past that date is **stale**: it stays on the record and stops counting.

## Readiness (wave 2)

For a scope and a framework, each applicable requirement is in exactly one state, worked out and never typed in:

| State | Rule |
|---|---|
| **Gap** | No control mapped to it is used in this scope |
| **Planned** | Controls are mapped, and at least one implementation is not yet in place |
| **In place** | Every implementation is in place, but at least one lacks a current, counted test with current evidence |
| **Verified** | Every implementation is in place and has a current test result of effective, with current evidence |
| **Failing** | At least one control's current test result is partly effective or ineffective |

A requirement takes the weakest state among its controls, with *failing* weakest of all. Requirements excluded as not applicable are left out of every figure and listed separately with their reasons. The readiness bar for a scope is the count in each state, the list narrows to any one of them, and each control in it says in words why it is where it is.

An owner's attestation alone can take a requirement to *in place*, never to *verified*. That takes a test: recorded by someone who does not own the control, confirmed by a second person who does not own it either, and still within the cadence that keeps a rating current. A confirmed test result is the control's rating, and a judgment does not replace it while it holds. A control is tested in the scope that does it; scopes that inherit it take the result.

## Issues and their clocks (wave 2)

An issue has a **severity** with a defined meaning, and its due date follows from severity by rule (by default: Critical 30 days, High 90, Moderate 180, Low 365). Moving the date needs a reason and is counted. An issue closes only when someone other than its owner has confirmed the evidence of closure.

An **exception** is an approved, time-limited departure from a control, a requirement, or a policy, with compensating controls. While it is in force the item it covers is shown as *excepted*, not failing; when it expires, the underlying state returns.

## Rules are data

Applicability, cadences, authority, severity clocks, the questions a questionnaire shows, and (from wave 5) third-party tiering are all expressed in one small **condition language**: a tree of `all`, `any`, `not`, and comparisons over named fields and answers. There are no expression strings, and nothing is ever evaluated as code. The evaluator exists in Python for authority and, where a form must react as it is filled in, in JavaScript, held together by one shared file of test cases.

Changes to the scoring method, appetite, or cadences are previewed before they are published: the app lists the risks whose rating, standing, or dates would change.
