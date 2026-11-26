# Security

RiskWren holds a map of an organization's weaknesses: the risks it has identified, the controls that are not working, the findings nobody has closed yet, and the evidence behind all of it. That makes its own security a first-order requirement, not a feature. This document sets out what is protected, from whom, the controls for each threat, and who may do what.

## What is being protected

| Asset | Why it matters |
|---|---|
| **The history** | Its value is that it cannot be quietly changed. An assessment or acceptance that can be edited is worth nothing to an auditor |
| **The register itself** | Open risks, failed tests, and unresolved issues are a reading list for an attacker and a liability if disclosed |
| **Evidence files** | Configuration exports, third-party reports, contracts; some confidential by their own terms |
| **Restricted records** | Investigations, cases, and audit work in progress, whose existence may itself be sensitive |
| **Accounts and sessions** | Whoever holds a leader's session can accept a risk; whoever holds a manager's can change the scoring method |
| **Program configuration** | Changing a scale, an appetite, or a cadence changes what the organization sees as acceptable |
| **Availability** | A register that is down sends people back to spreadsheets |

RiskWren is designed **not** to hold the regulated data it describes. Records describe systems and information; they never contain patient, participant, or other protected data. Forms say so where free text is requested, and evidence uploads carry a data class so that anything sensitive is at least labelled and access-limited.

## Who might attack, and how they get in

| Actor | Route |
|---|---|
| Someone outside, without an account | The sign-in page, the single sign-on callback, and from later waves anything opened to people without accounts |
| A signed-in member | Trying to read others' records, reach restricted ones, or use admin functions |
| An owner or leader | Assessing or accepting beyond their authority; accepting their own risk; closing their own issue |
| A steward or assessor | Reaching beyond their unit |
| Another website open in a user's browser | Cross-site requests riding the user's session |
| Content a user submitted | Script or markup in a description, a comment, a file name, or an uploaded SVG or HTML file |
| Someone with access to the database or disk | Editing history or reading files directly |
| A compromised or careless integration | A leaked API token or webhook secret |

## Controls, by threat

### Sign-in and sessions

- Sign-in is always required; there is no anonymous mode.
- Passwords are hashed with scrypt from the standard library, with parameters stored beside each hash so the cost can be raised later. Rules follow current guidance: a minimum length of 12, no composition rules, no forced rotation.
- Sign-in is throttled per account and per address, with the counters in the database so the limit holds across workers. Unknown accounts take the same time as known ones.
- Sessions are opaque random tokens in an `HttpOnly`, `SameSite=Strict`, `Secure` cookie. Only a hash is stored. Sessions expire after a period idle and after a maximum age, and are revoked on sign-out, password change, and account disablement.
- The last active administrator can never be removed or demoted, locally or through the identity provider.

### Single sign-on (wave 3)

- OpenID Connect authorization-code flow with PKCE, `state`, and `nonce`. Sign-in state is stored server-side, single-use, short-lived, and tied to the browser that began it.
- The ID token's signature, issuer, audience, expiry, and nonce are all verified before a session is created.
- The client secret is read from the environment and never written to the configuration file or the database.
- Roles mapped from the provider are replaced at each sign-in, so removing someone from a group removes their access at their next sign-in.

### Authorization

- **One policy table.** Every API route names the permission it requires. A route missing from the table is refused, and a test fails if any route lacks an entry.
- **Checked again in the service.** Service functions take the acting principal and check both the permission and the record: scope, ownership, and visibility. The API cannot reach data by skipping a check, because the check is where the data is.
- **A role-by-route matrix test** signs in as each role and exercises every route, asserting the expected outcome.
- **Separation of duties.** Nobody accepts a risk they own. Nobody accepts a risk above the limit on their grant. From wave 2: nobody records the result of a test on a control they own, nobody reviews their own test, nobody validates the closure of an issue they own, and nobody approves their own exception.
- **Administration is not judgment.** The admin role manages accounts and settings. It does not, by itself, allow assessing, accepting, or testing; an administrator who also does that work holds a second role, and the history shows which they acted under.

### Cross-site requests and content

- Every state-changing request needs a per-session CSRF token in a header, and requests whose origin does not match the host are refused.
- The content security policy is `default-src 'self'` with no inline script or style and no third-party origins. Frames are denied.
- The front end inserts data only as text nodes. No user-supplied value is ever parsed as HTML. Descriptions and notes support a small, safe formatting subset rendered by the app's own code.
- The generated theme stylesheet is built only from values that have passed strict validation.

### Files (wave 2)

- Uploads have a size limit (25 MB) and an allowlist of types, checked by content, not by name. Text of any kind is kept as plain text; programs and unrecognized binary are refused.
- Files are stored by hash outside any served directory and are only ever returned through a route that checks access to something the file is attached to.
- Downloads are always sent as attachments with a policy of `default-src 'none'; sandbox` and sniffing off, and anything that is not an inert type leaves as plain bytes, so an uploaded HTML or SVG file cannot run in the app's origin. Each download is an event.
- Uploaded logos are sanitized and served from a route with its own locked-down policy.

