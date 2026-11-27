# Wave 8: Incidents and resilience (v0.8.0)

**Goal:** when something goes wrong, it is reported, handled, and learned from; and the organization knows what it cannot afford to lose. Waves 1 to 7 made a record of what could go wrong, what is done about it, what is promised, who is depended on, and how all of it is checked. Wave 8 adds what actually happens: incidents, near misses, and concerns reported by anyone, triaged and handled, kept to those who need to know when they are sensitive, assessed for whether they must be notified, and joined back to the risks they realized and the controls that failed; and, for resilience, what each process needs to recover and whether what it relies on can deliver it.

**Branch:** `wave-8` · **Target version:** `0.8.0` · **Status:** ☐ in progress

The security team comes first here as everywhere ([roadmap](../roadmap.md#whose-work-comes-first)). For a security team, this wave is incident handling on the same record as the risks and controls: a report that takes a minute from anyone, triage that names the systems, information, and third parties involved, a breach assessment with its clock, and the risks an incident realized and the controls that failed, so that the register learns from what happened.

## Exit criteria

The wave is done when, on a fresh checkout:

1. Anyone signed in can report an incident, a near miss, or a concern in one short form (INC-01).
2. Where the organization opens it, a concern can be reported through a link with no sign-in and no identity kept, and the reporter follows it up with a code (INC-02).
3. Each report is triaged: a category, a severity, the records it concerns, and who handles it (INC-03).
4. A case can be limited to named people, and its existence is hidden from everyone else, in search and history too (INC-04).
5. An incident involving protected information has a structured breach assessment with its factors, conclusion, deadlines, and each notification made (INC-05).
6. An incident links to the risks it realized and the controls that failed, opens corrective actions, and records what was learned (INC-06).
7. A process has a business impact analysis, and its recovery needs are checked against what its dependencies can deliver (RES-01, RES-02).
8. Continuity plans are versioned and print for use offline; exercises record findings that become issues (RES-03, RES-04).
9. The role-by-route matrix covers every new route; the demo has something worth reading on every new screen; the accessibility audit passes over them.

## Slices

### Slice 1: Reporting and triage ☐

**Goal:** a report from anyone in a minute, and each one triaged.

- [ ] Report an incident, a near miss, or a concern: what happened, when, and where, in one short form (INC-01)
- [ ] Reporting without a name, where the organization opens it, with a code to follow up (INC-02)
- [ ] Triage: category, severity, the records it concerns, and who handles it (INC-03)

**Acceptance:** a report takes one form; it is seen by its reporter, those who triage, its handlers, its unit's leaders and stewards, and those who read everything, and by nobody else; triage gives it a category, a severity, its records, and an owner, and is in the history.

### Slice 2: Cases ☐

- [ ] Restricted cases with named members, hidden from everyone else in lists, search, and history (INC-04)

### Slice 3: Breach assessment ☐

- [ ] The structured assessment, deadlines, and notifications; privacy impact assessments; privacy and breach framework packs (INC-05, INC-07)

### Slice 4: Learning and losses ☐

- [ ] Incidents joined to risks and controls; corrective actions; loss events and near misses (INC-06)

### Slice 5: Business impact ☑

- [x] Impact analysis per process; recovery needs checked against what dependencies can deliver (RES-01, RES-02)
- [ ] Sites, as dependencies of their own

**Acceptance:** an analysis says how a process's loss hurts over time, its recovery time and point, and the least it needs; each system and service it relies on is checked against that, and every shortfall is listed, including a capability nobody has said.

**Done:** built first, while slices 1 and 2 wait on the decisions below. `impact_analysis` holds, for one process, the impact at each of five times (never lessening), the recovery time and point in hours, and the least it needs, by a named person, superseded and never edited. `recovery_capability` holds what a system or service can be restored within and lose, and what that rests on. `riskwren.resilience` checks a process's current analysis against the current capability of each system and service it relies on and lists the shortfalls in words; both appear in the record's history with titles of their own. A process's **Business impact** tab, a system's or service's **Recovery** tab with the processes that rely on it, and **Reports → Resilience**, most shortfalls first. The demo analyses four critical processes and the systems they rely on: research storage relies on a backup service whose full restore takes five days against the three days it needs. The acceptance test is `tests/test_resilience.py`. Sites, as places a process relies on, are left for a later slice.

### Slice 6: Plans and exercises ☐

- [ ] Versioned plans that print for use offline; exercises with findings (RES-03, RES-04)

### Slice 7: Release prep ☐

- [ ] Guides, changelog, upgrade from 0.7.0 on both databases, audits, release, and the site republished

## Decisions

Settled on 2026-11-27, before slices 1 and 2 were built.

- **Who sees an incident.** Its reporter, the people handling it (its owners), those who triage (managers, and assessors for its unit), the leaders and stewards of its unit and the units above it, and those who read everything. An incident that concerns people in its own unit is made a restricted case (slice 2), which its unit's leaders and stewards do not see unless they are named on it.
- **Who triages.** Managers, and assessors for the incident's unit, which includes a security team whose assessors work across the organization. Triage sets the category, the severity (on the issue scale), the unit, the records it concerns, and the owner who handles it.
- **Reporting without a name is off until an administrator opens it.** When it is open, a report through the link keeps no account, no name, and no address. The follow-up code is shown once, kept only as a digest, and long enough that guessing it is hopeless, so, unlike the other links, failed codes are not counted against the address that sent them, and nothing ties a report to where it came from. Whether the server's own access log may keep addresses is the operator's to decide, and the guide will say so.
- **Categories** are a vocabulary of the program, editable like the others, starting as security, privacy, safety, conduct, compliance, operations, and other.

## Notes

- An incident is a record of its own (`INC`), not an issue: an issue is something to put right, an incident is something that happened. Triage may raise issues from an incident; slice 4 joins it to the risks it realized and the controls that failed.
