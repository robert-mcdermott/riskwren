"""The hash chain over events, and its verification.

Each event's hash covers its own content and the hash of the event before it. Changing,
removing, or inserting an event anywhere breaks every hash after it.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import PurePath
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from riskwren.core.clock import isoformat
from riskwren.db.models.system import ChainHead, Event

GENESIS = "0" * 64
_FIELDS = (
    "actor_kind",
    "actor_id",
    "actor_label",
    "action",
    "subject_type",
    "subject_id",
    "subject_ref",
    "parent_type",
    "parent_id",
    "changes",
    "context",
)


def jsonable(value: Any) -> Any:
    """A value reduced to what JSON holds identically on both databases."""
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return str(value)
        # PostgreSQL's jsonb rewrites 1e20 as an integer; store whole numbers that way.
        return int(value) if value.is_integer() else value
    if isinstance(value, datetime):
        return isoformat(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return jsonable(value.value)
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, set | frozenset):
        return sorted((jsonable(v) for v in value), key=repr)
    if isinstance(value, Sequence):
        return [jsonable(v) for v in value]
    return str(value)


def canonical(seq: int, at: datetime, row: Mapping[str, Any]) -> str:
    """The exact text an event's hash is taken over."""
    body = {"seq": seq, "at": isoformat(at), **{name: row[name] for name in _FIELDS}}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def link(prev_hash: str, body: str) -> str:
    return hashlib.sha256(f"{prev_hash}\n{body}".encode()).hexdigest()


def append(conn: Connection, at: datetime, rows: Sequence[Mapping[str, Any]]) -> None:
    """Add events to the end of the chain, inside the caller's transaction.

    The head row is locked first, so two transactions appending at once take turns and the
    chain stays a single line.
    """
    if not rows:
        return
    head = conn.execute(select(ChainHead.seq, ChainHead.hash).with_for_update()).one()
    seq, prev = head.seq, head.hash
    records = []
    for row in rows:
        seq += 1
        digest = link(prev, canonical(seq, at, row))
        records.append({"id": seq, "at": at, **row, "prev_hash": prev, "hash": digest})
        prev = digest
    conn.execute(insert(Event), records)
    conn.execute(update(ChainHead).values(seq=seq, hash=prev))


@dataclass(frozen=True)
class ChainReport:
    ok: bool
    events: int
    head: str
    broken_at: int | None = None
    reason: str = ""


def verify(conn: Connection, *, batch: int = 2000) -> ChainReport:
    """Recompute the whole chain and report the first place it does not hold."""
    expected_seq = 0
    prev = GENESIS
    last_id = 0
    columns = [
        Event.id,
        Event.at,
        Event.prev_hash,
        Event.hash,
        *(getattr(Event, f) for f in _FIELDS),
    ]
    while True:
        rows = conn.execute(
            select(*columns).where(Event.id > last_id).order_by(Event.id).limit(batch)
        ).all()
        if not rows:
            break
        for row in rows:
            expected_seq += 1
            data = row._asdict()
            if row.id != expected_seq:
                return ChainReport(
                    False, expected_seq - 1, prev, expected_seq,
                    f"event {expected_seq} is missing (found {row.id} in its place)",
                )  # fmt: skip
            if row.prev_hash != prev:
                return ChainReport(
                    False, expected_seq - 1, prev, row.id,
                    f"event {row.id} does not follow the event before it",
                )  # fmt: skip
            if link(prev, canonical(row.id, row.at, data)) != row.hash:
                return ChainReport(
                    False, expected_seq - 1, prev, row.id,
                    f"event {row.id} has been altered",
                )  # fmt: skip
            prev = row.hash
        last_id = rows[-1].id
    head = conn.execute(select(ChainHead.seq, ChainHead.hash)).one()
    if head.seq != expected_seq or head.hash != prev:
        return ChainReport(
            False, expected_seq, prev, expected_seq + 1,
            f"the history ends at event {expected_seq}, but {head.seq} were recorded: "
            "events have been removed from the end",
        )  # fmt: skip
    return ChainReport(True, expected_seq, prev)
