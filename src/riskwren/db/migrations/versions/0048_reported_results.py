"""What other systems report of a control, a check or a piece of evidence, waiting for a
person to confirm it (INT-04); and how a webhook's message is shaped.

Revision ID: 0048
Revises: 0047
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0048"
down_revision: str | None = "0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reported_result",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("control_id", sa.Integer(), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("observed_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("reported_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_by_name", sa.String(length=200), nullable=True),
        sa.Column("decided_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("issue_id", sa.Integer(), nullable=True),
        sa.Column("evidence_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["control_id"],
            ["control.id"],
            name=op.f("fk_reported_result_control_id_control"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["account.id"], name=op.f("fk_reported_result_decided_by_account")
        ),
        sa.ForeignKeyConstraint(
            ["scope_id"], ["scope.id"], name=op.f("fk_reported_result_scope_id_scope")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reported_result")),
    )
    with op.batch_alter_table("reported_result", schema=None) as batch_op:
        batch_op.create_index("ix_reported_result_control", ["control_id", "status"], unique=False)

    with op.batch_alter_table("webhook", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("format", sa.String(length=16), server_default="plain", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("webhook", schema=None) as batch_op:
        batch_op.drop_column("format")

    with op.batch_alter_table("reported_result", schema=None) as batch_op:
        batch_op.drop_index("ix_reported_result_control")

    op.drop_table("reported_result")
