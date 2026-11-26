# ADR-0007: Program rules and content as data

- **Status:** Accepted
- **Date:** 2026-11-25

## Context

No two organizations rate risk the same way, and no organization is held to the same obligations two years running. Taxonomies, scales, appetite, cadences, who may accept what, controls, frameworks, and vocabulary all differ and all change. If any of them lived in code, every adopter would need a developer, and every change would need a release.

At the same time, rules that people can edit must not become a way to run arbitrary code, and a rating given under last year's scale must remain explainable.

## Decision

- **Everything that expresses the program is data:** vocabularies, the risk taxonomy and appetite, the scoring method, cadences, the authority table, severity clocks, risk and control libraries, frameworks and their crosswalks, and questionnaires.
- **It is edited in the app** by the manager and admin roles, with previews.
- **It is versioned.** A published scoring method or questionnaire version is immutable. Every assessment and response records the version it was made under.
- **The scoring method is a document, not a formula.** Levels have written definitions; likelihood and impact are combined by a matrix lookup; the effect of controls is a small table of weights and a limit. There are no expression strings, and nothing is ever evaluated as code.
- **One declarative condition language** serves applicability rules, questionnaire visibility, and tiering. It is a small tree of `all`, `any`, `not`, and comparisons over named fields and answers.
- **The scoring arithmetic and the condition evaluator each exist twice**, in Python for authority and in JavaScript for live previews, held together by shared files of test cases that both must pass.
- **Content moves as packs.** A program pack carries an organization's whole configuration; content packs carry libraries, frameworks, and questionnaires ([content-packs.md](../content-packs.md)).
- **RiskWren ships a complete default program**, so a new installation works on its first day and editing is optional.
- **Changes are previewed against real records** before publishing: the app lists which existing risks would change rating, standing, or dates.

## Consequences

- An adopter shapes RiskWren to its own program without touching code, and can share that shape with another organization as a file.
- Behavior depends on configuration, so support and testing must consider it: the default program has its own tests, and `riskwren doctor` validates the active configuration.
- The scoring method is deliberately limited. A way of rating that cannot be expressed in it is a signal to add a field to the method, not an escape hatch.
- Two implementations are a duplication to keep in step; the shared cases make drift a test failure.

## Alternatives

- **Rules in code with configuration flags:** simple to build, and every adopter's program becomes a fork.
- **An embedded scripting or formula language:** flexible, and it turns anyone who can edit a scale into someone who can run code on the server.
- **Custom object types and fields without limit:** the approach of the largest platforms, and the reason they need administrators and consultants. RiskWren fixes the shape of the record and lets the content vary.
