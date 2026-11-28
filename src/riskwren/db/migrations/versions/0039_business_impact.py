"""Resilience: business impact analyses and recovery capabilities (RES-01, RES-02).

Revision ID: 0039
Revises: 0038
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recovery_capability",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("recovery_hours", sa.Integer(), nullable=False),
        sa.Column("data_loss_hours", sa.Integer(), nullable=False),
        sa.Column("basis", sa.Text(), nullable=False),
        sa.Column("recorded_by", sa.Integer(), nullable=True),
        sa.Column("recorded_by_name", sa.String(length=200), nullable=False),
        sa.Column("recorded_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("superseded_by", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "subject_type IN ('system', 'service')",
            name=op.f("ck_recovery_capability_subject_type"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recovery_capability")),
    )
    with op.batch_alter_table("recovery_capability", schema=None) as batch_op:
        batch_op.create_index(
            "ix_recovery_capability_subject", ["subject_type", "subject_id"], unique=False
        )

    op.create_table(
        "impact_analysis",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("process_id", sa.Integer(), nullable=False),
        sa.Column("impacts", riskwren.db.types.JsonType, nullable=False),
        sa.Column("recovery_hours", sa.Integer(), nullable=False),
        sa.Column("data_loss_hours", sa.Integer(), nullable=False),
        sa.Column("minimum", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("analysed_by", sa.Integer(), nullable=True),
        sa.Column("analysed_by_name", sa.String(length=200), nullable=False),
        sa.Column("analysed_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("superseded_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["process_id"], ["process.id"], name=op.f("fk_impact_analysis_process_id_process")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_impact_analysis")),
    )
    with op.batch_alter_table("impact_analysis", schema=None) as batch_op:
        batch_op.create_index("ix_impact_analysis_process_id", ["process_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("impact_analysis", schema=None) as batch_op:
        batch_op.drop_index("ix_impact_analysis_process_id")

    op.drop_table("impact_analysis")
    with op.batch_alter_table("recovery_capability", schema=None) as batch_op:
        batch_op.drop_index("ix_recovery_capability_subject")

    op.drop_table("recovery_capability")
