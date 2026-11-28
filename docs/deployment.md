# Deployment

How to run RiskWren for real: in a container, with PostgreSQL, behind a proxy, backed up, and checked before anyone relies on it. [Getting started](getting-started.md) covers trying it on one machine; [Configuration](configuration.md) covers every setting.

The files this guide uses are in the repository's `deploy/` folder.

## Choose how to run it

| | For | What it takes |
|---|---|---|
| **A container with PostgreSQL** (`deploy/compose.yaml`) | Most installations | A host with Podman or Docker; the proxy in front |
| **A service on the host** (`deploy/riskwren.service`) | Hosts where containers are not used | Python 3.12 or later, `uv`, PostgreSQL, systemd |
| **One process with SQLite** | A small team, or trying it out | Nothing more; see [Getting started](getting-started.md) |

Whichever you choose: put a reverse proxy in front to end TLS, set `base_url` to the address people use, back up every day, and run `riskwren doctor --production` before you tell people it is there.

## In a container

`deploy/Containerfile` builds an image that holds RiskWren and nothing else. It runs as a user of its own, keeps its configuration and data home on the volume at `/data`, and sets the installation up the first time it starts.

```bash
cp deploy/.env.example deploy/.env      # fill it in; keep it out of version control
podman compose -f deploy/compose.yaml --env-file deploy/.env up -d --build
```

(`docker compose` works the same way.) The compose file runs PostgreSQL 16 beside RiskWren, waits for it to be ready, and publishes RiskWren on `127.0.0.1:8020` only, for the proxy. In `deploy/.env`:

- `RISKWREN_BASE_URL`: the `https://` address people use.
- `RISKWREN_DB_PASSWORD`: the database's password, made up for this installation.
- `RISKWREN_WORKERS`: server processes; one for each core RiskWren may use. See [Sizing](configuration.md#sizing).
- `RISKWREN_ADMIN_EMAIL`, `RISKWREN_ADMIN_NAME`, `RISKWREN_ADMIN_PASSWORD`: the first administrator, made on the first start only. Take the password out of the file once they have signed in, and recreate the container (`up -d --force-recreate`): a container keeps the environment it was started with.
- `RISKWREN_PROGRAM`: the [program to start from](getting-started.md#set-up-the-installation): `research-institute`, `academic-medical-center`, `university`, or `nonprofit`.

Every later start brings the database up to date (`riskwren db upgrade`) before the server starts, so an upgrade is a new image and a restart. Any setting in [Configuration](configuration.md) can be given to the container as an environment variable, `RISKWREN_<SECTION>_<KEY>`. Commands run inside it:

```bash
podman compose -f deploy/compose.yaml exec riskwren riskwren users add you@example.org --role admin
podman compose -f deploy/compose.yaml exec riskwren riskwren doctor --production
```

## As a service on the host

Install RiskWren into its own environment, and run it under systemd with `deploy/riskwren.service`:

```bash
sudo useradd --system --home-dir /var/lib/riskwren --shell /usr/sbin/nologin riskwren
sudo install -d -o riskwren -g riskwren -m 0750 /var/lib/riskwren /etc/riskwren
sudo UV_PROJECT_ENVIRONMENT=/opt/riskwren uv sync --frozen --no-dev --extra postgres --no-editable
sudo -u riskwren /opt/riskwren/bin/riskwren --config /etc/riskwren/riskwren.toml init
sudo cp deploy/riskwren.service /etc/systemd/system/
sudo systemctl enable --now riskwren
```

In `/etc/riskwren/riskwren.toml`, set the data home to `/var/lib/riskwren/var`, the database's address, and `base_url`. Secrets go in `/etc/riskwren/env`, readable only by root (mode 0600), which the unit reads: `RISKWREN_DATABASE_URL` with its password, the single sign-on client secret, the mail password.

The unit runs RiskWren as its own user with what it needs and nothing more: only the data home is writable, the rest of the system is read-only or hidden, it cannot gain privileges, load kernel modules, or change the clock, and it may make only the system calls an ordinary service makes. It brings the database up to date before each start.

## Behind a proxy

RiskWren speaks plain HTTP on `127.0.0.1` and expects a proxy to end TLS. `deploy/Caddyfile` does that with a certificate Caddy obtains itself; `deploy/nginx.conf` does it with yours. Either sends the `Host` header unchanged and `X-Forwarded-Proto: https`, so that RiskWren marks its session cookie `Secure` and checks where each change comes from. The nginx example keeps no access log for reports made without a name. See [Run behind a reverse proxy](configuration.md#run-behind-a-reverse-proxy).

## Back it up

Take a backup every day, from a scheduled task, and keep the files somewhere other than the server:

```bash
riskwren backup /backups/riskwren-$(date +%F).zip
```

A backup is taken while the server runs, and restores into SQLite or PostgreSQL alike. Restore one now and then, onto a spare machine, to know that it works. See [Back up and restore](configuration.md#back-up-and-restore).

## Check before going live

```bash
riskwren doctor --production
```

Besides the usual checks (the configuration, the data home, the database and its schema, the history), it checks what matters before real people rely on it, and exits with 1 if anything must be fixed:

| Check | Ready when |
|---|---|
| Address | `base_url` is the `https://` address people use |
| Listening | The server listens on this machine only, behind the proxy |
| Database for production | PostgreSQL, or SQLite with one worker for a small team |
| Backups | A backup was taken in the last two days |
| Demo | This is not a demo organization |
| Administrators | There are two, so that the installation is never left without one |
| Email for production | Email is set up, so that reminders reach people |

**Admin → Operations** shows the same, with the version, the database and its migration, the data home's size and free space, and the last backup, beside the scheduled work.

## Upgrade

Back up, then: in a container, build or pull the new image and restart; on the host, update the environment (`uv sync`) and restart the service. Both bring the database up to date as they start. The [changelog](../CHANGELOG.md) says what each release changes, and what looks different afterwards.
