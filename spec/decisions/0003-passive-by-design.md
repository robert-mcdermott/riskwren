# ADR-0003: Passive by design

- **Status:** Accepted
- **Date:** 2026-11-25

## Context

There are two ways for a risk and compliance system to learn whether controls are working. It can go looking: connect to cloud accounts, identity providers, endpoints, and scanners, and collect evidence on a schedule. Or it can be told: by people, by documents, and by other systems that choose to send it something.

Going looking produces fresher evidence with less human effort. It also needs standing credentials to the organization's most sensitive systems, a library of connectors that must each be maintained as those systems change, a long security review to deploy, and a much larger product. A system that holds a map of an organization's weaknesses *and* credentials to its infrastructure is a very attractive target.

Most of the value of a risk and compliance program lies elsewhere: in the register, the mapping of obligations to controls, the judgment recorded in assessments, and the follow-through on issues. None of that needs a connection to anything.

## Decision

RiskWren is passive, and the word has a precise meaning.

**RiskWren never:**

- inspects network traffic or reads logs;
- installs anything on endpoints;
- scans systems, code, cloud accounts, or software tenants, for vulnerabilities or for anything else;
- holds credentials to another system for the purpose of reading from it;
- blocks, changes, or sits in the path of anything.

**RiskWren learns only from:**

- what people enter: risks, assessments, ratings, test results, attestations, reports;
- documents people attach as evidence;
- spreadsheets people import;
- and, from wave 10, what another system deliberately **pushes** to it through the API: a test result or a piece of evidence posted onto a control by a script or tool the organization runs. A pushed result is recorded with its source, labelled as such, and never overrides a person's judgment.

Currency is reached through process, and the product is designed to make that process work: a home page of what each person owes, cadences in proportion to what is at stake, campaigns that chase themselves, evidence that goes stale on a date, and a refusal to count anything that nobody has checked.

## Consequences

- RiskWren can be deployed with no access to anything else, which makes it quick to approve and safe to run.
- It is honest about its limits: it shows what has been attested or tested and when, and never claims to know what it was not told.
- Evidence is as fresh as the people and scripts that supply it. The cadence table and the stale-evidence rule make that visible rather than hiding it.
- An organization that wants automated collection writes a small script against the push endpoint, or runs a separate tool for it and pushes the results.
- Requests to add scanning are declined by pointing here. The roadmap lists them under *Never*. Scheduled read-only collection from a named source is listed under *Later* and would need a decision record that supersedes part of this one.

## Alternatives

- **Connectors as a core feature:** the most-requested capability in this kind of product, and the one that turns it into a different, much larger one, with credentials to guard and integrations to maintain for every adopter, including those who never enable them.
- **Passive with no programmatic door at all:** simpler still, but it would force organizations that already produce machine-readable results to retype them.
