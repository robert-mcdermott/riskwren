# Wave 2: Compliance (v0.2.0)

**Goal:** test once, satisfy many. One set of controls answers every framework the organization is held to, and readiness against each is worked out from tests and evidence, never typed in. Wave 1 answered "what could go wrong, and what are we doing about it?" Wave 2 answers "what are we held to, and can we show that we meet it?" with the same controls.

**Branch:** `wave-2` · **Target version:** `0.2.0` · **Status:** ◐ in progress

## Exit criteria

The wave is done when, on a fresh checkout:

1. `riskwren init` loads four public frameworks, built from their publishers' machine-readable files, each showing its publisher, version, license, and source; a test fails the build if any pack carries text its declared policy does not allow (CMP-01 to CMP-03).
2. A manager enters an agreement's terms as a framework of the organization's own, by hand or from a spreadsheet, and it behaves like any other (CMP-05).
3. A control is mapped to requirements in several frameworks; a requirement shows its controls and a control its requirements; the starter controls arrive mapped (CMP-04).
4. A scope names its boundary and the frameworks or baselines it must meet; each requirement in it is applicable or excluded with a reason; each applicable control has an implementation; the result prints as a statement of applicability (CMP-06, CMP-07, CTL-06).
5. One scope offers controls and another inherits them, fully or in part; the inheriting scope shows the provider's state and cannot rate what it does not do (CTL-07, CTL-08).
6. An evidence item is collected once, attached to several controls and tests, downloaded only by those entitled to what it is attached to, and stops counting on its date (EVD-01 to EVD-04, EVD-06).
7. An assessment tests a scope's controls. Nobody records a result for a control they own; a result counts once a second person has reviewed it; a counted result becomes the control's rating, moves every requirement the control is mapped to in every scope that relies on it, and moves the suggested residual of every risk it reduces (AST-01 to AST-05).
8. For a scope and a framework, every applicable requirement is in one of five states, each with the reason, and the bar opens to the requirements behind each segment; gaps are listed with a way to raise an issue (CMP-08, CMP-09).
9. A failed test opens an issue. An issue's due date follows from its severity; it is worked through actions; its owner proposes closure and someone else confirms it; a root cause is recorded. An exception is approved by someone other than whoever asked, expires, and while in force shows what it covers as excepted; each person has a list of what has been assigned to them or changed for them (AST-06, ISS-01 to ISS-07, OVS-06).
10. Any list exports as CSV and JSON; processes, systems, third parties, risks, controls, and requirements import from a spreadsheet with a mapping step and a dry run that reports every problem by row (INV-08, RPT-05).
11. The dependency graph around any record shows what it relies on, what relies on it, and its risks, controls, and scopes, with a list that says the same thing; those who read everything can browse every change in one place (INV-11, INV-15).
12. The role-by-route matrix covers every new route; the demo organization has scopes, an assessment in progress, evidence going stale, and issues at every stage; the accessibility audit passes over every new screen.

## Slices

### Slice 1: Frameworks ☑

**Goal:** what the organization is held to, on record, in the publisher's own words where the law allows.

- [x] The pack loader for frameworks: validation of the whole pack before anything is written, every problem reported together
- [x] Text policies, and the test that holds every built-in pack to its own
- [x] Build scripts that generate the four built-in packs from the publishers' files, recording the source and its version
- [x] `framework`, `requirement`, `baseline`; `riskwren frameworks list / load / show`
- [x] The organization's own frameworks: created in the app, requirements typed in or pasted
- [x] Browsing: the frameworks list, a framework's tree with search, a requirement's page

**Acceptance:** a new installation has the four frameworks with their baselines; a pack with one bad requirement is refused whole; the tree of the largest framework opens and searches without delay.

**Done:** `scripts/build-framework-packs.py` builds the four packs from the publishers' own files, each pinned by digest: the Cybersecurity Framework 2.0 (106 outcomes), SP 800-53 Rev. 5 release 5.2.0 (1,014 active controls and enhancements, with four baselines), SP 800-171 Rev. 3 (97 requirements), and the Security Rule from the electronic Code of Federal Regulations (91 standards, specifications, and paragraphs). `init` and `db upgrade` load them in a tenth of a second. Anyone signed in browses a tree a level at a time, searches it whole, narrows it to a baseline, and opens any requirement in full. Those who run the program enter agreements and internal standards as frameworks of their own, a requirement at a time or pasted in after a dry run.

### Slice 2: Crosswalks ☐

**Goal:** one control, many requirements.

- [ ] `control_requirement` with coverage (full, partial), a note, and its source (pack or person)
- [ ] Mapping from either end: a control's requirements, a requirement's controls
- [ ] The starter controls' crosswalk to the built-in frameworks, shipped with the control library and applied when a control is adopted
- [ ] Coverage of a framework: requirements with and without controls

**Acceptance:** a control adopted from the library arrives mapped; coverage figures open the requirements they count.

### Slice 3: Scopes and inheritance ☐

**Goal:** a boundary, what it must meet, and who does what inside it.

