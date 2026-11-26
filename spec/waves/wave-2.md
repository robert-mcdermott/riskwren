# Wave 2: Compliance (v0.2.0)

**Goal:** test once, satisfy many. One set of controls answers every framework the organization is held to, and readiness against each is worked out from tests and evidence, never typed in. Wave 1 answered "what could go wrong, and what are we doing about it?" Wave 2 answers "what are we held to, and can we show that we meet it?" with the same controls.

**Branch:** `wave-2` · **Target version:** `0.2.0` · **Status:** ☑ released

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

### Slice 2: Crosswalks ☑

**Goal:** one control, many requirements.

- [x] `control_requirement` with coverage (full, partial), a note, and its source (pack or person)
- [x] Mapping from either end: a control's requirements, a requirement's controls
- [x] The starter controls' crosswalk to the built-in frameworks, shipped with the control library and applied when a control is adopted
- [x] Coverage of a framework: requirements with and without controls

**Acceptance:** a control adopted from the library arrives mapped; coverage figures open the requirements they count.

**Done:** a control has a Requirements tab, framework by framework; a requirement shows its controls and how well each is known to work. Twenty-seven of the starter controls carry 156 suggested mappings to the four built-in frameworks, each code checked against the packs by a test. A control started from the library arrives mapped, and one adopted before its framework was loaded is offered the suggestions. Each framework shows how many of its requirements have a control, and the ones with none are a filter away.

### Slice 3: Scopes and inheritance ☑

**Goal:** a boundary, what it must meet, and who does what inside it.

- [x] `scope` with members (units, processes, systems), frameworks and baselines, an owner; SCP references
- [x] Applicability per requirement with reasons; a baseline as the starting point
- [x] Implementations: status, responsibility, how it is done here
- [x] Offering and inheriting controls, fully or shared; the inheriting scope cannot rate what it inherits
- [x] The statement of applicability, printable
- [x] Information assets as a fourth kind of inventory record (INV-07)

**Acceptance:** the demo's enclave inherits identity and backup controls from central computing and shows their state; excluding a requirement without a reason is refused.

**Done:** a scope is a record like any other, with owners, history, and the register's visibility. It lists what is inside it, is held to frameworks from a baseline or from every requirement, and decides applicability a requirement at a time; a reason is required to leave one out. Each control it uses has an implementation. A scope that offers its controls can be inherited from, whole or shared, and the inheriting scope sees whose control it is and how well it is known to work, even where it could not open the control itself. The Requirements tab is the statement of applicability and prints as one. Information assets are the fourth kind of inventory record, linked to the systems that hold them and the parties they are shared with. The demo has a provider, a clinic under the health security rule, and a data enclave.

### Slice 4: Evidence and files ☑

**Goal:** proof, collected once.

- [x] Content-addressed file storage in the data home; size and type limits checked by content; downloads as attachments under a locked-down policy, recorded in the history
- [x] Evidence items: file, link, note, or attestation, with owner, collected date, period covered, valid-until, and data class
- [x] Links from one item to any number of controls and scopes; tests and issues join them in the slices that add them
- [x] Freshness: stale evidence stays and stops counting; evidence near its date appears on its owner's Home

**Acceptance:** an uploaded HTML or SVG file cannot run in the app's origin; a person who cannot see a control cannot download its evidence.

**Done:** files are stored under the SHA-256 of their bytes in the data home, in a directory nothing serves from; their kind is judged by content, and only a short list is taken. A file leaves only as an attachment, under a policy that allows nothing, and every download is an event. An evidence item is a file, a link, a note, or an attestation with a collection date, the period it covers, and a date it holds until, a year by default. It is attached to as many controls and scopes as it supports, and anyone may collect it for a unit they work in. Its owner is reminded on Home a month before it stops counting.

### Slice 5: Assessments and tests ☑

**Goal:** test once.

- [x] Assessments over a scope, against a framework (and so its baseline in that scope) or a chosen set, with a lead and a period
- [x] The test queue; procedure, method, sample, evidence, and a result for design and for operation
- [x] Independence: not the control's owner; reviewed by a second person before it counts
- [x] A counted result becomes the control's rating with the basis *test*, and flows to requirements, scopes, and risks
- [x] Readiness in five states with reasons, per scope and framework; gaps

