"""Indicators: a measure with thresholds, its readings over time, and the risks it warns of
(RSK-13).

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": "IND", "value": 0}])
    op.create_table(
        "indicator",
        sa.Column("measure", sa.String(length=40), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("warn_at", sa.Float(), nullable=True),
        sa.Column("breach_at", sa.Float(), nullable=False),
        sa.Column("frequency", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("last_value", sa.Float(), nullable=True),
        sa.Column("last_read_on", sa.Date(), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
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
        sa.CheckConstraint("direction IN ('up', 'down')", name=op.f("ck_indicator_direction")),
        sa.CheckConstraint(
            "frequency IN ('weekly', 'monthly', 'quarterly', 'annually')",
            name=op.f("ck_indicator_frequency"),
        ),
        sa.CheckConstraint(
            "state IN ('no_reading', 'ok', 'warn', 'breach')", name=op.f("ck_indicator_state")
        ),
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_indicator_status")),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_indicator_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_indicator")),
        sa.UniqueConstraint("ref", name=op.f("uq_indicator_ref")),
    )
    op.create_table(
        "indicator_reading",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("indicator_id", sa.Integer(), nullable=False),
        sa.Column("read_on", sa.Date(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("entered_by", sa.Integer(), nullable=True),
        sa.Column("entered_by_name", sa.String(length=200), nullable=False),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["indicator_id"],
            ["indicator.id"],
            name=op.f("fk_indicator_reading_indicator_id_indicator"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_indicator_reading")),
        sa.UniqueConstraint(
            "indicator_id", "read_on", name=op.f("uq_indicator_reading_indicator_id_read_on")
        ),
    )
    op.create_table(
        "indicator_risk",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("indicator_id", sa.Integer(), nullable=False),
        sa.Column("risk_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["indicator_id"],
            ["indicator.id"],
            name=op.f("fk_indicator_risk_indicator_id_indicator"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["risk_id"], ["risk.id"], name=op.f("fk_indicator_risk_risk_id_risk")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_indicator_risk")),
        sa.UniqueConstraint(
            "indicator_id", "risk_id", name=op.f("uq_indicator_risk_indicator_id_risk_id")
        ),
    )
    with op.batch_alter_table("indicator_risk", schema=None) as batch_op:
        batch_op.create_index("ix_indicator_risk_risk_id", ["risk_id"], unique=False)


def downgrade() -> None:
    op.execute("DELETE FROM counter WHERE prefix = 'IND'")
    with op.batch_alter_table("indicator_risk", schema=None) as batch_op:
        batch_op.drop_index("ix_indicator_risk_risk_id")

    op.drop_table("indicator_risk")
    op.drop_table("indicator_reading")
    op.drop_table("indicator")
