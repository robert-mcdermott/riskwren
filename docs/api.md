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
    "permissions": ["…"],
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
| `q` | Words to look for in the name, reference, or summary |
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

`{records}` is one of `processes`, `systems`, `third-parties`, `risks`, or `controls`. A record is addressed by its reference, such as `SYS-0036`.

| Route | What it does |
|---|---|
| `GET /{records}` · `POST /{records}` | List; add (a steward of the unit, or a manager) |
| `GET` · `PATCH /{records}/{ref}` | One record with everything about it; change it |
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
| `GET` · `POST /controls/{ref}/ratings` | What is known about a control; record a new rating |

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

## What the API will not do

- It never returns a record you may not see, and never counts one.
- It never edits an assessment, a control rating, or an acceptance. Each is superseded by a new one.
- It never changes the history. There is no route that does.
