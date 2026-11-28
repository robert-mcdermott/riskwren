"""Generated documentation must match the code. Regenerate with ``UPDATE_DOCS=1 uv run pytest
tests/test_docs.py``."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from riskwren.cli import reference

DOCS = Path(__file__).resolve().parent.parent / "docs"
UPDATE = os.environ.get("UPDATE_DOCS") == "1"


def _check(path: Path, fresh: str) -> None:
    if UPDATE:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(fresh, encoding="utf-8")
    assert path.is_file(), f"{path.name} is missing; run with UPDATE_DOCS=1"
    assert path.read_text(encoding="utf-8") == fresh, (
        f"{path.name} is out of date; run UPDATE_DOCS=1 uv run pytest tests/test_docs.py"
    )


def test_the_command_reference_is_current() -> None:
    _check(DOCS / "cli.md", reference.render())


def test_the_openapi_document_is_current(full_client: TestClient) -> None:
    document = full_client.get("/api/openapi.json").json()
    document["info"]["version"] = "current"  # the version changes every release
    _check(DOCS / "openapi.json", json.dumps(document, indent=2, sort_keys=True) + "\n")


def test_the_shipped_packs_are_what_their_script_writes() -> None:
    """The default program and the starter libraries are data written by a script. A change
    made to the files and not to the script would be lost the next time it ran."""
    import json
    import runpy

    root = Path(__file__).resolve().parent.parent
    made = runpy.run_path(str(root / "scripts" / "build-default-program.py"))
    packs = root / "src" / "riskwren" / "resources" / "packs"
    for name, pack in (
        ("default-program.json", made["PACK"]),
        ("risk-library.json", made["RISK_LIBRARY"]),
        ("starter-controls.json", made["CONTROL_LIBRARY"]),
    ):
        written = json.dumps(pack, indent=2, ensure_ascii=False) + "\n"
        assert (packs / name).read_text(encoding="utf-8") == written, (
            f"{name} differs from scripts/build-default-program.py; change the script and run it"
        )