**Acceptance:** recording one result changes the control, each mapped requirement in each relying scope, and each linked risk's suggestion, and a test proves all three.

**Done:** an assessment is a record (`ASM`) of a scope, started by an assessor or a manager, which plans a test for each control the scope does itself: all of them, those that answer an applicable requirement of one framework, or a chosen few. Each test has a method, a procedure, and a person it is assigned to, and appears on that person's Home. A result gives design and operation, what was looked at, what was found, and the evidence it cites. It is recorded by someone who does not own the control and counts once a second such person confirms it; a returned result is recorded again, and the earlier one is kept. A confirmed result becomes the control's rating on the basis of a test, which a judgment cannot overrule while it holds. Readiness is now worked out in five states, each control's with its reason in words, and a failing test shows in the scope that does the control and in every scope that inherits it. `tests/test_assessments.py::test_one_result_moves_the_control_every_scope_that_relies_on_it_and_every_risk` is the acceptance test. A failed test opening an issue waits for slice 6, where issues arrive.

### Slice 6: Issues and exceptions ☑

**Goal:** what is wrong, who is fixing it, and by when.

- [x] The issue register with sources; severity clocks from the program; ISS references
- [x] Actions on issues, reusing the action model from treatment
- [x] Proposed closure with evidence, confirmed by someone else; root cause on closing
- [x] Exceptions: requested, decided by someone with authority who did not ask, time-limited, renewable; the covered item shown as excepted
- [x] The plan of action view for a scope
- [x] In-app notices

**Acceptance:** a failed test opens a prefilled issue; an owner cannot confirm their own closure; an expired exception returns its item to its underlying state.

**Done:** an issue is a record (`ISS`) with a severity, what found it, and what it is about: controls, scopes, risks, and requirements. Its date follows from its severity by a table in the program (30, 90, 180, and 365 days), counted from the day it was raised; moving it needs a reason, and every move is kept. A confirmed test result of partly effective or ineffective opens one, filled in from the result, owned by the control's owners, and naming every scope that relies on the control. Anyone may raise one for a unit they work in. It is worked through the same actions treatment plans use, which now belong to a plan or an issue. Its owner proposes closure with what was done, a root cause, and evidence; an assessor or manager who neither owns it nor proposed it confirms or sends it back. An exception (`EXC`) is asked for by whoever keeps the scope or control, to a control or to a requirement within a scope, runs between two dates at most a year apart, and is decided by a leader or manager over the unit who did not ask. While it is in force a weak state is shown as excepted with what lies underneath; the day after, the state underneath is back. A scope has a plan of action tab that prints. Each person has notices with a count in the top bar. The acceptance tests are in `tests/test_issues.py`: `test_a_failed_test_opens_an_issue_filled_in_from_the_result`, `test_an_issue_is_closed_only_by_someone_who_does_not_own_it`, and `test_an_exception_is_decided_by_someone_else_and_ends_by_itself`.

### Slice 7: Import and export ☑

- [x] CSV and JSON export of every list, with the filters in force, recorded in the history
- [x] Spreadsheet import for each record type: column mapping, dry run, every problem by row
- [x] External references on records

**Acceptance:** an exported list re-imports unchanged into an empty installation.

**Done:** every list has an Export button that gives it as CSV or JSON, filtered as the page is and cut to what its reader may see; each export is an event saying who took which list, how many rows, and under what filters. Processes, systems, third parties, information, risks, and controls import from a CSV: the file's columns are matched to fields by their headings, the person corrects the matching, a dry run reports every problem by row, and nothing is added unless every row can be. Each row goes through the service that adds a record by hand. A framework of the organization's own takes its requirements from a CSV the same way. A record can carry what it is called in other systems, is found by those names, and shows them as links where the system has an address pattern. `tests/test_exchange.py::test_an_exported_list_reimports_unchanged_into_an_empty_installation` is the acceptance test: systems, processes, controls, and risks leave one installation and arrive in a second with their references, owners, tags, and external references, and the second's export is the first's, byte for byte.

### Slice 8: Dashboard, graph, and demo ☑

