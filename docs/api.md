# API

Everything the web app does, it does through a JSON API under `/api/v1`. This guide covers how to sign in, how answers and errors are shaped, how lists page, and what routes there are. The exact shape of every request and answer is in the OpenAPI document: [openapi.json](openapi.json) in this directory, or `/api/openapi.json` on a running server.

This release has no API tokens. A program signs in as an account, with that account's password, and holds a session as a browser does. Tokens scoped to a role arrive with integrations in a later release; see the [roadmap](../spec/roadmap.md).

Until 1.0, routes may change between releases. Changes are listed in the [changelog](../CHANGELOG.md).

## Sign in

```bash
curl -s -c cookies.txt -H 'Content-Type: application/json' \
  -d '{"email": "you@example.org", "password": "…"}' \
  http://127.0.0.1:8000/api/v1/session
```

The answer describes who you are, and sets a session cookie, `riskwren_session`:

```json
{
  "data": {
    "account": {"id": 12, "name": "Your Name", "email": "you@example.org"},
    "roles": ["manager"],
    "permissions": {"…": true},
    "units": {"manager": null},
    "member_units": [4],
    "has_password": true,
    "csrf_token": "…"
  },
  "meta": {}
}
```

In `units`, each scoped role lists the units it covers, or `null` for the whole organization.

`GET /api/v1/session` returns the same for the session you hold, or 401 if you hold none. `DELETE /api/v1/session` signs out.

## Changing things

Every request that changes anything (`POST`, `PUT`, `PATCH`, `DELETE`) must carry the session's CSRF token in a header:

```bash
curl -s -b cookies.txt -H 'Content-Type: application/json' \
  -H 'X-CSRF-Token: …' \
  -d '{"name": "Freezer farm", "kind": "device", "criticality": "critical", "org_unit_id": 4}' \
  http://127.0.0.1:8000/api/v1/systems
```

Without it the answer is 403. If the request carries an `Origin` header, it must match the host, or the request is refused.

### Editing a record someone else is editing

Records carry a `version`. Send the version you read with a `PATCH`, and if someone else has changed the record since, the answer is 409 and nothing is saved. Read it again and decide what to do.

## Answers

Every successful answer has the same envelope:

```json
{"data": …, "meta": {…}}
```

`data` is one object or a list. `meta` carries what is about the answer and not in it: paging for a list, or a count of what else changed.

Times are UTC in ISO 8601. Dates with no time, such as a due date, are `YYYY-MM-DD`.

## Errors

Errors are problem documents (`application/problem+json`):

```json
{
  "type": "about:blank",
  "title": "Unprocessable Entity",
  "status": 422,
  "detail": "The assessment was not recorded.",
  "errors": [
    {"location": ["rationale"], "message": "Say why, in a sentence or two. A rating is a judgment."}
  ],
  "instance": "/api/v1/risks/RSK-0002/assessments"
}
```

| Status | Meaning |
|---|---|
| 400 | The request could not be carried out as asked |
| 401 | Nobody is signed in, or the email address and password do not match |
| 403 | You are signed in but may not do this, or the CSRF token is missing. `detail` says which |
| 404 | No such thing, or none that you may see. The two are not told apart |
| 409 | A conflict: the record changed since you read it, or the thing is already so |
| 413 | The request is larger than 32 MB |
| 422 | A value is missing or not allowed. `errors` names each field |
| 429 | Too many failed sign-ins. Wait a few minutes |
| 503 | The database is unavailable |

## Lists

Every list route takes the same parameters:

| Parameter | Meaning |
|---|---|
| `q` | Words to look for in the name, reference, or summary, or in what the record is called in another system |
| `unit` | A unit's id. Includes every unit beneath it |
| `sort` | A field name. Start with `-` for descending. The default is `-updated_at` |
| `limit` | How many to return: 50 by default, 200 at most |
| `cursor` | Where to continue from: `next_cursor` or `prev_cursor` from the last answer |
| `mine` | `true` for only the records you are named on |

Each kind of record adds its own filters, such as `standing`, `residual_rating`, and `category` for risks. The OpenAPI document lists them.

A list's `meta` says where the page sits:

```json
{"total": 180, "offset": 0, "next_cursor": "eyJvZmZzZXQiOjUwfQ", "prev_cursor": null}
```

A list returns only what you may see, and `total` counts only that.

## Routes

