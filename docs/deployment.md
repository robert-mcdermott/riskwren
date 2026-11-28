# Deployment

How to run RiskWren for real: in a container or as a service, with PostgreSQL, behind a proxy, backed up, watched, checked before anyone relies on it, and upgraded. [Getting started](getting-started.md) covers trying it on one machine; [Configuration](configuration.md) covers every setting.

The files this guide uses are in the repository's `deploy/` folder. An installed deployment runs its commands as `riskwren …`, not `uv run riskwren …`: inside the container, or through the `riskwren-admin` helper on a host, both shown below.

## Choose how to run it

| | For | What it takes |
|---|---|---|
| **A container with PostgreSQL** | Most installations | A host with Podman or Docker, and the proxy in front. The recipe is `deploy/compose.yaml` |
| **A service on the host** | Hosts where containers are not used | Linux with systemd, Python 3.12 or later, `uv`, and PostgreSQL. The unit is `deploy/riskwren.service` |
| **One process with SQLite** | A small team, or trying it out | Nothing more; see [Getting started](getting-started.md) |

Whichever you choose: put a reverse proxy in front to end TLS, set `base_url` to the address people use, back up every day, and run `riskwren doctor --production` before you tell people it is there.

## In a container

`deploy/Containerfile` builds an image that holds RiskWren and nothing else. It runs as a user of its own, keeps its configuration and data home on the volume at `/data`, and sets the installation up the first time it starts. `deploy/compose.yaml` runs it with PostgreSQL 16 beside it.

