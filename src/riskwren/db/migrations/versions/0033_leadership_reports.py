"""Leadership reports: each as it was issued, frozen, with its fingerprint (RPT-08).

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": "LDR", "value": 0}])
    op.create_table(
        "leadership_report",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=24), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("body", riskwren.db.types.JsonType, nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("previous_id", sa.Integer(), nullable=True),
        sa.Column("issued_by", sa.Integer(), nullable=True),
        sa.Column("issued_by_name", sa.String(length=200), nullable=False),
        sa.Column("issued_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leadership_report")),
        sa.UniqueConstraint("ref", name=op.f("uq_leadership_report_ref")),
    )
    with op.batch_alter_table("leadership_report", schema=None) as batch_op:
        batch_op.create_index("ix_leadership_report_issued_at", ["issued_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("leadership_report", schema=None) as batch_op:
        batch_op.drop_index("ix_leadership_report_issued_at")

    op.drop_table("leadership_report")
    op.execute("DELETE FROM counter WHERE prefix = 'LDR'")