- [ ] `scope` with members (units, processes, systems), frameworks and baselines, an owner; SCP references
- [ ] Applicability per requirement with reasons; a baseline as the starting point
- [ ] Implementations: status, responsibility, how it is done here
- [ ] Offering and inheriting controls, fully or shared; the inheriting scope cannot rate what it inherits
- [ ] The statement of applicability, printable
- [ ] Information assets as a fourth kind of inventory record (INV-07)

**Acceptance:** the demo's enclave inherits identity and backup controls from central computing and shows their state; excluding a requirement without a reason is refused.

### Slice 4: Evidence and files ☐

**Goal:** proof, collected once.

- [ ] Content-addressed file storage in the data home; size and type limits checked by content; downloads as attachments under a locked-down policy, recorded in the history
- [ ] Evidence items: file, link, note, or attestation, with owner, collected date, period covered, valid-until, and data class
- [ ] Links from one item to any number of controls, tests, requirements, and issues
- [ ] Freshness: stale evidence stays and stops counting; evidence near its date appears on its owner's Home

**Acceptance:** an uploaded HTML or SVG file cannot run in the app's origin; a person who cannot see a control cannot download its evidence.

### Slice 5: Assessments and tests ☐

**Goal:** test once.

- [ ] Assessments over a scope, against a framework, a baseline, or a chosen set, with a lead and a period
- [ ] The test queue; procedure, method, sample, evidence, and a result for design and for operation
- [ ] Independence: not the control's owner; reviewed by a second person before it counts
- [ ] A counted result becomes the control's rating with the basis *test*, and flows to requirements, scopes, and risks
- [ ] Readiness in five states with reasons, per scope and framework; gaps

**Acceptance:** recording one result changes the control, each mapped requirement in each relying scope, and each linked risk's suggestion, and a test proves all three.

### Slice 6: Issues and exceptions ☐

**Goal:** what is wrong, who is fixing it, and by when.

- [ ] The issue register with sources; severity clocks from the program; ISS references
- [ ] Actions on issues, reusing the action model from treatment
- [ ] Proposed closure with evidence, confirmed by someone else; root cause on closing
- [ ] Exceptions: requested, decided by someone with authority who did not ask, time-limited, renewable; the covered item shown as excepted
- [ ] The plan of action view for a scope
- [ ] In-app notices

**Acceptance:** a failed test opens a prefilled issue; an owner cannot confirm their own closure; an expired exception returns its item to its underlying state.

### Slice 7: Import and export ☐

- [ ] CSV and JSON export of every list, with the filters in force, recorded in the history
- [ ] Spreadsheet import for each record type: column mapping, dry run, every problem by row
- [ ] External references on records

**Acceptance:** an exported list re-imports unchanged into an empty installation.

### Slice 8: Dashboard, graph, and demo ☐

- [ ] Readiness by scope and framework, stale evidence, and issues by age on the dashboard, each figure opening its list
- [ ] The dependency graph around any record, with a list beside it that says the same thing
- [ ] An organization-wide history view for those who read everything
- [ ] The demo: the clinical systems under the health security rule, the controlled-access data enclave, central information technology as a provider, an assessment in progress, evidence going stale, issues at every stage

**Acceptance:** every wave 2 screen has data worth reading in the demo; the graph is usable by keyboard and its list is complete.

### Slice 9: Release prep ☐

- [ ] Guides: compliance (frameworks, scopes, readiness), evidence and testing, issues and exceptions; the existing guides brought up to date
- [ ] The accessibility audit over every new screen
- [ ] Upgrade from 0.1.0 checked: every row kept
- [ ] Dependency review; version `0.2.0`; pull request, tag, release

## Notes

Decisions and discoveries made during the wave are logged here, newest last.

- **Published requirements are recorded by their framework, not row by row.** Loading SP 800-53 writes a thousand rows of content that is the same in every installation. The history holds one event for the framework, with a digest of what was loaded, and not a thousand. A change to a requirement of one of the organization's own frameworks is its own record, and each is an event that says what the text was and what it became.
- **A statement is carried as the publication prints it.** The machine-readable catalogs hold a statement as nested parts with placeholders for parameters. A pack renders them as the document does: lettered and numbered items a line each, and `[Assignment: organization-defined frequency]` where the organization is to choose. Withdrawn entries are left out.
- **A heading is not a requirement.** Families, functions, sections, and paragraphs that only introduce others are kept in the tree and marked as headings, so that nothing is mapped to "Implementation specifications:".
- **The regulation is read from its paragraphs.** The Security Rule arrives as flat paragraphs marked (a), (1), (i), (A). The builder rebuilds the tree from the marks, takes titles from the italic leads, and tells standards from implementation specifications by what the text itself says.
- **A requirement is addressed by a query, not a path.** Codes such as `164.308(a)(1)(ii)(A)` and an agreement's `A/1` do not belong in a path, so one requirement is `…/requirement?code=`.
- **The terms check can allow a word in a named file.** A word on the private list that is also ordinary English appears once in a publisher's own text. The list, which is not in the repository, can now say that a term is allowed in particular files; it is refused everywhere else, including commit messages.