- [x] Readiness by scope and framework, stale evidence, and issues by age on the dashboard, each figure opening its list
- [x] The dependency graph around any record, with a list beside it that says the same thing
- [x] An organization-wide history view for those who read everything
- [x] The demo: the clinical systems under the health security rule, the controlled-access data enclave, central information technology as a provider, an assessment in progress, evidence going stale, issues at every stage

**Acceptance:** every wave 2 screen has data worth reading in the demo; the graph is usable by keyboard and its list is complete.

**Done:** a compliance dashboard beside the risk dashboard, for the whole organization or one unit and those beneath it: each scope against each framework it is held to, in the same six states as its statement of applicability; open issues by severity and by how long ago they were raised; the longest overdue; what the controls' ratings rest on (a test that found them effective, one that found them wanting, or none); evidence that still counts and that does not; exceptions waiting, in force, and ended; and assessments in progress. Every figure is the count of a list and opens it; the lists gained the filters that needed (an issue's age, an exception ending soon, a control by what a test found). Every record has a Connections link to a picture of what it is joined to (links, risks, controls, scopes, evidence, issues, exceptions, assessments), with the same in a list beside it; a neighbor can be opened in place or put in the middle, by mouse or keyboard. Those who read everything have a History page of every change, narrowed by person, record, kind, and date. The demo gained a security leader to sign in as and a critical finding from a penetration test. The acceptance tests are in `tests/test_overview.py` and `tests/js/graph-layout.test.mjs`. `scripts/keyboard-check.mjs` drives the picture in a browser with the keyboard alone (opening a neighbor, closing it, putting one in the middle) and counts the list against the answer; it found, and now guards against, the focus being lost when the picture is redrawn. The accessibility audit walks the picture and its list in every palette and mode.

### Slice 9: Release prep ☑

- [x] Guides: compliance (frameworks, scopes, readiness), evidence and testing, issues and exceptions; the existing guides brought up to date
- [x] The accessibility audit over every new screen
- [x] Upgrade from 0.1.0 checked: every row kept
- [x] Dependency review; version `0.2.0`; pull request, tag, release

**Done:** three new guides and the other six brought up to date, with every link and anchor between them checked. The upgrade was run from release 0.1.0's own code and data on SQLite and on PostgreSQL: each of that release's 29 tables kept every row unchanged, the history grew by the upgrade's own events and still verifies, the data home's files were untouched, and the upgraded installation served the new screens. The runtime dependencies are the same five as 0.1.0, and an audit of the locked versions found no known vulnerability. The accessibility audit passes over 98 scenes in three palettes and both modes.

## Notes

Decisions and discoveries made during the wave are logged here, newest last.

