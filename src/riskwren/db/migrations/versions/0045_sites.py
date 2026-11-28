"""Resilience: sites, as dependencies of their own, and the recovery capability of a site or
a third party (RES-02).

Revision ID: 0045
Revises: 0044
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0045"
down_revision: str | None = "0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": "SIT", "value": 0}])
    op.create_table(
        "site",
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("criticality", sa.String(length=40), nullable=False),
        sa.Column("data_class", sa.String(length=40), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("tags", riskwren.db.types.JsonType, nullable=False),
        sa.Column("restricted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("org_unit_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_site_status")),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_site_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_site")),
        sa.UniqueConstraint("ref", name=op.f("uq_site_ref")),
    )
    with op.batch_alter_table("site", schema=None) as batch_op:
        batch_op.create_index("ix_site_org_unit_id", ["org_unit_id"], unique=False)

    with op.batch_alter_table("recovery_capability", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_recovery_capability_subject_type"), type_="check")
        batch_op.create_check_constraint(
            batch_op.f("ck_recovery_capability_subject_type"),
            "subject_type IN ('system', 'service', 'site', 'third_party')",
        )


def downgrade() -> None:
    with op.batch_alter_table("recovery_capability", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_recovery_capability_subject_type"), type_="check")
        batch_op.create_check_constraint(
            batch_op.f("ck_recovery_capability_subject_type"),
            "subject_type IN ('system', 'service')",
        )

    with op.batch_alter_table("site", schema=None) as batch_op:
        batch_op.drop_index("ix_site_org_unit_id")

    op.drop_table("site")
    op.execute("DELETE FROM counter WHERE prefix = 'SIT'")
