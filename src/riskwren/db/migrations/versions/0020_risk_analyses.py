"""Risk analyses: an exercise over a scope that walks what is in it against a list of threats
(RSK-15).

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": "RAN", "value": 0}])
    op.create_table(
        "risk_analysis",
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=True),
        sa.Column("conclusion", sa.Text(), nullable=True),
        sa.Column("closed_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("closed_by_name", sa.String(length=200), nullable=True),
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
        sa.CheckConstraint("status IN ('open', 'closed')", name=op.f("ck_risk_analysis_status")),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_risk_analysis_org_unit_id_org_unit")
        ),
        sa.ForeignKeyConstraint(
            ["scope_id"], ["scope.id"], name=op.f("fk_risk_analysis_scope_id_scope")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_analysis")),
        sa.UniqueConstraint("ref", name=op.f("uq_risk_analysis_ref")),
    )
    with op.batch_alter_table("risk_analysis", schema=None) as batch_op:
        batch_op.create_index("ix_risk_analysis_org_unit_id", ["org_unit_id"], unique=False)

    op.create_table(
        "risk_analysis_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("subject_ref", sa.String(length=24), nullable=False),
        sa.Column("subject_name", sa.String(length=200), nullable=False),
        sa.Column("threat_key", sa.String(length=80), nullable=False),
        sa.Column("threat_title", sa.String(length=200), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("risk_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("considered_by_name", sa.String(length=200), nullable=True),
        sa.Column("considered_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "outcome IN ('pending', 'not_applicable', 'covered', 'raised')",
            name=op.f("ck_risk_analysis_item_outcome"),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["risk_analysis.id"],
            name=op.f("fk_risk_analysis_item_analysis_id_risk_analysis"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["risk_id"], ["risk.id"], name=op.f("fk_risk_analysis_item_risk_id_risk")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_analysis_item")),
        sa.UniqueConstraint(
            "analysis_id",
            "subject_type",
            "subject_id",
            "threat_key",
            name=op.f("uq_risk_analysis_item_analysis_id_subject_type_subject_id_threat_key"),
        ),
    )
    with op.batch_alter_table("risk_analysis_item", schema=None) as batch_op:
        batch_op.create_index("ix_risk_analysis_item_risk_id", ["risk_id"], unique=False)


def downgrade() -> None:
    op.execute("DELETE FROM counter WHERE prefix = 'RAN'")
    with op.batch_alter_table("risk_analysis_item", schema=None) as batch_op:
        batch_op.drop_index("ix_risk_analysis_item_risk_id")

    op.drop_table("risk_analysis_item")
    with op.batch_alter_table("risk_analysis", schema=None) as batch_op:
        batch_op.drop_index("ix_risk_analysis_org_unit_id")

    op.drop_table("risk_analysis")
