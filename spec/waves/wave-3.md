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

### Slice 2: Schedules and email ☐

**Goal:** the app knows what is due, and says so.

- [ ] The job scheduler: daily jobs, each run by exactly one process, with what ran and what it did on record
- [ ] Cadences as one table keyed by rating and criticality; key controls; the next test date on a control
- [ ] Reminders, then escalation to the steward and the leader, on a schedule the program sets
- [ ] SMTP delivery, off until set up; as it happens or a daily digest; each person's preferences

**Acceptance:** two servers on one database run a job once between them; an overdue action reminds its owner and later their steward; with no mail server, nothing is attempted and nothing is lost.

### Slice 3: Questionnaires ☐

**Goal:** questions as data, asked the same way everywhere.

- [ ] Questionnaires as versioned documents of sections and questions with conditions
- [ ] One condition evaluator, in Python and in JavaScript, held together by shared test cases
- [ ] Answers kept with the version they were given under

**Acceptance:** the same cases pass in both evaluators; an answer still reads as asked after the questionnaire changes.

### Slice 4: Campaigns ☐

**Goal:** ask the owners, by a date, and see who has answered.

- [ ] Campaigns: a set of people, one thing to do, a date, tracking, reminders, and coverage by unit
- [ ] Risk and control self-assessment; control attestation; unit completeness; evidence requests
- [ ] Attestation as a basis of assurance, shown apart from a test, with a rule for what readiness may rest on

**Acceptance:** an attested control is never shown as verified; a campaign's coverage by unit matches the list behind it.

### Slice 5: Indicators ☐

**Goal:** early warning.

- [ ] Indicators with thresholds, readings, and a trend, linked to risks
- [ ] A breach raises a notice and flags the risks it warns of

**Acceptance:** a reading past its threshold notifies the indicator's owner and shows on each linked risk.

### Slice 6: Find and tidy ☐

**Goal:** anything on record can be found, and kept in order.

- [ ] Search across every record type, cut to what the searcher may see; saved and shared views
- [ ] Completeness on each record; likely duplicates suggested, for records and for new issues
- [ ] Reassigning what someone owned when their account is disabled

**Acceptance:** a search never returns a record its searcher could not open; disabling an owner leaves nothing without one.

### Slice 7: Program editors ☐

**Goal:** the program is edited where it is used.

- [ ] Editors for the taxonomy, scales and matrix, appetite, cadences, and vocabularies
- [ ] An impact preview: the risks whose rating or standing would change
- [ ] Structured risk assessments over a scope

**Acceptance:** publishing a changed matrix changes exactly the risks the preview listed.

### Slice 8: Release prep ☐

- [ ] Guides, changelog, upgrade from 0.2.1 on both databases, audits, release, and the site republished

## Notes

- Single sign-on follows [ADR-0008](../decisions/0008-accounts-and-single-sign-on.md), amended in slice 1: the mappings are kept in the app and not in the configuration file, so that whoever administers RiskWren can change them without a restart or access to the server.
