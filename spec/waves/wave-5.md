# Wave 5: Third parties (v0.5.0)

**Goal:** know who the organization depends on, what each can reach, and whether the paper covers it. Waves 1 to 4 made a register of what could go wrong, what must be complied with, and what the organization has said and promised. Its third parties have been names in the inventory since wave 1. Wave 5 makes them a program: what each provides and touches, how much is at stake with each, what they say about themselves and what independent reports say about them, whether an agreement covers what is shared with them, and what happens when a relationship changes or ends.

**Branch:** `wave-5` · **Target version:** `0.5.0` · **Status:** ☐ in progress

The security team comes first here as everywhere ([roadmap](../roadmap.md#whose-work-comes-first)). For a security team, third-party risk is mostly a question of information and access: who holds the organization's restricted information, who can reach its systems, and what independent assurance there is that each is careful. In this wave that means: a tier for each third party set by the program's own rules from what it holds and reaches, with the reasons shown; a security questionnaire, chosen by tier, that the supplier's contact answers through a link without an account; assurance reports read for what they actually cover, with the responsibilities they leave to the organization joined to its own controls; and a stop wherever identifiable health information, controlled-access data, or other regulated information is shared with someone and no agreement of the right kind covers it.

## Exit criteria

The wave is done when, on a fresh checkout:

1. A third party has services as records of their own, each with the systems it reaches and the information it handles (TPR-01).
2. A short set of questions, answered partly from the inventory, sets a third party's tier by the program's rules, with the reasons that applied shown; a person who records a different tier says why, and both are kept (TPR-02).
3. A questionnaire chosen by the tier is sent to a named contact through a link that expires; the contact answers without an account and reaches nothing else; the answers are reviewed, the concerns among them counted, and a conclusion recorded (TPR-03).
4. Assurance reports and certificates are held as evidence with the period they cover and their expiry; a structured review records what was in scope, each exception noted, and each responsibility the organization keeps, joined to the control that meets it (TPR-04).
5. An agreement names the third parties it is with and the services, systems, and information it covers; one that is ending warns its owners (TPR-05).
6. Where regulated information is shared with a third party and no open agreement of a kind the program requires covers it, every record involved shows a stop until one does (TPR-06).
7. A concern from a review becomes an issue whose actions may belong to the third party's contact (TPR-07).
8. Each third party is due for review on the cadence its tier sets, and at once when an event calls for it (TPR-08).
9. Ending a relationship opens a checklist, and the third party is retired only when every step is recorded (TPR-09).
10. A third party names the parties it depends on, which appear in the picture of connections (TPR-10).
11. The role-by-route matrix covers every new route, including the one route a person without an account can reach; the demo has something worth reading on every new screen; the accessibility audit passes over them.

## Slices

### Slice 1: Services and tiering ☑

**Goal:** what each third party provides and touches, and how much is at stake with it.

- [x] Services (`SVC`): what a third party provides, in the inventory beside it, with the systems each reaches and the information each handles as links; processes rely on services and systems are supplied by them
- [x] A kind of link added by a release reaches an installation that has edited its link kinds
- [x] Tiering: the program's tiers, each with a review cadence and the rules that place a third party in it, written in the one condition language
- [x] A short questionnaire, its answers suggested from the inventory (the most sensitive information it holds or handles, the most critical work that relies on it, the systems it reaches); the tier the rules give, with each reason that applied
- [x] A tiering is a judgment by a named person: a different tier from the rules' needs a reason; earlier tierings stay
- [x] Third parties show their tier in lists and on their page, which gains services and tiering; the demo's suppliers and partners have services and tiers

**Acceptance:** the tier recorded is the one the program's rules give for the answers, with exactly the reasons that matched, unless the person says why it should differ, and both are kept.

**Done:** a service (`service`, `SVC`) is a thing of the inventory with its third party (`third_party_id`), a kind (`service_kinds`), and everything a thing has. It reaches systems and handles information through two new kinds of link (`reaches`, `handles`), and processes rely on services and systems are supplied by them. A release's new kinds of link, and new pairs of records a kind may join, now reach an installation that has saved its own kinds of link; its names stay. A service is added from its third party's page by those who keep the third party, in its unit unless another is said, or by a unit's steward. The program's tiering (`rules.tiering`) names the questionnaire it asks (`third-party-tiering`, shipped with the purpose `tiering`) and four tiers, each with a review cadence and rules in the condition language over `answers` and `facts`; the last tier has no rules. What the inventory says is gathered from the third party, its active services, the information shared with it or handled by its services, the systems it or its services supply, the systems its services reach, and the processes it performs or that rely on its services: the highest data class, the kinds of information, the highest criticality of what relies on it (not of what it merely reaches), and the systems it reaches. The answers it suggests are filled in, with the records each comes from. A tiering (`tier_assessment`) keeps the answers, the facts, the questionnaire version, the tier the rules give with every reason of that tier that holds, the tier recorded, and the reason where they differ; a later one supersedes it and both stay. `third_party.tier` copies the latest, so lists show, sort (Tier 1 first), and cut by it; a third party with no tier is missing one in Tidy. Those who keep a third party, and assessors within their scope, tier it. The tiering table is in the program pack, checked before it is loaded. Third parties have a menu of their own and a page with Overview, Tiering, and History. The demo has 37 services from 36 suppliers and partners, each tiered from what the inventory suggests and what its keeper knows, one recorded a tier lower than the rules' with the reason, the supplier of identity tiered again by the security leader when the email service moved to it, and seven sponsors and partners not yet tiered. The acceptance test is `tests/test_third_parties.py::test_the_tier_recorded_is_the_rules_with_their_reasons_unless_the_person_says_why`.

### Slice 2: Due diligence ☑

**Goal:** ask a third party about itself, without giving it an account.

- [x] Contacts at a third party: names and addresses, who are not accounts
- [x] Reviews (`DDR`): a questionnaire chosen by the tier, sent to a contact, answered, reviewed, and concluded
- [x] The respondent link: a long random token, kept only as a digest, that expires, can be withdrawn, stops working once the answers are sent, and reaches one form and nothing else; carried in the part of the address the browser never sends, and by email when mail is set up, with the message cleared once sent
- [x] The form a contact sees: who is asking, by when, the questions, saving to finish later, and sending
- [x] Review: the answers as asked; the answers the questionnaire marks as concerns, counted and listed; the reviewer's conclusion (approved, approved with conditions, not approved) with what was decided
- [x] Three shipped due diligence questionnaires, from a short one to a full security questionnaire, written for organizations in the United States

**Acceptance:** a contact with no account answers through the link and through nothing else: the link reaches only its own review's questionnaire, and stops working when it expires, is withdrawn, or has been used to send the answers; its token is never stored; the reviewer sees the answers with their concerns counted.

**Done:** a contact (`third_party_contact`) is a person at a third party with a name, an email address, a role, and whether they have left; contacts are kept by those who keep the third party and by assessors, and only they and those who read everything see them. A review (`third_party_review`, `DDR`) belongs to a third party and its unit, records the tier when it began, and asks the questionnaire that tier names (`due_diligence` in the tiering table, falling back to the shipped choice), or another chosen; it is started by those who keep the third party, or an assessor. Sending it makes a link (`respondent_link`): 32 random bytes, of which only the SHA-256 digest is kept; it is for one review and one contact, lasts 1 to 90 days (30 unless said), withdraws any earlier link, and pins the version of the questionnaire. The address carries the token after `#`; the page reads it, takes it out of the address bar, and sends it in the `X-RiskWren-Link` header. Three public routes (`GET`, `PUT /respond`, `POST /respond/submit`) find the link by its digest and reach that review's questionnaire alone; they answer `404` for a token that leads nowhere, `410` for one that expired, was withdrawn, or was used, and `429` after 30 unknown tokens from one address in 15 minutes; they are never cached and need no CSRF token, since they act on no session. The contact saves to finish later and sends; a sent response (`response`, now with no account and a `contact_id`) finishes the link, and the history names the contact as acting by link. Where email is set up the link is sent to the contact, and the message's words are cleared once it has gone or failed. A choice option can carry `concern`, and a yes-or-no question `concern_if`; the review lists the answers that are concerns first, with how many marked answers there were. The reviewer concludes it (approved, approved with conditions, or not approved, with a note for the last two). Answers to read, answers late, and a link that stopped before anyone answered are on the owners' Home, and the date the answers are wanted is in the reminders. Three questionnaires ship: short (8 questions), standard (about 25), and full (about 45), written for organizations in the United States. The demo has contacts at twelve third parties and eleven reviews: six concluded over the year, two with conditions; a survey host's answers in, with five concerns, waiting for the security leader; one half answered; one late; one whose link ran out; and one not yet sent. The acceptance tests are `tests/test_due_diligence.py::test_a_contact_answers_through_the_link_and_through_nothing_else` and `::test_a_link_stops_when_it_expires_or_is_withdrawn_or_replaced`.

### Slice 3: Assurance documents ☑

**Goal:** what independent reports say about a third party, read for what they cover.

- [x] Reports and certificates as evidence of a third party: its kind (an attestation report, a certification, a penetration test summary, a bridge letter), the period it covers, and its expiry
- [x] A contact can send them through the review's link
- [x] A structured review: which of the third party's services it covers and which it does not, the opinion, the parts carved out to others, each exception noted and whether it matters here, and each responsibility left to the organization, joined to the control that meets it
- [x] What it can be relied on for, and until when; one past its expiry stops counting, and its owners are told before

**Acceptance:** an assurance document past its expiry no longer counts for its third party; a review records its scope, its exceptions, and the organization's own responsibilities, each joined to one of the organization's controls, which shows it.

**Done:** a report or certificate is an `evidence` item linked to the third party (`evidence_link.subject_type = third_party`) in its unit, confidential by default; the third party is not one of evidence's ordinary subjects, so a report is seen by its owners, its unit's keepers, assessors, and those who read everything, and not by everyone who sees the third party. Those who keep the third party, and assessors, add one and review it. A review (`assurance_review`) keeps the kind (ten, from a SOC 2 Type II report to a bridge letter), the issuer, the opinion, the services it covers (the rest are shown as not covered), what is carved out, the exceptions (each with whether it matters here and the response), the reliance (relies, partly, cannot; the last two with a note), and who reviewed it; reviewing again supersedes. Each responsibility the report leaves to the organization (`assurance_responsibility`) is in place, with the control that does it, not in place, or not applicable; a control's detail lists the responsibilities of the reviews in force that it meets. A third party's standing is whether any report in date has a review that relies on it, wholly or with gaps. A contact sends up to ten files through a review's link (`POST /respond/files`), each judged by its content like any upload, kept as evidence of the third party and of the review, owned by the review's keepers. The demo has seven: a certification relied on, a SOC 2 report relied on with gaps that does not cover a service added since, one past its expiry, a certificate whose scope stops short of the trial applications, a test summary not yet read, and a report a survey host sent with its answers. The acceptance tests are `tests/test_assurance.py::test_a_report_past_its_expiry_no_longer_counts` and `::test_a_review_records_scope_exceptions_and_the_organizations_own_part`.

### Slice 4: Coverage ☐

**Goal:** whether the paper covers what is shared.

- [ ] An agreement names the third parties it is with, and covers services as well as systems, information, and scopes
- [ ] The program's rules for which kinds of agreement information of each kind needs when it is shared, as data
- [ ] The stop: information shared with a third party, directly or through one of its services, that needs an agreement and has none open and in force with that party covering it; shown on the information, the third party, the service, and the agreements list, and gathered in one list
- [ ] Third parties' agreements on their page, and the demo's gaps

**Acceptance:** every record involved in sharing regulated information with a third party shows the stop while no agreement of a required kind with that party covers it, and none does once one does.

### Slice 5: Lifecycle ☐

**Goal:** a relationship over time: findings, re-assessment, and its end.

- [ ] A concern from a review or an exception in an assurance report raised as an issue about the third party, whose actions may belong to its contact
- [ ] Re-assessment on the cadence the tier sets, from the last concluded review; called for at once by an event, with the event recorded
- [ ] Offboarding: ending a relationship opens a checklist (access removed, information returned or destroyed, agreements closed, an attestation recorded); the third party is retired once every step is recorded
- [ ] Subcontractors: a third party names the parties it depends on, shown on both and in the picture of connections

**Acceptance:** a finding's action can belong to a contact; a third party is due for review on its tier's cadence and when an event calls for it; offboarding retires a third party only when every step is recorded.

### Slice 6: Release prep ☐

- [ ] Guides, changelog, upgrade from 0.4.0 on both databases, audits, release, and the site republished

## Notes

- A **service** is what the organization gets from a third party, and it is what touches the organization's systems and information. A third party with three services can hold restricted information through one and nothing through the others; tiering and coverage read the services.
- The **tier** is a judgment, like every rating here ([ADR-0011](../decisions/0011-judgment-over-arithmetic.md)): the rules suggest and show their working; a named person records it.
- The respondent link follows [security.md](../security.md): long random tokens, single-purpose, expiring, reaching one form. The token travels after `#` in the address, which browsers do not send to servers, so it is not in any server's or proxy's logs.
- Nothing in this wave reaches out to a third party's systems. A questionnaire is answered by a person; a report is read by a person ([ADR-0003](../decisions/0003-passive-by-design.md)).
