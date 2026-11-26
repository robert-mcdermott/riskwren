"""The data home: the one directory that holds everything not in the database."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from riskwren.core.errors import DataHomeError

MARKER = ".riskwren-home"
MARKER_TEXT = (
    "This directory is a RiskWren data home.\n"
    "It holds evidence files, uploaded logos, exports, logs, and, with SQLite, the database.\n"
    "Back it up as a whole. Do not edit its contents by hand.\n"
)


@dataclass(frozen=True)
class DataHome:
    root: Path

    @property
    def files(self) -> Path:
        """Evidence and attachments, stored by their SHA-256."""
        return self.root / "files"

    @property
    def brand(self) -> Path:
        """Uploaded logos and other brand images."""
        return self.root / "brand"

    @property
    def exports(self) -> Path:
        return self.root / "exports"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def database_file(self) -> Path:
        """Where the SQLite database lives when no database URL is configured."""
        return self.root / "riskwren.db"

    @property
    def marker(self) -> Path:
        return self.root / MARKER

    def create(self) -> None:
        """Make the data home. Safe to run again."""
        for path in (self.root, self.files, self.brand, self.exports, self.logs):
            path.mkdir(parents=True, exist_ok=True)
        if not self.marker.exists():
            self.marker.write_text(MARKER_TEXT, encoding="utf-8")

    def is_initialized(self) -> bool:
        return self.marker.is_file() and self.files.is_dir()

    def require(self) -> None:
        if not self.is_initialized():
            raise DataHomeError(
                f"No initialized data home at {self.root}. Run `riskwren init` first."
            )
        if not os.access(self.root, os.W_OK):
            raise DataHomeError(f"The data home at {self.root} is not writable.")
