# ADR-0010: The deployment in a file, the program in the database

- **Status:** Accepted
- **Date:** 2026-11-25

## Context

RiskWren has two very different kinds of settings. Some describe how the server runs: where the database is, which address to listen on, how to reach the identity provider and the mail server. Others describe the risk and compliance program and the product's appearance: the taxonomy, the scoring method, appetite, cadences, vocabularies, the organization's name, logo, and colors.

The first kind is set by whoever operates the server, rarely, and may involve secrets. The second is set by the program team and administrators, often, through the app, and must take effect immediately on every server process and leave a record.

## Decision

- **Deployment settings live in `riskwren.toml`**, with environment variable overrides. They are read at startup, validated strictly, and take effect on restart. Secrets are never in the file; the file names the environment variable that holds each one.
- **Program settings live in the database**, are edited in the app, take effect at once on every worker, and record an event for every change like any other write.
- **Branding is a program setting.** Names, logos, palette, and accent are edited in Admin → Appearance, and the server generates the theme stylesheet from the stored values. Uploaded images are kept in the data home.
- **The line between the two is fixed:** if a setting needs a restart, involves a secret, or describes infrastructure, it belongs in the file. Otherwise it belongs in the database.
- **Program settings move as a program pack**: one exported file that can be reviewed, kept under version control, and imported into another installation.
- **`riskwren init` seeds the database** from the built-in default program pack, so a new installation is configured before anyone opens the app.
- The command line can read and set program settings too (`riskwren program …`), for automation.

## Consequences

- Operators and the program team each have one place to look, and neither needs the other's access.
- Several server processes never disagree about the program, because none of them caches it beyond a request.
- A container can run with a read-only configuration file.
- An installation's full state is the file, the database, and the data home; the export command captures the latter two and reminds the operator about the first.
- Settings changed in the app are not visible in the configuration file, which may surprise operators used to files. `riskwren program export` gives them a file to read and compare.

## Alternatives

- **Everything in the file:** changes need file access and a restart, the app would have to rewrite the file to offer an editor, and several processes must watch it for changes.
- **Everything in the database:** the database URL cannot live in the database, and secrets do not belong there.
- **Branding in the file with an in-app editor that rewrites it:** workable on one machine, fragile with several processes or a read-only file system.
