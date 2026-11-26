"""The inventory: the things risk attaches to, with their owners and the links between them."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from riskwren.db.base import Base
from riskwren.db.types import JsonType, UtcDateTime

RECORD_STATUSES = ("active", "retired")


def one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class RecordMixin:
    """What every record a person can cite has: a reference, a unit, and a version."""

    __audit_skip__ = frozenset({"version", "updated_at"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref: Mapped[str] = mapped_column(String(24), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JsonType, default=list)
    # A restricted record is known only to its owners, its unit's stewards and leaders,
    # managers, and auditors.
    restricted: Mapped[bool] = mapped_column(Boolean, default=False)
    # Rises with every edit. An edit made against an older version is refused.
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime)

    @declared_attr
    def org_unit_id(cls) -> Mapped[int]:
        return mapped_column(ForeignKey("org_unit.id"))


class ThingMixin(RecordMixin):
    """What processes, systems, and third parties share: how much the organization depends
    on them, and the highest class of data they handle."""

    status: Mapped[str] = mapped_column(String(24), default="active")
    criticality: Mapped[str] = mapped_column(String(40))
    data_class: Mapped[str | None] = mapped_column(String(40))


class Process(ThingMixin, Base):
    """Something the organization does and depends on."""

    __tablename__ = "process"
    __subject__ = "process"

    kind: Mapped[str] = mapped_column(String(40))
    purpose: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),
        Index("ix_process_org_unit_id", "org_unit_id"),
    )


class System(ThingMixin, Base):
    """An application, platform, instrument, device, or piece of infrastructure."""

    __tablename__ = "system"
    __subject__ = "system"

    kind: Mapped[str] = mapped_column(String(40))
    hosting: Mapped[str | None] = mapped_column(String(40))
    lifecycle: Mapped[str] = mapped_column(String(40), default="in_service")
    url: Mapped[str | None] = mapped_column(String(300))

    __table_args__ = (
        CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),
        Index("ix_system_org_unit_id", "org_unit_id"),
    )


class ThirdParty(ThingMixin, Base):
    """An outside organization the organization depends on or shares with."""

    __tablename__ = "third_party"
    __subject__ = "third_party"

    kind: Mapped[str] = mapped_column(String(40))
    website: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),
        Index("ix_third_party_org_unit_id", "org_unit_id"),
    )


class RecordOwner(Base):
    """A person named on a record, and in what capacity."""

    __tablename__ = "record_owner"
    __audit_parent__ = ("@record_type", "record_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_type: Mapped[str] = mapped_column(String(24))
    record_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    kind: Mapped[str] = mapped_column(String(24))

    __table_args__ = (
        UniqueConstraint("record_type", "record_id", "account_id", "kind"),
        Index("ix_record_owner_account_id", "account_id"),
        Index("ix_record_owner_record", "record_type", "record_id"),
    )


class RecordLink(Base):
    """A named relationship between two records: what relies on what."""

    __tablename__ = "record_link"
    __audit_parent__ = ("@from_type", "from_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_type: Mapped[str] = mapped_column(String(24))
    from_id: Mapped[int] = mapped_column(Integer)
    relation: Mapped[str] = mapped_column(String(24))
    to_type: Mapped[str] = mapped_column(String(24))
    to_id: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(300))

    __table_args__ = (
        UniqueConstraint("from_type", "from_id", "relation", "to_type", "to_id"),
        Index("ix_record_link_to", "to_type", "to_id"),
    )
