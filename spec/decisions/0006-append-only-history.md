# ADR-0006: An append-only, hash-chained history

- **Status:** Accepted
- **Date:** 2026-11-25

## Context

A risk and compliance record is only useful to an auditor, a regulator, or a court if it can be shown that it was not changed after the fact. People also need ordinary answers from history: who changed this rating, what did this risk say when it was accepted, what did the register look like last June.

## Decision

- **Every write records an event** in the same transaction: actor, time, action, subject, each changed field with its value before and after, and what the change was part of.
- **Events are recorded by the session, not by hand.** After each flush, the session turns every new, changed, and deleted row of an audited model into an event. Services cannot forget, and the ways around it are refused: flushing changes with no actor, and bulk statements against audited tables.
- **The event table is append-only.** The application never updates or deletes a row, and triggers in the database refuse both, on SQLite and on PostgreSQL.
- **Events are chained by hash.** Each event's hash covers its content and the previous event's hash. An event's number is its place in the chain, assigned under a lock on a single head row, so concurrent writers take turns and the numbering has no gaps. `riskwren verify` recomputes the chain and reports the first break. The latest hash can be exported on a schedule to somewhere the database administrator cannot write.
- **Current-state tables are the fast path; the event log is the authority for the past.** A record as of a date is rebuilt by replaying its events.
- **Assessments, ratings, test results, acceptances, and attestations are never edited.** A correction is a new entry that supersedes the old one.
- **Reads of sensitive things are events too:** evidence downloads, exports, and views of restricted records.

## Consequences

- Any record's full story can be shown, and any past state reconstructed, without separate audit tables per entity.
- Tampering outside the application is detectable. It is not prevented: someone with full control of the database could rewrite the whole chain, which is why the exported hash matters and why the guide says to keep it elsewhere.
- The event table grows without bound. At RiskWren's write rate this is megabytes per year; no pruning is offered.
- Personal data in events (names, email addresses of actors) is kept as long as the record is. An account can be disabled and its display name replaced, but its actions stay attributed to a stable account key.
- Field changes must be serializable, which constrains how JSON columns are compared and stored.

## Alternatives

- **An audit table per entity:** many tables, easy to forget one, and no single chain.
- **Full event sourcing with no current-state tables:** elegant, but every list and report would be a projection to maintain, for no benefit at this scale.
- **Database-level change capture:** specific to one database, and it records row changes without who or why.
