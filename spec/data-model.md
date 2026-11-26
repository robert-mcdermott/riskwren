# Data model

RiskWren keeps everything in one relational database, SQLite by default and PostgreSQL in production, behind one SQLAlchemy model and one Alembic migration history. Files (evidence, attachments, logos) live on disk in the data home, addressed by their hash; the database holds their metadata.

This document describes the entities, how they relate, and the rules that apply to all of them. Column-level detail lives in the models and migrations; when they change, this document changes in the same commit. Entities are marked with the wave that introduces them; those of later waves are sketched and will be detailed when their wave is planned.

## Conventions

- **Two identifiers per record.** Every row has an integer primary key used for joins. Every record a person might cite also has a **reference**: a short, permanent, human-readable key with a type prefix and a sequence number (`RSK-0142`). References never change and are never reused. They are what a committee paper, an audit report, or an email cites.
- **Timestamps** are UTC, stored as timezone-aware values, shown in the viewer's time zone. Dates that are only dates (a due date, a valid-until date) are stored as dates.
- **Vocabularies are data.** Any field described below as "a vocabulary" (criticality, data class, system kind, control kind, root cause, and so on) draws its values from a settings-backed list the organization can rename, extend, and retire. Rows keep the stable key of the value, never its label, so renaming a value never rewrites history.
- **JSON columns** hold structured values whose shape is defined by configuration (the scoring method, an assessment's levels by dimension, questionnaire answers). They are stored through SQLAlchemy's portable JSON type and never queried with database-specific operators; anything that needs filtering or sorting is a real column.
- **Soft deletion only.** Records are closed, retired, or archived, never deleted, so references and history stay valid. Drafts that were never submitted can be discarded by their author.
- **Judgments are never edited.** Assessments, control ratings, test results, acceptances, approvals, and attestations are statements by a person at a time. A correction is a new row that supersedes the old one.
- **Every write is an event.** No table is written except through the service layer, which records an event in the same transaction (see [History](#history)).
- **Optimistic concurrency.** Editable records carry a version number; a change made against an older version is refused.

| Prefix | Record | Wave | Prefix | Record | Wave |
|---|---|---|---|---|---|
| `PRC` | Process | 1 | `ASM` | Assessment | 2 |
| `SYS` | System | 1 | `EV` | Evidence | 2 |
| `TP` | Third party | 1 | `ISS` | Issue | 2 |
| `RSK` | Risk | 1 | `EXC` | Exception | 2 |
| `CTL` | Control | 1 | `IND` | Indicator | 3 |
| `PLN` | Treatment plan | 1 | `POL` | Policy document | 4 |
| `ACT` | Action | 1 | `AGR` | Agreement | 4 |
| `INF` | Information asset | 2 | `AUD` | Audit engagement | 7 |
| `SCP` | Scope | 2 | `INC` | Incident | 8 |

## Overview

```text
                         ┌────────────┐
                         │  Org unit  │◀── parent
                         └─────┬──────┘
                 belongs to    │     owners, stewards, leaders
        ┌──────────────┬───────┴───────┬────────────────┐
        ▼              ▼               ▼                ▼
  ┌───────────┐  ┌───────────┐  ┌─────────────┐  ┌─────────────┐
  │  Process  │─▶│  System   │─▶│ Third party │  │ Information │
  └─────┬─────┘  └─────┬─────┘  └──────┬──────┘  └──────┬──────┘
        └──────────────┴───── concerns ┴────────────────┘
                               ▲
                         ┌─────┴─────┐  reduced by   ┌───────────┐  satisfies  ┌─────────────┐
                         │   Risk    │──────────────▶│  Control  │────────────▶│ Requirement │
                         └─────┬─────┘               └─────┬─────┘             └──────┬──────┘
          assessment · plan    │          rating · test    │     implementation       │ of a
          acceptance · action  ▼                           ▼     within a ──▶ Scope   ▼
                                                       Evidence                   Framework
                                   Issue ──▶ Action          Exception
```

## Organization and people (wave 1)

### Org unit

The organization as a tree: `org_unit(id, parent_id, kind, name, code, status)`. `kind` is a vocabulary (by default: organization, division, department, center, core facility, lab, clinic, office). There is one root. A unit may be closed, which keeps its records and history but removes it from pickers.

Units are the backbone of scoping. Every process, system, risk, and control belongs to exactly one unit, and a role can be granted for a unit, which then covers every unit beneath it.

### Account

`account(id, email, display_name, title, status, time_zone)` is a person who can sign in or be named on a record. An account can exist before its person has ever signed in (created by an import or by being named as an owner), in which case it is *invited*.

- `credential` holds a local password hash for accounts that have one.
- `membership(account_id, org_unit_id, title, is_primary)` records which units a person works in. It drives defaults and what a member can see; it grants nothing else.
- `session_token` and `failed_sign_in` support sign-in and are not history.
- From wave 3: `identity(account_id, issuer, subject)` links an account to a single sign-on identity, and `provider_mapping` says which of the provider's groups or application roles gives which role here.

### Roles

`role_grant(account_id, role, org_unit_id?, accept_limit?, source)`.

| Role | Line | What it allows |
|---|---|---|
| `admin` | — | Accounts, sign-in settings, branding, and system configuration. Not, by itself, the right to assess or accept anything |
| `manager` | Second | Run the program: edit any record, manage the taxonomy, scoring method, appetite, cadences, libraries, frameworks, and campaigns |
| `assessor` | Second | Record assessments and (wave 2) tests for records in scope; read what is needed to do so |
| `auditor` | Third | Read everything, including the full history; change nothing outside audit's own records (wave 7) |
| `leader` | First | Read everything in their unit and beneath it; accept risks up to the limit on their grant |
| `steward` | First | Keep their unit's records current: add and edit records, reassign owners, and answer for the unit's completeness |
| `member` | First | Read what is published to everyone, see and do what is assigned to them, and report |

`manager`, `assessor`, `leader`, and `steward` grants may be limited to a unit, which covers everything beneath it; without a unit they cover the organization. Being an **owner** of a record is not a role: it is a relationship on the record, and it carries the right to edit that record and the duty to keep it current. See [security.md](security.md).

## The things risk attaches to

All three wave 1 record types share a header: `ref`, `name`, `summary`, `org_unit_id`, `status` (active, retired), `criticality` (a vocabulary, ordered), `data_class` (a vocabulary, ordered: the highest class of data handled), `tags`, `restricted`, `version`, and timestamps. What differs between record types is described once, in a registry, so that adding, editing, listing, owners, links, visibility, and history are written once for all of them.

- **Process** (wave 1): `process(…, kind, purpose)`. Something the organization does: a research service, a clinical service, an administrative process. `kind` is a vocabulary.
- **System** (wave 1): `system(…, kind, hosting, lifecycle)`. An application, platform, instrument, device, or piece of infrastructure. `hosting` and `lifecycle` are vocabularies.
- **Third party** (wave 1): `third_party(…, kind, website, standing)`. A supplier, collaborator, sponsor, or subrecipient. Wave 5 adds tier, services, contacts, and reviews.
- **Information asset** (wave 2): `information_asset(…, categories, identifiability, held_in, shared_with)`.
- **Site** (wave 8).

### Owners

`record_owner(record_type, record_id, account_id, kind)`. `kind` is a vocabulary: by default *owner* (accountable), *delegate* (acts for the owner and may edit), and *contact*. Whoever adds a record becomes its owner until they name someone else, and the owners of a record can never be set to a list without one. A record whose every owner's account is disabled, or which was imported with nobody named, is **orphaned**, which is shown on the record and in every list.

### Links

`record_link(from_type, from_id, relation, to_type, to_id, note)`. `relation` is a vocabulary of named relationships, each with a forward and a reverse label and the pairs of record types it may join. A link's changes appear in the history of the record it starts from.

| Kind (default) | From → to | Reads as |
|---|---|---|
| `relies_on` | Process → System | relies on / supports |
| `supplied_by` | System → Third party | supplied by / supplies |
| `performed_by` | Process → Third party | performed by / performs |
| `depends_on` | System → System, Process → Process | depends on / is depended on by |
| `part_of` | System → System, Process → Process | is part of / includes |
| `holds` | System → Information asset (wave 2) | holds / is held in |

### Tags

Free labels, for whatever the vocabularies do not cover, kept as a list on the record.

## Risk (wave 1)

### Category

`risk_category(id, parent_id, key, name, description, appetite, status, position)`. A tree. `appetite` is the key of the highest acceptable residual rating and is set on top-level categories; lower levels use their parent's unless they set their own.

### Scoring method

`scoring_method(id, version, status, definition, published_at, published_by)`. `definition` is the JSON document described in [engine.md](engine.md): likelihood levels, impact dimensions and levels, the matrix, the ratings, and the control-effect weights. One version is *current*; earlier versions remain because assessments refer to them.

### Risk

`risk(ref, name, cause, event, consequence, category_id, org_unit_id, status, closed_reason, response, inherent_*, residual_*, target_*, standing, next_review_on, residual_in_doubt, escalated_to_unit_id, library_key, version, …)`. `name` is its short title.

- `status`: draft, open, closed.
- `response`: a vocabulary (reduce, accept, transfer, avoid), with a rationale.
- The `*_likelihood`, `*_impact`, and `*_rating` columns are **copies** of the latest assessment of each kind, kept on the risk so lists and the heat map are fast. The assessments are the authority.
- `standing` is worked out by the service from the rating, the appetite, and the state of plans and acceptances (see [engine.md](engine.md#appetite-and-standing)), and stored so that it can be filtered.
- `risk_subject(risk_id, subject_type, subject_id)`: the processes, systems, and third parties a risk concerns.

### Assessment of a risk

`risk_assessment(id, risk_id, kind, likelihood, impact, impact_levels, rating, rationale, suggested, method_id, assessed_by, assessed_by_name, assessed_at, superseded_by)`. The assessor's name is kept as it was, so the record reads the same after an account is renamed.

- `kind`: inherent, residual, target.
- `impact_levels`: the level chosen on each dimension rated.
- `suggested`: for a residual assessment, the suggestion the engine made and its working (each control, its strength, its weight), so the reasoning can be shown later exactly as it was.
- Never updated after it is written, except to set `superseded_by`.

### Risk library

`risk_library(key, category_key, title, cause, event, consequence, suggested_controls, source_pack)`: reusable statements loaded from packs. Starting a risk from a library entry copies its text, which the author then makes specific.

## Controls (wave 1)

### Control

`control(ref, title, statement, objective, kind, nature, frequency, org_unit_id, status, is_key, design, operation, strength, rated_at, library_key, source_pack, version, …)`.

- `kind` (preventive, detective, corrective, directive), `nature` (manual, automated, both), and `frequency` are vocabularies.
- `design`, `operation`, `strength`, and `rated_at` are copies of the latest rating.

### Control rating

`control_rating(id, control_id, design, operation, basis, note, rated_by, rated_at, test_id?, superseded_by)`. `basis`: judgment, attestation (wave 3), test (wave 2). Never updated after it is written.

### Risk and control

`risk_control(risk_id, control_id, reduces, reliance, note)`. `reduces`: likelihood, impact, both. `reliance`: primary, supporting.

## Treatment (wave 1)

- **Treatment plan:** `treatment_plan(ref, risk_id, objective, target_rating, owner_id, due_on, status, …)`. Status: draft, active, complete, cancelled.
- **Acceptance:** `acceptance(id, risk_id, rating_accepted, rationale, conditions, accepted_by, accepted_at, expires_on, withdrawn_at, withdrawn_reason)`. Never edited; it may be withdrawn, which is itself recorded.
- **Action:** `action(ref, title, detail, owner_id, due_on, original_due_on, extensions, status, source_type, source_id, completed_at, completion_note, …)`. One table for every action in the product, whatever it came from: a treatment plan in wave 1; an issue, an incident, an exercise, or an audit finding later. Status: open, in progress, done, cancelled.

## Compliance (wave 2)

- **Framework:** `framework(id, key, title, version, publisher, license, text_policy, attribution, source_url, pack_version, kind, status)`. `kind`: standard, regulation, agreement, internal.
- **Requirement:** `requirement(id, framework_id, parent_id, code, title, text, summary, position, is_citable, status)`. A tree; codes are stable across pack versions.
- **Baseline:** `baseline(id, framework_id, key, title)` with `baseline_requirement`: a published selection from a framework.
- **Crosswalk:** `control_requirement(control_id, requirement_id, coverage, note, source)`. `coverage`: full, partial. `source`: pack, person.
- **Scope:** `scope(ref, name, summary, org_unit_id, status, offers_controls, …)`, with `scope_member(scope_id, subject_type, subject_id)` for what is inside the boundary and `scope_framework(scope_id, framework_id, baseline_id?)` for what it must meet.
- **Applicability:** `scope_requirement(scope_id, requirement_id, applicable, reason, decided_by, decided_at)`.
- **Implementation:** `implementation(id, scope_id, control_id, status, responsibility, statement, parameters, inherits_from_id?, inheritance, …)`. `inheritance`: none, inherited, shared.
- **Assessment:** `assessment(ref, scope_id, title, framework_id?, baseline_id?, lead_id, period_start, period_end, status, …)`.
- **Test:** `test(id, assessment_id, implementation_id, procedure, method, sample, design, operation, note, tested_by, tested_at, reviewed_by, reviewed_at, superseded_by)`.
- **Evidence:** `evidence(ref, title, kind, file_id?, url?, note?, owner_id, collected_on, covers_from, covers_to, valid_until, data_class, …)` with `evidence_link(evidence_id, subject_type, subject_id)`; `file(sha256, size, media_type, original_name)`.
- **Issue:** `issue(ref, title, description, severity, source_kind, source_type, source_id, org_unit_id, owner_id, due_on, original_due_on, extensions, status, root_cause, closure_note, validated_by, validated_at, …)` with `issue_subject` linking it to controls, requirements, scopes, and risks.
- **Exception:** `exception(ref, subject_type, subject_id, scope_id?, justification, compensating, requested_by, decided_by, decision, starts_on, expires_on, status, …)`.
- **Notice:** `notice(account_id, kind, subject_type, subject_id, text, created_at, read_at)`.

## Later waves (sketch)

| Wave | Entities |
|---|---|
| 3 | `job`, `campaign`, `campaign_item`, `attestation`, `questionnaire`, `questionnaire_version`, `response`, `indicator`, `indicator_reading`, `mail_outbox`, `saved_view`, `search_doc`, `identity`, `provider_mapping` |
| 4 | `policy_document`, `policy_version`, `policy_approval`, `acknowledgment`, `agreement`, `agreement_coverage`, `objective`, `session`, `session_item` |
| 5 | `service` (what a third party provides), `third_party_contact`, `tier_assessment`, `review` (due diligence), `respondent_link`, `assurance_review` |
| 6 | `measure_snapshot`, `report`, `scenario`, `estimate` |
| 7 | `audit_entity`, `audit_plan`, `engagement`, `workpaper`, `request_item`, `external_access` |
| 8 | `incident`, `case`, `case_member`, `breach_assessment`, `notification`, `loss_event`, `impact_analysis`, `continuity_plan`, `plan_version`, `exercise`, `site` |
| 9 | `api_token`, `webhook`, `webhook_delivery`, `custom_field` |

## Program settings

`setting(key, value, version, updated_by, updated_at)` holds everything the program team configures that is not a table of its own: vocabularies, cadences, the authority table, severity clocks, visibility, and branding. Each change is an event. The whole program (settings, categories, the scoring method, libraries) exports and imports as a **program pack** ([content-packs.md](content-packs.md)).

## History

`event(seq, at, actor_id, actor_label, action, subject_type, subject_id, subject_ref, changes, context, prev_hash, hash)`.

- Written by the session, not by hand: after each flush, every new, changed, and deleted row of an audited model becomes an event in the same transaction, with each changed field's value before and after.
- `action` names the operation in the service's own words (`risk.assess`, `acceptance.record`), so a history reads as what people did, not as row changes.
- `context` ties together the events of one operation and records what the change was part of.
- Append-only: the application never updates or deletes an event, and triggers on both databases refuse it. Each event's hash covers its content and the previous hash; `event_head` holds the tip under a lock so numbering has no gaps.
- A record as of a date is rebuilt by replaying its events (wave 6).

## Reference counters

`ref_counter(prefix, next)` hands out numbers per prefix under a lock. A number is never reused, even if the row that took it is rolled back.
