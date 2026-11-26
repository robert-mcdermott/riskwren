# ADR-0005: One relational database, on SQLite or PostgreSQL

- **Status:** Accepted
- **Date:** 2026-11-25

## Context

RiskWren must be trivial to try and dependable in production. Someone evaluating it should not need to install a database server. An organization running it for hundreds of people wants the database its operations team already backs up and monitors.

RiskWren's data is relational and modest in size: thousands to tens of thousands of records, and an event log that grows by a few per change.

## Decision

- **One relational database holds everything except file contents.**
- **SQLite is the default**, as a single file in the data home, in write-ahead-log mode with foreign keys enforced. It is a supported way to run a small installation, not only a way to try RiskWren.
- **PostgreSQL is supported for production**, selected by a database URL, with its driver as an optional extra.
- **SQLAlchemy 2 ORM** with declarative, typed models and a synchronous session per request.
- **Alembic** for migrations, driven from inside the package, written to run on both databases, and applied only when an administrator asks.
- **Portability is a rule, not a hope:**
  - only portable column types, through two custom types for JSON and UTC date-times;
  - no database-specific SQL in application code; JSON columns are never queried with operators, and anything filtered or sorted is a real column;
  - a fixed naming convention for constraints, so migrations match on both;
  - the whole test suite runs on both databases in continuous integration from the first commit.
- **Moving between them** is an export and an import, which is also the backup format.

## Consequences

- A working system from three commands, and a clear path to production without changing code or losing data.
- Features that exist in only one database are not used: no full-text search extension, no JSON indexes. Search uses an ordinary table ([architecture.md](../architecture.md)).
- SQLite allows one writer at a time. For RiskWren's write volume this is not a limit in practice; the guide says when to move to PostgreSQL (many concurrent users, several server processes under load, or an operations team that requires it).
- The append-only rule on the event table is enforced by the application and by triggers, written once for each database.

## Alternatives

- **PostgreSQL only:** simpler to build, but it puts a server installation in front of every first look.
- **SQLite only:** simplest, but many organizations will not run a production service on it.
- **A document database:** the data is relational, and reports are joins.
- **Adding PostgreSQL later:** retrofitting a second database after the code has leaned on the first costs far more than keeping both honest from the start.
