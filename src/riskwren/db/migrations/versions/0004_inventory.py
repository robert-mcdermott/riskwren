"""Inventory: processes, systems, third parties, owners, and links (INV-01 to INV-06).

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PREFIXES = ("PRC", "SYS", "TP")


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": prefix, "value": 0} for prefix in PREFIXES])
    op.create_table(
        "record_link",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("from_type", sa.String(length=24), nullable=False),
        sa.Column("from_id", sa.Integer(), nullable=False),
        sa.Column("relation", sa.String(length=24), nullable=False),
        sa.Column("to_type", sa.String(length=24), nullable=False),
        sa.Column("to_id", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_record_link")),
        sa.UniqueConstraint(
            "from_type",
            "from_id",
            "relation",
            "to_type",
            "to_id",
            name=op.f("uq_record_link_from_type_from_id_relation_to_type_to_id"),
        ),
    )
    with op.batch_alter_table("record_link", schema=None) as batch_op:
        batch_op.create_index("ix_record_link_to", ["to_type", "to_id"], unique=False)

    op.create_table(
        "process",
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("criticality", sa.String(length=40), nullable=False),
        sa.Column("data_class", sa.String(length=40), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "tags",
            riskwren.db.types.JsonType,
            nullable=False,
        ),
        sa.Column("restricted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("org_unit_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_process_status")),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_process_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_process")),
        sa.UniqueConstraint("ref", name=op.f("uq_process_ref")),
    )
    with op.batch_alter_table("process", schema=None) as batch_op:
        batch_op.create_index("ix_process_org_unit_id", ["org_unit_id"], unique=False)

    op.create_table(
        "record_owner",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("record_type", sa.String(length=24), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_record_owner_account_id_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_record_owner")),
        sa.UniqueConstraint(
            "record_type",
            "record_id",
            "account_id",
            "kind",
            name=op.f("uq_record_owner_record_type_record_id_account_id_kind"),
        ),
    )
    with op.batch_alter_table("record_owner", schema=None) as batch_op:
        batch_op.create_index("ix_record_owner_account_id", ["account_id"], unique=False)
        batch_op.create_index("ix_record_owner_record", ["record_type", "record_id"], unique=False)

    op.create_table(
        "system",
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("hosting", sa.String(length=40), nullable=True),
        sa.Column("lifecycle", sa.String(length=40), nullable=False),
        sa.Column("url", sa.String(length=300), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("criticality", sa.String(length=40), nullable=False),
        sa.Column("data_class", sa.String(length=40), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "tags",
            riskwren.db.types.JsonType,
            nullable=False,
        ),
        sa.Column("restricted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("org_unit_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_system_status")),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_system_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_system")),
        sa.UniqueConstraint("ref", name=op.f("uq_system_ref")),
    )
    with op.batch_alter_table("system", schema=None) as batch_op:
        batch_op.create_index("ix_system_org_unit_id", ["org_unit_id"], unique=False)

    op.create_table(
        "third_party",
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("website", sa.String(length=300), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("criticality", sa.String(length=40), nullable=False),
        sa.Column("data_class", sa.String(length=40), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "tags",
            riskwren.db.types.JsonType,
            nullable=False,
        ),
        sa.Column("restricted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("org_unit_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_third_party_status")),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_third_party_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_third_party")),
        sa.UniqueConstraint("ref", name=op.f("uq_third_party_ref")),
    )
    with op.batch_alter_table("third_party", schema=None) as batch_op:
        batch_op.create_index("ix_third_party_org_unit_id", ["org_unit_id"], unique=False)


def downgrade() -> None:
    op.execute("DELETE FROM counter WHERE prefix IN ('PRC', 'SYS', 'TP')")
    with op.batch_alter_table("third_party", schema=None) as batch_op:
        batch_op.drop_index("ix_third_party_org_unit_id")

    op.drop_table("third_party")
    with op.batch_alter_table("system", schema=None) as batch_op:
        batch_op.drop_index("ix_system_org_unit_id")

    op.drop_table("system")
    with op.batch_alter_table("record_owner", schema=None) as batch_op:
        batch_op.drop_index("ix_record_owner_record")
        batch_op.drop_index("ix_record_owner_account_id")

    op.drop_table("record_owner")
    with op.batch_alter_table("process", schema=None) as batch_op:
        batch_op.drop_index("ix_process_org_unit_id")

    op.drop_table("process")
    with op.batch_alter_table("record_link", schema=None) as batch_op:
        batch_op.drop_index("ix_record_link_to")

    op.drop_table("record_link")
