# Security review (wave 9)

RiskWren 0.9.0 was reviewed against the **OWASP Application Security Verification Standard 4.0.3, level 2** (PLT-19), on 2026-11-27, before its release. The review read the code; it did not test a running installation from outside. It covered:

- **V2 and V3**, authentication and sessions
- **V4 and V8.3**, access control and what each person may see
- **V5, V7, V12, V13, and V14**, input, errors and logging, files, the API, and configuration

Each chapter was read by a reviewer working from the code alone, and every finding was then traced in the code before it was fixed or accepted. Where a finding is fixed, a test keeps it fixed: `tests/test_security_review.py`, and the tests named below.

## Findings and what was done

| # | Finding | Severity | ASVS | Resolution |
|---|---|---|---|---|
| V4-1 | A token's principal had no account, so comparisons with "created by me" matched every record nobody made: a member's token listed reports made without a name, restricted cases among them | High | 4.1.3, 4.2.1 | **Fixed.** A token acts with a negative account number no account has, so nothing is ever its own; `riskwren.db.guard` keeps that number out of every column that names a person. `test_a_token_is_nobody_and_owns_nothing` |
| V4-2 | A token could read questionnaire answers sent through a link, which also have no account | Medium | 4.2.1 | **Fixed** by V4-1 |
| V4-3 | Webhooks run from `riskwren jobs run` did not know every kind of record, and named a restricted case | High | 4.1.3, 8.3.4 | **Fixed.** Queueing loads every kind of record first, and treats a kind it does not know as restricted |
| V4-4 | A token could ask for an exception and then decide it, or propose an issue's closure and confirm it | Medium | 4.3.3 | **Fixed.** Judgments a named person makes (rating, accepting, deciding, confirming, approving, signing off, publishing, triage) refuse tokens: `PERSON_ONLY` in `access/policy.py`. `test_a_token_makes_no_judgment` |
| V4-5 | A record's history named records the reader may not see | Medium | 4.2.1, 8.3.4 | **Fixed.** A history read by a person names an unseen record as "a record you cannot see"; dossiers likewise |
| V4-6 | A dry run of an import said that a name was already on record in a unit the importer cannot see | Low | 4.2.1 | **Accepted for now**: it says a name is taken, not what the record says. To be narrowed to units the importer may add to |
| V4-7 | An incident's list card showed its handlers and severity to a reporter who sees only their report | Low | 4.1.3 | **Accepted for now**: a reporter sees their own report's handler by design; severity to be blanked in cards as it is in the detail |
| V4-8 | The history of everything showed which evidence a workpaper cited before the report was issued | Low | 4.1.3 | **Accepted for now**: references only, to those who read everything. To be redacted with the workpaper's words |
| V4-9 | Some GET routes record events (exports, dossiers, a campaign's refreshed state) | Informational | — | **Accepted**: what is recorded is bookkeeping and the record of the read itself |
| V12-1 | A dossier sent to be checked could unpack a manifest of hundreds of megabytes into memory | Medium | 12.1.1, 12.1.2 | **Fixed.** The manifest is limited to 4 MB, files are hashed in pieces, and a broken archive is reported, not raised. `test_a_dossier_check_reads_within_bounds` |
| V5-2 | Spreadsheet formulas were guarded in text cells but not in list cells, such as tags | Low | 5.3.1 | **Fixed.** `test_a_list_cell_cannot_be_a_formula` |
| V5-3 | A Markdown link to `/\host` passed as a path inside the site | Low | 5.1.5 | **Fixed.** Backslashes and control characters are refused in links, as at sign-in |
| V7-4 | A failed statement's values (a report's words, an answer) could reach the log | Low | 7.1.1, 7.1.2 | **Fixed.** The engine hides statement parameters |
| V7-5 | The server's access log, and Caddy's, recorded where reports without a name came from | Low | 7.1.2 | **Fixed.** Those paths are left out of the server's access log, and the Caddy and nginx examples neither log nor forward the address for them |
| V14-6 | In a container, every person seemed to come from one address, so the limits on failed sign-ins applied to everyone at once | Low | 14.1 | **Fixed.** The compose file trusts the forwarded address from the proxy (`FORWARDED_ALLOW_IPS`) |
| V14-7 | No `Strict-Transport-Security` header | Low | 14.4.5 | **Fixed.** Sent with every answer over https, and in both proxy examples |
| V12-9 | A body sent in chunks, with no length, was not held to the size limit | Low | 12.1.1, 13.1 | **Fixed.** The application counts the body as it arrives (`max_body_size`) |
| V5-10 | A framework pack's header (its source address, publisher, license) was not checked | Low | 5.1.3, 5.1.4 | **Fixed.** Checked for type and length, and the address must be http or https |
| V12-8 | No storage quota, no sweep of replaced files, no virus scan of uploads | Low | 12.1.3, 12.4.2 | **Accepted for now**: uploads are limited in size and type and are only ever downloaded; a scan hook is planned |
| V12-11 | An administrator can register a webhook to an address inside the network | Informational | 12.6.1 | **Accepted**: only administrators register webhooks, which must be https and are not redirected; a ticketing system inside the network is a proper use |
| V2-1 | The limit on failed sign-ins to one account, from anywhere, can be used to keep its owner out for fifteen minutes | Medium | 2.2.1 | **Mitigated, accepted.** The limit was lowered to 25 in fifteen minutes (100 an hour); single sign-on is not affected; and in a container, people are now told apart by address (V14-6). A limit that exempts devices that signed in before needs the address of each sign-in kept, and is planned |
| V2-2 | Signing in to one's own account reset the count of failures from that address, and the account limit allowed 120 an hour | Low | 2.2.1 | **Fixed.** A success clears only that account's counts; the wide limit is 100 an hour |
| V2-3 | Sessions could not be set shorter than an hour idle or a day in all | Low | 3.3.2 | **Fixed.** Both take fractions; `session_idle_hours = 0.5` and `session_max_days = 0.5` meet level 2. The defaults (12 hours, 7 days) are unchanged, and the configuration guide says so |
| V2-4 | A person who signs in through the identity provider, with no password, could be given one by anyone holding their session | Low | 3.7.1 | **Fixed.** A first password needs a sign-in in the last ten minutes |
| V2-5 | The current password could be guessed through the change-password route, outside the sign-in limits | Low | 2.2.1 | **Fixed.** Wrong current passwords are counted and limited there too |
| V2-6 | The session cookie's `Secure` flag depended on how each request arrived | Low | 3.4.1 | **Fixed.** It is always set when `base_url` is https. The `__Host-` prefix is not used, so that the cookie keeps working over plain http on a developer's own machine |
| V2-10 | A person was not told when their password changed | Low | 2.2.3 | **Fixed.** A notice, and email where it is set up |
| V2-11 | Passwords of up to 1,024 characters were accepted | Low | 2.1.2 | **Fixed.** At most 128. `test_a_password_is_at_most_128_characters` |
| V2-7 | People cannot see and end their own other sessions | Low | 3.3.4 | **Planned** |
| V2-8 | Passwords are not checked against a list of breached ones | Low | 2.1.7 | **Planned**, from a list shipped with RiskWren, so that nothing is sent anywhere |
| V2-9 | A password an administrator sets does not have to be changed | Low | 2.3.1 | **Accepted for now**: the person is told (V2-10) and asked to choose their own |
| — | Local passwords are one factor; a second factor comes only through single sign-on | Level 2 asks for it | 2.2 | **Accepted, documented**: production installations are advised to use single sign-on, which brings the organization's own second factor |

