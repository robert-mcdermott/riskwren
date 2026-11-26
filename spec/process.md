# How we work

## Waves and slices

- A **wave** is a release. Waves 1 to 10 become versions `0.1.0` to `0.10.0`, and wave 11 is `1.0.0`; after it, each wave is a minor release.
- A wave is planned in [`waves/wave-n.md`](waves/) as a set of **slices**: coherent chunks of related work with a goal, a checklist, and acceptance criteria. The wave file for the next wave is written before that wave starts, not earlier, so that it reflects what the previous wave taught.
- The **last slice** of every wave is release prep: documentation, changelog, version, final checks.
- Slices are done in order unless the wave file says otherwise. A slice may be split if it grows. It is not left half-finished at the end of a wave.

## Lifecycle of a wave

```text
main ──●────────────────────────────────────────●── tag v0.n.0 ──▶ release
        \                                      /
 wave-n  ●── slice 1 ── slice 2 ── … ── slice k (release prep) ── PR
```

1. Branch `wave-n` from an up-to-date `main`.
2. Work slice by slice. Each slice lands as one or more focused commits on `wave-n`, with the wave file's checklist and status updated in the same commits.
3. The final slice prepares the release.
4. Open a pull request from `wave-n` to `main`, then merge it.
5. Tag `v0.n.0` on the merge commit and publish a release whose notes come from the changelog.

## Definition of done (every slice)

- [ ] Acceptance criteria in the wave file are met
- [ ] `uv run pytest` passes offline, on SQLite and on PostgreSQL
- [ ] `uv run ruff check` and `uv run ruff format --check` are clean
- [ ] New behavior has tests; bug fixes have regression tests
- [ ] Every new API route has an entry in the policy table, and the role-by-route matrix covers it
- [ ] Every new write goes through a service function and records an event
- [ ] API changes are reflected in `docs/openapi.json` and the guides
- [ ] Schema changes include a migration that runs on both databases, and an update to [data-model.md](data-model.md)
- [ ] The demo organization shows the new capability with data
- [ ] Any new runtime dependency has a decision record
- [ ] The private-terms check passes
- [ ] The wave file's checklist and status are updated; `CHANGELOG.md` has an entry under *Unreleased*

## Release checklist (last slice)

- [ ] All slices in the wave are ☑, or explicitly moved to a later wave with a note
- [ ] README and guides updated for new capabilities
- [ ] `CHANGELOG.md`: *Unreleased* moved to the new version with the date
- [ ] Version set in `pyproject.toml`; `uv lock` up to date
- [ ] Fresh-clone install and quickstart verified on both databases
- [ ] Upgrade from the previous release checked: every row and file kept
- [ ] `riskwren demo` builds, and its history verifies
- [ ] The automated accessibility audit passes in every palette and mode
- [ ] Private-terms check run over the whole repository
- [ ] Roadmap and wave status updated
- [ ] Screenshots of changed screens retaken (`node scripts/capture.mjs`), and the guides checked against the changelog
- [ ] The site's own audit passes (`node scripts/site/audit.mjs`): both themes, desk and phone widths
- [ ] After the release: the site built from the tag and published to `gh-pages`

## What the automated checks run on

Every push is checked on a hosted runner: lint, format, and the whole suite on SQLite and on PostgreSQL. The same files are checked once:

- A branch is checked when it is pushed. A pull request from that branch is not checked again; it shows the push's result, which is for the same commit. Only a pull request from a fork is checked as a pull request.
- A commit whose files are exactly those of a commit that has already passed is not checked again. Merging a wave into a main that has not moved makes such a commit, so the merge is not re-tested, and neither is the tag or the release, which start nothing.
- A newer push to a branch stops the run for the one before it.

So merge only when the wave branch's own run is green: that run is the one the merge relies on.

## Tools

All Python work goes through `uv`:

```bash
uv sync                              # install
uv run riskwren init                  # first-time setup
uv run riskwren serve                 # run
uv run pytest                        # tests on SQLite
scripts/test-both.sh                 # tests on SQLite and PostgreSQL
uv run ruff check && uv run ruff format --check
uv add <package>                     # only with a decision record
```

The documentation site and screenshot capture use Node 22 with no packages (see the [roadmap](roadmap.md#documentation-site-between-v020-and-v030-)):

```bash
node scripts/site/build.mjs          # build the site into ./site, checking every link
node scripts/site/audit.mjs          # check the built site in both themes and at phone width
node scripts/capture.mjs             # retake the pictures the guides use
node scripts/a11y-audit.mjs          # the application's accessibility audit
```

## Versioning

- Semantic versioning. Before 1.0, a minor version (a wave) may contain breaking changes, called out under **Breaking** in the changelog. From 1.0, the compatibility statement defines what may change and when.
- The database schema is always migrated forward by Alembic. Every release can be reached from every earlier one.
- The scoring method, questionnaires, and packs carry their own versions, and an assessment always keeps the version it was made under.

## Commits and pull requests

- Commit messages: a short imperative summary line (72 characters or fewer), a blank line, then *what* and *why* in plain prose. Reference requirement IDs where useful (for example `RSK-04`).
- No by-lines or attribution trailers of any kind in commit messages, pull requests, documentation, or release notes.
- One pull request per wave. Its description summarizes the slices, notable decisions (linking the decision records), and how it was verified.

## Content rules for everything committed

RiskWren is generic and re-brandable, and the repository is public. Code, docs, tests, commit messages, pull requests, and release notes therefore follow these rules:

- **Generic examples only.** Use the demo organization, `example.org` addresses, and invented names. Never a real organization's configuration, people, or vendors.
- **No personal data in fixtures.** Test fixtures are synthetic.
- **Concepts, not comparisons.** Describe what RiskWren does on its own terms. No other product is named, and market analysis is not kept in this repository.
- **Public standards may be named** where a content pack or a format is based on one, with its publisher and license.
- **No secrets.** Keys and credentials come from environment variables or untracked local files.

The private-terms check (`scripts/check_terms.py`) enforces the rules that can be automated, using a term list kept outside version control in `.private/terms.txt`.

## Architecture decisions

Significant decisions are recorded in [decisions/](decisions/), numbered in order, using the template in [ADR-0001](decisions/0001-record-architecture-decisions.md). A decision record is never rewritten after acceptance; a new one supersedes it.
