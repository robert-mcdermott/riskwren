# When something goes wrong

This guide is for anyone who is stuck: someone who cannot sign in, cannot see a record, or is refused something they expected to be able to do, and whoever looks after the installation when it misbehaves. Most refusals are RiskWren keeping one of its rules; [The rules it keeps](concepts.md#the-rules-it-keeps) explains them.

## Check the installation

Start here when anything about the server seems wrong.

```bash
uv run riskwren doctor
```

On an installed deployment, run `riskwren doctor` (the [deployment guide](deployment.md) says how, for a container or a service). It checks each of these, and says what to do about anything that fails or deserves a look:

| Check | What it means when it fails |
|---|---|
| **Configuration** | `riskwren.toml` cannot be read, or holds a setting RiskWren does not know or a secret it refuses. The message names the line |
| **Python** | Which Python runs RiskWren |
| **Data home** | The folder that holds files, logs, and exports is missing or cannot be written (run `riskwren init`, or fix its permissions). A warning, not a failure, when its disk has less than 1 GB free |
| **Database** | The database cannot be reached: check the address, the password in the environment, and that the server is running |
| **Schema** | The database is older than this version: back up, then `riskwren db upgrade`. Or it is newer: run the version that made it |
| **History guard** | The database has lost the triggers that stop the history being changed. Restore from a backup, and find out who changed the database |
| **History** | An event in the history does not match the chain: something changed it outside RiskWren. The message names the event |
| **Sign-in** | Single sign-on is set up but the provider cannot be reached or does not answer as expected. Without single sign-on it says *local accounts* |
| **Email** | The mail server cannot be reached or refuses the sign-in |
| **Scheduled work** | Scheduled work is not running, so reminders, email, and webhooks are not sent |

`riskwren doctor --production` adds what matters before real people rely on it: the `https://` address, where the server listens, PostgreSQL, a recent backup, a second administrator, email, and that it is not a demo. **Admin → Operations** shows the same in the app.

`riskwren verify` checks the history on its own, and the documents and leadership reports that were frozen, and says where any difference is.

**Logs.** The server writes its log to `logs/riskwren.log` in the data home (`./var` unless configured otherwise), keeping the last five files of 5 MB. For more detail, put `-v` before the command: `riskwren -v serve`. Read a log before you share it outside the organization.

## Signing in

| What happens | What to do |
|---|---|
| The password is not accepted | Check that the email address is the one your account was made with. An administrator can set a new one under **Admin → People**, or with `riskwren users reset-password you@example.org`. There is no self-service reset |
| Sign-in is refused for a while after several tries | Failed attempts to one account, or from one address, are limited. Wait fifteen minutes, or ask an administrator to set a new password |
| Signed out unexpectedly | A session ends after a time without activity and after a longer time in any case (12 hours and 7 days unless configured otherwise), and when the password changes |
| "Sign in with your organization account" fails | An administrator checks **Admin → Single sign-on**: the connection check says what the provider answered. Local passwords still work for administrators |
| Nobody can sign in as an administrator | On the server: `riskwren users add you@example.org --name "Your Name" --role admin`, or reset an existing administrator's password |
| The page says the request is missing its CSRF token | The page was open across a sign-out or a restart. Reload it |

## I cannot see a record

RiskWren decides what each person may see by one rule, and every list, count, and search follows it. You cannot see a record when:

- **It is a risk or control in another unit,** and the program's setting is *Unit* or *Assigned* ([Who sees what](running-the-program.md#who-sees-what)). Ask to be named on it, or ask a steward or manager of that unit.
- **It is restricted.** Only whoever made it, its owners, the stewards, leaders, and managers who cover its unit, auditors, and administrators see it.
- **It is evidence, an issue, or an exception** in a unit you have no role over and are not named on. Working in the unit is not enough for these.
- **It is an incident case** restricted to the people named on it.
- **Your account works in the wrong unit.** **Admin → People** shows which units each person **Works in**; the *Unit* setting uses it.

A record you cannot see is answered as not found, not as forbidden, so that its existence is not given away.

## I am not allowed to do something

| You are refused | Because | What to do |
|---|---|---|
| Recording or confirming a test result of a control | You own the control, or you recorded the result you are trying to confirm | Ask another assessor. A result counts only when a second person who does not own the control confirms it |
| Confirming an issue's closure | You own the issue, or you proposed closing it | Ask another assessor or a manager |
| Deciding an exception | You asked for it | It goes to another leader of the unit, or a manager |
| Accepting a risk | You own it, or its rating is above your limit, or you lead a different unit | Someone with a higher limit, or who leads the unit, accepts it. A manager cannot accept risk |
| Approving a plan or signing off a workpaper (internal audit) | You drafted the plan, or prepared the workpaper | Another auditor, or a leader of the whole organization for a plan |
| Raising a risk or adding a record | Only a unit's steward or a manager adds records | Ask your steward, or, for a risk, report what you have seen |
| Editing a record | You are not its owner, its unit's steward, or a manager | Ask to be named as an owner |
| Linking a risk to another unit's control | You cannot see the control under the program's visibility | A manager links it |
| Changing the program | Only a manager for the whole organization or an administrator shapes it | Ask the risk and compliance team |
| "This token may only read" | The token was made read-only | An administrator makes one that may change things, if it should |
| "This is a judgment a named person makes, not a token" | Rating, accepting, deciding, confirming, approving, publishing, and triage belong to people | Do it in the app as a person |
| "Your role does not allow this" | The route needs a role you do not have | Ask an administrator, if you should have it |

## A figure looks wrong

Figures are worked out from the record, never typed in, and each counts only what its reader may see: two people may see different numbers on the same dashboard, and both are right. Every figure opens the list it counts, which is the quickest way to see what is behind it.

- **A requirement stopped being verified.** Its evidence lapsed, its test result is more than a rating's lifetime old, or a control that answers it was found wanting. Each control in the scope's list says how it came to be where it is ([Readiness](compliance.md#readiness)).
- **A risk is flagged as in doubt.** Something it rests on changed: a control's rating fell, a plan finished, an indicator passed its limit. Assessing the risk again clears it ([When the picture changes](the-register.md#when-the-picture-changes)).
- **A risk's standing changed though nobody touched it.** An acceptance expired, a plan fell behind, or the program's appetite changed.
- **Last quarter's number was different.** Figures are today's. A leadership report keeps the figures of the day it was issued, and **As of a date** shows any record as it stood ([As of a date](running-the-program.md#as-of-a-date)).

## Email, reminders, and webhooks are not arriving

All three are sent by scheduled work.

1. Run `riskwren doctor`: it says whether scheduled work is running. If `[server] scheduler` is off, something else must run `riskwren jobs run` on a schedule ([Scheduled work](configuration.md#scheduled-work)).
2. Look at **Admin → Operations**: each job's last run and its result, and whether it is paused.
3. For email, send yourself a message from **Admin → Operations**, or run `riskwren mail test you@example.org`. People choose under **Your account** whether to get each notice, a daily summary, or none.
4. A reminder is sent once for each date. Moving the date starts again; nothing is sent twice for the same date.
5. For a webhook, its latest deliveries under **Admin → Other systems** show each answer the address gave. **Send a test** checks the address.

## Restore from a backup

A backup is one file, made with `riskwren backup FILE`. To restore it:

1. Stop RiskWren.
2. Make sure the database is empty and the data home has no files: a restore never writes over an installation. Do not run `riskwren init` first, since it fills the database.
3. Check what the backup holds: `riskwren restore FILE --describe`. It names the version and migration that took it.
4. Install that same version of RiskWren, and run `riskwren restore FILE`. It checks every table, every file, and the history against the backup's manifest.
5. If that version is older than the one you run, install the current version, then run `riskwren db upgrade`.
6. Run `riskwren doctor`, then start the server.

The same steps move an installation between SQLite and PostgreSQL. See [Back up and restore](configuration.md#back-up-and-restore), and [Test a restore](deployment.md#test-a-restore) to practice before you need it.

## Get help, and report a problem

- **Questions and problems** go to the project's issue tracker: <https://github.com/robert-mcdermott/riskwren/issues>. Say which version (`riskwren --version`), which database, what you did, what you expected, and what happened, with the output of `riskwren doctor`.
- **Never put real records in an issue.** The demo organization reproduces most problems: build one with `riskwren demo` and say which sample person and which page.
- **A security problem** is reported privately, as [SECURITY.md](../SECURITY.md) explains, never in a public issue.
