# ADR-0004: Vanilla web frontend with no build step

- **Status:** Accepted
- **Date:** 2026-11-25

## Context

The web app is where almost everyone meets RiskWren, and it has to look and feel like a finished professional product. It also has to stay maintainable for years by a small team, be easy for an adopter to audit, and run under a strict content security policy.

## Decision

- **Plain ES modules, served as written.** No framework, no bundler, no transpiler, no package manager for the browser. What is in the repository is what runs.
- **A static shell and the JSON API.** One `index.html`; the server renders no pages.
- **Small core modules:** a DOM helper that only ever inserts data as text, a History API router that keeps all view state in the URL, an API client that handles CSRF and caching, and session and preference helpers.
- **One module per page, one per component,** each returning DOM. Rarely used pages are imported on first use.
- **CSS custom properties for every visual value**, with light and dark values side by side, palettes as attribute-scoped overrides, and a server-generated stylesheet for an organization's branding.
- **Charts and the dependency graph are drawn as SVG** by modules in the app.
- **Budgets and rules are tests:** size limits, no inline script or style, no third-party origins, no parsing of data as HTML, every import resolves.

## Consequences

- Nothing to install or build for the frontend, no dependency tree to patch, and a codebase a reviewer can read from top to bottom.
- A strict content security policy holds without exceptions.
- Some things a framework gives for free are written once here: the router, form state, list rendering. The assessment form and, later, the questionnaire renderer are the largest of these and get their own tests.
- Contributors used to a component framework have conventions to learn, documented beside the core modules.

## Alternatives

- **A component framework with a build:** faster to start, but it brings a toolchain and hundreds of transitive packages into a project whose adopters must vouch for it.
- **Server-rendered pages with light scripting:** workable for records, awkward for the assessment form with its live rating, the heat map, and the test queue, and it would add a template engine.
