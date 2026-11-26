# ADR-0009: Documentation site and screenshots with Node and no packages

- **Status:** Accepted
- **Date:** 2026-11-25

## Context

RiskWren needs a product website with complete, illustrated documentation. Screenshots must show the real application, in both themes, and must be cheap to retake, or they will go stale within a release. The site must never disagree with the guides in the repository.

The application itself is Python managed with uv and has a strict dependency budget. The documentation tooling is separate from the application: it runs on a maintainer's machine and in continuous integration, never in an installation.

## Decision

- **The Markdown guides in `docs/` are the single source.** They read correctly in the repository, and the site is generated from them unchanged.
- **The site generator is one script for Node 22 with no packages.** It renders the guides with its own small Markdown renderer, builds the menu, a client-side search index, the changelog page, and an API reference from the committed OpenAPI document, reuses the application's design tokens for its light and dark themes, and fails on any broken link, anchor, or image.
- **Screenshots are captured by a script that drives headless Chrome over its debugging protocol**, using Node's built-in WebSocket and no packages. It builds a fresh demo organization, starts RiskWren on it, signs in as the sample person each scene calls for, and saves every scene in light and dark. A scene is one line of data. Any scene can be retaken by name.
- **The same scenes feed an automated accessibility audit.**
- **Diagrams are generated as SVG** in both themes from one color table.
- **Publishing is deliberate.** The site is what is committed on the `gh-pages` branch. The build writes into a worktree of that branch only when told to publish.
- **Screenshots only ever show the demo organization.**

## Consequences

- Maintainers need Node 22 and a Chromium-based browser as well as uv. Installations do not.
- Nothing to install, lock, or patch for the documentation tooling.
- The Markdown renderer supports the subset the guides use; the guides are written within it.
- Retaking every screenshot is one command and takes minutes, so it happens at every release.

## Alternatives

- **A Python static site generator and a browser automation package:** keeps one language, but adds a Markdown library, a theme, and a browser driver with its own downloaded browsers as development dependencies to track.
- **A hosted documentation service:** quick, but it separates the documentation from the repository and from the application's own look.
- **Screenshots taken by hand:** always out of date, and tempting to take from a real installation.
