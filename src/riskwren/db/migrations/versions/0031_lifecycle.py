"""Lifecycle: when a third party is next due for review, actions a third party's contact does,
and offboarding (TPR-07, TPR-08, TPR-09).

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "offboarding",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("third_party_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("steps", riskwren.db.types.JsonType, nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_by_name", sa.String(length=200), nullable=False),
        sa.Column("started_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("finished_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('open', 'done', 'cancelled')", name=op.f("ck_offboarding_status")
        ),
        sa.ForeignKeyConstraint(
            ["third_party_id"],
            ["third_party.id"],
            name=op.f("fk_offboarding_third_party_id_third_party"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_offboarding")),
    )
    with op.batch_alter_table("offboarding", schema=None) as batch_op:
        batch_op.create_index("ix_offboarding_third_party_id", ["third_party_id"], unique=False)

    with op.batch_alter_table("action", schema=None) as batch_op:
        batch_op.add_column(sa.Column("contact_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_action_contact_id_third_party_contact"),
            "third_party_contact",
            ["contact_id"],
            ["id"],
        )

    with op.batch_alter_table("third_party", schema=None) as batch_op:
        batch_op.add_column(sa.Column("next_review_on", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("review_called", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("third_party", schema=None) as batch_op:
        batch_op.drop_column("review_called")
        batch_op.drop_column("next_review_on")

    with op.batch_alter_table("action", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_action_contact_id_third_party_contact"), type_="foreignkey"
        )
        batch_op.drop_column("contact_id")

    with op.batch_alter_table("offboarding", schema=None) as batch_op:
        batch_op.drop_index("ix_offboarding_third_party_id")

    op.drop_table("offboarding")
