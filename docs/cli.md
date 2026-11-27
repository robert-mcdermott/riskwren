# Command reference

Every `riskwren` command. This page is written from the program itself, so it always matches
the version it ships with. Run commands with `uv run riskwren …` from the project directory.

Options that come before the command apply to all of them:

```text
riskwren [-h] [--version] [-c FILE] [-v | -q] COMMAND ...
```

## Commands

| Command | What it does |
|---|---|
| [`riskwren init`](#riskwren-init) | Set up a new installation |
| [`riskwren serve`](#riskwren-serve) | Run the web server |
| [`riskwren demo`](#riskwren-demo) | Build a fictional organization to explore |
| [`riskwren db`](#riskwren-db) | Look after the database schema |
| [`riskwren users`](#riskwren-users) | Manage accounts from the command line |
| [`riskwren verify`](#riskwren-verify) | Check that the history has not been altered |
| [`riskwren frameworks`](#riskwren-frameworks) | See and load what the organization is held to |
| [`riskwren program`](#riskwren-program) | Move the program between installations |
| [`riskwren doctor`](#riskwren-doctor) | Check that this installation is healthy |
| [`riskwren jobs`](#riskwren-jobs) | See scheduled work, or run it now |
| [`riskwren mail`](#riskwren-mail) | Send waiting email, or test the mail settings |

## `riskwren init`

Write a configuration file if there is none, create the data home, create or upgrade the database, and create the first administrator if there is none. Safe to run again.

| Option | Meaning |
|---|---|
| `--force` | overwrite an existing configuration file |
| `--admin-email` `EMAIL` | create the first administrator with this address |
| `--admin-name` `NAME` | the first administrator's name |
| `--password-stdin` | read the password from standard input instead of asking |

## `riskwren serve`

Run RiskWren's web server. It refuses to start on a database whose schema is behind; run `riskwren db upgrade` first.

| Option | Meaning |
|---|---|
| `--host` | address to listen on (default: from the configuration) |
| `--port` `PORT` | port to listen on (default: from the configuration) |
| `--workers` `WORKERS` | server processes (default: from the configuration) |
| `--reload` | restart when the code changes (development) |
| `--demo-on-network` | let a demo organization listen beyond this machine (anyone who reaches it can sign in as its sample people) |

## `riskwren demo`

Build the Northmere Institute for Health Research, a fictional organization with two years of history, in its own directory. Everything in it is made by the same code the app uses. Start it with the command it prints.

| Option | Meaning |
|---|---|
| `PATH` | where to build it (default: ./demo) |
| `--seed` `SEED` | a different number gives a different Northmere |
| `--port` `PORT` | the port its server will use (default: 8020) |
| `--force` | rebuild a demo that is already there |

## `riskwren db`

Look after the database schema.

### `riskwren db upgrade`

Apply any migrations the database has not had. Export first: an upgrade cannot be undone except by restoring.

### `riskwren db current`

Show which migration the database is at, and which this version expects. Exits with 1 when they differ.

## `riskwren users`

Manage accounts from the command line: for setting up, and for getting back in when nobody can sign in. Everyday account management is in the app, under Admin. Changes made here are recorded in the history as made at the command line.

### `riskwren users add`

Add an account. It asks for a password unless --password-stdin or --invite is given.

| Option | Meaning |
|---|---|
| `EMAIL` | the email address the person signs in with |
| `--name` | the person's name |
| `--title` | their job title |
| `--role` `ROLE` | a role: admin, manager, assessor, auditor, steward=unit:CODE, or leader=unit:CODE,limit:RATING; manager and assessor may also take unit:CODE (may be repeated) |
| `--unit` `CODE` | a unit they work in, by code (may be repeated) |
| `--password-stdin` | read the password from standard input instead of asking |
| `--invite` | add them without a password: they can be named on records now, and sign in once they are given a password or use single sign-on |

### `riskwren users list`

List every account with its status and roles.

### `riskwren users disable`

Stop an account signing in and end its sessions. Its history is kept, and what the person alone answered for passes to the steward of its unit until someone is named for good. The last active administrator cannot be disabled.

| Option | Meaning |
|---|---|
| `EMAIL` | the account's email address |

### `riskwren users enable`

Let a disabled account sign in again.

| Option | Meaning |
|---|---|
| `EMAIL` | the account's email address |

### `riskwren users reset-password`

Give an account a new password and end its sessions.

| Option | Meaning |
|---|---|
| `EMAIL` | the account's email address |
| `--password-stdin` | read the password from standard input instead of asking |

### `riskwren users roles`

Show an account's roles, or with --set replace the roles granted in RiskWren. Roles mapped from an identity provider are left alone. The last active administrator cannot lose that role.

| Option | Meaning |
|---|---|
| `EMAIL` | the account's email address |
| `--set` `ROLE` | a role: admin, manager, assessor, auditor, steward=unit:CODE, or leader=unit:CODE,limit:RATING; manager and assessor may also take unit:CODE (may be repeated); with none, removes every role |

## `riskwren verify`

Recompute the hash chain over every event in the history and report the first one that does not hold. Exits with 1 if the history is broken.

## `riskwren frameworks`

A framework is a source of requirements: a public standard, a regulation, an agreement's terms. Four public ones ship with RiskWren and are loaded at installation. Others are loaded from a pack file, or entered in the app.

### `riskwren frameworks list`

List every framework.

### `riskwren frameworks load`

Load a framework from a pack file, or the built-in ones that are missing. A pack is checked whole first and refused whole if anything is wrong.

| Option | Meaning |
|---|---|
| `FILE` | the pack to load |
| `--builtin` | load the built-in frameworks not yet here |
| `--dry-run` | check the pack, and load nothing |

### `riskwren frameworks show`

Show a framework's publisher, version, license, and source.

| Option | Meaning |
|---|---|
| `KEY` | the framework's key, such as nist-csf |

## `riskwren program`

The program is everything a risk and compliance team configures: vocabularies, the risk categories and their appetite, the scoring method, cadences, and who may accept what. It lives in the database and moves as one file.

### `riskwren program export`

Write the whole program as one JSON document, to a file or to standard output.

| Option | Meaning |
|---|---|
| `--output`, `-o` `FILE` | write to this file |

### `riskwren program import`

Load a program pack. The whole pack is checked first, and nothing is loaded unless all of it can be. A new scoring method is published as a new version; assessments already made keep the version they were made under, and every open risk is read again from what was loaded: its ratings, its standing, and its next review.

| Option | Meaning |
|---|---|
| `FILE` | the pack to load |
| `--dry-run` | say what would change, and change nothing |

## `riskwren doctor`

Check the configuration, the data home, the database and its schema, and the history. Exits with 1 if anything must be fixed.

## `riskwren jobs`

Scheduled work brings risks up to date with the calendar, sends reminders, and sends email where that is set up. The server does this by itself while it runs. These commands are for seeing how it is going, and for running it from a scheduled task where the server's own scheduler is turned off.

### `riskwren jobs run`

Run every job that is due. With a job's name, run that one now whether or not it is due. A job another process is running is left to it.

| Option | Meaning |
|---|---|
| `JOB` | one job to run now |

## `riskwren mail`

Email is optional. Where it is set up, the server sends it by itself while it runs. These commands are for testing the settings and for sending by hand.

### `riskwren mail run`

Queue notices and daily summaries, and send what is waiting. Exits with 1 if a message could not be sent.

### `riskwren mail test`

Send one message now to the account with this address, and say whether the mail server accepted it.

| Option | Meaning |
|---|---|
| `EMAIL` | the account to send it to |
