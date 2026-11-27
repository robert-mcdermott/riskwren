"""Scenarios, and estimates of a risk in ranges (RSK-18, RSK-19).

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": "SCN", "value": 0}])
    op.create_table(
        "scenario",
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("assumptions", sa.Text(), nullable=True),
        sa.Column("conclusion", sa.Text(), nullable=True),
        sa.Column("concluded_on", sa.Date(), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('draft', 'concluded', 'retired')", name=op.f("ck_scenario_status")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_scenario_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenario")),
        sa.UniqueConstraint("ref", name=op.f("uq_scenario_ref")),
    )
    with op.batch_alter_table("scenario", schema=None) as batch_op:
        batch_op.create_index("ix_scenario_org_unit_id", ["org_unit_id"], unique=False)

    op.create_table(
        "risk_estimate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("risk_id", sa.Integer(), nullable=False),
        sa.Column("frequency_low", sa.Float(), nullable=False),
        sa.Column("frequency_likely", sa.Float(), nullable=False),
        sa.Column("frequency_high", sa.Float(), nullable=False),
        sa.Column("loss_low", sa.Integer(), nullable=False),
        sa.Column("loss_likely", sa.Integer(), nullable=False),
        sa.Column("loss_high", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("assumptions", sa.Text(), nullable=False),
        sa.Column("estimated_by", sa.Integer(), nullable=True),
        sa.Column("estimated_by_name", sa.String(length=200), nullable=False),
        sa.Column("estimated_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("superseded_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["risk_id"], ["risk.id"], name=op.f("fk_risk_estimate_risk_id_risk")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_estimate")),
    )
    with op.batch_alter_table("risk_estimate", schema=None) as batch_op:
        batch_op.create_index("ix_risk_estimate_risk_id", ["risk_id"], unique=False)

    op.create_table(
        "scenario_subject",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scenario_id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "subject_type IN ('risk', 'process')", name=op.f("ck_scenario_subject_subject_type")
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"], ["scenario.id"], name=op.f("fk_scenario_subject_scenario_id_scenario")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenario_subject")),
    )
    with op.batch_alter_table("scenario_subject", schema=None) as batch_op:
        batch_op.create_index("ix_scenario_subject_scenario_id", ["scenario_id"], unique=False)
        batch_op.create_index(
            "ix_scenario_subject_subject", ["subject_type", "subject_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("scenario_subject", schema=None) as batch_op:
        batch_op.drop_index("ix_scenario_subject_subject")
        batch_op.drop_index("ix_scenario_subject_scenario_id")

    op.drop_table("scenario_subject")
    with op.batch_alter_table("risk_estimate", schema=None) as batch_op:
        batch_op.drop_index("ix_risk_estimate_risk_id")

    op.drop_table("risk_estimate")
    with op.batch_alter_table("scenario", schema=None) as batch_op:
        batch_op.drop_index("ix_scenario_org_unit_id")

    op.drop_table("scenario")
    op.execute("DELETE FROM counter WHERE prefix = 'SCN'")
