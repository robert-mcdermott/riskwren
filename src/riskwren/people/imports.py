"""Bring units and people in from a spreadsheet saved as CSV (INV-01).

Every import can be run dry first. The report lists what would be created and changed and
every problem found, with its row. Nothing is written unless every row is good.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from riskwren.access.principal import Grant, Principal
from riskwren.core.errors import Invalid, PermissionDenied, RiskWrenError
from riskwren.events import audit
from riskwren.people import accounts, units

MAX_ROWS = 20_000
UNIT_COLUMNS = ("code", "name", "kind", "parent_code")
PEOPLE_COLUMNS = ("email", "name", "title", "unit_codes", "roles")


@dataclass
class Report:
    kind: str
    dry_run: bool
    rows: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    problems: list[dict[str, Any]] = field(default_factory=list)

    def problem(self, row: int, message: str) -> None:
        self.problems.append({"row": row, "message": message})

    @property
    def applied(self) -> bool:
        return not self.dry_run and not self.problems

    def to_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "dry_run": self.dry_run,
            "applied": self.applied,
            "rows": self.rows,
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "problems": self.problems,
        }


def _rows(text: str, required: tuple[str, ...], known: tuple[str, ...]) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    header = [(name or "").strip().lower() for name in (reader.fieldnames or [])]
    missing = [name for name in required if name not in header]
    if missing:
        raise Invalid(
            "The file is missing columns.",
            {"file": f"Add the column{'s' if len(missing) > 1 else ''}: {', '.join(missing)}. "
             f"The columns are: {', '.join(known)}."},
        )  # fmt: skip
    rows = []
    for raw in reader:
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        if any(row.values()):
            rows.append(row)
        if len(rows) > MAX_ROWS:
            raise Invalid(
                "The file is too large.", {"file": f"Import at most {MAX_ROWS} rows at a time."}
            )
    return rows


def import_units(session: Session, principal: Principal, text: str, *, dry_run: bool) -> Report:
    """Columns: ``code``, ``name``, ``kind``, ``parent_code``. Units are matched by code. A
    parent may be named before or after its children. Exactly one unit has no parent."""
    if not principal.is_admin:
        raise PermissionDenied("Only an administrator can import units.")
    report = Report("units", dry_run)
    rows = _rows(text, ("code", "name", "kind"), UNIT_COLUMNS)
    report.rows = len(rows)
    existing = {unit.code: unit for unit in units.all_units(session) if unit.code}
    has_root = any(unit.parent_id is None for unit in units.all_units(session))
    seen: dict[str, int] = {}
    for number, row in enumerate(rows, start=2):
        code = row["code"]
        if not code:
            report.problem(number, "A unit needs a code.")
        elif code in seen:
            report.problem(number, f"The code {code} is also on row {seen[code]}.")
        else:
            seen[code] = number
        if not row["name"]:
            report.problem(number, "A unit needs a name.")
        if not row["kind"]:
            report.problem(number, "A unit needs a kind.")
    known = set(existing) | set(seen)
    roots = []
    for number, row in enumerate(rows, start=2):
        parent = row.get("parent_code", "")
        if parent and parent not in known:
            report.problem(
                number, f"The parent {parent} is not in the file or already in RiskWren."
            )
        if parent and parent == row["code"]:
            report.problem(number, "A unit cannot be its own parent.")
        if (
            not parent
            and row["code"]
            and not (row["code"] in existing and existing[row["code"]].parent_id is None)
        ):
            roots.append(number)
    if len(roots) + (1 if has_root else 0) > 1:
        for number in roots:
            report.problem(number, "Only one unit, the organization itself, can have no parent.")
    if report.problems:
        return report

    # Create parents before children: keep passing over the rows until none is waiting.
    with audit.operation(session, "units.import"):
        waiting = list(enumerate(rows, start=2))
        by_code = dict(existing)
        while waiting:
            later = []
            for number, row in waiting:
                parent_code = row.get("parent_code", "")
                if parent_code and parent_code not in by_code:
                    later.append((number, row))
                    continue
                parent_id = by_code[parent_code].id if parent_code else None
                unit = by_code.get(row["code"])
                try:
                    if unit is None:
                        if not dry_run:
                            by_code[row["code"]] = units.create(
                                session, principal, name=row["name"], kind=row["kind"],
                                code=row["code"], parent_id=parent_id,
                            )  # fmt: skip
                        else:
                            by_code[row["code"]] = _Planned(parent_id)  # type: ignore[assignment]
                        report.created += 1
                    else:
                        same = (unit.name, unit.kind, unit.parent_id) == (
                            row["name"], row["kind"].lower(), parent_id,
                        )  # fmt: skip
                        if isinstance(unit, _Planned) or same:
                            report.unchanged += 1
                        else:
                            if not dry_run:
                                changes: dict[str, Any] = {"name": row["name"], "kind": row["kind"]}
                                if parent_id is not None:
                                    changes["parent_id"] = parent_id
                                units.update(session, principal, unit, changes)
                            report.updated += 1
                except RiskWrenError as exc:
                    report.problem(number, str(exc))
            if len(later) == len(waiting):
                for number, _row in later:
                    report.problem(
                        number, "This unit and its parents refer to each other in a loop."
                    )
                break
            waiting = later
    return report


class _Planned:
    """A unit a dry run would have created: enough of one to be a parent."""

    def __init__(self, parent_id: int | None) -> None:
        self.id = -1
        self.parent_id = parent_id


def parse_role(session: Session, text: str) -> Grant:
    """``admin``, ``steward=unit:CODE``, or ``leader=unit:CODE,limit:RATING``."""
    name, _, scope = text.strip().partition("=")
    name = name.strip().lower()
    org_unit_id: int | None = None
    accept_limit: str | None = None
    for part in filter(None, (p.strip() for p in scope.split(","))):
        kind, _, value = part.partition(":")
        kind, value = kind.strip().lower(), value.strip()
        if kind == "unit" and value:
            unit = units.by_code(session, value)
            if unit is None:
                raise Invalid(
                    "The role is not valid.", {"role": f"There is no unit with the code {value}."}
                )
            org_unit_id = unit.id
        elif kind == "limit" and value:
            accept_limit = value.lower()
        else:
            raise Invalid(
                "The role is not valid.",
                {
                    "role": f"{text!r} is not understood. "
                    "Write steward=unit:CODE or leader=unit:CODE,limit:RATING."
                },
            )
    return Grant(name, org_unit_id=org_unit_id, accept_limit=accept_limit)


def import_people(session: Session, principal: Principal, text: str, *, dry_run: bool) -> Report:
    """Columns: ``email``, ``name``, and optionally ``title``, ``unit_codes``, and ``roles``
    (each a list separated by semicolons). People are matched by email. New people are added
    as invited: they can be named on records at once, and sign in once they have a password
    or use single sign-on. Roles and units are set only where the column has a value."""
    if not principal.is_admin:
        raise PermissionDenied("Only an administrator can import people.")
    report = Report("people", dry_run)
    rows = _rows(text, ("email", "name"), PEOPLE_COLUMNS)
    report.rows = len(rows)
    seen: dict[str, int] = {}
    plans = []
    for number, row in enumerate(rows, start=2):
        email = accounts.normalize_email(row["email"])
        before = len(report.problems)
        if not accounts.EMAIL.match(email):
            report.problem(number, f"{row['email'] or '(empty)'} is not an email address.")
        elif email in seen:
            report.problem(number, f"{email} is also on row {seen[email]}.")
        else:
            seen[email] = number
        if not row["name"]:
            report.problem(number, "A person needs a name.")
        unit_ids = []
        for code in filter(None, (c.strip() for c in row.get("unit_codes", "").split(";"))):
            unit = units.by_code(session, code)
            if unit is None:
                report.problem(number, f"There is no unit with the code {code}.")
            else:
                unit_ids.append(unit.id)
        grants = []
        for text_role in filter(None, (r.strip() for r in row.get("roles", "").split(";"))):
            try:
                grant = parse_role(session, text_role)
                accounts.check_grant(session, grant)
                grants.append(grant)
            except Invalid as exc:
                report.problem(number, "; ".join(exc.errors.values()) or str(exc))
        if len(report.problems) == before:
            plans.append((number, email, row, unit_ids, grants))
    if report.problems:
        return report

    with audit.operation(session, "people.import"):
        for number, email, row, unit_ids, grants in plans:
            account = accounts.by_email(session, email)
            title = row.get("title", "") or None
            try:
                if account is None:
                    report.created += 1
                    if not dry_run:
                        account = accounts.create(
                            session, principal, email=email, display_name=row["name"], title=title
                        )
                        if unit_ids:
                            accounts.set_memberships(session, principal, account, unit_ids)
                        if grants:
                            accounts.set_grants(session, principal, account, grants)
                    continue
                details: dict[str, Any] = {}
                if account.display_name != row["name"]:
                    details["display_name"] = row["name"]
                if title and account.title != title:
                    details["title"] = title
                have_units = [m.org_unit_id for m in accounts.memberships_of(session, account.id)]
                move = bool(unit_ids) and have_units != unit_ids
                have_grants = {
                    (g.role, g.org_unit_id, g.accept_limit)
                    for g in accounts.grants_of(session, account.id)
                    if g.source == "local"
                }
                regrant = bool(grants) and have_grants != {
                    (g.role, g.org_unit_id, g.accept_limit) for g in grants
                }
                if not (details or move or regrant):
                    report.unchanged += 1
                    continue
                report.updated += 1
                if dry_run:
                    continue
                if details:
                    accounts.update(session, principal, account, details)
                if move:
                    accounts.set_memberships(session, principal, account, unit_ids)
                if regrant:
                    accounts.set_grants(session, principal, account, grants)
            except RiskWrenError as exc:
                report.problem(number, str(exc))
    return report
