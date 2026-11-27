"""Measures: the daily snapshot of each defined measure, for its trend (RPT-06).

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "measure_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("measure", sa.String(length=40), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("taken_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_measure_snapshot")),
        sa.UniqueConstraint("day", "measure", name=op.f("uq_measure_snapshot_day_measure")),
    )
    with op.batch_alter_table("measure_snapshot", schema=None) as batch_op:
        batch_op.create_index("ix_measure_snapshot_measure", ["measure", "day"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("measure_snapshot", schema=None) as batch_op:
        batch_op.drop_index("ix_measure_snapshot_measure")

    op.drop_table("measure_snapshot")
