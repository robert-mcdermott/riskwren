"""Crosswalks: controls mapped to the requirements they help to satisfy, and the starter
controls' suggested mappings (CMP-04).

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "control_requirement",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("control_id", sa.Integer(), nullable=False),
        sa.Column("requirement_id", sa.Integer(), nullable=False),
        sa.Column("coverage", sa.String(length=16), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "coverage IN ('full', 'partial')", name=op.f("ck_control_requirement_coverage")
        ),
        sa.CheckConstraint(
            "source IN ('pack', 'person')", name=op.f("ck_control_requirement_source")
        ),
        sa.ForeignKeyConstraint(
            ["control_id"],
            ["control.id"],
            name=op.f("fk_control_requirement_control_id_control"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["account.id"], name=op.f("fk_control_requirement_created_by_account")
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            ["requirement.id"],
            name=op.f("fk_control_requirement_requirement_id_requirement"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_control_requirement")),
        sa.UniqueConstraint("control_id", "requirement_id", name="uq_control_requirement"),
    )
    with op.batch_alter_table("control_requirement", schema=None) as batch_op:
        batch_op.create_index(
            "ix_control_requirement_requirement_id", ["requirement_id"], unique=False
        )

    # The library already has rows, so the new column starts with a default and then lets
    # it go: the library's loader fills it in.
    with op.batch_alter_table("control_library", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "requirements",
                riskwren.db.types.JsonType,
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
    with op.batch_alter_table("control_library", schema=None) as batch_op:
        batch_op.alter_column("requirements", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("control_library", schema=None) as batch_op:
        batch_op.drop_column("requirements")

    with op.batch_alter_table("control_requirement", schema=None) as batch_op:
        batch_op.drop_index("ix_control_requirement_requirement_id")

    op.drop_table("control_requirement")
