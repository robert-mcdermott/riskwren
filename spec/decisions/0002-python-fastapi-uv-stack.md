# ADR-0002: Python, uv, FastAPI, and a small dependency budget

- **Status:** Accepted
- **Date:** 2026-11-25

## Context

RiskWren will be installed by small teams, often by one person who also has other work. It must be quick to install, easy to audit, and cheap to keep patched. It holds a map of an organization's weaknesses, so its own supply chain is part of what an adopter has to trust.

## Decision

- **Python 3.12 or newer**, for its reach among the organizations RiskWren is built for.
- **uv for everything**: installing, locking, running, testing, and building. The lock file is committed. Documentation and scripts never call `pip` or a virtual environment directly.
- **FastAPI on uvicorn** for the API, with synchronous handlers. The workload is ordinary request and response against a database; nothing needs an event loop.
- **A fixed, short list of runtime dependencies:** `fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `httpx`, and `psycopg` as an optional extra. Development adds `pytest` and `ruff`.
- **The standard library before a package.** Password hashing, TOML and JSON parsing, email, token verification, and the command line all use it.
- Adding a runtime dependency requires a decision record that says what it replaces and what it costs.

## Consequences

- A small install, a short list for a security review, and few upgrades to track.
- Some things are written by hand that a package would provide: the scoring arithmetic, the condition evaluator, token verification, the Markdown subset for notes, charts and the heat map. Each is small and tested.
- No template engine means the web app is a static shell over the JSON API ([ADR-0004](0004-vanilla-frontend.md)).
- No multipart parser means uploads are sent as the raw request body.

## Alternatives

- **A full-stack framework with an admin interface and server templates:** more built in, but a larger surface, and the admin interface would not be the product's interface.
- **Asynchronous handlers and drivers throughout:** more moving parts for no gain at this scale.
- **A package for each convenience:** quicker at first, and a growing audit and upgrade burden for every adopter afterward.
