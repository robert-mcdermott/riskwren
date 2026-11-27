# Wave 7: Audit (v0.7.0)

**Goal:** give the third line its own workspace on the same record, without compromising its independence. Waves 1 to 6 made a record that the first and second lines keep, and that auditors could read but not touch. Wave 7 gives internal audit what it does with that record: decide what is worth auditing and when, plan a period's work, carry out each engagement with a program of work and workpapers that are reviewed and signed off, ask the audited for what is needed, and turn what is found into issues that management puts right and audit confirms. Work in progress is the audit team's alone until the report is issued.

**Branch:** `wave-7` · **Target version:** `0.7.0` · **Status:** ☐ in progress

The security team comes first here as everywhere ([roadmap](../roadmap.md#whose-work-comes-first)). For a security leader, audit is the most demanding reader of the record: an engagement on access management or third-party risk asks for the same controls, tests, evidence, and issues the security team already keeps. In this wave that means an auditor can draw on that record directly instead of asking for it again; requests name what is needed and are answered with evidence already on file where it exists; and a finding about a security control lands in the same issue register, with the same severity and dates, that the security team already works from.

## Exit criteria

The wave is done when, on a fresh checkout:

1. The audit universe lists the auditable units, processes, systems, third parties, and scopes, each with its last audit and a ranking drawn from the register, which an auditor may adjust with a reason (AUD-01).
2. A period's plan names its engagements with the reason for each, is approved by a named person, and is tracked against: planned, under way, reported, or dropped with a reason (AUD-02).
3. An engagement moves through planning, fieldwork, and reporting, with a team, dates, and a program of work (AUD-03).
4. Each step of the program has a workpaper with what was done, what was found, the evidence, review notes, and sign-off by someone other than its preparer (AUD-04).
5. Requests to the audited list what is needed, each assigned to a person with a date and answered with evidence (AUD-05).
6. A finding becomes an issue with management's action plan, and audit validates its closure (AUD-06).
7. Work in progress is visible only to the engagement's team until the report is issued (AUD-07).
8. A person outside the organization can be given read-only access to one engagement or scope for a set period, and everything they open is recorded (AUD-08).
9. A period's engagements, findings by severity, and overdue actions print as one report for the committee (AUD-09).
10. The role-by-route matrix covers every new route; the demo has something worth reading on every new screen; the accessibility audit passes over them.

## Slices

### Slice 1: Universe and plan ☑

**Goal:** what is worth auditing, and what this period's work will be.

- [x] The audit universe: units, processes, systems, third parties, and scopes as auditable entities, each with its last audit, and a ranking drawn from the register (its open risks and their ratings, its open issues, how critical it is, and how long since it was audited) that an auditor may adjust with a reason
- [x] The plan for a period: engagements proposed with the reason for each, approved by a named person, and tracked against

**Acceptance:** an entity's ranking says how it was reached, and moves when the register does; a plan once approved records who approved it, and each engagement in it says where it stands.

**Done:** `riskwren.internal_audit.universe` gathers the register once (open risks with their subjects and units, live issues with theirs, the units beneath each unit, criticalities, what audit has said, and the engagements) and ranks every unit beneath the organization and every process, system, third party, and scope in use: up to 30 for its worst open risk's residual rating, 4 for each risk above appetite (up to 16), 2 for each open issue and 2 more for each critical or high one (up to 16), up to 15 for its criticality, up to 20 for a scope's requirements not yet in place, 20 if never audited down to 5 after a year, and what audit moved it by, each part shown with its points. 55 or more is high, 30 or more medium. `audit_entity` keeps what audit says about a thing (a move of up to 30 points with its reason, an audit before RiskWren, or leaving it out with the reason). `audit_plan` (`APL`) is drafted by auditors and approved by an auditor other than its drafter, recording the committee, or by a leader of the whole organization; `engagement` (`AUD`) rows are planned in it with their reasons and dates, dropped with a reason or restored, and say if they were added after approval. Read by those who read everything and those who lead the whole organization; changed by auditors alone, refused at the door for anyone else (a new `audit` need in the access table). **Audit → Universe** and **Audit → Plans**; the demo's auditor moves medication dispensing up after two near misses, records an earlier identity audit, leaves Facilities and Safety out, and drafts this year's plan, which the president approves for the committee, and next year's. The acceptance tests are `tests/test_internal_audit.py`.

### Slice 2: Engagements and workpapers ☑

**Goal:** an engagement carried out, its work reviewed and signed off, and kept to its team until it is reported.

- [x] Stages, a team, dates, and the program of work
- [x] Workpapers with what was done, what was found, the evidence, review notes, and sign-off by someone other than the preparer
- [x] Work in progress visible only to the team until the report is issued

**Acceptance:** an engagement moves on only when its work allows (a program before fieldwork, every workpaper signed off before reporting, a summary and an opinion to report); a preparer cannot sign off their own workpaper, nor one with a review note open; before the report, someone who may read the plans, or an auditor not on the team, sees that the engagement exists and nothing of its work, and the history holds none of its words.

**Done:** `engagement_member` (a lead and members, auditors all), `workpaper` (a step's procedure, what was done and found, evidence by reference, its preparer and sign-off), and `review_note` (written, answered by the preparer, cleared by its writer). Starting an engagement names its team and what it covers; its lead moves it from planning to fieldwork, reporting, and reported, the last with a summary and an opinion, after which the universe counts the thing as audited that day. Recording the work again, or a new note, undoes a sign-off. Until it is reported, its work, scope, and notes are its team's alone; the history redacts the words of workpapers, notes, and the engagement's scope and report, so that reading it does not undo that. **Audit → Plans** opens each engagement's page with its stages, team, progress, and program of work. The demo's two auditors have reported two engagements and are in fieldwork on a third, with a review note waiting for its answer. The acceptance tests are `tests/test_engagements.py`.

### Slice 3: Requests ☑

- [x] Requests to the audited, each item assigned to a person with a date and answered with evidence, from what is on file where it exists

**Acceptance:** a request reaches the person asked on their home page and nobody else outside the team; it is answered by that person alone, with words or evidence they can see; the team accepts it or sends it back with the reason, and the history keeps its words out.

**Done:** `audit_request` holds what is asked, of whom, by when, the answer and its evidence, and whether it was accepted or sent back. The team asks while planning or in fieldwork; the person asked, auditor or not, opens and answers it, and is offered the evidence already kept about the thing being audited, and for a scope about the controls it uses, that they may see. Home lists a request for the person asked and an answer to read for the team. The engagement's page lists its requests; a request has a page of its own. The demo has a request answered and accepted, one answered and waiting for the team, and one past its date. The acceptance test is `tests/test_engagements.py::test_a_request_is_answered_by_the_person_asked_and_accepted_by_the_team`.

### Slice 4: Findings and follow-up ☑

- [x] Findings as issues with management's action plan; closure validated by audit; the report issued; the committee report

**Acceptance:** a finding is an issue that says which engagement raised it; management proposes its closure, and only an auditor who neither owns it nor proposed the closure confirms it; the committee report counts it by severity.

**Done:** a finding is raised by the engagement's team during fieldwork or reporting through the register's own `issues.create`, as audit (`source_kind` *audit*, `source_type` *engagement*), in the unit of the thing audited, about the scope when it is one, and handed to the manager named; its date follows from its severity and its actions are management's action plan. `issues.confirms` makes an auditor, not the second line, the one who confirms, withdraws, or reopens a finding, and a proposed closure is told to the engagement's team and waits on auditors' home pages; the validation route is open to everyone and the service decides. The engagement lists its findings; each plan has a committee report of its engagements and opinions, findings by severity, and findings and actions past their date, which prints. The demo's first engagement raised two findings: one put right, proposed closed, and confirmed by audit; one with its action past its date. The acceptance test is `tests/test_engagements.py::test_a_finding_is_an_issue_that_audit_confirms_closed`.

### Slice 5: Outside auditors ☑

- [x] Scoped, time-limited, read-only access for a person outside the organization, with every view recorded

**Acceptance:** a link opens one reported engagement or one scope, read-only, and nothing else; it stops on its date or when withdrawn; each use is an event in the history naming who looked; the token is never stored.

**Done:** `outside_access` holds the person, whom they are with, why, the one engagement (once reported) or scope it opens, its end at most 90 days ahead, and the digest of its 256-bit token, which is shown once in `meta.link.url` and follows a `#`. Given and withdrawn by auditors (**Audit → Outside access**); `GET /outside` with the token in `X-RiskWren-Access` is the one route it reaches, without an account, slowed against guessing as the due diligence link is, and gone (410) once expired or withdrawn. It returns the engagement as its readers see it, or the scope's statement, controls, evidence, and plan of action; each use writes `outside.viewed` on the engagement or scope with the outsider as the actor, and counts. The page at `/outside` reads it without the app around it. The demo's external auditors have the backups engagement and have looked twice; the sponsor's monitor had the trial data platform for a fortnight last spring. The acceptance tests are `tests/test_outside.py`.

Not done, and said so: the files of evidence are listed, not downloadable, through the link; an outsider who needs one asks for it.

### Slice 6: Release prep ☐

- [ ] Guides, changelog, upgrade from 0.6.0 on both databases, audits, release, and the site republished

## Notes

- Auditors still change nothing in the first and second lines' records. What wave 7 gives them is records of their own: the universe's adjustments, the plan, engagements, workpapers, requests, and findings, which become issues in the shared register like any other.
- Slices 1 and 2 were built together and landed in one commit: the plan's engagements and the engagement's stages are the same record.
- An entity of the universe is not a new kind of thing: it is a unit, process, system, third party, or scope already in the record, with what audit knows about it.
