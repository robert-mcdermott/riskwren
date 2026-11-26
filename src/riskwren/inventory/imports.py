"""Bring records in from a spreadsheet saved as CSV (INV-08).

The file's columns are matched to a record's fields, by their names where they can be and
by the person where they cannot. Every row then goes through the same service that adds a
record by hand, so the same rules apply and the same history is written. A dry run does all
of that and keeps none of it. Nothing is loaded unless every row can be.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.errors import Invalid, NotFound, RiskWrenError
from riskwren.db.models import Account, OrgUnit
from riskwren.events import audit
from riskwren.inventory import records
from riskwren.inventory.registry import TYPES, RecordType
from riskwren.people import accounts
from riskwren.people.imports import MAX_ROWS, Report
from riskwren.program import vocab
from riskwren.reporting import exports

# The kinds of record a spreadsheet can bring in. What is judged (a rating, a test, an
# acceptance) is never imported: a judgment is made here, by a named person.
IMPORTABLE = ("process", "system", "third_party", "information", "risk", "control")
LABELS = {
    "ref": "Reference", "name": "Name", "summary": "Summary", "unit": "Unit",
    "owners": "Owners", "category": "Category", "criticality": "Criticality",
    "data_class": "Data class", "status": "Status", "tags": "Tags",
    "restricted": "Restricted", "external_refs": "External references",
}  # fmt: skip
HINTS = {
    "ref": "Kept if it is free; otherwise the next one is given",
    "unit": "A unit's code, or its name",
    "owners": "Email addresses, separated by semicolons",
    "tags": "Separated by semicolons",
    "restricted": "yes or no",
    "external_refs": "system:identifier, separated by semicolons",
    "category": "A risk category's key, or its name",
}
# Other headings a column is often given.
ALSO = {
    "ref": ("reference", "id", "identifier"),
    "name": ("title",),
    "summary": ("description", "notes"),
    "unit": ("org unit", "department", "unit code", "owning unit"),
    "owners": ("owner", "owner email", "owned by"),
    "external_refs": ("external reference", "external references", "external ids"),
    "data_class": ("data classification", "classification"),
}
SPLIT = re.compile(r"\s*[;\n]\s*")
YES = {"yes", "y", "true", "1", "x"}
NO = {"no", "n", "false", "0", ""}


def record_type_for(key_or_path: str) -> RecordType:
    for record_type in TYPES.values():
        if key_or_path in (record_type.key, record_type.path):
            if record_type.key in IMPORTABLE:
                return record_type
            break
    raise NotFound(f"{key_or_path!r} is not a kind of record that can be imported.")


def fields_for(record_type: RecordType) -> list[dict[str, Any]]:
    """What a file can say about each record of this type, in the order an export writes it."""
    own = {field.name: field for field in record_type.fields}
    # A field with a default need not be in the file: a record left without it gets the default.
    needed = {"name", "unit"} | {
        name for name, field in own.items() if field.required and field.default is None
    }
    if record_type.key == "risk":
        needed.add("category")
    return [
        {
            "name": name,
            "label": own[name].label if name in own else LABELS[name],
            "required": name in needed,
            "hint": HINTS.get(name),
        }
        for name in exports.importable(record_type)
    ]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def read(text: str) -> tuple[list[str], list[dict[str, str]]]:
    """The file's column headings, and its rows that are not blank."""
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    try:
        header = [cell.strip() for cell in next(reader)]
    except StopIteration:
        raise Invalid("The file is empty.", {"file": "It needs a header row."}) from None
    if len(set(filter(None, header))) != len(list(filter(None, header))):
        raise Invalid("The file could not be read.", {"file": "Two columns have the same heading."})
    rows: list[dict[str, str]] = []
    for cells in reader:
        row = {
            name: exports.unguard((cells[index] if index < len(cells) else "").strip())
            for index, name in enumerate(header)
            if name
        }
        if any(row.values()):
            rows.append(row)
        if len(rows) > MAX_ROWS:
            raise Invalid(
                "The file is too large.", {"file": f"Import at most {MAX_ROWS} rows at a time."}
            )
    return [name for name in header if name], rows


def guess(header: list[str], fields: list[dict[str, Any]]) -> dict[str, str | None]:
    """Which column is which field, where the headings make it plain."""
    by_norm = {_norm(name): name for name in header}
    found: dict[str, str | None] = {}
    for field in fields:
        names = (field["name"], field["label"], *ALSO.get(field["name"], ()))
        found[field["name"]] = next(
            (by_norm[_norm(name)] for name in names if _norm(name) in by_norm), None
        )
    return found


def columns(record_type: RecordType, text: str) -> dict[str, Any]:
    """Before anything is checked: the file's columns, and which field each is taken for."""
    header, rows = read(text)
    fields = fields_for(record_type)
    mapping = guess(header, fields)
    return {
        "columns": header,
        "rows": len(rows),
        "fields": [{**field, "column": mapping[field["name"]]} for field in fields],
        "unused": [name for name in header if name not in mapping.values()],
    }


