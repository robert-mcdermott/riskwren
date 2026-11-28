"""Drafts that an assistant or another system proposes: a risk, an issue, or a control,
made only when a person opens one in the ordinary form and saves it (INT-06).

Revision ID: 0049
Revises: 0048
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0049"
down_revision: str | None = "0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "draft",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("values", riskwren.db.types.JsonType, nullable=False),
        sa.Column("why", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("org_unit_id", sa.Integer(), nullable=True),
        sa.Column("made_by", sa.Integer(), nullable=True),
        sa.Column("made_by_name", sa.String(length=200), nullable=False),
        sa.Column("made_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_by_name", sa.String(length=200), nullable=True),
        sa.Column("decided_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("record_ref", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["account.id"], name=op.f("fk_draft_decided_by_account")
        ),
        sa.ForeignKeyConstraint(["made_by"], ["account.id"], name=op.f("fk_draft_made_by_account")),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_draft_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_draft")),
    )
    with op.batch_alter_table("draft", schema=None) as batch_op:
        batch_op.create_index("ix_draft_status", ["status", "made_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("draft", schema=None) as batch_op:
        batch_op.drop_index("ix_draft_status")

    op.drop_table("draft")
