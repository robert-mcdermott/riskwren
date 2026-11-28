"""Backing an installation up to one file, and restoring it into an empty database.

A backup is portable: every table is written as JSON lines, row by row in the order of its
primary key, with every stored file and a manifest that counts and fingerprints each. The
same file restores into SQLite or PostgreSQL, so moving between them is a backup from one
and a restore into the other. A restore goes only into an empty database, and only with the
version of RiskWren whose migrations the backup was taken at; it then checks every table,
every file, and the history against the manifest.
"""

from __future__ import annotations

import base64
import hashlib
import json
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import Date, Integer, Table, delete, func, inspect, select, text, update
from sqlalchemy.engine import Connection, Engine

from riskwren import PRODUCT_NAME, __version__
from riskwren.core.clock import utc_now
from riskwren.core.errors import RiskWrenError
from riskwren.db import migrate
from riskwren.db.base import Base
from riskwren.db.types import UtcDateTime
from riskwren.events import chain
from riskwren.home import DataHome

FORMAT = 1
MANIFEST = "manifest.json"
# Folders of the data home that are the installation's own. Exports and logs are not kept:
# exports can be made again, and logs belong to the machine.
FOLDERS = ("files", "brand")
BATCH = 1000


class BackupError(RiskWrenError):
    """A backup cannot be taken or restored. The message says why."""


def _encode(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes | memoryview):
        return {"$bytes": base64.b64encode(bytes(value)).decode("ascii")}
    return value


def _line(row: dict[str, Any]) -> str:
    """A row as one line of JSON, the same whichever database it was read from."""
    return json.dumps({key: _encode(value) for key, value in row.items()}, sort_keys=True,
                      ensure_ascii=False, separators=(",", ":"))  # fmt: skip


def _decoder(table: Table) -> dict[str, Any]:
    """For each column that JSON cannot carry as it is, how to read it back."""
    found: dict[str, Any] = {}
    for column in table.columns:
        kind = column.type
        if isinstance(kind, UtcDateTime):
            found[column.name] = datetime.fromisoformat
        elif isinstance(kind, Date):
            found[column.name] = date.fromisoformat
    return found


