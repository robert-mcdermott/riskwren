# Configuration

This guide is for whoever runs the server. It covers `riskwren.toml`, environment overrides, the data home, PostgreSQL, running behind a reverse proxy, and the guard on demo installations.

## What is configured where

RiskWren keeps two kinds of settings apart.

| Kind | Where it lives | Examples |
|---|---|---|
| How the server runs | `riskwren.toml` and the environment | Address, port, database, data home |
| The program and the product's look | The database, set in the app or by a program pack | Risk categories, appetite, the scoring method, cadences, vocabularies, name, logo, colors |

This guide is about the first. For the second, see [Running the program](running-the-program.md).

## Where the file is found

`uv run riskwren init` writes a commented `riskwren.toml` in the current directory. Every command looks for the file in this order:

1. The `--config FILE` option (short form `-c`), given before the command.
2. The `RISKWREN_CONFIG` environment variable.
3. `./riskwren.toml`.

```bash
uv run riskwren --config /etc/riskwren/riskwren.toml doctor
```

Relative paths in the file are resolved against the file's own directory, not the directory you run from. An installation therefore moves as a unit.

## Every section and key

The file has three sections. A section or key that RiskWren does not know is an error, not something it ignores. Every problem in the file is reported together.

### `[server]`

| Key | Default | Meaning |
|---|---|---|
| `host` | `"127.0.0.1"` | The address the web server listens on. Keep `127.0.0.1` when a reverse proxy on the same machine terminates TLS. Use `0.0.0.0` only behind one |
| `port` | `8000` | The port |
| `workers` | `1` | How many server processes to run. One is enough for SQLite and small teams |
| `base_url` | `""` | The public address people use to reach RiskWren, such as `"https://riskwren.example.org"`. Meant for links in messages RiskWren sends. This release sends no email, so it can stay empty |
| `session_idle_hours` | `12` | A sign-in ends after this long without activity |
| `session_max_days` | `7` | A sign-in ends after this long in any case |

`host`, `port`, and `workers` can also be given to `uv run riskwren serve` as `--host`, `--port`, and `--workers`, which take precedence for that run.

### `[database]`

| Key | Default | Meaning |
|---|---|---|
| `url` | `""` | Empty means SQLite, in a file inside the data home. For PostgreSQL, an address beginning `postgresql+psycopg://`. See [Use PostgreSQL](#use-postgresql) |

### `[data]`

| Key | Default | Meaning |
|---|---|---|
| `home` | `"var"` | The data home: the one directory that holds everything not in the database |

RiskWren also gives advice that does not stop it running. `serve` and `doctor` warn when several workers share one SQLite file, and when `base_url` is `http://` on a host other than localhost.

## Environment overrides

Any value can be overridden by an environment variable named `RISKWREN_<SECTION>_<KEY>`, in capitals. The environment wins over the file.

| Variable | Overrides |
|---|---|
| `RISKWREN_SERVER_HOST` | `[server] host` |
| `RISKWREN_SERVER_PORT` | `[server] port` |
| `RISKWREN_SERVER_WORKERS` | `[server] workers` |
| `RISKWREN_SERVER_BASE_URL` | `[server] base_url` |
| `RISKWREN_SERVER_SESSION_IDLE_HOURS` | `[server] session_idle_hours` |
| `RISKWREN_SERVER_SESSION_MAX_DAYS` | `[server] session_max_days` |
| `RISKWREN_DATABASE_URL` | `[database] url` |
| `RISKWREN_DATA_HOME` | `[data] home` |

```bash
RISKWREN_SERVER_PORT=8080 uv run riskwren serve
```

`RISKWREN_CONFIG` is separate: it names the file itself.

## Secrets are refused in the file

`riskwren.toml` is meant to be safe to read, copy, and keep under version control. RiskWren refuses to start if the file holds a secret: a key that looks like a password, secret, token, or key, or a database address with a password in it.

Put secrets in the environment instead. For the database, set the password in `PGPASSWORD`, or put the whole address, password and all, in `RISKWREN_DATABASE_URL`.

## The data home

The data home is created by `init`. With the default settings it is `./var`.

| Path | Holds |
|---|---|
| The SQLite database | When no database address is set |
| `brand/` | Uploaded logos and the tab icon |
| `logs/` | The server's log, rotated |
| `files/` | Reserved for evidence files, which come in the next release |
| `exports/` | Reserved for exports |
| `.riskwren-home` | A marker that says this directory is a data home |

- Back it up as a whole. With PostgreSQL, back up the database as well.
- Do not edit its contents by hand.
- It must be writable by the account that runs the server.
- Request bodies and tokens are never written to the log.

## Use PostgreSQL

SQLite is the default and needs no setup. Use PostgreSQL when many people will use RiskWren at once or you want more than one server process. The features and the data model are the same on both, and the test suite runs on both.

1. Install the driver, which is optional:

   ```bash
   uv sync --extra postgres
   ```

2. Create an empty database and a role that owns it, with your usual PostgreSQL tools.

3. Set the address in `riskwren.toml`, without the password:

   ```toml
   [database]
   url = "postgresql+psycopg://riskwren@db.example.org:5432/riskwren"
   ```

4. Put the password in the environment, then set up and check:

   ```bash
   export PGPASSWORD=…
   uv run riskwren init
   uv run riskwren doctor
   ```

Moving an existing installation from SQLite to PostgreSQL is not automated in this release. Start new installations on the database you mean to keep.

## Upgrade

After updating the code:

```bash
uv sync
uv run riskwren db upgrade
```

`db upgrade` applies any migrations the database has not had and adds anything new in the default program without overwriting what you have shaped. Back up first: an upgrade cannot be undone except by restoring. `serve` refuses to start on a schema that is behind, and `uv run riskwren db current` shows where the database is.

## Run behind a reverse proxy

RiskWren speaks plain HTTP and expects a reverse proxy to terminate TLS in front of it.

- Keep `host = "127.0.0.1"` when the proxy is on the same machine.
- Have the proxy send `X-Forwarded-Proto: https`. RiskWren marks its session cookie `Secure` when the request arrived over HTTPS, by that header or directly.
- Forward the `Host` header unchanged. Requests that change anything are refused when their origin does not match the host, which is part of the protection against requests from other sites.
- Requests larger than 32 MB are refused.

The app sets its own security headers, including a content security policy with no inline script or style and no third-party origins, so the proxy does not need to add them.

## The demo and the network

A demo organization signs in anyone who asks as any of its sample people, with no password. So a demo's server listens only on the machine it runs on: `serve` refuses any other host, and the sample sign-in refuses requests from other machines.

If you do want to show a demo to others on a network you trust:

```bash
uv run riskwren --config demo/riskwren.toml serve --host 0.0.0.0 --demo-on-network
```

Anyone who can reach it can then sign in as the demo's risk manager or administrator. Never do this with a database that holds anything real; a demo database holds nothing that is.