class _Lookups:
    """What a row's words are matched against, read once for the whole file."""

    def __init__(self, session: Session, record_type: RecordType) -> None:
        self.units: dict[str, int] = {}
        for unit in session.scalars(select(OrgUnit)):
            self.units[unit.name.lower()] = unit.id
        for unit in session.scalars(select(OrgUnit)):
            if unit.code:
                self.units[unit.code.lower()] = unit.id  # a code wins over a name
        self.people = {
            accounts.normalize_email(email): account_id
            for account_id, email in session.execute(select(Account.id, Account.email))
        }
        self.owner_kinds = set(vocab.keys(session, "owner_kinds"))
        self.vocab: dict[str, dict[str, str]] = {}
        names = {field.name: field.vocab for field in record_type.fields if field.vocab}
        names.update(criticality="criticalities", data_class="data_classes")
        for field, name in names.items():
            self.vocab[field] = {}
            for item in vocab.get(session, name):
                self.vocab[field][str(item["label"]).lower()] = item["key"]
                self.vocab[field][str(item["key"]).lower()] = item["key"]
        self.systems = {}
        for item in vocab.get(session, "external_systems"):
            self.systems[str(item["label"]).lower()] = item["key"]
            self.systems[str(item["key"]).lower()] = item["key"]
        self.categories: dict[str, str] = {}
        if record_type.key == "risk":
            from riskwren.db.models import RiskCategory

            for row in session.scalars(select(RiskCategory)):
                self.categories[row.name.lower()] = row.key
                self.categories[row.key.lower()] = row.key
        model: Any = record_type.model
        self.taken = {
            (name.lower(), unit): ref
            for name, unit, ref in session.execute(select(model.name, model.org_unit_id, model.ref))
        }


def _values(
    record_type: RecordType, row: Mapping[str, str], known: _Lookups, said: list[str]
) -> tuple[dict[str, Any], list[dict[str, Any]] | None]:
    """A row as the values the service takes, and the owners it names. Anything that cannot
    be matched is added to ``said``."""
    values: dict[str, Any] = {}
    owners: list[dict[str, Any]] | None = None
    for name, given in row.items():
        if name == "ref":
            if given:
                values["_ref"] = given
        elif name == "unit":
            unit = known.units.get(given.lower())
            if given and unit is None:
                said.append(f"Unit: there is no unit {given!r}.")
            values["org_unit_id"] = unit
        elif name == "owners":
            if not given:
                continue
            owners = []
            for part in filter(None, SPLIT.split(given)):
                kind, _, email = part.rpartition(":")
                kind = kind.strip().lower() or "owner"
                account = known.people.get(accounts.normalize_email(email))
                if account is None:
                    said.append(f"Owners: nobody has the address {email.strip()!r}.")
                elif kind not in known.owner_kinds:
                    said.append(f"Owners: {kind!r} is not a kind of owner.")
                else:
                    owners.append({"account_id": account, "kind": kind})
        elif name == "tags":
            values["tags"] = [tag for tag in SPLIT.split(given) if tag]
        elif name == "restricted":
            if given.lower() not in YES | NO:
                said.append("Restricted: say yes or no.")
            values["restricted"] = given.lower() in YES
        elif name == "external_refs":
            refs = []
            for part in filter(None, SPLIT.split(given)):
                system, _, value = part.partition(":")
                key = known.systems.get(system.strip().lower())
                if key is None or not value.strip():
                    said.append(
                        f"External references: {part!r} is not a system on record, a colon, "
                        "and an identifier."
                    )
                else:
                    refs.append({"system": key, "value": value.strip()})
            values["external_refs"] = refs
        elif name == "category":
            values["category"] = known.categories.get(given.lower(), given) if given else None
        elif name in known.vocab:
            # A choice is given by its key or by the words people see. One that is neither
            # goes through as written, and the service says what the choices are.
            values[name] = known.vocab[name].get(given.lower(), given) if given else None
        elif name == "status":
            values["status"] = given.lower() or None
        else:
            values[name] = given
    return values, owners


