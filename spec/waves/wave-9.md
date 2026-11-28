# Wave 9: Adoption (v0.9.0)

**Goal:** an organization that has never seen RiskWren installs it, makes it its own, and runs it in production. Waves 1 to 8 built the record and everything a program does with it, shaped by one fictional research institute. Wave 9 is about the second organization: one that is not a research institute, has its own words for things, runs its own servers, connects its own systems, and needs to know that what it is trusting has been reviewed.

**Branch:** `wave-9` · **Target version:** `0.9.0` · **Status:** ◐ in progress

The security team comes first here as everywhere ([roadmap](../roadmap.md#whose-work-comes-first)). For a security team adopting RiskWren, this wave answers the questions asked before anything goes into production: can it be backed up and restored, how does it behave with our numbers, can our other systems reach it with a token that can do only what it should, how do we deploy it the way we deploy everything else, and has it been reviewed against a standard we recognize.

## Exit criteria

The wave is done when, on a fresh checkout:

1. An installation is backed up to one file, restored into an empty database, and moved between SQLite and PostgreSQL by command, with every row, file, and the history intact (PLT-15).
2. How it performs at 10,000 records and with many people at once is measured and written down, and nothing measured is slow enough to be noticed.
3. The organization's own words replace the product's for the kinds of record and for units, and email carries its header (PLT-17).
4. A new installation can start from a program pack for a research institute, an academic medical center, a university, or a general nonprofit (PLT-18); an administrator adds fields of the organization's own to a kind of record; frameworks whose text cannot be shipped load as identifiers to which the organization adds its own words.
5. An administrator issues a token limited to a role, a unit, and optionally to reading, shown once, stored as a hash, with an expiry (INT-02); named events are sent, signed, to addresses an administrator registers, carrying references and not record contents (INT-03); the API's contract is recorded, and a change that would break a client is caught by a test.
6. A container image, a compose file with PostgreSQL, a hardened service unit, and proxy examples are in the repository and are checked; `doctor --production` says what is not yet ready; an operations view shows the installation's state (PLT-16).
7. The application is reviewed against a published verification standard, with each finding and its resolution recorded (PLT-19); the accessibility audit and a screen-reader check pass over every screen.
8. A handbook takes a risk and compliance team from its first decisions to the yearly rhythm (DOC-03), and an adopter's guide takes an organization from evaluation to production.
9. The role-by-route matrix covers every new route; the demo shows each new capability where it can; the accessibility audit passes over every new screen.

## Slices

### Slice 1: Production ☑

**Goal:** it can be trusted with an organization's records: backed up, restored, moved, and measured.

- [x] `riskwren backup`: one file with every table, every stored file, and a manifest of digests, taken as one consistent reading (PLT-15)
- [x] `riskwren restore`: into an empty database, at the archive's migration, checked against the manifest and the history (PLT-15)
- [x] Moving between SQLite and PostgreSQL is a backup from one and a restore into the other
- [x] Measured at 10,000 records and many people at once; what was measured, and on what, written down; anything slow made fast
- [x] Several workers: scheduled work runs once however many there are

**Acceptance:** a backup of the demo restores into an empty SQLite and an empty PostgreSQL database, each table reads back with the same fingerprint, the history verifies, and the restored database takes new records; a changed backup, one from another version, and one naming a file outside the data home are refused; the measurement is in the configuration guide.

**Done:** `riskwren.backup` writes each table as JSON lines in primary-key order inside one transaction (`REPEATABLE READ` on PostgreSQL), with the data home's `files` and `brand` folders and a manifest of row counts and SHA-256 fingerprints; a restore migrates an empty database to the backup's migration, takes out what the migrations seeded, loads every table in dependency order (a column naming a row of its own table is filled in afterwards), starts PostgreSQL's numbering after the restored rows, writes the files only inside the data home, and reads every table back to compare. The demo went from SQLite to PostgreSQL and back with every fingerprint the same. `scripts/measure.py` grows the demo to a number of records and has people read the busiest pages at once against a real server; the configuration guide's **Sizing** gives the results. Measuring found the compliance dashboard building every control's full view for each scope (about 730 queries), now a brief statement (174), and a read-only request asking for the same settings, units, and categories dozens of times, now remembered for the length of the request (`riskwren.db.remember`), taking home from 268 queries to 172. Claiming a scheduled job was already safe across processes, and is tested. The acceptance tests are `tests/test_backup.py` and `tests/test_remember.py`.

### Slice 2: Brand kit ☑

- [x] The organization's own words for the kinds of record and for units, in the file or the app (PLT-17)
- [x] An email header with the product's name and the organization's accent

**Done:** most of the brand kit came early, in 0.8.0: exact colors, the sign-in message and picture, footer links, the email's last line, and contrast checks. This slice adds `terms` to the branding (in the app under **Admin → Appearance → Your own words**, or `[branding.terms]` in the file, which then locks them): one and many for units, processes, systems, third parties, services, information assets, sites, issues, exceptions, and incidents. The web app applies them to the kinds of record (their labels, plurals, nouns, and articles), to the menu, and to the unit's name in forms, lists, filters, and **Admin → Units**. Email opens with a header in the organization's accent (the file's day accent, the one chosen, or the palette's), with the product's name and the organization's. The acceptance tests are in `tests/test_branding.py`.

### Slice 3: Starter programs ☑

- [x] Program packs for an academic medical center, a university, and a general nonprofit, beside the research institute's (PLT-18), chosen at `init`
- [x] Fields of the organization's own on a kind of record: text, a number, a date, or a choice
- [x] Identifier-only framework packs for frameworks whose text cannot be shipped, to which the organization adds its own words

**Done:** `scripts/build-starter-programs.py` writes four program packs to `resources/packs/programs/` from the default: what differs is the families of risk (those that do not apply are retired, never removed), the kinds of unit, process, and information, and how the scales speak of the work. `riskwren init --program KEY` loads one after the default, and `riskwren program import KEY` takes a starter's name. Fields of the organization's own are the program's `custom_fields` setting (up to twelve on each of systems, processes, third parties, services, information assets, sites, risks, and controls; text, a number, a date, or a choice; with help and whether needed), edited under **Admin → Program → Fields**; values are `custom_value` rows, children of their record in the history (migration 0046), given as `custom` through the API, asked for in the inventory's forms, and shown on a record's page under **More about it**. The demo asks for a cost center and a support tier on systems. ISO/IEC 27001:2022 ships as its codes alone (`iso-27001`, text policy `identifiers`, which may now carry a code without a label), loaded with `riskwren frameworks load iso-27001`; `riskwren frameworks text` loads a licence holder's titles and text into `requirement.local_title` and `local_text`, shown in place of the code and marked as theirs. The NIST AI Risk Management Framework, also planned for wave 9 in the content plan, moves to a later wave. The acceptance tests are `tests/test_starters.py` and `tests/test_fields.py`.

### Slice 4: API for others ☑

- [x] Scoped tokens (INT-02)
- [x] Signed webhooks (INT-03)
- [x] A recorded API contract, and a test that catches a change that would break a client

**Done:** `api_token` (migration 0047) keeps a token's name, the first ten characters to tell it apart, its SHA-256 digest, the role it acts as (auditor, manager, assessor, steward, or member; never an administrator), a unit for a manager's, an assessor's, or a steward's, whether it may only read, and its end, at most 366 days on. The access middleware takes `Authorization: Bearer`, ignores any cookie beside it, refuses a token not in force with 401 and a change from a reading token with 403, and needs no CSRF token for it. A token's principal holds its role and nothing of a person's; its changes are events with the actor kind `token` and its name. When it was last used is written outside the history, at most every five minutes. `webhook`, `webhook_delivery`, and `webhook_cursor`: a scheduled job, **Webhooks**, reads the history since the cursor, makes one message for each operation on a named record of the families a hook wants (never a restricted record, and never the past when a hook is new), signs it with HMAC-SHA256 over the time and the body, and tries again after 1 minute, 5, 30, 2 hours, and 12 hours. Both are under **Admin → Other systems**, which the demo fills with two tokens and a paused webhook. `docs/api-contract.json` records each operation's parameters and body fields and whether each is needed; `tests/test_contract.py` fails on a route, parameter, or field taken away, or on one newly needed. The acceptance tests are `tests/test_integration.py` and `tests/test_contract.py`.

### Slice 5: Deployment ☑

- [x] A container image and a compose file with PostgreSQL, built and run in a check (PLT-16)
- [x] A hardened service unit and proxy examples
- [x] `doctor --production`
- [x] **Admin → Operations**: version, database, jobs, the last backup, the data home's size, and health

**Done:** `deploy/Containerfile` builds in two stages with `uv` from the lock file, runs as user 10001 with `/data` as its volume, and on its first start runs `riskwren init` (taking the first administrator and a starter program from the environment), on every later one `riskwren db upgrade`. `.containerignore` keeps the build context to what the image needs. `deploy/compose.yaml` runs it with PostgreSQL 16, healthy before RiskWren starts, published on `127.0.0.1` only; `deploy/riskwren.service` is a systemd unit with only the data home writable and the usual hardening; `deploy/Caddyfile` and `deploy/nginx.conf` end TLS in front, the latter keeping no log for reports made without a name. The image was built with Podman and run: it set itself up from the university program, ran as its own user, and answered its health check and its pages. `riskwren backup` leaves a note of the last backup in the data home; `riskwren doctor --production` (`doctor.going_live`, which reaches nothing outside) checks the address, where it listens, the database, a backup in the last two days, the demo marker, two administrators, and email, and **Admin → Operations** (the scheduled work page, renamed, at `/admin/operations`) shows the same beside the installation's version, database and migration, workers, data home, and last backup. A new guide, Deployment. The acceptance test is `tests/test_backup.py::test_doctor_says_what_stands_between_it_and_production`.

### Slice 6: Security and accessibility review ☐

- [ ] A review against the OWASP Application Security Verification Standard, level 2, with each finding and its resolution recorded (PLT-19)
- [ ] The full accessibility audit, and a screen-reader check of the main journeys

### Slice 7: The program handbook ☐

- [ ] One guide for a risk and compliance team, from first decisions to the yearly rhythm (DOC-03)
- [ ] The adopter's guide: from evaluation to production

### Slice 8: Release prep ☐

- [ ] Guides, changelog, upgrade from 0.8.0 on both databases, audits, release, and the site republished

## Decisions

Made on 2026-11-27 without the user, under their go-ahead to build waves 9 and 10 while they were away; each is open to their review.

- **A backup is a portable file, not a database dump.** Rows are written as JSON lines, table by table, with a manifest of counts and digests, so the same file restores into SQLite or PostgreSQL and moving between them needs nothing else. A restore goes into an empty database only, never over an existing one.
- **Tokens act as a role, never as a person.** A token carries a role, optionally a unit, and optionally read-only; what it does is recorded under the token's name. It never signs in to the web app and needs no CSRF token, since it is not a cookie.
- **Webhooks carry references, never contents.** The receiver asks the API, with a token, for what it may see. Deliveries are queued, signed with HMAC-SHA256, retried with backoff, and kept for a time.
- **Terms change nouns, not meanings.** An organization may rename the kinds of record and units; statuses, roles, and the words of the program (scales, appetite) are already its own.
- **Identifier-only packs ship identifiers and nothing else** for frameworks whose publishers do not allow their text to be copied; the organization adds its own words, which stay in its database.

## Notes

- The starter programs differ in what a program is made of (taxonomy, appetite, vocabularies, cadences, roles' words) and not in the product's behavior.
