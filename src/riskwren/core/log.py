"""Logging to the console and, once there is a data home, to a file in it."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure(verbosity: int = 0, *, quiet: bool = False, log_dir: Path | None = None) -> None:
    """Set up the ``riskwren`` logger. Request bodies and form answers are never logged."""
    level = logging.WARNING if quiet else (logging.DEBUG if verbosity > 0 else logging.INFO)
    logger = logging.getLogger("riskwren")
    logger.setLevel(level)
    logger.handlers.clear()
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(console)
    if log_dir is not None and log_dir.is_dir():
        file = RotatingFileHandler(log_dir / "riskwren.log", maxBytes=5_000_000, backupCount=5)
        file.setFormatter(logging.Formatter(FORMAT))
        logger.addHandler(file)
    logger.propagate = False


# Reports made without a name keep no address, and so the server's own access log is not told
# of them either. (A proxy in front keeps its own log: see docs/configuration.md.)
UNLOGGED = ("/report", "/api/v1/anonymous-reports")


class _Unnamed(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args if isinstance(record.args, tuple) else ()
        path = str(args[2]) if len(args) > 2 else ""
        return not any(
            path == root or path.startswith((f"{root}/", f"{root}?")) for root in UNLOGGED
        )


def quiet_unnamed_reports() -> None:
    """Leave reports made without a name out of the server's access log."""
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(each, _Unnamed) for each in access.filters):
        access.addFilter(_Unnamed())