1. Copy the settings file and fill it in. Keep it out of version control: it holds the database's password.

   ```bash
   cp deploy/.env.example deploy/.env
   ```

   | Setting | What it is |
   |---|---|
   | `RISKWREN_BASE_URL` | The `https://` address people use |
   | `RISKWREN_DB_PASSWORD` | The database's password, made up for this installation |
   | `RISKWREN_WORKERS` | Server processes: one for each core RiskWren may use. See [Sizing](configuration.md#sizing) |
   | `RISKWREN_ADMIN_EMAIL`, `RISKWREN_ADMIN_NAME`, `RISKWREN_ADMIN_PASSWORD` | The first administrator, made on the first start only |
   | `RISKWREN_PROGRAM` | The [program to start from](getting-started.md#set-up-the-installation): `research-institute` (the default), `academic-medical-center`, `university`, or `nonprofit` |

2. Build the image and start both containers:

   ```bash
   podman compose -f deploy/compose.yaml --env-file deploy/.env up -d --build
   ```

   (`docker compose` works the same way.) The database starts first, and RiskWren waits until it is ready. RiskWren is published on `127.0.0.1:8020` only, for the proxy.

3. Watch it start, then check it:

   ```bash
   podman compose -f deploy/compose.yaml logs -f riskwren
   podman compose -f deploy/compose.yaml exec riskwren riskwren doctor
   ```

4. Once the first administrator has signed in, take `RISKWREN_ADMIN_PASSWORD` out of `deploy/.env` and recreate the container, since a container keeps the environment it was started with:

   ```bash
   podman compose -f deploy/compose.yaml --env-file deploy/.env up -d --force-recreate
   ```

5. Put the [proxy](#behind-a-proxy) in front, [schedule backups](#back-it-up), and [check it before going live](#check-before-going-live).

The first start runs `riskwren init`. Every later start brings the database up to date (`riskwren db upgrade`) before the server starts, so an upgrade is a new image and a restart.

If `RISKWREN_ADMIN_EMAIL` or `RISKWREN_ADMIN_PASSWORD` was left empty, the first start makes no administrator, and the server will not start until there is one: the container keeps restarting. Add one, giving the password when asked, and it starts on its next try:

```bash
podman compose -f deploy/compose.yaml run --rm riskwren riskwren users add you@example.org --name 'Your Name' --role admin
```

### Settings and commands

Any setting in [Configuration](configuration.md) can be given to the container as an environment variable, `RISKWREN_<SECTION>_<KEY>`. Add it under `environment:` for the `riskwren` service in your copy of `compose.yaml`, with its value in `deploy/.env`. Secrets go the same way: `RISKWREN_SSO_CLIENT_SECRET`, `RISKWREN_MAIL_PASSWORD`, and the assistant's key. `[branding]` cannot be set from the environment; it goes in `/data/riskwren.toml` on the volume, which the first start writes, with its images beside it.

Commands run inside the running container, as RiskWren's own user and with its environment. (If your compose tool does not read `deploy/.env` by itself, add `--env-file deploy/.env` to each command.)

```bash
podman compose -f deploy/compose.yaml exec riskwren riskwren users list
podman compose -f deploy/compose.yaml exec riskwren riskwren doctor --production
podman compose -f deploy/compose.yaml exec riskwren riskwren jobs
```

Inside the container RiskWren listens on every address, so `doctor --production` marks **Listening** as something to look at. That is expected: the compose file publishes the port on `127.0.0.1` only, so the server is reached from this host alone, which is what the check is after. It also tells RiskWren to believe the address the proxy forwards (`FORWARDED_ALLOW_IPS`), so that failed sign-ins are counted for each person rather than for the proxy; that is safe only while nothing but the proxy can reach the port.

## As a service on the host

`deploy/riskwren.service` runs RiskWren under systemd. It expects RiskWren installed in `/opt/riskwren`, its configuration in `/etc/riskwren/riskwren.toml`, its secrets in `/etc/riskwren/env`, and its data home under `/var/lib/riskwren`. Run these steps from a checkout of the release you are installing.

1. Make the account it runs as, and its folders:

   ```bash
   sudo useradd --system --home-dir /var/lib/riskwren --shell /usr/sbin/nologin riskwren
   sudo install -d -o riskwren -g riskwren -m 0750 /var/lib/riskwren /etc/riskwren
   ```

2. Install RiskWren into its own environment, with the PostgreSQL driver. (If `sudo` cannot find `uv`, give its full path, from `command -v uv`.)

   ```bash
   sudo UV_PROJECT_ENVIRONMENT=/opt/riskwren uv sync --frozen --no-dev --extra postgres --no-editable
   ```

3. Write the configuration before setting anything up, starting from the commented example:

   ```bash
   sudo install -o root -g riskwren -m 0640 src/riskwren/resources/riskwren.example.toml /etc/riskwren/riskwren.toml
   sudoedit /etc/riskwren/riskwren.toml
   ```

   Change these, and leave the rest until you need it:

   ```toml
   [server]
   port = 8020                       # the port the proxy examples send to
   base_url = "https://grc.example.org"
   workers = 4                       # one for each core RiskWren may use
   [database]
   url = "postgresql+psycopg://riskwren@db.example.org:5432/riskwren"
   [data]
   home = "/var/lib/riskwren/var"
   ```

   Before step 6, create the empty database and the role that owns it, with your usual PostgreSQL tools.

4. Put the secrets in `/etc/riskwren/env`, readable only by root. The unit reads it when the service starts.

   ```bash
   sudo install -o root -g root -m 0600 /dev/null /etc/riskwren/env
   sudoedit /etc/riskwren/env
   ```

   One `NAME=value` a line, for those in use. Put a value with spaces, `$`, or quotes in it inside single quotes.

   ```bash
   PGPASSWORD=…
   RISKWREN_SSO_CLIENT_SECRET=…
   RISKWREN_MAIL_PASSWORD=…
   ```

5. Add a helper that runs a `riskwren` command as the service does: as its user, with its configuration and its secrets. Setting up, backups, and checks all go through it.

   ```bash
   sudo tee /usr/local/sbin/riskwren-admin > /dev/null <<'EOF'
   #!/bin/sh
   # Run a riskwren command as the service runs: as its user, with its configuration and secrets.
   set -eu
   export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
   set -a
   . /etc/riskwren/env
   set +a
   export RISKWREN_CONFIG=/etc/riskwren/riskwren.toml
   cd /var/lib/riskwren
   exec runuser -u riskwren -- /opt/riskwren/bin/riskwren "$@"
   EOF
   sudo chmod 0700 /usr/local/sbin/riskwren-admin
   ```

6. Set the installation up. `init` keeps the configuration you wrote, creates the data home and the database's tables, loads the program, and asks for the first administrator. Add `--program university` (or another) to start from a different program.

   ```bash
   sudo riskwren-admin init
   sudo riskwren-admin doctor
   ```

7. Install the unit and start it:

   ```bash
   sudo cp deploy/riskwren.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now riskwren
   systemctl status riskwren
   ```

8. Put the [proxy](#behind-a-proxy) in front, [schedule backups](#back-it-up), and [check it before going live](#check-before-going-live).

The unit runs RiskWren as its own user with what it needs and nothing more: only `/var/lib/riskwren` is writable, the rest of the system is read-only or hidden, it cannot gain privileges, load kernel modules, or change the clock, and it may make only the system calls an ordinary service makes. It brings the database up to date (`riskwren db upgrade`) before each start, and starts the server again after a failure.

## Behind a proxy

RiskWren speaks plain HTTP on `127.0.0.1` and expects a proxy to end TLS. Two examples send to `127.0.0.1:8020`, where both the container and the service above listen:

| Example | What it does |
|---|---|
| `deploy/Caddyfile` | Caddy gets and renews the certificate itself |
| `deploy/nginx.conf` | nginx uses your certificate, and redirects plain HTTP to HTTPS |

In either, replace `grc.example.org` with your address (and, for nginx, the certificate's paths). Both:

- send the `Host` header unchanged and `X-Forwarded-Proto: https`, so that RiskWren marks its session cookie `Secure` and checks where each change comes from;
- forward each person's address, so that failed sign-ins are counted for each of them;
- allow requests up to 33 MB, a little over the 32 MB RiskWren takes;
- tell browsers to use HTTPS only (`Strict-Transport-Security`);
- keep no address for reports made without a name (`/report` and `/api/v1/anonymous-reports`): neither the proxy's log nor RiskWren is told where they came from.

RiskWren sets its own security headers, so the proxy needs to add no others. See [Run behind a reverse proxy](configuration.md#run-behind-a-reverse-proxy).

## Back it up

Take a backup every day, from a scheduled task, and keep the files somewhere other than the server, as carefully as the database itself: a backup holds everything. A backup is taken while the server runs, as of one moment, and restores into SQLite or PostgreSQL alike. It does not hold the configuration file or the secrets; keep those with your own configuration management. See [Back up and restore](configuration.md#back-up-and-restore).

### Backups on the host

1. Make a folder for backups:

   ```bash
   sudo install -d -o riskwren -g riskwren -m 0750 /var/lib/riskwren/backups
   ```

2. Take one, to see that it works:

   ```bash
   sudo riskwren-admin backup /var/lib/riskwren/backups/riskwren-$(date +%F).zip
   ```

3. Schedule it. In root's crontab (`sudo crontab -e`), this takes one at 02:30 every day; in a crontab, `%` is written `\%`:

   ```
   30 2 * * * /usr/local/sbin/riskwren-admin backup /var/lib/riskwren/backups/riskwren-$(date +\%F).zip
   ```

4. Copy each file to where your other backups go, with your usual tools, and remove old ones from the server.

### Backups in a container

`riskwren backup` writes inside the container, onto its volume, which is on the same host. So back up there, copy the file out, and remove it from the volume. Save this as a script, change the two paths, and run it every day from cron or a systemd timer, as the user who runs the containers:

```sh
#!/bin/sh
# Back RiskWren up from its container to a folder on the host.
set -eu
name=riskwren-$(date +%F).zip
rw="podman compose -f /srv/riskwren/deploy/compose.yaml exec -T riskwren"
$rw mkdir -p /data/backups
$rw riskwren backup "/data/backups/$name"
$rw cat "/data/backups/$name" > "/srv/backups/$name"
$rw rm "/data/backups/$name"
```

Then copy the files in `/srv/backups` to where your other backups go.

`doctor --production` and **Admin → Operations** show when the last backup was taken, and how large it was.

### Test a restore

Restore a backup now and then (every quarter, say) to know that it works and that you know how. A restore goes only into an empty database, so do it in a folder of its own on a spare machine or your own computer, from a checkout of the version of RiskWren that took the backup.

1. Make an empty installation to restore into. A configuration file that only turns the scheduler off is enough: everything else takes its default, so the backup goes into SQLite in a new data home beside the file, whichever database it came from. With the scheduler off, the copy sends no reminders and tells no webhooks.

   ```bash
   mkdir restore-test
   printf '[server]\nscheduler = false\n' > restore-test/riskwren.toml
   ```

2. See what the backup holds, and which version took it. If that is not the version you have, check it out.

   ```bash
   uv run riskwren --config restore-test/riskwren.toml restore --describe riskwren-2026-12-01.zip
   ```

3. Restore it. It reads back every table, checks every file, and verifies the history, and ends by saying that every table, every file, and the history match the backup. Anything that does not is named, and the command exits with 1.

   ```bash
   uv run riskwren --config restore-test/riskwren.toml restore riskwren-2026-12-01.zip
   ```

4. Check it, start it on this machine only, and sign in as an administrator to see the records as they were:

   ```bash
   uv run riskwren --config restore-test/riskwren.toml doctor
   uv run riskwren --config restore-test/riskwren.toml serve --port 8030
   ```

5. Delete the folder when you are done: it holds everything the backup held.

To restore after a real loss, see [Restore from a backup](help.md#restore-from-a-backup).

## Check before going live

```bash
riskwren doctor --production
```

In a container, run it through `podman compose -f deploy/compose.yaml exec riskwren`; on a host, as `sudo riskwren-admin doctor --production`.

It runs the usual checks:

- the configuration, and the data home and its free space;
- the database, its schema, the guard on the history, and the history itself;
- single sign-on and email, where they are set up;
- whether scheduled work is running.

Then it checks what matters before real people rely on it, and exits with 1 if anything must be fixed:

| Check | Ready when | If not |
|---|---|---|
| Address | `base_url` is the `https://` address people use | Must be fixed |
| Listening | The server listens on this machine only, behind the proxy | To look at; expected in a container |
| Database for production | PostgreSQL, or SQLite with one worker for a small team | Must be fixed with several workers on SQLite; to look at with one |
| Backups | A backup was taken in the last two days | Must be fixed when there is none; to look at when the last is older |
| Demo | This is not a demo organization | Must be fixed |
| Administrators | There are two, so that the installation is never left without one | To look at |
| Email for production | Email is set up, so that reminders reach people | To look at |

**Admin → Operations** shows the same, with the version, the database and its migration, the data home's size and free space, and the last backup, beside the scheduled work. [Check the installation](help.md#check-the-installation) says what to do about each thing `doctor` reports.

## Keep an eye on it

| Where | What it tells you |
|---|---|
| `GET /api/v1/health/live` | Whether the server process is up. No sign-in needed |
| `GET /api/v1/health/ready` | `200` when the database answers and its schema is the one this version expects; `503` when the database cannot be reached or the schema is out of date. No sign-in needed; the container's health check uses it |
| The service's own log | `journalctl -u riskwren` on a host, `podman compose -f deploy/compose.yaml logs riskwren` for a container |
| `logs/riskwren.log` in the data home | The server's log, rotated, kept on the machine |
| **Admin → Operations** | Each scheduled job and how its last run went, and email waiting, sent, and given up on |
| `riskwren verify` | Whether the history, every published document, and every leadership report still match what was recorded. Run it from time to time; it exits with 1 if anything does not hold |

When reminders, email, or webhooks stop arriving, see [Email, reminders, and webhooks are not arriving](help.md#email-reminders-and-webhooks-are-not-arriving).

## Upgrade

Read the new release's entry in the [changelog](../CHANGELOG.md) first. Its **Upgrading from** part says which migrations it brings and what looks or behaves differently afterwards. An upgrade cannot be undone except by restoring the backup taken before it, with the version that took it.

### Upgrade a container

1. At a quiet time, [back up](#backups-in-a-container) and copy the file off the volume. Work done between the backup and the upgrade would be lost only if you had to go back.
2. In your checkout, get the new release: `git pull`, or check out the release's tag.
3. Build the new image and start it. The new container brings the database up to date before the server starts.

   ```bash
   podman compose -f deploy/compose.yaml --env-file deploy/.env up -d --build
   ```

4. Check it:

   ```bash
   podman compose -f deploy/compose.yaml logs riskwren
   podman compose -f deploy/compose.yaml exec riskwren riskwren doctor --production
   ```

### Upgrade a service on the host

1. Stop the service, so that nothing is written after the backup:

   ```bash
   sudo systemctl stop riskwren
   ```

2. Back up, and copy the file off the server. Do it before installing the new release: once the code is newer than the database, `backup` refuses until `db upgrade` has run.

   ```bash
   sudo riskwren-admin backup /var/lib/riskwren/backups/riskwren-before-upgrade-$(date +%F).zip
   ```

3. In your checkout, get the new release (`git pull`, or check out the release's tag), and install it over the old:

   ```bash
   sudo UV_PROJECT_ENVIRONMENT=/opt/riskwren uv sync --frozen --no-dev --extra postgres --no-editable
   ```

4. Bring the database up to date, and check the installation:

   ```bash
   sudo riskwren-admin db upgrade
   sudo riskwren-admin doctor --production
   ```

5. Start the service:

   ```bash
   sudo systemctl start riskwren
   ```

The unit runs `db upgrade` before every start as well, so step 5 would do it anyway. Running it in step 4 shows what it did, and lets `doctor` check the result before anyone signs in.
