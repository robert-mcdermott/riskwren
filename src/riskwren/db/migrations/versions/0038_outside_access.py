"""Internal audit: read-only access for outside auditors, through a link (AUD-08).

Revision ID: 0038
Revises: 0037
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outside_access",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("organization", sa.String(length=200), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("granted_by", sa.Integer(), nullable=True),
        sa.Column("granted_by_name", sa.String(length=200), nullable=False),
        sa.Column("granted_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("expires_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("views", sa.Integer(), nullable=False),
        sa.Column("last_viewed_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "subject_type IN ('engagement', 'scope')", name=op.f("ck_outside_access_subject_type")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outside_access")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_outside_access_token_hash")),
    )
    with op.batch_alter_table("outside_access", schema=None) as batch_op:
        batch_op.create_index(
            "ix_outside_access_subject", ["subject_type", "subject_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("outside_access", schema=None) as batch_op:
        batch_op.drop_index("ix_outside_access_subject")

    op.drop_table("outside_access")
