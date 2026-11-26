"""The kinds of record a person can cite, and what each is made of.

Every record type registers itself here, so that owners, links, history, and visibility are
written once and work for all of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.core.errors import NotFound
from riskwren.db.base import Base
from riskwren.db.models import Process, System, ThirdParty
from riskwren.db.refs import parse_ref


@dataclass(frozen=True)
class Field:
    """One editable fact about a record, beyond what every record has."""

    name: str
    label: str
    kind: str = "text"  # text | long | choice | url
    vocab: str | None = None
    required: bool = False
    default: Any = None
    max_length: int = 200


@dataclass(frozen=True)
class RecordType:
    key: str  # the name used in events, owners, and links
    model: type[Base]
    prefix: str
    path: str  # its place in the API and the web app
    label: str
    plural: str
    fields: tuple[Field, ...] = ()
    # Whether it carries a criticality, a data class, and an active or retired status.
    is_thing: bool = True
    # Whether everyone signed in may see it unless it is restricted. The inventory is open,
    # because a record can only be linked to what its author can see; the register of risks
    # and controls follows the organization's visibility setting.
    open: bool = False
    sorts: tuple[str, ...] = ("updated_at", "name", "ref")
    filters: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict, hash=False, compare=False)


TYPES: dict[str, RecordType] = {}
BY_PREFIX: dict[str, RecordType] = {}
BY_PATH: dict[str, RecordType] = {}


def register(record_type: RecordType) -> RecordType:
    TYPES[record_type.key] = record_type
    BY_PREFIX[record_type.prefix] = record_type
    BY_PATH[record_type.path] = record_type
    return record_type


THING_SORTS = ("updated_at", "name", "ref", "criticality", "status", "kind")
THING_FILTERS = ("status", "kind", "criticality", "data_class")

PROCESS = register(
    RecordType(
        "process",
        Process,
        "PRC",
        "processes",
        "process",
        "processes",
        fields=(
            Field("kind", "Kind", "choice", vocab="process_kinds", required=True),
            Field("purpose", "Purpose", "long"),
        ),
        open=True,
        sorts=THING_SORTS,
        filters=THING_FILTERS,
    )
)
SYSTEM = register(
    RecordType(
        "system",
        System,
        "SYS",
        "systems",
        "system",
        "systems",
        fields=(
            Field("kind", "Kind", "choice", vocab="system_kinds", required=True),
            Field("hosting", "Hosting", "choice", vocab="hosting"),
            Field(
                "lifecycle",
                "Lifecycle",
                "choice",
                vocab="lifecycles",
                required=True,
                default="in_service",
            ),
            Field("url", "Address", "url", max_length=300),
        ),
        open=True,
        sorts=(*THING_SORTS, "lifecycle"),
        filters=(*THING_FILTERS, "hosting", "lifecycle"),
    )
)
THIRD_PARTY = register(
    RecordType(
        "third_party",
        ThirdParty,
        "TP",
        "third-parties",
        "third party",
        "third parties",
        fields=(
            Field("kind", "Kind", "choice", vocab="third_party_kinds", required=True),
            Field("website", "Website", "url", max_length=300),
            Field("notes", "Notes", "long"),
        ),
        open=True,
        sorts=THING_SORTS,
        filters=THING_FILTERS,
    )
)


def find(session: Session, record_type: RecordType, ref: str) -> Any:
    """The record with this reference. What the asker may see of it is the caller's to check."""
    parsed = parse_ref(ref)
    if parsed is None or parsed[0] != record_type.prefix:
        raise NotFound(f"There is no {record_type.label} {ref}.")
    model: Any = record_type.model
    record = session.scalars(select(model).where(model.ref == ref.strip().upper())).first()
    if record is None:
        raise NotFound(f"There is no {record_type.label} {ref}.")
    return record


def find_any(session: Session, ref: str) -> tuple[RecordType, Any]:
    """The record with this reference, whatever kind it is."""
    parsed = parse_ref(ref)
    record_type = BY_PREFIX.get(parsed[0]) if parsed else None
    if record_type is None:
        raise NotFound(f"There is no record {ref}.")
    return record_type, find(session, record_type, ref)