def _decode(row: dict[str, Any], decoders: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key, value in row.items():
        if isinstance(value, dict) and set(value) == {"$bytes"}:
            value = base64.b64decode(value["$bytes"])
        elif value is not None and key in decoders:
            value = decoders[key](value)
        out[key] = value
    return out


def _tables(engine: Engine | Connection) -> list[Table]:
    """Every table of this version of RiskWren that the database has, parents before the
    tables that name them."""
    present = set(inspect(engine).get_table_names())
    return [table for table in Base.metadata.sorted_tables if table.name in present]


def _ordered(table: Table) -> Any:
    keys = list(table.primary_key.columns) or list(table.columns)
    return select(table).order_by(*keys)


def _rows(conn: Connection, table: Table) -> Iterator[dict[str, Any]]:
    result = conn.execution_options(stream_results=True, yield_per=BATCH).execute(_ordered(table))
    for row in result.mappings():
        yield dict(row)


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _stored_files(home: DataHome) -> Iterator[tuple[str, Path]]:
    for folder in FOLDERS:
        base = home.root / folder
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                yield f"{folder}/{path.relative_to(base).as_posix()}", path


@dataclass
class Summary:
    """What a backup or a restore did, to print and to check."""

    path: Path
    version: str
    migration: str
    database: str
    taken_at: str
    rows: int = 0
    tables: int = 0
    files: int = 0
    events: int = 0
    head: str | None = None
    problems: list[str] = field(default_factory=list)


def _snapshot(conn: Connection) -> None:
    """Read everything as of one moment, while others go on writing."""
    if conn.dialect.name == "postgresql":
        conn.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")


def take(engine: Engine, home: DataHome, path: Path) -> Summary:
    """Write the whole installation to ``path``, as of one moment."""
    migration = migrate.current_revision(engine)
    if migration is None or migration != migrate.head_revision():
        raise BackupError("Bring the database up to date with `riskwren db upgrade` first.")
    path = Path(path)
    if path.exists():
        raise BackupError(f"{path} already exists. Name a new file.")
    taken = utc_now().isoformat()
    summary = Summary(path, __version__, migration, engine.dialect.name, taken)
    manifest: dict[str, Any] = {
        "format": FORMAT, "product": PRODUCT_NAME, "version": __version__,
        "migration": migration, "database": engine.dialect.name, "taken_at": taken,
        "tables": {}, "files": {},
    }  # fmt: skip
    partial = path.with_name(path.name + ".partial")
    try:
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            with engine.connect() as conn, conn.begin():
                _snapshot(conn)
                for table in _tables(conn):
                    digest = hashlib.sha256()
                    count = 0
                    with archive.open(f"tables/{table.name}.jsonl", "w") as out:
                        for row in _rows(conn, table):
                            line = _line(row) + "\n"
                            data = line.encode("utf-8")
                            out.write(data)
                            digest.update(data)
                            count += 1
                    manifest["tables"][table.name] = {"rows": count, "sha256": digest.hexdigest()}
                    summary.rows += count
                    summary.tables += 1
                report = chain.verify(conn)
                if not report.ok:
                    raise BackupError(
                        f"The history is broken at event {report.broken_at}: {report.reason}. "
                        "Nothing was backed up."
                    )
                manifest["history"] = {"events": report.events, "head": report.head}
                summary.events, summary.head = report.events, report.head
            for name, source in _stored_files(home):
                manifest["files"][name] = _digest_file(source)
                archive.write(source, f"data/{name}")
                summary.files += 1
            archive.writestr(MANIFEST, json.dumps(manifest, indent=1, sort_keys=True))
        partial.replace(path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    _note(home, summary)
    return summary


NOTE = "backups.json"


def _note(home: DataHome, summary: Summary) -> None:
    """Where and when the last backup was taken, for `doctor --production` and Admin."""
    note = {"path": str(summary.path.resolve()), "taken_at": summary.taken_at,
            "bytes": summary.path.stat().st_size, "rows": summary.rows, "files": summary.files,
            "events": summary.events}  # fmt: skip
    (home.root / NOTE).write_text(json.dumps({"last": note}, indent=1) + "\n", encoding="utf-8")


def last(home: DataHome) -> dict[str, Any] | None:
    """The last backup this installation knows of, or None."""
    try:
        return json.loads((home.root / NOTE).read_text(encoding="utf-8")).get("last")
    except (OSError, ValueError):
        return None


def read_manifest(path: Path) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read(MANIFEST))
    except (OSError, KeyError, zipfile.BadZipFile, ValueError) as exc:
        raise BackupError(f"{path} is not a {PRODUCT_NAME} backup.") from exc
    if manifest.get("product") != PRODUCT_NAME or manifest.get("format") != FORMAT:
        raise BackupError(f"{path} is not a {PRODUCT_NAME} backup this version can read.")
    return manifest


def _empty(engine: Engine) -> bool:
    if migrate.current_revision(engine) is not None:
        return False
    return not [name for name in inspect(engine).get_table_names() if name != "alembic_version"]


def _clear(conn: Connection, tables: list[Table]) -> None:
    """Take out the rows the migrations themselves put in, such as the first counters."""
    for table in reversed(tables):
        conn.execute(delete(table))


def _self_references(table: Table) -> list[str]:
    return [fk.parent.name for fk in table.foreign_keys if fk.column.table is table]


def _load(conn: Connection, archive: zipfile.ZipFile, table: Table) -> int:
    """Insert one table's rows. A column naming another row of the same table is filled in
    afterwards, so that the order of the rows never matters."""
    decoders = _decoder(table)
    later = _self_references(table)
    keys = [column.name for column in table.primary_key.columns]
    fill: list[dict[str, Any]] = []
    batch: list[dict[str, Any]] = []
    count = 0
    with archive.open(f"tables/{table.name}.jsonl") as handle:
        for raw in handle:
            row = _decode(json.loads(raw), decoders)
            if later and any(row.get(name) is not None for name in later):
                fill.append({**{k: row[k] for k in keys}, **{n: row[n] for n in later}})
                row = {**row, **dict.fromkeys(later)}
            batch.append(row)
            count += 1
            if len(batch) >= BATCH:
                conn.execute(table.insert(), batch)
                batch = []
    if batch:
        conn.execute(table.insert(), batch)
    for values in fill:
        where = [table.c[k] == values[k] for k in keys]
        conn.execute(update(table).where(*where).values({n: values[n] for n in later}))
    return count


def _reset_sequences(conn: Connection, tables: list[Table]) -> None:
    """On PostgreSQL, start each table's numbering after the rows restored into it."""
    if conn.dialect.name != "postgresql":
        return
    for table in tables:
        keys = list(table.primary_key.columns)
        if len(keys) != 1 or not isinstance(keys[0].type, Integer):
            continue
        column = keys[0]
        sequence = conn.scalar(
            text("SELECT pg_get_serial_sequence(:t, :c)"), {"t": table.name, "c": column.name}
        )
        if sequence is None:
            continue
        highest = conn.scalar(select(func.max(column)))
        conn.execute(
            text("SELECT setval(:s, :v, :called)"),
            {"s": sequence, "v": highest or 1, "called": highest is not None},
        )


def check(engine: Engine, manifest: dict[str, Any]) -> list[str]:
    """Every table read back and fingerprinted as the backup fingerprinted it."""
    problems = []
    tables = {table.name: table for table in _tables(engine)}
    with engine.connect() as conn, conn.begin():
        for name, expected in manifest["tables"].items():
            table = tables.get(name)
            if table is None:
                problems.append(f"Table {name} is in the backup but not in this version.")
                continue
            digest = hashlib.sha256()
            count = 0
            for row in _rows(conn, table):
                digest.update((_line(row) + "\n").encode("utf-8"))
                count += 1
            if count != expected["rows"] or digest.hexdigest() != expected["sha256"]:
                problems.append(f"Table {name} does not match the backup: {count} rows read back, "
                                f"{expected['rows']} backed up.")  # fmt: skip
        report = chain.verify(conn)
        history = manifest.get("history", {})
        if not report.ok:
            problems.append(f"The history is broken at event {report.broken_at}: {report.reason}.")
        elif report.head != history.get("head") or report.events != history.get("events"):
            problems.append("The history does not end where the backup's did.")
    return problems


def restore(engine: Engine, home: DataHome, path: Path) -> Summary:
    """Load a backup into an empty database and data home, then check it against itself."""
    path = Path(path)
    manifest = read_manifest(path)
    head = migrate.head_revision()
    if manifest["migration"] != head:
        raise BackupError(
            f"This backup was taken by {PRODUCT_NAME} {manifest['version']} (migration "
            f"{manifest['migration']}); this is {__version__} (migration {head}). Restore it with "
            f"{PRODUCT_NAME} {manifest['version']}, then upgrade."
        )
    if not _empty(engine):
        raise BackupError(
            "The database is not empty. A backup is restored only into an empty database, so "
            "that nothing already there is overwritten or mixed in."
        )
    if home.is_initialized() and any(home.files.iterdir()):
        raise BackupError(f"The data home at {home.root} already holds files.")
    summary = Summary(path, manifest["version"], manifest["migration"], engine.dialect.name,
                      manifest["taken_at"])  # fmt: skip
    home.create()
    migrate.upgrade(engine)
    tables = _tables(engine)
    with zipfile.ZipFile(path) as archive:
        missing = [t.name for t in tables if t.name not in manifest["tables"]]
        if missing:
            raise BackupError(f"The backup has no table {missing[0]}.")
        with engine.connect() as conn, conn.begin():
            _clear(conn, tables)
            for table in tables:
                summary.rows += _load(conn, archive, table)
                summary.tables += 1
            _reset_sequences(conn, tables)
        root = home.root.resolve()
        for name, expected in manifest["files"].items():
            relative = PurePosixPath(name)
            if relative.is_absolute() or ".." in relative.parts or relative.parts[0] not in FOLDERS:
                raise BackupError(f"The backup names a file outside the data home: {name}.")
            target = (root / Path(*relative.parts)).resolve()
            if root not in target.parents:
                raise BackupError(f"The backup names a file outside the data home: {name}.")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(f"data/{name}") as source, target.open("wb") as out:
                digest = hashlib.sha256()
                for block in iter(lambda source=source: source.read(1 << 20), b""):
                    digest.update(block)
                    out.write(block)
            if digest.hexdigest() != expected:
                summary.problems.append(f"The file {name} does not match the backup.")
            summary.files += 1
    summary.problems += check(engine, manifest)
    history = manifest.get("history", {})
    summary.events, summary.head = history.get("events", 0), history.get("head")
    return summary


def describe(path: Path) -> dict[str, Any]:
    """What a backup holds, from its manifest, without restoring it."""
    manifest = read_manifest(path)
    return {
        "version": manifest["version"], "migration": manifest["migration"],
        "database": manifest["database"], "taken_at": manifest["taken_at"],
        "tables": len(manifest["tables"]),
        "rows": sum(t["rows"] for t in manifest["tables"].values()),
        "files": len(manifest["files"]), "history": manifest.get("history", {}),
    }  # fmt: skip


__all__ = [
    "BackupError",
    "Summary",
    "check",
    "describe",
    "last",
    "read_manifest",
    "restore",
    "take",
]
