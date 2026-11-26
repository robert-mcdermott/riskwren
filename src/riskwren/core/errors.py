"""One exception hierarchy. The API maps it to problem documents, the command line to messages."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


class RiskWrenError(Exception):
    """Anything RiskWren can explain to the person who caused it."""


class ConfigError(RiskWrenError):
    """The configuration file is wrong. ``problems`` lists every fault found, in one pass."""

    def __init__(self, message: str, problems: Sequence[str] = ()) -> None:
        self.problems = list(problems)
        super().__init__("\n".join([message, *(f"  - {p}" for p in self.problems)]))


class DataHomeError(RiskWrenError):
    """The data home is missing, unwritable, or was never initialized."""


class StoreError(RiskWrenError):
    """The database cannot be used: unreachable, unsupported, or behind on migrations."""


class AuditError(RiskWrenError):
    """A write was attempted in a way that would leave no event behind."""


class NotFound(RiskWrenError):
    """The thing asked for does not exist, or the asker may not know that it does."""


class PermissionDenied(RiskWrenError):
    """The acting person may not do this."""


class Conflict(RiskWrenError):
    """The request is valid but cannot be applied to the record as it now stands."""


class Invalid(RiskWrenError):
    """The input is wrong. ``errors`` maps field names to what is wrong with each."""

    def __init__(self, message: str, errors: Mapping[str, str] | None = None) -> None:
        self.errors = dict(errors or {})
        super().__init__(message)
