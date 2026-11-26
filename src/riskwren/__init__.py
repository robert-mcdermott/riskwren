"""RiskWren: an open system of record for governance, risk, and compliance."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("riskwren")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0+unknown"

PRODUCT_NAME = "RiskWren"
TAGLINE = "Risk and compliance people actually keep current."
