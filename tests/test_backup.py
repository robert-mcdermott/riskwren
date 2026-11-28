"""Backup and restore (PLT-15): one portable file, restored only into an empty database, and
checked against itself. Moving between SQLite and PostgreSQL is a backup from one and a
restore into the other; when the suite runs on PostgreSQL, these tests restore from it into
SQLite."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from riskwren import backup
from riskwren.cli import main
from riskwren.db.engine import Database
from riskwren.home import DataHome
from riskwren.policy import documents
from tests.conftest import Instance
from tests.people import People
from tests.test_documents import publish
from tests.test_risks import who


def _with_a_file(instance: Instance, people: People) -> None:
    """A published document with an attachment, so the backup holds a stored file."""
    steward, leader = who(instance.db, people, "steward"), who(instance.db, people, "leader")
    with instance.db.write(steward.actor) as session:
        paper = documents.create(session, steward, {
            "name": "Freezer procedure", "kind": "procedure",
            "org_unit_id": people.units["IMM"], "body": "Keep the door shut."})  # fmt: skip
        publish(session, steward, leader, paper)
    stored = instance.home.files / "ab" / "cdef"
    stored.parent.mkdir(parents=True, exist_ok=True)
    stored.write_bytes(b"a stored file")


def _empty(tmp_path: Path, name: str) -> tuple[Database, DataHome]:
    home = DataHome(tmp_path / name)
    home.create()
    return Database(f"sqlite:///{home.database_file}"), home


def test_a_backup_restores_into_an_empty_database_whole(
    instance: Instance, people: People, tmp_path: Path
) -> None:
    _with_a_file(instance, people)
    path = tmp_path / "backup.zip"
    taken = backup.take(instance.db.engine, instance.home, path)
    assert taken.tables > 100 and taken.rows > 0 and taken.files == 1 and taken.events > 0
    with pytest.raises(backup.BackupError, match="already exists"):
        backup.take(instance.db.engine, instance.home, path)

    db, home = _empty(tmp_path, "restored")
    try:
        done = backup.restore(db.engine, home, path)
        assert done.problems == []
        assert (done.rows, done.files, done.events) == (taken.rows, 1, taken.events)
        assert (home.files / "ab" / "cdef").read_bytes() == b"a stored file"
        # A second restore over it is refused: nothing is overwritten or mixed in.
        with pytest.raises(backup.BackupError, match="not empty"):
            backup.restore(db.engine, home, path)
        # The restored copy backs up to the very same tables and history.
        again = backup.take(db.engine, home, tmp_path / "again.zip")
        first, second = backup.read_manifest(path), backup.read_manifest(tmp_path / "again.zip")
        assert first["tables"] == second["tables"] and first["history"] == second["history"]
        assert again.events == taken.events
    finally:
        db.dispose()


def test_a_changed_backup_is_found_out(instance: Instance, people: People, tmp_path: Path) -> None:
    _with_a_file(instance, people)
    path = tmp_path / "backup.zip"
    backup.take(instance.db.engine, instance.home, path)
    changed = tmp_path / "changed.zip"
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(changed, "w") as out:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "tables/org_unit.jsonl":
                data = data.replace(b"Immunology", b"Immunolog")
            out.writestr(item, data)
    db, home = _empty(tmp_path, "restored")
    try:
        done = backup.restore(db.engine, home, changed)
        assert any("org_unit" in problem for problem in done.problems)
    finally:
        db.dispose()


def test_a_backup_from_another_version_or_naming_files_outside_is_refused(
    instance: Instance, people: People, tmp_path: Path
) -> None:
    path = tmp_path / "backup.zip"
    backup.take(instance.db.engine, instance.home, path)

    def rewrite(name: str, change) -> Path:  # type: ignore[no-untyped-def]
        target = tmp_path / name
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(target, "w") as out:
            for item in source.infolist():
                data = source.read(item.filename)
                if item.filename == "manifest.json":
                    manifest = json.loads(data)
                    change(manifest)
                    data = json.dumps(manifest).encode()
                out.writestr(item, data)
        return target

    older = rewrite("older.zip", lambda m: m.update(migration="0001", version="0.1.0"))
    db, home = _empty(tmp_path, "restored")
    try:
        with pytest.raises(backup.BackupError, match=r"Restore it with RiskWren 0\.1\.0"):
            backup.restore(db.engine, home, older)
        outside = rewrite("outside.zip", lambda m: m["files"].update({"files/../../x": "0"}))
        with pytest.raises(backup.BackupError, match="outside the data home"):
            backup.restore(db.engine, home, outside)
    finally:
        db.dispose()
    with pytest.raises(backup.BackupError, match="not a RiskWren backup"):
        backup.read_manifest(tmp_path / "older.zip.missing")


def test_the_commands_back_up_and_restore(
    instance: Instance, people: People, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "backup.zip"
    assert main(["--config", str(instance.path), "backup", str(path)]) == 0
    assert "Backed up" in capsys.readouterr().out
    target = tmp_path / "target"
    target.mkdir()
    (target / "riskwren.toml").write_text('[data]\nhome = "var"\n', encoding="utf-8")
    config = ["--config", str(target / "riskwren.toml")]
    # The target is always SQLite here: the suite's own database may be PostgreSQL.
    with pytest.MonkeyPatch.context() as patch:
        patch.delenv("RISKWREN_DATABASE_URL", raising=False)
        assert main([*config, "restore", "--describe", str(path)]) == 0
        assert "tables" in capsys.readouterr().out
        assert main([*config, "restore", str(path)]) == 0
        assert "match the backup" in capsys.readouterr().out
        assert main([*config, "verify"]) == 0


def test_doctor_says_what_stands_between_it_and_production(
    instance: Instance,
    people: People,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    as_role,  # type: ignore[no-untyped-def]
) -> None:
    from riskwren.cli import doctor

    found = {
        check.name: check.status for check in doctor.going_live(instance.config, instance.home)
    }
    assert found["Address"] == doctor.FAIL and found["Backups"] == doctor.FAIL
    backup.take(instance.db.engine, instance.home, tmp_path / "now.zip")
    again = {check.name: check for check in doctor.going_live(instance.config, instance.home)}
    assert again["Backups"].status == doctor.OK and "now.zip" in again["Backups"].detail
    assert main(["--config", str(instance.path), "doctor", "--production"]) == 1
    assert "Backups" in capsys.readouterr().out
    shown = as_role("admin").get("/api/v1/admin/operations").json()["data"]
    assert shown["last_backup"]["path"].endswith("now.zip") and shown["migration"]
    assert {check["name"] for check in shown["checks"]} >= {"Address", "Backups", "Administrators"}
    assert as_role("manager").get("/api/v1/admin/operations").status_code == 403
