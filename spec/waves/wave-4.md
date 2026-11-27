# Wave 4: Policy and obligations (v0.4.0)

**Goal:** the governance in governance, risk, and compliance: what the organization has said it will do, and what it has promised others. Waves 1 to 3 made a register that knows what could go wrong, what must be complied with, and keeps itself current. Wave 4 adds the organization's own word: its policies, standards, procedures, and guidelines, read and acknowledged by the people they apply to; the agreements that bind it; the frameworks as they change; and the objectives and committees the register serves.

**Branch:** `wave-4` · **Target version:** `0.4.0` · **Status:** ◐ in progress

The security team comes first here as everywhere ([roadmap](../roadmap.md#whose-work-comes-first)). In this wave that means: the information security policy and the standards beneath it, approved by named people and never altered once published; an acceptable use policy that every member of staff acknowledges and that the security team can show they have; documents tied to the controls they direct and the requirements they answer, so that "is there a policy for this?" has an answer with a date on it; data use agreements whose security terms reach the systems that hold the data; and new versions of the security frameworks loaded beside the old, with what changed.

## Exit criteria

The wave is done when, on a fresh checkout:

1. Policies, standards, procedures, and guidelines are records with an owner and a unit, arranged so that each names the document it implements; a document's text is held here, or is a link to where the organization already keeps it, or is a file; its lifecycle is tracked here either way (POL-01, POL-07).
2. A draft is reviewed and approved by people named for it, none of them its author, before it is published; a published version is never altered; any two versions can be compared with the differences marked (POL-02, POL-08).
3. Each document has a next review date from a cadence the program sets; a review that is due or overdue shows on the document, on its owners' Home, and in the reminders (POL-03).
4. Anyone signed in finds and reads the published documents that apply to them, on a phone as well as at a desk; people are asked, by unit or role, to acknowledge a version, and who has and has not is tracked (POL-05, POL-06).
5. A document shows the controls it directs and the requirements it answers; an exception may be to a document (POL-04, ISS-06).
6. An agreement is a record with its parties, its dates, what it covers, and the requirements it imposes, with a warning before it ends (CMP-12).
7. A new version of a framework is loaded beside the old; the app lists what was added, changed, and withdrawn, and which controls and scopes it affects; a publisher's mapping between two frameworks suggests crosswalks a person confirms (CMP-10, CMP-11).
8. Strategic objectives are records that risks name; a committee session has an agenda, the decisions taken on each item, and minutes (RSK-16, OVS-09).
9. The role-by-route matrix covers every new route; the demo has something worth reading on every new screen; the accessibility audit passes over them.

## Slices

### Slice 1: Policy documents ☑

**Goal:** the organization's own word, with its versions, its approvals, and its review dates.

- [x] Documents (`POL`) of four kinds, policy, standard, procedure, and guideline, each implementing one of its own kind or a broader one; an owner, a unit, and a review cadence
- [x] Versions: a draft is written here (formatted text), linked to where it is kept, or attached as a file; a change note says what changed and why
- [x] Approval: the draft is sent to named people, none of them its author; each approves or returns it with a reason; once all have approved, it can be published
- [x] Publishing: a published version is numbered and never altered; its text is fingerprinted in the history, and `riskwren verify` checks it still matches; the version it replaces is superseded
- [x] Review: a next review date from the program's cadence; a review that leaves the document as it is, or a new draft; due and overdue reviews on Home and in the reminders
- [x] Comparing any two versions of the text, side by side, with the differences marked
- [x] Policies → Documents; a document's page with its text, its versions, the draft and its approvals, and its history; the demo's security policies and the documents beneath them

**Acceptance:** a draft cannot be published until every person named for it has approved, and its author cannot be one of them; once published, no route changes it; the history's fingerprint of every published version matches what is shown.

**Done:** a document (`policy_document`, `POL`) is a record with a kind, the document it implements (its own kind or a broader one, never a narrower one, and never beneath itself), a unit, owners, and an optional review cadence of its own. Its words are in `policy_version` rows: a draft, one in review, one approved, the one published, and those superseded or discarded. A version is text in a small Markdown, a link, or a stored file; its fingerprint is the digest of what it says. The text is not copied into the history: the publishing event carries the fingerprint, and `riskwren verify` checks every published version against it and against its file. A document is added and changed by its owners or by the steward, leader, or manager of its unit. A draft is sent to between one and ten named people who may see the document, none of whom started or sent it; each approves it, or returns it with a reason, which cancels the rest of that round; sending it again starts a new round. When every approval is in it is approved, and an editor publishes it: it is numbered from 1, supersedes the one before, and sets the next review from that day. There is no route that changes a published version. A review keeps the version in force and moves the next review on, with what was looked at kept in the history; the program's cadence, `document_review_months`, is 12 as shipped and is edited with the others, which moves every document that follows it. Two versions are compared line by line, a reworded line paired with the most like it, and word by word within it. Approvals, publishing, rework, and reviews are on Home; reviews are in the reminders and go up to the steward and the leader. In the browser the Markdown is read into plain objects and built with the DOM helper, so nothing written in a document becomes markup. The demo has eleven documents beneath its information security policy, among them a new version of the policy waiting for the president, a guideline returned to its author, a procedure kept on the intranet, a policy kept as a PDF, and a standard overdue for review. The acceptance test is `tests/test_documents.py::test_a_draft_is_published_only_once_everyone_named_has_approved_it`, with `test_what_was_published_is_never_changed`, which alters a version in the database and finds it reported.

### Slice 2: Library and acknowledgment ☐

**Goal:** everyone can read what applies to them, and say they have.

- [ ] Who a document applies to: everyone, or units and roles
- [ ] The library: the published documents that apply to the reader, searched by their words, readable on a phone
- [ ] Acknowledgment: a person confirms they have read a version; a version can say it must be acknowledged again
- [ ] Acknowledgment campaigns by unit and role, with tracking, reminders, and coverage by unit

**Acceptance:** who has and has not acknowledged a version is exactly the people it applies to, split by whether they have; a new version that must be acknowledged again asks everyone again.

### Slice 3: Policies in the web of records ☐

**Goal:** a document is connected to what it governs.

- [ ] A document directs controls and answers requirements, shown on each side
- [ ] Exceptions to a document, decided and ending like the others
- [ ] Documents in the picture of connections, in search, in what records are missing, and in exports

**Acceptance:** a requirement shows the published documents that answer it, and a document the controls it directs; an exception to a document ends by its dates.

### Slice 4: Agreements ☐

**Goal:** what the organization has promised others, with dates.

- [ ] Agreements (`AGR`): awards, data use agreements, contracts, and the like, with their parties, dates, and notice periods
- [ ] What an agreement covers: systems, information, and scopes; the requirements it imposes, as a framework of its own
- [ ] A warning before an agreement ends, and before its notice date

**Acceptance:** the requirements an agreement imposes appear in each scope that holds what it covers; its owners are warned before it ends.

### Slice 5: Framework updates ☐

**Goal:** a framework changes, and the program follows it without starting again.

- [ ] A new version of a framework loaded beside the old
- [ ] What was added, changed, and withdrawn; which controls, scopes, and exceptions it affects
- [ ] Moving a scope to the new version, with the mappings carried across where the code is unchanged
- [ ] A publisher's mapping between two frameworks as suggested crosswalks a person confirms; further framework packs

**Acceptance:** loading a new version leaves every scope on the old one exactly as it was until it is moved; the list of what changed matches the two versions.

### Slice 6: Objectives and sessions ☐

**Goal:** the register serves the organization's aims and its committees.

- [ ] Strategic objectives as records; a risk names the objectives it threatens, and each objective shows its risks
- [ ] Committee sessions: an agenda of items drawn from the register, the decision taken on each, and the minutes

**Acceptance:** an objective's risks are exactly those that name it; a decision recorded in a session shows on the record it was about.

### Slice 7: Release prep ☐

- [ ] Guides, changelog, upgrade from 0.3.0 on both databases, audits, release, and the site republished

## Notes

- The record type is the **document** (`POL`), so that a standard or a procedure is not called a policy. The section of the app is still **Policies**, as people say.
- A published version is a statement by the people who approved it, and like every judgment here it is never edited. A correction is a new version.
