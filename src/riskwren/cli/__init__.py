"""The ``riskwren`` command line. It runs the same code as the web app."""

from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import sqlalchemy.exc

from riskwren import PRODUCT_NAME, TAGLINE, __version__
from riskwren.cli import users
from riskwren.config import (
    CONFIG_NAME,
    ENV_CONFIG,
    Config,
    config_warnings,
    example_config_text,
    find_config_path,
    load_config,
)
from riskwren.core import log as logs
from riskwren.core.errors import RiskWrenError
from riskwren.db import migrate
from riskwren.db.engine import Database
from riskwren.demo import build as demo_build
from riskwren.events import chain
from riskwren.home import DataHome
from riskwren.people import accounts

log = logging.getLogger("riskwren.cli")

EXIT_OK = 0
EXIT_ERROR = 1


def _load(args: argparse.Namespace) -> tuple[Config, DataHome]:
    config = load_config(args.config)
    home = DataHome(config.data.home)
    if home.is_initialized():
        logs.configure(args.verbose, quiet=args.quiet, log_dir=home.logs)
    return config, home


def _database(config: Config, *, current: bool = True) -> Database:
    """Open the database, refusing one whose schema is not what this version expects."""
    db = Database(config.database_url)
    if current:
        try:
            migrate.require_current(db.engine)
        except RiskWrenError:
            db.dispose()
            raise
    return db


def _install_program(db: Database) -> dict[str, int]:
    """Load the default program and the starter libraries where they are missing."""
    from riskwren.events.actor import Actor
    from riskwren.program import packs

    with db.write(Actor.command("Setup")) as session:
        return packs.install(session)


def cmd_program_export(args: argparse.Namespace) -> int:
    import json

    from riskwren.program import packs

    config, _ = _load(args)
    db = _database(config)
    try:
        with db.read() as session:
            text = json.dumps(packs.export(session), indent=2, ensure_ascii=False) + "\n"
    finally:
        db.dispose()
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        sys.stdout.write(text)
    return EXIT_OK


