"""Internal audit: requests to the audited, answered with evidence (AUD-05).

Revision ID: 0037
Revises: 0036
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_request",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("engagement_id", sa.Integer(), nullable=False),
        sa.Column("what", sa.Text(), nullable=False),
        sa.Column("assignee_id", sa.Integer(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("evidence", riskwren.db.types.JsonType, nullable=False),
        sa.Column("answered_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("returned_reason", sa.Text(), nullable=True),
        sa.Column("accepted_by_name", sa.String(length=200), nullable=True),
        sa.Column("accepted_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("asked_by", sa.Integer(), nullable=True),
        sa.Column("asked_by_name", sa.String(length=200), nullable=False),
        sa.Column("asked_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('open', 'answered', 'accepted')", name=op.f("ck_audit_request_status")
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"], ["account.id"], name=op.f("fk_audit_request_assignee_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["engagement_id"],
            ["engagement.id"],
            name=op.f("fk_audit_request_engagement_id_engagement"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_request")),
    )
    with op.batch_alter_table("audit_request", schema=None) as batch_op:
        batch_op.create_index(
            "ix_audit_request_assignee_id", ["assignee_id", "status"], unique=False
        )
        batch_op.create_index("ix_audit_request_engagement_id", ["engagement_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("audit_request", schema=None) as batch_op:
        batch_op.drop_index("ix_audit_request_engagement_id")
        batch_op.drop_index("ix_audit_request_assignee_id")

    op.drop_table("audit_request")