def run(
    session: Session,
    principal: Principal,
    record_type: RecordType,
    text: str,
    *,
    mapping: Mapping[str, str | None] | None = None,
    dry_run: bool,
) -> Report:
    """Check a file, and unless this is a dry run or it has problems, add what it holds.

    ``mapping`` says which column is each field; fields left out are guessed from the
    headings. The caller rolls the transaction back unless the report says it was applied.
    """
    if record_type.key not in IMPORTABLE:
        raise NotFound(f"{record_type.plural.capitalize()} are not imported from a file.")
    header, rows = read(text)
    fields = fields_for(record_type)
    chosen = guess(header, fields)
    for name, column in (mapping or {}).items():
        if name not in chosen:
            raise Invalid(
                "The columns were not understood.", {"mapping": f"{name!r} is not a field."}
            )
        if column and column not in header:
            raise Invalid(
                "The columns were not understood.",
                {"mapping": f"The file has no column {column!r}."},
            )
        chosen[name] = column or None
    missing = [f["label"] for f in fields if f["required"] and not chosen[f["name"]]]
    if missing:
        raise Invalid(
            "The file is missing columns.",
            {"mapping": f"Say which column holds: {', '.join(missing)}."},
        )
    report = Report(record_type.path, dry_run)
    report.rows = len(rows)
    known = _Lookups(session, record_type)
    labels = {f["name"]: f["label"] for f in fields} | {"org_unit_id": "Unit", "_ref": "Reference"}
    with audit.operation(session, f"{record_type.key}.import"):
        for number, raw in enumerate(rows, start=2):
            row = {name: raw.get(column, "") for name, column in chosen.items() if column}
            said: list[str] = []
            values, owners = _values(record_type, row, known, said)
            key = (str(values.get("name") or "").lower(), values.get("org_unit_id"))
            if key[0] and key in known.taken:
                where = known.taken[key]
                said.append(
                    f"A {record_type.label} of this name is already on record in the unit"
                    + (f", as {where}." if where else ", from an earlier row.")
                )
            if said:
                for message in said:
                    report.problem(number, message)
                continue
            try:
                if record_type.key == "risk":
                    from riskwren.risk import register

                    record = register.create(session, principal, values)
                else:
                    record = records.create(session, principal, record_type, values)
                if owners:
                    records.set_owners(session, principal, record_type, record, owners)
            except Invalid as problem:
                for field, message in problem.errors.items():
                    report.problem(number, f"{labels.get(field, field)}: {message}")
                if not problem.errors:
                    report.problem(number, str(problem))
            except RiskWrenError as problem:
                report.problem(number, str(problem))
            else:
                known.taken[key] = ""  # from this file, whatever becomes of it
                report.created += 1
    if not rows:
        report.problem(1, "The file has a header and no rows.")
    return report


def count(session: Session, record_type: RecordType) -> int:
    model: Any = record_type.model
    return int(session.execute(select(func.count()).select_from(model)).scalar_one())


# --- Requirements of one of the organization's own frameworks ------------------------------

REQUIREMENT_FIELDS = [
    {"name": "code", "label": "Code", "required": True, "hint": "Such as 4.2 or DUA-7"},
    {"name": "title", "label": "Title", "required": False, "hint": None},
    {"name": "text", "label": "Text", "required": False, "hint": "What it requires"},
    {"name": "parent", "label": "Parent", "required": False,
     "hint": "The code of the requirement it sits under, from the file or already on record"},
]  # fmt: skip


def requirement_columns(text: str) -> dict[str, Any]:
    header, rows = read(text)
    mapping = guess(header, REQUIREMENT_FIELDS)
    return {
        "columns": header,
        "rows": len(rows),
        "fields": [{**field, "column": mapping[field["name"]]} for field in REQUIREMENT_FIELDS],
        "unused": [name for name in header if name not in mapping.values()],
    }


def requirements(
    session: Session,
    principal: Principal,
    framework: Any,
    text: str,
    *,
    mapping: Mapping[str, str | None] | None = None,
    dry_run: bool,
) -> Report:
    """Add requirements to one of the organization's own frameworks from a file. A parent is
    named by its code and must come before its children, or be on record already."""
    from riskwren.compliance import frameworks

    header, rows = read(text)
    chosen = guess(header, REQUIREMENT_FIELDS)
    for name, column in (mapping or {}).items():
        if name not in chosen or (column and column not in header):
            raise Invalid(
                "The columns were not understood.",
                {"mapping": f"{name!r} is not a field, or the file has no column {column!r}."},
            )
        chosen[name] = column or None
    if not chosen["code"]:
        raise Invalid("The file is missing columns.", {"mapping": "Say which column holds: Code."})
    report = Report("requirements", dry_run)
    report.rows = len(rows)
    labels = {field["name"]: field["label"] for field in REQUIREMENT_FIELDS}
    with audit.operation(session, "requirement.import"):
        for number, raw in enumerate(rows, start=2):
            values = {name: raw.get(column, "") for name, column in chosen.items() if column}
            try:
                frameworks.add_requirement(session, principal, framework, values)
            except Invalid as problem:
                for field, message in problem.errors.items():
                    report.problem(number, f"{labels.get(field, field)}: {message}")
            except RiskWrenError as problem:
                report.problem(number, str(problem))
                if number == 2:
                    break  # the framework itself cannot take them; every row would say so
            else:
                report.created += 1
    if not rows:
        report.problem(1, "The file has a header and no rows.")
    return report
