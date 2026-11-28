# Wave 10: Connected (v0.10.0)

**Goal:** fit into the systems around it while staying passive: others tell RiskWren, or ask it; it never goes looking. Wave 9 gave other systems a token and told them what happens. Wave 10 lets them put results in, ask whether something is in good standing, and lets an assistant read the record and draft what a person then confirms. All of it is optional, and off until an administrator turns it on.

**Branch:** `wave-10` · **Target version:** `0.10.0` · **Status:** ☑ done

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

### Slice 3: Tool server for assistants ☑

- [x] `riskwren tools`: a Model Context Protocol server over standard input and output, acting with a token (INT-06)
- [x] Tools that read: search, a record, a risk with its controls, a scope's readiness, what is overdue
- [x] Tools that draft: a risk, an issue, a control; each a draft a person opens, changes, and confirms, or sets aside

**Done:** `riskwren.integration.tools` is one set of tools, each calling RiskWren's own API through a small interface, so the tool server and the assistant in the app (slice 4) share them and neither can see more than the asker. `riskwren.integration.mcp` speaks JSON-RPC 2.0 one message to a line, with `initialize`, `ping`, `tools/list`, and `tools/call`, by hand rather than with a library; the protocol is small and the server only answers. `riskwren tools --url` takes the token from `RISKWREN_TOKEN` only, wants `https://` away from the same computer, and `--no-drafts` leaves out the drafting tools. Drafts are `draft` rows (migration 0049) listed under **Drafts** for those who may add that kind of record in its unit; **Open** puts a draft in the ordinary form for a risk, an issue, or a control, and saving it marks the draft as used, naming the record, which must be one the same person made after the draft was proposed. The demo's security engineer has a desktop assistant with a reading token that has drafted a risk and an issue. The tests are `tests/test_drafts.py`.

### Slice 4: Optional assistant ☑

- [x] `[assistant]` in the configuration: off by default; when off, nothing of it is installed (INT-07)
- [x] Providers by protocol: the OpenAI-compatible API (which local servers speak), Anthropic's Messages API, and Amazon Bedrock's Converse API; keys only from the environment
- [x] Draft a risk statement from a description; summarize a record; both from what the asker may see, and only from data classes the program allows
- [x] Every exchange recorded in the history; a daily limit per person; Admin → Assistant to check the connection and read the log

**Done:** `riskwren.assistant` holds the providers (each a plain HTTP call, no vendor library; Bedrock signed with Signature Version 4 from the standard library, or a Bedrock API key), and the service. While `enabled` is false its routes are not mounted, the session says so, and the app neither shows nor loads anything of it. When on, **Summarize** sits beside **Connections** on every record's page, and **Draft with the assistant** on the register: a description becomes a draft that opens in the ordinary **Raise a risk** form. Both use the tools of slice 3 through RiskWren's own API in the same process, with the asker's cookie and CSRF token or their token, so a token reaches the assistant as itself. Everything a tool reads passes `withhold`, which turns a restricted record, and a record whose data class is not in `send`, into its reference and why. Each exchange is an `assistant_exchange` row (migration 0050), written before the provider is asked with the asker's account or token row locked while the day's exchanges are counted, so the limit holds under concurrency, and written again when it ends, both as events in the hash-chained history. One overall time limit covers every call; six rounds of tools at most. **Admin → Assistant** shows the setup, checks the connection, and lists the log. The API's own documents and the role-by-route matrix are made with the assistant on. Tried end to end against a small model running on the same computer: the connection check, a summary through three tools, and a drafted risk opening in the form. The tests are `tests/test_assistant.py`, with a scripted provider: nothing is sent anywhere.

### Slice 5: Release prep ☑

- [x] Guides, changelog, upgrade from 0.9.0 on both databases, audits, release, and the site republished

**Done:** version 0.10.0; the changelog's introduction and upgrade notes; the README's account of the release; the guides' index, with its questions and what this release does not do yet; a section on the site's home page for the connections; every picture taken again, with From other systems and Drafts new. The upgrade from 0.9.0 was run from that release's own code with its demo organization on both databases: migrations 0048 to 0050 applied, every row of every table unchanged, the history verifies, the old webhook kept the plain format, and a token's report, an assessor's confirmation raising an issue, a standing check, and a draft from a reading token ran over the old data; a second upgrade changed nothing. The whole suite passed (761 tests). The accessibility audit found nothing in 325 scenes, the screen-reader check nothing in fifteen journeys, the keyboard check nothing, and the site's audit nothing in nineteen pages.

## Decisions

Made on 2026-11-27 without the user, under their go-ahead to build waves 9 and 10 while they were away; each is open to their review. The assistant follows the pattern the user pointed to in another of their projects, with its known weaknesses addressed.

- **Pushed results are proposals until a person confirms them.** A scanner's failure is shown on the control at once, as reported by its source, but readiness and ratings move only when an assessor confirms it, the same second pair of eyes a person's result needs.
- **The reference says yes or no, never why in detail.** A purchasing process learns that a supplier is not in good standing and the reason's kind (no review in date, a gap in coverage), not the review's contents.
- **Drafts are records of their own,** never half-made records: a person confirms a draft through the ordinary form, so every rule applies, and a draft set aside leaves nothing behind.
- **A token that may only read may still draft.** A draft changes nothing until a person makes a record of it, so the safest token for an assistant, one that may only read, is enough. It is the one change such a token may send.
- **Providers are named by protocol, called over plain HTTP,** with no vendor library. Keys come from the environment only; a key in the file is refused.
- **The assistant reads through the API as the asker,** with their cookie or their token, so it can never see more than they may; and it is sent only what the program's data classes allow.

- **A token that may only read may also ask the assistant.** It only reads and drafts, and the exchange is recorded under the token's name.
- **The assistant's answers are shown, not kept on the record.** A summary is a reading aid; the record says what the organization decided. Only a draft can become a record, through a person.
- **No streaming.** Each provider is asked for a whole answer: simpler, the same for all three protocols, and the answers are short.

## Notes

- Nothing in this wave reaches out except a webhook's message and a call to the provider an administrator configured.
