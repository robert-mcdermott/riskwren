# Contributing to RiskWren

Thank you for helping. This page covers setting up, the checks every change must pass, and
the conventions the project keeps. The plan the work follows is in [`spec/`](spec/README.md).

## Setup

RiskWren needs [uv](https://docs.astral.sh/uv/), which provides the right Python. All Python
work goes through it.

```bash
uv sync                        # install RiskWren and its development tools
uv run riskwren init            # write riskwren.toml, create ./var and the database
uv run riskwren doctor          # check the installation
uv run riskwren serve --reload  # run it at http://127.0.0.1:8000
```

`riskwren.toml` and `var/` are yours and are ignored by git.

Adding a dependency is `uv add <package>` (or `uv add --dev <package>`). A new runtime
dependency also needs a decision record in [`spec/decisions/`](spec/decisions/README.md) that
says what it replaces and what it costs; the budget is deliberately small.

## Checks

```bash
uv run pytest                  # the tests, on SQLite, offline
uv run ruff check              # lint
uv run ruff format --check     # formatting (uv run ruff format to fix)
```

### Both databases

Everything must work on SQLite and on PostgreSQL. With podman or docker installed:

```bash
scripts/test-both.sh           # the suite on SQLite, then on a disposable PostgreSQL
```

To keep a PostgreSQL running between runs, start it with `scripts/dev-postgres.sh` (which
prints its address) and run:

```bash
RISKWREN_TEST_DATABASE=postgres RISKWREN_TEST_POSTGRES_URL=<address> uv run --extra postgres pytest
```

Each test gets its own fresh database. Tests marked `sqlite_only` are about the SQLite file
itself and are skipped on PostgreSQL. `scripts/dev-postgres.sh stop` removes the container.

### Generated documentation

`docs/cli.md` is written from the command-line parser and `docs/openapi.json` from the API.
Tests fail when either is out of date. Regenerate them with:

```bash
UPDATE_DOCS=1 uv run pytest tests/test_docs.py
```

### The documentation site and its screenshots

The guides in `docs/` are the source of the documentation site. It is built by a script that
needs Node 22 and no packages, and the pictures in it are taken from the demo organization
by headless Chrome (set `CHROME` if yours is not found).

```bash
node scripts/site/build.mjs          # build into ./site; fails on a broken link, anchor, or picture
node scripts/site/audit.mjs          # open every page in both themes, at desk and phone widths
node scripts/capture.mjs             # retake the pictures the guides and the home page use
node scripts/capture.mjs risk home   # retake only scenes whose name contains a word given
node scripts/a11y-audit.mjs          # the application's accessibility audit, over every scene
```

- To put a picture in a guide, name it: `![What it shows](img/NAME-light.webp)`, where `NAME`
  is a scene in `scripts/lib/scenes.mjs`, then run `node scripts/capture.mjs NAME`. The dark
  version is taken with it, and the site shows whichever suits the reader's theme.
- Only pictures something uses are kept in `docs/img`; a test fails on one that nothing
  names, or that lacks either theme.
- The home page is `scripts/site/pages/index.html`, and the menu is `MENU` at the top of
  `scripts/site/build.mjs`. A new guide has to be added to the menu; a test says so.
- The tests build the site, so a broken link in a guide fails like any other test.
- Publishing is deliberate: `node scripts/site/build.mjs --publish DIR` copies the built
  site into `DIR`, a worktree of the `gh-pages` branch, and commits and pushes nothing.

### The private-terms check

Some words must never appear in this public repository. The list is kept outside version
control, in `.private/terms.txt` (or wherever `RISKWREN_TERMS_FILE` points), one term per
line. Install the hooks once, and the check runs on every commit and commit message:

```bash
python3 scripts/check_terms.py --install-hooks
python3 scripts/check_terms.py          # check the whole working tree now
```

Without a term list the check passes and says so.

## How the code is arranged

Read [`spec/architecture.md`](spec/architecture.md) first. Three rules matter most:

- **Only services write.** Routes, commands, imports, and scheduled jobs all call the same
  service functions.
- **Every change leaves an event.** Sessions record one automatically for each new, changed,
  or deleted row of an audited model, in the same transaction. Open a writing session with
  `Database.write(actor)`. Bulk `update` and `delete` statements against audited tables are
  refused, because they would change rows without history: load the rows and change them.
- **Nothing is specific to one database.** Use the portable column types in
  `riskwren.db.types`, never query inside a JSON column, and write migrations that run on both.

A schema change is a new numbered migration in `src/riskwren/db/migrations/versions/` plus an
update to [`spec/data-model.md`](spec/data-model.md). A test compares what the migrations
build with what the models describe.

## Conventions

- **Waves and slices.** Work follows [`spec/roadmap.md`](spec/roadmap.md) and the current
  wave file; the definition of done is in [`spec/process.md`](spec/process.md).
- **Commits.** A short imperative summary line, a blank line, then what and why in plain
  prose. No by-lines or attribution trailers.
- **Generic content only.** Examples use the demo organization and `example.org`. No real
  organization, person, vendor, or other product is named anywhere in the repository.
- **Changelog.** User-visible changes get a line under *Unreleased* in `CHANGELOG.md`.
