# Wave 3: Keeping watch (v0.3.0)

**Goal:** a register that stays true without a central team chasing it. Waves 1 and 2 made a register worth keeping. Wave 3 makes it keep itself: people sign in with the identity they already have, the app knows what is due and says so, owners are asked on a schedule to confirm what they own, and anything on record can be found.

**Branch:** `wave-3` · **Target version:** `0.3.0` · **Status:** ◐ in progress

The security team comes first here as everywhere ([roadmap](../roadmap.md#whose-work-comes-first)). In this wave that means: sign-in under the organization's own multi-factor authentication and offboarding, test and evidence cadences that follow from what a control protects, and attestation that is never mistaken for a test.

## Exit criteria

The wave is done when, on a fresh checkout:

1. A new installation signs in with local accounts and nothing else, exactly as before. Naming an OpenID Connect issuer and a client turns single sign-on on beside them; it works with Microsoft Entra ID and with any standards-based provider; the provider's application roles or groups give roles here, with unit scopes; and a local administrator can always get in (PLT-13).
2. One process runs each daily job exactly once: it opens what is due, reminds, escalates, and marks what has lapsed (OVS-01, OVS-03).
3. How often risks are reviewed, controls tested and attested, and evidence renewed is one table keyed by rating and criticality; a key control's cadence is shorter; each control shows its next test date (OVS-02, CTL-10, AST-07).
4. Notices go by email through an SMTP server the administrator names, as they happen or as a digest, by each person's choice; nothing is sent until that is set up (OVS-05).
5. A questionnaire is a versioned document whose questions appear by condition, evaluated the same way by the server and the browser; answers display as they were asked (OVS-07).
6. A campaign asks a set of people to do one thing by a date, with tracking, reminders, and coverage by unit: re-assess risks and controls, attest that controls still operate, complete a unit's records, or supply a named piece of evidence (OVS-04, RSK-12, CTL-09, EVD-05).
7. An attestation and an independent test are shown as different kinds of assurance, and a rule says which a readiness figure may rest on (AST-08).
8. An indicator has thresholds, readings over time, and a trend, is linked to the risks it warns of, and raises a notice when breached (RSK-13).
9. One search finds any record its searcher may see; a filtered list can be saved and shared; each record shows which expected facts are missing; likely duplicates are suggested; disabling an account lists what the person owned and reassigns it in one step (INV-10, INV-12, ISS-08, OVS-08).
10. Program staff edit the taxonomy, the scales and matrix, appetite, cadences, and vocabularies in the app, and see which risks would change rating or standing before publishing; a structured assessment over a scope walks its assets and threats (RSK-14, RSK-15).
11. The role-by-route matrix covers every new route; the demo has something worth reading on every new screen; the accessibility audit passes over them.

## Slices

### Slice 1: Single sign-on ☑

**Goal:** people sign in with the identity they already have, and nobody has to.

Local accounts stay the default and are never removed: an evaluation or a small team needs nothing else installed. Single sign-on is something an administrator turns on.

- [x] `[sso]` in the configuration file: an issuer and a client turn it on; the client secret is read from the environment and refused in the file
- [x] The OpenID Connect client: discovery, the authorization-code flow with PKCE, `state`, and `nonce`; sign-in state kept server-side, used once, short-lived, and bound to the browser that began it
- [x] ID token verification over the standard library: RS256 signature against the provider's published keys, issuer, audience, expiry, and nonce; keys fetched again once when a token names one not yet seen
- [x] Microsoft Entra ID: a tenant's own issuer (the shared issuers that accept any directory are refused); application roles (the `roles` claim) or groups
- [x] `identity`, `provider_mapping`, `sign_in_request`; accounts linked by issuer and subject, joined to an existing account by a verified address, created at first sign-in unless that is turned off
- [x] Mappings kept in the app: a value of the claim gives a role, with a unit and, for a leader, an acceptance limit, or membership of a unit. Mapped roles are replaced at every sign-in; roles granted here are left alone; the last administrator is never removed
- [x] The sign-in page offers both ways; local sign-in can be limited to accounts that already have a password, and never turned off for an administrator
- [x] Admin → Single sign-on: what is set up, the address to give the provider, a check that the provider answers, and the mappings
- [x] `riskwren doctor` checks the provider and the secret; the guide walks through Entra ID and a generic provider

**Acceptance:** with nothing configured, no route or page mentions single sign-on and local sign-in is unchanged. Against a provider run inside the tests: a first sign-in creates an account with the mapped roles; removing the group removes the role at the next sign-in and leaves local grants alone; a token with a wrong signature, issuer, audience, nonce, or an expired one is refused; an answer replayed, or brought to another browser, is refused.

**Done:** single sign-on is off in a new installation and nothing mentions it: `/meta` says nothing of it, the round trip answers 404, and the sign-in page is the password form it always was. Naming an issuer and a client under `[sso]` turns it on beside local accounts. The client reads the provider's discovery document and keys, remembers both for an hour, and fetches the keys again once when a token names one it has not seen. The round trip is the authorization-code flow with PKCE; its state is kept server-side as a hash, used once, dropped after ten minutes, and bound by a cookie to the browser that began it. The ID token is verified over the standard library alone: an RS256 signature by integer arithmetic against the published key, then issuer, audience, expiry, and nonce. A person is known by issuer and subject; joined to an existing account by an address the provider vouches for; created otherwise, unless that is turned off. Mappings are kept in the app and give a role for the whole organization or a unit, a leader's limit, or membership; mapped roles are replaced at every sign-in and marked as the provider's, hand-given roles are untouched, and the last administrator is kept. A missing claim takes mapped roles away, except where the provider says the list was too long to send. Passwords stay for everyone or for administrators only. Admin → Single sign-on shows the connection and checks it; `doctor` does the same. `tests/test_sso.py` holds the acceptance tests against a provider run inside the tests, which is also `scripts/dev_identity_provider.py` for trying it on a laptop. The whole flow was also walked in a real browser against that provider.

### Slice 2: Schedules and email ☑

**Goal:** the app knows what is due, and says so.

- [x] The job scheduler: daily jobs, each run by exactly one process, with what ran and what it did on record
- [x] Cadences as one table keyed by rating and criticality; key controls; the next test date on a control
- [x] Reminders, then escalation to the steward and the leader, on a schedule the program sets
- [x] SMTP delivery, off until set up; as it happens or a daily digest; each person's preferences

**Acceptance:** two servers on one database run a job once between them; an overdue action reminds its owner and later their steward; with no mail server, nothing is attempted and nothing is lost.

**Done:** four jobs run inside the server: the calendar, reminders, email, and housekeeping. A process claims a job's row before running it, with a lease that lapses if the process dies, so several workers, several servers, and `riskwren jobs run` from a scheduled task run each job once between them; what is due comes from the database and the clock, so a restart catches up. Runs that did something, and failures with their reason, are kept for ninety days. Admin → Scheduled work shows each job and can run or pause it; `riskwren jobs` does the same. Reminders look at everything with a date: actions, risk reviews, issues, evidence, acceptances, exceptions, and control tests. Whoever it waits on is told two weeks ahead and the day after; actions and issues that stay late go to the unit's steward after a week and its leader after three. Each stage is said once for a given date, moving the date starts again, and something found long overdue is told once at the stage it has reached. The three periods and the shorter cadence for key controls are in the program's cadences; a control shows when its next test is due. Email is optional: with `[mail]` set, notices go to an outbox in the database and are sent from there, each as it happens or as a daily summary by each person's choice, with retries and a limit, and nothing written before email was set up is ever sent. Editing the cadence table in the app waits for slice 7 with the other program editors. Acceptance tests are in `tests/test_schedule.py` (two connections to one database run a job once between them; an action reminds its owner, then the steward, then the leader) and `tests/test_mail.py`, which sends over real SMTP to a server inside the test (with no mail server, nothing is attempted and nothing is sent later).

### Slice 3: Questionnaires ☑

**Goal:** questions as data, asked the same way everywhere.

- [x] Questionnaires as versioned documents of sections and questions with conditions
- [x] One condition evaluator, in Python and in JavaScript, held together by shared test cases
- [x] Answers kept with the version they were given under

**Acceptance:** the same cases pass in both evaluators; an answer still reads as asked after the questionnaire changes.

**Done:** the condition language of the engine document is `riskwren.core.conditions`: `all`, `any`, `not`, and thirteen comparisons over named fields, as plain data; a malformed condition is refused with what is wrong and where. Its twin in the browser is `js/core/conditions.js`, and both pass the 64 cases in `tests/fixtures/conditions-cases.json`. A questionnaire is a key, a purpose, and versions; a version is a document of sections and questions (yes or no, one or any of a list, text, a number, a date), each of which may carry a rule over earlier answers. A document is checked whole: keys, kinds, options, and that every rule is well formed and looks only backwards. Which questions show, and which answers count, is `showing`, on the server and in the browser, held together by 21 shared cases; an answer to a question that has become hidden is dropped. Saving a changed document publishes a new version and leaves the others alone; a response records its version and is read through it, as the questions and options stood then; a draft is finished under the version it was begun under. Four questionnaires are built in and loaded at `init` and on upgrade; one the organization has edited is left alone by later releases. Admin → Questionnaires lists them; each has a form to try that reacts as it is filled in, an outline with every rule in words, its versions, and a structured editor. The acceptance tests are `tests/test_conditions.py` with `tests/js/conditions.test.mjs`, and `tests/test_questionnaires.py::test_a_change_is_a_new_version_and_an_answer_reads_as_it_was_asked`. Who is asked what, by when, is the next slice: nothing sends a questionnaire to anyone yet.

### Slice 4: Campaigns ☑

**Goal:** ask the owners, by a date, and see who has answered.

- [x] Campaigns: a set of people, one thing to do, a date, tracking, reminders, and coverage by unit
- [x] Risk and control self-assessment; control attestation; unit completeness; evidence requests
- [x] Attestation as a basis of assurance, shown apart from a test, with a rule for what readiness may rest on

**Acceptance:** an attested control is never shown as verified; a campaign's coverage by unit matches the list behind it.

**Done:** a campaign (`CMP`) has a kind, a questionnaire pinned at the version in use when it starts, a date, and what it is about: a unit and everything beneath it or, for controls, what a scope uses. Starting one lists everything it is about, each with whoever is asked (an owner before a delegate; a unit's steward), and tells each person once with a count. Something with nobody to ask is listed and shown as such. Any owner of the thing may answer; answers are a questionnaire response, saved as a draft or sent. Sending has its effect: an attestation is recorded on the control; a control that does not operate, an owner who should be someone else, a risk that no longer stands or is wrongly rated, and a unit whose records need attention are each told to those who must act. An evidence request has no questions and closes when evidence collected after it was made is attached to its control, which the scheduler notices. A campaign's page gives progress, outcomes, coverage by unit with the least covered first, and every item; it can remind, excuse an item with a reason, close, or be cancelled. Pending items are on each person's Home and in the scheduled reminders, which go up to the steward and the leader. Attestation is a basis of assurance of its own: it is shown on the control apart from the rating, it never produces verified, and a negative one given after a test takes the control's requirements out of verified, with the reason in words. The acceptance tests are `tests/test_campaigns.py::test_an_attested_control_is_never_shown_as_verified` and, in `test_a_campaign_asks_the_owners_and_tracks_who_has_answered`, coverage by unit checked against the list behind it. The demo has a closed risk self-assessment, a control attestation most of the way through, and an evidence request just made.

### Slice 5: Indicators ☑

**Goal:** early warning.

- [x] Indicators with thresholds, readings, and a trend, linked to risks
- [x] A breach raises a notice and flags the risks it warns of

**Acceptance:** a reading past its threshold notifies the indicator's owner and shows on each linked risk.

**Done:** an indicator (`IND`) is a record like any other, with owners, a unit, and history: what it is counted in, which way is worse, an optional warning level, a limit, how often it is read, and where it is read from. Nothing is fetched: a reading is recorded by an owner or the unit's steward, one for a day, and a second for the same day corrects the first with both kept in the history. Each reading is placed against the levels, and the indicator carries its latest value and state. The trend is worse, better, or steady from the newest readings, where a move of less than a twentieth of the distance between the warning level and the limit is steady. An indicator is linked to the open risks it warns of. When the newest reading passes the limit, the indicator's owners and the owners of each linked risk are told once, each assessed risk is marked as having its rating in doubt with the indicator as the reason, and the risk's page shows the indicator under Early warning. The indicator's page charts its readings against both levels as an inline drawing with a table beneath it. A reading falling due is on Home and in the scheduled reminders, only as it falls due and without going up to the steward. The risk dashboard counts indicators by where they stand; the list filters by where each stands and exports. The acceptance test is `tests/test_indicators.py::test_a_breach_tells_the_owner_and_shows_on_each_risk_it_warns_of`. The demo has eight indicators with up to fifteen months of readings: one past its limit this month, several past their warning level, one improving, one two quarters overdue, and one never read.

### Slice 6: Find and tidy ☑

**Goal:** anything on record can be found, and kept in order.

- [x] Search across every record type, cut to what the searcher may see; saved and shared views
- [x] Completeness on each record; likely duplicates suggested, for records and for new issues
- [x] Reassigning what someone owned when their account is disabled

**Acceptance:** a search never returns a record its searcher could not open; disabling an owner leaves nothing without one.

**Done:** the search (`riskwren.inventory.find`) asks each kind's own list for what matches, so what a person may find is decided by the one rule every list already uses; it adds actions, ranks each kind's matches (a reference, the whole name, the start of a name, the start of its words, anywhere in the name, elsewhere on the record), and puts the kind with the best match first. A list's search now needs every word, in any order. It is in the command palette as records under the pages, and on a page of its own. A saved view is a list's path and its filters under a name, private unless someone who looks after a list shares it; it holds no rows. Completeness is one condition per expected fact, used to say what a record lacks, to filter any list (`missing=`), and to count, so a count is always the length of its list; only records still in use are counted, and a summary is not expected, because a rule nearly every record fails tells nobody anything. Likeness between names is the same words in any order or nearly the same spelling, stricter across units than within one; it is offered as a name is typed for the inventory, risks, controls, and issues, and listed as pairs, which someone who can edit either may dismiss. Disabling an account passes what the person alone answered for (records, open actions, active treatment plans, and pending campaign items) to the nearest steward, then leader, then a manager, tells them, and keeps a note of each thing until someone is named for good; a page lists what a person holds and passes it on in one step, for an administrator or a steward in their own units. Reports → Tidy brings the three together. The acceptance tests are `tests/test_tidy.py::test_a_search_never_returns_a_record_its_searcher_could_not_open`, which opens every result as each of the seven roles, and `test_disabling_an_owner_leaves_nothing_without_one`.

**Not done:** merging two records into one (INV-12 asks for it, keeping both histories). A record is referred to by type and id from too many places to move them all safely in this slice: links, owners, risk and control links, scopes, evidence, issues, campaign items, and indicators. Duplicates are found and shown, and a person retires one by hand. Merging is carried to a later wave.

### Slice 7: Program editors ☑

**Goal:** the program is edited where it is used.

- [x] Editors for the taxonomy, scales and matrix, appetite, cadences, and vocabularies
- [x] An impact preview: the risks whose rating or standing would change
- [x] Structured risk assessments over a scope

**Acceptance:** publishing a changed matrix changes exactly the risks the preview listed.

**Done:** one function, `riskwren.risk.program.change`, changes the scoring method, appetites, or cadences and returns every open risk whose ratings, standing, or next review moved. A preview is that function run and then rolled back, so it lists what publishing would change by doing it; nothing of it is kept, not an event. Publishing a method makes a new version and reads every open risk again from the matrix in force, then its standing and its next review; each assessment keeps the rating it was given and its version, and a risk the program moved says so in its history with the lines that changed. Loading a program pack settles the register the same way, which it did not before. A method is refused if it removes or re-keys a rating, or has fewer levels than risks are rated at; cadences are checked whole, each problem against the part it is in. Categories are added (two deep), renamed, ordered, and retired. A vocabulary is renamed, ordered, added to, and retired, never re-keyed; lists the software gives meaning to (severities, kinds of link, control frequencies, owner kinds) can only be renamed, and a value new records start with cannot be retired. Admin → Program has a tab for each, with a draft bar and a preview dialog for what can move a risk. A structured risk assessment is a **risk analysis** (`RAN`), so named because "assessment" already means a judgment of one risk and the testing of controls. It is over a scope's boundary, units included, or over what a unit holds, against the library risks of chosen categories: one question for each thing against each threat, made when it starts. Each is answered as not applying, as covered by a risk on the register (which then says it concerns the thing, and may be put in doubt), or by raising a risk from the library for the thing's owner. It closes when every question has an answer and with what it found; its report keeps the names of the day. The acceptance test is `tests/test_program_editing.py::test_publishing_a_changed_matrix_changes_exactly_the_risks_the_preview_listed`; the analysis is covered by `tests/test_analysis.py`.

**Not done in the app:** who may accept what, the number of levels and ratings, and how much a control may reduce a rating. They are changed with a program pack, where everything that names a rating can be changed together.

### Slice 8: Release prep ☐

- [ ] Guides, changelog, upgrade from 0.2.1 on both databases, audits, release, and the site republished

## Notes

- Single sign-on follows [ADR-0008](../decisions/0008-accounts-and-single-sign-on.md), amended in slice 1: the mappings are kept in the app and not in the configuration file, so that whoever administers RiskWren can change them without a restart or access to the server.
