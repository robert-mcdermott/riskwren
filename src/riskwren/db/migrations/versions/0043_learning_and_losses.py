"""Incidents: the risks they realized and the controls that failed or held, what was
learned, and what they cost (INC-06).

Revision ID: 0043
Revises: 0042
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0043"
down_revision: str | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incident_loss",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.Integer(), nullable=True),
        sa.Column("recorded_by_name", sa.String(length=200), nullable=False),
        sa.Column("recorded_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('response', 'recovery', 'lost_revenue', 'notification', 'legal', "
            "'fines', 'other')",
            name=op.f("ck_incident_loss_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incident.id"],
            name=op.f("fk_incident_loss_incident_id_incident"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by"], ["account.id"], name=op.f("fk_incident_loss_recorded_by_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_loss")),
    )
    with op.batch_alter_table("incident_loss", schema=None) as batch_op:
        batch_op.create_index("ix_incident_loss_incident_id", ["incident_id"], unique=False)

    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.add_column(sa.Column("lessons", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("root_cause", sa.String(length=40), nullable=True))

    with op.batch_alter_table("incident_subject", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("role", sa.String(length=16), server_default="concerns", nullable=False)
        )
        batch_op.drop_constraint(batch_op.f("uq_incident_subject"), type_="unique")
        batch_op.create_unique_constraint(
            "uq_incident_subject", ["incident_id", "subject_type", "subject_id", "role"]
        )
        batch_op.create_check_constraint(
            batch_op.f("ck_incident_subject_role"),
            "role IN ('concerns', 'realized', 'failed', 'held')",
        )


def downgrade() -> None:
    with op.batch_alter_table("incident_subject", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_incident_subject_role"), type_="check")
        batch_op.drop_constraint("uq_incident_subject", type_="unique")
        batch_op.create_unique_constraint(
            batch_op.f("uq_incident_subject"), ["incident_id", "subject_type", "subject_id"]
        )
        batch_op.drop_column("role")

    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.drop_column("root_cause")
        batch_op.drop_column("lessons")

    with op.batch_alter_table("incident_loss", schema=None) as batch_op:
        batch_op.drop_index("ix_incident_loss_incident_id")

    op.drop_table("incident_loss")
