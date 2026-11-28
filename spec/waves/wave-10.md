# Wave 10: Connected (v0.10.0)

**Goal:** fit into the systems around it while staying passive: others tell RiskWren, or ask it; it never goes looking. Wave 9 gave other systems a token and told them what happens. Wave 10 lets them put results in, ask whether something is in good standing, and lets an assistant read the record and draft what a person then confirms. All of it is optional, and off until an administrator turns it on.

**Branch:** `wave-10` · **Target version:** `0.10.0` · **Status:** ◐ in progress

The security team comes first here as everywhere ([roadmap](../roadmap.md#whose-work-comes-first)). For a security team, this wave is the scanner that reports a failed check onto the control it tests, the purchasing process that asks whether a supplier has been reviewed before it buys, the ticket opened when an issue is raised, and an assistant that drafts a risk from what an engineer wrote, all without RiskWren reaching into anything.

## Exit criteria

The wave is done when, on a fresh checkout:

1. Another system posts a test result or a piece of evidence onto a control with a token; it is recorded with its source, counts as a person's would only once a person confirms it, and never overrides a person's judgment (INT-04).
2. Another process asks whether a third party, a scope, or an exception is in good standing and gets a yes, a no, or a not found, with the reasons and nothing more (INT-05); the guides give recipes for purchasing and data-access processes; webhooks can be shaped for a ticketing system or a chat channel.
3. An optional tool server lets an assistant read what its token may and draft changes that a person confirms in the app (INT-06).
4. An optional assistant, off and invisible by default, drafts risk statements and summarizes records with a provider the organization chooses, a local one included; every exchange is recorded (INT-07).
5. The role-by-route matrix covers every new route; the accessibility audit passes over every new screen.

## Slices

### Slice 1: Results pushed in ☑

- [x] A token posts a test result onto a control in a scope, or a piece of evidence onto a control, with its source (INT-04)
- [x] A pushed result waits for a person's confirmation before it counts, and never replaces one a person recorded

**Done:** `riskwren.integration.results` keeps each report as a `reported_result` row (migration 0048) with its source (the token's name), what was observed and when, an optional scope that must use the control, and where it stands. Only a token acting as a manager, an assessor, or a steward, and allowed to change things, reports; a person records results in an assessment. A report is shown on the control's page at once, under **Reported by other systems**, and in **Compliance → From other systems** for those who assess the control's unit. Confirming one takes a person (never a token) who assesses the unit and does not own the control: a partial or failed check raises an issue on the control and the scope, as a security-test finding; evidence is filed with the control for a year; a pass is kept as confirmed. Setting one aside needs a reason. None of it rates the control. The demo has three tokens for a scanner, an asset inventory, and a patch scanner, a paused service-desk webhook, and reports waiting and confirmed. The acceptance tests are in `tests/test_results.py`.

### Slice 2: A reference others can check ☑

- [x] `GET /standing/{kind}/{ref}`: yes, no, or not found, with the reasons, for a third party, a scope, or an exception (INT-05)
- [x] Recipes for a purchasing process and a data-access process
- [x] Webhook shapes for a ticketing system and a chat channel

**Done:** `riskwren.integration.standing` answers for what the asker may see, and otherwise 404. A third party is out of standing when it is not active, its review is overdue, or the coverage rules find information shared with it that no required agreement covers; a scope when it is not active, a control it uses failed a test, or a critical or high issue about it is past its date; an exception whenever it is not in force. Each reason has a code and a sentence, and nothing of the record's contents. A webhook has a `format`: the plain message, a ticket (`title`, `description`, `link`), or a chat message (`text`), each still naming only the event and the record. The API guide has recipes for purchasing, data access, deployments, ticketing, and chat. The tests are in `tests/test_results.py` and `tests/test_integration.py`.

### Slice 3: Tool server for assistants ☐

- [ ] `riskwren tools`: a Model Context Protocol server over standard input and output, acting with a token (INT-06)
- [ ] Tools that read: search, a record, a risk with its controls, a scope's readiness, what is overdue
- [ ] Tools that draft: a risk, an issue, a control; each a draft a person opens, changes, and confirms, or sets aside

### Slice 4: Optional assistant ☐

- [ ] `[assistant]` in the configuration: off by default; when off, nothing of it is installed (INT-07)
- [ ] Providers by protocol: the OpenAI-compatible API (which local servers speak), Anthropic's Messages API, and Amazon Bedrock's Converse API; keys only from the environment
- [ ] Draft a risk statement from a description; summarize a record; both from what the asker may see, and only from data classes the program allows
- [ ] Every exchange recorded in the history; a daily limit per person; Admin → Assistant to check the connection and read the log

### Slice 5: Release prep ☐

- [ ] Guides, changelog, upgrade from 0.9.0 on both databases, audits, release, and the site republished

## Decisions

Made on 2026-11-27 without the user, under their go-ahead to build waves 9 and 10 while they were away; each is open to their review. The assistant follows the pattern the user pointed to in another of their projects, with its known weaknesses addressed.

- **Pushed results are proposals until a person confirms them.** A scanner's failure is shown on the control at once, as reported by its source, but readiness and ratings move only when an assessor confirms it, the same second pair of eyes a person's result needs.
- **The reference says yes or no, never why in detail.** A purchasing process learns that a supplier is not in good standing and the reason's kind (no review in date, a gap in coverage), not the review's contents.
- **Drafts are records of their own,** never half-made records: a person confirms a draft through the ordinary form, so every rule applies, and a draft set aside leaves nothing behind.
- **Providers are named by protocol, called over plain HTTP,** with no vendor library. Keys come from the environment only; a key in the file is refused.
- **The assistant reads through the API as the asker,** with their cookie or their token, so it can never see more than they may; and it is sent only what the program's data classes allow.

## Notes

- Nothing in this wave reaches out except a webhook's message and a call to the provider an administrator configured.