### The history

- Events are append-only in the application, and triggers in the database refuse updates and deletes on the event table. `riskwren doctor` reports a missing trigger.
- Each event is hashed together with the previous event's hash. `riskwren verify` recomputes the chain and reports the first break. The latest hash can be exported on a schedule and kept elsewhere, so that even rewriting the whole chain is detectable.
- Reading sensitive things is recorded too: evidence downloads, exports, and views of restricted records are events.

### Integrations (wave 9 and later)

- API tokens are scoped to a role and optionally to read-only, shown once, stored as hashes, and expire.
- Webhooks are signed, sent only to addresses an administrator registered, and carry references rather than record contents by default.
- A result pushed in by another system is recorded with its source and is never able to override a person's judgment or close an issue.
- Links given to people without accounts (a third party answering a questionnaire, a person reporting a concern) are long random tokens, single-purpose, expiring, and reach one form and nothing else.

### Operations

- Secrets come only from the environment.
- No request bodies, form answers, or tokens are written to logs.
- `riskwren doctor --production` (wave 9) checks the things that matter before going live: TLS in front, secure cookies in effect, a current schema, a recent backup, mail and single sign-on reachable, and no default or demo accounts present.
- The demo organization is built only by an explicit command into its own data home, marks itself as a demo on every page, and its server refuses to listen on anything but the local machine unless told otherwise.

## Who can see and do what

### Visibility

**The inventory is open.** Processes, systems, information assets, and third parties are visible to everyone signed in, because a record can only be linked to what its author can see: a lab cannot say that its work relies on central storage if it cannot find central storage. What they describe is rarely sensitive, and what is can be marked restricted.

**The register follows a setting.** A register of risks and controls is useful in proportion to how widely it is read and dangerous in proportion to how widely it is exposed. Organizations differ on where to draw the line, so for ordinary members it is a setting with three levels:

| Setting | A member sees |
|---|---|
| **Open** | Every risk and control that is not restricted |
| **Unit** (default) | The risks and controls of the units they belong to, and any they own or are named on |
| **Assigned** | Only the risks and controls they own or are named on |

Whatever the setting, leaders and stewards see their unit and everything beneath it, and managers, assessors in scope, auditors, and administrators see what their role needs. Issues, test results, and evidence (wave 2) are visible only to those with a role in them. Any record can be marked **restricted**, which limits even its existence to its owners, its unit's stewards and leaders, managers, and auditors; an assessor does not see restricted records unless named on them.

One function per record type decides what a principal may see. Single records, lists, counts, charts, searches, and exports all call it, so they always agree.

### Permissions

| Capability | Member | Owner of the record | Steward (in scope) | Leader (in scope) | Assessor (in scope) | Manager | Auditor | Admin |
|---|---|---|---|---|---|---|---|---|
| See what is assigned to them; complete an action | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Read the inventory (unless restricted) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Read risks and controls | by setting | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Read frameworks and their requirements (wave 2) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Read scopes (wave 2) | by setting | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Keep a scope: its boundary, frameworks, applicability, and implementations (wave 2) | | ✓ | ✓ | | | ✓ | | |
| Add evidence for a unit they work in or have a role over (wave 2) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | | |
| Attach evidence to a control or a scope (wave 2) | | ✓ | ✓ | | ✓ | ✓ | | |
| Add a record in a unit | | | ✓ | | | ✓ | | |
| Edit a record; link and unlink; map a control to requirements (wave 2) | | ✓ | ✓ | | | ✓ | | |
| Assess a risk; rate a control | | ✓ | ✓ | | ✓ | ✓ | | |
| Record a response; create and manage a treatment plan | | ✓ | ✓ | | | ✓ | | |
| Accept a risk | | | | ✓ (not their own; up to their limit) | | | | |
| Escalate a risk; reassign owners | | | ✓ | ✓ | | ✓ | | |
| Record a test result (wave 2) | | | | | ✓ (not their own control) | ✓ (not their own control) | | |
| Validate closure of an issue (wave 2) | | | | | ✓ (not their own) | ✓ (not their own) | | |
| Read the full history; export | | | | | | ✓ | ✓ | ✓ |
| Edit the taxonomy, scoring method, appetite, cadences, libraries, and vocabularies | | | | | | ✓ | | ✓ |
| Enter and keep the organization's own frameworks; retire a framework (wave 2) | | | | | | ✓ | | ✓ |
| Manage accounts, roles, units, branding, and system settings | | | | | | | | ✓ |

A manager's authority to edit any record does not include accepting risk: acceptance belongs to the first line, to a named leader with the authority for that rating.

## Review

- **Each wave:** the role-by-route matrix, the web safety tests (no inline script or style, no third-party origins, no HTML parsing of data), and dependency review are part of the definition of done.
- **Wave 9:** a full review against the OWASP Application Security Verification Standard, level 1, with findings and their resolution recorded in `spec/reviews/`.
- **Before 1.0:** the review is repeated, and a second person who did not write the code walks the threat table above.

Vulnerabilities are reported privately as described in `SECURITY.md`.