Every route requires a signed-in account except those marked public. What a route allows beyond that depends on the record: its unit, its owners, and its visibility. See [Running the program](running-the-program.md#roles-and-scope).

### System and session

| Route | What it does |
|---|---|
| `GET /health/live` · `GET /health/ready` | Whether the server is up, and whether it can serve (public) |
| `GET /meta` | Product name, version, branding, and palettes (public) |
| `GET` · `POST` · `DELETE /session` | Who is signed in; sign in; sign out |
| `POST /session/password` | Change your own password |
| `GET /sso/start` · `GET /sso/callback` | The single sign-on round trip, for a browser (public; 404 unless it is set up) |
| `GET` · `PUT /session/preferences` | How you want notices by email, where email is set up |
| `GET` · `POST /questionnaires` · `GET` · `PATCH /questionnaires/{key}` | Questionnaires and their versions; a changed document is published as a new version (changing them is for those who run the program) |
| `GET` · `POST /campaigns` · `POST /campaigns/preview` | Campaigns you run or may read; start one; count who one would ask |
| `GET /campaigns/{ref}` · `POST /campaigns/{ref}/remind` · `/close` · `/cancel` | One campaign with its coverage by unit and items; remind those who have not answered; end it |
| `GET /campaign-items/{id}` · `POST /campaign-items/{id}/answer` · `/excuse` | What one person is asked; answer it, as a draft or in full; take it out of the campaign |
| `GET` · `POST /indicators` · `GET` · `PATCH /indicators/{ref}` · `PUT /indicators/{ref}/owners` · `GET /indicators/{ref}/history` | Indicators with where each stands; one with its readings, trend, and the risks it warns of |
| `GET` · `POST /documents` · `GET` · `PATCH /documents/{ref}` · `PUT /documents/{ref}/owners` · `GET /documents/{ref}/history` | Policies, standards, procedures, and guidelines; one with the version in force, the one coming, and every published version |
| `POST` · `PATCH` · `DELETE /documents/{ref}/draft` · `POST /documents/{ref}/draft/file` | Start the next version, change it, discard it, or send a file as its content |
| `POST /documents/{ref}/draft/submit` · `/decision` · `/withdraw` · `/publish` | Send it to named people to approve; approve it or return it; take it back; publish it |
| `POST /documents/{ref}/review` · `/retire` · `/reinstate` | Review it and keep it as it is; take it out of use; put it back |
| `GET /documents/{ref}/versions/{id}` · `GET …/versions/{id}/file` · `GET /documents/{ref}/compare?from=&to=` | One version; its file; two versions side by side |
| `GET` · `POST /objectives` · `GET` · `PATCH /objectives/{ref}` · `PUT /objectives/{ref}/owners` · `GET /objectives/{ref}/history` · `PUT /risks/{ref}/objectives` | Strategic objectives, each with the risks that name it; the objectives a risk threatens |
| `GET` · `POST /sessions` · `GET` · `PATCH /sessions/{ref}` · `PUT /sessions/{ref}/owners` · `GET /sessions/{ref}/history` · `POST /sessions/{ref}/held` · `/cancel` | Committee sessions, with their agenda, decisions, attendees, and minutes |
| `POST /sessions/{ref}/items` · `PATCH` · `DELETE /sessions/{ref}/items/{id}` · `POST …/items/{id}/move` · `POST …/items/{id}/decision` | Put an item on the agenda (a record's reference, or a topic), change it, take it off, move it, and record the decision, which shows on the record (`decisions` on any record) |
| `GET` · `POST /framework-packs` | The frameworks that ship and which are loaded; load one by its key, or a whole pack (those who run the program) |
| `GET /frameworks/{key}/changes?from=` · `GET /frameworks/{key}/change?from=&code=` · `POST /frameworks/{key}/versions` | What changed from an earlier version, and what uses it; one requirement in both, with the words that differ; start a new version of a framework of your own |
| `POST /scopes/{ref}/frameworks/{key}/move` | Move a scope to a later version, carrying its decisions, exceptions, and the organization's crosswalks where the code is unchanged |
| `GET /frameworks/{key}/suggestions` · `POST …/suggestions/confirm` · `POST …/suggestions/set-aside` | Crosswalks a publisher's mapping suggests; map one; set one aside |
| `GET` · `POST /agreements` · `GET` · `PATCH /agreements/{ref}` · `PUT /agreements/{ref}/owners` · `GET /agreements/{ref}/history` | Agreements, open ones unless `status=closed` or `all`; one with what it covers, its terms, and the scopes they bind; change it, its dates, or its terms |
| `GET` · `POST /services` · `GET` · `PATCH /services/{ref}` · `PUT /services/{ref}/owners` · `POST /services/{ref}/links` · `DELETE /services/{ref}/links/{link_id}` · `GET /services/{ref}/history` | What third parties provide; `third_party` names the provider by reference, and filters the list |
| `POST /third-parties/{ref}/contacts` · `PATCH /contacts/{contact_id}` | The people at a third party who can be asked; contacts appear on the third party for those who keep it, assessors, and those who read everything |
| `GET /reviews` · `POST /third-parties/{ref}/reviews` · `GET` · `PATCH /reviews/{ref}` · `PUT /reviews/{ref}/owners` · `GET /reviews/{ref}/history` | Due diligence reviews (`status=open` for those not concluded, `late=true`); start one with the questionnaire the tier names unless another is given; one with its link's state, its answers, and their concerns |
| `POST /reviews/{ref}/send` · `/withdraw` · `/conclude` · `/cancel` | Send it to a contact through a new link (the address is in `meta.link.url`, this once, and emailed where email is set up); withdraw the link; record `conclusion` (`approved`, `conditions`, `declined`) and `note`; cancel it |
| `GET /assurance-kinds` · `GET` · `POST /third-parties/{ref}/assurance` · `POST /third-parties/{ref}/assurance/{document}/reviews` | The kinds of report, opinions, and judgments; a third party's reports and certificates, with their state and latest review, and whether anything in date can be relied on; add one (then send its file to `POST /evidence/{ref}/file`); review one, with `services`, `exceptions`, `responsibilities` (each `text`, `control` by reference, and `status`), and `reliance` |
| `GET /portfolio?by=&period=` | Figures by `unit`, `category`, `framework`, `third_party`, or `causes`, over a `quarter`, `half`, or `year`, each with the `path` and `filters` of the list it counts. `GET /risks?added=FROM..TO`, `GET /issues?raised=`, `closed=`, `root_cause=`, `framework=`, and `GET /exceptions?framework=` cut those lists the same way |
| `GET /leadership-reports` · `GET /leadership-reports/next?from=&to=` · `POST /leadership-reports` · `GET /leadership-reports/{ref}` | The reports issued, the latest first; the next as it stands now, not stored (managers for the whole organization); issue it with `title`, `summary`, `from`, and `to`, freezing what it says with its `fingerprint`; one as it was issued, with `check` saying whether its fingerprint still matches what it says and what the history recorded (`verified`). Read by those who read everything and those who lead the whole organization |
| `GET /as-of?type=&on=&live=` · `GET /as-of/{ref}?on=` | A register (`risk`, `control`, `issue`, `exception`, `third_party`) as it stood at the end of a day, rebuilt from the history: each record that existed then with its fields `then` and `now` and which `changed` (`live=false` for those not open or in use then as well); one record's fields then and now, its owners then and now, and how many changes there have been since |
| `GET /dossiers/{ref}` · `POST /dossiers/check` | A dossier of a scope, a risk, or a third party, as a ZIP whose `manifest.json` lists each file's size and SHA-256 and carries a `fingerprint` (taking one is recorded in the history); check one sent as the request body (up to 32 MB): `verified`, the `problems` found, the manifest, and when and by whom the history says it was taken (`recorded`) |
| `GET /scopes/{ref}/security-plan` · `GET /scopes/{ref}/oscal/ssp?framework=` · `GET /scopes/{ref}/oscal/poam` | The scope's system security plan as a page that prints by itself; the same in OSCAL 1.1.2 against one framework it is held to (needed when it is held to more than one); its plan of action and milestones in OSCAL. Each is a download |
| `GET` · `POST /scenarios` · `GET` · `PATCH /scenarios/{ref}` · `PUT /scenarios/{ref}/owners` · `PUT /scenarios/{ref}/subjects` · `GET /scenarios/{ref}/history` | Scenarios (`risk=` for those that touch a risk or process); one with what it `touches` and the `simulation` of its risks' estimates; conclude one with `status` and `conclusion`; say which risks and processes it touches |
| `GET /risks/{ref}/bow-tie` · `GET` · `POST /risks/{ref}/estimate` | A risk's causes, preventive controls, event, mitigating controls, and consequences; its estimate in ranges with its simulation and the estimates before it; estimate it anew (`frequency_low`, `_likely`, `_high`, `loss_low`, `_likely`, `_high`, `currency`, `assumptions`) |
| `GET /audit/universe?kind=&left_out=` · `GET` · `PUT /audit/universe/{kind}/{key}` | Everything worth auditing, highest ranked first, each with the `parts` of its ranking; one thing (`kind` is `unit`, `process`, `system`, `third_party`, or `scope`; `key` a unit's id or the record's reference); what audit says about it: `adjustment` with `adjustment_reason`, `last_audited_on` with `last_audit_note`, `left_out` with `left_out_reason` (auditors) |
| `GET` · `POST /audit/plans` · `GET /audit/plans/{ref}` · `POST /audit/plans/{ref}/engagements` · `/approve` · `/close` · `POST /engagements/{ref}/drop` · `/restore` | Plans for a period, drafted by auditors; one with its engagements and their counts; plan an engagement on a thing with its `reason`; approve with a `note` (an auditor who did not draft it, or a leader of the whole organization); close; drop with a `reason`, or restore |
| `GET /auditors` · `GET /engagements/{ref}` · `POST /engagements/{ref}/start` · `/advance` · `/workpapers` · `PUT /workpapers/{paper_id}` · `POST /workpapers/{paper_id}/sign-off` · `/notes` · `POST /review-notes/{note_id}/answer` · `/clear` | The auditors who may be on a team; an engagement, whose work (`workpapers`, `scope_note`) only its team sees until it is reported (`restricted`); start it with a `lead`, `members`, and `scope_note`; move it on (to reported with `summary` and `opinion`); add a step; record `done`, `found`, and `evidence`; sign off; add, answer, and clear review notes |
| `POST /engagements/{ref}/requests` · `GET /audit/requests/{request_id}` · `POST /audit/requests/{request_id}/answer` · `/accept` · `/return` | Ask the audited for something (`what`, `assignee`, `due_on`); a request, for the person asked (with the evidence already `on_file` they may answer with) or the team; answer it (`answer`, `evidence`); accept the answer, or send it back with a `reason` |
| `POST /engagements/{ref}/findings` · `GET /audit/plans/{ref}/committee-report` | Raise a finding as an issue (`name`, `summary`, `severity`, `owner_id`, `subjects`), whose closure an auditor confirms through `POST /issues/{ref}/validation`; a plan's engagements with their opinions, the findings by severity, and the findings and actions past their date |
| `GET /measures` | Every defined measure, with what it counts, its figure for the caller, the list it opens (`path` and `filters`), and the organization's trend from the daily snapshots (managers, auditors, administrators) |
| `GET /coverage` · `PUT /agreements/{ref}/parties` | Every stop the person may see, each with what is shared, through what, and the rules it fails (`needs`), with the program's sharing rules; say which third parties an agreement is with (`with` on the agreement). Information, third parties, and services carry their own `stops` |
| `POST /third-parties/{ref}/call-review` · `/offboarding` · `/offboarding/steps/{step}` · `/offboarding/cancel` · `POST /reviews/{ref}/findings` | Call for a review now (`event`, `note`); end the relationship and record each step (`access`, `information`, `agreements`, `attestation`) with a `note`; raise a finding from a review as an issue. An issue's action takes `contact_id` for one done by a third party's contact. `GET /third-parties?review=due` (or `soon`) cuts the list by review date |
| `POST /respond/files?name=` | For the holder of a link: send a report with the answers, as the request body, up to ten |
| `GET` · `PUT /respond` · `POST /respond/submit` | For the holder of a link, with no account: the token goes in the `X-RiskWren-Link` header, never in the address. What they are asked; save the answers; send them. `404` for a token that leads nowhere, `410` for one that expired, was withdrawn, or was used, and `429` after too many unknown tokens from one address |
| `GET /tiers` · `GET` · `POST /third-parties/{ref}/tiering` | The program's tiers with their rules; a third party's tiering, with the questions, what the inventory suggests, and its tierings; record one, with `tier` and `rationale` where it differs from the rules'. `GET /third-parties?tier=` cuts the list to a tier, or `none` |
| `PUT /agreements/{ref}/covers` · `POST /agreements/{ref}/close` · `/reopen` | Say what it covers (systems, information, and scopes, by reference); close it with the reason; open it again |
| `GET /documents/{ref}/governs` · `PUT /documents/{ref}/controls` · `DELETE …/controls/{id}` · `PUT /documents/{ref}/requirements` · `DELETE …/requirements/{id}` | The controls a document directs and the requirements it answers; add one (or change its note), or take it off. A requirement (`GET /frameworks/{key}/requirement`) and a control (`GET /controls/{ref}`) show the documents from their side |
| `PUT /documents/{ref}/audience` · `GET /documents/{ref}/acknowledgments` | Who it applies to (everyone, or units and roles); who has acknowledged the version they must, by unit and person (for those who keep it, assessors, and those who read everything) |
| `GET /library?q=&all=` · `GET /library/{ref}` · `POST /library/{ref}/acknowledge` | The published documents that apply to you, or every one you may read, found by their words; one as it is in force; say you have read it |
| `POST /program/preview` · `POST /program/publish` | Which open risks a change to the scoring method, appetite, or cadences would move; make the change (those who run the program) |
| `POST /risk-categories` · `PATCH /risk-categories/{key}` | Add a risk category; rename, describe, retire, or move one |
| `GET /admin/vocabularies` · `PUT /vocabularies/{name}` | Every vocabulary with what may be changed in it; rename, reorder, add to, or retire its values |
| `GET` · `POST /risk-analyses` · `POST /risk-analyses/preview` · `GET` · `PATCH /risk-analyses/{ref}` | Risk analyses; start one over a scope or a unit; how many questions one would have; one with its progress and everything it considered |
| `GET /risk-analyses/{ref}/assets/{subject}` · `POST /risk-analyses/{ref}/items/{id}` · `POST …/assets/{subject}/rest` | One thing with each threat and the risks that might answer it; answer one question; say none of the others apply |
| `POST /risk-analyses/{ref}/close` · `/reopen` | Close an analysis with what it found; reopen it |
| `GET /search` | Every kind of record, and actions, by words; only what you may open |
| `GET` · `POST /views` · `PATCH` · `DELETE /views/{id}` | Saved views of a list: yours and the shared ones |
| `GET /tidy` · `GET /similar` · `POST /tidy/not-duplicates` | What records are missing, likely duplicates, and what people who have left still hold; what a new name might already be; say two records are different things |
| `GET /accounts/{id}/holdings` · `POST /accounts/{id}/handover` | What a person answers for, with who is standing in; pass it on |
| `POST /indicators/{ref}/readings` · `PUT /indicators/{ref}/risks` · `GET /risks/{ref}/indicators` | Record what an indicator stood at on a day; say which risks it warns of; the indicators that warn of a risk |
| `POST /questionnaires/check` | Check a document without saving it, and see which questions given answers would show |
| `POST /questionnaires/{key}/responses` · `GET /responses/{id}` | Answer a questionnaire, as a draft or in full; read answers as they were asked |
| `GET /jobs` · `POST /jobs/{key}/run` · `PUT /jobs/{key}` | Scheduled work: how it is going, run one job now, pause or resume one (administrators) |
| `GET /mail` · `POST /mail/test` | How email is set up and how it is doing; send yourself a test message (administrators) |
| `GET /sso` · `POST /sso/check` · `PUT /sso/mappings` | How single sign-on is set up; whether the provider answers; which of its roles give which roles here (administrators) |

### People and units

| Route | What it does |
|---|---|
| `GET /accounts` · `POST /accounts` | Find people; add an account (admin) |
| `GET` · `PATCH /accounts/{id}` | One account; change it |
| `PUT /accounts/{id}/roles` · `PUT /accounts/{id}/units` | Set its roles and units (admin) |
| `POST /accounts/{id}/password` | Set a password for someone (admin) |
| `GET /roles` | The roles and what each allows |
| `GET /units` · `POST /units` · `GET` · `PATCH /units/{id}` | The organization's units |
| `POST /imports/units` · `POST /imports/people` | Import from CSV, with `dry_run` (admin) |

### The inventory, risks, and controls

`{records}` is one of `processes`, `systems`, `third-parties`, `information`, `risks`, or `controls`. A record is addressed by its reference, such as `SYS-0036`.

| Route | What it does |
|---|---|
| `GET /{records}` · `POST /{records}` | List; add (a steward of the unit, or a manager) |
| `GET` · `PATCH /{records}/{ref}` | One record with everything about it; change it. `external_refs` sets what it is called in other systems |
| `PUT /{records}/{ref}/owners` | Name its owners, delegates, and contacts |
| `GET /{records}/{ref}/history` | Its history |
| `POST /{records}/{ref}/links` · `DELETE /{records}/{ref}/links/{id}` | Link two inventory records; unlink them |

### Risks

| Route | What it does |
|---|---|
| `GET /risk-library` | Common risks to start from |
| `GET` · `POST /risks/{ref}/assessments` | Its assessments; record a new one |
| `PUT /risks/{ref}/subjects` | Say which processes, systems, and third parties it concerns |
| `PUT /risks/{ref}/escalation` | Escalate it to a unit above, or take it back |
| `GET` · `PUT /risks/{ref}/controls` · `DELETE /risks/{ref}/controls/{control_ref}` | The controls that bear on it, with what they suggest; link one; unlink one |

### Controls

| Route | What it does |
|---|---|
| `GET /control-library` | Common controls to start from |
| `GET` · `POST /controls/{ref}/ratings` | What is known about a control; record a new rating. Refused while a test result still holds |
| `GET` · `PUT /controls/{ref}/requirements` · `DELETE /controls/{ref}/requirements/{id}` | The requirements a control answers; map one, in full or in part; unmap one |
| `POST /controls/{ref}/requirements/suggested` | Add the mappings the library suggests for it |

### Treatment

| Route | What it does |
|---|---|
| `GET /risks/{ref}/treatment` | The response, plans, acceptances, and whether you may accept it |
| `PUT /risks/{ref}/response` | Record the response and the reason |
| `POST /risks/{ref}/plans` · `GET /plans` · `GET /plans/{ref}` | Open a plan; list plans; one plan with its actions |
| `POST /plans/{ref}/cancellation` · `POST /plans/{ref}/actions` | Cancel a plan; add an action |
| `GET /actions` · `PATCH /actions/{ref}` | List actions; progress, finish, reassign, or reschedule one |
| `POST /risks/{ref}/acceptances` | Accept the risk (a leader with the authority) |
| `GET /acceptances` · `POST /acceptances/{id}/withdrawal` | List acceptances; withdraw one |

### Frameworks and scopes

A requirement is addressed by a query, since codes such as `164.308(a)(1)(ii)(A)` do not belong in a path: `/frameworks/{key}/requirement?code=…`.

| Route | What it does |
|---|---|
| `GET /frameworks` · `POST /frameworks` | The frameworks on record; add one of your own (a manager for the whole organization, or an administrator) |
| `GET` · `PATCH /frameworks/{key}` | One framework; change or retire one of your own |
| `GET /frameworks/{key}/requirements` | One level of its tree with `parent`, or a search with `q` or `baseline` |
| `GET` · `PATCH` · `DELETE /frameworks/{key}/requirement` | One requirement in full, with the controls that answer it; change or remove one of your own |
| `POST /frameworks/{key}/requirements` · `POST …/requirements/paste` | Add a requirement; add many from pasted lines, with `dry_run` |
| `GET /frameworks/{key}/coverage` | How many requirements have a control, and which have none |
| `GET /scopes` · `POST /scopes` · `GET` · `PATCH /scopes/{ref}` | Scopes, as any other record, with `/owners` and `/history` |
| `PUT /scopes/{ref}/members` | What is inside the boundary: units and inventory records |
| `PUT /scopes/{ref}/frameworks` · `DELETE /scopes/{ref}/frameworks/{key}` | Hold it to a framework, from a baseline or from every requirement; release it |
| `GET` · `PUT /scopes/{ref}/requirements` | The statement of applicability, with `framework`, `state`, and `q`; leave a requirement out or bring it back |
| `GET` · `PUT /scopes/{ref}/controls` · `DELETE /scopes/{ref}/controls/{id}` | How each control is done in the scope; use one or say where it stands; stop using one |
| `GET /scopes/{ref}/controls/candidates` · `GET …/offered` · `POST …/inherited` | Controls that answer its requirements; controls other scopes offer; inherit one, whole or shared |
| `GET /scopes/{ref}/plan-of-action` | The open issues that bear on it, each with its actions |

### Evidence, assessments, and tests

| Route | What it does |
|---|---|
| `GET /evidence` · `POST /evidence` · `GET` · `PATCH /evidence/{ref}` | Evidence items, with `state` (`current`, `expiring`, `stale`), `/owners`, and `/history` |
| `PUT /evidence/{ref}/subjects` | Say which controls and scopes it supports |
| `POST` · `GET /evidence/{ref}/file` | Send its file as the request body; download it. A download is recorded |
| `GET /evidence-for/{ref}` | The evidence attached to a control or a scope |
| `GET /assessments` · `POST /assessments` · `GET` · `PATCH /assessments/{ref}` | Assessments; start one of a scope (an assessor or a manager); one with its tests |
| `POST /assessments/{ref}/tests` · `PATCH` · `DELETE /tests/{id}` | Add a control to it; plan a test; take one out |
| `POST /tests/{id}/results` | Record what a test found (not for a control you own) |
| `POST /results/{id}/review` | Confirm a result, or return it (not your own result, nor for a control you own) |
| `POST /assessments/{ref}/completion` · `POST …/cancellation` | Close it once every test counts; abandon it |

### Issues, exceptions, and notices

| Route | What it does |
|---|---|
| `GET /issues` · `POST /issues` · `GET` · `PATCH /issues/{ref}` | Issues, with `status` (or `live`), `severity`, `source_kind`, `about`, `age`, and `overdue`; raise one |
| `PUT /issues/{ref}/subjects` · `POST /issues/{ref}/actions` | Say what it is about; add an action |
| `POST /issues/{ref}/due-date` | Move its date, with the reason |
| `POST /issues/{ref}/closure` | Propose closure: what was done, the root cause, and evidence |
| `POST /issues/{ref}/validation` | Confirm the closure, or send it back (an assessor or a manager who does not own it) |
| `POST /issues/{ref}/cancellation` · `POST /issues/{ref}/reopening` | Withdraw one raised in error; open a closed one again |
| `GET /exceptions` · `POST /exceptions` · `GET` · `PATCH /exceptions/{ref}` | Exceptions, with `state`; ask for one to a control, or to a requirement within a scope |
| `POST /exceptions/{ref}/decision` | Approve or refuse it (a leader or a manager who did not ask) |
| `POST /exceptions/{ref}/withdrawal` | Take back a request, or end an exception early |
| `GET /notices` · `GET /notices/count` · `POST /notices/read` | What has been assigned to you or decided for you; how many are unread; mark them read |

### Import and export

| Route | What it does |
|---|---|
| `GET /exports/{list}` | Any list as `format=csv` or `format=json`, with that list's own filters. `{list}` is a record list's name, or `actions`, `plans`, `acceptances`, `requirements` (with `framework`), or `statement` (with `scope` and `framework`). Recorded in the history |
| `POST /imports/records/{records}/columns` | Send a CSV; the answer says which column is taken for which field |
| `POST /imports/records/{records}` | Import processes, systems, third parties, information, risks, or controls from CSV, with `dry_run` (the default) and `mapping` |
| `POST /imports/requirements/{key}/columns` · `POST /imports/requirements/{key}` | The same, for the requirements of one of your own frameworks |

### The program and reports

| Route | What it does |
|---|---|
| `GET /program` | Categories with appetite, the scoring method, cadences, and the acceptance table |
| `PATCH /risk-categories/{key}` | Set a category's appetite (a manager for the whole organization) |
| `GET /vocabularies` | The lists of values records choose from |
| `GET` · `PUT /admin/visibility` | How much of the register everyone sees |
| `GET` · `PUT /admin/branding` and its images | Appearance (admin) |
| `GET /home` | What is waiting on you |
| `GET /heat-map` | Risks by likelihood and impact, with `kind`, `unit`, and `category` |
| `GET /dashboard` | Where the register stands, with `unit`. Each figure comes with the filters of the list it counts |
| `GET /compliance` | Readiness by scope and framework, issues by severity and age, evidence, exceptions, and assessments in progress, with `unit` |
| `GET /graph/{ref}` | A record and everything joined to it, in groups |
| `GET /history` | Every change, newest first, with `actor`, `about`, `kind`, `since`, `until`, and `before` (managers, auditors, and administrators) |

## What the API will not do

- It never returns a record you may not see, and never counts one.
- It never edits an assessment, a control rating, a test result, or an acceptance. Each is superseded by a new one.
- It never lets a person record or confirm a test result for a control they own, confirm the closure of an issue they own, or decide an exception they asked for.
- It never imports a rating. A file can say what a risk or a control is, and not how it has been judged.
- It never changes the history. There is no route that does.
