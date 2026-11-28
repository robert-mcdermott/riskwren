"""Tokens that act as a role (INT-02), and webhooks that are told of named events, signed,
with their deliveries and how far through the history they have been queued (INT-03).

Revision ID: 0047
Revises: 0046
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0047"
down_revision: str | None = "0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "webhook",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("events", riskwren.db.types.JsonType, nullable=False),
        sa.Column("secret", sa.String(length=80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by_name", sa.String(length=200), nullable=False),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook")),
    )
    op.create_table(
        "webhook_cursor",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_cursor")),
    )
    op.create_table(
        "api_token",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("org_unit_id", sa.Integer(), nullable=True),
        sa.Column("read_only", sa.Boolean(), nullable=False),
        sa.Column("expires_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_by_name", sa.String(length=200), nullable=False),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_name", sa.String(length=200), nullable=True),
        sa.Column("last_used_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_api_token_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_token")),
        sa.UniqueConstraint("digest", name=op.f("uq_api_token_digest")),
    )
    op.create_table(
        "webhook_delivery",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("webhook_id", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(length=60), nullable=False),
        sa.Column("event_seq", sa.Integer(), nullable=True),
        sa.Column("payload", riskwren.db.types.JsonType, nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("sent_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["webhook_id"],
            ["webhook.id"],
            name=op.f("fk_webhook_delivery_webhook_id_webhook"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_delivery")),
    )
    with op.batch_alter_table("webhook_delivery", schema=None) as batch_op:
        batch_op.create_index(
            "ix_webhook_delivery_due", ["status", "next_attempt_at"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("webhook_delivery", schema=None) as batch_op:
        batch_op.drop_index("ix_webhook_delivery_due")

    op.drop_table("webhook_delivery")
    op.drop_table("api_token")
    op.drop_table("webhook_cursor")
    op.drop_table("webhook")
