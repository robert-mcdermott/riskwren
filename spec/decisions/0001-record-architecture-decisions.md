# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-11-25

## Context

RiskWren is meant to be adopted, adapted, and maintained by people who were not present when its design choices were made. A choice whose reasons are lost tends to be either reversed by accident or defended without understanding.

## Decision

- Significant decisions are written as short records in `spec/decisions/`, numbered in order.
- A decision is significant when it constrains future work: a dependency, a storage choice, a security mechanism, a boundary on what the product does.
- Each record has the same parts: **Status** and **Date**, then **Context**, **Decision**, **Consequences**, and **Alternatives**.
- A record is never rewritten after acceptance. When a decision changes, a new record supersedes the old one and the old one's status says so.
- Adding a runtime dependency always requires a record.

## Consequences

- The reasons behind the architecture can be read in order, in an hour.
- Changing direction costs a page of writing, which is the right amount of friction.

## Alternatives

- **No records, only commit messages:** reasons end up scattered and are hard to find.
- **A single design document kept up to date:** it loses the history of what was tried and why it changed.
