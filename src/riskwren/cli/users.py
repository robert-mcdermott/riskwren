"""``riskwren users``: accounts from the command line, for setup and for recovery."""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.config import Config
from riskwren.core.errors import Invalid, NotFound, RiskWrenError
from riskwren.db.engine import Database
from riskwren.db.models import Account
from riskwren.people import accounts, imports, units

ME = Principal.for_command()


def read_password(*, from_stdin: bool) -> str:
    """A new password: one line from standard input, or typed twice at the terminal."""
    if from_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    if not sys.stdin.isatty():
        raise RiskWrenError("No terminal to ask for a password. Pass --password-stdin.")
    first = getpass.getpass("New password: ")
    if getpass.getpass("Again: ") != first:
        raise RiskWrenError("The two passwords did not match.")
    return first


def _find(session: Session, email: str) -> Account:
    account = accounts.by_email(session, email)
    if account is None:
        raise NotFound(f"There is no account for {email}.")
    return account


def _explain(exc: Invalid) -> RiskWrenError:
    details = "; ".join(exc.errors.values())
    return RiskWrenError(f"{exc} {details}".strip())


def describe_roles(session: Session, account_id: int) -> str:
    by_id = {unit.id: unit for unit in units.all_units(session)}
    parts = []
    for grant in accounts.grants_of(session, account_id):
        text = grant.role
        if grant.org_unit_id is not None:
            unit = by_id.get(grant.org_unit_id)
            text += f"={unit.code or unit.name}" if unit else f"=unit {grant.org_unit_id}"
        if grant.accept_limit:
            text += f" (accepts up to {grant.accept_limit})"
        if grant.source != "local":
            text += " (from the identity provider)"
        parts.append(text)
    return ", ".join(parts) or "member"


def add(db: Database, args: argparse.Namespace) -> int:
    password = None if args.invite else read_password(from_stdin=args.password_stdin)
    try:
        with db.write(ME.actor) as session:
            grants = [imports.parse_role(session, spec) for spec in args.role or []]
            account = accounts.create(
                session, ME, email=args.email, display_name=args.name, title=args.title,
                password=password, grants=grants,
            )  # fmt: skip
            unit_ids = []
            for code in args.unit or []:
                unit = units.by_code(session, code)
                if unit is None:
                    raise NotFound(f"There is no unit with the code {code}.")
                unit_ids.append(unit.id)
            if unit_ids:
                accounts.set_memberships(session, ME, account, unit_ids)
            print(
                f"Added {account.email} ({account.status}): {describe_roles(session, account.id)}"
            )
    except Invalid as exc:
        raise _explain(exc) from exc
    return 0


def list_(db: Database, _args: argparse.Namespace) -> int:
    with db.read() as session:
        found = accounts.search(session)
        if not found:
            print("No accounts yet. Add one: riskwren users add EMAIL --name NAME --role admin")
            return 0
        width = max(len(a.email) for a in found)
        for account in found:
            print(
                f"{account.email.ljust(width)}  {account.status:<8}  {account.display_name}"
                f"  [{describe_roles(session, account.id)}]"
            )
    return 0


def set_status(db: Database, args: argparse.Namespace, status: str) -> int:
    with db.write(ME.actor) as session:
        account = _find(session, args.email)
        accounts.set_status(session, ME, account, status)
    print(f"{args.email} is now {status}.")
    return 0


def reset_password(db: Database, args: argparse.Namespace) -> int:
    with db.read() as session:
        _find(session, args.email)
    password = read_password(from_stdin=args.password_stdin)
    try:
        with db.write(ME.actor) as session:
            accounts.set_password(session, ME, _find(session, args.email), password)
    except Invalid as exc:
        raise _explain(exc) from exc
    print(f"Password set for {args.email}. Their other sessions were ended.")
    return 0


def roles(db: Database, args: argparse.Namespace) -> int:
    if args.set is None:
        with db.read() as session:
            account = _find(session, args.email)
            print(f"{account.email}: {describe_roles(session, account.id)}")
        return 0
    try:
        with db.write(ME.actor) as session:
            account = _find(session, args.email)
            grants = [imports.parse_role(session, spec) for spec in args.set]
            accounts.set_grants(session, ME, account, grants)
            print(f"{account.email}: {describe_roles(session, account.id)}")
    except Invalid as exc:
        raise _explain(exc) from exc
    return 0


def first_admin(db: Database, config: Config, args: argparse.Namespace) -> None:
    """Called by ``init``: make the first administrator if there is none."""
    with db.read() as session:
        if accounts.active_admins(session):
            return
    email, name = args.admin_email, args.admin_name
    if email is None and sys.stdin.isatty() and not args.password_stdin:
        print("\nRiskWren needs an administrator to start with.")
        email = input("Your email address: ").strip()
        name = name or input("Your name: ").strip()
    if not email:
        print(
            "\nNo administrator yet. Create one before starting the server:\n"
            "  riskwren users add you@example.org --name 'Your Name' --role admin"
        )
        return
    password = read_password(from_stdin=args.password_stdin)
    try:
        with db.write(ME.actor) as session:
            existing = accounts.by_email(session, email)
            if existing is not None:
                accounts.set_password(session, ME, existing, password)
                accounts.set_grants(
                    session, ME, existing, [*_local(session, existing.id), _admin()]
                )
            else:
                accounts.create(
                    session, ME, email=email, display_name=name or email.split("@")[0],
                    password=password, grants=[_admin()],
                )  # fmt: skip
    except Invalid as exc:
        raise _explain(exc) from exc
    print(f"Administrator: {accounts.normalize_email(email)}")


def _admin():  # type: ignore[no-untyped-def]
    from riskwren.access.principal import Grant

    return Grant("admin")


def _local(session: Session, account_id: int):  # type: ignore[no-untyped-def]
    from riskwren.access.principal import Grant

    return [
        Grant(g.role, g.org_unit_id, g.accept_limit)
        for g in accounts.grants_of(session, account_id)
        if g.source == "local"
    ]
