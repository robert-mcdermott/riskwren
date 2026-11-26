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
