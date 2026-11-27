# Configuration

This guide is for whoever runs the server. It covers `riskwren.toml`, environment overrides, the data home, PostgreSQL, running behind a reverse proxy, and the guard on demo installations.

## What is configured where

RiskWren keeps two kinds of settings apart.

| Kind | Where it lives | Examples |
|---|---|---|
| How the server runs | `riskwren.toml` and the environment | Address, port, database, data home |
| The program and the product's look | The database, set in the app or by a program pack | Risk categories, appetite, the scoring method, cadences, vocabularies, name, logo, colors |

This guide is about the first. For the second, see [Running the program](running-the-program.md).

The look is the one thing that can live in either place. Most organizations set it in the app. One that needs its brand reproduced exactly can fix it in the file: see [`[branding]`](#branding).

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

The file has five sections. Only the first three matter for a new installation; `[sso]` and `[mail]` are optional. A section or key that RiskWren does not know is an error, not something it ignores. Every problem in the file is reported together.

### `[server]`

| Key | Default | Meaning |
|---|---|---|
| `host` | `"127.0.0.1"` | The address the web server listens on. Keep `127.0.0.1` when a reverse proxy on the same machine terminates TLS. Use `0.0.0.0` only behind one |
| `port` | `8000` | The port |
| `workers` | `1` | How many server processes to run. One is enough for SQLite and small teams |
| `base_url` | `""` | The public address people use to reach RiskWren, such as `"https://riskwren.example.org"`. Used for the single sign-on redirect address, and for links in messages RiskWren sends. Set it when you use single sign-on |
| `session_idle_hours` | `12` | A sign-in ends after this long without activity |
| `session_max_days` | `7` | A sign-in ends after this long in any case |
| `scheduler` | `true` | Run scheduled work inside this server. See [Scheduled work](#scheduled-work) |

`host`, `port`, and `workers` can also be given to `uv run riskwren serve` as `--host`, `--port`, and `--workers`, which take precedence for that run.

### `[database]`

| Key | Default | Meaning |
|---|---|---|
| `url` | `""` | Empty means SQLite, in a file inside the data home. For PostgreSQL, an address beginning `postgresql+psycopg://`. See [Use PostgreSQL](#use-postgresql) |

### `[data]`

| Key | Default | Meaning |
|---|---|---|
| `home` | `"var"` | The data home: the one directory that holds everything not in the database |

### `[sso]`

Single sign-on is optional and off until both `issuer` and `client_id` are set. See [Single sign-on](#single-sign-on).

| Key | Default | Meaning |
|---|---|---|
| `issuer` | `""` | The identity provider's issuer address. For Microsoft Entra ID, `"https://login.microsoftonline.com/<tenant id>/v2.0"` |
| `client_id` | `""` | The client (application) ID the provider gave RiskWren |
| `client_secret_env` | `"RISKWREN_SSO_CLIENT_SECRET"` | The name of the environment variable that holds the client secret. The secret itself is refused in the file |
| `scopes` | `"openid profile email"` | What RiskWren asks the provider for. Must include `openid` |
| `roles_claim` | `"roles"` | The claim in the ID token that lists a person's application roles or groups |
| `label` | `"Sign in with your organization account"` | The words on the sign-in button |
| `trust_email` | `false` | Accept the provider's address for a person without its saying the address is verified. Entra ID does not say, so set this to `true` for a single Entra ID tenant |
| `create_accounts` | `true` | Make an account the first time someone signs in. With `false`, only people who already have an account can sign in |
| `local_sign_in` | `true` | Keep the password form for everyone who has a password. With `false`, only administrators may sign in with a password |

### `[mail]`

Email is optional and off until both `host` and `from_address` are set. See [Email](#email).

| Key | Default | Meaning |
|---|---|---|
| `host` | `""` | The SMTP server |
| `port` | `587` | Its port |
| `security` | `"starttls"` | `"starttls"` (usual on port 587), `"tls"` (port 465), or `"none"` |
| `username` | `""` | The account to sign in to the mail server with, if it needs one |
| `password_env` | `"RISKWREN_MAIL_PASSWORD"` | The name of the environment variable that holds the password. The password itself is refused in the file |
| `from_address` | `""` | The address messages come from |
| `from_name` | `""` | The name beside it. Empty means the product's name |
| `digest_hour` | `7` | The hour of the day, in UTC, after which daily summaries are sent |

### `[branding]`

Optional. Leave it out and the look is set in the app, under **Admin → Appearance**, as before.

Use this section when the look has to be exact: every color by day and after dark, the official logo files, the brand's typefaces. It is also the way to keep a brand in version control, or to give several installations the same look.

**What is set here wins** over what the app stores, and shows under Admin → Appearance as locked, marked *Set in the configuration file*. Whatever this section leaves out can still be changed in the app. Nothing here is written to the database, so taking a line out gives that setting back to the app. A change takes effect when the server is restarted.

| Key | Meaning |
|---|---|
| `product_name` | The name in the sidebar, the browser tab, and email. Up to 40 characters |
| `organization_name` | Your organization's name, on the sign-in page |
| `show_powered_by` | `false` to hide the small "Powered by RiskWren" link |
| `logo_light`, `logo_dark` | Image files for light and dark backgrounds. With no `logo_dark`, the light one is used for both |
| `favicon` | The browser tab icon |
| `sign_in_image` | The picture beside the sign-in form |
| `logo_height` | The logo's height in the sidebar, in pixels, from 20 to 48. The usual is 30. Use it where a brand sets a least width for its logo |
| `font` | The typeface for everything, as a list of font names in order of preference |
| `font_headings` | A different typeface for page titles and section headings |
| `sign_in_message` | A message on the sign-in page, up to 600 characters |
| `email_footer` | The last line of every email |
| `footer_links` | Up to five links, each `{ label = "…", url = "…" }` |
| `palette` | One of the built-in palettes: `wren`, `slate`, `garnet` |
| `accent`, `accent_dark` | An accent color over a built-in palette, as hex. Not needed when `[branding.colors]` is set |
| `rating_ramp` | How ratings are colored: `ordinal`, one hue from pale to deep, or `signal`, green through amber to red |

Image paths are relative to the file's folder. Images are PNG, JPEG, WebP, or SVG, up to 2 MB, and are served as they are: RiskWren scales a logo and changes nothing else about it.

Fonts are named, never shipped. A name works on a computer that has the font installed, and the next name in the list is tried on one that does not, so end the list with fonts every computer has. A font that is licensed, as most brand typefaces are, cannot be put on the server for everyone.

#### Exact colors

`[branding.colors.day]` and `[branding.colors.night]` replace the built-in palettes. Give both, or neither. Each color is a hex value.

| Color | What it is | If left out |
|---|---|---|
| `bg` | The page behind everything | Needed |
| `surface` | Cards, panels, and fields | Needed |
| `text` | Ordinary text | Needed |
| `muted` | Secondary text | Needed |
| `accent` | Links, primary buttons, and the selected page | Needed |
| `on_accent` | Text on a primary button | Black or white, whichever reads better |
| `stripe` | The second color of the stripe across the top of the page | The accent |
| `border` | Hairlines between things | A step from the surface |
| `border_strong`, `surface_2`, `surface_3`, `subtle`, `accent_hover`, `accent_soft` | Finer shades: stronger lines, the sidebar and quieter panels, the faintest text, a button under the pointer, the background of a selected item | Worked out from the colors above, a step lighter or darker on the same hue |

```toml
[branding]
product_name = "Lantern"
organization_name = "Northmere Institute for Health Research"
logo_light = "brand/northmere.svg"
logo_dark = "brand/northmere-white.svg"
favicon = "brand/northmere-icon.png"
font = ["Inter", "Arial"]

[branding.colors.day]
bg = "#f6f5f2"
surface = "#ffffff"
text = "#1d2733"
muted = "#57606b"
accent = "#1f5f8b"

[branding.colors.night]
bg = "#12171d"
surface = "#1a222b"
text = "#ffffff"
muted = "#b9c2cc"
accent = "#6cb6e6"
on_accent = "#0f1a24"
```

RiskWren refuses to start with colors that cannot be read. Text on the page and on a card, secondary text, the accent on a card, and text on the accent must each reach a contrast of 4.5 to 1, by day and after dark, and the message says which pair fell short and by how much. A brand color that is too pale for text on white, as a bright yellow or a light blue often is, belongs in `stripe`, not `accent`.

Three things are left alone, because they carry meaning: the colors for within appetite, warning, and above it; the colors of the ratings (chosen with `rating_ramp`); and the colors that tell kinds of record apart. When exact colors are set, people are no longer offered a palette of their own to choose, since there is nothing for it to change. Light and dark mode remain each person's choice.

To check a brand on every screen, run the accessibility audit with it: put the `[branding]` section in a file of its own, with full paths for its images, and name that file in `RISKWREN_DEMO_BRANDING` when you run `node scripts/a11y-audit.mjs`.

RiskWren also gives advice that does not stop it running. `serve` and `doctor` warn when several workers share one SQLite file, when `base_url` is `http://` on a host other than localhost, and when email is set up without a `base_url` for its links.

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
| `files/` | Evidence files, each stored once under the SHA-256 of its content. Nothing here is served directly |
| `exports/` | Reserved for exports |
| `.riskwren-home` | A marker that says this directory is a data home |

- Back it up as a whole. With PostgreSQL, back up the database as well.
- Do not edit its contents by hand.
- It must be writable by the account that runs the server.
- Request bodies and tokens are never written to the log.

## Single sign-on

**You do not need this to use RiskWren.** A new installation signs in with an email address and a password that RiskWren keeps, and an evaluation or a small team needs nothing else. Single sign-on is something an administrator adds when the organization wants people to use the account they already have, under its own multi-factor authentication and offboarding.

When it is on, it sits beside local accounts and does not replace them. The sign-in page shows the organization's button first, with the password form folded beneath it. An administrator can always sign in with a password, so a provider that is down or misconfigured never locks everyone out.

RiskWren speaks OpenID Connect: the authorization-code flow with PKCE. It works with Microsoft Entra ID and with any provider that follows the standard and signs its ID tokens with RS256.

### What you set, and where

| What | Where |
|---|---|
| The provider's issuer and RiskWren's client ID | `[sso]` in `riskwren.toml` |
| The client secret | An environment variable, `RISKWREN_SSO_CLIENT_SECRET` unless you name another |
| RiskWren's public address | `[server] base_url`, so the redirect address is always the same |
| Which of the provider's roles or groups give which role here | In the app: **Admin → Single sign-on** |

The redirect address to give the provider is `<base_url>/api/v1/sso/callback`. **Admin → Single sign-on** shows it, before and after you set anything up.

### With Microsoft Entra ID

1. In the Entra admin center, open **App registrations → New registration**. Name it, choose **Accounts in this organizational directory only**, and add a **Web** redirect URI: your `base_url` followed by `/api/v1/sso/callback`.
2. From the registration's **Overview**, copy the **Application (client) ID** and the **Directory (tenant) ID**.
3. Under **Certificates & secrets**, add a client secret and copy its **Value**. It is shown once.
4. Under **App roles**, create a role for each kind of access you want to give from Entra ID, for users and groups. The role's **Value** is what RiskWren sees: for example `RiskWren.Admin`, `RiskWren.Assessor`, `RiskWren.Security.Leader`.
5. Under **Enterprise applications**, open the same application, then **Users and groups**, and assign people or groups to those roles. Under **Properties**, set **Assignment required** to **Yes** if only assigned people should be able to sign in.
6. Under **Token configuration**, add the optional **ID** claim `email`.
7. In `riskwren.toml`:

   ```toml
   [server]
   base_url = "https://riskwren.example.org"

   [sso]
   issuer = "https://login.microsoftonline.com/<tenant id>/v2.0"
   client_id = "<application id>"
   trust_email = true
   ```

8. Put the secret's value in `RISKWREN_SSO_CLIENT_SECRET` in the environment RiskWren starts in, and restart it.
9. Run `uv run riskwren doctor`. It reads the provider and says whether the secret is set.
10. Sign in with a password as an administrator, open **Admin → Single sign-on**, choose **Check the connection**, and map each app role's value to a role here.

Three things about Entra ID are worth knowing.

- **Name one tenant.** RiskWren refuses the shared issuers (`common`, `organizations`, `consumers`), because they would accept a sign-in from any directory.
- **Entra ID does not mark addresses as verified**, which is why `trust_email` is `true` above. That is safe for a single tenant, whose addresses are the organization's own. Without it nobody can be matched to an existing account or created.
- **Prefer app roles to groups.** To use groups instead, add a groups claim under **Token configuration**, set `roles_claim = "groups"`, and map each group's object ID. Entra ID leaves the groups out of the token for a person in more than about two hundred of them; RiskWren then leaves that person's roles as they were and says so in its log.

### With another provider

Register RiskWren as a confidential web client with the redirect address above. Set `issuer` to the address whose `/.well-known/openid-configuration` the provider serves, and `client_id` to what it gave you. Have it put a person's groups or roles in a claim, and name that claim in `roles_claim` (many providers call it `groups`). If the provider says `email_verified` is true for its addresses, leave `trust_email` as it is.

### Roles from the provider

**Admin → Single sign-on** lists mappings. Each says: everyone the provider gives this value gets this role here.

| Role here | For |
|---|---|
| Works in a unit | One unit. Membership grants nothing by itself; it decides what a member sees |
| Steward, Leader | One unit, and everything beneath it. A leader's mapping also says what they may accept |
| Assessor, Manager | The whole organization, or one unit |
| Auditor, Administrator | The whole organization |

- Roles given this way are **set again at every sign-in**. Take the role away at the provider and it is gone here the next time the person signs in. A shorter `session_max_days` shortens the wait.
- Roles given by hand under **Admin → People** are left alone, and are shown apart from those the provider gave.
- **The last administrator is never removed**, whatever the provider says.
- A unit in a mapping is the unit itself, so renaming it changes nothing.

### Who a person is

A person is known by the provider's own identifier for them, never by an address alone. The first time someone signs in:

- if an account here has the address the provider vouches for, the two are joined, and from then on the provider's identifier is what counts;
- otherwise an account is made for them, with the roles their mappings give, unless `create_accounts` is `false`.

A disabled account cannot come in through the provider. Signing out of RiskWren does not sign anyone out of the provider.

### Passwords, once it is on

With `local_sign_in = true`, anyone who has a password may still use it. With `false`, only administrators may. There is no setting that removes the administrator's password, on purpose: it is the way in when the provider cannot be reached.

### Try it on a laptop

`scripts/dev_identity_provider.py` is a stand-in provider for trying this out. It has a fixed list of people and no passwords, and its signing key is published in the file, so it proves nothing and listens only on the machine it runs on.

```bash
uv run python scripts/dev_identity_provider.py
```

Then set `issuer = "http://127.0.0.1:8099"`, `client_id = "riskwren-dev"`, and `trust_email = true` under `[sso]`, and start RiskWren with `RISKWREN_SSO_CLIENT_SECRET=dev-secret` in its environment.

## Scheduled work

RiskWren does four things by itself, so that nobody has to remember to.

| Job | How often | What it does |
|---|---|---|
| The calendar | Hourly | Brings risks up to date when a plan passes its date or an acceptance ends |
| Reminders | Hourly | Reminds people of what is nearly due, and tells stewards and leaders what stays late. See [Reminders](running-the-program.md#reminders) |
| Email | Every minute | Queues notices and daily summaries and sends what is waiting, where [email](#email) is set up |
| Measures | Every six hours | Takes the day's snapshot of every measure, for its trend; a later one the same day replaces it |
| Housekeeping | Daily | Removes run records older than ninety days and sign-ins that were never finished |

The server runs them while it is up. Nothing needs to be installed or scheduled.

- **Each job runs once.** Before a process runs a job it claims the job in the database. With several workers, or several servers on one database, whichever claims it has it and the others leave it alone. A process that dies mid-job loses its claim after fifteen minutes.
- **A restart loses nothing.** What is due is worked out from the database and the clock, so a server that was down catches up when it starts.
- **Admin → Scheduled work** shows each job, when it last ran and what it did, and can run one now or pause it. A failed run is shown with its reason and tried again when next due.
- `uv run riskwren jobs` lists the same from the command line, and `uv run riskwren jobs run` runs whatever is due.

To run the jobs from the operating system's scheduler instead, set `scheduler = false` under `[server]` and run `uv run riskwren jobs run` every few minutes. `doctor` warns if the scheduler is off and nothing has run for two days.

## Email

**You do not need this to use RiskWren.** Notices and reminders are read in the app, under the bell at the top right, and on Home. Email sends the same notices to people's inboxes as well, for organizations that want that.

1. Under `[mail]` in `riskwren.toml`, set `host` and `from_address`. If the mail server needs a sign-in, set `username`, and put the password in the `RISKWREN_MAIL_PASSWORD` environment variable.
2. Set `base_url` under `[server]`, so that messages can link back.
3. Restart RiskWren, and run `uv run riskwren doctor`: it connects and signs in to the mail server, and sends nothing.
4. Send yourself a message from **Admin → Scheduled work**, or with `uv run riskwren mail test you@example.org`.

Then each person chooses, under **Your account**: each notice as it happens, one summary a day, or no email. The choice appears only once email is set up.

- **Nothing is sent from the request that caused it.** A notice is written to the database, the mailer turns it into a message in an outbox in the same database, and sends from there. A mail server that is down is tried again later, with longer waits, and given up on after six attempts.
- **Turning email on does not send people their history.** Only notices written after it is set up are sent.
- **A daily summary** gathers what a person has not yet read in the app, once a day after `digest_hour`.
- Messages say what happened and link to it. They carry no record's contents beyond its name.

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

`db upgrade` applies any migrations the database has not had and adds anything new in the default program without overwriting what you have shaped. Coming from 0.4.0, that is the questionnaire tiering asks and the three due diligence questionnaires. Coming from 0.3.0, that is also the publishers' mappings carried with the built-in frameworks: where each SP 800-53 Rev. 4 control went in Rev. 5, and the SP 800-53 controls each SP 800-171 requirement comes from. Coming from 0.2.1, that is the four built-in questionnaires; the [changelog](../CHANGELOG.md) says what behaves differently afterwards. Coming from 0.1.0, that is also the four public frameworks and the mappings the common controls carry to them; your own controls are not mapped for you, and each one that came from the library offers the mappings on its **Requirements** tab. Back up first: an upgrade cannot be undone except by restoring. `serve` refuses to start on a schema that is behind, and `uv run riskwren db current` shows where the database is.

## Run behind a reverse proxy

RiskWren speaks plain HTTP and expects a reverse proxy to terminate TLS in front of it.

- Keep `host = "127.0.0.1"` when the proxy is on the same machine.
- Have the proxy send `X-Forwarded-Proto: https`. RiskWren marks its session cookie `Secure` when the request arrived over HTTPS, by that header or directly.
- Forward the `Host` header unchanged. Requests that change anything are refused when their origin does not match the host, which is part of the protection against requests from other sites.
- Requests larger than 32 MB are refused.

The app sets its own security headers, including a content security policy with no inline script or style and no third-party origins, so the proxy does not need to add them.

If reporting without a name is open (see [Incidents](incidents.md#reporting-without-a-name)), RiskWren keeps nothing about who sends a report, but the proxy's access log, and the server's own, may record the address of every request. To keep reports at `/report` and `/api/v1/anonymous-reports` from being tied to an address, leave those paths out of the logs, or keep no addresses in them.

## The demo and the network

A demo organization signs in anyone who asks as any of its sample people, with no password. So a demo's server listens only on the machine it runs on: `serve` refuses any other host, and the sample sign-in refuses requests from other machines.

If you do want to show a demo to others on a network you trust:

```bash
uv run riskwren --config demo/riskwren.toml serve --host 0.0.0.0 --demo-on-network
```

Anyone who can reach it can then sign in as the demo's risk manager or administrator. Never do this with a database that holds anything real; a demo database holds nothing that is.
