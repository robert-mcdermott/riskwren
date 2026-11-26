# RiskWren specification

> **Risk and compliance people actually keep current.**

This folder is RiskWren's public planning space: the product vision, the architecture, the decisions behind it, and the roadmap we build against. It is the source of truth for *what* we are building and *why*. Code says *how*.

## Start here

| Document | What it answers |
|---|---|
| [vision.md](vision.md) | What RiskWren is, who it serves, what makes it different, and what it deliberately is not |
| [requirements.md](requirements.md) | The capability catalog, with IDs, priorities, and the wave that delivers each |
| [engine.md](engine.md) | How a risk is rated, how controls move it, appetite and standing, acceptance, cadences, and readiness |
| [data-model.md](data-model.md) | The records, how they relate, and the append-only history |
| [content-packs.md](content-packs.md) | The default program, libraries, and frameworks as data; what text may be shipped |
| [architecture.md](architecture.md) | System shape: layers, components, storage, configuration, and the dependency budget |
| [ux.md](ux.md) | Design principles, identity, design system, information architecture, and key screens |
| [security.md](security.md) | What is protected, the controls for each threat, and who can see and do what |
| [demo-organization.md](demo-organization.md) | The fictional institute behind the demo, the screenshots, and the end-to-end test |
| [roadmap.md](roadmap.md) | Waves (releases) and their slices, from v0.1.0 to v1.0.0 |
| [waves/](waves/) | Detailed slice plans and status for each wave |
| [process.md](process.md) | How we work: waves and slices, the definition of done, releases, and content rules |
| [decisions/](decisions/) | Architecture decision records |
| [glossary.md](glossary.md) | Shared vocabulary |

## How to use these documents

- **Before starting a slice**, read its section in the current wave file and the documents it links to.
- **When a decision changes the architecture**, write a new decision record in [decisions/](decisions/). Supersede, don't rewrite.
- **When a slice lands**, update its status in the wave file and add a line to the changelog.
- **Keep this folder generic.** RiskWren is built for any organization to adopt and re-brand. Nothing here names a real institution, a real person, or another product. Examples use the demo organization.