- **Published requirements are recorded by their framework, not row by row.** Loading SP 800-53 writes a thousand rows of content that is the same in every installation. The history holds one event for the framework, with a digest of what was loaded, and not a thousand. A change to a requirement of one of the organization's own frameworks is its own record, and each is an event that says what the text was and what it became.
- **A statement is carried as the publication prints it.** The machine-readable catalogs hold a statement as nested parts with placeholders for parameters. A pack renders them as the document does: lettered and numbered items a line each, and `[Assignment: organization-defined frequency]` where the organization is to choose. Withdrawn entries are left out.
- **A heading is not a requirement.** Families, functions, sections, and paragraphs that only introduce others are kept in the tree and marked as headings, so that nothing is mapped to "Implementation specifications:".
- **The regulation is read from its paragraphs.** The Security Rule arrives as flat paragraphs marked (a), (1), (i), (A). The builder rebuilds the tree from the marks, takes titles from the italic leads, and tells standards from implementation specifications by what the text itself says.
- **A requirement is addressed by a query, not a path.** Codes such as `164.308(a)(1)(ii)(A)` and an agreement's `A/1` do not belong in a path, so one requirement is `…/requirement?code=`.
- **A suggested mapping is partial until someone says otherwise.** A plain-words control rarely answers the whole of a requirement that has a dozen parts. The library's mappings arrive marked as suggested and as answering in part; a person who changes one has made it their own.
- **Coverage is not readiness.** A requirement with a control mapped to it is covered, which says nothing about whether the control works. The coverage card says so; readiness, from tests and evidence, comes in slice 5.
- **Coverage follows what its reader may see of controls.** A requirement's controls, and every count of them, leave out controls the reader could not open, and say how many were left out. A retired control answers nothing.
- **Suggestions are offered, not applied behind anyone's back.** Upgrading does not map an organization's existing controls. A control that came from the library shows what the library suggests, and its keeper adds them or not.
- **The demo is built once for the tests that only read it.** A build makes some fifty thousand small statements, which is seconds on SQLite and over a minute against a PostgreSQL container. The tests that only read the demo now share one build; those that are about building it still build their own.
- **A gap is judged by the controls a scope uses.** The first rule called a requirement a gap if any control mapped to it had no implementation in the scope. Where several units each keep their own control for the same requirement, that would make every scope a gap for ever. A requirement is a gap when no control mapped to it is used in the scope; planned when one that is used is not yet in place; in place when all of them are. [engine.md](../engine.md) says so.
- **A decision that matches the starting point is not kept.** Applicability is the baseline plus the decisions that depart from it. Putting a requirement back to where the scope started removes the decision; the history keeps that it was made and unmade.
- **What is inherited whole has no standing of its own.** An inheriting scope cannot say that a control it inherits whole is in place: it stands where the provider's does, and slips the day theirs does. A shared control is as far along as the weaker half.
- **A provider cannot quietly withdraw.** A scope cannot stop offering its controls, or stop using one, while another scope inherits it.
- **Offering a control shows its name and state, and no more.** People in an inheriting scope see whose control they rely on and how well it is known to work without being able to open the provider's record.
- **Requirements carry their place in the document.** Rows are written a level at a time, so the order they were written in is not reading order. Each requirement keeps a sequence number, and every flat list (a search, a baseline, a statement of applicability) is in the order of the source.
- **Markup is taken as text, and leaves as text.** A page or a drawing that carries script is a legitimate thing to keep as evidence of a configuration. It is stored as the plain text it is, returned with a plain-text type as an attachment, under a sandboxed policy with sniffing off, so it cannot run in the app's origin. Programs and unrecognized binary are refused.
- **Evidence is more closely held than the register.** Whoever collected it, those named on it, and those with a role over its unit see it. Others see it only through something it is attached to that they may see, and not at all if it is restricted or of the most sensitive data class. An organization-wide assessor sees what is not restricted.
- **Collecting is open; attaching is not.** Anyone may add evidence for a unit they work in, because the people who do the work hold the proof. Putting it on a control or a scope is for those who keep or assess that control or scope.
- **A record type may set its own visibility.** Evidence needed a rule the shared one could not express, so a record type can now supply its own, used by single records, lists, and counts alike.
- **A scope tests what it does itself.** A control inherited whole or shared is tested where it is provided, once, and the result reaches every scope that relies on it. An assessment of an inheriting scope plans no test for it and cannot be given one.
- **A result waits for a second person.** Recording a result changes nothing. Confirming it does, and the person who confirms is neither the tester nor an owner of the control. Until then the control, its requirements, and its risks stand where they stood.
- **A test outranks a judgment while it holds.** Once a control has a confirmed test result, rating it by judgment is refused until the result is out of date, by the same cadence that makes any rating stale. Otherwise the cheapest way to clear a failing test would be to have an opinion.
- **Verified needs evidence that still counts.** Tested effective is not enough: evidence attached to the control, or cited by the result, must be current. When it goes stale the requirement drops back to in place without anyone touching it, and says why.
- **A reason travels with every state.** Each control in a statement of applicability carries its state and a sentence saying how it got there, so a reader never has to work out why a requirement is not verified.
- **An assessment's history tells its tests.** Planning a test, recording a result, confirming it, and returning it are each told in the assessment's history with the control's name, since they are what an assessment consists of.
- **One issue for one failing control.** A control that fails a second test while its issue is still open does not get a second issue: the first stands, and the test shows it. Once that issue is closed, a later failure opens a new one.
- **A test-raised issue belongs to the control's owners.** Whoever found the weakness is not the one to fix it. If the control has no owner the issue has none either, and shows to the unit's stewards as needing one.
- **Changing the severity sets the date again.** The date is the rule applied to the day the issue was raised, so a change of severity re-applies it and puts aside any date set by hand. The history keeps both.
- **Only the second line withdraws an issue.** An owner who could cancel their own issue would never need its closure confirmed. Withdrawing one raised in error, and reopening one that turned out not to be fixed, are for an assessor or a manager.
- **An issue is known to those with a part in it.** Whoever raised it, those named on it, anyone with an action on it, and those with a role over its unit. Working in the unit is not enough.
- **Actions have a source.** The action table always said where an action came from; the service now does too. A treatment plan and an issue each say who manages their actions and what follows when one changes, and the one list of everything owed shows both.
- **An exception changes how a state is shown, not what it is.** It is worked out on the day from its dates, never by a job that flips a status, so nothing has to run for it to end. It stands in only for failing, gap, or planned, and what lies underneath is always shown beside it.
- **An exception to an inherited control can be asked for where it is felt.** A scope that inherits a failing control cannot fix it, and may need to say so. Its keepers ask within their own scope, by the control's name, without being able to open the provider's record. An exception approved in the provider's scope reaches those that inherit from it.
- **The table is not called what the word means in the language it is written in.** The record type is `exception` everywhere a person or the API sees it; the table and the model are `exception_request`.
- **Notices are pointers, not records.** A notice is a sentence and a place to go, for one person, about something assigned to them or decided for them. It is not in the history, which already holds what happened, and nobody is told about what they did themselves.
- **An import is many additions, not a load.** Each row is given to the same function a person's own addition goes through, in the importer's name, so permissions, validation, defaults, and history are the same and cannot drift. A dry run does all of it and rolls it back.
- **Judgments are not imported.** A file can say what a risk or a control is. What it says of a rating, a standing, or a test is not read: those are made here, by a named person on a date. An export carries them as columns after the ones an import reads.
- **A file's own references are kept when they are free.** An import that brings a `ref` column keeps each reference and moves the counter past it, so a copy of a register refers to the same things by the same names. A reference already in use is a problem on its row.
- **The same file twice adds nothing.** A row whose name is already on record in its unit is a problem, so that an import run a second time is refused whole and not doubled.
- **An export is what its reader could already see.** Anyone may export a list they can open; it applies the same rule as the list and is recorded. Text a spreadsheet would run as a formula is written with an apostrophe before it, which an import takes off again.
- **External references are one small table.** One table for every kind of record, a child of the record in the history, with the system chosen from a vocabulary that may give an address pattern. They are set with the record's other facts and not through routes of their own.
- **The plan of action is loaded when it is opened.** The scope page had reached its size budget; the tab and the issue form now arrive when asked for.
- **The security team comes first.** Said by the project's owner during this slice: the first adopters are chief information security officers and their teams, so their path is to be the best-made part of the product. The compliance dashboard was shaped to that reader, the demo gained a security leader and a finding from a penetration test, Home gained what a test has found wanting and what is late, and the vision and the roadmap now say whose work comes first. No scope was dropped.
- **The dashboard counts lists; it does not keep figures.** Every number is the count of a list under some filters and carries those filters, so it can be opened, and so it cannot disagree with the list. Where a figure needed a filter the list did not have, the list got the filter.
- **Readiness is counted once per scope.** A requirement that three scopes must meet is three things to make ready. The dashboard says so beside the total.
- **The picture is two columns, not a web.** A ring of neighbors looked like a graph and could not hold their names without overlapping. Neighbors are in columns either side of the record, a group at a time, and a neighbor's own neighbors in a column beyond it. What does not fit is counted in the picture and listed in full beside it. The layout is a function of the data alone and has its own tests.
- **The picture and the list are one answer.** Both are drawn from the same response, grouped the same way, so the list is complete by construction and the picture can leave things out without hiding them.
- **The whole history leaves sign-ins out unless asked.** Every change is there, but the page opens on changes to records; sign-ins, exports, and settings are one choice away.
- **The audit must not pass what it did not see.** A guide had called a button by a name the app never used, and the audit scene that pressed it found nothing and passed. A scene whose button is missing now fails, and the guides' links are checked against their headings before a release.
- **What a script writes, the script must hold.** The default program is written by a script, and three slices changed the file and not the script. Nothing was lost, because nobody ran it; the additions are now in the script, which reproduces the file exactly, and a test fails if they part again.
- **The terms check can allow a word in a named file.** A word on the private list that is also ordinary English appears once in a publisher's own text. The list, which is not in the repository, can now say that a term is allowed in particular files; it is refused everywhere else, including commit messages.
