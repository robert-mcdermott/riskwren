"""The assistant's record of each exchange: who asked, what for, which tools it used, what it
answered, and what it cost (INT-07). The table is made whether or not the assistant is on.

Revision ID: 0050
Revises: 0049
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0050"
down_revision: str | None = "0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assistant_exchange",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("asked_by", sa.Integer(), nullable=True),
        sa.Column("token_id", sa.Integer(), nullable=True),
        sa.Column("asked_by_name", sa.String(length=200), nullable=False),
        sa.Column("task", sa.String(length=32), nullable=False),
        sa.Column("ref", sa.String(length=32), nullable=True),
        sa.Column("asked", sa.Text(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("tools_used", riskwren.db.types.JsonType, nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("draft_id", sa.Integer(), nullable=True),
        sa.Column("asked_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("took_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["asked_by"], ["account.id"], name=op.f("fk_assistant_exchange_asked_by_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistant_exchange")),
    )
    with op.batch_alter_table("assistant_exchange", schema=None) as batch_op:
        batch_op.create_index(
            "ix_assistant_exchange_person", ["asked_by", "asked_at"], unique=False
        )
        batch_op.create_index("ix_assistant_exchange_token", ["token_id", "asked_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("assistant_exchange", schema=None) as batch_op:
        batch_op.drop_index("ix_assistant_exchange_token")
        batch_op.drop_index("ix_assistant_exchange_person")

    op.drop_table("assistant_exchange")
