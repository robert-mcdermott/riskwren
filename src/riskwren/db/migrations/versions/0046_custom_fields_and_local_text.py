"""Fields of the organization's own on its records, and the licensed text of a framework that
ships as identifiers, imported by an organization that holds the license (PLT-18).

Revision ID: 0046
Revises: 0045
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0046"
down_revision: str | None = "0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "custom_value",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("record_type", sa.String(length=24), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("field", sa.String(length=40), nullable=False),
        sa.Column("value", riskwren.db.types.JsonType, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_custom_value")),
        sa.UniqueConstraint(
            "record_type",
            "record_id",
            "field",
            name=op.f("uq_custom_value_record_type_record_id_field"),
        ),
    )
    with op.batch_alter_table("custom_value", schema=None) as batch_op:
        batch_op.create_index("ix_custom_value_record", ["record_type", "record_id"], unique=False)

    with op.batch_alter_table("requirement", schema=None) as batch_op:
        batch_op.add_column(sa.Column("local_title", sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column("local_text", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("requirement", schema=None) as batch_op:
        batch_op.drop_column("local_text")
        batch_op.drop_column("local_title")

    with op.batch_alter_table("custom_value", schema=None) as batch_op:
        batch_op.drop_index("ix_custom_value_record")

    op.drop_table("custom_value")
