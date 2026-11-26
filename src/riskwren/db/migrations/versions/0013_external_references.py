"""External references: what a record is called in another system (INV-09).

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_ref",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("record_type", sa.String(length=24), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("system", sa.String(length=40), nullable=False),
        sa.Column("value", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_external_ref")),
        sa.UniqueConstraint(
            "record_type",
            "record_id",
            "system",
            "value",
            name=op.f("uq_external_ref_record_type_record_id_system_value"),
        ),
    )
    with op.batch_alter_table("external_ref", schema=None) as batch_op:
        batch_op.create_index("ix_external_ref_record", ["record_type", "record_id"], unique=False)
        batch_op.create_index("ix_external_ref_value", ["value"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("external_ref", schema=None) as batch_op:
        batch_op.drop_index("ix_external_ref_value")
        batch_op.drop_index("ix_external_ref_record")

    op.drop_table("external_ref")
