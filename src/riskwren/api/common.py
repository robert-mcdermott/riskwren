"""Conventions shared by every route: response envelopes, sessions, and paging."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from riskwren.core.errors import Invalid
from riskwren.db.engine import Database
from riskwren.events.actor import Actor

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def envelope(data: Any, **meta: Any) -> dict[str, Any]:
    """Every successful answer: ``{"data": …, "meta": …}``."""
    return {"data": data, "meta": meta}


def database(request: Request) -> Database:
    return request.app.state.db


@contextmanager
def reading(request: Request) -> Iterator[Session]:
    """A session for a request that only looks things up."""
    with database(request).read() as session:
        yield session


@contextmanager
def writing(request: Request, actor: Actor) -> Iterator[Session]:
    """A session for a request that changes things. It commits when the block ends, before
    the answer is sent, and every change in it is recorded against ``actor``."""
    with database(request).write(actor) as session:
        yield session


def clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    return max(1, min(limit, MAX_LIMIT))


def encode_cursor(position: dict[str, Any]) -> str:
    raw = json.dumps(position, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except (ValueError, UnicodeDecodeError) as exc:
        raise Invalid("The cursor is not valid.", {"cursor": "not a cursor from this API"}) from exc
    if not isinstance(value, dict):
        raise Invalid("The cursor is not valid.", {"cursor": "not a cursor from this API"})
    return value
