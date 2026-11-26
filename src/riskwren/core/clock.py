"""Time, always in UTC, from a clock that tests and the demo can set."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime


def _system_now() -> datetime:
    return datetime.now(UTC)


_now: Callable[[], datetime] = _system_now


def utc_now() -> datetime:
    """The current time. Everything in RiskWren that needs the time asks here."""
    return _now()


def today() -> date:
    return utc_now().date()


def to_utc(value: datetime) -> datetime:
    """A timezone-aware datetime in UTC. Naive values are taken to be UTC already."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def isoformat(value: datetime) -> str:
    """The one text form of a time used in hashes and exports: UTC, microseconds, ``Z``."""
    return to_utc(value).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@contextmanager
def clock_set_to(source: Callable[[], datetime]) -> Iterator[None]:
    """Run a block with another clock. The demo uses it to build thirty months of history."""
    global _now
    previous, _now = _now, source
    try:
        yield
    finally:
        _now = previous


@contextmanager
def frozen_at(moment: datetime) -> Iterator[None]:
    fixed = to_utc(moment)
    with clock_set_to(lambda: fixed):
        yield
