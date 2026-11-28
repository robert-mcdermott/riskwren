"""Incidents: restricted cases, known only to those named on them (INC-04).

Revision ID: 0041
Revises: 0040
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incident_member",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_incident_member_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incident.id"],
            name=op.f("fk_incident_member_incident_id_incident"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_member")),
        sa.UniqueConstraint("incident_id", "account_id", name="uq_incident_member"),
    )
    with op.batch_alter_table("incident_member", schema=None) as batch_op:
        batch_op.create_index("ix_incident_member_account_id", ["account_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("incident_member", schema=None) as batch_op:
        batch_op.drop_index("ix_incident_member_account_id")

    op.drop_table("incident_member")