## What held

The reviewers recorded, among others:

- **Passwords.** Hashed with scrypt and a salt, at least 12 characters, any characters, no composition rules or forced rotation.
- **Sign-in.** One answer for every failure, whether the account exists or not.
- **Sessions.** Tokens of 256 bits, kept only as digests, new at every sign-in, and ended on the server at sign-out, on a password change, and when an account is disabled. Cookies are HttpOnly and SameSite=Strict.
- **Request forgery.** A per-session token in a header, compared in constant time, and the origin checked on every change.
- **Single sign-on.** OpenID Connect with PKCE, state, and nonce. Only RS256 is accepted, with the issuer, audience, and times checked.
- **Links that need no account** (due diligence, outside auditors, reports without a name). Their secrets are kept only as digests, sent in headers or after `#`, and ended on their date or when withdrawn.
- **Access.** Every route is in one policy table, and a route missing from it is refused. Every record is read through the person's own visibility, and a record they may not see answers 404.
- **Segregation of duties** holds between people: requester and decider, proposer and confirmer, preparer and signer, drafter and approver.
- **Pages.** No HTML is built from text in the browser, and the content security policy has no inline script.
- **Files.** Uploads are judged by their content, stored by their digest outside the web root, and only ever downloaded.
- **Headers.** The usual security headers, and no CORS.
- **Secrets.** Refused in the configuration file.
- **Errors.** Generic to the person, with detail kept for the log.
- **Deployment.** The container runs as its own user, and the systemd unit is locked down.

## Accessibility

The automated audit (`scripts/a11y-audit.mjs`) checks every documented screen in three palettes and both modes against WCAG 2.2 AA. A screen-reader check (`scripts/screen-reader-check.mjs`) reads each main journey's accessibility tree: one main landmark and one level-one heading, headings in order, a name on every control and link, labels on every field, and status messages announced. A person using a screen reader has not yet gone through the app; that is planned before 1.0.