def cmd_program_import(args: argparse.Namespace) -> int:
    import json

    from riskwren.access.principal import Principal
    from riskwren.core.errors import Invalid
    from riskwren.program import packs

    config, _ = _load(args)
    try:
        pack = json.loads(Path(args.file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RiskWrenError(f"{args.file} could not be read as a pack: {exc}") from exc
    db = _database(config)
    principal = Principal.for_command()
    try:
        with db.write(principal.actor) as session:
            try:
                result = packs.import_(session, principal, pack, dry_run=args.dry_run)
            except Invalid as exc:
                raise RiskWrenError(f"{exc} {' '.join(exc.errors.values())}") from exc
    finally:
        db.dispose()
    if not result["changed"]:
        print("Nothing to change: the program already matches the pack.")
        return EXIT_OK
    print("Would change:" if args.dry_run else "Changed:")
    for line in result["changed"]:
        print(f"  {line}")
    return EXIT_OK


def cmd_init(args: argparse.Namespace) -> int:
    path = find_config_path(args.config)
    if path.exists() and not args.force:
        print(f"Using the configuration at {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(example_config_text(), encoding="utf-8")
        print(f"Wrote {path}")
    config = load_config(path)
    home = DataHome(config.data.home)
    home.create()
    print(f"Data home: {home.root}")
    db = Database(config.database_url)
    try:
        before = migrate.current_revision(db.engine)
        migrate.upgrade(db.engine)
        after = migrate.current_revision(db.engine)
    finally:
        db.dispose()
    kind = "SQLite" if config.uses_sqlite else "PostgreSQL"
    if before == after:
        print(f"Database: {kind}, already at migration {after}")
    else:
        print(f"Database: {kind}, now at migration {after}")
    db = Database(config.database_url)
    try:
        loaded = _install_program(db)
        if any(loaded.values()):
            print("Program: loaded the default program and the starter libraries")
        users.first_admin(db, config, args)
    finally:
        db.dispose()
    for warning in config_warnings(config):
        print(f"Note: {warning}")
    print("\nNext: run `riskwren doctor`, then `riskwren serve`.")
    return EXIT_OK


def _port_free(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    config, home = _load(args)
    home.require()
    db = _database(config)  # refuses a schema that is behind
    try:
        with db.read() as session:
            is_demo = demo_build.marker(session) is not None
            if accounts.active_admins(session) == 0:
                raise RiskWrenError(
                    "Nobody could sign in: there is no administrator yet. Create one first:\n"
                    "  riskwren users add you@example.org --name 'Your Name' --role admin"
                )
    finally:
        db.dispose()
    host = args.host or config.server.host
    port = args.port or config.server.port
    if is_demo:
        if args.demo_on_network:
            os.environ["RISKWREN_DEMO_ON_NETWORK"] = "1"
        elif host not in ("127.0.0.1", "localhost", "::1"):
            raise RiskWrenError(
                "This is a demo organization: anyone who can reach it can sign in as any of "
                "its sample people.\nIt listens only on this machine unless you say otherwise: "
                "riskwren serve --demo-on-network"
            )
    workers = 1 if args.reload else (args.workers or config.server.workers)
    if not _port_free(host, port):
        raise RiskWrenError(
            f"Port {port} on {host} is already in use. Stop what is using it, or pick "
            f"another: riskwren serve --port {port + 1}"
        )
    for warning in config_warnings(config):
        log.warning(warning)
    # Each worker process rebuilds the app from the configuration, so name it for them.
    os.environ[ENV_CONFIG] = str(config.path)
    print(f"{PRODUCT_NAME} {__version__} on http://{host}:{port}")
    uvicorn.run(
        "riskwren.api.app:create_app_from_env",
        factory=True,
        host=host,
        port=port,
        workers=workers if workers > 1 else None,
        reload=args.reload,
        reload_dirs=[str(Path(__file__).resolve().parent.parent)] if args.reload else None,
        log_level="warning" if args.quiet else "info",
        server_header=False,
    )
    return EXIT_OK


def cmd_frameworks_list(args: argparse.Namespace) -> int:
    from riskwren.compliance import frameworks

    config, _ = _load(args)
    db = _database(config)
    try:
        with db.read() as session:
            rows = frameworks.all_(session, retired=True)
            if not rows:
                print("No frameworks are loaded. Load the built-in ones with:")
                print("  riskwren frameworks load --builtin")
                return EXIT_OK
            width = max(len(row.key) for row in rows)
            for row in rows:
                state = "" if row.status == "active" else "  (retired)"
                print(
                    f"{row.key.ljust(width)}  {row.citable_count:>5} requirements  "
                    f"{row.title}, {row.version or 'no version'}{state}"
                )
    finally:
        db.dispose()
    return EXIT_OK


def cmd_frameworks_load(args: argparse.Namespace) -> int:
    import json

    from riskwren.compliance import packs as framework_packs
    from riskwren.core.errors import Conflict
    from riskwren.events.actor import Actor

    if bool(args.file) == bool(args.builtin):
        raise RiskWrenError("Name a pack file, or use --builtin for the ones that ship.")
    config, _ = _load(args)
    pack = None
    if args.file:
        try:
            pack = json.loads(Path(args.file).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RiskWrenError(f"{args.file} could not be read as a pack: {exc}") from exc
        found = framework_packs.problems(pack)
        if found:
            print(f"{args.file} cannot be loaded:")
            for line in found:
                print(f"  {line}")
            return EXIT_ERROR
        if args.dry_run:
            head = pack["pack"]
            print(f"{args.file} is a sound pack: {head['title']} ({head['key']}).")
            return EXIT_OK
    db = _database(config)
    try:
        with db.write(Actor.command("Frameworks")) as session:
            if pack is None:
                added = 0 if args.dry_run else framework_packs.install(session)
                print(f"Loaded {added} built-in framework{'s' if added != 1 else ''}.")
                return EXIT_OK
            try:
                made = framework_packs.load(session, pack)
            except Conflict as exc:
                raise RiskWrenError(str(exc)) from exc
            print(f"Loaded {made.title}: {made.citable_count} requirements.")
    finally:
        db.dispose()
    return EXIT_OK


def cmd_frameworks_show(args: argparse.Namespace) -> int:
    from riskwren.compliance import frameworks
    from riskwren.core.errors import NotFound

    config, _ = _load(args)
    db = _database(config)
    try:
        with db.read() as session:
            try:
                row = frameworks.by_key(session, args.key)
            except NotFound as exc:
                raise RiskWrenError(str(exc)) from exc
            print(f"{row.title} ({row.key})")
            for label, value in (
                ("Version", row.version),
                ("Publisher", row.publisher),
                ("License", row.license),
                ("Text", frameworks.POLICY_LABELS[row.text_policy]),
                ("Source", row.source_url),
                ("Built from", row.built_from),
                ("Pack", row.pack_version),
            ):
                if value:
                    print(f"  {label + ':':<11} {value}")
            held = f"{row.citable_count} requirements in {row.requirement_count} entries"
            print(f"  {'Holds:':<11} {held}")
            for baseline in frameworks.baselines(session, row):
                print(f"  {'Baseline:':<11} {baseline.title}, {baseline.requirement_count}")
    finally:
        db.dispose()
    return EXIT_OK


DEMO_MARKER = ".riskwren-demo"


def cmd_demo(args: argparse.Namespace) -> int:
    import shutil
    import time

    root = Path(args.path).expanduser().resolve()
    marker = root / DEMO_MARKER
    if root.exists() and any(root.iterdir()):
        if not marker.is_file():
            raise RiskWrenError(f"{root} is not empty and is not a demo. Choose another directory.")
        if not args.force:
            raise RiskWrenError(
                f"There is already a demo in {root}. Start it with:\n"
                f"  riskwren --config {root / CONFIG_NAME} serve\n"
                "or rebuild it with --force."
            )
        for name in ("var", CONFIG_NAME):  # only what this command made
            target = root / name
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
    root.mkdir(parents=True, exist_ok=True)
    marker.write_text("A RiskWren demo organization. Safe to delete.\n", encoding="utf-8")
    path = root / CONFIG_NAME
    path.write_text(
        example_config_text().replace("port = 8000", f"port = {args.port}"), encoding="utf-8"
    )
    config = load_config(path, env={})
    DataHome(config.data.home).create()
    started = time.monotonic()
    db = Database(config.database_url)
    try:
        migrate.upgrade(db.engine)
        summary = demo_build.build(db, seed=args.seed, files=DataHome(config.data.home).files)
        with db.engine.connect() as conn:
            report = chain.verify(conn)
    finally:
        db.dispose()
    counts = summary.counts
    print(f"Built the {demo_build.ORGANIZATION} in {root}")
    print(
        f"  {counts.get('units', 0)} units, {counts.get('accounts', 0)} people, "
        f"{counts.get('processes', 0)} processes, {counts.get('systems', 0)} systems, "
        f"{counts.get('third parties', 0)} third parties"
    )
    print(
        f"  {counts.get('risks', 0)} risks, {counts.get('controls', 0)} controls, "
        f"{counts.get('plans', 0)} treatment plans, {counts.get('acceptances', 0)} acceptances, "
        f"{counts.get('scopes', 0)} scopes, {counts.get('evidence', 0)} items of evidence"
    )
    print(
        f"  {report.events} events of history, which "
        f"{'verify' if report.ok else 'DO NOT verify'}; {time.monotonic() - started:.0f} seconds"
    )
    print("\nStart it, then open the address it prints and choose who to sign in as:")
    print(f"  riskwren --config {path} serve")
    return EXIT_OK if report.ok else EXIT_ERROR


def cmd_db_upgrade(args: argparse.Namespace) -> int:
    config, home = _load(args)
    home.require()
    db = _database(config, current=False)
    try:
        before = migrate.current_revision(db.engine)
        if before is not None and before not in migrate.script_revisions():
            migrate.require_current(db.engine)  # explains that the database is newer
        migrate.upgrade(db.engine)
        after = migrate.current_revision(db.engine)
        loaded = _install_program(db)
    finally:
        db.dispose()
    print(f"Already at migration {after}." if before == after else f"Upgraded {before} → {after}.")
    if any(loaded.values()):
        print("Loaded what was missing from the default program and the starter libraries.")
    return EXIT_OK


def cmd_db_current(args: argparse.Namespace) -> int:
    config, _ = _load(args)
    db = _database(config, current=False)
    try:
        current = migrate.current_revision(db.engine)
    finally:
        db.dispose()
    head = migrate.head_revision()
    print(f"Database: {current or 'empty'}")
    print(f"This version of {PRODUCT_NAME}: {head}")
    return EXIT_OK if current == head else EXIT_ERROR


def cmd_verify(args: argparse.Namespace) -> int:
    config, _ = _load(args)
    db = _database(config)
    try:
        with db.engine.connect() as conn:
            report = chain.verify(conn)
    finally:
        db.dispose()
    if report.ok:
        print(f"The history holds: {report.events} events, each following the last.")
        print(f"Head: {report.head}")
        return EXIT_OK
    print(f"The history is broken at event {report.broken_at}: {report.reason}.", file=sys.stderr)
    print(f"{report.events} events before it verify.", file=sys.stderr)
    return EXIT_ERROR


def cmd_doctor(args: argparse.Namespace) -> int:
    from riskwren.cli import doctor

    checks = doctor.run(args.config)
    width = max(len(check.name) for check in checks)
    for check in checks:
        print(f"{doctor.MARKS[check.status]} {check.name.ljust(width)}  {check.detail}")
    failed = sum(check.status == doctor.FAIL for check in checks)
    warned = sum(check.status == doctor.WARN for check in checks)
    print()
    if failed:
        print(f"{failed} problem{'s' if failed != 1 else ''} to fix.")
        return EXIT_ERROR
    print(
        "Everything checks out." if not warned else f"Working, with {warned} thing(s) to look at."
    )
    return EXIT_OK


def _users(action: str) -> Callable[[argparse.Namespace], int]:
    def handler(args: argparse.Namespace) -> int:
        config, _ = _load(args)
        db = _database(config)
        try:
            if action == "disable":
                return users.set_status(db, args, "disabled")
            if action == "enable":
                return users.set_status(db, args, "active")
            run = {
                "add": users.add,
                "list": users.list_,
                "reset-password": users.reset_password,
                "roles": users.roles,
            }[action]
            return run(db, args)
        finally:
            db.dispose()

    return handler


ROLE_HELP = (
    "a role: admin, manager, assessor, auditor, steward=unit:CODE, or "
    "leader=unit:CODE,limit:RATING; manager and assessor may also take unit:CODE "
    "(may be repeated)"
)
STDIN_HELP = "read the password from standard input instead of asking"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="riskwren",
        description=f"{PRODUCT_NAME}: {TAGLINE}",
        epilog="Documentation: the docs/ folder of the repository.",
    )
    parser.add_argument("--version", action="version", version=f"{PRODUCT_NAME} {__version__}")
    parser.add_argument(
        "-c",
        "--config",
        metavar="FILE",
        help=f"the configuration file (default: ${ENV_CONFIG}, then ./{CONFIG_NAME})",
    )
    noise = parser.add_mutually_exclusive_group()
    noise.add_argument("-v", "--verbose", action="count", default=0, help="say more")
    noise.add_argument("-q", "--quiet", action="store_true", help="say only what went wrong")
    commands = parser.add_subparsers(title="commands", metavar="COMMAND")

    init = commands.add_parser(
        "init",
        help="set up a new installation",
        description="Write a configuration file if there is none, create the data home, "
        "create or upgrade the database, and create the first administrator if there is "
        "none. Safe to run again.",
    )
    init.add_argument(
        "--force", action="store_true", help="overwrite an existing configuration file"
    )
    init.add_argument(
        "--admin-email", metavar="EMAIL", help="create the first administrator with this address"
    )
    init.add_argument("--admin-name", metavar="NAME", help="the first administrator's name")
    init.add_argument("--password-stdin", action="store_true", help=STDIN_HELP)
    init.set_defaults(handler=cmd_init)

    serve = commands.add_parser(
        "serve",
        help="run the web server",
        description="Run RiskWren's web server. It refuses to start on a database whose schema "
        "is behind; run `riskwren db upgrade` first.",
    )
    serve.add_argument("--host", help="address to listen on (default: from the configuration)")
    serve.add_argument(
        "--port", type=int, help="port to listen on (default: from the configuration)"
    )
    serve.add_argument(
        "--workers", type=int, help="server processes (default: from the configuration)"
    )
    serve.add_argument(
        "--reload", action="store_true", help="restart when the code changes (development)"
    )
    serve.add_argument(
        "--demo-on-network",
        action="store_true",
        help="let a demo organization listen beyond this machine (anyone who reaches it can "
        "sign in as its sample people)",
    )
    serve.set_defaults(handler=cmd_serve)

    demo = commands.add_parser(
        "demo",
        help="build a fictional organization to explore",
        description="Build the Northmere Institute for Health Research, a fictional "
        "organization with two years of history, in its own directory. Everything in it is "
        "made by the same code the app uses. Start it with the command it prints.",
    )
    demo.add_argument(
        "path",
        nargs="?",
        default="demo",
        metavar="PATH",
        help="where to build it (default: ./demo)",
    )
    demo.add_argument(
        "--seed", type=int, default=1, help="a different number gives a different Northmere"
    )
    demo.add_argument(
        "--port", type=int, default=8020, help="the port its server will use (default: 8020)"
    )
    demo.add_argument("--force", action="store_true", help="rebuild a demo that is already there")
    demo.set_defaults(handler=cmd_demo)

    db = commands.add_parser(
        "db", help="look after the database schema", description="Look after the database schema."
    )
    db_commands = db.add_subparsers(title="commands", metavar="COMMAND")
    upgrade = db_commands.add_parser(
        "upgrade",
        help="bring the schema up to this version",
        description="Apply any migrations the database has not had. Export first: "
        "an upgrade cannot be undone except by restoring.",
    )
    upgrade.set_defaults(handler=cmd_db_upgrade)
    current = db_commands.add_parser(
        "current",
        help="show which migration the database is at",
        description="Show which migration the database is at, and which this version expects. "
        "Exits with 1 when they differ.",
    )
    current.set_defaults(handler=cmd_db_current)
    db.set_defaults(handler=lambda _args: db.print_help() or EXIT_OK)

    people = commands.add_parser(
        "users",
        help="manage accounts from the command line",
        description="Manage accounts from the command line: for setting up, and for getting "
        "back in when nobody can sign in. Everyday account management is in the app, under "
        "Admin. Changes made here are recorded in the history as made at the command line.",
    )
    people_commands = people.add_subparsers(title="commands", metavar="COMMAND")
    add = people_commands.add_parser(
        "add",
        help="add an account",
        description="Add an account. It asks for a password unless --password-stdin or "
        "--invite is given.",
    )
    add.add_argument("email", metavar="EMAIL", help="the email address the person signs in with")
    add.add_argument("--name", required=True, help="the person's name")
    add.add_argument("--title", help="their job title")
    add.add_argument("--role", action="append", metavar="ROLE", help=ROLE_HELP)
    add.add_argument(
        "--unit",
        action="append",
        metavar="CODE",
        help="a unit they work in, by code (may be repeated)",
    )
    secret = add.add_mutually_exclusive_group()
    secret.add_argument("--password-stdin", action="store_true", help=STDIN_HELP)
    secret.add_argument(
        "--invite",
        action="store_true",
        help="add them without a password: they can be named on records now, and sign in "
        "once they are given a password or use single sign-on",
    )
    add.set_defaults(handler=_users("add"))
    listing = people_commands.add_parser(
        "list", help="list accounts", description="List every account with its status and roles."
    )
    listing.set_defaults(handler=_users("list"))
    disable = people_commands.add_parser(
        "disable",
        help="stop an account signing in",
        description="Stop an account signing in and end its sessions. Its records and history "
        "are kept. The last active administrator cannot be disabled.",
    )
    enable = people_commands.add_parser(
        "enable",
        help="let a disabled account sign in again",
        description="Let a disabled account sign in again.",
    )
    for name, command in (("disable", disable), ("enable", enable)):
        command.add_argument("email", metavar="EMAIL", help="the account's email address")
        command.set_defaults(handler=_users(name))
    reset = people_commands.add_parser(
        "reset-password",
        help="give an account a new password",
        description="Give an account a new password and end its sessions.",
    )
    reset.add_argument("email", metavar="EMAIL", help="the account's email address")
    reset.add_argument("--password-stdin", action="store_true", help=STDIN_HELP)
    reset.set_defaults(handler=_users("reset-password"))
    role_command = people_commands.add_parser(
        "roles",
        help="show or set an account's roles",
        description="Show an account's roles, or with --set replace the roles granted in "
        "RiskWren. Roles mapped from an identity provider are left alone. The last active "
        "administrator cannot lose that role.",
    )
    role_command.add_argument("email", metavar="EMAIL", help="the account's email address")
    role_command.add_argument(
        "--set", nargs="*", metavar="ROLE", help=ROLE_HELP + "; with none, removes every role"
    )
    role_command.set_defaults(handler=_users("roles"))
    people.set_defaults(handler=lambda _args: people.print_help() or EXIT_OK)

    verify = commands.add_parser(
        "verify",
        help="check that the history has not been altered",
        description="Recompute the hash chain over every event in the history and report the "
        "first one that does not hold. Exits with 1 if the history is broken.",
    )
    verify.set_defaults(handler=cmd_verify)

    held = commands.add_parser(
        "frameworks",
        help="see and load what the organization is held to",
        description="A framework is a source of requirements: a public standard, a "
        "regulation, an agreement's terms. Four public ones ship with RiskWren and are loaded "
        "at installation. Others are loaded from a pack file, or entered in the app.",
    )
    held_commands = held.add_subparsers(dest="frameworks_command", metavar="ACTION")
    held.set_defaults(handler=lambda _args: held.print_help() or EXIT_OK)
    held_list = held_commands.add_parser(
        "list", help="list the frameworks on record", description="List every framework."
    )
    held_list.set_defaults(handler=cmd_frameworks_list)
    held_load = held_commands.add_parser(
        "load",
        help="load a framework pack",
        description="Load a framework from a pack file, or the built-in ones that are "
        "missing. A pack is checked whole first and refused whole if anything is wrong.",
    )
    held_load.add_argument("file", nargs="?", metavar="FILE", help="the pack to load")
    held_load.add_argument(
        "--builtin", action="store_true", help="load the built-in frameworks not yet here"
    )
    held_load.add_argument(
        "--dry-run", action="store_true", help="check the pack, and load nothing"
    )
    held_load.set_defaults(handler=cmd_frameworks_load)
    held_show = held_commands.add_parser(
        "show",
        help="show one framework and where it comes from",
        description="Show a framework's publisher, version, license, and source.",
    )
    held_show.add_argument("key", metavar="KEY", help="the framework's key, such as nist-csf")
    held_show.set_defaults(handler=cmd_frameworks_show)

    program = commands.add_parser(
        "program",
        help="move the program between installations",
        description="The program is everything a risk and compliance team configures: "
        "vocabularies, the risk categories and their appetite, the scoring method, cadences, "
        "and who may accept what. It lives in the database and moves as one file.",
    )
    program_commands = program.add_subparsers(dest="program_command", metavar="ACTION")
    program.set_defaults(handler=lambda _args: program.print_help() or EXIT_OK)
    program_export = program_commands.add_parser(
        "export",
        help="write the program as a pack",
        description="Write the whole program as one JSON document, to a file or to "
        "standard output.",
    )
    program_export.add_argument("--output", "-o", metavar="FILE", help="write to this file")
    program_export.set_defaults(handler=cmd_program_export)
    program_import = program_commands.add_parser(
        "import",
        help="load a program pack",
        description="Load a program pack. The whole pack is checked first, and nothing is "
        "loaded unless all of it can be. A new scoring method is published as a new version; "
        "assessments already made keep the version they were made under.",
    )
    program_import.add_argument("file", metavar="FILE", help="the pack to load")
    program_import.add_argument(
        "--dry-run", action="store_true", help="say what would change, and change nothing"
    )
    program_import.set_defaults(handler=cmd_program_import)

    doctor = commands.add_parser(
        "doctor",
        help="check that this installation is healthy",
        description="Check the configuration, the data home, the database and its schema, "
        "and the history. Exits with 1 if anything must be fixed.",
    )
    doctor.set_defaults(handler=cmd_doctor)

    parser.set_defaults(handler=lambda _args: parser.print_help() or EXIT_OK)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logs.configure(args.verbose, quiet=args.quiet)
    try:
        return int(args.handler(args) or EXIT_OK)
    except RiskWrenError as exc:
        print(f"riskwren: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except (sqlalchemy.exc.OperationalError, sqlalchemy.exc.InterfaceError) as exc:
        reason = str(getattr(exc, "orig", exc)).strip().splitlines()[0]
        print(f"riskwren: the database cannot be reached: {reason}", file=sys.stderr)
        return EXIT_ERROR
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130
