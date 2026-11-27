"""Find and tidy: saved views, pairs said not to be duplicates, and what was handed on when
someone left (INV-10, INV-12, OVS-08).

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "not_duplicate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("record_type", sa.String(length=24), nullable=False),
        sa.Column("low_id", sa.Integer(), nullable=False),
        sa.Column("high_id", sa.Integer(), nullable=False),
        sa.Column("said_by_name", sa.String(length=200), nullable=False),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_not_duplicate")),
        sa.UniqueConstraint(
            "record_type",
            "low_id",
            "high_id",
            name=op.f("uq_not_duplicate_record_type_low_id_high_id"),
        ),
    )
    op.create_table(
        "handover",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("from_account_id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("held_by", sa.Integer(), nullable=False),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["from_account_id"], ["account.id"], name=op.f("fk_handover_from_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["held_by"], ["account.id"], name=op.f("fk_handover_held_by_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_handover")),
        sa.UniqueConstraint(
            "from_account_id",
            "subject_type",
            "subject_id",
            "kind",
            name=op.f("uq_handover_from_account_id_subject_type_subject_id_kind"),
        ),
    )
    with op.batch_alter_table("handover", schema=None) as batch_op:
        batch_op.create_index("ix_handover_held_by", ["held_by"], unique=False)

    op.create_table(
        "saved_view",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("owner_name", sa.String(length=200), nullable=False),
        sa.Column("path", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("query", sa.String(length=1000), nullable=False),
        sa.Column("shared", sa.Boolean(), nullable=False),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_saved_view_account_id_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_saved_view")),
        sa.UniqueConstraint(
            "account_id", "path", "name", name=op.f("uq_saved_view_account_id_path_name")
        ),
    )
    with op.batch_alter_table("saved_view", schema=None) as batch_op:
        batch_op.create_index("ix_saved_view_path", ["path"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("saved_view", schema=None) as batch_op:
        batch_op.drop_index("ix_saved_view_path")

    op.drop_table("saved_view")
    with op.batch_alter_table("handover", schema=None) as batch_op:
        batch_op.drop_index("ix_handover_held_by")

    op.drop_table("handover")
    op.drop_table("not_duplicate")
