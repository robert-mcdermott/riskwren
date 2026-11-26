"""Frameworks: sources of requirements, their trees, and baselines (CMP-01, CMP-03, CMP-05).

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "framework",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=120), nullable=True),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("publisher", sa.String(length=200), nullable=True),
        sa.Column("license", sa.String(length=200), nullable=True),
        sa.Column("text_policy", sa.String(length=24), nullable=False),
        sa.Column("attribution", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(length=300), nullable=True),
        sa.Column("built_from", sa.Text(), nullable=True),
        sa.Column("pack_version", sa.String(length=40), nullable=True),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requirement_count", sa.Integer(), nullable=False),
        sa.Column("citable_count", sa.Integer(), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('standard', 'regulation', 'agreement', 'internal')",
            name=op.f("ck_framework_kind"),
        ),
        sa.CheckConstraint("origin IN ('pack', 'local')", name=op.f("ck_framework_origin")),
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_framework_status")),
        sa.CheckConstraint(
            "text_policy IN ('verbatim', 'attributed', 'identifiers', 'summary', 'own')",
            name=op.f("ck_framework_text_policy"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["account.id"], name=op.f("fk_framework_created_by_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_framework")),
        sa.UniqueConstraint("key", name=op.f("uq_framework_key")),
    )
    op.create_table(
        "baseline",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("framework_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("requirement_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["framework_id"],
            ["framework.id"],
            name=op.f("fk_baseline_framework_id_framework"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_baseline")),
        sa.UniqueConstraint("framework_id", "key", name="uq_baseline_framework_key"),
    )
    op.create_table(
        "requirement",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("framework_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("guidance", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("is_citable", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.CheckConstraint("status IN ('active', 'withdrawn')", name=op.f("ck_requirement_status")),
        sa.ForeignKeyConstraint(
            ["framework_id"],
            ["framework.id"],
            name=op.f("fk_requirement_framework_id_framework"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["requirement.id"],
            name=op.f("fk_requirement_parent_id_requirement"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requirement")),
        sa.UniqueConstraint("framework_id", "code", name="uq_requirement_framework_code"),
    )
    with op.batch_alter_table("requirement", schema=None) as batch_op:
        batch_op.create_index(
            "ix_requirement_parent", ["framework_id", "parent_id", "position"], unique=False
        )
        batch_op.create_index("ix_requirement_sequence", ["framework_id", "sequence"], unique=False)

    op.create_table(
        "baseline_requirement",
        sa.Column("baseline_id", sa.Integer(), nullable=False),
        sa.Column("requirement_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["baseline_id"],
            ["baseline.id"],
            name=op.f("fk_baseline_requirement_baseline_id_baseline"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            ["requirement.id"],
            name=op.f("fk_baseline_requirement_requirement_id_requirement"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "baseline_id", "requirement_id", name=op.f("pk_baseline_requirement")
        ),
    )
    with op.batch_alter_table("baseline_requirement", schema=None) as batch_op:
        batch_op.create_index(
            "ix_baseline_requirement_requirement_id", ["requirement_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("baseline_requirement", schema=None) as batch_op:
        batch_op.drop_index("ix_baseline_requirement_requirement_id")

    op.drop_table("baseline_requirement")
    with op.batch_alter_table("requirement", schema=None) as batch_op:
        batch_op.drop_index("ix_requirement_sequence")
        batch_op.drop_index("ix_requirement_parent")

    op.drop_table("requirement")
    op.drop_table("baseline")
    op.drop_table("framework")
