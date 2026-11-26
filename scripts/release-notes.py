#!/usr/bin/env python3
"""Print one version's section of the changelog, for the release notes.

uv run python scripts/release-notes.py 0.1.0
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def notes(version: str, text: str) -> str:
    found = re.search(
        rf"^## {re.escape(version)}\b[^\n]*\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL
    )
    if found is None:
        raise SystemExit(f"CHANGELOG.md has no section for {version}")
    return found.group(1).strip() + "\n"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    changelog = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
    sys.stdout.write(notes(sys.argv[1], changelog.read_text(encoding="utf-8")))
